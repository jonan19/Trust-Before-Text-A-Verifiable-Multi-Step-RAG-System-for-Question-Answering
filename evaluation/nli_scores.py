"""
nli_scores.py — Record the NLI contradiction score of every Stage-4 candidate
pair the current system sends to the NLI prong, per query, on Corpus 1 or 2.

Source for the paper's NLI-separation figure (Fig. 6). Zero LLM tokens: the
harness stubs synthesis and reuses the retrieval cache. The pipeline is not
changed: validation._has_nli_contradiction is wrapped only to record the score
it already computes, and returns exactly what the original returns. As a check,
the run's 78 decisions are compared with the stored current-system run
(evaluation/results/rerun_corpus<N>.json) and any difference is reported.

    python evaluation/nli_scores.py --corpus 1
    python evaluation/nli_scores.py --corpus 2

Writes evaluation/results/nli_scores_corpus<N>.json.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import harness_bootstrap  # noqa: F401
from harness import CORPORA, config_snapshot, load_queries, run_queries, setup
from run_info import run_info

OUT_DIR = Path(__file__).resolve().parent / "results"


def make_recorder(validation, seen: list[dict]):
    """Wrap validation._has_nli_contradiction so each NLI score is appended to `seen`.

    Same computation as the original (both directions, max of the two); the
    original's own verdict is returned unchanged, so no decision can move.
    """
    original = validation._has_nli_contradiction

    def recording(text_a: str, text_b: str) -> bool:
        model = validation._get_nli_model()
        if model is not None:
            ab = model.predict([(text_a, text_b)], apply_softmax=True)[0]
            ba = model.predict([(text_b, text_a)], apply_softmax=True)[0]
            seen.append({"a": text_a, "b": text_b,
                         "score": round(max(float(ab[0]), float(ba[0])), 6)})
        return original(text_a, text_b)

    return recording


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", choices=sorted(CORPORA), required=True)
    args = ap.parse_args()

    orchestrator = setup(args.corpus)
    import validation

    seen: list[dict] = []
    validation._has_nli_contradiction = make_recorder(validation, seen)

    stored_path = OUT_DIR / f"rerun_corpus{args.corpus}.json"
    stored = {r["id"]: r["observed"]
              for r in json.loads(stored_path.read_text(encoding="utf-8"))["results"]}

    out = []
    for q in load_queries(args.corpus):
        seen.clear()
        rec = run_queries(orchestrator, [q], progress=False)[0]
        spans = set(rec.get("conflict_spans") or [])
        reported = [s["score"] for s in seen if spans and {s["a"], s["b"]} == spans]
        out.append({
            "id": rec["id"],
            "expected": rec["expected"],
            "observed": rec["observed"],
            "stored_observed": stored.get(rec["id"]),
            "conflict_kind": rec["conflict_kind"],
            "conflict_pair": rec["conflict_pair"],
            "expected_conflict_pair": rec["expected_conflict_pair"],
            "n_nli_pairs": len(seen),
            "max_nli": max((s["score"] for s in seen), default=None),
            "reported_nli": reported[0] if reported else None,
            "scores": sorted((s["score"] for s in seen), reverse=True),
        })
        print(f"{rec['id']} exp={rec['expected']:<12} got={rec['observed']:<12} "
              f"pairs={len(seen):3d} max={out[-1]['max_nli']}", flush=True)

    same = sum(r["observed"] == r["stored_observed"] for r in out)
    meta = {"corpus": args.corpus, "n": len(out),
            "threshold": validation.NLI_CONFLICT_THRESHOLD,
            "decisions_equal_stored_run": same,
            "stored_run": stored_path.name}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"nli_scores_corpus{args.corpus}.json"
    path.write_text(json.dumps({"meta": meta, "config": config_snapshot(),
                                "run_info": run_info(), "results": out},
                               indent=2), encoding="utf-8")
    print(f"\ndecisions equal to {stored_path.name}: {same}/{len(out)}")
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
