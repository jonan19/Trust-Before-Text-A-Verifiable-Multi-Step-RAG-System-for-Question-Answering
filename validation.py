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
# Answerhood model — lazy-loaded, used only by the Stage 4 ANSWERHOOD_MARGIN
# gate. Distinct from the topic bi-encoder above: a cross-encoder measures
# query/sentence ANSWERHOOD (does this sentence answer the question?), which
# is a different signal from topical cosine similarity — see the
# "Answer-Anchored Relevance Gating" plan and the falsified "query/span
# embedding similarity gate" entry in docs/STATUS.md, which is the bi-encoder
# above, not this. Shipped enabled 2026-08-24 (ANSWERHOOD_MARGIN default 5.5);
# set RAG_ANSWERHOOD_MARGIN=0 to disable.
# ---------------------------------------------------------------------------
_ANSWERHOOD_MODEL: "_CrossEncoder | None" = None  # type: ignore[type-arg]
_ANSWERHOOD_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def _get_answerhood_model():  # type: ignore[type-arg]
    """
    Lazy-load the answerhood cross-encoder. A fixed encoder, not a generative
    model, so it does not weaken the pipeline's determinism guarantee — same
    argument as _get_topic_model. Returns None if unavailable, in which case
    the gate degrades open (see _answerhood_margins).
    """
    global _ANSWERHOOD_MODEL
    if not _CROSSENCODER_AVAILABLE:
        return None
    if _ANSWERHOOD_MODEL is None:
        try:
            _log.info("[Validation] Loading answerhood model '%s' (first use)...",
                      _ANSWERHOOD_MODEL_NAME)
            _ANSWERHOOD_MODEL = _CrossEncoder(_ANSWERHOOD_MODEL_NAME)
        except Exception as exc:  # pragma: no cover
            _log.warning("[Validation] Failed to load answerhood model: %s — "
                         "ANSWERHOOD_MARGIN gate disabled for this process.", exc)
            return None
    return _ANSWERHOOD_MODEL


