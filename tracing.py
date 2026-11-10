"""
tracing.py — optional execution tracing for the Trust Before Text pipeline.

**Off by default. Tracing watches the pipeline; it never votes.**

Why this exists
---------------
The decision layer is deterministic and LLM-free, which makes it explainable in
principle but not in practice: until now the only instrumentation in the repo
was two ``logging.getLogger`` calls, so every investigation of a wrong decision
meant writing a new single-use script (``evaluation/dump_stage3.py``,
``focus.py``, ``coverage_leak_diag.py``, ``overabstention_diag.py``, and about
thirty more). This module records, per query, the quantities the decision
actually turns on: the per-stage survivor counts, the focus terms, the NLI
contradiction scores, the answerhood margins, and which gate vetoed what. Those
are precisely the quantities behind failure patterns 1 and 3 in ``CLAUDE.md``.

Contract
--------
1. **No-op unless ``RAG_TRACE=1``.** Every public function returns immediately.
2. **Never changes a decision.** Nothing here mutates pipeline data: values are
   copied, coerced and rounded on the way out. Every public function swallows
   its own exceptions, so a bug in tracing can never raise into the pipeline
   and alter control flow.
3. **Verified, not asserted.** ``python evaluation/rerun_suite.py
   --trace-compare --corpora 1,2`` runs the decision eval with and without the
   flag and requires identical decisions *and* identical cited conflict pairs
   on all 78 queries of both corpora. A failure there means the instrumentation
   is wrong, not the system.

Output
------
One JSON object per query, appended as a line to
``evaluation/results/traces/trace_<date>.jsonl`` (override the directory with
``RAG_TRACE_DIR``). Evidence text is omitted unless ``RAG_TRACE_TEXT=1``, so a
trace file holds the decision's shape without copying the corpus into it.

Record shape::

    {"ts", "query", "fields": {...}, "counters": {...},
     "stages": [{"name", "ms", <fields>, "counters": {...}}, ...]}

Usage
-----
``begin_query`` / ``end_query`` bracket one pipeline run. ``note`` and ``bump``
write into a pending bucket that the next ``stage`` call flushes into that
stage's record, so a call site needs one line and no re-indentation::

    tracing.begin_query(query)
    ...
    tracing.note(focus_terms=sorted(focus))     # inside find_conflict
    tracing.bump("veto_rank_cutoff")            # inside the pair loop
    tracing.stage("stage4_conflict", n_in=len(stage3_wide))
    ...
    tracing.end_query(decision=decision)
"""

from __future__ import annotations

import contextvars
import datetime
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Optional

__all__ = ["enabled", "begin_query", "end_query", "stage", "note", "bump",
           "append", "set_label", "current", "sink_path"]

_ROOT = Path(__file__).resolve().parent

# Read once at import. A trace flag that can change mid-run would make two
# halves of one eval incomparable, which is the opposite of the point.
_ON: bool = os.getenv("RAG_TRACE", "").strip() not in ("", "0", "false", "False")
_WITH_TEXT: bool = os.getenv("RAG_TRACE_TEXT", "").strip() not in ("", "0", "false", "False")
_MAX_LABEL: int = 64          # strings this short are labels, always kept
_MAX_TEXT: int = 300          # characters kept per text value when _WITH_TEXT
_MAX_LIST: int = 40           # items kept per list value

_CURRENT: contextvars.ContextVar[Optional[dict]] = contextvars.ContextVar(
    "rag_trace_current", default=None)
# Fields set before a run starts (the eval harness knows the query id; the
# pipeline does not). Consumed by the next begin_query, then cleared, so a
# label can never leak onto an unrelated query.
_LABEL: contextvars.ContextVar[dict] = contextvars.ContextVar(
    "rag_trace_label", default={})
_WRITE_LOCK = threading.Lock()


def enabled() -> bool:
    """True when RAG_TRACE was set at import time."""
    return _ON


def sink_path() -> Optional[Path]:
    """The JSONL file this process appends to, or None when tracing is off."""
    if not _ON:
        return None
    d = os.getenv("RAG_TRACE_DIR", "").strip()
    base = Path(d) if d else _ROOT / "evaluation" / "results" / "traces"
    return base / ("trace_%s.jsonl" % datetime.date.today().isoformat())


# ---------------------------------------------------------------------------
# Value coercion — everything written out is a copy, never a live object
# ---------------------------------------------------------------------------
def _safe(value: Any) -> Any:
    """Coerce one value into something JSON-serialisable and bounded in size.

    Text values are dropped entirely unless RAG_TRACE_TEXT=1: a trace is meant
    to show the shape of a decision, not to duplicate the corpus.
    """
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, str):
        # Short strings are labels, gate names, filenames and focus terms, and
        # are always kept: redacting them would hide the very thing a trace is
        # read for. Evidence spans and chunk text are long, and stay behind
        # RAG_TRACE_TEXT so a trace file never quietly duplicates the corpus.
        if len(value) <= _MAX_LABEL:
            return value
        if not _WITH_TEXT:
            return "<%d chars>" % len(value)
        return value if len(value) <= _MAX_TEXT else value[:_MAX_TEXT] + "..."
    if isinstance(value, (set, frozenset)):
        items = sorted(str(v) for v in value)
        return items[:_MAX_LIST] + (["..."] if len(items) > _MAX_LIST else [])
    if isinstance(value, (list, tuple)):
        items = [_safe(v) for v in value[:_MAX_LIST]]
        return items + (["..."] if len(value) > _MAX_LIST else [])
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in list(value.items())[:_MAX_LIST]}
    return str(value)


