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
import math
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
# Query-intent embedding model — lazy-loaded, used only by the Stage 4
# query-span relevance gate (see QUERY_SPAN_RELEVANCE).
# ---------------------------------------------------------------------------
_TOPIC_MODEL = None
_TOPIC_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_TOPIC_EMB_CACHE: dict[str, object] = {}


def _get_topic_model():
    """
    Lazy-load the bi-encoder used to measure query/span topical similarity.

    Deterministic (a fixed encoder, not a generative model), so it does not
    weaken the pipeline's determinism guarantee. Returns None if
    sentence-transformers is unavailable, in which case the gate degrades
    open (see _query_span_similarity).
    """
    global _TOPIC_MODEL
    if not _CROSSENCODER_AVAILABLE:
        return None
    if _TOPIC_MODEL is None:
        try:
            from sentence_transformers import SentenceTransformer
            _log.info("[Validation] Loading query-intent model '%s' (first use)...",
                      _TOPIC_MODEL_NAME)
            _TOPIC_MODEL = SentenceTransformer(_TOPIC_MODEL_NAME)
        except Exception as exc:  # pragma: no cover
            _log.warning("[Validation] Failed to load query-intent model: %s — "
                         "query-span gate disabled.", exc)
            return None
    return _TOPIC_MODEL


def _query_span_similarity(query: str, span: str) -> float:
    """
    Cosine similarity between the query and a candidate conflicting span.

    Degrades OPEN (returns 1.0) when the model is unavailable, so a missing
    optional dependency can never silently suppress conflict detection — the
    safe direction for this project is to keep flagging, not to skip.
    """
    model = _get_topic_model()
    if model is None:
        return 1.0
    try:
        import numpy as _np
        for text in (query, span):
            if text not in _TOPIC_EMB_CACHE:
                _TOPIC_EMB_CACHE[text] = model.encode([text], show_progress_bar=False)[0]
        eq, es = _TOPIC_EMB_CACHE[query], _TOPIC_EMB_CACHE[span]
        denom = float(_np.linalg.norm(eq) * _np.linalg.norm(es))
        if denom <= 0.0:
            return 1.0
        return float(_np.dot(eq, es) / denom)
    except Exception as exc:  # pragma: no cover
        _log.warning("[Validation] query-span similarity error: %s — gate skipped.", exc)
        return 1.0

# ---------------------------------------------------------------------------
# Thresholds — tune as needed
# ---------------------------------------------------------------------------
DUPLICATE_SIM_THRESHOLD: float       = 0.90   # cosine sim >= this -> duplicate
RELEVANCE_RATIO_THRESHOLD: float     = 0.30   # keep chunk if sim >= best_sim * ratio
MIN_RELEVANCE_SCORE: float           = 0.05   # absolute floor (catches fully off-topic chunks)
MIN_CHUNKS_FOR_SUFFICIENCY: int      = 1      # at least this many relevant chunks needed
MIN_CHUNKS_FOR_AVG_SUFFICIENCY: int  = int(
    os.getenv("RAG_MIN_CHUNKS_FOR_AVG_SUFFICIENCY", "2")
)                                              # H2 (average-score branch) only applies to an evidence
                                               # set of at least this size — see check_sufficiency.
                                               # 1 restores the previous behaviour.
KNEE_GAP_MULTIPLE: float             = float(
    os.getenv("RAG_KNEE_GAP_MULTIPLE", "0")
)                                              # Stage 3 discontinuity cutoff ("autocut"/knee).
                                               # When > 0, evidence is cut at the largest JUMP in
                                               # this query's own descending score curve, provided
                                               # that jump is at least this multiple of the median
                                               # gap between adjacent results. A ratio between gaps
                                               # inside one result list carries no corpus
                                               # calibration, which is the property an absolute
                                               # floor lacks: MIN_CHUNK_SCORE_THRESHOLD=0.60
                                               # discarded Corpus-2 Q038's conflicting chunk at
                                               # 0.5945 and Q076's at 0.5751, before Stage 4 ever
                                               # ran, so no conflict-side change could recover them.
                                               # The same idea is standard practice elsewhere
                                               # (Weaviate's autocut; knee detection in the
                                               # adaptive-k RAG literature). 0 disables it.
