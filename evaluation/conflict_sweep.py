"""
conflict_sweep.py — Sweep the "how specific must a shared term be" parameter of
the Stage-4 query-relevance gate, scoring every setting on BOTH corpora.

Two families are compared:

  rank(keep)  a shared term counts if it is among the rarest `keep` fraction of
              the query's content terms
  ratio(tau)  a shared term counts if its IDF is at least `tau` times the
              highest IDF among the query's content terms

The point of sweeping both on both corpora is to see whether any setting is
jointly good, and how sharply performance depends on the setting. A rule whose
best value differs per corpus is a calibrated constant in disguise (Limitation
2) and is rejected no matter how well it scores on one corpus.

    python evaluation/conflict_sweep.py
"""

from __future__ import annotations

import json
from pathlib import Path

import harness_bootstrap  # noqa: F401
import validation
from conflict_lab import base_prongs
from focus import CorpusStats, matches, stems, tokenize

HERE = Path(__file__).resolve().parent


_NUM_RE = __import__("re").compile(r"\d[\d.,/-]*")

# Words that name a source document rather than anything inside one. A query
# saying "in the Handbook versus the Grading Policy" is telling the system WHERE
# to look, not WHAT the answer is about; counting those words as the query's
# distinguishing terms crowds out the ones that carry the question ("probation",
# "recording"). Derived from the corpus's own indexed filenames, so it needs no
# per-corpus word list.
def source_name_terms(corpus: str) -> set[str]:
    import harness
    data_dir = harness.CORPORA[corpus]["data"]
    out: set[str] = set()
    for f in data_dir.glob("*.docx"):
        if f.name.startswith("~$"):
            continue
        out |= {w for w in tokenize(f.stem.replace("_", " ")) if len(w) > 2}
    return out


def _expand(terms: set[str], *, numerals: bool = False,
            drop: set[str] | None = None) -> set[str]:
    out: set[str] = set()
    for t in terms:
        out |= {w for w in tokenize(t) if len(w) > 2}
        if numerals:
            # Figures are excluded from the sufficiency focus (a number in the
            # question is what is being asked ABOUT), but for conflict detection
            # they are often the most specific shared anchor two documents have:
            # a superseded policy and its replacement may share little except
            # the year they refer to.
            out |= set(_NUM_RE.findall(t))
    return out - (drop or set())


def _shared(p: dict, allowed: set[str]) -> bool:
    if not allowed:
        return True
    a, b = stems(p["span_a"]), stems(p["span_b"])
    return any(matches(t, a) and matches(t, b) for t in allowed)


def score(corpus: str, selector, *, numerals: bool = False,
          drop_source_names: bool = False) -> dict:
    stats = CorpusStats.load(HERE / "corpus_stats" / f"corpus{corpus}.json")
    data = json.loads((HERE / "pairs" / f"corpus{corpus}.json").read_text(encoding="utf-8"))
    drop = source_name_terms(corpus) if drop_source_names else set()
    flagged, tp, false_ids, missed = 0, 0, [], []
    for rec in data:
        terms = _expand(validation._query_content_terms(rec["processed"]),
                        numerals=numerals, drop=drop)
        allowed = selector(terms, stats)
        fired = any(base_prongs(p) and _shared(p, allowed) for p in rec["pairs"])
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


def rank_selector(keep: float):
    def sel(terms: set[str], stats: CorpusStats) -> set[str]:
        if not terms:
            return set()
        ranked = sorted(terms, key=lambda t: (-stats.idf(t), t))
        return set(ranked[:max(1, round(len(ranked) * keep))])
    return sel


def ratio_selector(tau: float):
    def sel(terms: set[str], stats: CorpusStats) -> set[str]:
        if not terms:
            return set()
        top = max(stats.idf(t) for t in terms)
        return {t for t in terms if stats.idf(t) >= tau * top}
    return sel


def main() -> None:
    out: dict = {}
    print(f"{'rule':>14} | {'corpus 1: P     R     F1':<28} | corpus 2: P     R     F1")
    print("-" * 78)
    rows = ([("all_terms", lambda t, s: t)]
            + [(f"rank{k:.1f}", rank_selector(k)) for k in (0.4, 0.5, 0.6, 0.7, 0.8)]
            + [(f"ratio{t:.2f}", ratio_selector(t)) for t in (0.4, 0.5, 0.6)])
    # Each setting is also scored with the two structural term-set corrections
    # (numerals admitted, source-name words removed) to separate "the rule is
    # wrong" from "the rule was reading the wrong words".
    variants = [("", {}), ("+num", {"numerals": True}),
                ("+num-src", {"numerals": True, "drop_source_names": True})]
    for name, sel in rows:
      for suffix, kw in variants:
        r1, r2 = score("1", sel, **kw), score("2", sel, **kw)
        name = f"{name}{suffix}"
        out[name] = {"1": r1, "2": r2}
        print(f"{name:>16} | P={r1['precision']:.3f} R={r1['recall']:.3f} F1={r1['f1']:.3f} "
              f"flag={r1['flagged']:>2} | P={r2['precision']:.3f} R={r2['recall']:.3f} "
              f"F1={r2['f1']:.3f} flag={r2['flagged']:>2}")

    print("\nmissed true conflicts per setting:")
    for name in out:
        print(f"  {name:>14}  c1={out[name]['1']['missed']}  c2={out[name]['2']['missed']}")

    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / "conflict_sweep.json").write_text(json.dumps(out, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