def _safe_fields(fields: dict) -> dict:
    return {str(k): _safe(v) for k, v in fields.items()}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def begin_query(query: str, **fields: Any) -> None:
    """Open a trace for one pipeline run.

    Any trace left open by an earlier run (an exception escaped before
    ``end_query``) is discarded here rather than merged, so a failed query can
    never contaminate the next one's record.
    """
    if not _ON:
        return
    try:
        _CURRENT.set({
            "ts": datetime.datetime.now().isoformat(timespec="milliseconds"),
            # The query is the user's own question, not retrieved corpus
            # content, and a trace without it is close to unreadable. Note for
            # production use: RAG_TRACE should stay off there anyway.
            "query": query,
            "fields": {**_LABEL.get({}), **_safe_fields(fields)},
            "counters": {},
            "stages": [],
            "_t0": time.perf_counter(),
            "_tlast": time.perf_counter(),
            "_pending_fields": {},
            "_pending_counters": {},
        })
        _LABEL.set({})
    except Exception:
        pass


def set_label(**fields: Any) -> None:
    """Fields to attach to the NEXT begin_query, then forgotten.

    The eval harness knows a query's id and gold label; the pipeline does not
    and should not. This is how a trace line is joined back to a result row
    without threading an id through every pipeline signature.
    """
    if not _ON:
        return
    try:
        _LABEL.set(_safe_fields(fields))
    except Exception:
        pass


def current() -> Optional[dict]:
    """The open trace record, or None. For debugging this module."""
    if not _ON:
        return None
    try:
        return _CURRENT.get()
    except Exception:
        return None


def note(**fields: Any) -> None:
    """Attach fields to the next stage record. No-op when tracing is off."""
    if not _ON:
        return
    try:
        rec = _CURRENT.get()
        if rec is not None:
            rec["_pending_fields"].update(_safe_fields(fields))
    except Exception:
        pass


def bump(counter: str, n: int = 1) -> None:
    """Increment a named counter on the next stage record.

    Used for the per-pair veto tallies inside the Stage 4 loop, where the
    interesting quantity is "how many pairs did each gate reject" rather than
    any individual pair.
    """
    if not _ON:
        return
    try:
        rec = _CURRENT.get()
        if rec is not None:
            c = rec["_pending_counters"]
            c[counter] = c.get(counter, 0) + n
    except Exception:
        pass


def append(key: str, value: Any) -> None:
    """Append one value to a list field on the next stage record.

    For quantities there are many of per query, where the set is the
    interesting thing: the NLI contradiction score of every pair that reached
    the model, for instance. Capped by _MAX_LIST on the way out.
    """
    if not _ON:
        return
    try:
        rec = _CURRENT.get()
        if rec is not None:
            rec["_pending_fields"].setdefault(key, []).append(_safe(value))
    except Exception:
        pass


def stage(name: str, **fields: Any) -> None:
    """Record one completed stage, flushing any pending notes and counters.

    ``ms`` is the time since the previous ``stage`` call (or since
    ``begin_query`` for the first), so per-stage cost comes for free without
    wrapping anything in a context manager.
    """
    if not _ON:
        return
    try:
        rec = _CURRENT.get()
        if rec is None:
            return
        now = time.perf_counter()
        entry: dict = {"name": name, "ms": round((now - rec["_tlast"]) * 1000, 2)}
        entry.update(_safe_fields(fields))
        entry.update(rec["_pending_fields"])
        if rec["_pending_counters"]:
            entry["counters"] = dict(rec["_pending_counters"])
        rec["stages"].append(entry)
        rec["_pending_fields"] = {}
        rec["_pending_counters"] = {}
        rec["_tlast"] = now
    except Exception:
        pass


def end_query(**fields: Any) -> None:
    """Close the trace and append it to the sink as one JSONL line.

    Pending notes that no ``stage`` call claimed are flushed onto the record so
    nothing recorded is silently dropped.
    """
    if not _ON:
        return
    try:
        rec = _CURRENT.get()
        if rec is None:
            return
        _CURRENT.set(None)
        rec["fields"].update(_safe_fields(fields))
        rec["fields"].update(rec.pop("_pending_fields", {}))
        rec["counters"].update(rec.pop("_pending_counters", {}))
        rec["total_ms"] = round((time.perf_counter() - rec["_t0"]) * 1000, 2)
        for k in ("_t0", "_tlast"):
            rec.pop(k, None)

        path = sink_path()
        if path is None:
            return
        line = json.dumps(rec, ensure_ascii=False, default=str)
        with _WRITE_LOCK:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
    except Exception:
        pass