def _answerhood_margins(query: str, pool: list[str]) -> dict[str, float]:
    """
    For every sentence in *pool*, its answerhood MARGIN to this query's own
    top-1 score: 0.0 for the best-scoring sentence, growing for worse ones.
    A per-query relative measure rather than an absolute cutoff — raw
    cross-encoder scores are uncalibrated logits that do not transfer across
    corpora (see ANSWERHOOD_MARGIN); the margin is corpus-independent the same
    way the retired MAX_CONFLICT_EVIDENCE_RANK's rank cutoff was.

    Degrades OPEN: returns {} (empty) when the model is unavailable or *pool*
    is empty, so a missing optional dependency can never silently suppress
    conflict detection — callers must treat an empty mapping as "gate off",
    the same safe-direction contract as _query_span_similarity.
    """
    if not pool:
        return {}
    model = _get_answerhood_model()
    if model is None:
        return {}
    try:
        raw = model.predict([(query, s) for s in pool])
        top1 = float(max(raw))
        return {s: top1 - float(r) for s, r in zip(pool, raw)}
    except Exception as exc:  # pragma: no cover
        _log.warning("[Validation] answerhood margin error: %s — gate skipped.", exc)
        return {}

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
ANSWERHOOD_MARGIN: float             = float(
    os.getenv("RAG_ANSWERHOOD_MARGIN", "5.5")
)                                              # Stage 4 ANSWERHOOD gate (suppress-only): both sentences of
                                               # a candidate pair must score within this MARGIN of this
                                               # query's own top-1 answerhood score
                                               # (cross-encoder/ms-marco-MiniLM-L-6-v2 over the query's
                                               # candidate-sentence pool) before the pair may be compared.
                                               # Distinct signal from QUERY_SPAN_RELEVANCE above: that gate
                                               # is a bi-encoder measuring TOPICALITY (is this span about
                                               # the same subject?) and was falsified as a class separator
                                               # on Corpus 2 (docs/STATUS.md, falsified-candidates table).
                                               # A cross-encoder measures ANSWERHOOD (does this span answer
                                               # THIS question?) — a decorrelated signal per the
                                               # "Answer-Anchored Relevance Gating" plan. A margin, not an
                                               # absolute score, for the same corpus-transfer reason
                                               # QUERY_SPAN_RELEVANCE and the retired
                                               # MAX_CONFLICT_EVIDENCE_RANK are both relative to the
                                               # query's own ranking rather than fitted. This gate may only
                                               # SUPPRESS a conflict the deterministic layer already raised
                                               # (find_conflict tries the next candidate pair, never
                                               # creates a new abstention) — see claude.md, "The LLM Is Not
                                               # the Variable". 0.0 disables the gate entirely.
                                               #
                                               # SHIPPED 2026-08-24 at 5.5 (was 0.0/disabled). Confirmed
                                               # end-to-end, not just in the offline lab — see
                                               # evaluation/results/invariance_corpus{1,2}.json:
                                               #   Live at delta=5.5 (evaluation/run_eval.py): C2 false
                                               #   conflicts 9->2, conflict precision 0.625->0.875,
                                               #   attribution precision 0.583->0.875, accuracy 82.1%->89.7%.
                                               #   C1 unaffected (already 0 false conflicts).
                                               #   Invariance (evaluation/invariance_harness.py, gate ON):
                                               #   all four structural transforms (permute/duplicate/
                                               #   distractor/query_lower) stay 0/78 on both corpora — no
                                               #   violation introduced. query_thanks/query_polite actually
                                               #   IMPROVE with the gate on (C1 unsafe flips 1+1 -> 0+0).
                                               #   Cost: C2 conflict recall 15/16 -> 14/16 (Q036) — but Q036
                                               #   was already a wrong-evidence report (see claude.md failure
                                               #   pattern #3), so this is a wrong-evidence-citation ->
                                               #   honest-refusal move, not a new unsafe answer (unsafe
                                               #   answers stayed 1/32, still only Q045). Accepted per
                                               #   claude.md's Five-Line Decision Rule, Rule 3 (trades error
                                               #   toward safety; cost documented here and in docs/STATUS.md).
                                               #
                                               # CALIBRATION (evaluation/answerhood_lab.py Phase 1):
                                               #   Attribution-aware go/no-go over both corpora's Stage-4
                                               #   reported pairs (misattributed "right decision, wrong
                                               #   evidence" reports counted as false-evidence, not true):
                                               #   flat band [5.04, 6.65) covers all 30 correctly-attributed
                                               #   true conflicts while suppressing 8/10 false-evidence
                                               #   reports (vs. 1/10 for the equivalent QUERY_SPAN_RELEVANCE
                                               #   bound on the same data). The 2 surviving false conflicts
                                               #   are Corpus 2's two hardest known cases (docs/STATUS.md
                                               #   Problem 1): the 21-vs-18 credit-hours pair and the
                                               #   Dean's-List-vs-financial-aid GPA pair, whose margins
                                               #   (4.44, 3.68) sit BELOW a true conflict's (5.04) and so
                                               #   cannot be separated without losing that true conflict.
                                               #   Re-measure this band before trusting it on a new corpus —
                                               #   set RAG_ANSWERHOOD_MARGIN=0 to restore prior behaviour.
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
MIN_FOCUS_PRESENCE: float            = float(
    os.getenv("RAG_MIN_FOCUS_PRESENCE", "0.5")
)                                              # Stage 5 focus-presence precondition, applied BEFORE
                                               # the H2/H4 disjunction: this fraction of the query's
                                               # focus terms (_sufficiency_focus_terms — the rarest
                                               # half of its content words, out-of-vocabulary terms
                                               # KEPT) must actually appear in the evidence.
                                               # 0.0 disables the gate and restores the previous
                                               # H2-OR-H4 behaviour exactly.
                                               #
                                               # WHY a fraction and not the pure presence test that
                                               # docs/STATUS.md Problem 2 specifies. The spec assumed
                                               # focus terms would be the query's TOPIC words, so
                                               # "present at all" would be unambiguous. Measured, they
                                               # are not: smoothed IDF ties every df-0 word at maximum
                                               # rarity, so a gap query's real subject (Q051
                                               # `relocation`, `moving`) and an answerable query's
                                               # framing verbs (Q013 `held`, `often`) rank
                                               # identically. Corpus-1 Q051 and Q013 are in fact
                                               # feature-identical here — 2 absent df-0 terms and 3
                                               # present in-vocabulary terms each — so NO rule over
                                               # focus-term presence separates them, and neither does
                                               # coverage (both 0.60). The gap is closed by requiring
                                               # a MAJORITY of focus terms present; Q013 is the price.
                                               #
                                               # FALSIFIED ALTERNATIVES (both corpora, decision-layer
                                               # only; "closes" = unsafe answers removed):
                                               #   0.0+ (pure presence, >=1 focus term): closes Q051
                                               #     only, costs Q013. Corpus 2 unchanged, so the
                                               #     Q017 leak SURVIVES (unsafe stays 2/32). This is
                                               #     the literal reading of the spec and it does not
                                               #     close the leak it was designed for.
                                               #   1.0 (ALL focus terms present): closes both leaks
                                               #     but costs 44 answerable queries (24 on C1, 20 on
                                               #     C2) — unusable.
                                               #   0.5 with FOCUS_KEEP_FRACTION 0.34: closes both,
                                               #     costs 13. With 0.67: closes Q051 only, costs 3.
                                               #   0.34 (i.e. "not 1-of-3"): closes both at cost 3
                                               #     rather than 4, but 0.34 is a value chosen to sit
                                               #     just above 1/3 for two queries. Rejected as a
                                               #     fitted constant, not on its measurement.
                                               # 0.5 at the inherited FOCUS_KEEP_FRACTION is the
                                               # cheapest configuration that closes both leaks without
                                               # a constant fitted to a specific query.

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

