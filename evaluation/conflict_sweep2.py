"""
conflict_sweep2.py — Second sweep for the Stage-4 gate (Limitation 1), testing
an evidence-rank gate alone and combined with the shared-discriminative-term
gate, on both corpora.

Rank gate rationale: a contradiction should drive abstention only if it sits in
the evidence that actually answers this query. A pair of chunks that the
retriever ranked 7th and 9th disagreeing about something is, for this question,
a fact about the corpus, not about the answer. Expressed as a fraction of the
best score for THIS query (a relative quantity, not an absolute one), so it
carries no corpus-specific calibration.

    python evaluation/conflict_sweep2.py
"""

from __future__ import annotations

import json
from pathlib import Path

import harness_bootstrap  # noqa: F401
import validation
from conflict_lab import base_prongs
from conflict_sweep import _expand, rank_selector
from focus import CorpusStats, matches, stems

HERE = Path(__file__).resolve().parent


def _shared(p: dict, allowed: set[str]) -> bool:
    if not allowed:
        return True
    a, b = stems(p["span_a"]), stems(p["span_b"])
    return any(matches(t, a) and matches(t, b) for t in allowed)


def score(corpus: str, *, keep: float | None, top_n: int | None,
          band: float | None, numerals: bool = True) -> dict:
    stats = CorpusStats.load(HERE / "corpus_stats" / f"corpus{corpus}.json")
    data = json.loads((HERE / "pairs" / f"corpus{corpus}.json").read_text(encoding="utf-8"))
    flagged, tp, false_ids, missed = 0, 0, [], []

    for rec in data:
        scores = sorted(rec["chunk_scores"], reverse=True)
        best = scores[0] if scores else 0.0
        cut_n = scores[min(top_n, len(scores)) - 1] if (top_n and scores) else None
        cut_b = best * band if band else None

        allowed = set()
        if keep is not None:
            terms = _expand(validation._query_content_terms(rec["processed"]), numerals=numerals)
            allowed = rank_selector(keep)(terms, stats)

        fired = False
        for p in rec["pairs"]:
            if not base_prongs(p):
                continue
            if cut_n is not None and min(p["score_a"], p["score_b"]) < cut_n:
                continue
            if cut_b is not None and min(p["score_a"], p["score_b"]) < cut_b:
                continue
            if keep is not None and not _shared(p, allowed):
                continue
            fired = True
            break

        if fired:
            flagged += 1
            if rec["expected"] == "conflict":
                tp += 1
            else:
                false_ids.append(rec["id"])
        elif rec["expected"] == "conflict":
            missed.append(rec["id"])

    n_true = sum(1 for r in data if r["expected"] == "conflict")
    prec = tp / flagged if flagged else 0.0
    rc = tp / n_true if n_true else 0.0
    return {"flagged": flagged, "precision": round(prec, 3), "recall": round(rc, 3),
            "f1": round(2 * prec * rc / (prec + rc), 3) if (prec + rc) else 0.0,
            "false": false_ids, "missed": missed}


def main() -> None:
    settings: list[tuple[str, dict]] = [("current", dict(keep=None, top_n=None, band=None))]
    for n in (2, 3, 4, 5):
        settings.append((f"top{n}", dict(keep=None, top_n=n, band=None)))
    for b in (0.85, 0.90, 0.95):
        settings.append((f"band{b:.2f}", dict(keep=None, top_n=None, band=b)))
    for k in (0.6, 0.7, 0.8):
        settings.append((f"term{k:.1f}", dict(keep=k, top_n=None, band=None)))
        for n in (3, 4, 5):
            settings.append((f"term{k:.1f}+top{n}", dict(keep=k, top_n=n, band=None)))
        for b in (0.90, 0.95):
            settings.append((f"term{k:.1f}+band{b:.2f}", dict(keep=k, top_n=None, band=b)))

    out = {}
    print(f"{'setting':>18} |      corpus 1        |      corpus 2")
    print("-" * 74)
    for name, kw in settings:
        r1, r2 = score("1", **kw), score("2", **kw)
        out[name] = {"1": r1, "2": r2}
        print(f"{name:>18} | P={r1['precision']:.3f} R={r1['recall']:.3f} F1={r1['f1']:.3f} "
              f"| P={r2['precision']:.3f} R={r2['recall']:.3f} F1={r2['f1']:.3f}"
              f"   missed c1={len(r1['missed'])} c2={len(r2['missed'])}")

    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / "conflict_sweep2.json").write_text(json.dumps(out, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
