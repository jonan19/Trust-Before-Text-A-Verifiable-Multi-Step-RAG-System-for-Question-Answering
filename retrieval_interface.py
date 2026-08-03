"""
retrieval_interface.py — Retrieval interface for the Trust Before Text RAG system.

This module is the single import point used by orchestrator.py:

    from retrieval_interface import retrieve

It delegates to the configured retrieval backend. Qdrant hybrid retrieval is
the active backend. Set RAG_RETRIEVER=qdrant (default) in your .env file.

Return format:
    [
        {
            "text":     str,    # chunk content
            "source":   str,    # document filename
            "chunk_id": int,    # chunk index within the document
            "section":  str,    # section / page label
            "score":    float,  # similarity score in (0, 1]
        },
        ...
    ]
"""

from __future__ import annotations

import os

from qdrant_retrieval import retrieve as _qdrant_retrieve

SUPPORTED_RETRIEVERS: tuple[str, ...] = ("qdrant",)


def active_retriever() -> str:
    """Return the configured retrieval backend name."""
    backend = os.getenv("RAG_RETRIEVER", "qdrant").strip().lower()
    # Normalise aliases
    if backend in {"qdrant_hybrid", "hybrid"}:
        backend = "qdrant"
    if backend not in SUPPORTED_RETRIEVERS:
        raise ValueError(
            f"Unsupported RAG_RETRIEVER='{backend}'. "
            f"Choose one of: {', '.join(SUPPORTED_RETRIEVERS)}"
        )
    return backend


def retrieve(query: str, top_k: int = 5, backend: str | None = None) -> list[dict]:
    """
    Retrieve the most relevant document chunks for a given query.

    Parameters
    ----------
    query  : The user's search query (or a decomposed sub-query from the orchestrator).
    top_k  : Maximum number of chunks to return.
    backend: Override the active backend (optional). Useful for testing.

    Returns
    -------
    A list of chunk dicts ordered by descending similarity score.
    Each dict contains: text, source, chunk_id, section, score.
    """
    selected = (backend or active_retriever()).strip().lower()
    if selected in {"qdrant_hybrid", "hybrid"}:
        selected = "qdrant"

    if selected == "qdrant":
        return _qdrant_retrieve(query, top_k=top_k)

    raise ValueError(
        f"Unsupported retrieval backend '{selected}'. "
        f"Choose one of: {', '.join(SUPPORTED_RETRIEVERS)}"
    )