MIN_KNEE_KEEP: int                   = 2       # never cut below this many chunks: a knee computed
                                               # over one or two results is noise, and Stage 4 needs
                                               # at least a pair to compare at all
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
MAX_CONFLICT_EVIDENCE_RANK: int      = int(
    os.getenv("RAG_MAX_CONFLICT_EVIDENCE_RANK", "0")
)                                              # RETIRED (default 0 = disabled). This positional
                                               # cutoff was the precision mechanism before the
                                               # Stage-4 anchor test existed. With the anchor test
                                               # active it is inert: measured on Corpus 1, values 0
                                               # and 6 produce byte-identical results. It is kept
                                               # only so the old behaviour can be restored for
                                               # comparison.
                                               #
                                               # Retiring it removes a knife edge. A hard top-N over
                                               # near-tied scores decided outcomes on differences of
                                               # ~0.0001: Corpus-1 Q047's conflicting chunk sat
                                               # 0.0006 below the cutoff, and prefixing the query
                                               # with "Could you tell me:" moved it 0.0001 above,
                                               # flipping a genuine conflict into an answer.                                              # Stage 4 query-relevance gate: both chunks of a pair
                                               # must be among this query's N highest-scoring pieces
                                               # of evidence before they may be compared at all.
                                               # A contradiction only justifies abstention if it sits
                                               # in the evidence that actually answers THIS question;
                                               # two low-ranked chunks disagreeing is a fact about the
                                               # corpus, not about the answer. The cutoff is a rank
                                               # within the query's own ranking, not a score value, so
                                               # it carries no corpus-specific calibration: measured on
                                               # two independently authored corpora it preserved
                                               # conflict recall at 16/16 on BOTH while raising
                                               # conflict F1 (0.842 -> 0.970 and 0.604 -> 0.727).
                                               # 0 disables the gate.
RANK_TIE_EPSILON: float              = float(
    os.getenv("RAG_RANK_TIE_EPSILON", "0.005")
)                                              # score difference below which two chunks are
                                               # treated as tied for the Stage-4 rank gate.
                                               # A resolution tolerance, not a fitted class
                                               # separator: measured over both corpora the
                                               # median gap between adjacent ranked chunks is
                                               # 0.0306 (C1) and 0.0153 (C2), while ~10% of
                                               # adjacent gaps fall under 0.005 on BOTH
                                               # (10.4% / 9.5%). So 0.005 is roughly a fifth
                                               # of a typical real gap and an order of
                                               # magnitude above the 0.0001-0.0006 margins
                                               # that were deciding outcomes. 0 restores the
                                               # exact-cutoff behaviour.
QUERY_SPAN_RELEVANCE: float          = float(
    os.getenv("RAG_QUERY_SPAN_RELEVANCE", "0.35")
)                                              # Stage 4 query-intent gate: minimum semantic similarity
                                               # between the QUERY and each conflicting span before the
                                               # pair may be compared at all. Addresses query-irrelevant
                                               # pair comparison (the documented root cause of every
                                               # false conflict): a genuine contradiction between two
                                               # documents should only drive abstention when both spans
                                               # are actually about what was asked. Distinct from
                                               # MIN_CONFLICT_RELEVANCE, which scores the whole retrieved
                                               # CHUNK; a chunk can be retrieved relevantly while the
                                               # specific sentence that contradicts is off-topic.
                                               # 0.0 disables the gate entirely.
                                               #
                                               # CALIBRATION (measured, both corpora, decision-layer only):
                                               #   Safe window (conflict recall 16/16 AND no added unsafe
                                               #   answers): Corpus 1 holds to 0.48 (breaks 0.49);
                                               #   Corpus 2 holds to 0.35 (breaks 0.40).
                                               #   Default 0.35 = min of the two safe maxima, so it is
                                               #   inside BOTH windows rather than fitted to either.
                                               #     C1: 92.3%->93.6%, precision 0.727->0.800, 16/16, 0/32
                                               #     C2: 66.7%->69.2%, precision 0.432->0.457, 16/16, 4/32
                                               #   Raising to 0.47 gives C1 98.7% and conflict F1 1.000
                                               #   but BREAKS Corpus 2 (recall 14/16, unsafe 4->6), so it
                                               #   is corpus-specific and deliberately NOT the default.
                                               #   Re-measure this window before trusting it on a new corpus.
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


