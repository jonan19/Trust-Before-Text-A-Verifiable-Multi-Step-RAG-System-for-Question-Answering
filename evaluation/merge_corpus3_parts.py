"""Merge batched Corpus 3 runs into the single result file run_eval_corpus3.py would write.

run_eval_corpus3.py saves its output only when every bundle it was given has
finished, which makes a 3-hour run fragile. rerun_corpus3.py therefore runs each
track in batches of bundles (run_eval_corpus3.py --bundles ...), one output file
per batch, and this script pools them.

Nothing is reimplemented: pooled metrics come from harness.metrics(), the same
function run_eval_corpus3.py calls, over the concatenated per-query records, in
bundle order. The merged file has the same schema as an unbatched run (meta,
config, metrics, per_bundle, results), so bootstrap_ci.py, span_attribution.py
and the comparison read it unchanged.

Guards, because a silent partial merge would produce plausible wrong numbers:
  * every bundle of the split appears exactly once across the parts;
  * every part ran under the identical configuration and query file.

    python evaluation/merge_corpus3_parts.py --tag c3_hypothesis \
        --queries queries.json --parts 6 --split test
Inputs : evaluation/results/<tag>__part<i>_corpus3_<split>.json  (i = 1..parts)
Output : evaluation/results/<tag>_corpus3_<split>.json
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import harness_bootstrap  # noqa: F401  (adds this dir to sys.path)
from harness import CORPORA, metrics
from run_eval_corpus3 import always_answer_floor, bundles_for
from run_info import run_info

OUT_DIR = Path(__file__).resolve().parent / "results"


def merge(parts: list[dict], expected_bundles: list[str], queries_file: str, tag: str,
          split: str) -> dict:
    """Pool already-loaded part files. Raises SystemExit on any inconsistency."""
    pooled: list[dict] = []
    per_bundle: dict[str, dict] = {}
    configs = []
    elapsed = 0.0
    for p in parts:
        meta = p["meta"]
        if meta.get("queries_file") != queries_file:
            raise SystemExit("A part used queries file %r, expected %r."
                             % (meta.get("queries_file"), queries_file))
        configs.append(json.dumps(p["config"], sort_keys=True))
        elapsed += float(meta.get("elapsed_s") or 0)
        for name, m in p["per_bundle"].items():
            if name in per_bundle:
                raise SystemExit("Bundle %s appears in more than one part." % name)
            per_bundle[name] = m
        pooled.extend(p["results"])

    if len(set(configs)) > 1:
        raise SystemExit("Parts ran under different configurations; refusing to merge.")
    missing = sorted(set(expected_bundles) - set(per_bundle))
    extra = sorted(set(per_bundle) - set(expected_bundles))
    if missing or extra:
        raise SystemExit("Bundle mismatch. missing: %s  unexpected: %s" % (missing, extra))

    order = {name: i for i, name in enumerate(sorted(per_bundle))}
    pooled.sort(key=lambda r: order[r["bundle"]])  # stable: keeps within-bundle order
    per_bundle = {k: per_bundle[k] for k in sorted(per_bundle)}

    pooled_metrics = metrics(pooled)
    pooled_metrics["always_answer_floor_pct"] = always_answer_floor(pooled)
    pooled_metrics["gold_distribution"] = dict(Counter(r["expected"] for r in pooled))
    return {
        "meta": {"tag": tag, "corpus": "3", "split": split, "queries_file": queries_file,
                 "n_bundles": len(per_bundle), "elapsed_s": round(elapsed, 1),
                 "merged_from_parts": len(parts)},
        "config": parts[0]["config"],
        "run_info": run_info(),
        "metrics": pooled_metrics,
        "per_bundle": per_bundle,
        "results": pooled,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True, help="final tag, e.g. c3_hypothesis")
    ap.add_argument("--queries", default="queries.json")
    ap.add_argument("--parts", type=int, required=True)
    ap.add_argument("--split", choices=["dev", "test"], default="test")
    args = ap.parse_args()

    files = [OUT_DIR / f"{args.tag}__part{i}_corpus3_{args.split}.json"
             for i in range(1, args.parts + 1)]
    absent = [f.name for f in files if not f.exists()]
    if absent:
        raise SystemExit("Missing part files: %s" % absent)
    parts = [json.loads(f.read_text(encoding="utf-8")) for f in files]

    result = merge(parts, bundles_for(args.split), args.queries, args.tag, args.split)
    out = OUT_DIR / f"{args.tag}_corpus3_{args.split}.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    m = result["metrics"]
    print("merged %d parts -> %d bundles, %d queries" % (
        args.parts, result["meta"]["n_bundles"], len(result["results"])))
    for k in ("accuracy", "accuracy_pct", "conflict_precision", "conflict_recall",
              "gap_leak_count", "unsafe_answers", "always_answer_floor_pct"):
        print("  %-26s %s" % (k, m.get(k)))
    print("Wrote %s" % out)


if __name__ == "__main__":
    main()
