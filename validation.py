"""
validation.py — V3 Validation Pipeline for the Trust Before Text RAG system.

Pipeline (7 stages, all deterministic — no LLM):

    Stage 1  Chunk Normalization        remove empty chunks, normalise whitespace
    Stage 2  Duplicate Removal          cosine-sim dedup, keep highest-scoring copy
    Stage 3  Relevance Filtering        drop chunks below query-relevance threshold
    Stage 4  Evidence Consistency       detect contradictions (keyword + numeric)
    Stage 5  Evidence Sufficiency       heuristic: count + avg-score + coverage
    Stage 6  Evidence Structuring       add rank field, enforce descending-score order
    Stage 7  Abstention Decision        named reason: "conflict" | "insufficient" | None

Public interface:
    validate(chunks, query="") -> dict

Return schema:
    {
        "cleaned_chunks"    : list[dict],   # structured, ranked evidence
        "conflict_flag"     : bool,
        "sufficiency_flag"  : bool,
        "confidence_score"  : float,        # top-weighted avg retrieval score
        "abstention_reason" : str | None,   # "conflict" | "insufficient" | None
        "relevant_count"    : int,          # chunks passing relevance filter
    }
"""

from __future__ import annotations

import re
from typing import Optional

from utils import clean_text, compute_query_similarity, compute_chunk_similarity

# ---------------------------------------------------------------------------
# Thresholds — tune as needed
# ---------------------------------------------------------------------------
DUPLICATE_SIM_THRESHOLD: float  = 0.90   # cosine sim >= this -> duplicate
RELEVANCE_RATIO_THRESHOLD: float = 0.30  # keep chunk if sim >= best_sim * ratio (broad enough for multi-topic queries)
MIN_RELEVANCE_SCORE: float       = 0.05  # absolute floor (catches fully off-topic chunks)
MIN_CHUNKS_FOR_SUFFICIENCY: int  = 1     # at least this many relevant chunks needed
MIN_AVG_SCORE_FOR_SUFFICIENCY: float = 0.65  # avg retrieval score threshold
CONFLICT_SIM_THRESHOLD: float   = 0.55  # semantic overlap floor for conflict check

# ---------------------------------------------------------------------------
# Antonym / contradiction pairs  (expanded in V3)
# Each tuple: (negative_term, positive_term)
# The detector fires when one chunk contains the negative and the other the
# positive (or vice-versa) within the same semantic neighbourhood.
# ---------------------------------------------------------------------------
_CONTRADICTION_PAIRS: list[tuple[str, str]] = [
    # Policy stance
    ("prohibited",    "allowed"),
    ("not allowed",   "allowed"),
    ("banned",        "permitted"),
    ("forbidden",     "permitted"),
    ("disallowed",    "permitted"),
    # Obligation
    ("mandatory",     "optional"),
    ("required",      "not required"),
    ("compulsory",    "voluntary"),
    ("must",          "may"),
    # Capability
    ("cannot",        "can"),
    ("cannot",        "able to"),
    ("unable to",     "able to"),
    # Logical
    ("never",         "always"),
    ("no",            "yes"),
    ("not",           "is"),
    # Approval workflow
    ("deny",          "approve"),
    ("rejected",      "approved"),
    ("refused",       "accepted"),
    # Temporal
    ("terminated",    "active"),
    ("expired",       "valid"),
    ("discontinued",  "available"),
]


# ===========================================================================
# Internal helpers
# ===========================================================================

def _extract_numbers(text: str) -> list[float]:
    """Extract all numeric values (int or decimal) from *text*."""
    return [float(n) for n in re.findall(r"\b\d+(?:\.\d+)?\b", text)]


def _has_numeric_contradiction(text_a: str, text_b: str) -> bool:
    """
    Return True if both texts contain numbers and their PRIMARY numeric
    values differ by more than a rounding epsilon.

    Scoped to same-section pairs only in the caller to reduce false positives.
    """
    nums_a = _extract_numbers(text_a)
    nums_b = _extract_numbers(text_b)
    if not nums_a or not nums_b:
        return False
    return abs(nums_a[0] - nums_b[0]) > 0.01


def _has_keyword_contradiction(text_a: str, text_b: str) -> bool:
    """
    Check whether the two texts express contradictory stances using the
    expanded _CONTRADICTION_PAIRS list.

    Logic: for each (neg, pos) pair —
        - If A contains *neg* and B contains *pos*  (but NOT neg) → flag
        - If B contains *neg* and A contains *pos*  (but NOT neg) → flag
    """
    a, b = text_a.lower(), text_b.lower()
    for neg, pos in _CONTRADICTION_PAIRS:
        a_neg = neg in a
        b_neg = neg in b
        a_pos = pos in a
        b_pos = pos in b

        # Directional: one clearly asserts neg, the other clearly asserts pos
        if (a_neg and not b_neg and b_pos) or (b_neg and not a_neg and a_pos):
            return True
    return False


