"""
orchestrator.py — V3 Orchestrator for the Trust Before Text RAG system.

Pipeline (deterministic, no agents):
    query → classify → [decompose] → retrieve → validate(query) → decide → [synthesize]

V3 changes vs V2:
    - validate() now receives the query string (enables Stage 3 relevance filtering)
    - make_decision() reads abstention_reason for richer routing
    - Verbose output shows: relevant_count, abstention_reason, evidence ranks
    - Retry-exhausted conflict produces a conflict-specific abstain message
"""

from __future__ import annotations

import re
from typing import Literal

from retrieval_interface import retrieve
from validation import validate
from synthesis import synthesize
from utils import build_context_block, format_abstention_response, print_separator

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MAX_RETRIES: int     = 1    # retry retrieval once on conflict before giving up
RETRIEVAL_TOP_K: int = 5    # chunks fetched per (sub-)query

# Keywords that signal a complex, multi-part query
_COMPLEX_KEYWORDS: list[str] = [
    "compare", "comparison", "difference", "differences",
    "versus", "vs", " and ", " also ", "both",
]

# ---------------------------------------------------------------------------
# Decision type
# ---------------------------------------------------------------------------
Decision = Literal["proceed", "retry", "abstain"]


# ===========================================================================
# 1. Intent Classification
# ===========================================================================

def classify_query(query: str) -> Literal["simple", "complex"]:
    """
    Rule-based classifier — no LLM.
    Returns "complex" if a complexity-signal keyword is present, else "simple".
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

    Example:
        "Compare leave policy and remote work policy"
        → ["leave policy", "remote work policy"]
    """
    normalized = re.sub(
        r"^(compare|comparison between|difference between|differences between)\s+",
        "",
        query.strip(),
        flags=re.IGNORECASE,
    )
    parts = re.split(r"\s+(?:and|vs\.?|versus|also)\s+", normalized, flags=re.IGNORECASE)
    cleaned = [p.strip() for p in parts if p.strip()]
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


# ===========================================================================
# 5. Main Orchestration Entry Point
# ===========================================================================

def run(query: str, verbose: bool = True) -> dict:
    """
    Run the full V3 RAG pipeline for a user query.

    Parameters
    ----------
    query   : The raw user question.
    verbose : If True, print step-by-step pipeline output.

    Returns
    -------
    {
        "query"           : str,
        "decision"        : "proceed" | "retry" | "abstain",
        "answer"          : str | None,
        "context"         : str | None,
        "validation"      : dict,         # full V3 validation result
        "sub_queries"     : list[str],
        "synthesis_result": dict | None,
    }
    """
    if verbose:
        print_separator("ORCHESTRATOR V3 START")
        print(f"  Query : {query}")

    # ── Step 1: Classify ────────────────────────────────────────────────────
    query_type = classify_query(query)
    if verbose:
        print(f"  Type  : {query_type}")

    # ── Step 2: Decompose if complex ────────────────────────────────────────
    sub_queries = decompose_query(query) if query_type == "complex" else [query]
    if verbose and len(sub_queries) > 1:
        print(f"  Sub-queries: {sub_queries}")

    # ── Step 3: Retrieve → Validate loop (with one conflict retry) ──────────
    validation_result: dict = {}
    decision: Decision = "abstain"
    top_k = RETRIEVAL_TOP_K

    for attempt in range(MAX_RETRIES + 1):
        raw_chunks = retrieve_for_queries(sub_queries, top_k=top_k)

        if verbose:
            print_separator(f"Retrieval — attempt {attempt + 1}")
            print(f"  Retrieved chunks : {len(raw_chunks)}")

        # ── Step 4: Validate (pass query for relevance filtering) ──────────
        validation_result = validate(raw_chunks, query=query)

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
            query            = query,
            cleaned_chunks   = validation_result["cleaned_chunks"],
            sufficiency_flag = validation_result["sufficiency_flag"],
            conflict_flag    = validation_result["conflict_flag"],
        )
        answer = synthesis_result["answer"]

    elif decision == "abstain":
        reason = validation_result.get("abstention_reason", "insufficient")
        synthesis_result = format_abstention_response(reason)
        answer = synthesis_result["answer"]

    else:
        # Retry exhausted — persistent conflict
        synthesis_result = format_abstention_response("conflict")
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
        "decision"        : decision,
        "answer"          : answer,
        "context"         : context,
        "validation"      : validation_result,
        "sub_queries"     : sub_queries,
        "synthesis_result": synthesis_result,
    }
