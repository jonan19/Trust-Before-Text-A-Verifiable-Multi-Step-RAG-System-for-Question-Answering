"""
coverage_leak_diag.py — Why do Q053 and Q017 pass Stage 5 on Corpus 2?
(Limitations 2/3 residual.)

The average-score branch leaks were fixed structurally by
MIN_CHUNKS_FOR_AVG_SUFFICIENCY. Q053 was recorded as passing on the COVERAGE
branch instead, which is a different mechanism and therefore needs a different
diagnosis. This dumps, for each query of interest, exactly which branch
returned True and the numbers behind it:

  chunk count, avg score (and whether the average branch even applies),
  coverage score, and — the part the aggregate score hides — WHICH query terms
  were counted as covered, and by what text.

`_query_coverage` scores a term as covered with a raw substring test against
the concatenated evidence, so this also reports, per covered term, whether it
matched a standalone word or only the inside of a longer one. A term covered
only as a substring is a term the evidence does not actually discuss.

Comparison cases (queries that correctly abstain on the coverage branch) are
printed alongside, so the difference is visible rather than asserted.

    python evaluation/coverage_leak_diag.py --corpus 2
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import harness_bootstrap  # noqa: F401
import harness
import validation

HERE = Path(__file__).resolve().parent


def term_report(query: str, chunks: list[dict]) -> list[dict]:
    """Per-term coverage detail for the terms _query_coverage actually uses."""
    raw_tokens = {w.lower().strip(".,;:?!'\"()") for w in query.split()}
    tokens = {t for t in raw_tokens
              if not any(t.endswith(e) for e in validation._FILE_EXTENSIONS)}
    content_terms = {t for t in (tokens - validation._COVERAGE_STOPWORDS) if t}
    evidence_text = " ".join(c.get("text", "").lower() for c in chunks)

    out = []
    for t in sorted(content_terms):
        substr = t in evidence_text
        whole = bool(re.search(rf"\b{re.escape(t)}\b", evidence_text))
        out.append({"term": t, "substring": substr, "whole_word": whole,
                    "substring_only": substr and not whole})
    return out


def diagnose(orchestrator, q: dict) -> dict:
    res = orchestrator.run(q["query"], verbose=False)
    val = res.get("validation") or {}
    chunks = val.get("cleaned_chunks") or []
    scores = [c.get("score", 0.0) for c in chunks]
    avg = sum(scores) / len(scores) if scores else 0.0
    cov = val.get("query_coverage_score")
    avg_applies = len(chunks) >= validation.MIN_CHUNKS_FOR_AVG_SUFFICIENCY
    avg_branch = avg_applies and avg >= validation.MIN_AVG_SCORE_FOR_SUFFICIENCY
    cov_branch = (cov is not None
                  and cov >= validation.MIN_QUERY_COVERAGE)
    terms = term_report(q["query"], chunks)
    return {
        "id": q["id"], "query": q["query"],
        "expected": q["expected_decision"],
        "observed": harness.decision_of(res),
        "sufficiency_flag": val.get("sufficiency_flag"),
        "n_chunks": len(chunks),
        "avg_score": round(avg, 4),
        "avg_applies": avg_applies,
        "avg_branch_passes": bool(avg_branch),
        "coverage": cov,
        "coverage_branch_passes": bool(cov_branch),
        "chunk_scores": [round(s, 4) for s in scores],
        "terms": terms,
        "n_terms": len(terms),
        "n_covered": sum(t["substring"] for t in terms),
        "n_substring_only": sum(t["substring_only"] for t in terms),
        "chunk_sources": [c.get("source") for c in chunks],
    }


def show(d: dict) -> None:
    verdict = "LEAK" if (d["expected"] == "insufficient"
                         and d["observed"] == "answer") else "ok"
    print(f"\n=== {d['id']}  [{verdict}] exp={d['expected']} got={d['observed']} ===")
    print(f"  {d['query']}")
    print(f"  chunks={d['n_chunks']} scores={d['chunk_scores']}")
    print(f"  avg={d['avg_score']} applies={d['avg_applies']} "
          f"-> avg branch {'PASS' if d['avg_branch_passes'] else 'fail'} "
          f"(bar {validation.MIN_AVG_SCORE_FOR_SUFFICIENCY})")
    print(f"  coverage={d['coverage']} "
          f"-> coverage branch {'PASS' if d['coverage_branch_passes'] else 'fail'} "
          f"(bar {validation.MIN_QUERY_COVERAGE})")
    print(f"  terms {d['n_covered']}/{d['n_terms']} covered, "
          f"{d['n_substring_only']} of them SUBSTRING-ONLY")
    for t in d["terms"]:
        mark = ("substring-only!" if t["substring_only"]
                else "whole" if t["whole_word"] else "absent")
        print(f"     {t['term']:<18} {mark}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="2")
    ap.add_argument("--ids", default="Q053,Q017")
    ap.add_argument("--compare", default="",
                    help="comma-separated ids that correctly abstain, for contrast")
    args = ap.parse_args()

    orchestrator = harness.setup(args.corpus)
    queries = {q["id"]: q for q in harness.load_queries(args.corpus)}

    targets = [i.strip() for i in args.ids.split(",") if i.strip()]
    compare = [i.strip() for i in args.compare.split(",") if i.strip()]

    # If no explicit comparison set, use every gap query that correctly
    # abstains — the coverage branch's behaviour on those is the control.
    if not compare:
        compare = [q["id"] for q in queries.values()
                   if q["expected_decision"] == "insufficient"
                   and q["id"] not in targets]

    out = []
    print("#" * 70)
    print("LEAKING QUERIES")
    print("#" * 70)
    for i in targets:
        d = diagnose(orchestrator, queries[i])
        out.append(d)
        show(d)

    print("\n" + "#" * 70)
    print("CORRECTLY ABSTAINING GAP QUERIES (control)")
    print("#" * 70)
    ctrl = []
    for i in compare:
        d = diagnose(orchestrator, queries[i])
        ctrl.append(d)
        out.append(d)
    for d in ctrl:
        show(d)

    # Aggregate contrast: is substring-only coverage what distinguishes them?
    print("\n" + "=" * 70)
    print("CONTRAST")
    leaks = [d for d in out if d["expected"] == "insufficient"
             and d["observed"] == "answer"]
    absts = [d for d in out if d["expected"] == "insufficient"
             and d["observed"] != "answer"]
    for name, grp in (("leaking", leaks), ("abstaining", absts)):
        if not grp:
            continue
        cov = [d["coverage"] for d in grp if d["coverage"] is not None]
        sub = [d["n_substring_only"] for d in grp]
        print(f"  {name:11} n={len(grp)} "
              f"coverage median={sorted(cov)[len(cov)//2] if cov else None} "
              f"substring-only terms: {sub}")

    path = HERE / "results" / f"coverage_leak_diag_corpus{args.corpus}.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWrote {path}")


if __name__ == "__main__":
    main()
