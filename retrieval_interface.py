
"""
retrieval_interface.py — Stub interface for the external retrieval module.

The README states that the retrieval module and vector database are
ALREADY IMPLEMENTED EXTERNALLY.  This file provides:
  1. The expected function signature so the rest of the system can import it.
  2. A deterministic mock implementation for local development / testing.

In production, replace the body of `retrieve()` with the real implementation
(e.g. a call to your Chroma / FAISS / Weaviate retrieval function).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Production hook
# ---------------------------------------------------------------------------
# Uncomment and adapt when wiring up the real retrieval backend:
#
# from your_retrieval_package import retrieve as _real_retrieve
#
# def retrieve(query: str, top_k: int = 5) -> list[dict]:
#     return _real_retrieve(query, top_k=top_k)

# ---------------------------------------------------------------------------
# Mock implementation (used until real retrieval is wired in)
# ---------------------------------------------------------------------------

_MOCK_CORPUS: list[dict] = [
    {
        "text": "Employees are entitled to 20 days of annual leave per calendar year.",
        "source": "policy.pdf",
        "section": "Leave Policy",
        "score": 0.91,
    },
    {
        "text": "Annual leave for employees is capped at 15 days.",
        "source": "handbook_v1.pdf",
        "section": "Leave Policy",
        "score": 0.78,
    },
    {
        "text": "Employees may work remotely up to 2 days per week with manager approval.",
        "source": "handbook.pdf",
        "section": "Remote Work",
        "score": 0.88,
    },
    {
        "text": "Remote work arrangements require prior written consent from HR.",
        "source": "policy.pdf",
        "section": "Remote Work",
        "score": 0.82,
    },
    {
        "text": "All employees must complete mandatory safety training annually.",
        "source": "compliance.pdf",
        "section": "Safety",
        "score": 0.73,
    },
    {
        "text": "Salary reviews are conducted twice a year in April and October.",
        "source": "hr_guide.pdf",
        "section": "Compensation",
        "score": 0.85,
    },
]


def retrieve(query: str, top_k: int = 5) -> list[dict]:
    """
    Retrieve the most relevant document chunks for a given query.

    Parameters
    ----------
    query   : The user's search query (or a decomposed sub-query).
    top_k   : Maximum number of chunks to return.

    Returns
    -------
    A list of chunk dicts, each with keys:
        - text    : str   — the chunk content
        - source  : str   — originating document filename
        - section : str   — section / heading inside the document
        - score   : float — relevance score in [0, 1]
    """
    # --- Mock: keyword-based scoring so results vary by query ---
    query_lower = query.lower()
    scored: list[tuple[float, dict]] = []

    for chunk in _MOCK_CORPUS:
        chunk_text_lower  = chunk["text"].lower()
        chunk_section_lower = chunk["section"].lower()

        keyword_overlap = sum(
            1 for word in query_lower.split()
            if len(word) > 3 and (word in chunk_text_lower or word in chunk_section_lower)
        )

        # Only include chunks that have at least some relevance to the query
        if keyword_overlap == 0:
            # Very low base score — topic not mentioned at all
            boosted_score = chunk["score"] * 0.5
        else:
            boosted_score = chunk["score"] + keyword_overlap * 0.03

        scored.append((boosted_score, chunk, keyword_overlap))

    scored.sort(key=lambda x: x[0], reverse=True)

    # Filter to only chunks with at least partial relevance for off-topic queries
    best_overlap = scored[0][2] if scored else 0
    if best_overlap == 0:
        # Completely off-topic: return at most 1 chunk with a degraded score
        result = [{**scored[0][1], "score": scored[0][0]}] if scored else []
        return result[:1]

    return [{**chunk, "score": round(score, 4)} for score, chunk, _ in scored[:top_k]]

