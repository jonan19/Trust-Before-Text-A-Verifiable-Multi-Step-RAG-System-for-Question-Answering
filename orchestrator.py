"""
orchestrator.py — V4 Orchestrator for the Trust Before Text RAG system.

Pipeline (deterministic, no agents):
    query → preprocess → classify → [decompose] → retrieve → validate(query) → decide → [synthesize]

V3 changes vs V2:
    - validate() now receives the query string (enables Stage 3 relevance filtering)
    - make_decision() reads abstention_reason for richer routing
    - Verbose output shows: relevant_count, abstention_reason, evidence ranks
    - Retry-exhausted conflict produces a conflict-specific abstain message

V4 changes:
    - Added preprocess_query(): strips punctuation artifacts, collapses whitespace,
      expands common contractions, so "What's the leave policy??" and
      "What is the leave policy?" both embed identically.
    - Expanded _COMPLEX_KEYWORDS to catch more multi-part query patterns
      (e.g. "explain", "list", "what are the differences").
    - Query preprocessing is applied before classify/decompose so all
      downstream stages receive the normalised form.
"""

from __future__ import annotations

import os
import re
from typing import Literal

from retrieval_interface import retrieve  # semantic similarity search
try:
    from qdrant_retrieval import retrieve_by_source as _retrieve_by_source
except ImportError:  # pragma: no cover
    _retrieve_by_source = None  # type: ignore[assignment]
from validation import validate
from synthesis import synthesize
from utils import build_context_block, format_abstention_response, print_separator

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MAX_RETRIES: int         = 1    # retry retrieval once on conflict before giving up
# Chunks fetched per (sub-)query. Raised from 10 to 30 so retrieval maximizes
# recall and hands validation (the sole relevance-filtering authority) a
# larger candidate set to filter from. Override via RAG_RETRIEVAL_TOP_K.
RETRIEVAL_TOP_K: int     = int(os.getenv("RAG_RETRIEVAL_TOP_K", "30"))
SOURCE_TARGET_TOP_K: int = 20   # chunks fetched when query targets a specific document
                                 # (summarize, explain one file) — need broad coverage
SOURCE_TARGET_MIN_CHUNKS: int = 4  # re-fetch if source-filtered result has fewer than this
MIN_SUBQUERY_WORDS: int  = 3    # minimum word count for a valid decomposed sub-query

# Keywords that signal a complex, multi-part query.
# NOTE: bare " and " intentionally excluded — it fires on almost every sentence
# ("What is the leave policy and how do I apply?") causing spurious decomposition.
_COMPLEX_KEYWORDS: list[str] = [
    # Explicit comparison operators — these genuinely signal 2+ topics
    "compare", "comparison", "difference", "differences",
    "versus", "vs", "contrast",
    # Multi-topic conjunctions — specific enough to imply two topics
    " also ", "both", "as well as",
    # Multi-item enumeration with a clear list intent
    "what are the differences", "compare and contrast",
]

# ---------------------------------------------------------------------------
# Decision type
# ---------------------------------------------------------------------------
Decision = Literal["proceed", "retry", "abstain"]

# ---------------------------------------------------------------------------
# Contraction expansion map (for preprocess_query)
# ---------------------------------------------------------------------------
_CONTRACTIONS: dict[str, str] = {
    "what's":  "what is",
    "where's": "where is",
    "who's":   "who is",
    "how's":   "how is",
    "when's":  "when is",
    "it's":    "it is",
    "i'm":     "i am",
    "i've":    "i have",
    "i'll":    "i will",
    "i'd":     "i would",
    "don't":   "do not",
    "doesn't": "does not",
    "can't":   "cannot",
    "won't":   "will not",
    "isn't":   "is not",
    "aren't":  "are not",
    "wasn't":  "was not",
    "weren't": "were not",
    "haven't": "have not",
    "hasn't":  "has not",
    "wouldn't":"would not",
    "shouldn't":"should not",
    "couldn't":"could not",
}


# ===========================================================================
# 0. Query Preprocessing  (NEW in V4)
# ===========================================================================