def _is_calendar_year(value: float) -> bool:
    """True for a bare four-digit integer in the calendar-year range."""
    return float(value).is_integer() and 1900 <= value <= 2100


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

    # Fallback: no unit context found in at least one text → use first numbers.
    #
    # Calendar years are excluded here. A bare 19xx/20xx integer in a policy
    # document is almost always the document's own version or effective date —
    # metadata about the text, not a value the text asserts. Because this branch
    # compares "the first number in each span" with no notion of what either
    # number measures, an unfiltered year turns ordinary document versioning
    # into a contradiction: Corpus-2 Q029 fired on two "Purpose" boilerplates,
    # one "effective for the 2025-2026 academic year" and one "This 2022 policy
    # previously governed...", neither of which asserts a policy value at all.
    # Scoped to the fallback deliberately: a year-shaped number that carries a
    # real unit ("2000 hours") is extracted by _extract_numbers_with_unit above
    # and never reaches here.
    nums_a = [n for n in _extract_numbers(text_a) if not _is_calendar_year(n)]
    nums_b = [n for n in _extract_numbers(text_b) if not _is_calendar_year(n)]
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
# Stage 0 — Evidence Provenance  (NEW)
# ===========================================================================

# Fingerprints of every chunk in the corpus this pipeline is answering from,
# published by the retrieval layer after ingestion (see
# qdrant_retrieval.load_chunk_registry). None means "no registry available",
# in which case the check is skipped: a store built before registries existed
# must keep working, and refusing all evidence would be the wrong failure mode
# for a missing file. Populated via set_evidence_registry().
_EVIDENCE_REGISTRY: Optional[set[str]] = None


def set_evidence_registry(fingerprints: Optional[set[str]]) -> None:
    """Publish the corpus's chunk fingerprints for Stage 0 verification."""
    global _EVIDENCE_REGISTRY
    _EVIDENCE_REGISTRY = fingerprints


def evidence_fingerprint(text: str) -> str:
    """
    Fingerprint used by Stage 0. Delegates to qdrant_retrieval.chunk_fingerprint
    (the function that writes the registry this is checked against) so the two
    sides of the provenance check cannot drift apart. Imported lazily to match
    the existing retrieval->validation lazy-import direction and avoid a
    module-load-time circular import.
    """
    from qdrant_retrieval import chunk_fingerprint
    return chunk_fingerprint(text)


