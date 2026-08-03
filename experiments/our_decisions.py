"""
our_decisions.py — Regenerate the CURRENT (v6) frozen-system decisions for all
78 queries, straight from the live deterministic pipeline. Zero LLM tokens.

Why this exists
---------------
The saved data/phase6_fullrun_results*.json files are STALE:
  * phase6_fullrun_results.json     = v4 (67.9%)
  * phase6_fullrun_results_v5.json  = v5 (83.3%)
Neither is the current v6 system (92.3%). The baseline experiment needs the
real current decisions for the "ours" column, so we recompute them here by
running orchestrator.run() with synthesis stubbed out (the decision is made
BEFORE synthesis, so stubbing it changes nothing but the network cost).

Also performs a determinism spot-check (Pillar 1): re-run a subset twice and
confirm identical decisions — ours flips = 0 by construction.

Output: experiments/our_decisions.json
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import orchestrator  # noqa: E402

# Stub synthesis so no LLM/network call happens. The decision + validation are
# computed before synthesis in orchestrator.run(), so this does not affect them.
_ORIG_SYNTH = orchestrator.synthesize
orchestrator.synthesize = lambda **kw: {  # type: ignore[assignment]
    "answer": "(synthesis skipped for decision-only run)",
    "status": "ok",
    "reason": None,
    "citations": [],
}

DATA = ROOT / "data"
OUT = ROOT / "experiments" / "our_decisions.json"


def decision_of(result: dict) -> str:
    """Map an orchestrator result to answer / conflict / insufficient."""
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


def main():
    queries = json.load(open(DATA / "queries.json", encoding="utf-8"))["queries"]
    exp = {q["id"]: q["expected_decision"] for q in queries}

    records = []
    t0 = time.time()
    n = len(queries)
    for i, q in enumerate(queries, 1):
        res = orchestrator.run(q["query"], verbose=False)
        dec = decision_of(res)
        rec = {
            "id": q["id"],
            "query": q["query"],
            "expected": exp[q["id"]],
            "observed": dec,
            "conflict_pair": conflict_pair(res),
            "match": dec == exp[q["id"]],
        }
        records.append(rec)
        mark = "OK " if rec["match"] else "XX "
        print(f"[{i}/{n}] {mark}{q['id']} exp={rec['expected']:<12} "
              f"got={dec}", flush=True)

    correct = sum(r["match"] for r in records)
    print(f"\nOur system: {correct}/{n} = {round(100 * correct / n, 1)}% "
          f"({time.time() - t0:.0f}s)")

    # ── Determinism spot-check (Pillar 1): re-run a subset, compare ──────────
    subset = ["Q001", "Q010", "Q029", "Q035", "Q040", "Q049", "Q062", "Q072"]
    print("\nDeterminism spot-check (re-run subset twice):")
    flips = 0
    by_id = {r["id"]: r["observed"] for r in records}
    for qid in subset:
        q = next(x for x in queries if x["id"] == qid)
        d2 = decision_of(orchestrator.run(q["query"], verbose=False))
        same = d2 == by_id[qid]
        flips += 0 if same else 1
        print(f"  {qid}: run1={by_id[qid]:<12} run2={d2:<12} "
              f"{'identical' if same else 'FLIP!'}")
    print(f"Determinism: {len(subset) - flips}/{len(subset)} identical "
          f"({flips} flips) — ours is deterministic by construction.")

    payload = {
        "meta": {
            "system": "Trust Before Text (current / v6)",
            "n_queries": n,
            "accuracy": correct,
            "accuracy_pct": round(100 * correct / n, 1),
            "determinism_subset": subset,
            "determinism_flips": flips,
        },
        "results": records,
    }
    json.dump(payload, open(OUT, "w", encoding="utf-8"), indent=2)
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