REQUIRE_ASSERTIVE_SPANS: bool = os.getenv(
    "RAG_REQUIRE_ASSERTIVE_SPANS", "1") == "1"
#   Stage 4 assertiveness precondition. A contradiction is a disagreement
#   between two ASSERTIONS; a span that states no rule cannot be half of one.
#
#   This generalises MIN_CONFLICT_SENTENCE_CHARS directly above, which tries to
#   express the same idea by length and cannot: a "Purpose ..." section header
#   is comfortably over 25 characters, passes that gate, and goes on to be
#   compared against another section header. Corpus 2 Q024 and Q029 are exactly
#   that — two scope statements flagged as contradicting each other:
#       "Purpose This policy governs on-campus housing eligibility ..."
#       "Purpose This policy governs campus emergency notification ..."
#
#   A span is assertive if it carries a QUANTITY or a DEONTIC term. Both true
#   conflict families survive by construction: the numeric ones (3 vs 6 months,
#   3 vs 2 days/week, 6% vs 5%) are quantitative, and the semantic one (C4,
#   permitted vs prohibited) is deontic. Measured, decision-only, both corpora:
#       Corpus 1  accuracy 92.3% -> 96.2%, conflict precision 0.842 -> 1.000,
#                 F1 0.914 -> 1.000, false conflicts 3 -> 0 (Q019/Q025/Q032),
#                 recall 16/16 unchanged, unsafe answers 0 unchanged.
#       Corpus 2  accuracy 80.8% -> 82.1%, precision 0.600 -> 0.625,
#                 false conflicts 10 -> 9 (Q024), recall 15/16 unchanged,
#                 unsafe answers 1 unchanged.
#   The rule was derived from Corpus 2 observations and removed all three
#   Corpus 1 false conflicts, none of which had been inspected when it was
#   written — cross-corpus transfer, not a fit. It introduces no threshold.
#   Set to 0 to restore the previous behaviour.

DIMENSIONAL_VETO: bool = os.getenv(
    "RAG_DIMENSIONAL_VETO", "1") == "1"
#   Stage 4 commensurability precondition, applied only when BOTH spans carry a
#   quantity. Two numbers may only contradict if they measure the same
#   dimension: "2 days per week" is a RATE, "26 weeks of continuous service" is
#   a DURATION, and no disagreement between them is possible. Corpus 1 Q076
#   reported precisely that pair — office attendance vs maternity-pay
#   eligibility — because both spans mention "week" and NLI scored them 0.9994.
#
#   This is the "dimensioned numeric comparison" named in the archived roadmap
#   and never implemented. Purely semantic conflicts are untouched: the veto
#   only runs when both sides are quantitative, so C4 (permitted vs prohibited)
#   never reaches it. Measured, decision-only, both corpora:
#       Corpus 1  decision accuracy unchanged, recall 16/16 unchanged, unsafe 0
#                 unchanged; conflict ATTRIBUTION precision 0.789 -> 0.842
#                 (Q076 now cites the pair it actually abstained on).
#       Corpus 2  identical to baseline in every metric.
#   Its value is traceability, not accuracy: it moves zero queries' decisions.
#   Set to 0 to restore the previous behaviour.


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

# Politeness / greeting tokens. Used ONLY by the Stage-5 focus computation
# (_sufficiency_focus_terms), which is why they are a separate set rather than
# more entries in _QUESTION_SCAFFOLD above.
#
# Stage 4 does not need them: _focus_terms drops every out-of-vocabulary term,
# and a policy corpus contains none of these (df 0 in both corpora), so adding
# them to _QUESTION_SCAFFOLD would be provably inert there. Stage 5 DOES need
# them, because it deliberately keeps out-of-vocabulary terms (an absent word is
# the gap signal it is looking for) and therefore inherits the exact failure
# _focus_terms was fixed for: smoothed IDF ranks an unseen word as maximally
# rare, so "Thanks!" appended to a question puts `thanks` at the top of the
# focus ranking, where it can never be present in the evidence.
#
# Measured, candidate gate at MIN_FOCUS_PRESENCE=0.5, `query_thanks` transform:
# without this set the focus gate flips on 19/78 queries on Corpus 1 and 13/78
# on Corpus 2; with it, 0/78 and 0/78. This is a category (gratitude/greeting
# framing), not a single token — _COVERAGE_STOPWORDS already carries "please"
# on identical grounds.
_POLITENESS_SCAFFOLD: frozenset[str] = frozenset({
    "thanks", "thank", "thankyou", "hi", "hello", "hey", "greetings",
    "regards", "kindly", "cheers", "appreciate", "appreciated",
})

