"""
sufficiency_lab.py — Offline analysis of the Stage-5 sufficiency gate
(Limitation 3: gap-query leakage through the average-score branch).

Uses the Stage-3 dumps, so it needs no retrieval and no NLI. For every query on
both corpora it recomputes the gate's inputs (chunk count, average calibrated
score, query coverage) and reports how each candidate gate rule would classify
it, split by whether the query is a genuine gap (expected "insufficient") or a
genuine answerable query.

Candidate rules compared:
  current   H1 and H3 and (H2 or H4)                       -- shipped behaviour
  paired    same, but H2 only counts when >= 2 chunks      -- structural
  strict    H1 and H3 and H4                               -- coverage only

    python evaluation/sufficiency_lab.py
"""

from __future__ import annotations

import json
from pathlib import Path

import harness_bootstrap  # noqa: F401
import validation

STAGE3 = Path(__file__).resolve().parent / "stage3"


def gate_inputs(rec: dict) -> dict:
    chunks = rec["chunks"]
    scores = [c["score"] for c in chunks]
    avg = sum(scores) / len(scores) if scores else 0.0
    cov = validation._query_coverage(rec["processed"], chunks) if chunks else 1.0
    return {
        "n": len(chunks),
        "avg": round(avg, 4),
        "cov": cov,
        "h1": len(chunks) >= validation.MIN_CHUNKS_FOR_SUFFICIENCY,
        "h3": any(c["relevance_score"] > validation.MIN_RELEVANCE_SCORE for c in chunks),
        "h2": avg >= validation.MIN_AVG_SCORE_FOR_SUFFICIENCY,
        "h4": cov >= validation.MIN_QUERY_COVERAGE,
    }


RULES = {
    "current": lambda g: g["h1"] and g["h3"] and (g["h2"] or g["h4"]),
    # An "average" over a single chunk is not an average: it is that one chunk's
    # score wearing the authority of a set-level statistic. Require the
    # average-score branch to describe at least two chunks; a lone chunk must
    # earn sufficiency on coverage instead.
    "paired": lambda g: g["h1"] and g["h3"] and ((g["h2"] and g["n"] >= 2) or g["h4"]),
    "strict": lambda g: g["h1"] and g["h3"] and g["h4"],
}


def main() -> None:
    summary: dict[str, dict] = {}
    for corpus in ("1", "2"):
        records = json.loads((STAGE3 / f"corpus{corpus}.json").read_text(encoding="utf-8"))
        rows = []
        for rec in records:
            g = gate_inputs(rec)
            row = {"id": rec["id"], "expected": rec["expected"], **g}
            for name, fn in RULES.items():
                row[name] = fn(g)
            rows.append(row)

        print(f"\n{'=' * 72}\nCorpus {corpus}\n{'=' * 72}")
        for name in RULES:
            gaps = [r for r in rows if r["expected"] == "insufficient"]
            answers = [r for r in rows if r["expected"] == "answer"]
            leaks = [r["id"] for r in gaps if r[name]]
            lost = [r["id"] for r in answers if not r[name]]
            print(f"  {name:8}  gap leaks {len(leaks):>2}/{len(gaps)} {str(leaks):<44} "
                  f"answerable blocked {len(lost):>2}/{len(answers)} {lost}")
            summary.setdefault(name, {})[corpus] = {"leaks": leaks, "blocked": lost}

        print("\n  gap queries that pass the CURRENT gate (leak detail):")
        for r in rows:
            if r["expected"] == "insufficient" and r["current"]:
                print(f"    {r['id']}  n={r['n']} avg={r['avg']:.4f} cov={r['cov']:.2f} "
                      f"h2={r['h2']} h4={r['h4']}")
        print("\n  answerable queries carried by H2 ALONE (what 'paired' risks):")
        for r in rows:
            if r["expected"] == "answer" and r["h2"] and not r["h4"]:
                print(f"    {r['id']}  n={r['n']} avg={r['avg']:.4f} cov={r['cov']:.2f}")

    out = STAGE3.parent / "results" / "sufficiency_lab.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
