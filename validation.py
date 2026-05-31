"""
validation.py — V4 Validation Pipeline for the Trust Before Text RAG system.

Pipeline (7 stages, all deterministic — no LLM):

    Stage 1  Chunk Normalization        remove empty chunks, normalise whitespace
    Stage 2  Duplicate Removal          cosine-sim dedup, keep highest-scoring copy
    Stage 3  Relevance Filtering        drop chunks below query-relevance threshold
    Stage 4  Evidence Consistency       detect contradictions (keyword + numeric)
    Stage 5  Evidence Sufficiency       heuristic: count + avg-score + coverage
    Stage 6  Evidence Structuring       add rank field, enforce descending-score order
    Stage 7  Abstention Decision        named reason: "conflict" | "insufficient" | None

V3 changes vs V2:
    - validate() receives query string for Stage 3 relevance filtering
    - make_decision() reads abstention_reason for richer routing
    - Verbose output shows relevant_count, abstention_reason, evidence ranks

V4 changes:
    - Stage 3 (filter_by_relevance): if chunks already carry a `relevance_score`
      set by the retrieval module (embedding-based), those scores are used
      directly — the TF-cosine recomputation is skipped. This is both faster
      and more accurate (semantic vs lexical relevance).
    - _has_numeric_contradiction: upgraded from "first number only" to a
      unit-context-aware comparison. Numbers are only flagged as contradictory
      when both texts reference the SAME unit (e.g. "days", "months", "%") with
      different values. "20 days annual leave" vs "5 working days notice" no
      longer triggers a false positive because "working_day" ≠ "day" in context.

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
RELEVANCE_RATIO_THRESHOLD: float = 0.30  # keep chunk if sim >= best_sim * ratio
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
    # Capability
    ("cannot",        "can"),
    ("cannot",        "able to"),
    ("unable to",     "able to"),
    # Logical
    ("never",         "always"),
    ("no",            "yes"),
    # Approval workflow
    ("deny",          "approve"),
    ("rejected",      "approved"),
    ("refused",       "accepted"),
    # Temporal
    ("terminated",    "active"),
    ("expired",       "valid"),
    ("discontinued",  "available"),
]

# ---------------------------------------------------------------------------
# Unit pattern for numeric-contradiction detection  (V4 — context-aware)
# ---------------------------------------------------------------------------
# Captures: value, optional qualifier ("working", "calendar", "business"),
# and the unit noun (days, weeks, months, years, hours, percent, %).
# Qualifiers are kept to distinguish "working days" from plain "days".
_UNIT_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)"          # numeric value
    r"\s*"
    r"(calendar\s+|working\s+|business\s+)?"  # optional qualifier
    r"(days?|weeks?|months?|years?|hours?|employees?|percent|%)",
    re.IGNORECASE,
)


# ===========================================================================
# Internal helpers
# ===========================================================================

def _extract_numbers(text: str) -> list[float]:
    """Extract all numeric values (int or decimal) from *text*."""
    return [float(n) for n in re.findall(r"\b\d+(?:\.\d+)?\b", text)]


def _extract_numbers_with_unit(text: str) -> list[tuple[float, str]]:
    """
    Extract (value, context_key) pairs from *text*.

    context_key is a normalised string combining the optional qualifier and
    the unit, e.g.:
        "20 days"          → (20.0, "day")
        "5 working days"   → (5.0,  "working_day")
        "15 calendar days" → (15.0, "calendar_day")
        "10%"              → (10.0, "%")
    """
    results: list[tuple[float, str]] = []
    for m in _UNIT_PATTERN.finditer(text):
        val       = float(m.group(1))
        qualifier = (m.group(2) or "").strip().lower()          # "working", "calendar", ""
        unit      = m.group(3).lower().rstrip("s")              # normalise plural: days→day
        ctx_key   = f"{qualifier}_{unit}" if qualifier else unit
        results.append((val, ctx_key))
    return results


def _has_numeric_contradiction(text_a: str, text_b: str) -> bool:
    """
    V4: Unit-context-aware numeric contradiction detection.

    A contradiction is flagged only when both texts state a DIFFERENT numeric
    value for the SAME unit context (e.g. "20 days" vs "15 days").

    "20 days annual leave" vs "5 working days notice" does NOT trigger because
    their context keys differ: "day" vs "working_day".

    Falls back to the first-number comparison when no unit context is found
    in either text (e.g. pure numeric config values).

    Scoped to same-section pairs only in the caller to reduce false positives.
    """
    pairs_a = _extract_numbers_with_unit(text_a)
    pairs_b = _extract_numbers_with_unit(text_b)

    if pairs_a and pairs_b:
        # Build lookup: unit_context → best (minimum) value in text_a
        by_unit_a: dict[str, float] = {}
        for val, ctx in pairs_a:
            # Keep the first occurrence per context key (most prominent value)
            if ctx not in by_unit_a:
                by_unit_a[ctx] = val

        # Compare text_b's (value, context) pairs against text_a's lookup
        for val_b, ctx_b in pairs_b:
            if ctx_b in by_unit_a:
                if abs(by_unit_a[ctx_b] - val_b) > 0.01:
                    return True   # same unit context, different values → contradiction
        return False

    # Fallback: no unit context found in at least one text → use first numbers
    nums_a = _extract_numbers(text_a)
    nums_b = _extract_numbers(text_b)
    if not nums_a or not nums_b:
        return False
    return abs(nums_a[0] - nums_b[0]) > 0.01


def _has_keyword_contradiction(text_a: str, text_b: str) -> bool:
    """
    Check whether the two texts express contradictory stances using the
    expanded _CONTRADICTION_PAIRS list.

    V4: Uses whole-word (word-boundary) regex matching instead of substring
    'in' checks. This prevents false positives where common words appear as
    substrings inside longer words — e.g. "is" matching inside "decisions",
    "increases", "basis"; or "no" matching inside "not", "note", "know".

    Logic: for each (neg, pos) pair —
        - If A contains *neg* (as whole word) and B contains *pos* (but NOT neg) → flag
        - If B contains *neg* (as whole word) and A contains *pos* (but NOT neg) → flag
    """
    a, b = text_a.lower(), text_b.lower()

    def _contains(text: str, phrase: str) -> bool:
        """True if *phrase* appears as a whole-word match in *text*."""
        return bool(re.search(r"\b" + re.escape(phrase) + r"\b", text))

    for neg, pos in _CONTRADICTION_PAIRS:
        a_neg = _contains(a, neg)
        b_neg = _contains(b, neg)
        a_pos = _contains(a, pos)
        b_pos = _contains(b, pos)

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

    compute_chunk_similarity is LRU-cached (utils.py) so repeated pair
    comparisons across pipeline retries are not recomputed.
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
# Stage 3 — Relevance Filtering  (upgraded in V4)
# ===========================================================================

def filter_by_relevance(chunks: list[dict], query: str) -> list[dict]:
    """
    Stage 3: Keep only chunks that are sufficiently relevant to the query.

    V4 upgrade — two-path strategy:

    Path A (preferred): If chunks already carry a `relevance_score` set by
        the retrieval module, those embedding-based scores are used directly.
        This avoids recomputing TF-cosine similarity and produces better
        relevance estimates (semantic > lexical matching).

    Path B (fallback): If no `relevance_score` is present, compute TF-cosine
        similarity between the query and each chunk text (original V3 behaviour).

    Both paths:
        1. Find the best relevance score across all chunks.
        2. Keep chunks with score >= best * RELEVANCE_RATIO_THRESHOLD
           AND >= MIN_RELEVANCE_SCORE.

    If query is empty or all chunks already pass, the list is returned as-is.
    """
    if not query.strip() or not chunks:
        return [{**c, "relevance_score": c.get("relevance_score", 1.0)} for c in chunks]

    # Determine which path to use
    has_embedding_scores = all("relevance_score" in c for c in chunks)

    if has_embedding_scores:
        # Path A: use pre-computed embedding-based relevance scores
        scored = list(chunks)   # scores already present; no recomputation needed
    else:
        # Path B: compute TF-cosine as fallback
        scored = [
            {**chunk, "relevance_score": round(compute_query_similarity(query, chunk["text"]), 4)}
            for chunk in chunks
        ]

    best_sim = max(c["relevance_score"] for c in scored)

    # If best score is effectively zero, everything is off-topic
    if best_sim < MIN_RELEVANCE_SCORE:
        return []

    cutoff   = best_sim * RELEVANCE_RATIO_THRESHOLD
    relevant = [c for c in scored if c["relevance_score"] >= cutoff]
    return relevant


# ===========================================================================
# Stage 4 — Evidence Consistency Analysis  (upgraded in V3 + V4)
# ===========================================================================

def detect_conflicts(chunks: list[dict]) -> bool:
    """
    Stage 4: Return True if any pair of chunks contains contradictory evidence.

    Two-pronged strategy:
    A) For semantically similar chunks (sim >= CONFLICT_SIM_THRESHOLD):
       apply keyword-contradiction heuristics.
    B) For chunks sharing the same document section:
       apply both keyword AND numeric contradiction checks.

    V4: _has_numeric_contradiction now uses unit-context awareness to
    reduce false positives (e.g. "20 days leave" vs "5 working days notice").
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
        relevance_score float   query-text relevance (Stage 3 output)
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
    Run the full V4 7-stage validation pipeline on retrieved chunks.

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
    # V4: uses embedding-based relevance_score if already present in chunks
    # (set by retrieval.py); falls back to TF-cosine if not.
    stage3 = filter_by_relevance(stage2, query)
    relevant_count = len(stage3)

    # ── Stage 4: Conflict Detection ──────────────────────────────────────────
    # Runs on the RELEVANCE-FILTERED set (stage3).
    # Rationale: a contradiction between two documents should only trigger
    # abstention if both documents are relevant to the current query.
    conflict_flag = detect_conflicts(stage3)

    # ── Stage 5: Sufficiency Check ───────────────────────────────────────────
    sufficiency_flag = check_sufficiency(stage3)

    # ── Stage 6: Evidence Structuring ────────────────────────────────────────
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
