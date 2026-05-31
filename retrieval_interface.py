"""
retrieval_interface.py — Retrieval interface for the Trust Before Text RAG system.

This module is the single import point used by orchestrator.py:

    from retrieval_interface import retrieve

It delegates to the real ChromaDB retrieval backend implemented in retrieval.py.
The function signature and return format are unchanged from the stub so no
other module requires modification.

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

from retrieval import retrieve as _chroma_retrieve


def retrieve(query: str, top_k: int = 5) -> list[dict]:
    """
    Retrieve the most relevant document chunks for a given query.

    Parameters
    ----------
    query  : The user's search query (or a decomposed sub-query from the orchestrator).
    top_k  : Maximum number of chunks to return.

    Returns
    -------
    A list of chunk dicts ordered by descending similarity score.
    Each dict contains: text, source, chunk_id, section, score.
    """
    return _chroma_retrieve(query, top_k=top_k)
