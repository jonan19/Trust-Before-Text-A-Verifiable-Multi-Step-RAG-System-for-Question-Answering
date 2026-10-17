"""
answerhood_lab.py — Offline separation study for a query-conditioned
answerhood signal (Plan: "Answer-Anchored Relevance Gating", Phase 1).

Question: can a cross-encoder answerhood score do what the bi-encoder
topicality gate (QUERY_SPAN_RELEVANCE, validation.py:290) could not — separate
Stage 4's TRUE conflict pairs from its FALSE ones? Companion to and modelled
on analyze_span_relevance.py, which established the bi-encoder gate fails this
test on Corpus 2. This script computes the same acceptance test for a
cross-encoder margin, side by side with the existing bi-encoder numbers, and
touches NO live code — validation.py is read, never modified.

For every query, this script:
  1. Replays the orchestrator's attempt-1 evidence path through Stage 3 with
     the score floor DISABLED (apply_score_floor=False) — this is
     `stage3_wide`, what find_conflict() actually receives in validate()
     (validation.py:2051), NOT the score-floored dump in evaluation/stage3/,
     which predates the Stage4/Stage5 evidence-set split (see docs/STATUS.md,
     "The Stage-3 score floor was silently destroying conflicts").
  2. Calls the REAL validation.find_conflict() on that evidence — not a
     reimplementation, so every existing gate (rank cutoff, MIN_CONFLICT_
     RELEVANCE, sentence extraction, anchor test, QUERY_SPAN_RELEVANCE,
     assertive-span/dimensional veto, NLI) runs exactly as in production.
  3. For the query's full candidate sentence pool (every sentence surviving
     _query_relevant_sentences() over stage3_wide, deduplicated), scores
     query-vs-sentence answerhood with cross-encoder/ms-marco-MiniLM-L-6-v2
     and computes each sentence's MARGIN to that query's own top-1 score —
     the corpus-independent form the plan specifies (validation.py:1538-1541,
     RANK_TIE_EPSILON note at :276-289, applied here to a continuous score
     instead of a rank position).
  4. If find_conflict reported a pair, records both spans' margins alongside
     the existing bi-encoder qsim (_query_span_similarity) for direct
     comparison.

    python evaluation/answerhood_lab.py --corpus 1
    python evaluation/answerhood_lab.py --corpus 2
    python evaluation/answerhood_lab.py --corpus 1 --corpus 2   # both + verdict

Output: evaluation/results/answerhood_lab_corpus<N>.json, plus a printed
go/no-go verdict per the plan's stated acceptance test:

    "a usable gate exists only if there is a margin delta such that every
    true-conflict pair on BOTH corpora has max(margin_a, margin_b) <= delta
    while a majority of the false-conflict pairs exceed it."
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import harness_bootstrap  # noqa: F401
import harness
import validation

RESULTS = Path(__file__).resolve().parent / "results"

_CROSS_ENCODER_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_cross_encoder = None


def _get_cross_encoder():
    global _cross_encoder
    if _cross_encoder is None:
        from sentence_transformers import CrossEncoder
        print(f"Loading {_CROSS_ENCODER_NAME} (first use)...")
        _cross_encoder = CrossEncoder(_CROSS_ENCODER_NAME)
    return _cross_encoder


def _stage3_wide_for(orchestrator, query: str) -> tuple[str, list[dict]]:
    """
    Replay orchestrator.run's attempt-1 evidence path with NO Stage-3 score
    floor — the exact evidence set find_conflict() sees in production
    (validate()'s `stage3_wide`, validation.py:2051), which dump_stage3.py's
    frozen dump does NOT reproduce (it applies the floor). Otherwise identical
    to dump_stage3.stage3_for.
    """
    processed = orchestrator.preprocess_query(query)
    qtype = orchestrator.classify_query(processed)
    subs = orchestrator.decompose_query(processed) if qtype == "complex" else [processed]
    top_k = (orchestrator.RETRIEVAL_TOP_K + len(subs)
             if qtype == "complex" and len(subs) > 1 else orchestrator.RETRIEVAL_TOP_K)

    raw = orchestrator.retrieve_for_queries(subs, top_k=top_k)
    target = orchestrator._extract_target_source(processed, raw)
    if target:
        filtered = [c for c in raw if c.get("source") == target]
        raw = filtered if filtered else raw

    s1 = validation.normalize_chunks(raw)
    s2 = validation.remove_duplicates(s1)
    s3_wide = validation.filter_by_relevance(s2, processed, apply_score_floor=False)
    return processed, s3_wide


def _candidate_pool(chunks: list[dict], content_terms: set[str]) -> list[str]:
    """
    Every sentence find_conflict() would consider comparing, deduplicated.
    Mirrors find_conflict()'s own guards (MIN_CONFLICT_RELEVANCE, then
    _query_relevant_sentences) so the pool matches what the detector actually
    looks at, not just what retrieval returned.
    """
    seen: dict[str, None] = {}
    for c in chunks:
        rel = c.get("relevance_score", c.get("score", 0.0))
        if rel < validation.MIN_CONFLICT_RELEVANCE:
            continue
        for sent in validation._query_relevant_sentences(c.get("text", ""), content_terms):
            seen.setdefault(sent, None)
    return list(seen.keys())


def _margins(query: str, pool: list[str]) -> dict[str, float]:
    """Cross-encoder answerhood margin to this query's own top-1 score."""
    if not pool:
        return {}
    model = _get_cross_encoder()
    raw = model.predict([(query, s) for s in pool])
    top1 = float(max(raw))
    return {s: round(top1 - float(r), 6) for s, r in zip(pool, raw)}