def verify_provenance(chunks: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Stage 0: split evidence into chunks that provably came from the ingested
    corpus and chunks that did not.

    Why this exists
    ---------------
    Every later stage answers the question "is this evidence good enough?" and
    none of them can answer "is this evidence real?". A fabricated passage
    carrying a high retrieval score satisfies the sufficiency gate exactly as a
    genuine one does, because the gate reads scores and text, both of which the
    fabricator supplies (measured: a fake chunk injected into a genuine
    knowledge gap passed the gate 4 times out of 4). No threshold can fix that,
    because the fabricated evidence is not weak; it is false.

    Provenance is checked instead of judged: a chunk counts as evidence only if
    its fingerprint appears in the registry written when the corpus was
    ingested. This is a deterministic set membership test, so it is immune to
    how persuasive the fabricated text is, and it distinguishes the case
    deterministic logic previously could not tell apart: evidence that is absent
    versus evidence that is invented.

    Returns (verified, rejected). When no registry is available every chunk is
    returned as verified.
    """
    if _EVIDENCE_REGISTRY is None:
        return list(chunks), []

    verified: list[dict] = []
    rejected: list[dict] = []
    for chunk in chunks:
        if evidence_fingerprint(chunk.get("text", "")) in _EVIDENCE_REGISTRY:
            verified.append(chunk)
        else:
            rejected.append(chunk)

    if rejected:
        _log.warning(
            "[Stage 0] Rejected %d chunk(s) with no provenance in the ingested "
            "corpus (sources: %s).",
            len(rejected),
            sorted({c.get("source", "unknown") for c in rejected}),
        )
    return verified, rejected


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

def _knee_cut(chunks: list[dict]) -> list[dict]:
    """
    Cut the evidence list at the largest discontinuity in its score curve.

    Scale-free by construction: it compares gaps *within one query's own
    results* rather than testing scores against a fixed number, so it carries
    nothing corpus-specific across to a new corpus. The guard is a ratio (this
    jump must be KNEE_GAP_MULTIPLE times the median jump), which is likewise a
    relationship between gaps rather than a magnitude.

    Returns the list unchanged when no jump stands out, which is the safe
    direction: keeping a weak chunk costs precision, dropping a strong one can
    remove half of a genuine contradiction.
    """
    if KNEE_GAP_MULTIPLE <= 0 or len(chunks) <= MIN_KNEE_KEEP:
        return chunks

    ordered = sorted(chunks, key=lambda c: c.get("score", 0.0), reverse=True)
    scores = [c.get("score", 0.0) for c in ordered]
    gaps = [scores[i] - scores[i + 1] for i in range(len(scores) - 1)]
    if not gaps:
        return chunks

    positive = sorted(g for g in gaps if g > 0)
    if not positive:
        return chunks
    mid = len(positive) // 2
    median_gap = (positive[mid] if len(positive) % 2
                  else (positive[mid - 1] + positive[mid]) / 2)
    if median_gap <= 0:
        return chunks

    # Only consider cut points that leave at least MIN_KNEE_KEEP chunks.
    candidates = [(gaps[i], i + 1) for i in range(len(gaps)) if i + 1 >= MIN_KNEE_KEEP]
    if not candidates:
        return chunks
    largest_gap, cut_at = max(candidates)
    if largest_gap < KNEE_GAP_MULTIPLE * median_gap:
        return chunks
    return ordered[:cut_at]


def filter_by_relevance(chunks: list[dict], query: str, *,
                        apply_score_floor: bool = True) -> list[dict]:
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
    if apply_score_floor:
        chunks = [c for c in chunks if c.get("score", 0.0) >= MIN_CHUNK_SCORE_THRESHOLD]
        chunks = _knee_cut(chunks)

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

MIN_CONTAINMENT_CHARS: int = 30   # shortest span that may be judged a duplicate
                                  # of another by containment (see _same_assertion)


def _normalize_span(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace — for identity tests only."""
    return " ".join(re.sub(r"[^\w\s]", " ", text.lower()).split())


def _same_assertion(text_a: str, text_b: str) -> bool:
    """
    True when two spans assert the same thing, so they cannot contradict.

    Exact match, or one normalized span contained verbatim in the other. See
    the call site in ``find_conflict`` for why containment is needed: chunk
    boundaries clip shared boilerplate at the head, leaving two strings that
    differ while saying the same thing.
    """
    if text_a == text_b:
        return True
    na, nb = _normalize_span(text_a), _normalize_span(text_b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    shorter, longer = (na, nb) if len(na) <= len(nb) else (nb, na)
    return len(shorter) >= MIN_CONTAINMENT_CHARS and shorter in longer


MAX_CONFLICT_SENTENCES: int = int(
    os.getenv("RAG_MAX_CONFLICT_SENTENCES", "4")
)                                              # per chunk, most query-relevant first.
                                               # Bounds the sentence-pair cross product
                                               # in find_conflict; a chunk contributes at
                                               # most this many candidate assertions.
MIN_CONFLICT_SENTENCE_CHARS: int = 25          # below this a "sentence" is a heading or
                                               # a stray fragment, not an assertion


# ---------------------------------------------------------------------------
# Query focus terms — corpus-IDF weighted (Stage 4 anchor test)
# ---------------------------------------------------------------------------
# A query's content words are not equally informative. "How large is the annual
# bonus and when is it paid?" shares the word "paid" with virtually every
# sentence in a pay policy, but only sentences about BONUSES answer it. Matching
# on any shared content term is therefore too weak to scope a contradiction:
# measured on Corpus 1, "Bonuses are paid in the April payroll" was compared
# against "Salaries are paid monthly in arrears on the 25th" and flagged as a
# contradiction, the two sentences having nothing in common but "paid".
#
# Rarity is measured against the ingested corpus (document frequency over
# chunks), a statistic the retriever's sparse stage already computes, and the
# selection is RANK-based (the rarest half of what was asked) rather than an
# absolute IDF cutoff. A rank means the same thing on any corpus; an absolute
# cutoff is exactly the kind of fitted constant that failed to transfer before.
# Question scaffolding — words that frame a question rather than name its
# subject. Used ONLY by _focus_terms, deliberately not added to
# _COVERAGE_STOPWORDS: that set is shared with the H4 coverage check, and
# widening it perturbs sufficiency for every query (adding conjunctions to it
# was tested and rejected for exactly that reason). Keeping the two lists
# separate means the anchor test can be corrected without re-opening H4.
#
# These need excluding because corpus IDF actively MIS-ranks them. IDF measures
# rarity in the documents, and a word like "versus" or "many" is rare in a
# policy document precisely because it is question vocabulary, not subject
# matter — so it scores as maximally discriminative and crowds out the real
# topic. Measured on Corpus 1 Q036 ("What does the probationary period length
# say in the Handbook versus the Recruitment policy?"), the selected focus
# terms were {length, recruitment, say, versus} while "probationary", the
# actual subject, was dropped as too common. The conflict was missed.
_QUESTION_SCAFFOLD: frozenset[str] = frozenset({
    # reporting verbs — refer to what a document says, not to what it is about
    "say", "says", "said", "mention", "mentions", "mentioned", "according",
    # comparison framing
    "versus", "vs", "difference", "differences", "differ", "differs",
    # quantity / degree framing
    "many", "much", "up", "per",
    # desire and modality framing
    "like", "want", "wants", "need", "needs", "wish",
})


_CORPUS_DF: dict[str, int] | None = None
_CORPUS_DOCS: int = 0
ANCHOR_REQUIRE_BOTH: bool            = os.getenv(
    "RAG_ANCHOR_REQUIRE_BOTH", "1") not in ("0", "false", "False")
                                               # Stage 4 anchor test: must BOTH sentences of a pair
                                               # mention a query focus term, or is one enough?
                                               # Requiring both is stricter than the concept needs
                                               # and fails on asymmetric vocabulary — two documents
                                               # stating the same rule, one formally and one not.
                                               # Corpus-2 Q045: focus {progress, requirement}; the
                                               # 2.5 side says "Satisfactory Academic Progress ...
                                               # 2.5" and anchors, the 2.0 side states the same rule
                                               # informally and does not, so a genuine conflict is
                                               # suppressed.
FOCUS_KEEP_FRACTION: float = 0.5   # rarest half of the query's content terms
MIN_STEM_MATCH_CHARS: int = 4      # below this, containment matching is unsafe

_WORD_RE = re.compile(r"[a-z][a-z']*")


def _tokenize(text: str) -> list[str]:
    """
    Alphabetic tokens only; hyphens are separators.

    Numerals are excluded deliberately: a figure in the question ("a gift worth
    GBP 70") is the value being asked ABOUT, so its absence from the evidence
    says nothing about whether the evidence answers the question.
    """
    return _WORD_RE.findall(text.lower().replace("-", " "))


def _stem(word: str) -> str:
    """
    Conservative suffix stripping: plural and participle endings only.

    A full Porter stemmer conflates more aggressively (e.g. "policy"/"police"),
    which for a policy corpus is the wrong trade. The goal is only to stop
    morphology from hiding a term that is plainly present -- "claims submitted"
    should satisfy a question about "submitting a claim".
    """
    for suffix, repl in (("ies", "y"), ("ied", "y"), ("sses", "ss"),
                         ("ing", ""), ("ed", ""), ("es", ""), ("s", "")):
        if word.endswith(suffix) and len(word) - len(suffix) + len(repl) >= 3:
            return word[: len(word) - len(suffix)] + repl
    return word


def _stems(text: str) -> set[str]:
    return {_stem(t) for t in _tokenize(text)}


def set_corpus_stats(stats: Optional[dict]) -> None:
    """
    Publish the ingested corpus's document frequencies (see
    qdrant_retrieval.load_corpus_stats). Passing None disables focus weighting,
    in which case the anchor test is skipped rather than guessing.
    """
    global _CORPUS_DF, _CORPUS_DOCS
    if not stats:
        _CORPUS_DF, _CORPUS_DOCS = None, 0
        return
    _CORPUS_DF = stats.get("df") or {}
    _CORPUS_DOCS = int(stats.get("doc_count") or 0)


def _idf(term: str) -> float:
    """Smoothed IDF over chunks. An unseen term is maximally rare."""
    df = (_CORPUS_DF or {}).get(_stem(term), 0)
    return math.log((_CORPUS_DOCS + 1) / (df + 1))


def _focus_terms(query: str) -> set[str]:
    """
    The query's discriminative terms: the rarest FOCUS_KEEP_FRACTION of its
    content words by corpus IDF. Empty when no corpus statistics have been
    published, which disables the anchor test rather than approximating it.
    """
    if not _CORPUS_DF or not _CORPUS_DOCS:
        return set()
    expanded: set[str] = set()
    for term in _query_content_terms(query):
        expanded |= {w for w in _tokenize(term) if len(w) > 2}
    expanded -= _QUESTION_SCAFFOLD

    # A term the corpus does not contain at all cannot anchor anything.
    #
    # Smoothed IDF treats an unseen term as MAXIMALLY rare, which is right for
    # judging whether evidence answers a question (a query term absent from the
    # evidence is exactly what signals a knowledge gap) and wrong for choosing
    # what a contradiction must be about. An out-of-vocabulary term is not
    # highly discriminative, it is simply not in the corpus, and requiring a
    # sentence to mention it guarantees the anchor test suppresses everything.
    #
    # This is what made the anchor test sensitive to the query's surface form.
    # Appending "Thanks!" put "thanks" — df 0 in a policy corpus, therefore top
    # of the IDF ranking — into the focus set, no evidence sentence mentioned
    # it, and genuine conflicts stopped firing: 6 decisions changed on Corpus 1
    # under `query_thanks`, 4 of them abstain -> answer. Restricting focus to
    # in-vocabulary terms removes that whole class, including the reason
    # _QUESTION_SCAFFOLD was needed for words like "versus" and "many".
    #
    # Absence stays a sufficiency signal (H4 coverage); it is only barred from
    # being an ANCHOR signal.
    expanded = {t for t in expanded if (_CORPUS_DF or {}).get(_stem(t), 0) > 0}
    if not expanded:
        return set()
    ranked = sorted(expanded, key=lambda t: (-_idf(t), t))
    keep = max(1, round(len(ranked) * FOCUS_KEEP_FRACTION))
    return set(ranked[:keep])


def _mentions_focus(sentence: str, focus: set[str]) -> bool:
    """
    Does *sentence* mention at least one of the query's focus terms?

    Stemmed, with a containment fallback in either direction so that a term
    split by a chunk boundary is still recognised. Floored at
    MIN_STEM_MATCH_CHARS so short stems cannot match by accident.
    """
    if not focus:
        return True
    evidence = _stems(sentence)
    for term in focus:
        stem = _stem(term)
        if stem in evidence:
            return True
        if len(stem) >= MIN_STEM_MATCH_CHARS and any(
                len(e) >= MIN_STEM_MATCH_CHARS and (e in stem or stem in e)
                for e in evidence):
            return True
    return False


def _query_relevant_sentences(text: str, content_terms: set[str],
                              limit: Optional[int] = None) -> list[str]:
    """
    The sentences of *text* that mention the query, most relevant first.

    Ranked by how many query content terms each sentence carries, so the
    bounded cross product in ``find_conflict`` spends its budget on the
    sentences most likely to answer the question. With no content terms (no
    query) the text is simply split into sentences, preserving the previous
    whole-text behaviour.
    """
    limit = MAX_CONFLICT_SENTENCES if limit is None else limit
    scored: list[tuple[int, str]] = []
    for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
        sentence = sentence.strip()
        if len(sentence) < MIN_CONFLICT_SENTENCE_CHARS:
            continue
        if content_terms:
            toks = {w.lower().strip(".,;:?!'\"()") for w in sentence.split()}
            overlap = len(toks & content_terms)
            if overlap == 0:
                continue
        else:
            overlap = 1
        scored.append((overlap, sentence))
    scored.sort(key=lambda pair: -pair[0])
    return [sentence for _, sentence in scored[:limit]]


def _contradiction_kind(text_a: str, text_b: str) -> Optional[str]:
    """
    Run the three contradiction prongs over one pair of spans.

    A) Keyword antonyms — cheap and precise, so gated on high lexical overlap.
    B) NLI — deliberately NOT gated on high lexical overlap (Finding 1): its
       purpose is paraphrastic contradictions, which by definition share little
       vocabulary. Only the NLI_SIM_FLOOR performance guard applies.
    C) Numeric, unit-aware — cheap/precise, gated on high lexical overlap.
    """
    if _same_assertion(text_a, text_b):
        return None
    sim = compute_chunk_similarity(text_a, text_b)
    high_sim = sim >= CONFLICT_SIM_THRESHOLD
    if high_sim and _has_keyword_contradiction(text_a, text_b):
        return "keyword"
    if sim >= NLI_SIM_FLOOR and _has_nli_contradiction(text_a, text_b):
        return "nli"
    if high_sim and _has_numeric_contradiction(text_a, text_b):
        return "numeric"
    return None


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
    focus = _focus_terms(query)

    # Query-relevance gate: the score a chunk must reach to be eligible for
    # comparison at all, defined as the score of this query's Nth-best chunk.
    # Deriving it from the current query's own ranking (rather than an absolute
    # score) is what makes the gate corpus-independent.
    rank_cutoff: float | None = None
    if MAX_CONFLICT_EVIDENCE_RANK > 0 and len(chunks) > MAX_CONFLICT_EVIDENCE_RANK:
        ranked_scores = sorted((c.get("score", 0.0) for c in chunks), reverse=True)
        # Tie-tolerant: admit everything within RANK_TIE_EPSILON of the Nth
        # score, so chunks the retriever could not meaningfully separate are
        # never split by their position in the list. Without this the gate is a
        # knife edge — Corpus-1 Q047's conflicting chunk sat 0.0006 below the
        # cutoff, and prefixing the query with "Could you tell me:" perturbed
        # the embedding by ~0.001, moved it 0.0001 above, and changed the
        # decision from conflict to answer.
        rank_cutoff = ranked_scores[MAX_CONFLICT_EVIDENCE_RANK - 1] - RANK_TIE_EPSILON

    for i, a in enumerate(chunks):
        for b in chunks[i + 1:]:
            # Skip if from the same source file
            source_a = a.get("source", "unknown_a")
            source_b = b.get("source", "unknown_b")
            if source_a == source_b and source_a != "unknown":
                continue

            # Both chunks must be top-ranked evidence FOR THIS QUERY. A
            # contradiction between two chunks the retriever ranked well below
            # the best evidence is a disagreement the corpus contains, not one
            # the answer depends on. Checked before the spans are built so
            # irrelevant pairs also skip the expensive NLI inference.
            if rank_cutoff is not None and (
                    a.get("score", 0.0) < rank_cutoff or b.get("score", 0.0) < rank_cutoff):
                continue

            # Guard: both chunks must be individually relevant to the query.
            rel_a = a.get("relevance_score", a.get("score", 0.0))
            rel_b = b.get("relevance_score", b.get("score", 0.0))
            if rel_a < MIN_CONFLICT_RELEVANCE or rel_b < MIN_CONFLICT_RELEVANCE:
                continue

            # Query-scoping: compare the query-relevant SENTENCES pairwise.
            #
            # This used to join every query-relevant sentence of each chunk into
            # one span and hand the two spans to NLI as a single premise pair.
            # That is the wrong granularity, and it was being propped up by a
            # bug: chunks used to arrive truncated, so the "spans" were short
            # and NLI saw something close to a sentence pair by accident. With
            # whole chunks the spans run to several sentences and the
            # contradiction signal dilutes below threshold. Measured on
            # Corpus-2 Q037, a genuine 2.5-vs-2.0 GPA conflict:
            #
            #     multi-sentence spans -> _has_nli_contradiction False
            #     the two answer sentences alone -> True
            #
            # Comparing sentence to sentence also makes the reported evidence
            # exact: the pair returned below is the sentence that actually
            # contradicts, not a paragraph containing it.
            sents_a = _query_relevant_sentences(a["text"], content_terms)
            sents_b = _query_relevant_sentences(b["text"], content_terms)
            if not sents_a or not sents_b:
                continue

            kind: Optional[str] = None
            text_a = text_b = ""
            for cand_a in sents_a:
                for cand_b in sents_b:
                    # Anchor test: both sentences must assert something about
                    # what was actually asked, judged on the query's FOCUS terms
                    # (its rarest content words) rather than on any shared word.
                    # This is the difference between "these two sentences are
                    # about the same topic" and "these two sentences are
                    # candidate answers to this question". A real contradiction
                    # between two documents is only a reason to abstain when it
                    # is a contradiction about the thing being asked; otherwise
                    # one genuine conflict re-fires under every query that
                    # happens to share a common word with it.
                    anchored_a = _mentions_focus(cand_a, focus)
                    anchored_b = _mentions_focus(cand_b, focus)
                    if not (anchored_a and anchored_b if ANCHOR_REQUIRE_BOTH
                            else anchored_a or anchored_b):
                        continue

                    # Query-intent gate, now per sentence: a contradiction only
                    # justifies abstention when BOTH sentences are about what
                    # the user asked. Runs before the prongs so irrelevant
                    # pairs skip the expensive NLI inference.
                    if QUERY_SPAN_RELEVANCE > 0.0 and query.strip():
                        if (_query_span_similarity(query, cand_a) < QUERY_SPAN_RELEVANCE
                                or _query_span_similarity(query, cand_b) < QUERY_SPAN_RELEVANCE):
                            continue
                    kind = _contradiction_kind(cand_a, cand_b)
                    if kind:
                        text_a, text_b = cand_a, cand_b
                        break
                if kind:
                    break

            if kind:
                _log.debug(
                    "[Stage 4] %s conflict: '%s' vs '%s'",
                    kind, source_a, source_b,
                )
                return {
                    "kind": kind,
                    "chunks": [
                        {"source": source_a, "section": a.get("section", "unknown"),
                         "text": text_a},
                        {"source": source_b, "section": b.get("section", "unknown"),
                         "text": text_b},
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
    # Personal pronouns. "me", "my" and "it" were already excluded; the rest of
    # the set was not, which left first- and second-person pronouns counting as
    # query CONTENT. A pronoun is never a topic: "i" occurs in virtually every
    # English chunk, so it is covered for free and inflates H4 by one term.
    # Measured on Corpus 2 Q053 ("How do I get credit for a semester studying
    # abroad?"): coverage 0.6 = 3/5, and the three "covered" terms were
    # "credit", "semester" and "i", while the two terms that define the
    # question -- "studying" and "abroad" -- were absent from the evidence
    # entirely. Completing the pronoun set is a correction to what counts as
    # content, not a re-tuning of MIN_QUERY_COVERAGE.
    "i", "we", "us", "our", "ours", "you", "your", "yours",
    "myself", "ourselves", "yourself", "they", "them", "their", "theirs",
    # NOTE: adding conjunctions/negation ("and", "or", "but", "not", "if") here
    # was tested and REJECTED. It is defensible on the same grounds as the
    # pronouns -- "and" is grammatical glue, not a topic -- but shrinking the
    # denominator raises coverage for answerable and gap queries alike:
    # Corpus 2 accuracy fell 80.8% -> 79.5% (Q019 answer -> insufficient) while
    # recovering none of the three over-abstentions it was meant to address.
    # See docs/archive/FIXES_REPORT.md, follow-up round item 3.
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
    # H2 describes the quality of an evidence *set*. Over a single surviving
    # chunk it is not an average at all: it is that one chunk's score wearing
    # the authority of a set-level statistic, and a lone chunk sitting just
    # above the Stage-3 floor then satisfies it. That is precisely how gap
    # queries leaked on Corpus 2 (Q050/Q055/Q078: one chunk each, averages
    # 0.658-0.678 against a 0.65 bar, while the coverage branch correctly
    # rejected all three). Requiring the average branch to describe at least
    # MIN_CHUNKS_FOR_AVG_SUFFICIENCY chunks is a structural correction, not a
    # re-tuned threshold: a single chunk must now earn sufficiency on coverage.
    avg_applies = len(chunks) >= MIN_CHUNKS_FOR_AVG_SUFFICIENCY
    if not (avg_applies and avg_score >= MIN_AVG_SCORE_FOR_SUFFICIENCY) \
            and coverage < MIN_QUERY_COVERAGE:
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
    # ── Stage 0: Provenance ───────────────────────────────────────────────
    # Runs before everything else: evidence that cannot be traced to the
    # ingested corpus is not weak evidence, it is not evidence, and no later
    # stage is able to notice the difference.
    stage0, rejected = verify_provenance(chunks)

    # ── Stage 1: Normalize ────────────────────────────────────────────────
    stage1 = normalize_chunks(stage0)

    # ── Stage 2: Deduplicate ──────────────────────────────────────────────
    stage2 = remove_duplicates(stage1)

    # ── Stage 3: Relevance Filtering ──────────────────────────────────────
    # V4: uses embedding-based relevance_score if already present in chunks
    # (set by retrieval.py); falls back to TF-cosine if not.
    stage3 = filter_by_relevance(stage2, query)
    relevant_count = len(stage3)

    # Stage 4 and Stage 5 ask different questions and need different evidence.
    #
    # Sufficiency asks "is this evidence good enough to answer from?", so it must
    # judge on strong evidence only — that is what MIN_CHUNK_SCORE_THRESHOLD is
    # for, and removing it floods the evidence set: Corpus-1 gap leaks go 1/16 ->
    # 10/16 with the floor off.
    #
    # Conflict detection asks "do any two of these disagree?", which needs
    # RECALL. Half of a contradiction is often the weaker chunk, and once the
    # floor has discarded it no amount of work in Stage 4 can recover it:
    # Corpus-2 Q038's conflicting chunk scored 0.5945 and Q076's 0.5751, both
    # just under a 0.60 bar, and both conflicts were unrecoverable at ANY
    # rank-gate setting for exactly this reason.
    #
    # Serving both from one cutoff forces a trade between gap leaks and conflict
    # recall that neither stage actually requires. The separation is structural:
    # a contradiction is DETECTED over everything plausibly relevant, while an
    # answer is BUILT only from evidence strong enough to support it. Weak
    # evidence can therefore block an answer but never produce one, which is the
    # safe direction for both stages.
    stage3_wide = filter_by_relevance(stage2, query, apply_score_floor=False)

    # ── Stage 4: Conflict Detection ────────────────────────────────────────
    # Runs on the RELEVANCE-FILTERED set (stage3).
    # Rationale: a contradiction between two documents should only trigger
    # abstention if both documents are relevant to the current query.
    # find_conflict returns the offending pair (or None) so downstream code can
    # show *which* documents disagree instead of listing every retrieved source.
    conflict_detail = find_conflict(stage3_wide, query=query)
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
        "unverified_count"    : len(rejected),
        "unverified_sources"  : sorted({c.get("source", "unknown") for c in rejected}),
    }
