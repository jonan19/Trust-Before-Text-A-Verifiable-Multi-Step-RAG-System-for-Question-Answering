"""
threshold_sensitivity.py — Limitation 2: does the system still depend on
Corpus-1-calibrated constants?

"The threshold does not generalize" is really two claims: (a) the value fitted
on one corpus is not optimal on another, and (b) performance is sensitive
enough to the value that this matters. The structural gates added for L1/L3 are
supposed to attack (b): if performance is flat across a wide band of threshold
values on BOTH corpora, then the calibrated number stops being load-bearing,
which is the only version of "generalizes" a fixed constant can honestly claim.

This sweeps the two constants named in the limitation, with and without the
structural gates, on both corpora:

  NLI_CONFLICT_THRESHOLD          (conflict decisions, from the pair tables)
  MIN_AVG_SCORE_FOR_SUFFICIENCY   (sufficiency decisions, from the Stage-3 dumps)

    python evaluation/threshold_sensitivity.py
"""

from __future__ import annotations

import json
from pathlib import Path

import harness_bootstrap  # noqa: F401
import validation

HERE = Path(__file__).resolve().parent
RANK_N = 4


def conflict_scan(corpus: str, nli_t: float, rank_gate: bool) -> dict:
    data = json.loads((HERE / "pairs" / f"corpus{corpus}.json").read_text(encoding="utf-8"))
    tp = fp = fn = 0
    for rec in data:
        scores = sorted(rec["chunk_scores"], reverse=True)
        cut = scores[RANK_N - 1] if (rank_gate and len(scores) > RANK_N) else None
        fired = False
        for p in rec["pairs"]:
            if cut is not None and min(p["score_a"], p["score_b"]) < cut:
                continue
            high = p["sim"] >= validation.CONFLICT_SIM_THRESHOLD
            hit = ((high and p["keyword"])
                   or (p["sim"] >= validation.NLI_SIM_FLOOR and "nli_contra_ab" in p
                       and max(p["nli_contra_ab"], p["nli_contra_ba"]) >= nli_t)
                   or (high and p["numeric"]))
            if hit:
                fired = True
                break
        if fired:
            tp += rec["expected"] == "conflict"
            fp += rec["expected"] != "conflict"
        else:
            fn += rec["expected"] == "conflict"
    p_ = tp / (tp + fp) if tp + fp else 0.0
    r_ = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": round(p_, 3), "recall": round(r_, 3),
            "f1": round(2 * p_ * r_ / (p_ + r_), 3) if (p_ + r_) else 0.0}


def sufficiency_scan(corpus: str, avg_t: float, paired: bool) -> dict:
    records = json.loads((HERE / "stage3" / f"corpus{corpus}.json").read_text(encoding="utf-8"))
    leaks = blocked = 0
    for rec in records:
        chunks = rec["chunks"]
        scores = [c["score"] for c in chunks]
        avg = sum(scores) / len(scores) if scores else 0.0
        cov = validation._query_coverage(rec["processed"], chunks) if chunks else 1.0
        h1 = len(chunks) >= validation.MIN_CHUNKS_FOR_SUFFICIENCY
        h3 = any(c["relevance_score"] > validation.MIN_RELEVANCE_SCORE for c in chunks)
        h2 = avg >= avg_t and (len(chunks) >= 2 or not paired)
        h4 = cov >= validation.MIN_QUERY_COVERAGE
        ok = h1 and h3 and (h2 or h4)
        if rec["expected"] == "insufficient" and ok:
            leaks += 1
        if rec["expected"] == "answer" and not ok:
            blocked += 1
    return {"leaks": leaks, "blocked": blocked}


def main() -> None:
    out: dict = {}

    print("NLI contradiction threshold — conflict F1")
    print(f"{'thr':>6} | {'c1 no gate':>10} {'c1 +rank':>9} | {'c2 no gate':>10} {'c2 +rank':>9}")
    print("-" * 56)
    for t in (0.80, 0.85, 0.90, 0.94, 0.97, 0.99):
        row = {f"c{c}_{'gate' if g else 'plain'}": conflict_scan(c, t, g)
               for c in ("1", "2") for g in (False, True)}
        out[f"nli_{t}"] = row
        print(f"{t:>6.2f} | {row['c1_plain']['f1']:>10.3f} {row['c1_gate']['f1']:>9.3f} | "
              f"{row['c2_plain']['f1']:>10.3f} {row['c2_gate']['f1']:>9.3f}")

    print("\nSufficiency average-score threshold — (gap leaks, answerable blocked)")
    print(f"{'thr':>6} | {'c1 current':>14} {'c1 paired':>12} | {'c2 current':>12} {'c2 paired':>12}")
    print("-" * 66)
    for t in (0.55, 0.60, 0.62, 0.65, 0.68, 0.70, 0.75):
        row = {f"c{c}_{'paired' if p else 'plain'}": sufficiency_scan(c, t, p)
               for c in ("1", "2") for p in (False, True)}
        out[f"avg_{t}"] = row
        def fmt(d):
            return f"({d['leaks']},{d['blocked']})"
        print(f"{t:>6.2f} | {fmt(row['c1_plain']):>14} {fmt(row['c1_paired']):>12} | "
              f"{fmt(row['c2_plain']):>12} {fmt(row['c2_paired']):>12}")

    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / "threshold_sensitivity.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
