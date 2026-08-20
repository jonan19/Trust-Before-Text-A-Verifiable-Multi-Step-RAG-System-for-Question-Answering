"""
harness.py — Shared evaluation harness for the limitation-fix work.

Purpose
-------
Re-run the live deterministic pipeline's DECISIONS over either corpus, under an
arbitrary threshold configuration, cheaply enough to sweep. Zero LLM tokens.

Two ideas make sweeping affordable:

  1. Retrieval is deterministic and threshold-independent (all validation
     thresholds act *after* retrieval), so `retrieve(query, top_k)` results are
     cached to disk on first use and replayed thereafter. The cache key
     includes the corpus, so the two stores never mix.
  2. Everything else runs through the real `orchestrator.run()`, so no decision
     logic is reimplemented here — the retry loop, source-targeting and
     validation stages are exercised exactly as in production.

Corpus selection mirrors `experiments_corpus2/our_decisions_corpus2.py`: a
`functools.partial` monkeypatch of `retrieval_interface._qdrant_retrieve`,
leaving every frozen module untouched.
"""

from __future__ import annotations

import functools
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CACHE_DIR = Path(__file__).resolve().parent / "_retrieval_cache"

# Corpus 1 reads from a byte-identical copy of qdrant_db/ (same collection,
# same manifest, same sparse encoder). The live qdrant_db/ is held open by a
# long-running local process; Qdrant's embedded mode allows only one writer per
# storage folder, so evaluation runs use the copy. Retrieval results are
# unaffected: the copy is made from the same on-disk collection.
CORPORA = {
    "1": {"data": ROOT / "data", "qdrant": "qdrant_db_c1_copy"},
    "2": {"data": ROOT / "data_corpus2", "qdrant": "qdrant_db_c2_copy"},
}


def _cache_path(corpus: str, query: str, top_k: int) -> Path:
    key = hashlib.sha256(f"{corpus}||{top_k}||{query}".encode("utf-8")).hexdigest()[:32]
    return CACHE_DIR / corpus / f"{key}.json"


def setup(corpus: str, *, stub_synthesis: bool = True):
    """
    Point retrieval at `corpus`'s store, wrap it in a disk cache, and (by
    default) stub synthesis so no LLM/network call happens.

    Returns the imported `orchestrator` module.
    """
    import qdrant_retrieval
    import retrieval_interface
    import orchestrator

    qdir = CORPORA[corpus]["qdrant"]
    (CACHE_DIR / corpus).mkdir(parents=True, exist_ok=True)

    raw_retrieve = functools.partial(qdrant_retrieval.retrieve, qdrant_dir=qdir)

    def cached_retrieve(query: str, top_k: int = 5, **kw):
        path = _cache_path(corpus, query, top_k)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        chunks = raw_retrieve(query, top_k=top_k, **kw)
        path.write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
        return chunks

    retrieval_interface._qdrant_retrieve = cached_retrieve

    # Publish the store's provenance registry up front. In production this
    # happens inside qdrant_retrieval.retrieve(), which the disk cache above
    # skips on a hit, so the harness has to do it explicitly or Stage 0 would
    # silently see no registry and wave everything through.
    import validation
    validation.set_evidence_registry(qdrant_retrieval.load_chunk_registry(qdir))
    validation.set_corpus_stats(qdrant_retrieval.load_corpus_stats(qdir))

    if stub_synthesis:
        orchestrator.synthesize = lambda **kw: {  # type: ignore[assignment]
            "answer": "(synthesis skipped for decision-only run)",
            "status": "ok",
            "reason": None,
            "citations": [],
        }
    return orchestrator


def load_queries(corpus: str) -> list[dict]:
    path = CORPORA[corpus]["data"] / "queries.json"
    return json.loads(path.read_text(encoding="utf-8"))["queries"]


def decision_of(result: dict) -> str:
    """Map an orchestrator result to answer / conflict / insufficient."""
    if result.get("decision") == "proceed":
        return "answer"
    if (result.get("validation") or {}).get("abstention_reason") == "conflict":
        return "conflict"
    return "insufficient"


