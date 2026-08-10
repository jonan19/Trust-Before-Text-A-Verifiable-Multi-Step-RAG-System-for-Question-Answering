"""
our_decisions_corpus2.py — Regenerate the CURRENT (v6, FROZEN) system's
decisions for all 78 Corpus-2 (Ashcombe Falls University) queries, straight
from the live deterministic pipeline. Zero LLM tokens, zero code changes to
the frozen system.

Mirrors experiments/our_decisions.py exactly, with two differences needed to
point the (otherwise untouched) pipeline at the new corpus instead of editing
any frozen file:

  1. Monkeypatch retrieval_interface._qdrant_retrieve to a partial bound to
     qdrant_dir='qdrant_db_corpus2' (retrieval_interface.retrieve() does not
     forward qdrant_dir, and qdrant_retrieval.retrieve()'s default always
     points at Corpus 1's qdrant_db/). This changes WHERE chunks are fetched
     from, not any threshold, validation rule, or decision logic.
  2. Stub orchestrator.synthesize so no LLM/network call happens (identical
     to our_decisions.py — the decision is made before synthesis).

Usage:
    python experiments_corpus2/our_decisions_corpus2.py --smoke   # 3 queries
    python experiments_corpus2/our_decisions_corpus2.py --all     # all 78

Output: experiments_corpus2/our_decisions_corpus2.json
"""

from __future__ import annotations

import argparse
import functools
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import qdrant_retrieval          # noqa: E402
import retrieval_interface       # noqa: E402
import orchestrator              # noqa: E402

CORPUS2_QDRANT_DIR = "qdrant_db_corpus2"

# ---------------------------------------------------------------------------
# Point retrieval at the Corpus-2 Qdrant store (separate dir; Corpus 1's
# qdrant_db/ is never touched). This only changes the data source, not any
# retrieval/validation/decision logic in the frozen files.
# ---------------------------------------------------------------------------
retrieval_interface._qdrant_retrieve = functools.partial(
    qdrant_retrieval.retrieve, qdrant_dir=CORPUS2_QDRANT_DIR
)

# ---------------------------------------------------------------------------
# Stub synthesis so no LLM/network call happens (same as our_decisions.py).
# ---------------------------------------------------------------------------
orchestrator.synthesize = lambda **kw: {  # type: ignore[assignment]
    "answer": "(synthesis skipped for decision-only run)",
    "status": "ok",
    "reason": None,
    "citations": [],
}

DATA = ROOT / "data_corpus2"
OUT = ROOT / "experiments_corpus2" / "our_decisions_corpus2.json"


def decision_of(result: dict) -> str:
    dec = result.get("decision")
    reason = (result.get("validation") or {}).get("abstention_reason")
    if dec == "proceed":
        return "answer"
    if reason == "conflict":
        return "conflict"
    return "insufficient"


def conflict_pair(result: dict):
    detail = (result.get("validation") or {}).get("conflict_detail")
    if detail and detail.get("chunks"):
        srcs = [c.get("source") for c in detail["chunks"]]
        return sorted(set(s for s in srcs if s))[:2]
    return None


def run_queries(queries: list[dict]) -> list[dict]:
    records = []
    n = len(queries)
    for i, q in enumerate(queries, 1):
        res = orchestrator.run(q["query"], verbose=False)
        dec = decision_of(res)
        rec = {
            "id": q["id"],
            "category": q.get("category"),
            "query": q["query"],
            "expected": q["expected_decision"],
            "observed": dec,
            "conflict_pair": conflict_pair(res),
            "match": dec == q["expected_decision"],
        }
        records.append(rec)
        mark = "OK " if rec["match"] else "XX "
        print(f"[{i}/{n}] {mark}{q['id']} exp={rec['expected']:<12} got={dec}",
              flush=True)
    return records


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="3-query smoke test")
    ap.add_argument("--all", action="store_true", help="full 78-query run")
    args = ap.parse_args()
    if not args.smoke and not args.all:
        ap.error("specify --smoke or --all")

    queries = json.load(open(DATA / "queries.json", encoding="utf-8"))["queries"]

    if args.smoke:
        # 1 answer, 1 conflict, 1 insufficient — matches the run protocol's
        # "3 queries end-to-end" smoke-test rule.
        ids = {"Q001", "Q036", "Q016"}
        queries = [q for q in queries if q["id"] in ids]

    t0 = time.time()
    records = run_queries(queries)
    correct = sum(r["match"] for r in records)
    n = len(records)
    print(f"\nCorpus 2 — our system: {correct}/{n} = "
          f"{round(100 * correct / n, 1)}% ({time.time() - t0:.0f}s)")

    payload = {
        "meta": {
            "system": "Trust Before Text (current / v6, FROZEN)",
            "corpus": "Corpus 2 (Ashcombe Falls University)",
            "n_queries": n,
            "accuracy": correct,
            "accuracy_pct": round(100 * correct / n, 1) if n else None,
            "mode": "smoke" if args.smoke else "all",
        },
        "results": records,
    }
    json.dump(payload, open(OUT, "w", encoding="utf-8"), indent=2)
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
