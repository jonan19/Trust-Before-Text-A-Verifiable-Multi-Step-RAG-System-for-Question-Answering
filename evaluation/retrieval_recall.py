"""
retrieval_recall.py — document-level retrieval recall against expected_sources.

Measures the retriever alone, on the single preprocessed query (no
decomposition, no retry), exactly as validation first receives it. Zero LLM
tokens. Gap queries carry no expected source and are excluded.

    python evaluation/retrieval_recall.py --corpus 1
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import harness_bootstrap  # noqa: F401
import harness

HERE = Path(__file__).resolve().parent
KS = (1, 3, 5, 10, 30)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", choices=["1", "2"], required=True)
    args = ap.parse_args()

    orchestrator = harness.setup(args.corpus)
    from retrieval_interface import retrieve

    rows = []
    for q in harness.load_queries(args.corpus):
        gold = set(q.get("expected_sources") or [])
        if not gold:
            continue
        chunks = retrieve(orchestrator.preprocess_query(q["query"]),
                          top_k=orchestrator.RETRIEVAL_TOP_K)
        ranked = [c.get("source") for c in chunks]
        first = next((i for i, s in enumerate(ranked, 1) if s in gold), None)
        rows.append({
            "id": q["id"], "expected": q["expected_decision"], "gold": sorted(gold),
            "n_retrieved": len(ranked),
            "recall": {k: len(gold & set(ranked[:k])) / len(gold) for k in KS},
            "all_gold": {k: gold <= set(ranked[:k]) for k in KS},
            "first_gold_rank": first,
        })

    def summarise(sub):
        n = len(sub)
        return {
            "n": n,
            "recall_at_k": {k: round(sum(r["recall"][k] for r in sub) / n, 4) for k in KS},
            "all_gold_at_k": {k: sum(r["all_gold"][k] for r in sub) for k in KS},
            "mrr": round(sum(1 / r["first_gold_rank"] for r in sub if r["first_gold_rank"]) / n, 4),
            "no_gold_retrieved": [r["id"] for r in sub if r["first_gold_rank"] is None],
        }

    summary = {"all": summarise(rows)}
    for cls in ("answer", "conflict", "insufficient"):
        sub = [r for r in rows if r["expected"] == cls]
        if sub:
            summary[cls] = summarise(sub)

    print(json.dumps(summary, indent=2))
    out = HERE / "results" / f"retrieval_recall_corpus{args.corpus}.json"
    out.write_text(json.dumps({"meta": {"corpus": args.corpus,
                                        "top_k": orchestrator.RETRIEVAL_TOP_K},
                               "summary": summary, "results": rows}, indent=2),
                   encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