# Enclitic suffixes, for recognising that a CONTRACTED stopword is still a
# stopword. _tokenize keeps apostrophes inside a token, so "I'm" survives whole
# and never meets the pronoun entries in _COVERAGE_STOPWORDS — the documented
# Q053 pronoun bug ("a pronoun is never a topic") recurring in contracted form.
# Measured on Corpus 2 Q074: focus {graduating, i'm, opt, visa}, with `i'm`
# occupying a quarter of the set.
_CLITIC_SUFFIXES: tuple[str, ...] = (
    "n't", "'re", "'ve", "'ll", "'m", "'d", "'s", "'t",
)


def _clitic_base(token: str) -> str:
    """"i'm" -> "i", "don't" -> "do", "dean's" -> "dean". Unchanged if no clitic."""
    for suffix in _CLITIC_SUFFIXES:
        if token.endswith(suffix) and len(token) > len(suffix):
            return token[: len(token) - len(suffix)]
    return token


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
ANCHOR_ASYMMETRIC_QSPAN: float       = float(
    os.getenv("RAG_ANCHOR_ASYMMETRIC_QSPAN", "0")
)                                              # DISABLED (0 = off, current behaviour exactly).
                                               # Candidate rescue for Corpus-2 Q045, the one genuine
                                               # contradiction the anchor test suppresses: when only
                                               # ONE sentence of a pair mentions a focus term, admit
                                               # the pair anyway if BOTH sentences reach this
                                               # query-span similarity. The intent was to buy back
                                               # asymmetric-vocabulary conflicts without the blanket
                                               # relaxation that was already falsified (anchor on
                                               # EITHER sentence: Corpus 1 precision 0.842 -> 0.640).
                                               # Diagnosed pair (Q045, both spans well clear of
                                               # QUERY_SPAN_RELEVANCE=0.35, NLI contradiction True,
                                               # blocked by the anchor test alone):
                                               #   0.6489 "...need-based financial aid, students must
                                               #           maintain at least a 2.0 cumulative GPA."
                                               #   0.7666 "Satisfactory Academic Progress ... minimum
                                               #           cumulative GPA of 2.5"
                                               #
                                               # MEASURED at 0.60, both corpora, on top of the Stage-5
                                               # focus gate (run_eval tag `aqs60`):
                                               #   Corpus 1: byte-identical to the default run —
                                               #     92.3%, precision 0.8421, recall 16/16, F1 0.9143,
                                               #     unsafe 0/32. The rescue never fires here.
                                               #   Corpus 2: recall 15/16 -> 16/16 (Q045 RECOVERED),
                                               #     unsafe 1/32 -> 0/32, F1 0.7317 -> 0.7442,
                                               #     accuracy 80.8% unchanged
                                               #     ... but precision 0.6000 -> 0.5926: one new false
                                               #     conflict, Q002 (answer -> conflict).
                                               #
                                               # SHIPPED DISABLED. It is a real improvement on every
                                               # axis except the one it was required not to move, and
                                               # 0.60 is a value read off Q045's own span similarity
                                               # (0.6489) — a constant derived from the query it was
                                               # meant to fix, on the corpus that is also the training
                                               # set (see docs/STATUS.md Problem 3). Raising the bar to
                                               # ~0.64 would very likely drop Q002 and keep Q045, and
                                               # that is precisely the fit-to-two-queries move this
                                               # project has repeatedly been burned by, so it was NOT
                                               # measured or adopted. Enable only with a third,
                                               # genuinely held-out corpus to calibrate against.
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