def _weighted_confidence(chunks: list[dict]) -> float:
    """
    Compute a top-weighted average retrieval score.

    The highest-scoring chunk contributes double weight so that a
    single excellent piece of evidence lifts confidence appropriately.
    """
    if not chunks:
        return 0.0
    scores = [c.get("score", 0.0) for c in chunks]
    scores_sorted = sorted(scores, reverse=True)
    # Weight: rank-1 counts 2×, rest count 1×
    weighted_sum = scores_sorted[0] * 2 + sum(scores_sorted[1:])
    weight_total = 2 + max(0, len(scores_sorted) - 1)
    return weighted_sum / weight_total


# ===========================================================================
# Stage 1 — Chunk Normalization
# ===========================================================================

def normalize_chunks(chunks: list[dict]) -> list[dict]:
    """
    Stage 1: Clean text fields and remove empty chunks.

    - Strips and collapses whitespace (delegates to utils.clean_text)
    - Drops chunks that become empty after cleaning
    """
    normalized: list[dict] = []
    for chunk in chunks:
        text = clean_text(chunk.get("text", ""))
        if not text:
            continue
        normalized.append({**chunk, "text": text})
    return normalized


# ===========================================================================
# Stage 2 — Duplicate Removal
# ===========================================================================

def remove_duplicates(chunks: list[dict]) -> list[dict]:
    """
    Stage 2: Remove near-duplicate chunks using TF cosine similarity.

    Sorted descending by retrieval score so that when two chunks are
    near-duplicates the higher-scoring one is retained.
    Threshold: DUPLICATE_SIM_THRESHOLD (default 0.90).
    """
    sorted_chunks = sorted(chunks, key=lambda c: c.get("score", 0.0), reverse=True)
    kept: list[dict] = []

    for candidate in sorted_chunks:
        is_dup = any(
            compute_chunk_similarity(candidate["text"], kept_chunk["text"])
            >= DUPLICATE_SIM_THRESHOLD
            for kept_chunk in kept
        )
        if not is_dup:
            kept.append(candidate)

    return kept


# ===========================================================================
# Stage 3 — Relevance Filtering  (NEW in V3)
# ===========================================================================

def filter_by_relevance(chunks: list[dict], query: str) -> list[dict]:
    """
    Stage 3: Keep only chunks that are sufficiently relevant to the query.

    Strategy (deterministic, no ML model required):
        1. Compute TF-cosine similarity between the query and each chunk text.
        2. Find the best similarity score across all chunks.
        3. Keep any chunk whose similarity >= best_sim * RELEVANCE_RATIO_THRESHOLD
           AND >= MIN_RELEVANCE_SCORE (absolute floor).

    If query is empty or all chunks already pass, the list is returned as-is.
    Each chunk gets an additional "relevance_score" key for downstream use.
    """
    if not query.strip() or not chunks:
        return [{**c, "relevance_score": 1.0} for c in chunks]

    # Score every chunk
    scored = [
        {**chunk, "relevance_score": round(compute_query_similarity(query, chunk["text"]), 4)}
        for chunk in chunks
    ]

    best_sim = max(c["relevance_score"] for c in scored)

    # If best score is effectively zero everything is off-topic
    if best_sim < MIN_RELEVANCE_SCORE:
        return []

    cutoff = best_sim * RELEVANCE_RATIO_THRESHOLD
    relevant = [c for c in scored if c["relevance_score"] >= cutoff]
    return relevant


# ===========================================================================
# Stage 4 — Evidence Consistency Analysis  (upgraded in V3)
# ===========================================================================

def detect_conflicts(chunks: list[dict]) -> bool:
    """
    Stage 4: Return True if any pair of chunks contains contradictory evidence.

    Two-pronged strategy:
    A) For semantically similar chunks (sim >= CONFLICT_SIM_THRESHOLD):
       apply keyword-contradiction heuristics.
    B) For chunks sharing the same document section:
       apply both keyword AND numeric contradiction checks.

    The expanded _CONTRADICTION_PAIRS list improves coverage over V2.
    """
    for i, a in enumerate(chunks):
        for b in chunks[i + 1:]:
            sim = compute_chunk_similarity(a["text"], b["text"])
            same_section = (
                a.get("section", "").lower() == b.get("section", "").lower()
                and a.get("section", "") != ""
            )

            if sim >= CONFLICT_SIM_THRESHOLD or same_section:
                if _has_keyword_contradiction(a["text"], b["text"]):
                    return True
                if same_section and _has_numeric_contradiction(a["text"], b["text"]):
                    return True

    return False


# ===========================================================================
# Stage 5 — Evidence Sufficiency Check  (upgraded in V3)
# ===========================================================================

def check_sufficiency(chunks: list[dict]) -> bool:
    """
    Stage 5: Deterministic heuristics — returns True when all three pass:

    H1. Minimum chunk count    : at least MIN_CHUNKS_FOR_SUFFICIENCY chunks
    H2. Average retrieval score: avg score >= MIN_AVG_SCORE_FOR_SUFFICIENCY
    H3. Relevance floor        : at least one chunk has relevance_score > 0
                                 (ensures we don't synthesize from off-topic evidence)
    """
    if len(chunks) < MIN_CHUNKS_FOR_SUFFICIENCY:
        return False

    scores = [c.get("score", 0.0) for c in chunks]
    avg_score = sum(scores) / len(scores)
    if avg_score < MIN_AVG_SCORE_FOR_SUFFICIENCY:
        return False

    # H3: at least one chunk must have non-trivial relevance to the query
    has_relevant = any(c.get("relevance_score", 1.0) > MIN_RELEVANCE_SCORE for c in chunks)
    return has_relevant