def conflict_pair(result: dict):
    detail = (result.get("validation") or {}).get("conflict_detail")
    if detail and detail.get("chunks"):
        srcs = [c.get("source") for c in detail["chunks"]]
        return sorted({s for s in srcs if s})[:2]
    return None


def run_queries(orchestrator, queries: list[dict], *, progress: bool = True) -> list[dict]:
    records: list[dict] = []
    n = len(queries)
    for i, q in enumerate(queries, 1):
        res = orchestrator.run(q["query"], verbose=False)
        val = res.get("validation") or {}
        detail = val.get("conflict_detail") or {}
        rec = {
            "id": q["id"],
            "category": q.get("category"),
            "query": q["query"],
            "expected": q["expected_decision"],
            "observed": decision_of(res),
            "conflict_pair": conflict_pair(res),
            "conflict_kind": detail.get("kind"),
            "conflict_spans": [c.get("text") for c in detail.get("chunks", [])],
            "sufficiency_flag": val.get("sufficiency_flag"),
            "coverage": val.get("query_coverage_score"),
            "relevant_count": val.get("relevant_count"),
            "avg_score": (
                round(sum(c["score"] for c in val.get("cleaned_chunks", []))
                      / len(val["cleaned_chunks"]), 4)
                if val.get("cleaned_chunks") else None
            ),
        }
        rec["match"] = rec["observed"] == rec["expected"]
        records.append(rec)
        if progress:
            mark = "OK " if rec["match"] else "XX "
            print(f"[{i}/{n}] {mark}{q['id']} exp={rec['expected']:<12} got={rec['observed']}",
                  flush=True)
    return records


def metrics(records: list[dict]) -> dict:
    n = len(records)
    correct = sum(r["match"] for r in records)

    true_conflict = [r for r in records if r["expected"] == "conflict"]
    flagged = [r for r in records if r["observed"] == "conflict"]
    tp = sum(1 for r in flagged if r["expected"] == "conflict")
    precision = tp / len(flagged) if flagged else 0.0
    recall = tp / len(true_conflict) if true_conflict else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    gaps = [r for r in records if r["expected"] == "insufficient"]
    unsafe_gap = [r for r in gaps if r["observed"] == "answer"]
    # "Unsafe" = answered when the safe outcome was any abstention.
    should_abstain = [r for r in records if r["expected"] in ("insufficient", "conflict")]
    unsafe_all = [r for r in should_abstain if r["observed"] == "answer"]

    return {
        "n": n,
        "accuracy": correct,
        "accuracy_pct": round(100 * correct / n, 1) if n else None,
        "conflict_tp": tp,
        "conflict_flagged": len(flagged),
        "conflict_true": len(true_conflict),
        "conflict_precision": round(precision, 4),
        "conflict_recall": round(recall, 4),
        "conflict_f1": round(f1, 4),
        "false_conflicts": [r["id"] for r in flagged if r["expected"] != "conflict"],
        "missed_conflicts": [r["id"] for r in true_conflict if r["observed"] != "conflict"],
        "gap_leaks": [r["id"] for r in unsafe_gap],
        "gap_leak_count": f"{len(unsafe_gap)}/{len(gaps)}",
        "unsafe_answers": f"{len(unsafe_all)}/{len(should_abstain)}",
    }


def config_snapshot() -> dict:
    """Record the threshold configuration a run was executed under."""
    import validation
    keys = [
        "MIN_CHUNK_SCORE_THRESHOLD", "MIN_AVG_SCORE_FOR_SUFFICIENCY",
        "MIN_QUERY_COVERAGE", "MIN_CHUNKS_FOR_SUFFICIENCY",
        "CONFLICT_SIM_THRESHOLD", "NLI_SIM_FLOOR", "NLI_CONFLICT_THRESHOLD",
        "MIN_CONFLICT_RELEVANCE", "QUERY_SPAN_RELEVANCE",
    ]
    snap = {k: getattr(validation, k) for k in keys if hasattr(validation, k)}
    snap["env_overrides"] = {k: v for k, v in os.environ.items() if k.startswith("RAG_")}
    return snap
