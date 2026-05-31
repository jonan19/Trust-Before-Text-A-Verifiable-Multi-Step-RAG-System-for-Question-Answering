"""
llm_interface.py — LLM Answer Generation interface.

Per README:
  * The LLM ONLY receives validated evidence (never raw retrieval output).
  * The LLM must not invent information — it answers strictly from context.
  * LLM usage happens ONLY during final answer generation.

Backend priority (first key found wins):
  1. Groq          — llama-3.3-70b-versatile  (set GROQ_API_KEY)
  2. OpenAI        — gpt-4o-mini              (set OPENAI_API_KEY)
  3. Google Gemini — gemini-1.5-flash         (set GEMINI_API_KEY)
  4. Mock          — deterministic, no key needed

Environment variables are loaded from the .env file in the project root
(via python-dotenv). Hard-coded env vars still take precedence.

V4 changes:
  - Added Groq backend (llama-3.3-70b-versatile) as the primary real LLM.
  - Added python-dotenv support so a .env file is auto-loaded.
  - Added exponential-backoff retry on all real API calls (max 3 attempts).
  - max_tokens raised to 1024 for richer answers.
"""

from __future__ import annotations

import os
import time

# ── Load .env file if present ────────────────────────────────────────────────
# python-dotenv loads key=value pairs from .env into os.environ.
# Does nothing if the file is missing or python-dotenv is not installed.
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except ImportError:
    pass   # dotenv optional — env vars can still be set via shell

# ---------------------------------------------------------------------------
# Backend detection  (priority: Groq → OpenAI → Gemini → mock)
# ---------------------------------------------------------------------------
_GROQ_KEY:   str = os.getenv("GROQ_API_KEY",   "")
_OPENAI_KEY: str = os.getenv("OPENAI_API_KEY", "")
_GEMINI_KEY: str = os.getenv("GEMINI_API_KEY", "")

_USE_GROQ:   bool = bool(_GROQ_KEY)
_USE_OPENAI: bool = bool(_OPENAI_KEY)  and not _USE_GROQ
_USE_GEMINI: bool = bool(_GEMINI_KEY)  and not _USE_GROQ and not _USE_OPENAI
_USE_MOCK:   bool = not _USE_GROQ and not _USE_OPENAI and not _USE_GEMINI

# Model names
_GROQ_MODEL:   str = "llama-3.3-70b-versatile"
_OPENAI_MODEL: str = "gpt-4o-mini"
_GEMINI_MODEL: str = "gemini-1.5-flash"

_MAX_TOKENS:  int   = 1024
_MAX_RETRIES: int   = 3
_RETRY_DELAY: float = 1.0   # seconds; doubles on each retry

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = (
    "You are a precise, evidence-based question-answering assistant. "
    "You MUST answer ONLY using the provided context. "
    "If the context does not contain enough information to answer the question, "
    "say: 'I cannot answer based on the available evidence.' "
    "Do NOT invent, assume, or infer facts beyond what is explicitly stated."
)

_SYNTHESIS_SYSTEM_PROMPT = (
    "You are a controlled synthesis assistant operating inside a "
    "Retrieval-Augmented Generation pipeline. "
    "You synthesize answers STRICTLY from the evidence passages provided in the user message. "
    "You MUST NOT use prior knowledge, world knowledge, or any information "
    "not explicitly present in those passages. "
    "If the evidence is insufficient, say so explicitly."
)


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------

def _with_retry(fn, *args, **kwargs) -> str:
    """Call *fn* with exponential backoff on transient errors."""
    delay = _RETRY_DELAY
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES - 1:
                time.sleep(delay)
                delay *= 2
    raise RuntimeError(
        f"LLM call failed after {_MAX_RETRIES} attempts: {last_exc}"
    ) from last_exc


# ===========================================================================
# Groq backend  (llama-3.3-70b-versatile)
# ===========================================================================

def _call_groq(query: str, context: str) -> str:
    """Send query + validated context to Groq (Llama 3.3 70B) and return the answer."""
    try:
        from groq import Groq  # type: ignore
    except ImportError:
        raise ImportError("groq package not installed. Run: pip install groq")

    def _request() -> str:
        client = Groq(api_key=_GROQ_KEY)
        user_message = (
            f"Context:\n{context}\n\n"
            f"Question: {query}\n\n"
            "Answer strictly from the context above."
        )
        response = client.chat.completions.create(
            model=_GROQ_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_message},
            ],
            temperature=0.0,
            max_tokens=_MAX_TOKENS,
        )
        return response.choices[0].message.content.strip()

    return _with_retry(_request)


def _call_synthesis_groq(prompt: str) -> str:
    """Send a pre-built synthesis prompt to Groq (Llama 3.3 70B)."""
    try:
        from groq import Groq  # type: ignore
    except ImportError:
        raise ImportError("groq package not installed. Run: pip install groq")

    def _request() -> str:
        client = Groq(api_key=_GROQ_KEY)
        response = client.chat.completions.create(
            model=_GROQ_MODEL,
            messages=[
                {"role": "system", "content": _SYNTHESIS_SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.0,
            max_tokens=_MAX_TOKENS,
        )
        return response.choices[0].message.content.strip()

    return _with_retry(_request)


# ===========================================================================
# OpenAI backend  (gpt-4o-mini)
# ===========================================================================

def _call_openai(query: str, context: str) -> str:
    """Send query + validated context to OpenAI and return the answer."""
    try:
        from openai import OpenAI  # type: ignore
    except ImportError:
        raise ImportError("openai package not installed. Run: pip install openai")

    def _request() -> str:
        client = OpenAI()
        user_message = (
            f"Context:\n{context}\n\n"
            f"Question: {query}\n\n"
            "Answer strictly from the context above."
        )
        response = client.chat.completions.create(
            model=_OPENAI_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_message},
            ],
            temperature=0.0,
            max_tokens=_MAX_TOKENS,
        )
        return response.choices[0].message.content.strip()

    return _with_retry(_request)