def _sufficiency_focus_terms(query: str) -> set[str]:
    """
    The Stage-5 twin of _focus_terms: the rarest FOCUS_KEEP_FRACTION of the
    query's content words by corpus IDF, but keeping OUT-OF-VOCABULARY terms.

    The two stages want opposite things from an absent word, so they cannot
    share one focus set.

      Stage 4 (anchor test) asks "what must a contradiction be ABOUT?". A term
      the corpus does not contain cannot answer that — requiring a sentence to
      mention it would suppress every pair — so _focus_terms drops it.

      Stage 5 (sufficiency) asks "does this evidence cover what was asked?". A
      query term the corpus does not contain at all is not noise, it is exactly
      the knowledge gap being looked for. Corpus 1 Q051 ("what relocation
      allowance...") is a gap precisely because `relocation` has df 0.

    Dropping the in-vocabulary filter re-exposes the failure it was introduced
    to fix — smoothed IDF ranks an unseen word as maximally rare, so question
    scaffolding floats to the top of the ranking — which is why this function
    subtracts _POLITENESS_SCAFFOLD as well as _QUESTION_SCAFFOLD. See the note
    at _POLITENESS_SCAFFOLD for the measurement.

    Returns an empty set when no corpus statistics have been published, which
    disables the Stage-5 focus gate rather than approximating it.

    FALSIFIED: "the ranking is the bug, not the presence test".
    ---------------------------------------------------------
    The three queries this gate over-abstains on (C1 Q013, C2 Q059, C2 Q074)
    all have their topic words outranked by df-0 framing words, which suggests
    the fix is to stop absent terms crowding out in-vocabulary ones. It is not.
    Measured (df, presence) profiles, contractions dropped and the stemmer-miss
    repair below applied:

      C1 Q051 must REFUSE: moving(0,absent) relocation(0,absent)
                           allowance(3,present) role(4,present) available(6,present)
      C1 Q013 must PASS  : held(0,absent) often(0,absent)
                           drills(2,present) evacuation(2,present) fire(2,present)

    Q013's present terms are strictly RARER than Q051's while their absent terms
    are identical, so under any ranking monotone in IDF, Q013 is harder to pass
    than Q051: the ordering is the exact opposite of what is needed. C2 Q017 vs
    Q059 are outright isomorphic (2 absent df-0, 4 present, rarest present df 2
    on both sides), and both select 1-of-3 present at the shipped setting.

    An exhaustive search over 2304 focus constructions — keep fraction, presence
    fraction, guaranteed in-vocabulary slots, dropping out-of-vocabulary terms
    entirely, with and without the two repairs below — found **0** that refuse
    Q051 and Q017 while passing Q013, Q059 and Q074. Relaxing the target to
    Q013 alone also yields 0. The three over-abstentions are not recoverable by
    reweighting corpus-frequency features; separating them needs a signal this
    function does not have (Q051's `allowance` is present only inside the
    unrelated compound "mileage allowance payments" — phrase-level or semantic
    matching, not term-level rarity).

    FALSIFIED: repairing the stemmer's morphology misses.
    ----------------------------------------------------
    _stem genuinely mis-stems: "graduating"/"graduated" -> "graduat" misses both
    "graduation" and "graduate"; "living" -> "liv" misses "live"; consonant
    doubling is not undone ("submitting" -> "submitt" vs "submit"); and "es"/"s"
    over-strip ("process" -> "proces", "address" -> "addres"). But _stem and
    _tokenize are what _write_corpus_stats keyed the ingested df index with, so
    the defect cannot be corrected at the stemmer without re-ingesting both
    stores. A lookup-side repair (probe stem+"e", stem+"ion", the un-doubled
    stem, and _stem applied twice) was built and measured instead: across all
    156 queries it raises df above 0 for exactly TWO terms, both on Corpus 2
    ("graduating" 0->1, "living" 0->1), and changes exactly ONE Stage-5 gate
    outcome (Q047 — a conflict query, where sufficiency does not reach the
    decision). It recovers none of the three over-abstentions, and because _idf
    also feeds the Stage-4 anchor test it would perturb conflict scoping for
    that zero gain. Not shipped.

    FALSIFIED: counting an absent focus term as present on EMBEDDING similarity.
    ---------------------------------------------------------------------------
    All three over-abstentions are paraphrase misses — the corpus answers the
    question in different words ("latin honors ... are awarded as follows:
    summa cum laude (3.9 and above)" for `tiers`/`cutoffs`; "applications ...
    must be filed between 90 and 60 days" for `apply`; "conducted" for `held`).
    So rescuing an absent term by semantic rather than lexical match is the
    obvious next move. Measured (max cosine between the term and any evidence
    sentence, same encoder as _query_span_similarity), it is not merely weak,
    it is ANTI-correlated with what is needed:

      must stay absent   relocation 0.4024  moving 0.2969  abroad 0.3983/0.3066
      must be rescued    held 0.0718  often 0.1071  cutoffs 0.1680  tiers 0.2385

    A gap query's missing subject is semantically CLOSE to its corpus — an HR
    corpus that has no relocation policy still discusses commuting and
    accommodation; an international-student policy has no study-abroad section
    but is all about immigration. A paraphrase gap is semantically FAR, because
    the words that get paraphrased are abstraction and framing words with weak
    embeddings. Passing Q013 needs a bar of 0.0718 or lower; refusing Q051 needs
    one above 0.4024. No threshold satisfies both, on any corpus, at any value —
    checked over 0.30-0.70. This is the same mechanism that killed the
    embedding-similarity gate for Stage-4 conflict pairing, arrived at
    independently.
    """
    if not _CORPUS_DF or not _CORPUS_DOCS:
        return set()
    expanded: set[str] = set()
    for term in _query_content_terms(query):
        expanded |= {w for w in _tokenize(term) if len(w) > 2}
    expanded -= _QUESTION_SCAFFOLD
    expanded -= _POLITENESS_SCAFFOLD
    # A contracted stopword is still a stopword — see _CLITIC_SUFFIXES. Only the
    # DROP decision uses the clitic base; the token itself is left untouched, so
    # "dean's" (base "dean", not a stopword) keeps the exact surface form whose
    # stem is the key stored in corpus_stats.json.
    #
    # Deliberately applied HERE and not in _tokenize, _query_content_terms or
    # _query_coverage:
    #   - _tokenize / _stem feed _write_corpus_stats, so the ingested df index is
    #     keyed by THIS tokenizer's output ("dean'", "days'", "approv", "proces").
    #     Changing either silently invalidates every df lookup against a store
    #     that cannot be rebuilt here, which would make focus ranking worse, not
    #     better.
    #   - _query_coverage's term set is H4's DENOMINATOR. Removing terms from it
    #     raises coverage for gap and answerable queries alike, which is the
    #     shape of change already falsified for conjunctions (Corpus 2 accuracy
    #     80.8% -> 79.5%). No gap query in either corpus contains a contracted
    #     stopword, so there is nothing to win there and a known way to lose.
    expanded = {t for t in expanded
                if _clitic_base(t) not in _COVERAGE_STOPWORDS
                and _clitic_base(t) not in _QUESTION_SCAFFOLD}
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


