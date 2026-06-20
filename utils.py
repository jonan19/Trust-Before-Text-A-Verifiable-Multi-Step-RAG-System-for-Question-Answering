"""
utils.py — Shared utility functions for the Trust Before Text RAG system (V3).

Public API:
    clean_text(text)                        → str
    compute_query_similarity(query, text)   → float   [NEW in V3]
    format_abstention_response(reason)      → dict    [NEW in V3]
    format_chunk_as_context(chunk)          → str
    build_context_block(chunks)             → str
    print_separator(title, width)           → None

V4 changes:
    - LRU cache (maxsize=512) on compute_query_similarity and compute_chunk_similarity
      avoids recomputing identical pair similarities within the same pipeline run
      (Stage 2 dedup and Stage 4 conflict detection are O(n²) callers).
    - clean_text now normalises Unicode (NFKC) before whitespace collapsing so
      that exotic whitespace characters and ligatures are handled consistently.
"""

from __future__ import annotations

import math
import re
import unicodedata
from functools import lru_cache
from typing import Optional


# ===========================================================================
# Text cleaning
# ===========================================================================

def clean_text(text: str) -> str:
    """
    Normalise Unicode (NFKC), strip leading/trailing whitespace, and
    collapse all internal whitespace (including non-breaking spaces) to a
    single ASCII space.
    """
    # NFKC: normalise ligatures (ﬁ→fi), exotic spaces, etc.
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", text.strip())


# ===========================================================================
# Similarity helpers  (V3 — shared so validation.py can import them)
# ===========================================================================

def _token_vector(text: str) -> dict[str, float]:
    """
    Build a raw term-frequency vector (no IDF) from *text*.

    Tokens are lowercased; punctuation is stripped so that 'policy.'
    and 'policy' both map to the same key.
    """
    tokens = re.sub(r"[^\w\s]", "", text.lower()).split()
    vec: dict[str, float] = {}
    for t in tokens:
        vec[t] = vec.get(t, 0.0) + 1.0
    return vec


def _cosine(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    """Cosine similarity between two sparse term-frequency vectors."""
    dot   = sum(vec_a.get(t, 0.0) * v for t, v in vec_b.items())
    mag_a = math.sqrt(sum(v * v for v in vec_a.values()))
    mag_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a * mag_b)


@lru_cache(maxsize=512)
def compute_query_similarity(query: str, text: str) -> float:
    """
    Lightweight relevance score: cosine similarity between the query token
    vector and the chunk text token vector.

    Used as a fallback by Relevance Filtering (Stage 3) in validation.py
    when chunks do not yet carry an embedding-based relevance_score.

    LRU-cached: identical (query, text) pairs across pipeline retries are
    computed only once.

    Returns a float in [0, 1].
    """
    return _cosine(_token_vector(query), _token_vector(text))


@lru_cache(maxsize=512)
def compute_chunk_similarity(text_a: str, text_b: str) -> float:
    """
    Cosine similarity between two chunk texts.

    Used by Duplicate Removal (Stage 2) and Conflict Detection (Stage 4).

    LRU-cached: the O(n²) Stage 2 and Stage 4 loops frequently revisit
    the same pairs, especially across retry attempts.
    """
    return _cosine(_token_vector(text_a), _token_vector(text_b))


# ===========================================================================
# Abstention helpers  (V3)
# ===========================================================================

def format_abstention_response(reason: str) -> dict:
    """
    Build the standard abstention response dict.

    Parameters
    ----------
    reason : A short machine-readable label, e.g. "conflict" or "insufficient".

    Returns
    -------
    {
        "status" : "abstain",
        "reason" : reason,
        "answer" : <human-readable explanation>,
        "citations": []
    }
    """
    messages = {
        "conflict": (
            "I cannot provide a reliable answer because the retrieved evidence "
            "contains contradictory information. Please refine your query or "
            "consult the source documents directly."
        ),
        "insufficient": (
            "I cannot provide a reliable answer because the retrieved evidence "
            "is insufficient to answer your query."
        ),
        "no_relevant_evidence": (
            "I cannot provide a reliable answer because none of the retrieved "
            "evidence is relevant enough to your query."
        ),
    }
    answer = messages.get(
        reason,
        f"I cannot provide a reliable answer. Reason: {reason}.",
    )
    return {
        "status"   : "abstain",
        "reason"   : reason,
        "answer"   : answer,
        "citations": [],
    }


# ===========================================================================
# Context formatting (used by orchestrator + synthesis)
# ===========================================================================

def format_chunk_as_context(chunk: dict) -> str:
    """
    Format a single validated chunk for the LLM context block.

    Score is intentionally omitted — it is an internal system metric that
    the LLM does not need and that may confuse it.

    Example output:
        [Source: policy.pdf | Section: Leave Policy]
        Employees are entitled to 20 days of leave.
    """
    source  = chunk.get("source", "unknown")
    section = chunk.get("section", "unknown")
    text    = chunk.get("text", "").strip()
    return f"[Source: {source} | Section: {section}]\n{text}"


def build_context_block(chunks: list[dict]) -> str:
    """Join multiple formatted chunks into a single context string for the LLM."""
    if not chunks:
        return ""
    return "\n\n".join(format_chunk_as_context(c) for c in chunks)


# ===========================================================================
# Console helpers
# ===========================================================================

def print_separator(title: Optional[str] = None, width: int = 60) -> None:
    """Pretty-print a separator line, optionally with a centred title."""
    if title:
        pad   = max(0, width - len(title) - 2)
        left  = pad // 2
        right = pad - left
        print(f"{'-' * left} {title} {'-' * right}")
    else:
        print("-" * width)