# ===========================================================================
# Stage 6 — Evidence Structuring  (NEW in V3)
# ===========================================================================

def structure_evidence(chunks: list[dict]) -> list[dict]:
    """
    Stage 6: Return chunks as fully-typed structured evidence dicts.

    Adds a `rank` field (1 = best) and ensures descending score order.
    Downstream modules (synthesis, orchestrator) can rely on this ordering.

    Output keys per chunk:
        rank            int     1-indexed rank (1 = highest retrieval score)
        text            str     cleaned chunk text
        source          str     originating document
        section         str     section/heading within the document
        score           float   retrieval relevance score from the vector store
        relevance_score float   query-text cosine similarity (Stage 3 output)
    """
    sorted_chunks = sorted(chunks, key=lambda c: c.get("score", 0.0), reverse=True)
    structured: list[dict] = []
    for rank, chunk in enumerate(sorted_chunks, start=1):
        structured.append({
            "rank"           : rank,
            "text"           : chunk.get("text", ""),
            "source"         : chunk.get("source", "unknown"),
            "section"        : chunk.get("section", "unknown"),
            "score"          : round(chunk.get("score", 0.0), 4),
            "relevance_score": round(chunk.get("relevance_score", 1.0), 4),
        })
    return structured


# ===========================================================================
# Stage 7 — Abstention Decision  (NEW in V3)
# ===========================================================================

def decide_abstention(conflict_flag: bool, sufficiency_flag: bool) -> Optional[str]:
    """
    Stage 7: Return a named abstention reason or None if proceeding is safe.

    Priority order:
        1. conflict_flag      → "conflict"      (contradictory evidence)
        2. not sufficiency_flag → "insufficient" (too thin / low-quality evidence)
        3. None               → proceed to synthesis

    Returns
    -------
    "conflict" | "insufficient" | None
    """
    if conflict_flag:
        return "conflict"
    if not sufficiency_flag:
        return "insufficient"
    return None


# ===========================================================================
# Main entry point
# ===========================================================================

def validate(chunks: list[dict], query: str = "") -> dict:
    """
    Run the full V3 7-stage validation pipeline on retrieved chunks.

    Parameters
    ----------
    chunks : Raw list of chunk dicts from the retrieval module.
    query  : The user query string — required for Stage 3 relevance filtering.
             Pass an empty string to skip relevance filtering (backward-compatible).

    Returns
    -------
    {
        "cleaned_chunks"    : list[dict],   # structured, ranked evidence
        "conflict_flag"     : bool,
        "sufficiency_flag"  : bool,
        "confidence_score"  : float,        # top-weighted avg score
        "abstention_reason" : str | None,   # "conflict" | "insufficient" | None
        "relevant_count"    : int,          # chunks passing Stage 3
    }
    """
    # ── Stage 1: Normalize ───────────────────────────────────────────────────
    stage1 = normalize_chunks(chunks)

    # ── Stage 2: Deduplicate ─────────────────────────────────────────────────
    stage2 = remove_duplicates(stage1)

    # ── Stage 3: Relevance Filtering ─────────────────────────────────────────
    # Adds relevance_score to each chunk; drops off-topic ones.
    stage3 = filter_by_relevance(stage2, query)
    relevant_count = len(stage3)

    # ── Stage 4: Conflict Detection ──────────────────────────────────────────
    # Runs on the RELEVANCE-FILTERED set (stage3).
    # Rationale: a contradiction between two documents should only trigger
    # abstention if both documents are relevant to the current query.
    # Running on all deduped chunks would produce false-positive conflicts
    # (e.g., the leave policy contradiction firing for a salary question).
    conflict_flag = detect_conflicts(stage3)

    # ── Stage 5: Sufficiency Check ───────────────────────────────────────────
    # Run on the relevance-filtered set so low-relevance chunks don't inflate
    # the count and mask an actually-thin evidence pool.
    sufficiency_flag = check_sufficiency(stage3)

    # ── Stage 6: Evidence Structuring ────────────────────────────────────────
    # Only the relevance-filtered chunks are structured and passed to synthesis.
    structured = structure_evidence(stage3)

    # ── Stage 7: Abstention Decision ─────────────────────────────────────────
    abstention_reason = decide_abstention(conflict_flag, sufficiency_flag)

    # ── Confidence score (top-weighted) ──────────────────────────────────────
    confidence_score = _weighted_confidence(structured)

    return {
        "cleaned_chunks"   : structured,
        "conflict_flag"    : conflict_flag,
        "sufficiency_flag" : sufficiency_flag,
        "confidence_score" : round(confidence_score, 4),
        "abstention_reason": abstention_reason,
        "relevant_count"   : relevant_count,
    }
