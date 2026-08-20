"""
conflict_lab.py — Evaluate candidate Stage-4 conflict rules over the cached
pair tables (Limitation 1: false conflicts from query-irrelevant pairs).

Every rule is scored the way the pipeline would see it: a query is flagged as a
conflict if ANY eligible pair passes the rule. Reports conflict
precision/recall/F1 per corpus, so a rule that only helps the corpus it was
designed on is immediately visible as such.

    python evaluation/conflict_lab.py [--corpus 1|2] [--rules a,b,c]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import harness_bootstrap  # noqa: F401
import validation
from focus import CorpusStats, focus_terms, stems

HERE = Path(__file__).resolve().parent
NLI_T = validation.NLI_CONFLICT_THRESHOLD
SIM_T = validation.CONFLICT_SIM_THRESHOLD
NLI_FLOOR = validation.NLI_SIM_FLOOR


def base_prongs(p: dict) -> str | None:
    """Replicate find_conflict's three prongs exactly."""
    high_sim = p["sim"] >= SIM_T
    if high_sim and p["keyword"]:
        return "keyword"
    if p["sim"] >= NLI_FLOOR and "nli_contra_ab" in p:
        if max(p["nli_contra_ab"], p["nli_contra_ba"]) >= NLI_T:
            return "nli"
    if high_sim and p["numeric"]:
        return "numeric"
    return None


def shared_focus(p: dict, foc: set[str]) -> bool:
    """
    True when both spans mention at least one of the query's discriminative
    terms. This is the structural core of the fix: a contradiction is only
    about the user's question if both sides of it talk about what was asked,
    using a term specific enough to distinguish this question from its
    neighbours ("Dean's List", not "GPA").
    """
    if not foc:
        return True  # no discriminative terms -> gate cannot judge, stay open
    fs = {s for t in foc for s in stems(t)}
    a = stems(p["span_a"])
    b = stems(p["span_b"])
    return bool(fs & a & b)


def shared_any_term(p: dict) -> bool:
    return bool(p["shared_terms"])


RULES = {
    "current":      lambda p, f: base_prongs(p) is not None,
    "shared_term":  lambda p, f: base_prongs(p) is not None and shared_any_term(p),
    "focus":        lambda p, f: base_prongs(p) is not None and shared_focus(p, f),
    "focus_sym":    lambda p, f: (
        base_prongs(p) is not None and shared_focus(p, f)
        and (base_prongs(p) != "nli"
             or min(p.get("nli_contra_ab", 0.0), p.get("nli_contra_ba", 0.0)) >= NLI_T)
    ),
    "qsim035":      lambda p, f: (base_prongs(p) is not None
                                  and min(p["qsim_a"], p["qsim_b"]) >= 0.35),
    "qsim050":      lambda p, f: (base_prongs(p) is not None
                                  and min(p["qsim_a"], p["qsim_b"]) >= 0.50),
}


def evaluate(corpus: str, rule_names: list[str]) -> dict:
    stats = CorpusStats.load(HERE / "corpus_stats" / f"corpus{corpus}.json")
    data = json.loads((HERE / "pairs" / f"corpus{corpus}.json").read_text(encoding="utf-8"))

    out = {}
    for name in rule_names:
        fn = RULES[name]
        flagged, tp, fp_ids, fn_ids = 0, 0, [], []
        for rec in data:
            terms = validation._query_content_terms(rec["processed"])
            foc = focus_terms(terms, stats)
            fired = any(fn(p, foc) for p in rec["pairs"])
            if fired:
                flagged += 1
                if rec["expected"] == "conflict":
                    tp += 1
                else:
                    fp_ids.append(rec["id"])
            elif rec["expected"] == "conflict":
                fn_ids.append(rec["id"])
        n_true = sum(1 for r in data if r["expected"] == "conflict")
        prec = tp / flagged if flagged else 0.0
        rec_ = tp / n_true if n_true else 0.0
        f1 = 2 * prec * rec_ / (prec + rec_) if (prec + rec_) else 0.0
        out[name] = {"flagged": flagged, "tp": tp, "precision": round(prec, 4),
                     "recall": round(rec_, 4), "f1": round(f1, 4),
                     "false": fp_ids, "missed": fn_ids}
        print(f"  {name:12} flagged={flagged:>3} P={prec:.3f} R={rec_:.3f} F1={f1:.3f}  "
              f"missed={fn_ids}")
        print(f"               false={fp_ids}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", choices=["1", "2"])
    ap.add_argument("--rules", default=",".join(RULES))
    args = ap.parse_args()
    names = [r for r in args.rules.split(",") if r in RULES]
    corpora = [args.corpus] if args.corpus else ["1", "2"]

    all_out = {}
    for c in corpora:
        if not (HERE / "pairs" / f"corpus{c}.json").exists():
            print(f"\n(corpus {c} pair table not built yet, skipping)")
            continue
        print(f"\n{'=' * 74}\nCorpus {c}\n{'=' * 74}")
        all_out[c] = evaluate(c, names)
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / "conflict_lab.json").write_text(json.dumps(all_out, indent=2), encoding="utf-8")