def preprocess_query(query: str) -> str:
    """
    Normalise a raw user query before classification and retrieval.

    Steps applied in order:
        1. Strip leading/trailing whitespace.
        2. Collapse repeated whitespace and punctuation runs (e.g. "??" → "?").
        3. Expand common English contractions ("what's" → "what is").
        4. Strip trailing punctuation that is not part of the query content.

    The original casing is preserved — the embedding model is case-insensitive
    by design but keeping case avoids accidental disambiguation.

    Examples
    --------
    "What's  the leave  policy??"  → "What is the leave policy?"
    "compare  leave  AND remote"   → "compare leave AND remote"
    """
    q = query.strip()

    # Collapse repeated whitespace
    q = re.sub(r"\s+", " ", q)

    # Collapse repeated punctuation (e.g. "??" or "!!" → single)
    q = re.sub(r"([?!.,;:])\1+", r"\1", q)

    # Expand contractions (case-insensitive)
    for contraction, expansion in _CONTRACTIONS.items():
        q = re.sub(rf"\b{re.escape(contraction)}\b", expansion, q, flags=re.IGNORECASE)

    # Strip trailing punctuation left over after expansion
    q = q.rstrip("?!.,;:").strip()
    # Re-add a single question mark if it was a question
    # (preserves intent without duplicate '??')

    return q


# ===========================================================================
# 1. Intent Classification
# ===========================================================================

def classify_query(query: str) -> Literal["simple", "complex"]:
    """
    Rule-based classifier — no LLM.
    Returns "complex" if a complexity-signal keyword is present, else "simple".

    Receives the pre-processed (normalised) query.
    """
    q_lower = query.lower()
    for keyword in _COMPLEX_KEYWORDS:
        if keyword in q_lower:
            return "complex"
    return "simple"


# ===========================================================================
# 2. Query Decomposition
# ===========================================================================

def decompose_query(query: str) -> list[str]:
    """
    Lightweight rule-based decomposition for complex queries.

    Splits on conjunctions / comparison markers into focused sub-queries.
    Falls back to the original query if no useful split point is found.

    V5 fix: sub-queries shorter than MIN_SUBQUERY_WORDS words are discarded.
    This prevents degenerate splits like "benefits" and "allowances" being sent
    as standalone retrieval queries with insufficient context.

    Receives the pre-processed (normalised) query.

    Example:
        "Compare leave policy and remote work policy"
        → ["leave policy", "remote work policy"]

        "What are the benefits and allowances available?"
        → ["What are the benefits and allowances available?"]  (no split — parts too short)
    """
    # Step 1: Strip leading command verbs AND the word "both" so that
    # "summarise both HR Policy A and HR Policy B"
    # → "HR Policy A and HR Policy B"
    # → ["HR Policy A", "HR Policy B"]
    normalized = re.sub(
        r"^(compare|comparison between|difference between|differences between"
        r"|summarize|summarise|describe|explain|list|enumerate|tell me about"
        r"|give me|what are|show me)\s+(both\s+|the\s+)?",
        "",
        query.strip(),
        flags=re.IGNORECASE,
    )
    # Step 2: Also strip a standalone leading "both" that wasn't caught above
    normalized = re.sub(r"^both\s+", "", normalized, flags=re.IGNORECASE)

    parts = re.split(r"\s+(?:and|vs\.?|versus|also|as well as)\s+", normalized, flags=re.IGNORECASE)
    # Discard fragments that are too short to be meaningful standalone queries
    cleaned = [p.strip() for p in parts if len(p.strip().split()) >= MIN_SUBQUERY_WORDS]
    return cleaned if len(cleaned) > 1 else [query]


# ===========================================================================
# 3. Retrieval
# ===========================================================================