_DEONTIC_RE = re.compile(
    r"\b(must|may|shall|should|will|cannot|can't|prohibited|forbidden|"
    r"required|require[sd]?|entitled|eligible|allowed|permitted|expected|"
    r"obliged|banned|denied|granted)\b", re.IGNORECASE)

def _is_assertive_span(text: str) -> bool:
    """
    Does *text* assert a rule, rather than merely name a topic?

    A contradiction is a disagreement between two claims. A section header
    ("Purpose This policy governs campus emergency notification ...") names a
    scope and claims nothing, so pairing two of them is a category error rather
    than a disagreement — see REQUIRE_ASSERTIVE_SPANS for the measurement.

    Assertive = carries a quantity, or a deontic/modal term. Deliberately
    permissive: the job is to exclude boilerplate, not to parse the sentence.

    "Carries a quantity" is _DIM_RE — the SAME reading the dimensional veto
    uses — which requires a number governed by a unit ("3 months", "6%"), not
    merely a digit somewhere in the text. The distinction is load-bearing: a
    bare-digit test admits ordinals like "paid ... on the 25th of each month",
    which is Corpus 1 Q025, a false conflict against "Bonuses are paid in the
    April payroll". Measured: bare-digit reading leaves C1 at 94.9% with that
    false conflict standing; the unit-governed reading gives 96.2% and none.
    """
    return bool(_DIM_RE.search(text) or _DEONTIC_RE.search(text))


# Numerals written as words. The Corpus 2 academic-probation conflict disagrees
# in words ("one semester" vs "two consecutive semesters") while both spans also
# mention the same incidental "2.0 GPA". A digit-only reading therefore compares
# the 2.0s, finds them equal, and destroys a real conflict — measured at recall
# 15/16 -> 12/16 before this was added.
_WORD_NUMERALS: dict[str, str] = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
    "eleven": "11", "twelve": "12",
}
# Adjectives that may sit between a numeral and its unit and must be stepped
# over: "two consecutive semesters" measures semesters, not "consecutives".
_QTY_QUALIFIERS = frozenset({
    "consecutive", "additional", "further", "successive", "calendar",
    "business", "working", "academic", "cumulative", "full", "complete",
})
# A governing "noun" that is really a verb, pronoun or conjunction means the
# pattern matched across a clause boundary ("below 2.0 is placed" -> unit "i").
# Such a match carries no dimension and must be discarded, not compared.
_QTY_JUNK_UNITS = frozenset({
    "i", "is", "are", "was", "were", "be", "or", "and", "of", "the", "a", "an",
    "to", "in", "on", "at", "for", "with", "by", "higher", "lower", "above",
    "below", "more", "less", "least", "most", "over", "under", "up", "who",
    "that", "which", "will", "may", "must", "shall", "cumulative",
})
_DIM_NUM = r"(\d+(?:\.\d+)?)"
_DIM_RE = re.compile(
    _DIM_NUM + r"\s*(%|percent|per\s?cent)|"
    + _DIM_NUM + r"\s+([a-z]+?)s?\b(?:\s+(?:per|a|each|every)\s+([a-z]+?)s?\b)?",
    re.IGNORECASE)