def build(corpus: str) -> list[dict]:
    orchestrator = harness.setup(corpus)
    queries = harness.load_queries(corpus)

    out: list[dict] = []
    for i, q in enumerate(queries, 1):
        processed, chunks = _stage3_wide_for(orchestrator, q["query"])
        detail = validation.find_conflict(chunks, query=processed)

        content_terms = validation._query_content_terms(processed)
        pool = _candidate_pool(chunks, content_terms)
        margins = _margins(processed, pool)

        row: dict = {
            "id": q["id"],
            "category": q.get("category"),
            "query": q["query"],
            "expected": q["expected_decision"],
            "expected_conflict_pair": q.get("expected_conflict_pair"),
            "true_conflict": q["expected_decision"] == "conflict",
            "n_chunks": len(chunks),
            "pool_size": len(pool),
            "reported": detail is not None,
        }

        if detail is not None:
            span_a, span_b = detail["chunks"][0]["text"], detail["chunks"][1]["text"]
            src_a, src_b = detail["chunks"][0]["source"], detail["chunks"][1]["source"]
            margin_a = margins.get(span_a)
            margin_b = margins.get(span_b)
            qsim_a = validation._query_span_similarity(processed, span_a)
            qsim_b = validation._query_span_similarity(processed, span_b)
            row.update({
                "kind": detail["kind"],
                "src_a": src_a, "src_b": src_b,
                "span_a": span_a, "span_b": span_b,
                "qsim_a": round(qsim_a, 6),
                "qsim_b": round(qsim_b, 6),
                "margin_a": margin_a,
                "margin_b": margin_b,
                "max_margin": (max(margin_a, margin_b)
                               if margin_a is not None and margin_b is not None else None),
                "min_qsim": round(min(qsim_a, qsim_b), 6),
            })

        out.append(row)
        status = "CONFLICT" if detail is not None else "clean   "
        true_mark = "Y" if row["true_conflict"] else "n"
        print(f"[{i}/{len(queries)}] {q['id']}  {status}  true={true_mark}  "
              f"pool={len(pool)}", flush=True)

    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"answerhood_lab_corpus{corpus}.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {path}")
    return out


