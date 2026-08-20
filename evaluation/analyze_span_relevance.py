"""
analyze_span_relevance.py — Separation analysis for the Stage-4 query-intent
gate (Limitation 1: false conflicts from query-irrelevant pairs).

For every conflict the detector fired in a recorded baseline run, recompute the
query/span semantic similarity of BOTH spans it reported, and report the
distribution split by whether the query was a true conflict query or not.

A usable gate exists only if the true-conflict spans sit above the
false-conflict spans on min(sim(query, span_a), sim(query, span_b)).

    python evaluation/analyze_span_relevance.py
"""

from __future__ import annotations

import json
from pathlib import Path

import harness_bootstrap  # noqa: F401
import validation

RESULTS = Path(__file__).resolve().parent / "results"


def main() -> None:
    rows = []
    for corpus in ("1", "2"):
        data = json.loads((RESULTS / f"baseline_corpus{corpus}.json").read_text(encoding="utf-8"))
        for r in data["results"]:
            if r["observed"] != "conflict" or not r.get("conflict_spans"):
                continue
            sims = [validation._query_span_similarity(r["query"], s)
                    for s in r["conflict_spans"] if s]
            rows.append({
                "corpus": corpus,
                "id": r["id"],
                "true_conflict": r["expected"] == "conflict",
                "kind": r["conflict_kind"],
                "min_sim": round(min(sims), 4),
                "max_sim": round(max(sims), 4),
                "pair": r["conflict_pair"],
                "query": r["query"],
            })

    for corpus in ("1", "2"):
        sub = [r for r in rows if r["corpus"] == corpus]
        true_ = sorted(r["min_sim"] for r in sub if r["true_conflict"])
        false_ = sorted(r["min_sim"] for r in sub if not r["true_conflict"])
        print(f"\n=== Corpus {corpus} — min(query,span) similarity ===")
        print(f"  TRUE  conflicts (n={len(true_)}): min={true_[0]:.4f} "
              f"p10={true_[max(0, len(true_)//10)]:.4f} median={true_[len(true_)//2]:.4f}")
        print(f"  FALSE conflicts (n={len(false_)}): "
              f"median={false_[len(false_)//2]:.4f} max={false_[-1]:.4f}")
        print("  false-conflict detail:")
        for r in sorted((r for r in sub if not r["true_conflict"]), key=lambda r: -r["min_sim"]):
            print(f"    {r['id']}  min_sim={r['min_sim']:.4f}  kind={r['kind']:<8} {r['query'][:64]}")
        print("  lowest true conflicts:")
        for r in sorted((r for r in sub if r["true_conflict"]), key=lambda r: r["min_sim"])[:6]:
            print(f"    {r['id']}  min_sim={r['min_sim']:.4f}  kind={r['kind']:<8} {r['query'][:64]}")

    out = RESULTS / "span_relevance_analysis.json"
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
