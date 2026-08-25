"""
bootstrap_ci.py — Confidence intervals for Corpus 3, clustered by bundle.

Why clustered
-------------
The 17 queries inside a bundle are asked against the SAME four documents. They
share retrieval behaviour, share the corpus statistics fitted on those four
documents, and — as the dev split showed — frequently share the very same cited
conflict pair. They are not independent samples.

Resampling the 510 queries directly would therefore report an interval far
narrower than the evidence supports. This resamples the BUNDLES with
replacement, recomputing every metric over the pooled records of the resampled
bundles. The unit of resampling matches the unit of independence.

This replaces the project's historical raw-count reporting, where "16/16 vs
15/16" had no interval at all and docs/STATUS.md had to caveat that one query
was 6.25 points.

Usage
-----
    python evaluation/bootstrap_ci.py --tag c3_hypothesis --split test
    python evaluation/bootstrap_ci.py --tag dev_smoke --split dev --iterations 2000
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

import harness_bootstrap  # noqa: F401  (adds this dir to sys.path)
from harness import metrics

OUT_DIR = Path(__file__).resolve().parent / "results"

# Metrics worth an interval. Everything else metrics() emits is a list or a
# raw count that a percentile would not describe.
NUMERIC = [
    "accuracy_pct",
    "conflict_precision",
    "conflict_recall",
    "conflict_f1",
    "attribution_precision",
]


def percentile(values: list, q: float):
    """Linear-interpolated percentile; `values` need not be sorted."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 4)
    pos = q * (len(ordered) - 1)
    low = int(pos)
    high = min(low + 1, len(ordered) - 1)
    frac = pos - low
    return round(ordered[low] * (1 - frac) + ordered[high] * frac, 4)


def bootstrap(records: list, iterations: int, seed: int) -> dict:
    by_bundle = defaultdict(list)
    for rec in records:
        by_bundle[rec.get("bundle", "_none")].append(rec)
    names = sorted(by_bundle)

    if len(names) < 2:
        raise SystemExit(
            f"Only {len(names)} bundle(s) in this result file. A cluster bootstrap "
            "needs several bundles to resample; run more before computing intervals."
        )

    rng = random.Random(seed)
    draws = defaultdict(list)

    for _ in range(iterations):
        pooled = []
        for _ in range(len(names)):
            pooled.extend(by_bundle[names[rng.randrange(len(names))]])
        sample = metrics(pooled)
        for key in NUMERIC:
            value = sample.get(key)
            if value is not None:
                draws[key].append(value)

    point = metrics(records)
    out = {
        "n_bundles": len(names),
        "n_queries": len(records),
        "iterations": iterations,
        "seed": seed,
        "intervals": {},
    }
    for key in NUMERIC:
        values = draws.get(key) or []
        out["intervals"][key] = {
            "point": point.get(key),
            "ci_low": percentile(values, 0.025),
            "ci_high": percentile(values, 0.975),
        }

    # Per-bundle spread: 30 independent samples of the same pipeline. More
    # informative than any single point estimate, and impossible to produce
    # from a single-corpus design.
    per_bundle = [metrics(by_bundle[n])["accuracy_pct"] for n in names]
    per_bundle = [v for v in per_bundle if v is not None]
    out["per_bundle_accuracy"] = {
        "values": per_bundle,
        "min": min(per_bundle) if per_bundle else None,
        "max": max(per_bundle) if per_bundle else None,
        "median": percentile(per_bundle, 0.5),
    }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--split", choices=["dev", "test"], default="test")
    ap.add_argument("--iterations", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    path = OUT_DIR / f"{args.tag}_corpus3_{args.split}.json"
    if not path.exists():
        raise SystemExit(f"No result file at {path}. Run run_eval_corpus3.py first.")

    payload = json.loads(path.read_text(encoding="utf-8"))
    result = bootstrap(payload["results"], args.iterations, args.seed)

    out = OUT_DIR / f"{args.tag}_corpus3_{args.split}_ci.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"=== cluster bootstrap / {args.tag} / {args.split} ===")
    print(f"  {result['n_bundles']} bundles, {result['n_queries']} queries, "
          f"{result['iterations']} iterations, resampled by BUNDLE\n")
    for key, band in result["intervals"].items():
        if band["point"] is None:
            continue
        print(f"  {key:22} {band['point']}  95% CI [{band['ci_low']}, {band['ci_high']}]")

    spread = result["per_bundle_accuracy"]
    print(f"\n  per-bundle accuracy: min {spread['min']}%  median {spread['median']}%  "
          f"max {spread['max']}%")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
