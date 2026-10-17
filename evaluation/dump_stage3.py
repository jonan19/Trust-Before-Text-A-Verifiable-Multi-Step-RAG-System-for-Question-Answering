"""
dump_stage3.py — Dump the Stage-3 (relevance-filtered) evidence set for every
query on a corpus, so pair-level conflict rules can be designed and evaluated
offline without re-running retrieval or the NLI model for each idea.

This is the input to pair_lab.py. It records exactly what find_conflict sees on
the first orchestrator attempt: same preprocessing, same retrieval, same
source-targeting, same Stage 1-3 chain.

    python evaluation/dump_stage3.py --corpus 1
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import harness_bootstrap  # noqa: F401
import harness
import validation

OUT_DIR = Path(__file__).resolve().parent / "stage3"


def stage3_for(orchestrator, query: str) -> tuple[str, list[dict]]:
    """Replay orchestrator.run's attempt-1 evidence path, stopping at Stage 3."""
    processed = orchestrator.preprocess_query(query)
    qtype = orchestrator.classify_query(processed)
    subs = orchestrator.decompose_query(processed) if qtype == "complex" else [processed]
    top_k = (orchestrator.RETRIEVAL_TOP_K + len(subs)
             if qtype == "complex" and len(subs) > 1 else orchestrator.RETRIEVAL_TOP_K)

    raw = orchestrator.retrieve_for_queries(subs, top_k=top_k)
    target = orchestrator._extract_target_source(processed, raw)
    if target:
        filtered = [c for c in raw if c.get("source") == target]
        raw = filtered if filtered else raw

    s1 = validation.normalize_chunks(raw)
    s2 = validation.remove_duplicates(s1)
    s3 = validation.filter_by_relevance(s2, processed)
    return processed, s3


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", choices=sorted(harness.CORPORA), required=True)
    args = ap.parse_args()

    orchestrator = harness.setup(args.corpus)
    queries = harness.load_queries(args.corpus)

    out: list[dict] = []
    for i, q in enumerate(queries, 1):
        processed, chunks = stage3_for(orchestrator, q["query"])
        out.append({
            "id": q["id"],
            "category": q.get("category"),
            "query": q["query"],
            "processed": processed,
            "expected": q["expected_decision"],
            "chunks": [
                {"text": c.get("text", ""), "source": c.get("source", "unknown"),
                 "section": c.get("section", "unknown"),
                 "score": round(float(c.get("score", 0.0)), 6),
                 "relevance_score": round(float(c.get("relevance_score", 0.0)), 6)}
                for c in chunks
            ],
        })
        print(f"[{i}/{len(queries)}] {q['id']}  {len(chunks)} chunks", flush=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"corpus{args.corpus}.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
