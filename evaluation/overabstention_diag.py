"""
overabstention_diag.py — Why do Q006/Q073 (Corpus 1) and Q064 (Corpus 2)
abstain on questions their corpus can answer?

These three are the cost of the L3 chunk-count gate: each is a single-chunk
evidence set that used to pass on the average branch alone, and now must earn
sufficiency on coverage instead. That is the intended trade (over-abstention is
the safe direction), but "intended" is not the same as "understood", and the
Q053 result showed that a leak blamed on a threshold was really a one-line bug
in what counted as a content term. The same question is worth asking here.

For each over-abstaining query this dumps which hard/soft condition actually
failed, and — if it failed on coverage — which query terms were counted, so a
repeat of the Q053 stopword defect would be visible rather than inferred.

    python evaluation/overabstention_diag.py --corpus 1 --ids Q006,Q073
    python evaluation/overabstention_diag.py --corpus 2 --ids Q064
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


def why(orchestrator, q: dict) -> dict:
    res = orchestrator.run(q["query"], verbose=False)
    val = res.get("validation") or {}
    chunks = val.get("cleaned_chunks") or []
    scores = [c.get("score", 0.0) for c in chunks]
    avg = sum(scores) / len(scores) if scores else 0.0
    cov = val.get("query_coverage_score")

    # Re-derive each condition of check_sufficiency in order.
    h1 = len(chunks) >= validation.MIN_CHUNKS_FOR_SUFFICIENCY
    h3 = any(c.get("relevance_score", 1.0) > validation.MIN_RELEVANCE_SCORE
             for c in chunks)
    avg_applies = len(chunks) >= validation.MIN_CHUNKS_FOR_AVG_SUFFICIENCY
    h2 = avg_applies and avg >= validation.MIN_AVG_SCORE_FOR_SUFFICIENCY
    h4 = cov is not None and cov >= validation.MIN_QUERY_COVERAGE

    if not h1:
        blocker = f"H1 chunk count ({len(chunks)} < {validation.MIN_CHUNKS_FOR_SUFFICIENCY})"
    elif not h3:
        blocker = "H3 relevance floor (no chunk above relevance floor)"
    elif not (h2 or h4):
        if not avg_applies:
            blocker = (f"H2 blocked by chunk-count gate "
                       f"({len(chunks)} < {validation.MIN_CHUNKS_FOR_AVG_SUFFICIENCY}) "
                       f"AND H4 coverage {cov} < {validation.MIN_QUERY_COVERAGE}")
        else:
            blocker = (f"H2 avg {avg:.4f} < {validation.MIN_AVG_SCORE_FOR_SUFFICIENCY} "
                       f"AND H4 coverage {cov} < {validation.MIN_QUERY_COVERAGE}")
    else:
        blocker = "sufficiency passed (abstention came from elsewhere)"

    # Coverage term detail — the Q053 defect class.
    raw = {w.lower().strip(".,;:?!'\"()") for w in q["query"].split()}
    toks = {t for t in raw
            if not any(t.endswith(e) for e in validation._FILE_EXTENSIONS)}
    terms = {t for t in (toks - validation._COVERAGE_STOPWORDS) if t}
    ev = " ".join(c.get("text", "").lower() for c in chunks)
    term_detail = [
        {"term": t,
         "covered": t in ev,
         "whole_word": bool(re.search(rf"\b{re.escape(t)}\b", ev))}
        for t in sorted(terms)]

    return {
        "id": q["id"], "query": q["query"],
        "expected": q["expected_decision"],
        "observed": harness.decision_of(res),
        "abstention_reason": val.get("abstention_reason"),
        "n_chunks": len(chunks), "avg": round(avg, 4), "coverage": cov,
        "H1": h1, "H3": h3, "H2_avg": h2, "H2_applies": avg_applies, "H4_cov": h4,
        "blocker": blocker,
        "terms": term_detail,
        "chunk_scores": [round(s, 4) for s in scores],
        "chunk_sources": [c.get("source") for c in chunks],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="1")
    ap.add_argument("--ids", required=True)
    args = ap.parse_args()

    orchestrator = harness.setup(args.corpus)
    queries = {q["id"]: q for q in harness.load_queries(args.corpus)}

    out = []
    for i in [s.strip() for s in args.ids.split(",") if s.strip()]:
        d = why(orchestrator, queries[i])
        out.append(d)
        print(f"\n=== {d['id']} (corpus {args.corpus}) "
              f"exp={d['expected']} got={d['observed']} ===")
        print(f"  {d['query']}")
        print(f"  chunks={d['n_chunks']} scores={d['chunk_scores']}")
        print(f"  sources={d['chunk_sources']}")
        print(f"  avg={d['avg']}  coverage={d['coverage']}")
        print(f"  H1={d['H1']} H3={d['H3']} H2={d['H2_avg']} "
              f"(applies={d['H2_applies']}) H4={d['H4_cov']}")
        print(f"  BLOCKER: {d['blocker']}")
        print(f"  coverage terms:")
        for t in d["terms"]:
            mark = "covered" if t["covered"] else "ABSENT"
            print(f"     {t['term']:<20} {mark}")

    path = HERE / "results" / f"overabstention_corpus{args.corpus}.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWrote {path}")


if __name__ == "__main__":
    main()