_DIM_WORD_RE = re.compile(
    r"\b(" + "|".join(_WORD_NUMERALS) + r")\s+"
    + r"((?:(?:" + "|".join(_QTY_QUALIFIERS) + r")\s+)*)"
    + r"([a-z]+?)s?\b", re.IGNORECASE)


def _span_quantities(text: str) -> dict[tuple[str, str], set[str]]:
    """
    The quantities *text* asserts, keyed by their dimension.

    A key is (unit, period): ("day", "week") for "2 days per week" — a rate —
    versus ("week", "") for "26 weeks" — a duration. Two spans are
    commensurable only where their keys coincide. Calendar years are excluded:
    a year is a date, not a measured quantity, and admitting them made two
    "Purpose ..." headers look quantitative (Corpus 2 Q029).
    """
    found: dict[tuple[str, str], set[str]] = {}

    def add(unit: str, period: str, value: str) -> None:
        unit, period = unit.lower().strip(), period.lower().strip()
        if not unit or unit in _QTY_JUNK_UNITS:
            return
        if re.fullmatch(r"(19|20)\d{2}", value):   # calendar year, not a quantity
            return
        found.setdefault((unit, period), set()).add(value)

    for m in _DIM_RE.finditer(text):
        if m.group(1):
            if not re.fullmatch(r"(19|20)\d{2}", m.group(1)):
                found.setdefault(("percent", ""), set()).add(m.group(1))
            continue
        add(m.group(4) or "", m.group(5) or "", m.group(3))

    for m in _DIM_WORD_RE.finditer(text):
        add(m.group(3) or "", "", _WORD_NUMERALS[m.group(1).lower()])
    return found


def _is_commensurable_conflict(text_a: str, text_b: str) -> bool:
    """
    May these two quantitative spans contradict at all?

    True when they share a dimension AND disagree on its value. Callers must
    only consult this when BOTH spans carry a quantity; a non-quantitative span
    asserts its rule in prose and is none of this function's business.
    """
    qa, qb = _span_quantities(text_a), _span_quantities(text_b)
    shared = set(qa) & set(qb)
    if not shared:
        return False
    return any(qa[key] != qb[key] for key in shared)


