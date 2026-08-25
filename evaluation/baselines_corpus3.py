"""
baselines_corpus3.py — Reference arms for Corpus 3.

Why this exists
---------------
Corpus 3's gold distribution is skewed: on the test split, 396 of 510 queries are
`answer`, so a policy that never abstains scores 77.6% without reading anything.
Corpus 1 and 2 are near-balanced and have no comparable floor, which is why this
never mattered before. Reporting a Corpus 3 accuracy figure without the floor
beside it would be uninterpretable, and a reviewer would say so immediately.

Four arms, all scored by the same harness.metrics() the system is scored with:

  always_answer      the majority-class floor. The number that makes accuracy
                     interpretable.
  always_abstain     trivially perfect safety, near-zero utility. Establishes
                     that the safety claim only means something jointly with
                     utility — a system can score 0 unsafe answers by refusing
                     everything.
  retrieval_threshold  answer iff the top chunk clears MIN_CHUNK_SCORE_THRESHOLD,
                     else abstain. No validation stages, no conflict detection.
                     Isolates how much of the decision quality comes from the
                     validation pipeline rather than from retrieval alone.

The bare-LLM arm is deliberately NOT here: it costs tokens, and the project
already has evaluation/adversarial_baseline_probe.py for LLM comparisons. Run
that separately rather than duplicating its prompt handling.

These arms are decision policies, not systems: they reuse the cached retrieval
the real runs populated, so they cost no LLM tokens and no re-embedding.

Usage
-----
    python evaluation/baselines_corpus3.py --split dev
    python evaluation/baselines_corpus3.py --split test --tag c3_baselines
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import harness_bootstrap  # noqa: F401  (adds this dir to sys.path)
from harness import CORPORA, load_queries, metrics

OUT_DIR = Path(__file__).resolve().parent / "results"


def gold_records(split: str) -> list:
    """Every Corpus 3 query of a split, as bare gold records."""
    records = []
    for corpus in sorted(k for k in CORPORA if k.startswith(f"3-{split}-")):
        for query in load_queries(corpus):
            records.append({
                "id": query["id"],
                "bundle": corpus,
                "query": query["query"],
                "expected": query["expected_decision"],
                "expected_conflict_pair": query.get("expected_conflict_pair"),
                "conflict_pair": None,
            })
    return records


def score(records: list, decide) -> dict:
    """Apply a decision policy and score it with the standard metric block."""
    scored = []
    for rec in records:
        row = dict(rec)
        row["observed"] = decide(rec)
        row["match"] = row["observed"] == row["expected"]
        scored.append(row)
    return metrics(scored)


def retrieval_threshold_decisions(split: str, top_k: int = 5) -> dict:
    """
    Answer iff the best retrieved chunk clears the production score threshold.

    This arm does its OWN retrieval rather than reading the harness cache. The
    orchestrator preprocesses and decomposes a query before retrieving, so the
    cache is keyed by sub-queries and the original question is never a key —
    an earlier version of this function looked for the raw query text and found
    nothing, silently abstaining on all 255 queries.

    Retrieval here still goes through harness.setup()'s cached wrapper, so the
    results are written to the same on-disk cache and a re-run is free.

    Returns {query_id: decision}.
    """
    import qdrant_retrieval
    import retrieval_interface
    import validation
    from harness import setup

    threshold = getattr(validation, "MIN_CHUNK_SCORE_THRESHOLD", 0.0)
    decisions = {}

    for corpus in sorted(k for k in CORPORA if k.startswith(f"3-{split}-")):
        # _get_client caches one module-global client and ignores qdrant_dir
        # once open (qdrant_retrieval.py:118); without this reset every bundle
        # after the first would retrieve from bundle 0's store.
        qdrant_retrieval._close_client()
        qdrant_retrieval._published_registry_dir = None
        setup(corpus)

        for query in load_queries(corpus):
            chunks = retrieval_interface._qdrant_retrieve(query["query"], top_k=top_k)
            best = max((c.get("score", 0.0) for c in chunks), default=0.0)
            decisions[query["id"]] = "answer" if best >= threshold else "insufficient"

    return decisions, threshold


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test"], required=True)
    ap.add_argument("--tag", default="baselines")
    ap.add_argument("--skip-retrieval", action="store_true",
                    help="only the two trivial arms; skips the retrieval pass")
    args = ap.parse_args()

    records = gold_records(args.split)
    if not records:
        raise SystemExit(f"No corpus-3 bundles registered for split '{args.split}'.")

    arms = {
        "always_answer": score(records, lambda r: "answer"),
        "always_abstain": score(records, lambda r: "insufficient"),
    }

    if not args.skip_retrieval:
        decisions, threshold = retrieval_threshold_decisions(args.split)
        missing = [r["id"] for r in records if r["id"] not in decisions]
        arms["retrieval_threshold"] = score(
            records, lambda r: decisions.get(r["id"], "insufficient")
        )
        arms["retrieval_threshold"]["_threshold"] = threshold
        arms["retrieval_threshold"]["_unscored"] = len(missing)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{args.tag}_corpus3_{args.split}.json"
    out.write_text(json.dumps({
        "meta": {"split": args.split, "n": len(records)},
        "arms": arms,
    }, indent=2), encoding="utf-8")

    print(f"=== baselines / corpus 3 / {args.split} ({len(records)} queries) ===\n")
    header = f"  {'arm':22} {'acc%':>7} {'conf_P':>8} {'conf_R':>8} {'unsafe':>10}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for name, block in arms.items():
        print(f"  {name:22} {block['accuracy_pct']:>7} "
              f"{block['conflict_precision']:>8} {block['conflict_recall']:>8} "
              f"{block['unsafe_answers']:>10}")

    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