def retrieve_for_queries(sub_queries: list[str], top_k: int = RETRIEVAL_TOP_K) -> list[dict]:
    """
    Call the retrieval module for each sub-query and merge results.
    Text-level deduplication happens here; semantic deduplication is done
    later in the validation pipeline (Stage 2).
    """
    all_chunks: list[dict] = []
    seen_texts: set[str] = set()

    for q in sub_queries:
        chunks = retrieve(q, top_k=top_k)
        for chunk in chunks:
            text = chunk.get("text", "").strip()
            if text not in seen_texts:
                seen_texts.add(text)
                all_chunks.append(chunk)

    return all_chunks


# ===========================================================================
# 3b. Source-Targeted Query Detection  (NEW in V5)
# ===========================================================================

def _extract_target_source(query: str, chunks: list[dict]) -> str | None:
    """
    Detect whether the user is querying a specific source document.

    If the query explicitly names a source file present in the retrieved
    chunks (e.g. "summarize HR_Policy_A.docx" or "what does HR_Policy_A say"),
    return that filename so the caller can restrict validation to that source
    only — preventing spurious cross-document conflict flags.

    Matching is case-insensitive and checks both the full filename and the
    stem (name without extension).

    Returns the matched source filename string, or None if no match is found.
    """
    q_lower = query.lower()
    seen: set[str] = set()
    for chunk in chunks:
        src = chunk.get("source", "")
        if not src or src in seen:
            continue
        seen.add(src)
        from pathlib import Path
        stem = Path(src).stem
        if src.lower() in q_lower or stem.lower() in q_lower:
            return src
    return None


# ===========================================================================
# 4. Decision Engine  (V3 — reads abstention_reason)
# ===========================================================================

def make_decision(validation_result: dict) -> Decision:
    """
    Deterministic decision from validation flags:

        abstention_reason == "conflict"      → retry (seek more evidence)
        abstention_reason == "insufficient"  → abstain
        abstention_reason is None            → proceed to synthesis
    """
    reason = validation_result.get("abstention_reason")
    if reason == "conflict":
        return "retry"
    if reason == "insufficient":
        return "abstain"
    return "proceed"


def _conflict_pair_chunks(validation_result: dict) -> list[dict] | None:
    """
    Return the specific pair of chunks that conflicted (Finding 2), so the
    abstention message names only the two disagreeing documents and shows the
    query-relevant sentence from each — not every retrieved source with a blind
    boilerplate excerpt. Falls back to all cleaned_chunks if no detail is present
    (e.g. an older validation result without conflict_detail).
    """
    detail = validation_result.get("conflict_detail")
    if detail and detail.get("chunks"):
        return detail["chunks"]
    return validation_result.get("cleaned_chunks")


# ===========================================================================
# 5. Main Orchestration Entry Point
# ===========================================================================