def _contradiction_kind(text_a: str, text_b: str) -> Optional[str]:
    """
    Run the three contradiction prongs over one pair of spans.

    A) Keyword antonyms — cheap and precise, so gated on high lexical overlap.
    B) NLI — deliberately NOT gated on high lexical overlap (Finding 1): its
       purpose is paraphrastic contradictions, which by definition share little
       vocabulary. Only the NLI_SIM_FLOOR performance guard applies.
    C) Numeric, unit-aware — cheap/precise, gated on high lexical overlap.
    """
    # A contradiction needs two assertions. Boilerplate that states no rule
    # cannot be half of one, so it is rejected before the prongs — which also
    # spares those pairs the expensive NLI inference.
    if REQUIRE_ASSERTIVE_SPANS and not (
            _is_assertive_span(text_a) and _is_assertive_span(text_b)):
        return None
    if _same_assertion(text_a, text_b):
        return None
    sim = compute_chunk_similarity(text_a, text_b)
    high_sim = sim >= CONFLICT_SIM_THRESHOLD
    kind: Optional[str] = None
    if high_sim and _has_keyword_contradiction(text_a, text_b):
        kind = "keyword"
    elif sim >= NLI_SIM_FLOOR and _has_nli_contradiction(text_a, text_b):
        kind = "nli"
    elif high_sim and _has_numeric_contradiction(text_a, text_b):
        kind = "numeric"
    if kind is None:
        return None

    # Commensurability. When BOTH spans are quantitative the disagreement must
    # be about the same measured dimension; NLI cannot tell a rate from a
    # duration and scores "2 days per week" against "26 weeks of continuous
    # service" at 0.9994. A span that asserts its rule in prose is left alone.
    if DIMENSIONAL_VETO and _span_quantities(text_a) and _span_quantities(text_b):
        if not _is_commensurable_conflict(text_a, text_b):
            return None
    return kind


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

    # Answerhood pool (ANSWERHOOD_MARGIN gate): built once per query, not per
    # pair, from every query-relevant sentence across every individually
    # relevant chunk — the same candidate set the sentence-pair loop below
    # draws sents_a/sents_b from, so a sentence's margin is relative to
    # everything it could have been compared against for this query. Empty
    # when the gate is off (default) or the model is unavailable, in which
    # case the per-pair check below is skipped entirely (degrades open).
    answerhood_margins: dict[str, float] = {}
    if ANSWERHOOD_MARGIN > 0.0 and query.strip():
        pool: list[str] = []
        seen_pool: set[str] = set()
        for c in chunks:
            rel = c.get("relevance_score", c.get("score", 0.0))
            if rel < MIN_CONFLICT_RELEVANCE:
                continue
            for sent in _query_relevant_sentences(c.get("text", ""), content_terms):
                if sent not in seen_pool:
                    seen_pool.add(sent)
                    pool.append(sent)
        answerhood_margins = _answerhood_margins(query, pool)

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
                    ok = (anchored_a and anchored_b if ANCHOR_REQUIRE_BOTH
                          else anchored_a or anchored_b)
                    if not ok and ANCHOR_REQUIRE_BOTH and (anchored_a or anchored_b) \
                            and ANCHOR_ASYMMETRIC_QSPAN > 0.0 and query.strip():
                        # Half-anchored pair rescued on query-span similarity —
                        # see ANCHOR_ASYMMETRIC_QSPAN. Off by default.
                        ok = (_query_span_similarity(query, cand_a) >= ANCHOR_ASYMMETRIC_QSPAN
                              and _query_span_similarity(query, cand_b) >= ANCHOR_ASYMMETRIC_QSPAN)
                    if not ok:
                        continue

                    # Query-intent gate, now per sentence: a contradiction only
                    # justifies abstention when BOTH sentences are about what
                    # the user asked. Runs before the prongs so irrelevant
                    # pairs skip the expensive NLI inference.
                    if QUERY_SPAN_RELEVANCE > 0.0 and query.strip():
                        if (_query_span_similarity(query, cand_a) < QUERY_SPAN_RELEVANCE
                                or _query_span_similarity(query, cand_b) < QUERY_SPAN_RELEVANCE):
                            continue

                    # Answerhood gate: both sentences must score within
                    # ANSWERHOOD_MARGIN of this query's own top-1 answerhood
                    # score (see ANSWERHOOD_MARGIN docstring). Suppress-only —
                    # a rejected pair is skipped, not returned as an
                    # abstention; the loop tries the next candidate. Missing
                    # sentences (pool/model unavailable) default to margin 0.0
                    # so an empty answerhood_margins mapping is a true no-op.
                    if ANSWERHOOD_MARGIN > 0.0 and answerhood_margins:
                        if (answerhood_margins.get(cand_a, 0.0) > ANSWERHOOD_MARGIN
                                or answerhood_margins.get(cand_b, 0.0) > ANSWERHOOD_MARGIN):
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

    Three HARD requirements (all must hold):
      H1. Minimum chunk count : at least MIN_CHUNKS_FOR_SUFFICIENCY chunks.
      H3. Relevance floor     : at least one chunk has relevance_score > 0
                                (never synthesize from purely off-topic evidence).
      H5. Focus presence      : at least MIN_FOCUS_PRESENCE of the query's focus
                                terms appear in the evidence at all.

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

    # H5 — hard: the query's focus terms must be IN the evidence.
    #
    # H2 and H4 are both thresholds on a continuous quantity, and the two gap
    # queries that leaked were sitting just on the wrong side of one of them:
    # Corpus-2 Q017 cleared the average branch by 0.0031, and Corpus-1 Q051's
    # coverage rose 0.40 -> 0.60 across the sentence-boundary chunking fix —
    # crossing the 0.55 bar because more overlapping text was retrieved, with no
    # new information about relocation appearing anywhere. A gate that can be
    # moved by chunk geometry is measuring the wrong thing, so this precondition
    # asks a different question: not "how much of the query is covered?" but
    # "is what the query is ABOUT in here at all?".
    #
    # Placed BEFORE the H2/H4 disjunction on purpose. It is a veto, not a third
    # branch — evidence that does not mention the subject cannot become
    # sufficient by scoring well on average, which is exactly how Q051 passed.
    #
    # NOT a coverage threshold in disguise: coverage is a fraction over ALL
    # content words, this is a fraction over the rarest half only, and no value
    # of MIN_QUERY_COVERAGE separates these cases (Q051 leaks at coverage 0.60
    # while Corpus-1 Q070 is answerable at 0.3333). See MIN_FOCUS_PRESENCE for
    # why it is a fraction rather than the pure presence test and for the
    # alternatives that were measured and rejected.
    if MIN_FOCUS_PRESENCE > 0 and query.strip():
        focus = _sufficiency_focus_terms(query)
        if focus:
            evidence_text = " ".join(c.get("text", "") for c in chunks)
            present = sum(1 for t in focus if _mentions_focus(evidence_text, {t}))
            if present / len(focus) < MIN_FOCUS_PRESENCE:
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
