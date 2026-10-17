"""
focus_suff_lab.py — Evaluate the focus-term idea as a sufficiency requirement
(Limitation 3), offline, on both corpora at once.

Question: does "the evidence must mention what the question is actually about"
separate genuine gap queries from answerable ones better than the calibrated
average-score threshold that failed to transfer?

Rules compared (all keep H1/H3 unchanged):
  current    (h2 or h4)                       -- shipped
  paired     (h2 and n>=2) or h4              -- structural, from sufficiency_lab
  focus_any  ((h2 or h4) and >=1 focus term in evidence)
  focus_all  ((h2 or h4) and every focus term in evidence)
  focus_only (>=1 focus term in evidence)     -- focus replaces both branches

    python evaluation/focus_suff_lab.py
"""

from __future__ import annotations

import json
from pathlib import Path

import harness_bootstrap  # noqa: F401
import validation
from focus import CorpusStats, focus_terms, stems

HERE = Path(__file__).resolve().parent


def evaluate(keep: float = 0.5) -> dict:
    out: dict = {}
    for corpus in ("1", "2"):
        stats = CorpusStats.load(HERE / "corpus_stats" / f"corpus{corpus}.json")
        records = json.loads((HERE / "stage3" / f"corpus{corpus}.json").read_text(encoding="utf-8"))

        rows = []
        for rec in records:
            chunks = rec["chunks"]
            scores = [c["score"] for c in chunks]
            avg = sum(scores) / len(scores) if scores else 0.0
            cov = validation._query_coverage(rec["processed"], chunks) if chunks else 1.0
            h1 = len(chunks) >= validation.MIN_CHUNKS_FOR_SUFFICIENCY
            h3 = any(c["relevance_score"] > validation.MIN_RELEVANCE_SCORE for c in chunks)
            h2 = avg >= validation.MIN_AVG_SCORE_FOR_SUFFICIENCY
            h4 = cov >= validation.MIN_QUERY_COVERAGE

            terms = validation._query_content_terms(rec["processed"])
            # Morphology-invariant coverage: same threshold, same content terms,
            # but "claims submitted" now counts as covering "claim submitting".
            # Word-form mismatch is not evidence of a gap.
            ev_stems: set[str] = set()
            for c in chunks:
                ev_stems |= stems(c["text"])
            q_stems = {s for t in terms for s in stems(t)}
            cov_stem = (round(len({s for s in q_stems if s in ev_stems}) / len(q_stems), 4)
                        if q_stems and chunks else 1.0)
            h4s = cov_stem >= validation.MIN_QUERY_COVERAGE
            foc = focus_terms(terms, stats, keep=keep)
            ev = set()
            for c in chunks:
                ev |= stems(c["text"])
            hit = {t for t in foc if any(s in ev for s in stems(t))}
            f_any = bool(hit) if foc else True
            f_all = (hit == {t for t in foc}) if foc else True

            base = h1 and h3
            rows.append({
                "id": rec["id"], "expected": rec["expected"], "n": len(chunks),
                "avg": round(avg, 4), "cov": cov, "cov_s": cov_stem, "focus": sorted(foc),
                "focus_hit": sorted(hit),
                "current": base and (h2 or h4),
                "paired": base and ((h2 and len(chunks) >= 2) or h4),
                "focus_any": base and (h2 or h4) and f_any,
                "focus_all": base and (h2 or h4) and f_all,
                "focus_only": base and f_any,
                # Focus applied only where the leak actually happens: the
                # average-score branch. Coverage already measures query overlap
                # directly, so guarding H4 with focus would double-count it.
                "h2_focus": base and ((h2 and f_any) or h4),
                "paired_focus": base and ((h2 and len(chunks) >= 2 and f_any) or h4),
                "cov_stem": base and (h2 or h4s),
                "paired_stem": base and ((h2 and len(chunks) >= 2) or h4s),
                "paired_stem_focus": base and ((h2 and len(chunks) >= 2 and f_any) or h4s),
                "stem_only": base and h4s,
            })

        print(f"\n{'=' * 74}\nCorpus {corpus}   (focus = rarest {keep:.0%} of query content terms)\n{'=' * 74}")
        gaps = [r for r in rows if r["expected"] == "insufficient"]
        answers = [r for r in rows if r["expected"] == "answer"]
        for name in ("current", "paired", "focus_any", "focus_all", "focus_only", "h2_focus", "paired_focus", "cov_stem", "paired_stem", "paired_stem_focus", "stem_only"):
            leaks = [r["id"] for r in gaps if r[name]]
            lost = [r["id"] for r in answers if not r[name]]
            print(f"  {name:11} gap leaks {len(leaks)}/{len(gaps)} {str(leaks):<40} "
                  f"answerable blocked {len(lost)}/{len(answers)} {lost}")
            out.setdefault(name, {})[corpus] = {"leaks": leaks, "blocked": lost}

        print("\n  detail — gap queries and their focus terms:")
        for r in gaps:
            print(f"    {r['id']} n={r['n']} avg={r['avg']:.3f} cov={r['cov']:.2f} "
                  f"focus={r['focus']} hit={r['focus_hit']}")
        print("\n  detail — answerable queries missing a focus term:")
        for r in answers:
            if not r["focus_hit"] and r["focus"]:
                print(f"    {r['id']} n={r['n']} avg={r['avg']:.3f} cov={r['cov']:.2f} "
                      f"focus={r['focus']}")
    return out


if __name__ == "__main__":
    res = evaluate()
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / "focus_suff_lab.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
