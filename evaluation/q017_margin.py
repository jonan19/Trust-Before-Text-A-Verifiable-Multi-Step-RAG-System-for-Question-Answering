"""
q017_margin.py — Is Q017's average-branch pass separable from legitimate
average-branch passes? (Limitation 3 residual.)

Q017 leaks with avg_score 0.6531 against a 0.65 bar: a margin of 0.0031, while
its coverage score (0.40) correctly says the evidence does not address the
question. So the OR in check_sufficiency is doing exactly what it was built to
do — let a strong average overrule weak coverage — and the question is whether
any principled rule separates this case from the legitimate queries that rely
on the same branch.

This dumps, for every query on a corpus, the two branch inputs and which branch
carried the sufficiency decision. The specific thing being tested: can a query
that passes ONLY on a thin average margin, while scoring very low coverage, be
rejected without costing answerable queries that also lean on the average?

No threshold is changed here; this only measures the population.

    python evaluation/q017_margin.py --corpus 2
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import harness_bootstrap  # noqa: F401
import harness
import validation

HERE = Path(__file__).resolve().parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="2")
    args = ap.parse_args()

    orchestrator = harness.setup(args.corpus)
    queries = harness.load_queries(args.corpus)

    rows = []
    for q in queries:
        res = orchestrator.run(q["query"], verbose=False)
        val = res.get("validation") or {}
        chunks = val.get("cleaned_chunks") or []
        scores = [c.get("score", 0.0) for c in chunks]
        avg = sum(scores) / len(scores) if scores else 0.0
        cov = val.get("query_coverage_score")
        applies = len(chunks) >= validation.MIN_CHUNKS_FOR_AVG_SUFFICIENCY
        avg_pass = applies and avg >= validation.MIN_AVG_SCORE_FOR_SUFFICIENCY
        cov_pass = cov is not None and cov >= validation.MIN_QUERY_COVERAGE
        rows.append({
            "id": q["id"], "expected": q["expected_decision"],
            "observed": harness.decision_of(res),
            "n_chunks": len(chunks),
            "avg": round(avg, 4), "coverage": cov,
            "avg_pass": bool(avg_pass), "cov_pass": bool(cov_pass),
            "avg_margin": round(avg - validation.MIN_AVG_SCORE_FOR_SUFFICIENCY, 4),
            "sufficiency_flag": val.get("sufficiency_flag"),
            "only_avg": bool(avg_pass and not cov_pass),
        })

    only_avg = [r for r in rows if r["only_avg"]]
    print(f"\nQueries passing sufficiency on the AVERAGE branch alone "
          f"(coverage fails): {len(only_avg)}")
    hdr = f"  {'id':6} {'exp':13} {'got':13} {'chunks':>6} {'avg':>7} {'margin':>7} {'cov':>6}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for r in sorted(only_avg, key=lambda r: r["avg_margin"]):
        print(f"  {r['id']:6} {r['expected']:13} {r['observed']:13} "
              f"{r['n_chunks']:>6} {r['avg']:>7} {r['avg_margin']:>7} "
              f"{r['coverage']:>6}")

    # The proposed discriminator: thin average margin AND very low coverage.
    print("\nIf the average branch additionally required coverage >= X "
          "(i.e. the average may not overrule coverage that is near zero):")
    for x in (0.20, 0.30, 0.40, 0.50):
        lost = [r for r in rows
                if r["expected"] == "answer" and r["observed"] == "answer"
                and r["only_avg"] and (r["coverage"] or 0.0) < x]
        saved = [r for r in rows
                 if r["expected"] == "insufficient" and r["observed"] == "answer"
                 and r["only_avg"] and (r["coverage"] or 0.0) < x]
        print(f"   coverage floor {x:.2f}: gap leaks closed {len(saved)} "
              f"{[r['id'] for r in saved]}, answerable lost {len(lost)} "
              f"{[r['id'] for r in lost]}")

    path = HERE / "results" / f"q017_margin_corpus{args.corpus}.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\nWrote {path}")


if __name__ == "__main__":
    main()
