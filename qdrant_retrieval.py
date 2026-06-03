"""
Qdrant hybrid retrieval backend.

This module stores the same chunks used by ChromaDB in a local Qdrant
collection with two named vectors:
    - dense: sentence-transformers embeddings
    - sparse: a local BM25-style lexical sparse vector

Retrieval queries both vectors and combines their ranks with reciprocal rank
fusion (RRF). Returned chunks preserve the pipeline contract used by
validation.py while adding backend-specific diagnostics:
``dense_score``, ``sparse_score``, ``hybrid_score``, and ``retriever``.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
import atexit
from collections import Counter
from pathlib import Path
from typing import Iterable

from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

from ingestion import COLLECTION_NAME, EMBEDDING_MODEL
from retrieval_scoring import (
    MIN_COSINE_THRESHOLD,
    calibrate_score,
    raw_similarity_score,
)

DEFAULT_QDRANT_DIR: str = "qdrant_db"
DENSE_VECTOR_NAME: str = "dense"
SPARSE_VECTOR_NAME: str = "sparse"
SPARSE_MODEL_NAME: str = "local-bm25-v1"
MANIFEST_FILENAME: str = "manifest.json"
SPARSE_ENCODER_FILENAME: str = "sparse_encoder.json"

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?", re.IGNORECASE)
_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "trust-before-text-qdrant")

_client: QdrantClient | None = None
_model: SentenceTransformer | None = None
_sparse_encoder: dict | None = None
_embed_cache: dict[str, list[float]] = {}


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def _get_client(qdrant_dir: str = DEFAULT_QDRANT_DIR) -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(path=qdrant_dir)
    return _client


def _close_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


atexit.register(_close_client)


def _embed_query(query: str) -> list[float]:
    if query not in _embed_cache:
        _embed_cache[query] = _get_model().encode([query]).tolist()[0]
    return _embed_cache[query]


def _tokenize(text: str) -> list[str]:
    return [m.group(0).lower().strip("'") for m in _TOKEN_RE.finditer(text)]


def _file_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    h.update(filepath.read_bytes())
    return h.hexdigest()


def _load_manifest(qdrant_dir: Path) -> dict:
    manifest_path = qdrant_dir / MANIFEST_FILENAME
    if not manifest_path.exists():
        return {}
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_manifest(qdrant_dir: Path, manifest: dict) -> None:
    (qdrant_dir / MANIFEST_FILENAME).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _sparse_encoder_path(qdrant_dir: str | Path) -> Path:
    return Path(qdrant_dir) / SPARSE_ENCODER_FILENAME


def _fit_sparse_encoder(texts: list[str]) -> dict:
    tokenized = [_tokenize(text) for text in texts]
    doc_count = len(tokenized)
    doc_freq: Counter[str] = Counter()
    doc_lengths: list[int] = []

    for tokens in tokenized:
        doc_lengths.append(len(tokens))
        doc_freq.update(set(tokens))

    vocabulary = {term: idx + 1 for idx, term in enumerate(sorted(doc_freq))}
    idf = {
        term: math.log(1.0 + (doc_count - df + 0.5) / (df + 0.5))
        for term, df in doc_freq.items()
    }

    return {
        "model": SPARSE_MODEL_NAME,
        "doc_count": doc_count,
        "avg_doc_length": (sum(doc_lengths) / doc_count) if doc_count else 0.0,
        "vocabulary": vocabulary,
        "idf": idf,
        "k1": 1.5,
        "b": 0.75,
    }


def _save_sparse_encoder(qdrant_dir: Path, encoder: dict) -> None:
    _sparse_encoder_path(qdrant_dir).write_text(
        json.dumps(encoder, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _load_sparse_encoder(qdrant_dir: str | Path = DEFAULT_QDRANT_DIR) -> dict:
    global _sparse_encoder
    if _sparse_encoder is None:
        path = _sparse_encoder_path(qdrant_dir)
        if not path.exists():
            raise RuntimeError(
                f"Qdrant sparse encoder not found at '{path}'. "
                "Run: python main.py --ingest --retriever qdrant"
            )
        _sparse_encoder = json.loads(path.read_text(encoding="utf-8"))
    return _sparse_encoder


def _encode_sparse(text: str, encoder: dict, *, is_query: bool = False) -> models.SparseVector:
    tokens = _tokenize(text)
    if not tokens:
        return models.SparseVector(indices=[], values=[])

    tf = Counter(tokens)
    vocabulary: dict[str, int] = encoder["vocabulary"]
    idf: dict[str, float] = encoder["idf"]
    avgdl = float(encoder.get("avg_doc_length") or 1.0)
    k1 = float(encoder.get("k1", 1.5))
    b = float(encoder.get("b", 0.75))
    doc_len = max(1, len(tokens))

    indices: list[int] = []
    values: list[float] = []

    for term in sorted(tf):
        if term not in vocabulary:
            continue
        term_idf = float(idf.get(term, 0.0))
        if term_idf <= 0:
            continue
        count = float(tf[term])
        if is_query:
            weight = term_idf * count
        else:
            denom = count + k1 * (1.0 - b + b * doc_len / avgdl)
            weight = term_idf * ((count * (k1 + 1.0)) / denom)
        if weight > 0:
            indices.append(int(vocabulary[term]))
            values.append(float(weight))

    return models.SparseVector(indices=indices, values=values)


def _iter_source_files(data_dir: Path) -> list[Path]:
    supported = {".txt", ".pdf"}
    skip_prefixes = {"readme", "changelog", "license", "licence"}
    return sorted(
        f for f in data_dir.iterdir()
        if f.is_file()
        and f.suffix.lower() in supported
        and f.stem.lower() not in skip_prefixes
    )


def _point_id(source: str, chunk_id: int, section: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, f"{source}:{chunk_id}:{section}"))


def _delete_all_points(client: QdrantClient, collection_name: str) -> None:
    """Remove any residual points from a local collection before rebuilding."""
    while True:
        records, next_offset = client.scroll(
            collection_name=collection_name,
            limit=256,
            with_payload=False,
            with_vectors=False,
        )
        ids = [record.id for record in records]
        if ids:
            client.delete(collection_name=collection_name, points_selector=ids)
        if next_offset is None:
            break


def collection_is_empty(
    qdrant_dir: str | Path = DEFAULT_QDRANT_DIR,
    collection_name: str = COLLECTION_NAME,
) -> bool:
    qdrant_dir = Path(qdrant_dir)
    if not qdrant_dir.exists():
        return True

    client = QdrantClient(path=str(qdrant_dir))
    try:
        if not client.collection_exists(collection_name):
            return True
        return client.count(collection_name).count == 0
    except Exception:
        return True
    finally:
        client.close()


def get_manifest_model(qdrant_dir: str | Path = DEFAULT_QDRANT_DIR) -> str | None:
    manifest = _load_manifest(Path(qdrant_dir))
    return manifest.get("embedding_model")


def get_manifest_sparse_model(qdrant_dir: str | Path = DEFAULT_QDRANT_DIR) -> str | None:
    manifest = _load_manifest(Path(qdrant_dir))
    return manifest.get("sparse_model")


def ingest_documents(
    data_dir: str | Path = "data",
    qdrant_dir: str | Path = DEFAULT_QDRANT_DIR,
    collection_name: str = COLLECTION_NAME,
    force: bool = False,
) -> int:
    """
    Build or refresh the local Qdrant hybrid collection.

    Sparse IDF/vocabulary values depend on the full corpus, so Qdrant rebuilds
    the collection whenever source hashes change. For this project size that is
    simpler and safer than partial sparse-index mutation.
    """
    from ingestion import _iter_document_chunks

    global _sparse_encoder

    data_dir = Path(data_dir)
    qdrant_dir = Path(qdrant_dir)
    qdrant_dir.mkdir(parents=True, exist_ok=True)

    source_files = _iter_source_files(data_dir)
    if not source_files:
        print(f"  [Qdrant] WARNING: No .txt or .pdf files found in {data_dir}")
        return 0

    current_hashes = {f.name: _file_sha256(f) for f in source_files}
    manifest = {} if force else _load_manifest(qdrant_dir)
    already_current = (
        manifest.get("embedding_model") == EMBEDDING_MODEL
        and manifest.get("sparse_model") == SPARSE_MODEL_NAME
        and manifest.get("files") == current_hashes
        and not collection_is_empty(qdrant_dir, collection_name)
        and _sparse_encoder_path(qdrant_dir).exists()
    )

    if already_current:
        client = QdrantClient(path=str(qdrant_dir))
        try:
            count = client.count(collection_name).count
            print(f"  [Qdrant] Collection unchanged — {count} chunks ready.")
            return count
        finally:
            client.close()

    print("  [Qdrant] Rebuilding hybrid collection ...")
    chunks = list(_iter_document_chunks(data_dir, source_files))
    texts = [chunk[0] for chunk in chunks]
    if not texts:
        return 0

    model = _get_model()
    dense_embeddings = model.encode(texts, show_progress_bar=False).tolist()
    sparse_encoder = _fit_sparse_encoder(texts)
    sparse_vectors = [_encode_sparse(text, sparse_encoder) for text in texts]
    _sparse_encoder = sparse_encoder

    vector_size = len(dense_embeddings[0])
    client = QdrantClient(path=str(qdrant_dir))
    try:
        collection_config = {
            "vectors_config": {
                DENSE_VECTOR_NAME: models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE,
                )
            },
            "sparse_vectors_config": {
                SPARSE_VECTOR_NAME: models.SparseVectorParams(
                    index=models.SparseIndexParams(on_disk=False)
                )
            },
        }

        if client.collection_exists(collection_name):
            client.recreate_collection(
                collection_name=collection_name,
                **collection_config,
            )
            _delete_all_points(client, collection_name)
        else:
            client.create_collection(
                collection_name=collection_name,
                **collection_config,
            )

        points: list[models.PointStruct] = []
        for (text, source, chunk_id, section), dense, sparse in zip(
            chunks, dense_embeddings, sparse_vectors
        ):
            points.append(
                models.PointStruct(
                    id=_point_id(source, chunk_id, section),
                    vector={
                        DENSE_VECTOR_NAME: dense,
                        SPARSE_VECTOR_NAME: sparse,
                    },
                    payload={
                        "text": text,
                        "source": source,
                        "chunk_id": chunk_id,
                        "section": section,
                    },
                )
            )

        batch_size = 100
        for i in range(0, len(points), batch_size):
            client.upsert(collection_name=collection_name, points=points[i:i + batch_size])

        count = client.count(collection_name).count
    finally:
        client.close()

    _save_sparse_encoder(qdrant_dir, sparse_encoder)
    _save_manifest(qdrant_dir, {
        "embedding_model": EMBEDDING_MODEL,
        "sparse_model": SPARSE_MODEL_NAME,
        "files": current_hashes,
    })

    print(f"  [Qdrant] Done. {count} chunks stored in '{collection_name}'.")
    return count


def _query_dense(client: QdrantClient, query_embedding: list[float], limit: int) -> list:
    response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_embedding,
        using=DENSE_VECTOR_NAME,
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )
    return response.points


def _query_sparse(client: QdrantClient, sparse_query: models.SparseVector, limit: int) -> list:
    if not sparse_query.indices:
        return []
    response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=sparse_query,
        using=SPARSE_VECTOR_NAME,
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )
    return response.points


def _rrf_scores(result_sets: Iterable[list], k: int = 60) -> dict[str, float]:
    scores: dict[str, float] = {}
    for points in result_sets:
        for rank, point in enumerate(points, start=1):
            point_id = str(point.id)
            scores[point_id] = scores.get(point_id, 0.0) + (1.0 / (k + rank))
    max_possible = 2.0 / (k + 1.0)
    return {
        point_id: min(1.0, score / max_possible)
        for point_id, score in scores.items()
    }


def retrieve(
    query: str,
    top_k: int = 5,
    qdrant_dir: str = DEFAULT_QDRANT_DIR,
    prefetch_k: int | None = None,
) -> list[dict]:
    """Retrieve top-k chunks from Qdrant using dense+sparse hybrid ranking."""
    if not query.strip():
        return []

    query_embedding = _embed_query(query)
    encoder = _load_sparse_encoder(qdrant_dir)
    sparse_query = _encode_sparse(query, encoder, is_query=True)
    limit = max(top_k, prefetch_k or top_k * 4)

    try:
        client = _get_client(qdrant_dir)
        if not client.collection_exists(COLLECTION_NAME):
            raise RuntimeError(f"Collection '{COLLECTION_NAME}' does not exist")
        dense_points = _query_dense(client, query_embedding, limit)
        sparse_points = _query_sparse(client, sparse_query, limit)
    except Exception as exc:
        raise RuntimeError(
            f"Qdrant collection '{COLLECTION_NAME}' not ready in '{qdrant_dir}'. "
            "Run ingestion first: python main.py --ingest --retriever qdrant\n"
            f"Original error: {exc}"
        )

    dense_scores = {str(point.id): raw_similarity_score(point.score) for point in dense_points}
    sparse_scores_raw = {str(point.id): float(point.score) for point in sparse_points}
    max_sparse = max(sparse_scores_raw.values(), default=0.0)
    sparse_scores = {
        point_id: (score / max_sparse if max_sparse > 0 else 0.0)
        for point_id, score in sparse_scores_raw.items()
    }
    hybrid_scores = _rrf_scores([dense_points, sparse_points])

    point_by_id = {str(point.id): point for point in dense_points}
    point_by_id.update({str(point.id): point for point in sparse_points})

    ranked_ids = sorted(
        hybrid_scores,
        key=lambda point_id: (
            hybrid_scores.get(point_id, 0.0),
            dense_scores.get(point_id, 0.0),
            sparse_scores.get(point_id, 0.0),
        ),
        reverse=True,
    )

    chunks: list[dict] = []
    for point_id in ranked_ids:
        point = point_by_id[point_id]
        payload = point.payload or {}
        dense_score = dense_scores.get(point_id, 0.0)
        sparse_score = sparse_scores.get(point_id, 0.0)
        hybrid_score = hybrid_scores.get(point_id, 0.0)

        # RRF is a rank-fusion signal, not semantic similarity. Use it only
        # for ordering; validation relevance must stay tied to dense cosine so
        # lexical-only/off-topic matches cannot inflate sufficiency.
        raw_score = raw_similarity_score(dense_score)

        if raw_score < MIN_COSINE_THRESHOLD:
            continue

        text = str(payload.get("text", "")).strip()
        if not text:
            continue

        chunks.append({
            "text": text,
            "source": payload.get("source", "unknown"),
            "chunk_id": payload.get("chunk_id", -1),
            "section": payload.get("section", "unknown"),
            "score": calibrate_score(raw_score),
            "relevance_score": raw_score,
            "dense_score": round(dense_score, 6),
            "sparse_score": round(sparse_score, 6),
            "hybrid_score": round(hybrid_score, 6),
            "retriever": "qdrant_hybrid",
        })

        if len(chunks) >= top_k:
            break

    return chunks
