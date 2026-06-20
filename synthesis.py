"""
synthesis.py — V3 Synthesis Module for the Trust Before Text RAG system.

Position in pipeline:
    … → Validation Pipeline → Decision Engine → Synthesis Module → Final Answer

Constraints (unchanged from V2, tightened in V3):
    RECEIVES ONLY  : validated, ranked evidence chunks + flags
    NEVER ACCESSES : raw retrieval output, vector DB, external tools, memory
    DOES NOT       : retrieve, validate, make routing decisions

V3 changes vs V2:
    - Uses `rank` field from structured chunks (Stage 6 output) to order evidence block
    - Citations now include `score` field for traceability
    - Abstain guard also checks for empty cleaned_chunks
    - Evidence block uses rank label instead of sequential index

V4 changes:
    - Score removed from the LLM evidence block (it is an internal system metric
      that the LLM doesn't need and that may bias or confuse generation).
      Scores are still preserved in citations for the user-facing output.

Output schema:
    {
        "status"    : "success" | "abstain",
        "answer"    : str,
        "citations" : [{"source": str, "section": str, "score": float}]
    }
"""

from __future__ import annotations

from llm_interface import call_synthesis_llm

# ---------------------------------------------------------------------------
# Abstain messages (kept here for synthesis-specific phrasing)
# ---------------------------------------------------------------------------
_ABSTAIN_CONFLICT     = "Cannot synthesize an answer: the evidence contains contradictory information."
_ABSTAIN_INSUFFICIENT = "Cannot synthesize an answer: the available evidence is insufficient."

# ---------------------------------------------------------------------------
# Constrained synthesis prompt
# ---------------------------------------------------------------------------
_SYNTHESIS_PROMPT_TEMPLATE = """\
You are a synthesis assistant. Your ONLY task is to write a clear, accurate answer \
using the evidence passages provided below.

Rules you MUST follow:
- Answer ONLY using information explicitly stated in the evidence passages.
- Do NOT use prior knowledge or introduce any external facts.
- Do NOT infer, speculate, or fill gaps beyond what the evidence says.
- If the evidence is insufficient to answer the question, say exactly:
  "The provided evidence does not contain enough information to answer this question."
- Write in clear, professional prose. Keep the answer concise.
- Where relevant, cite the evidence rank (e.g. "[Evidence #1]") inline.

Evidence:
{evidence_block}

Question: {query}

Answer:"""


# ===========================================================================
# Internal helpers
# ===========================================================================

def _build_evidence_block(chunks: list[dict]) -> str:
    """
    Format structured chunks (Stage 6 output) into a numbered evidence block
    for the LLM prompt.

    Note: Score is intentionally omitted from each evidence header. Scores
    are internal retrieval metrics that the LLM does not need and that may
    anchor or confuse the synthesis. They are retained in citations for the
    user-facing output only.

    Uses the `rank` field from evidence structuring so the block order always
    matches the ranked order, even if chunks arrive in a different sequence.

    Example:
        [Evidence #1] Source: policy.pdf | Section: Leave Policy
            Employees are entitled to 20 days of annual leave per calendar year.

        [Evidence #2] Source: handbook.pdf | Section: Remote Work
            Employees may work remotely up to 2 days per week with manager approval.
    """
    # Sort by rank ascending (rank 1 = best)
    sorted_chunks = sorted(chunks, key=lambda c: c.get("rank", 999))
    lines: list[str] = []
    for chunk in sorted_chunks:
        rank    = chunk.get("rank", "?")
        source  = chunk.get("source", "unknown")
        section = chunk.get("section", "unknown")
        text    = chunk.get("text", "").strip()
        # Score deliberately excluded from the LLM prompt
        lines.append(
            f"[Evidence #{rank}] Source: {source} | Section: {section}\n"
            f"    {text}"
        )
    return "\n\n".join(lines)


def _build_citations(chunks: list[dict]) -> list[dict]:
    """
    Extract deduplicated source citations from validated chunks.

    V3: includes `score` for traceability. Uses the best score for any
    source+section combination that appears multiple times.
    """
    best: dict[tuple[str, str], float] = {}
    for chunk in chunks:
        key   = (chunk.get("source", ""), chunk.get("section", ""))
        score = chunk.get("score", 0.0)
        best[key] = max(best.get(key, 0.0), score)

    # Return in rank order (rank field present from Stage 6)
    seen: set[tuple[str, str]] = set()
    citations: list[dict] = []
    for chunk in sorted(chunks, key=lambda c: c.get("rank", 999)):
        key = (chunk.get("source", ""), chunk.get("section", ""))
        if key not in seen:
            seen.add(key)
            citations.append({
                "source" : key[0],
                "section": key[1],
                "score"  : round(best[key], 4),
            })
    return citations


def _build_prompt(query: str, chunks: list[dict]) -> str:
    """Render the constrained synthesis prompt."""
    return _SYNTHESIS_PROMPT_TEMPLATE.format(
        evidence_block=_build_evidence_block(chunks),
        query=query,
    )


# ===========================================================================
# Public entry point
# ===========================================================================

def synthesize(
    query: str,
    cleaned_chunks: list[dict],
    sufficiency_flag: bool,
    conflict_flag: bool,
) -> dict:
    """
    Generate a structured, citation-backed answer from validated evidence.

    Called ONLY after the Decision Engine has confirmed pipeline should proceed.

    Parameters
    ----------
    query            : The original user query.
    cleaned_chunks   : Stage-6 structured evidence (with rank, score, etc.).
    sufficiency_flag : True if evidence is sufficient (from Stage 5).
    conflict_flag    : True if contradictions were detected (from Stage 4).

    Returns
    -------
    {
        "status"    : "success" | "abstain",
        "answer"    : str,
        "citations" : [{"source": str, "section": str, "score": float}]
    }
    """
    # ── Guard: abstain immediately on bad flags or empty evidence ────────────
    if conflict_flag:
        return {"status": "abstain", "answer": _ABSTAIN_CONFLICT, "citations": []}

    if not sufficiency_flag or not cleaned_chunks:
        return {"status": "abstain", "answer": _ABSTAIN_INSUFFICIENT, "citations": []}

    # ── Build constrained prompt ─────────────────────────────────────────────
    prompt = _build_prompt(query, cleaned_chunks)

    # ── Call LLM (only via llm_interface) ───────────────────────────────────
    raw_answer = call_synthesis_llm(prompt)

    # ── Attach ranked citations ──────────────────────────────────────────────
    citations = _build_citations(cleaned_chunks)

    return {
        "status"   : "success",
        "answer"   : raw_answer.strip(),
        "citations": citations,
    }
