"""
retrieval.py — V4 ChromaDB Retrieval Module for the Trust Before Text RAG system.

Responsibilities:
    1. Load the persistent ChromaDB collection
    2. Embed the query using sentence-transformers (multi-qa-MiniLM-L6-cos-v1)
    3. Query ChromaDB for the top-k most similar chunks
    4. Filter, normalise, and calibrate scores
    5. Return results in the exact format expected by the pipeline

V4 changes:
    ─ Score pipeline redesigned (removes magic constants):
        a) Raw cosine similarity = 1.0 - ChromaDB cosine distance
        b) Floor filter: discard chunks with cosine_sim < MIN_COSINE_THRESHOLD
        c) Linear calibration: maps [MIN_COSINE_THRESHOLD, 1.0] → [SCORE_FLOOR, 1.0]
           so that any chunk passing the floor gets a calibrated score ≥ SCORE_FLOOR.
           SCORE_FLOOR is set to MIN_AVG_SCORE_FOR_SUFFICIENCY (0.65) so that
           even a single relevant chunk satisfies the validation sufficiency check.
    ─ Each chunk now carries `relevance_score` = raw cosine similarity.
      validation.py Stage 3 uses this directly (embedding-based > TF-cosine).
    ─ Query embeddings are cached in a module-level dict to avoid redundant
      encode() calls across retry attempts for the same query.

Score mapping example (MIN_COSINE_THRESHOLD=0.40, SCORE_FLOOR=0.65):
    raw=0.40  →  calibrated=0.65   (floor)
    raw=0.56  →  calibrated=0.743
    raw=0.70  →  calibrated=0.833
    raw=0.85  →  calibrated=0.942
    raw=1.00  →  calibrated=1.000

Public API:
    retrieve(query: str, top_k: int = 5) -> list[dict]

Return format (compatible with orchestrator -> validation -> synthesis):
    [
        {
            "text":           str,    # chunk content
            "source":         str,    # originating document filename
            "chunk_id":       int,    # sequential chunk index
            "section":        str,    # section / page within the document
            "score":          float,  # calibrated score in [SCORE_FLOOR, 1.0]
            "relevance_score":float,  # raw cosine similarity in [MIN_COSINE_THRESHOLD, 1.0]
        },
        ...
    ]
"""

from __future__ import annotations

import chromadb
from sentence_transformers import SentenceTransformer

from ingestion import COLLECTION_NAME, EMBEDDING_MODEL
from retrieval_scoring import (
    MIN_COSINE_THRESHOLD,
    SCORE_FLOOR,
    calibrate_score,
    distance_to_raw_score,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DEFAULT_CHROMA_DIR:   str   = "chroma_db"

# Cached clients — avoid re-opening on every call
_client:     chromadb.PersistentClient | None = None
_collection: chromadb.Collection       | None = None
_model:      SentenceTransformer       | None = None

# Query embedding cache — avoids re-encoding the same string on retry
_embed_cache: dict[str, list[float]] = {}


# ===========================================================================
# Internal helpers
# ===========================================================================

def _get_client(chroma_dir: str = DEFAULT_CHROMA_DIR) -> chromadb.PersistentClient:
    """Lazy-init and cache the ChromaDB persistent client."""
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=chroma_dir)
    return _client


def _get_collection(chroma_dir: str = DEFAULT_CHROMA_DIR) -> chromadb.Collection:
    """Lazy-init and cache the ChromaDB collection handle."""
    global _collection
    if _collection is None:
        client = _get_client(chroma_dir)
        _collection = client.get_collection(COLLECTION_NAME)
    return _collection


def _get_model() -> SentenceTransformer:
    """Lazy-load and cache the sentence-transformer model."""
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def _embed_query(query: str) -> list[float]:
    """
    Embed a query string, using a module-level cache to avoid redundant
    encode() calls across pipeline retry attempts for the same query.
    """
    if query not in _embed_cache:
        model = _get_model()
        _embed_cache[query] = model.encode([query]).tolist()[0]
    return _embed_cache[query]


# ===========================================================================
# Public entry point
# ===========================================================================

def retrieve(
    query:      str,
    top_k:      int = 5,
    chroma_dir: str = DEFAULT_CHROMA_DIR,
) -> list[dict]:
    """
    Retrieve the top-k most relevant chunks for a query from ChromaDB.

    Parameters
    ----------
    query     : The user's search query (or a decomposed sub-query).
    top_k     : Maximum number of chunks to return.
    chroma_dir: Path to the ChromaDB persistence directory.

    Returns
    -------
    A list of chunk dicts ordered by descending calibrated score.
    Empty list if no chunks pass MIN_COSINE_THRESHOLD (off-topic query).

    Raises
    ------
    RuntimeError if the ChromaDB collection has not been ingested yet.
    """
    if not query.strip():
        return []

    # ── Embed the query (cached) ───────────────────────────────────────────
    query_embedding = _embed_query(query)

    # ── Query ChromaDB ────────────────────────────────────────────────────
    try:
        collection = _get_collection(chroma_dir)
    except Exception as exc:
        raise RuntimeError(
            f"ChromaDB collection '{COLLECTION_NAME}' not found in '{chroma_dir}'. "
            f"Run ingestion first: python ingestion.py\n"
            f"Original error: {exc}"
        )

    # Guard: request no more chunks than exist in the collection
    n_available = collection.count()
    n_results   = min(top_k, max(1, n_available))

    results = collection.query(
        query_embeddings = [query_embedding],
        n_results        = n_results,
        include          = ["documents", "metadatas", "distances"],
    )

    # ── Unpack results ────────────────────────────────────────────────────
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    chunks: list[dict] = []

    for doc, meta, dist in zip(documents, metadatas, distances):
        if not doc or not doc.strip():
            continue

        raw_score = distance_to_raw_score(dist)

        # ── Floor filter: skip off-topic chunks ───────────────────────────
        if raw_score < MIN_COSINE_THRESHOLD:
            continue

        # ── Calibrate: linear map to [SCORE_FLOOR, 1.0] ──────────────────
        calibrated = calibrate_score(raw_score)

        chunks.append({
            "text":            doc.strip(),
            "source":          meta.get("source",   "unknown"),
            "chunk_id":        meta.get("chunk_id", -1),
            "section":         meta.get("section",  "unknown"),
            "score":           calibrated,    # calibrated — used by validation Stage 5
            "relevance_score": raw_score,     # raw cosine sim — used by validation Stage 3
        })

    return chunks