def verdict(rows_by_corpus: dict[str, list[dict]]) -> None:
    """
    The plan's stated go/no-go, printed for both corpora together.

    A usable margin gate exists only if some delta separates every
    true-conflict reported pair (max_margin <= delta, BOTH corpora) from a
    MAJORITY of the false-conflict reported pairs (max_margin > delta).

    Attribution-aware (claude.md failure pattern #3, "right decision, wrong
    evidence"): a report whose DECISION matches gold (true_conflict) but whose
    reported source pair does NOT match expected_conflict_pair is not a
    genuine answerhood-positive — the cited evidence is exactly as
    query-irrelevant as a false conflict's, it just happens to share a verdict
    with a real conflict elsewhere. It is moved into the false population
    rather than the true one, and reported separately so the effect is
    visible. This is the same distinction Phase 0's harness.metrics() now
    grades explicitly.
    """
    print("\n" + "=" * 72)
    print("GO/NO-GO -- cross-encoder answerhood margin vs. bi-encoder qsim")
    print("=" * 72)

    all_true: list[tuple[str, str, float, float]] = []
    all_false: list[tuple[str, str, float, float]] = []
    misattributed: list[tuple[str, str, float, float]] = []
    for corpus, rows in rows_by_corpus.items():
        reported = [r for r in rows if r["reported"] and r.get("max_margin") is not None]
        for r in reported:
            entry = (corpus, r["id"], r["max_margin"], r["min_qsim"])
            exp = r.get("expected_conflict_pair")
            attributed = bool(exp) and sorted([r["src_a"], r["src_b"]]) == sorted(exp)
            if r["true_conflict"] and attributed:
                all_true.append(entry)
            elif r["true_conflict"] and not attributed:
                misattributed.append(entry)
                all_false.append(entry)
            else:
                all_false.append(entry)

    if misattributed:
        print(f"\nMisattributed (\"right decision, wrong evidence\") -- correct verdict, "
              f"but the reported pair is NOT queries.json's expected_conflict_pair. Counted "
              f"below as FALSE-evidence, not true-conflict, even though the decision matched "
              f"gold (n={len(misattributed)}):")
        for c, qid, m, qs in misattributed:
            print(f"    C{c} {qid}  max_margin={m:.4f}  min_qsim={qs:.4f}")

    if not all_true:
        print("No true-conflict pairs were reported at all -- cannot evaluate. STOP.")
        return

    delta = max(m for _, _, m, _ in all_true)
    print(f"\nTrue-conflict reported pairs (n={len(all_true)}), sorted by max_margin:")
    for c, qid, m, qs in sorted(all_true, key=lambda t: -t[2]):
        print(f"    C{c} {qid}  max_margin={m:.4f}  min_qsim={qs:.4f}")
    print(f"\n=> delta (tightest bound covering ALL true conflicts) = {delta:.4f}")

    print(f"\nFalse-conflict reported pairs (n={len(all_false)}), sorted by max_margin:")
    for c, qid, m, qs in sorted(all_false, key=lambda t: -t[2]):
        print(f"    C{c} {qid}  max_margin={m:.4f}  min_qsim={qs:.4f}")

    above = [e for e in all_false if e[2] > delta]
    print(f"\nAt delta={delta:.4f}: {len(above)}/{len(all_false)} false-conflict pairs "
          f"exceed it (would be suppressed).")

    print("\nFor comparison, the bi-encoder qsim signal at the same true-conflict-covering "
          "bound (min_qsim floor = lowest true-conflict min_qsim):")
    qsim_floor = min(qs for _, _, _, qs in all_true)
    qsim_above = [e for e in all_false if e[3] < qsim_floor]
    print(f"    qsim_floor={qsim_floor:.4f}  ->  "
          f"{len(qsim_above)}/{len(all_false)} false-conflict pairs fall below it "
          f"(would be suppressed)")

    if len(all_false) == 0:
        print("\nVERDICT: no false conflicts were reported under this run -- nothing to "
              "separate. Re-check retrieval cache / config against docs/STATUS.md's "
              "current numbers before concluding anything.")
    elif len(above) > len(all_false) / 2:
        print(f"\nVERDICT: GO. delta={delta:.4f} covers all {len(all_true)} true conflicts "
              f"and suppresses a majority ({len(above)}/{len(all_false)}) of false ones. "
              "Proceed to Plan Phase 2.")
    else:
        print(f"\nVERDICT: NO-GO. Only {len(above)}/{len(all_false)} false conflicts would "
              "be suppressed at the delta required to keep every true conflict. The margin "
              "does not separate the classes on this data. Proceed to Plan Phase 4 "
              "(write up as a falsified candidate).")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", choices=["1", "2"], action="append", required=True,
                     help="repeatable; pass twice to run both and print the joint verdict")
    args = ap.parse_args()
    corpora = list(dict.fromkeys(args.corpus))  # de-dupe, preserve order

    rows_by_corpus = {c: build(c) for c in corpora}
    if len(corpora) > 1:
        verdict(rows_by_corpus)


if __name__ == "__main__":
    main()
