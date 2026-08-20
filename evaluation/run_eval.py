"""
run_eval.py — Decision-only evaluation of the live pipeline on either corpus,
under whatever threshold configuration the environment specifies.

    python evaluation/run_eval.py --corpus 1 --tag baseline
    RAG_QUERY_SPAN_RELEVANCE=0.35 python evaluation/run_eval.py --corpus 2 --tag qsr035

Writes evaluation/results/<tag>_corpus<N>.json and prints the metric
block. Never touches the frozen experiments/ or experiments_corpus2/ artifacts.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import harness_bootstrap  # noqa: F401  (adds this dir to sys.path)
from harness import (CORPORA, config_snapshot, load_queries, metrics,
                     run_queries, setup)

OUT_DIR = Path(__file__).resolve().parent / "results"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", choices=sorted(CORPORA), required=True)
    ap.add_argument("--tag", required=True, help="label for the output file")
    ap.add_argument("--ids", help="comma-separated query ids to run (default: all)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    orchestrator = setup(args.corpus)
    queries = load_queries(args.corpus)
    if args.ids:
        wanted = {s.strip() for s in args.ids.split(",")}
        queries = [q for q in queries if q["id"] in wanted]

    t0 = time.time()
    records = run_queries(orchestrator, queries, progress=not args.quiet)
    m = metrics(records)
    elapsed = round(time.time() - t0, 1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{args.tag}_corpus{args.corpus}.json"
    out.write_text(json.dumps({
        "meta": {"tag": args.tag, "corpus": args.corpus, "elapsed_s": elapsed},
        "config": config_snapshot(),
        "metrics": m,
        "results": records,
    }, indent=2), encoding="utf-8")

    print(f"\n=== {args.tag} / corpus {args.corpus} ({elapsed}s) ===")
    for k, v in m.items():
        print(f"  {k:22} {v}")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
