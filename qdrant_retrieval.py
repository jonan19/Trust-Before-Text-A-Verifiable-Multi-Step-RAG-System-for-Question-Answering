"""
Qdrant hybrid retrieval backend.

This module stores the same chunks used by ChromaDB in a local Qdrant
collection with three named vector types:
    - dense: all-MiniLM-L6-v2 sentence embeddings
    - sparse: local BM25-style lexical vectors with Qdrant's IDF modifier
    - multi: answerai-colbert-small-v1 token-level multivectors

Retrieval prefetches dense+sparse candidates and reranks them with the
ColBERT multivector. Returned chunks preserve the pipeline contract used by
validation.py while adding backend-specific diagnostics:
``dense_score``, ``sparse_score``, ``rrf_score``, ``colbert_score``,
``hybrid_score``, and ``retriever``.
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
from typing import Any, Iterable, Sequence

from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

from ingestion import COLLECTION_NAME
from retrieval_scoring import (
    MIN_COSINE_THRESHOLD,
    calibrate_score,
    raw_similarity_score,
)

DEFAULT_QDRANT_DIR: str = "qdrant_db"
DENSE_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
MULTI_MODEL_NAME: str = "answerdotai/answerai-colbert-small-v1"
SPARSE_MODEL_NAME: str = "qdrant/bm25-local-idf-v1"
DENSE_VECTOR_NAME: str = "dense"
SPARSE_VECTOR_NAME: str = "sparse"
MULTI_VECTOR_NAME: str = "multi"
DENSE_VECTOR_SIZE: int = 384
MULTI_VECTOR_SIZE: int = 96
MANIFEST_FILENAME: str = "manifest.json"
SPARSE_ENCODER_FILENAME: str = "sparse_encoder.json"
DEFAULT_PREFETCH_LIMIT: int = 20

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?", re.IGNORECASE)
_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "trust-before-text-qdrant")

_client: QdrantClient | None = None
_dense_model: SentenceTransformer | None = None
_colbert_components: tuple[Any, Any, Any, Any] | None = None
_sparse_encoder: dict | None = None
_dense_embed_cache: dict[str, list[float]] = {}
_colbert_embed_cache: dict[str, list[list[float]]] = {}


def _get_dense_model() -> SentenceTransformer:
    global _dense_model
    if _dense_model is None:
        _dense_model = SentenceTransformer(DENSE_MODEL_NAME)
    return _dense_model


def _get_colbert_components() -> tuple[Any, Any, Any, Any]:
    """
    Load the ColBERT encoder locally.

    The AnswerAI checkpoint stores the 96-dimensional ColBERT projection as
    ``linear.weight``. Loading it through a plain SentenceTransformer token
    embedding path exposes the 384-dimensional base BERT states, so we apply
    the learned projection explicitly instead of truncating vectors.
    """
    global _colbert_components
    if _colbert_components is None:
        import torch
        from huggingface_hub import hf_hub_download
        from safetensors.torch import load_file
        from transformers import AutoModel, AutoTokenizer
        from transformers import logging as transformers_logging

        tokenizer = AutoTokenizer.from_pretrained(MULTI_MODEL_NAME)
        previous_verbosity = transformers_logging.get_verbosity()
        transformers_logging.set_verbosity_error()
        try:
            model = AutoModel.from_pretrained(MULTI_MODEL_NAME)
        finally:
            transformers_logging.set_verbosity(previous_verbosity)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model.to(device)
        model.eval()

        projection = torch.nn.Linear(
            model.config.hidden_size,
            MULTI_VECTOR_SIZE,
            bias=False,
        )
        checkpoint_path = hf_hub_download(MULTI_MODEL_NAME, "model.safetensors")
        checkpoint = load_file(checkpoint_path, device="cpu")
        if "linear.weight" not in checkpoint:
            raise RuntimeError(
                f"ColBERT projection 'linear.weight' not found in {MULTI_MODEL_NAME}"
            )
        projection.weight.data.copy_(checkpoint["linear.weight"])
        projection.to(device)
        projection.eval()

        _colbert_components = (tokenizer, model, projection, device)
    return _colbert_components


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


def _embed_dense_query(query: str) -> list[float]:
    if query not in _dense_embed_cache:
        _dense_embed_cache[query] = _get_dense_model().encode(
            [query],
            show_progress_bar=False,
        ).tolist()[0]
    return _dense_embed_cache[query]


def _embed_colbert_texts(texts: Sequence[str]) -> list[list[list[float]]]:
    if not texts:
        return []

    import torch

    tokenizer, model, projection, device = _get_colbert_components()
    multivectors: list[list[list[float]]] = []
    batch_size = 8

    for start in range(0, len(texts), batch_size):
        batch = list(texts[start:start + batch_size])
        tokenized = tokenizer(
            batch,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
            return_special_tokens_mask=True,
        )
        special_tokens_mask = tokenized.pop("special_tokens_mask").to(device).bool()
        tokenized = {key: value.to(device) for key, value in tokenized.items()}

        with torch.no_grad():
            output = model(**tokenized)
            projected = projection(output.last_hidden_state)
            projected = torch.nn.functional.normalize(projected, p=2, dim=-1)

        attention_mask = tokenized["attention_mask"].bool()
        keep_mask = attention_mask & ~special_tokens_mask

        for token_vectors, token_mask, fallback_mask in zip(
            projected,
            keep_mask,
            attention_mask,
        ):
            selected = token_vectors[token_mask]
            if selected.numel() == 0:
                selected = token_vectors[fallback_mask]
            matrix = selected.detach().cpu().to(torch.float32).tolist()
            if not matrix:
                raise ValueError("ColBERT produced no token embeddings for a text")
            if len(matrix[0]) != MULTI_VECTOR_SIZE:
                raise ValueError(
                    f"Expected ColBERT vector size {MULTI_VECTOR_SIZE}, got {len(matrix[0])}. "
                    f"Model: {MULTI_MODEL_NAME}"
                )
            multivectors.append(matrix)

    return multivectors


def _embed_colbert_query(query: str) -> list[list[float]]:
    if query not in _colbert_embed_cache:
        _colbert_embed_cache[query] = _embed_colbert_texts([query])[0]
    return _colbert_embed_cache[query]


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
    return {
        "model": SPARSE_MODEL_NAME,
        "doc_count": doc_count,
        "avg_doc_length": (sum(doc_lengths) / doc_count) if doc_count else 0.0,
        "vocabulary": vocabulary,
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
    avgdl = float(encoder.get("avg_doc_length") or 1.0)
    k1 = float(encoder.get("k1", 1.5))
    b = float(encoder.get("b", 0.75))
    doc_len = max(1, len(tokens))

    indices: list[int] = []
    values: list[float] = []

    for term in sorted(tf):
        if term not in vocabulary:
            continue
        count = float(tf[term])
        if is_query:
            weight = count
        else:
            denom = count + k1 * (1.0 - b + b * doc_len / avgdl)
            weight = (count * (k1 + 1.0)) / denom
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


def get_manifest_multi_model(qdrant_dir: str | Path = DEFAULT_QDRANT_DIR) -> str | None:
    manifest = _load_manifest(Path(qdrant_dir))
    return manifest.get("multi_model")


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
        manifest.get("embedding_model") == DENSE_MODEL_NAME
        and manifest.get("sparse_model") == SPARSE_MODEL_NAME
        and manifest.get("multi_model") == MULTI_MODEL_NAME
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

    dense_embeddings = _get_dense_model().encode(
        texts,
        show_progress_bar=False,
    ).tolist()
    multi_embeddings = _embed_colbert_texts(texts)
    sparse_encoder = _fit_sparse_encoder(texts)
    sparse_vectors = [_encode_sparse(text, sparse_encoder) for text in texts]
    _sparse_encoder = sparse_encoder

    vector_size = len(dense_embeddings[0])
    if vector_size != DENSE_VECTOR_SIZE:
        raise ValueError(
            f"Expected dense vector size {DENSE_VECTOR_SIZE}, got {vector_size}. "
            f"Model: {DENSE_MODEL_NAME}"
        )

    client = QdrantClient(path=str(qdrant_dir))
    try:
        collection_config = {
            "vectors_config": {
                DENSE_VECTOR_NAME: models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE,
                ),
                MULTI_VECTOR_NAME: models.VectorParams(
                    size=MULTI_VECTOR_SIZE,
                    distance=models.Distance.COSINE,
                    multivector_config=models.MultiVectorConfig(
                        comparator=models.MultiVectorComparator.MAX_SIM,
                    ),
                    hnsw_config=models.HnswConfigDiff(m=0),
                ),
            },
            "sparse_vectors_config": {
                SPARSE_VECTOR_NAME: models.SparseVectorParams(
                    index=models.SparseIndexParams(on_disk=False),
                    modifier=models.Modifier.IDF,
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
        for (text, source, chunk_id, section), dense, sparse, multi in zip(
            chunks, dense_embeddings, sparse_vectors, multi_embeddings
        ):
            points.append(
                models.PointStruct(
                    id=_point_id(source, chunk_id, section),
                    vector={
                        DENSE_VECTOR_NAME: dense,
                        SPARSE_VECTOR_NAME: sparse,
                        MULTI_VECTOR_NAME: multi,
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
        "embedding_model": DENSE_MODEL_NAME,
        "sparse_model": SPARSE_MODEL_NAME,
        "multi_model": MULTI_MODEL_NAME,
        "files": current_hashes,
    })

    print(f"  [Qdrant] Done. {count} chunks stored in '{collection_name}'.")
    return count


def _query_dense(
    client: QdrantClient,
    collection_name: str,
    query_embedding: list[float],
    limit: int,
) -> list:
    response = client.query_points(
        collection_name=collection_name,
        query=query_embedding,
        using=DENSE_VECTOR_NAME,
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )
    return response.points


def _query_sparse(
    client: QdrantClient,
    collection_name: str,
    sparse_query: models.SparseVector,
    limit: int,
) -> list:
    if not sparse_query.indices:
        return []
    response = client.query_points(
        collection_name=collection_name,
        query=sparse_query,
        using=SPARSE_VECTOR_NAME,
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )
    return response.points


def _query_hybrid_rerank(
    client: QdrantClient,
    collection_name: str,
    query_embedding: list[float],
    sparse_query: models.SparseVector,
    multi_query: list[list[float]],
    prefetch_limit: int,
    rerank_limit: int,
) -> list:
    prefetch: list[models.Prefetch] = [
        models.Prefetch(
            query=query_embedding,
            using=DENSE_VECTOR_NAME,
            limit=prefetch_limit,
        )
    ]
    if sparse_query.indices:
        prefetch.append(
            models.Prefetch(
                query=sparse_query,
                using=SPARSE_VECTOR_NAME,
                limit=prefetch_limit,
            )
        )

    response = client.query_points(
        collection_name=collection_name,
        prefetch=prefetch,
        query=multi_query,
        using=MULTI_VECTOR_NAME,
        with_payload=True,
        with_vectors=[DENSE_VECTOR_NAME],
        limit=rerank_limit,
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


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    dot = 0.0
    left_norm = 0.0
    right_norm = 0.0
    for a, b in zip(left, right):
        af = float(a)
        bf = float(b)
        dot += af * bf
        left_norm += af * af
        right_norm += bf * bf
    if left_norm <= 0.0 or right_norm <= 0.0:
        return 0.0
    return dot / (math.sqrt(left_norm) * math.sqrt(right_norm))


def _named_vector(point: object, vector_name: str) -> list[float] | None:
    vectors = getattr(point, "vector", None)
    if isinstance(vectors, dict):
        value = vectors.get(vector_name)
        if isinstance(value, list):
            return value
    return None


def retrieve(
    query: str,
    top_k: int = 5,
    qdrant_dir: str = DEFAULT_QDRANT_DIR,
    prefetch_k: int | None = None,
) -> list[dict]:
    """Retrieve top-k chunks from Qdrant using dense+sparse prefetch and ColBERT reranking."""
    if not query.strip():
        return []

    query_embedding = _embed_dense_query(query)
    encoder = _load_sparse_encoder(qdrant_dir)
    sparse_query = _encode_sparse(query, encoder, is_query=True)
    multi_query = _embed_colbert_query(query)
    prefetch_limit = max(top_k, prefetch_k or DEFAULT_PREFETCH_LIMIT)
    rerank_limit = max(top_k, min(prefetch_limit * 2, top_k * 4))

    try:
        client = _get_client(qdrant_dir)
        if not client.collection_exists(COLLECTION_NAME):
            raise RuntimeError(f"Collection '{COLLECTION_NAME}' does not exist")
        dense_points = _query_dense(client, COLLECTION_NAME, query_embedding, prefetch_limit)
        sparse_points = _query_sparse(client, COLLECTION_NAME, sparse_query, prefetch_limit)
        reranked_points = _query_hybrid_rerank(
            client=client,
            collection_name=COLLECTION_NAME,
            query_embedding=query_embedding,
            sparse_query=sparse_query,
            multi_query=multi_query,
            prefetch_limit=prefetch_limit,
            rerank_limit=rerank_limit,
        )
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

    colbert_scores_raw = {str(point.id): float(point.score) for point in reranked_points}
    max_colbert = max(colbert_scores_raw.values(), default=0.0)

    chunks: list[dict] = []
    for point in reranked_points:
        point_id = str(point.id)
        payload = point.payload or {}
        dense_score = dense_scores.get(point_id)
        if dense_score is None:
            dense_vector = _named_vector(point, DENSE_VECTOR_NAME)
            dense_score = raw_similarity_score(
                _cosine_similarity(query_embedding, dense_vector)
            ) if dense_vector else 0.0
        sparse_score = sparse_scores.get(point_id, 0.0)
        rrf_score = hybrid_scores.get(point_id, 0.0)
        colbert_score = colbert_scores_raw.get(point_id, 0.0)
        hybrid_score = (colbert_score / max_colbert) if max_colbert > 0 else 0.0

        # ColBERT and RRF are ranking signals, not calibrated semantic
        # similarity. Validation relevance stays tied to dense cosine so
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
            "rrf_score": round(rrf_score, 6),
            "colbert_score": round(colbert_score, 6),
            "hybrid_score": round(hybrid_score, 6),
            "retriever": "qdrant_hybrid_colbert",
        })

        if len(chunks) >= top_k:
            break

    return chunks
