"""
invariance_harness.py — Metamorphic testing for the decision layer.

Why this exists
---------------
Every number in FIXES_REPORT.md and LIMITATIONS_STATUS.md is measured on 78
hand-authored queries per corpus, against documents and ground truth written by
this project. Both corpora even share a composition (46 answer / 16 insufficient
/ 16 conflict), so the second is closer to a re-skin of the first than to an
independent sample. Worse, Corpus 2 has been used to accept or reject candidate
rules dozens of times across those reports, so it is a training set, not a
held-out one. Nothing in this project is currently held out.

That makes accuracy-style metrics a poor guide. The conflict metrics rest on
n=16, where a single query is 6.25 points, and the failures we can actually
diagnose are not semantic: they are queries landing thousandths away from a
fitted constant (Q038 at 0.5945 against a 0.60 bar; Q017 at 0.6531 against 0.65).

This harness measures something that needs no new ground truth and does not
saturate: **invariance**. Each transform below is semantically neutral by
construction. It changes the form of the input, never what is being asked or
what the corpus says, so a correct system must return the same decision. Every
violation is therefore a genuine defect rather than a threshold near-miss, and
finding more of them does not require authoring more queries.

The approach is not new to this project. L4's 48 adversarial probes and L6's
fabricated-evidence test already work this way, which is exactly why they are
its strongest results: 0/48 and 0/4 are structural properties, not sample
statistics.

Transforms are applied at the RETRIEVAL BOUNDARY, so the whole real pipeline
runs behind them (sub-query decomposition, Stages 0-7, the conflict retry)
rather than a reimplementation of it.

    python evaluation/invariance_harness.py --corpus 1
    python evaluation/invariance_harness.py --corpus 2 --transforms permute,duplicate

Zero LLM tokens.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

import harness_bootstrap  # noqa: F401  (adds this dir to sys.path)
from harness import CORPORA, decision_of, load_queries, setup

OUT_DIR = Path(__file__).resolve().parent / "results"
SEED = 20260819


# ---------------------------------------------------------------------------
# Evidence transforms — applied to the chunk list the retriever returns.
# Each must leave the EVIDENCE CONTENT semantically unchanged.
# ---------------------------------------------------------------------------

def t_permute(chunks: list[dict], query: str, ctx: dict) -> list[dict]:
    """
    Reorder the retrieved evidence.

    Retrieval returns a set of chunks that the pipeline re-sorts by score
    anyway, so order carries no information and no decision may depend on it.
    `find_conflict` returns the FIRST contradicting pair it encounters and
    derives its rank cutoff from list position, so this is a direct test of
    whether those are order-stable.
    """
    out = list(chunks)
    random.Random(SEED + len(out)).shuffle(out)
    return out


def t_duplicate(chunks: list[dict], query: str, ctx: dict) -> list[dict]:
    """
    Present every chunk twice.

    Stage 2 deduplication exists precisely to make this a no-op. It is also a
    test of whether any decision rides on the NUMBER of chunks rather than on
    what they say: `MIN_CHUNKS_FOR_AVG_SUFFICIENCY` and
    `MAX_CONFLICT_EVIDENCE_RANK` both count chunks, so a rule that leaks
    chunk-count sensitivity will fail here.
    """
    return [dict(c) for c in chunks] + [dict(c) for c in chunks]


def t_distractor(chunks: list[dict], query: str, ctx: dict) -> list[dict]:
    """
    Append genuine but off-topic evidence from the same corpus.

    Distractors are drawn from the corpus's OWN chunks (the lowest-scoring
    results for an unrelated probe query), so they carry valid provenance
    fingerprints and survive Stage 0. A cross-corpus distractor would be
    rejected by provenance and make the test vacuous.

    Adding irrelevant evidence must never change a decision, and in particular
    must never turn an abstention into an answer. That direction is tracked
    separately below as a safety regression.
    """
    pool = ctx.get("distractor_pool") or []
    return list(chunks) + [dict(c) for c in pool[:2]]


EVIDENCE_TRANSFORMS = {
    "permute": t_permute,
    "duplicate": t_duplicate,
    "distractor": t_distractor,
}

# ---------------------------------------------------------------------------
# Query transforms — surface form only, never the question being asked.
# ---------------------------------------------------------------------------

QUERY_TRANSFORMS = {
    # Matching is case-folded throughout the pipeline, so case must not matter.
    "query_lower": lambda q: q.lower(),
    # A politeness token adds no content. It does add a token to the query
    # coverage DENOMINATOR, so a coverage rule that weighs every word equally
    # will drift under it.
    "query_thanks": lambda q: q.rstrip() + " Thanks!",
    "query_polite": lambda q: "Could you tell me: " + q[0].lower() + q[1:],
}

ALL_TRANSFORMS = list(EVIDENCE_TRANSFORMS) + list(QUERY_TRANSFORMS)


def _build_distractor_pool(base_retrieve, corpus: str) -> list[dict]:
    """Lowest-scoring chunks for a probe deliberately unrelated to the query set."""
    probe = ("fire evacuation drill frequency and first aider ratio"
             if corpus == "2" else
             "library book late return fine and campus parking permit")
    got = base_retrieve(probe, top_k=8)
    return sorted(got, key=lambda c: c.get("score", 0.0))[:4]


def run_one(orchestrator, queries, *, transform_name, base_retrieve, ctx):
    """Run the full query set under one transform; return {query_id: decision}."""
    import retrieval_interface as ri

    q_fn = QUERY_TRANSFORMS.get(transform_name)
    e_fn = EVIDENCE_TRANSFORMS.get(transform_name)

    if e_fn is not None:
        def wrapped(query, top_k=5, **kw):
            return e_fn(base_retrieve(query, top_k=top_k, **kw), query, ctx)
        ri._qdrant_retrieve = wrapped
    else:
        ri._qdrant_retrieve = base_retrieve

    out = {}
    for q in queries:
        text = q_fn(q["query"]) if q_fn else q["query"]
        out[q["id"]] = decision_of(orchestrator.run(text, verbose=False))
    ri._qdrant_retrieve = base_retrieve
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", choices=sorted(CORPORA), required=True)
    ap.add_argument("--transforms", default=",".join(ALL_TRANSFORMS))
    ap.add_argument("--tag", default="invariance")
    args = ap.parse_args()

    wanted = [t.strip() for t in args.transforms.split(",") if t.strip()]
    bad = [t for t in wanted if t not in ALL_TRANSFORMS]
    if bad:
        raise SystemExit(f"unknown transform(s): {bad}\navailable: {ALL_TRANSFORMS}")

    orchestrator = setup(args.corpus)
    queries = load_queries(args.corpus)

    import retrieval_interface as ri
    base_retrieve = ri._qdrant_retrieve
    ctx = {"distractor_pool": _build_distractor_pool(base_retrieve, args.corpus)}

    expected = {q["id"]: q["expected_decision"] for q in queries}

    t0 = time.time()
    print(f"baseline ({len(queries)} queries) ...", flush=True)
    baseline = run_one(orchestrator, queries, transform_name="__none__",
                       base_retrieve=base_retrieve, ctx=ctx)

    report = {"corpus": args.corpus, "n": len(queries), "transforms": {}}

    for name in wanted:
        print(f"transform {name} ...", flush=True)
        got = run_one(orchestrator, queries, transform_name=name,
                      base_retrieve=base_retrieve, ctx=ctx)
        violations = []
        for qid, before in baseline.items():
            after = got[qid]
            if before == after:
                continue
            violations.append({
                "id": qid,
                "expected": expected[qid],
                "baseline": before,
                "perturbed": after,
                # The direction that matters: an abstention that became an
                # answer has produced text the unperturbed system refused to.
                "safety_regression": (before in ("conflict", "insufficient")
                                      and after == "answer"),
            })
        unsafe = [v for v in violations if v["safety_regression"]]
        report["transforms"][name] = {
            "violations": len(violations),
            "violation_rate": round(len(violations) / len(queries), 4),
            "safety_regressions": len(unsafe),
            "detail": violations,
        }
        print(f"    {len(violations)}/{len(queries)} decisions changed "
              f"({len(unsafe)} of them abstain -> answer)", flush=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{args.tag}_corpus{args.corpus}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"\n=== invariance / corpus {args.corpus} "
          f"({round(time.time() - t0, 1)}s) ===")
    print(f"{'transform':<16} {'changed':>9} {'rate':>8} {'abstain->answer':>17}")
    for name in wanted:
        r = report["transforms"][name]
        print(f"{name:<16} {r['violations']:>9} {r['violation_rate']:>8} "
              f"{r['safety_regressions']:>17}")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
