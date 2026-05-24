"""
llm_interface.py — LLM Answer Generation interface.

Per README:
  * The LLM ONLY receives validated evidence (never raw retrieval output).
  * The LLM must not invent information — it answers strictly from context.
  * LLM usage happens ONLY during final answer generation.

This file provides:
  1. A `generate_answer()` function that wraps the LLM call.
  2. A clear prompt template that enforces evidence-only answering.
  3. A deterministic mock for development / testing without an API key.
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# Set the environment variable OPENAI_API_KEY (or equivalent) to use a
# real LLM backend.  Without it the module falls back to the mock.
_USE_MOCK: bool = not bool(os.getenv("OPENAI_API_KEY"))

# System prompt — enforces evidence-first, no-invention policy.
_SYSTEM_PROMPT = (
    "You are a precise, evidence-based question-answering assistant. "
    "You MUST answer ONLY using the provided context. "
    "If the context does not contain enough information to answer the question, "
    "say: 'I cannot answer based on the available evidence.' "
    "Do NOT invent, assume, or infer facts beyond what is explicitly stated."
)

# ---------------------------------------------------------------------------
# Real LLM backend (OpenAI — swap for any other provider as needed)
# ---------------------------------------------------------------------------

def _call_openai(query: str, context: str) -> str:
    """Send query + validated context to OpenAI and return the answer."""
    try:
        from openai import OpenAI  # type: ignore
    except ImportError:
        raise ImportError(
            "openai package not installed. Run: pip install openai"
        )

    client = OpenAI()
    user_message = (
        f"Context:\n{context}\n\n"
        f"Question: {query}\n\n"
        "Answer strictly from the context above."
    )
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ],
        temperature=0.0,   # deterministic output
        max_tokens=512,
    )
    return response.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
# Mock backend (no API key needed)
# ---------------------------------------------------------------------------

def _call_mock(query: str, context: str) -> str:
    """
    Deterministic mock that summarises the context without an LLM.
    Suitable for development and demonstration.
    """
    lines = [line.strip() for line in context.splitlines() if line.strip()]
    # Filter out source-header lines (start with "[Source:")
    evidence_lines = [l for l in lines if not l.startswith("[Source:")]
    if not evidence_lines:
        return "I cannot answer based on the available evidence."

    answer_parts = [f"• {line}" for line in evidence_lines]
    return (
        f"[MOCK LLM — no API key set]\n"
        f"Based on the verified evidence, here is what the documents state:\n"
        + "\n".join(answer_parts)
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_answer(query: str, context: str) -> str:
    """
    Generate a final answer from the validated context.

    Parameters
    ----------
    query   : The original user query (for the LLM prompt).
    context : Pre-formatted, validated evidence block from the orchestrator.

    Returns
    -------
    The LLM's answer string.
    """
    if not context.strip():
        return "I cannot answer based on the available evidence."

    if _USE_MOCK:
        return _call_mock(query, context)
    else:
        return _call_openai(query, context)


# ---------------------------------------------------------------------------
# Synthesis-specific LLM entry point
# ---------------------------------------------------------------------------
# Called ONLY by synthesis.py.
# Receives a fully-rendered constrained prompt — no free-form overrides.

_SYNTHESIS_SYSTEM_PROMPT = (
    "You are a controlled synthesis assistant operating inside a "
    "Retrieval-Augmented Generation pipeline. "
    "You synthesize answers STRICTLY from the evidence passages provided in the user message. "
    "You MUST NOT use prior knowledge, world knowledge, or any information "
    "not explicitly present in those passages. "
    "If the evidence is insufficient, say so explicitly."
)


def _call_synthesis_openai(prompt: str) -> str:
    """Send a pre-built synthesis prompt to the OpenAI API."""
    try:
        from openai import OpenAI  # type: ignore
    except ImportError:
        raise ImportError("openai package not installed. Run: pip install openai")

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": _SYNTHESIS_SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        temperature=0.0,   # deterministic — no creative latitude
        max_tokens=512,
    )
    return response.choices[0].message.content.strip()


def _call_synthesis_mock(prompt: str) -> str:
    """
    Deterministic synthesis mock — no API key required.
    Extracts evidence lines from the rendered prompt and returns them
    formatted as a bulleted synthesis, mimicking what an LLM would produce.
    """
    lines = prompt.splitlines()
    evidence_lines: list[str] = []
    in_evidence = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("Evidence:"):
            in_evidence = True
            continue
        if stripped.startswith("Question:"):
            in_evidence = False
            continue
        if in_evidence and stripped and not stripped.startswith("[") :
            # Collect indented text lines (the actual chunk content)
            evidence_lines.append(stripped)

    if not evidence_lines:
        return "The provided evidence does not contain enough information to answer this question."

    bullet_points = "\n".join(f"  * {line}" for line in evidence_lines)
    return (
        "[MOCK SYNTHESIS — no API key set]\n"
        "Based on the verified evidence:\n"
        f"{bullet_points}"
    )


def call_synthesis_llm(prompt: str) -> str:
    """
    Entry point for synthesis.py ONLY.

    Accepts a fully-rendered, constrained prompt produced by synthesis.py
    and routes it to the appropriate backend.

    Parameters
    ----------
    prompt : The complete synthesis prompt (evidence + query, pre-formatted).

    Returns
    -------
    The synthesized answer string.
    """
    if not prompt.strip():
        return "The provided evidence does not contain enough information to answer this question."

    if _USE_MOCK:
        return _call_synthesis_mock(prompt)
    else:
        return _call_synthesis_openai(prompt)

