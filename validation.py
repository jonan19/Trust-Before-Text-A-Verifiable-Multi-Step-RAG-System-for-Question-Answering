"""
validation.py — V5 Validation Pipeline for the Trust Before Text RAG system.

Pipeline (7 stages, all deterministic — no LLM):

    Stage 1  Chunk Normalization        remove empty chunks, normalise whitespace
    Stage 2  Duplicate Removal          cosine-sim dedup, keep highest-scoring copy
    Stage 3  Relevance Filtering        drop chunks below query-relevance threshold
    Stage 4  Evidence Consistency       detect contradictions (keyword + numeric + NLI)
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

V5 changes:
    - Stage 4 (detect_conflicts): upgraded from lexical-only (17 hardcoded antonym
      pairs) to a hybrid lexical + semantic NLI approach.
      Strategy (ordered by cost):
        1. Keyword contradiction check runs first — O(1), catches obvious pairs fast.
        2. If keywords do not fire, a cross-encoder NLI model
           (cross-encoder/nli-deberta-v3-base) classifies the pair as
           CONTRADICTION / ENTAILMENT / NEUTRAL.
      This catches semantic contradictions that share no antonym vocabulary:
          "Employees may telecommute" vs "On-site presence is compulsory"
          "Staff are entitled to work remotely" vs "Physical attendance is mandatory"
      The NLI model is lazy-loaded once on first use and reused for the lifetime
      of the process (no reload cost per query).
      NLI_CONFLICT_THRESHOLD (default 0.80) controls sensitivity — raise it to
      reduce false positives, lower it to increase recall.

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

import logging
import os
import re
from typing import Optional

from utils import clean_text, compute_query_similarity, compute_chunk_similarity

# sentence-transformers CrossEncoder — used for NLI-based conflict detection (V5)
try:
    from sentence_transformers import CrossEncoder as _CrossEncoder
    _CROSSENCODER_AVAILABLE = True
except ImportError:  # pragma: no cover
    _CrossEncoder = None          # type: ignore[assignment,misc]
    _CROSSENCODER_AVAILABLE = False

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# NLI model — lazy-loaded on first conflict check, reused afterwards
# ---------------------------------------------------------------------------
_NLI_MODEL: "_CrossEncoder | None" = None  # type: ignore[type-arg]
_NLI_MODEL_NAME = "cross-encoder/nli-deberta-v3-base"


def _get_nli_model() -> "_CrossEncoder | None":  # type: ignore[type-arg]
    """
    Lazy-load the NLI CrossEncoder model on first call; return None if the
    sentence-transformers package is unavailable (falls back to keyword-only).

    The model is stored in the module-level ``_NLI_MODEL`` singleton so it is
    only loaded once per process regardless of how many queries are processed.
    """
    global _NLI_MODEL
    if not _CROSSENCODER_AVAILABLE:
        return None
    if _NLI_MODEL is None:
        _log.info("[Validation V5] Loading NLI model '%s' (first use)...", _NLI_MODEL_NAME)
        try:
            _NLI_MODEL = _CrossEncoder(_NLI_MODEL_NAME)
            _log.info("[Validation V5] NLI model loaded successfully.")
        except Exception as exc:  # pragma: no cover
            _log.warning(
                "[Validation V5] Failed to load NLI model '%s': %s — "
                "falling back to keyword-only conflict detection.",
                _NLI_MODEL_NAME, exc,
            )
            return None
    return _NLI_MODEL


def get_nli_model():
    """
    Public accessor for the NLI model singleton.

    Allows other modules (e.g. synthesis.py) to reuse the model that was
    already loaded and cached by the validation pipeline, avoiding a second
    model load in the same process.
    """
    return _get_nli_model()

# ---------------------------------------------------------------------------
# Thresholds — tune as needed
# ---------------------------------------------------------------------------
DUPLICATE_SIM_THRESHOLD: float       = 0.90   # cosine sim >= this -> duplicate
RELEVANCE_RATIO_THRESHOLD: float     = 0.30   # keep chunk if sim >= best_sim * ratio
MIN_RELEVANCE_SCORE: float           = 0.05   # absolute floor (catches fully off-topic chunks)
MIN_CHUNKS_FOR_SUFFICIENCY: int      = 1      # at least this many relevant chunks needed
MIN_CHUNK_SCORE_THRESHOLD: float     = float(
    os.getenv("RAG_MIN_CHUNK_SCORE_THRESHOLD", "0.60")
)                                              # Stage 3 hard floor on calibrated `score` — chunks
                                               # below this are dropped before Stage 4/5 ever see
                                               # them, not just hidden from display.

# The four thresholds below are benchmark-calibratable: each directly gates a
# decision (conflict_flag or sufficiency_flag) that benchmark.py's metrics
# (conflict_precision/recall/f1, abstention_recall, false_abstention_rate)
# can observe end-to-end. Overridable via env var so calibrate_thresholds.py
# can sweep candidate values without code edits — defaults below are the
# previously hand-picked values, unchanged unless the env var is set.
MIN_AVG_SCORE_FOR_SUFFICIENCY: float = float(
    os.getenv("RAG_MIN_AVG_SCORE_FOR_SUFFICIENCY", "0.65")
)                                              # avg calibrated-score floor for sufficiency (H2).
                                               # MUST sit above the calibrated floor SCORE_FLOOR
                                               # (0.60) or the gate can never fire. A prior value
                                               # of 0.55 sat *below* the floor and silently disabled
                                               # H2, letting weak evidence pass. 0.65 restores a
                                               # real average-quality check.
CONFLICT_SIM_THRESHOLD: float        = float(
    os.getenv("RAG_CONFLICT_SIM_THRESHOLD", "0.68")
)                                              # lexical-overlap floor for the cheap keyword &
                                               # numeric checks. NLI is NOT gated on this (see
                                               # NLI_SIM_FLOOR) — gating NLI behind high lexical
                                               # similarity defeated its purpose (Finding 1).
NLI_SIM_FLOOR: float                 = float(
    os.getenv("RAG_NLI_SIM_FLOOR", "0.15")
)                                              # performance-only floor: below this the two spans
                                               # share almost no words and are treated as unrelated,
                                               # so NLI is skipped. Kept far below CONFLICT_SIM_THRESHOLD
                                               # so paraphrastic contradictions (low lexical overlap)
                                               # still reach NLI.
MIN_CONFLICT_RELEVANCE: float        = 0.25   # both chunks must score above this to be conflict-checked
NLI_CONFLICT_THRESHOLD: float        = float(
    os.getenv("RAG_NLI_CONFLICT_THRESHOLD", "0.94")
)                                              # NLI contradiction confidence floor.
                                               # Raise → fewer false positives; Lower → higher recall.
                                               # Calibrated 0.80 → 0.94 on the Meridian Grid 78-query
                                               # set: every true conflict scores >= 0.965 while most
                                               # false conflicts score <= 0.9194, leaving an empty
                                               # band between. 0.94 sits mid-gap. Measured effect:
                                               # 3 false conflicts removed, 12/12 true conflicts and
                                               # 16/16 gap queries unaffected. NOTE: corpus-calibrated,
                                               # not a universal constant — re-check on a new corpus.
MIN_QUERY_COVERAGE: float            = float(
    os.getenv("RAG_MIN_QUERY_COVERAGE", "0.55")
)                                              # H4: fraction of query content-words that must
                                               # appear in evidence for sufficiency to pass.
                                               # Raised from 0.35 to 0.55 to block false-positive
                                               # answers when evidence only partially overlaps the query.

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
    # Capability — bare modal pairs ("cannot"/"can", "cannot"/"able to")
    # removed: "can"/"cannot" are high-frequency, subject-blind words that fire
    # on unrelated statements ("employees can take leave" vs "unused leave
    # cannot be carried over"). Only the explicit "unable to"/"able to" phrasing
    # is kept (neither side a bare modal); paraphrastic capability
    # contradictions are still covered by the NLI check.
    ("unable to",     "able to"),
    # Logical polarity pairs ("never"/"always", "no"/"yes") removed for the same
    # reason — they carry no policy-stance semantics and fire on any two
    # sentences that happen to use both words about different subjects.
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


def _has_nli_contradiction(text_a: str, text_b: str) -> bool:
    """
    V5: Semantic contradiction detection using a cross-encoder NLI model.

    Uses ``cross-encoder/nli-deberta-v3-base`` to classify the relationship
    between two text passages as CONTRADICTION / ENTAILMENT / NEUTRAL.

    Checks both orderings (A→B and B→A) because NLI is directional — a model
    may score ``A entails B`` differently from ``B entails A``.

    Label order for nli-deberta-v3-base (after apply_softmax=True):
        index 0 → contradiction
        index 1 → entailment
        index 2 → neutral

    Returns True only when the maximum contradiction score across both
    directions meets or exceeds NLI_CONFLICT_THRESHOLD (default 0.80).

    Falls back to False (no conflict) if the NLI model is unavailable,
    ensuring the pipeline degrades gracefully to keyword-only mode.
    """
    model = _get_nli_model()
    if model is None:
        # NLI model unavailable — keyword check is the sole detector
        return False

    try:
        # Score both orderings; contradiction is index 0 in deberta-v3-base
        scores_ab = model.predict([(text_a, text_b)], apply_softmax=True)[0]
        scores_ba = model.predict([(text_b, text_a)], apply_softmax=True)[0]
        contradiction_score = max(float(scores_ab[0]), float(scores_ba[0]))
        return contradiction_score >= NLI_CONFLICT_THRESHOLD
    except Exception as exc:  # pragma: no cover
        _log.warning("[Validation V5] NLI inference error: %s — skipping NLI check.", exc)
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

    Source-aware (V5 fix): chunks from *different* source documents are
    never deduplicated against each other, even if their text is nearly
    identical. Two different documents stating the same policy wording are
    independent pieces of evidence and must both reach Stage 4 so the
    conflict detector can compare them.

    compute_chunk_similarity is LRU-cached (utils.py) so repeated pair
    comparisons across pipeline retries are not recomputed.
    """
    sorted_chunks = sorted(chunks, key=lambda c: c.get("score", 0.0), reverse=True)
    kept: list[dict] = []

    for candidate in sorted_chunks:
        candidate_source = candidate.get("source", "")
        is_dup = any(
            # Only consider it a duplicate if same source OR sources unknown
            (kept_chunk.get("source", "") == candidate_source or not candidate_source)
            and compute_chunk_similarity(candidate["text"], kept_chunk["text"])
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

    Hard floor (applied first, unconditionally): chunks whose calibrated
    `score` is below MIN_CHUNK_SCORE_THRESHOLD are dropped regardless of
    query text — they're treated as too low-quality to count as evidence at
    all, so they never reach Stage 4 (conflict) or Stage 5 (sufficiency).

    V4 upgrade — two-path strategy on the remaining chunks:

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
    chunks = [c for c in chunks if c.get("score", 0.0) >= MIN_CHUNK_SCORE_THRESHOLD]

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

def find_conflict(chunks: list[dict], query: str = "") -> Optional[dict]:
    """
    Stage 4 core: return the first contradictory chunk pair found, or None.

    Query-scoped (fix #1): each chunk is first reduced to the sentences that
    mention the query's content words, and the contradiction checks run on
    those query-relevant spans only. This stops a disagreement in a part of a
    chunk unrelated to the user's question from triggering a false conflict.
    When `query` is empty the full chunk text is used (backward compatible).

    Three-pronged hybrid strategy:

    A) Keyword antonym check — cheap and precise, so it stays gated on high
       lexical similarity (CONFLICT_SIM_THRESHOLD).
    B) NLI contradiction check — **not** gated on high lexical similarity
       (Finding 1). Its whole purpose is to catch paraphrastic contradictions
       that share almost no vocabulary ("may work remotely" vs "on-site
       presence is compulsory"), which by definition have low lexical overlap.
       Gating it behind CONFLICT_SIM_THRESHOLD (0.68) silently disabled it on
       exactly those cases. It now runs on any query-relevant pair above the
       tiny NLI_SIM_FLOOR (a performance guard, not a semantic gate).
       Threshold: NLI_CONFLICT_THRESHOLD (default 0.80). Degrades to skipped
       if the NLI model is unavailable.
    C) Numeric unit-aware check — cheap/precise, stays gated on high similarity.

    Returns
    -------
    { "kind": "keyword"|"nli"|"numeric",
      "chunks": [ {"source","section","text"(query-relevant span)}, {...} ] }
    for the first conflicting pair, or None if no conflict is found.
    """
    content_terms = _query_content_terms(query)

    for i, a in enumerate(chunks):
        for b in chunks[i + 1:]:
            # Skip if from the same source file
            source_a = a.get("source", "unknown_a")
            source_b = b.get("source", "unknown_b")
            if source_a == source_b and source_a != "unknown":
                continue

            # Guard: both chunks must be individually relevant to the query.
            rel_a = a.get("relevance_score", a.get("score", 0.0))
            rel_b = b.get("relevance_score", b.get("score", 0.0))
            if rel_a < MIN_CONFLICT_RELEVANCE or rel_b < MIN_CONFLICT_RELEVANCE:
                continue

            # Query-scoping (fix #1): compare only the query-relevant sentences.
            text_a = _query_relevant_text(a["text"], content_terms)
            text_b = _query_relevant_text(b["text"], content_terms)
            if not text_a or not text_b:
                continue
            # Identical spans (e.g. shared boilerplate copied across documents)
            # cannot contradict each other — skip before any check.
            if text_a == text_b:
                continue

            sim = compute_chunk_similarity(text_a, text_b)
            high_sim = sim >= CONFLICT_SIM_THRESHOLD

            kind: Optional[str] = None
            # A) Keyword antonyms — gated on high lexical similarity.
            if high_sim and _has_keyword_contradiction(text_a, text_b):
                kind = "keyword"
            # B) NLI — ungated (Finding 1): runs on any query-relevant pair with
            #    at least minimal lexical overlap (NLI_SIM_FLOOR perf guard).
            elif sim >= NLI_SIM_FLOOR and _has_nli_contradiction(text_a, text_b):
                kind = "nli"
            # C) Numeric — gated on high lexical similarity.
            elif high_sim and _has_numeric_contradiction(text_a, text_b):
                kind = "numeric"

            if kind:
                _log.debug(
                    "[Stage 4] %s conflict: '%s' vs '%s'",
                    kind, source_a, source_b,
                )
                return {
                    "kind": kind,
                    "chunks": [
                        {"source": source_a, "section": a.get("section", "unknown"),
                         "text": _most_relevant_sentence(text_a, content_terms)},
                        {"source": source_b, "section": b.get("section", "unknown"),
                         "text": _most_relevant_sentence(text_b, content_terms)},
                    ],
                }

    return None


def detect_conflicts(chunks: list[dict], query: str = "") -> bool:
    """
    Stage 4: True if any query-relevant chunk pair contradicts. Thin boolean
    wrapper over ``find_conflict`` — preserved for backward compatibility.
    """
    return find_conflict(chunks, query) is not None


# ===========================================================================
# Stage 5 helpers
# ===========================================================================

# Common English stopwords excluded from query coverage calculation.
# These words carry no topical content and would inflate or deflate coverage scores.
#
# IMPORTANT — two categories here:
#   1. Grammatical stopwords (is, the, are, ...)
#   2. Command/action verbs — instructions to the system that are never present
#      in the document content itself ("summarize", "explain", "describe").
#      Including these prevents H4 from penalising legitimate summarization
#      and explanation queries.
_COVERAGE_STOPWORDS: frozenset[str] = frozenset({
    # Grammatical
    "what", "is", "the", "are", "how", "does", "do", "a", "an", "for", "of",
    "in", "on", "at", "to", "by", "be", "was", "were", "can", "could",
    "would", "should", "will", "has", "have", "had", "it", "its", "that",
    "this", "these", "those", "with", "from", "about", "which", "who", "when",
    "me", "my", "all", "any", "some", "please", "get", "give", "tell",
    # Command / action verbs — system instructions, never appear in doc content
    "summarize", "summarise", "summary", "explain", "describe", "detail",
    "outline", "review", "list", "show", "provide", "generate", "write",
    "find", "search", "look", "fetch", "retrieve", "analyse", "analyze",
    "compare", "contrast", "highlight", "identify", "extract", "return",
    # Meta-reference nouns — refer to the document itself, not content inside it
    "document", "file", "doc", "text", "content", "information", "info",
    "above", "below", "following", "given", "attached", "regarding",
    # Answer-length / style qualifiers — describe HOW to answer, not WHAT
    "short", "brief", "briefly", "quick", "quickly", "simple", "simply",
    "long", "detailed", "concise", "concisely", "overview", "summarized",
    "comprehensive", "complete", "full", "partial", "basic", "advanced",
    # Generic HR / people nouns — appear in virtually every HR document chunk,
    # inflating coverage scores and masking the absence of real query terms.
    "employee", "employees", "employer", "staff", "personnel",
})

# File extension suffixes to strip from query tokens so that filenames like
# "hr_policy_a.docx" are not counted as content terms (the filename cannot
# appear inside the document it names).
_FILE_EXTENSIONS: frozenset[str] = frozenset({".docx", ".pdf", ".txt", ".doc", ".xlsx"})


def _query_content_terms(query: str) -> set[str]:
    """
    Extract the query's topical content words — grammatical stopwords, command
    verbs, and filenames removed (same filtering rationale as _query_coverage).

    Used by detect_conflicts (Stage 4) to scope contradiction checks to the
    part of each chunk that is actually about the query. Returns an empty set
    when the query is absent or reduces to no content words, in which case the
    caller falls back to comparing full chunk text.
    """
    if not query.strip():
        return set()
    raw_tokens = {w.lower().strip(".,;:?!'\"()") for w in query.split()}
    tokens: set[str] = set()
    for tok in raw_tokens:
        if any(tok.endswith(ext) for ext in _FILE_EXTENSIONS):
            continue
        tokens.add(tok)
    return {t for t in (tokens - _COVERAGE_STOPWORDS) if t}


def _query_relevant_text(text: str, content_terms: set[str]) -> str:
    """
    Return only the sentences of *text* that mention at least one query content
    term. This scopes conflict detection so that a contradiction in a part of a
    chunk unrelated to the query does not trigger a false abstention.

    If content_terms is empty (no query, or all stopwords), the full text is
    returned unchanged so conflict detection behaves exactly as before.
    """
    if not content_terms:
        return text
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    kept: list[str] = []
    for sentence in sentences:
        s_tokens = {w.lower().strip(".,;:?!'\"()") for w in sentence.split()}
        if s_tokens & content_terms:
            kept.append(sentence)
    return " ".join(kept)


def _most_relevant_sentence(span: str, content_terms: set[str]) -> str:
    """
    Return the single sentence of *span* that mentions the most query content
    words. Used only to pick a clean, on-topic excerpt for the conflict message
    (Finding 2) so a multi-sentence span does not display leading boilerplate.
    Does not affect conflict detection, which still compares the full span.
    """
    if not content_terms:
        return span
    sentences = re.split(r"(?<=[.!?])\s+", span.strip())
    if len(sentences) <= 1:
        return span

    def _score(sentence: str) -> int:
        toks = {w.lower().strip(".,;:?!'\"()") for w in sentence.split()}
        return len(toks & content_terms)

    best = max(sentences, key=_score)
    return best if _score(best) > 0 else span


def _query_coverage(query: str, chunks: list[dict]) -> float:
    """
    Compute what fraction of the query's content words appear in the evidence.

    'Content words' are defined as query tokens that are NOT:
      - Common grammatical stopwords
      - Command/action verbs (summarize, explain, describe, ...)
      - Filenames (stripped of extension they become ambiguous; with extension
        they can never appear verbatim inside the document)

    Returns a float in [0.0, 1.0].
    Returns 1.0 when the query is empty or reduces to no content words after
    filtering, so that command-only queries ("summarize Policy_A.docx") never
    fail H4 — they should always proceed to the LLM.

    Example:
        query  = "What is the remote work and overtime policy?"
        terms  = {"remote", "work", "overtime", "policy"}   (stopwords removed)
        evidence has "remote", "work", "policy" but not "overtime"
        coverage = 3/4 = 0.75

        query  = "summarize HR_Policy_A.docx"
        terms  after filtering = {}   ("summarize" is command, filename stripped)
        → returns 1.0 immediately (no content terms to check)
    """
    if not query.strip() or not chunks:
        return 1.0

    raw_tokens = {w.lower().strip(".,;:?!'\"()") for w in query.split()}

    # Discard tokens that are filenames entirely (including their stem).
    # A filename like "hr_policy_a.docx" becomes "hr_policy_a" after extension
    # stripping — but that stem also cannot appear inside the document itself.
    tokens: set[str] = set()
    for tok in raw_tokens:
        is_filename = any(tok.endswith(ext) for ext in _FILE_EXTENSIONS)
        if not is_filename:
            tokens.add(tok)
        # filename tokens are dropped completely — neither the full name nor
        # the stem should count as a content term to be covered

    content_terms = tokens - _COVERAGE_STOPWORDS
    # Remove empty strings
    content_terms = {t for t in content_terms if t}

    if not content_terms:
        return 1.0  # all stopwords / command verbs / filenames — no content to measure

    evidence_text = " ".join(c.get("text", "").lower() for c in chunks)
    covered = {t for t in content_terms if t in evidence_text}
    return round(len(covered) / len(content_terms), 4)


def check_sufficiency(chunks: list[dict], query: str = "") -> bool:
    """
    Stage 5: Deterministic sufficiency heuristics.

    Two HARD requirements (both must hold):
      H1. Minimum chunk count : at least MIN_CHUNKS_FOR_SUFFICIENCY chunks.
      H3. Relevance floor     : at least one chunk has relevance_score > 0
                                (never synthesize from purely off-topic evidence).

    Then ONE quality requirement, satisfied by EITHER of two signals (H2 OR H4):
      H2. Average retrieval score : avg score >= MIN_AVG_SCORE_FOR_SUFFICIENCY.
      H4. Query coverage          : >= MIN_QUERY_COVERAGE of the query's content
                                    words appear in the evidence.

    Why OR, not AND: the two signals punish opposite (legitimate) query shapes.
    A precise single-fact question retrieves few but strongly-relevant chunks —
    high avg score, low coverage. A broad / list question retrieves many chunks —
    high coverage, diluted avg score. Requiring BOTH over-abstained on both
    shapes. A query that is weak on BOTH counts is the genuine "insufficient"
    signal and still fails.
    """
    # H1 — hard
    if len(chunks) < MIN_CHUNKS_FOR_SUFFICIENCY:
        return False

    # H3 — hard: at least one chunk must have non-trivial relevance to the query
    has_relevant = any(c.get("relevance_score", 1.0) > MIN_RELEVANCE_SCORE for c in chunks)
    if not has_relevant:
        return False

    # H2 OR H4 — sufficient if evidence is strong on either average quality or coverage
    scores = [c.get("score", 0.0) for c in chunks]
    avg_score = sum(scores) / len(scores)
    coverage = _query_coverage(query, chunks) if query.strip() else 1.0
    if avg_score < MIN_AVG_SCORE_FOR_SUFFICIENCY and coverage < MIN_QUERY_COVERAGE:
        return False

    return True


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
    Run the full V5 7-stage validation pipeline on retrieved chunks.

    Parameters
    ----------
    chunks : Raw list of chunk dicts from the retrieval module.
    query  : The user query string — required for Stage 3 relevance filtering
             and Stage 5 query coverage check (H4).
             Pass an empty string to skip both (backward-compatible).

    Returns
    -------
    {
        "cleaned_chunks"      : list[dict],   # structured, ranked evidence
        "conflict_flag"       : bool,
        "conflict_detail"     : dict | None,  # {kind, chunks:[{source,section,text}]} — the pair
        "sufficiency_flag"    : bool,
        "confidence_score"    : float,        # top-weighted avg score
        "confidence_tier"     : str,          # "HIGH" | "MEDIUM" | "LOW"
        "abstention_reason"   : str | None,   # "conflict" | "insufficient" | None
        "relevant_count"      : int,          # chunks passing Stage 3
        "query_coverage_score": float,        # [0.0, 1.0] fraction of query terms in evidence
    }
    """
    # ── Stage 1: Normalize ────────────────────────────────────────────────
    stage1 = normalize_chunks(chunks)

    # ── Stage 2: Deduplicate ──────────────────────────────────────────────
    stage2 = remove_duplicates(stage1)

    # ── Stage 3: Relevance Filtering ──────────────────────────────────────
    # V4: uses embedding-based relevance_score if already present in chunks
    # (set by retrieval.py); falls back to TF-cosine if not.
    stage3 = filter_by_relevance(stage2, query)
    relevant_count = len(stage3)

    # ── Stage 4: Conflict Detection ────────────────────────────────────────
    # Runs on the RELEVANCE-FILTERED set (stage3).
    # Rationale: a contradiction between two documents should only trigger
    # abstention if both documents are relevant to the current query.
    # find_conflict returns the offending pair (or None) so downstream code can
    # show *which* documents disagree instead of listing every retrieved source.
    conflict_detail = find_conflict(stage3, query=query)
    conflict_flag = conflict_detail is not None

    # ── Stage 5: Sufficiency Check ───────────────────────────────────────
    # V5: query is passed through for the H4 coverage check
    query_coverage_score = _query_coverage(query, stage3)
    sufficiency_flag = check_sufficiency(stage3, query=query)

    # ── Stage 6: Evidence Structuring ──────────────────────────────────────
    structured = structure_evidence(stage3)

    # ── Stage 7: Abstention Decision ──────────────────────────────────────
    abstention_reason = decide_abstention(conflict_flag, sufficiency_flag)

    # ── Confidence score + tier ──────────────────────────────────────────
    confidence_score = _weighted_confidence(structured)
    confidence_tier  = (
        "HIGH"   if confidence_score >= 0.88 else
        "MEDIUM" if confidence_score >= 0.75 else
        "LOW"
    )

    return {
        "cleaned_chunks"      : structured,
        "conflict_flag"       : conflict_flag,
        "conflict_detail"     : conflict_detail,   # {kind, chunks:[{source,section,text}]} | None
        "sufficiency_flag"    : sufficiency_flag,
        "confidence_score"    : round(confidence_score, 4),
        "confidence_tier"     : confidence_tier,
        "abstention_reason"   : abstention_reason,
        "relevant_count"      : relevant_count,
        "query_coverage_score": query_coverage_score,
    }