def run(query: str, verbose: bool = True) -> dict:
    """
    Run the full V4 RAG pipeline for a user query.

    Parameters
    ----------
    query   : The raw user question.
    verbose : If True, print step-by-step pipeline output.

    Returns
    -------
    {
        "query"           : str,
        "preprocessed"    : str,          # normalised query used internally
        "decision"        : "proceed" | "retry" | "abstain",
        "answer"          : str | None,
        "context"         : str | None,
        "validation"      : dict,         # full V3 validation result
        "sub_queries"     : list[str],
        "synthesis_result": dict | None,
    }
    """
    if verbose:
        print_separator("ORCHESTRATOR V4 START")
        print(f"  Query : {query}")

    # ── Step 0: Preprocess ──────────────────────────────────────────────────
    processed_query = preprocess_query(query)
    if verbose and processed_query != query:
        print(f"  Preprocessed: {processed_query}")

    # ── Step 1: Classify ────────────────────────────────────────────────────
    query_type = classify_query(processed_query)
    if verbose:
        print(f"  Type  : {query_type}")

    # ── Step 2: Decompose if complex ────────────────────────────────────────
    sub_queries = decompose_query(processed_query) if query_type == "complex" else [processed_query]
    if verbose and len(sub_queries) > 1:
        print(f"  Sub-queries: {sub_queries}")

    # ── Step 3: Retrieve → Validate loop (with one conflict retry) ──────────
    validation_result: dict = {}
    decision: Decision = "abstain"

    # Dynamic top_k: complex multi-part queries get extra coverage per sub-query.
    top_k = (
        RETRIEVAL_TOP_K + len(sub_queries)
        if query_type == "complex" and len(sub_queries) > 1
        else RETRIEVAL_TOP_K
    )

    # ── Pre-retrieval source detection ────────────────────────────────────
    # Check if the query names a specific document BEFORE doing retrieval.
    # For source-targeted queries (summarize/explain a named file), semantic
    # similarity is the wrong tool — "summarize Policy_A.docx" has almost no
    # embedding overlap with the document's actual content.
    # Using retrieve_by_source (metadata filter) as the PRIMARY path guarantees
    # we always get ALL chunks from the named document on the first try.
    early_target_source: str | None = None
    if _retrieve_by_source is not None:
        try:
            from qdrant_retrieval import _load_manifest, DEFAULT_QDRANT_DIR
            from pathlib import Path as _Path
            manifest = _load_manifest(_Path(DEFAULT_QDRANT_DIR))
            indexed_files = list(manifest.get("files", {}).keys())
            query_lower = processed_query.lower()
            for fname in indexed_files:
                stem_lower = _Path(fname).stem.lower()
                stem_spaced = stem_lower.replace("_", " ")
                if (fname.lower() in query_lower
                        or stem_lower in query_lower
                        or stem_spaced in query_lower):
                    early_target_source = fname
                    break
        except Exception:
            pass

    for attempt in range(MAX_RETRIES + 1):

        if early_target_source and _retrieve_by_source is not None:
            # ── Source-targeted: fetch ALL chunks from the named document ──
            direct_chunks = _retrieve_by_source(early_target_source)
            if direct_chunks:
                raw_chunks = direct_chunks
                chunks_to_validate = direct_chunks
                if verbose:
                    print(f"  [Source filter]  Fetching all chunks from '{early_target_source}' ({len(direct_chunks)} chunks)")
            else:
                # Named doc has no indexed chunks — fall back to semantic search
                raw_chunks = retrieve_for_queries(sub_queries, top_k=top_k)
                chunks_to_validate = raw_chunks
        else:
            # ── Normal path: semantic similarity retrieval ─────────────────
            raw_chunks = retrieve_for_queries(sub_queries, top_k=top_k)

            # Post-retrieval source filter: restrict to named doc if detected
            target_source = _extract_target_source(processed_query, raw_chunks)
            if target_source:
                filtered = [c for c in raw_chunks if c.get("source") == target_source]
                chunks_to_validate = filtered if filtered else raw_chunks
                if verbose and filtered:
                    print(f"  [Source filter]  Restricting to '{target_source}' ({len(filtered)} chunks)")
            else:
                chunks_to_validate = raw_chunks

        if verbose:
            print_separator(f"Retrieval — attempt {attempt + 1}")
            print(f"  Retrieved chunks : {len(raw_chunks)}")

        # ── Step 4: Validate (pass processed query for relevance filtering) ──
        validation_result = validate(chunks_to_validate, query=processed_query)

        if verbose:
            print_separator("Validation Pipeline")
            print(f"  [Stage 2] After dedup      : {len(raw_chunks)} -> see stage 3")
            print(f"  [Stage 3] Relevant chunks  : {validation_result['relevant_count']}")
            print(f"  [Stage 4] Conflict flag    : {validation_result['conflict_flag']}")
            print(f"  [Stage 5] Sufficiency flag : {validation_result['sufficiency_flag']}")
            print(f"  [Stage 7] Abstention reason: {validation_result['abstention_reason'] or 'none — proceed'}")
            print(f"  Confidence score           : {validation_result['confidence_score']:.4f}")
            if validation_result["cleaned_chunks"]:
                print("  Evidence ranks:")
                for c in validation_result["cleaned_chunks"]:
                    print(
                        f"    #{c['rank']}  score={c['score']:.4f}"
                        f"  rel={c['relevance_score']:.4f}"
                        f"  [{c['source']} / {c['section']}]"
                    )

        # ── Step 5: Decide ───────────────────────────────────────────────────
        decision = make_decision(validation_result)
        if verbose:
            print(f"  Decision : {decision.upper()}")

        if decision == "retry" and attempt < MAX_RETRIES:
            if verbose:
                print("  --> Conflict detected. Retrying with wider top_k ...")
            top_k = RETRIEVAL_TOP_K + 3
            continue
        break  # no conflict, or retries exhausted

    # If retries were exhausted on a persistent conflict, the loop exits with
    # decision == "retry" which is semantically wrong for the output. Normalise
    # it to "abstain" so the pipeline summary, return dict, and all downstream
    # code agree on the actual outcome.
    if decision == "retry":
        decision = "abstain"

    # ── Cross-document conflict override — REMOVED ────────────────────────────
    # A previous version discarded a detected conflict and answered anyway when
    # the query was classified "complex" (compare/versus/both), on the theory
    # that differences between documents are expected for comparison queries.
    #
    # Measured on the Meridian Grid 78-query set, that override was strictly
    # harmful: it fired on 4 queries (Q035–Q038) and hid a *correctly detected*
    # conflict in every one — each with the right document pair and an NLI score
    # of 0.965–0.9999. The other 4 "complex" queries (Q030, Q032–Q034) had no
    # conflict for it to suppress, so it protected nothing. Removing it takes
    # conflict recall from 12/16 to 16/16 with zero regressions.
    #
    # A user asking "compare X in A and B" still gets both values: the conflict
    # abstention names the two documents and quotes the clashing sentence from
    # each, which serves that intent better than silently answering.

    # -- Step 6: Route --------------------------------------------------------
    synthesis_result: dict | None = None
    answer: str | None = None
    context: str | None = None

    if decision == "proceed":
        context = build_context_block(validation_result["cleaned_chunks"])

        if verbose:
            print_separator("Evidence -> Synthesis")
            print(context)

        synthesis_result = synthesize(
            query            = processed_query,
            cleaned_chunks   = validation_result["cleaned_chunks"],
            sufficiency_flag = validation_result["sufficiency_flag"],
            conflict_flag    = validation_result["conflict_flag"],
        )
        answer = synthesis_result["answer"]

    elif decision == "abstain":
        reason = validation_result.get("abstention_reason", "insufficient")
        # For conflicts, show ONLY the two documents that actually disagree
        # (find_conflict's pair), not every retrieved source (Finding 2).
        chunks = _conflict_pair_chunks(validation_result) if reason == "conflict" else None
        synthesis_result = format_abstention_response(reason, conflicting_chunks=chunks)
        answer = synthesis_result["answer"]

    else:
        # Retry exhausted — persistent conflict
        chunks = _conflict_pair_chunks(validation_result)
        synthesis_result = format_abstention_response("conflict", conflicting_chunks=chunks)
        answer = synthesis_result["answer"]

    if verbose:
        print_separator("SYNTHESIS RESULT")
        print(f"  Status  : {synthesis_result['status'].upper()}")
        if synthesis_result.get("reason"):
            print(f"  Reason  : {synthesis_result['reason']}")
        print(f"  Answer  : {answer}")
        if synthesis_result.get("citations"):
            print("  Citations:")
            for c in synthesis_result["citations"]:
                score_str = f"  score={c['score']:.4f}" if "score" in c else ""
                print(f"    - [{c['source']}] {c['section']}{score_str}")
        print_separator()

    return {
        "query"           : query,
        "preprocessed"    : processed_query,
        "query_type"      : query_type,
        "decision"        : decision,
        "answer"          : answer,
        "context"         : context,
        "validation"      : validation_result,
        "sub_queries"     : sub_queries,
        "synthesis_result": synthesis_result,
        # Observability: raw candidate count before Stage 2 dedup, so the
        # frontend can show the full retrieve -> dedup -> filter funnel.
        "raw_chunk_count" : len(raw_chunks),
        "target_source"   : early_target_source,
    }
