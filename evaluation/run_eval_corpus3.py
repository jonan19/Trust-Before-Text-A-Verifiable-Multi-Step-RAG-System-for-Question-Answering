"""
run_eval_corpus3.py — Decision evaluation over Corpus 3 (ContractNLI bundles).

Corpus 3 is not one store but ~45: one per 4-NDA bundle. This driver walks the
bundles of a split, runs the live pipeline over each bundle's queries, then
POOLS the records and hands them to the existing harness.metrics(). Nothing
about the scoring is reimplemented here — accuracy, conflict P/R/F1, gap leaks,
unsafe answers and attribution all come from the same function that produces the
Corpus 1/2 numbers in docs/STATUS.md.

Two Corpus-3-specific things this adds:

  * the always-answer floor, computed from the gold labels, printed beside
    accuracy. On the test split that floor is 77.6%, which is higher than Corpus
    2's current accuracy. An accuracy figure reported without it is not
    interpretable.
  * a per-bundle breakdown. Thirty bundles are thirty independent samples of the
    same pipeline; the spread across them is a generalisation signal the
    single-corpus design cannot produce, and it feeds bootstrap_ci.py.

Governance: refuses to run with any RAG_* override set. Corpus 3 is read once,
under the frozen configuration, and never used to select anything. See
docs/PREREGISTRATION_CORPUS3.md.

Usage
-----
    python evaluation/run_eval_corpus3.py --split dev  --tag dev_smoke
    python evaluation/run_eval_corpus3.py --split test --tag c3_hypothesis
    python evaluation/run_eval_corpus3.py --split test --queries queries_qform.json --tag c3_qform
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from pathlib import Path

import harness_bootstrap  # noqa: F401  (adds this dir to sys.path)
from harness import (CORPORA, config_snapshot, load_queries, metrics,
                     run_queries, setup)

OUT_DIR = Path(__file__).resolve().parent / "results"


def bundles_for(split: str) -> list[str]:
    return sorted(k for k in CORPORA if k.startswith(f"3-{split}-"))


def assert_frozen_config() -> None:
    """
    Corpus 3 is evaluated under the configuration Corpus 1/2 were frozen at.

    A RAG_* override here would mean a threshold was chosen with knowledge of
    this corpus, which is precisely what the held-out design exists to prevent.
    Refusing is cheaper than discovering it in the results.
    """
    overrides = {k: v for k, v in os.environ.items() if k.startswith("RAG_")}
    if overrides:
        raise SystemExit(
            f"Refusing to run: RAG_* overrides are set {overrides}.\n"
            "Corpus 3 runs under the frozen configuration only. "
            "See docs/PREREGISTRATION_CORPUS3.md."
        )


def always_answer_floor(records: list[dict]) -> float | None:
    """The majority-class baseline: accuracy of a policy that never abstains."""
    if not records:
        return None
    n_answer = sum(1 for r in records if r["expected"] == "answer")
    return round(100 * n_answer / len(records), 1)


def run_bundle(name: str, queries_file: str, *, quiet: bool) -> list[dict]:
    """
    Evaluate one bundle.

    _close_client() first, every time. qdrant_retrieval._get_client caches a
    single module-global client and IGNORES its qdrant_dir argument once one is
    open (qdrant_retrieval.py:118). Without this reset every bundle after the
    first would silently retrieve from bundle 0's store — producing plausible,
    entirely invalid results.
    """
    import qdrant_retrieval
    qdrant_retrieval._close_client()
    qdrant_retrieval._published_registry_dir = None

    orchestrator = setup(name)
    queries = load_queries(name, queries_file)
    return run_queries(orchestrator, queries, progress=not quiet, keep_evidence=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test"], required=True)
    ap.add_argument("--tag", required=True, help="label for the output file")
    ap.add_argument("--queries", default="queries.json",
                    help="query set filename within each bundle")
    ap.add_argument("--bundles", help="comma-separated bundle names (default: all)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    assert_frozen_config()

    names = bundles_for(args.split)
    if args.bundles:
        wanted = {s.strip() for s in args.bundles.split(",")}
        names = [n for n in names if n.removeprefix("3-") in wanted or n in wanted]
    if not names:
        raise SystemExit(f"No corpus-3 bundles registered for split '{args.split}'. "
                         f"Run: python evaluation/build_corpus3.py --split {args.split}")

    if args.split == "test":
        print("\n  *** TEST SPLIT — held-out data, opened once. "
              "See docs/PREREGISTRATION_CORPUS3.md.\n")

    t0 = time.time()
    pooled: list[dict] = []
    per_bundle: dict[str, dict] = {}

    for i, name in enumerate(names, 1):
        print(f"\n=== [{i}/{len(names)}] {name} ===", flush=True)
        records = run_bundle(name, args.queries, quiet=args.quiet)
        for rec in records:
            rec["bundle"] = name
        pooled.extend(records)
        per_bundle[name] = metrics(records)

    elapsed = round(time.time() - t0, 1)

    pooled_metrics = metrics(pooled)
    pooled_metrics["always_answer_floor_pct"] = always_answer_floor(pooled)
    pooled_metrics["gold_distribution"] = dict(Counter(r["expected"] for r in pooled))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{args.tag}_corpus3_{args.split}.json"
    out.write_text(json.dumps({
        "meta": {
            "tag": args.tag, "corpus": "3", "split": args.split,
            "queries_file": args.queries, "n_bundles": len(names),
            "elapsed_s": elapsed,
        },
        "config": config_snapshot(),
        "metrics": pooled_metrics,
        "per_bundle": per_bundle,
        "results": pooled,
    }, indent=2), encoding="utf-8")

    print(f"\n=== {args.tag} / corpus 3 / {args.split} "
          f"({len(names)} bundles, {len(pooled)} queries, {elapsed}s) ===")
    for k, v in pooled_metrics.items():
        print(f"  {k:26} {v}")

    floor = pooled_metrics["always_answer_floor_pct"]
    acc = pooled_metrics["accuracy_pct"]
    if floor is not None and acc is not None:
        verdict = "ABOVE" if acc > floor else "AT OR BELOW"
        print(f"\n  accuracy {acc}% vs always-answer floor {floor}% -> {verdict} floor")

    accs = [m["accuracy_pct"] for m in per_bundle.values() if m["accuracy_pct"] is not None]
    if accs:
        print(f"  per-bundle accuracy: min {min(accs)}%  max {max(accs)}%  "
              f"n={len(accs)} bundles")

    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