def _call_synthesis_openai(prompt: str) -> str:
    """Send a pre-built synthesis prompt to OpenAI."""
    try:
        from openai import OpenAI  # type: ignore
    except ImportError:
        raise ImportError("openai package not installed. Run: pip install openai")

    def _request() -> str:
        client = OpenAI()
        response = client.chat.completions.create(
            model=_OPENAI_MODEL,
            messages=[
                {"role": "system", "content": _SYNTHESIS_SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.0,
            max_tokens=_MAX_TOKENS,
        )
        return response.choices[0].message.content.strip()

    return _with_retry(_request)


# ===========================================================================
# Gemini backend  (gemini-1.5-flash)
# ===========================================================================

def _call_gemini(query: str, context: str) -> str:
    """Send query + validated context to Google Gemini and return the answer."""
    try:
        import google.generativeai as genai  # type: ignore
    except ImportError:
        raise ImportError(
            "google-generativeai not installed. Run: pip install google-generativeai"
        )

    def _request() -> str:
        genai.configure(api_key=_GEMINI_KEY)
        model = genai.GenerativeModel(
            model_name=_GEMINI_MODEL,
            system_instruction=_SYSTEM_PROMPT,
        )
        user_message = (
            f"Context:\n{context}\n\n"
            f"Question: {query}\n\n"
            "Answer strictly from the context above."
        )
        response = model.generate_content(
            user_message,
            generation_config=genai.types.GenerationConfig(
                temperature=0.0,
                max_output_tokens=_MAX_TOKENS,
            ),
        )
        return response.text.strip()

    return _with_retry(_request)


def _call_synthesis_gemini(prompt: str) -> str:
    """Send a pre-built synthesis prompt to Google Gemini."""
    try:
        import google.generativeai as genai  # type: ignore
    except ImportError:
        raise ImportError(
            "google-generativeai not installed. Run: pip install google-generativeai"
        )

    def _request() -> str:
        genai.configure(api_key=_GEMINI_KEY)
        model = genai.GenerativeModel(
            model_name=_GEMINI_MODEL,
            system_instruction=_SYNTHESIS_SYSTEM_PROMPT,
        )
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.0,
                max_output_tokens=_MAX_TOKENS,
            ),
        )
        return response.text.strip()

    return _with_retry(_request)


# ===========================================================================
# Mock backend  (no API key needed)
# ===========================================================================

def _call_mock(query: str, context: str) -> str:
    """
    Deterministic mock that summarises the context without an LLM.
    Suitable for development and demonstration.
    """
    lines = [line.strip() for line in context.splitlines() if line.strip()]
    evidence_lines = [l for l in lines if not l.startswith("[Source:")]
    if not evidence_lines:
        return "I cannot answer based on the available evidence."

    answer_parts = [f"• {line}" for line in evidence_lines]
    return (
        "[MOCK LLM — no API key set]\n"
        "Based on the verified evidence, here is what the documents state:\n"
        + "\n".join(answer_parts)
    )


def _call_synthesis_mock(prompt: str) -> str:
    """
    Deterministic synthesis mock — no API key required.
    Extracts evidence lines from the rendered prompt and returns them
    formatted as a bulleted synthesis.
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
        if in_evidence and stripped and not stripped.startswith("["):
            evidence_lines.append(stripped)

    if not evidence_lines:
        return "The provided evidence does not contain enough information to answer this question."

    bullet_points = "\n".join(f"  * {line}" for line in evidence_lines)
    return (
        "[MOCK SYNTHESIS — no API key set]\n"
        "Based on the verified evidence:\n"
        f"{bullet_points}"
    )


# ===========================================================================
# Active backend label (for startup display)
# ===========================================================================

def active_backend() -> str:
    """Return a human-readable label for the active LLM backend."""
    if _USE_GROQ:   return f"Groq ({_GROQ_MODEL})"
    if _USE_OPENAI: return f"OpenAI ({_OPENAI_MODEL})"
    if _USE_GEMINI: return f"Gemini ({_GEMINI_MODEL})"
    return "Mock (no API key — set GROQ_API_KEY in .env)"


# ===========================================================================
# Public entry points
# ===========================================================================

def generate_answer(query: str, context: str) -> str:
    """
    Generate a final answer from validated context.
    Backend priority: Groq → OpenAI → Gemini → mock.
    """
    if not context.strip():
        return "I cannot answer based on the available evidence."
    if _USE_GROQ:   return _call_groq(query, context)
    if _USE_OPENAI: return _call_openai(query, context)
    if _USE_GEMINI: return _call_gemini(query, context)
    return _call_mock(query, context)


def call_synthesis_llm(prompt: str) -> str:
    """
    Entry point for synthesis.py ONLY.
    Accepts a fully-rendered constrained prompt and routes to the active backend.
    Backend priority: Groq → OpenAI → Gemini → mock.
    """
    if not prompt.strip():
        return "The provided evidence does not contain enough information to answer this question."
    if _USE_GROQ:   return _call_synthesis_groq(prompt)
    if _USE_OPENAI: return _call_synthesis_openai(prompt)
    if _USE_GEMINI: return _call_synthesis_gemini(prompt)
    return _call_synthesis_mock(prompt)
