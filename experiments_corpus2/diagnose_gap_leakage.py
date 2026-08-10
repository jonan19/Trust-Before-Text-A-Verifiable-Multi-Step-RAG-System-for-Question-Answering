"""
diagnose_gap_leakage.py — READ-ONLY diagnosis of the 4 Corpus-2 gap-query
leaks (Q017, Q050, Q055, Q078).

Question: the Stage-5 sufficiency gate is a disjunction
    H2: avg score >= MIN_AVG_SCORE_FOR_SUFFICIENCY (0.65)
      OR
    H4: coverage  >= MIN_QUERY_COVERAGE (0.55)
For each leaked query, WHICH branch passed?

This script changes nothing. It does not import-and-mutate any threshold and
does not edit validation.py / orchestrator.py / synthesis.py. It replays the
exact pipeline path orchestrator.run() takes for these queries (preprocess ->
classify -> decompose -> retrieve -> validation stages 1-3 -> stage 5) and
re-derives the two sufficiency signals with the SAME expressions
check_sufficiency() uses, so the printed numbers are the ones the frozen gate
actually saw.

Retrieval is pointed at qdrant_db_corpus2 with the same functools.partial
monkeypatch our_decisions_corpus2.py uses. Decision-layer only: zero LLM tokens.

Usage:
    python experiments_corpus2/diagnose_gap_leakage.py
"""

from __future__ import annotations

import functools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import qdrant_retrieval          # noqa: E402
import retrieval_interface       # noqa: E402

CORPUS2_QDRANT_DIR = "qdrant_db_corpus2"
retrieval_interface._qdrant_retrieve = functools.partial(
    qdrant_retrieval.retrieve, qdrant_dir=CORPUS2_QDRANT_DIR
)

import orchestrator  # noqa: E402
import validation as V  # noqa: E402

# Stub synthesis: the decision is made before synthesis, so this only avoids a
# network call. (Same stub as our_decisions_corpus2.py.)
orchestrator.synthesize = lambda **kw: {  # type: ignore[assignment]
    "answer": "(synthesis skipped)", "status": "ok", "reason": None, "citations": [],
}

DATA = ROOT / "data_corpus2"
OUT_JSON = ROOT / "experiments_corpus2" / "gap_leakage_diagnosis.json"

LEAKED = ["Q017", "Q050", "Q055", "Q078"]
# Two gap queries the system got RIGHT, as controls — a diagnosis that cannot
# distinguish leaked from non-leaked gap queries would not be worth much.
CONTROLS = ["Q016", "Q049"]


def replay(raw_query: str) -> dict:
    """Replay orchestrator.run()'s attempt-1 path and expose Stage-5 internals.

    Mirrors orchestrator.run() lines: preprocess -> classify -> decompose ->
    dynamic top_k -> retrieve_for_queries -> validate(chunks, processed_query).
    None of the 78 Corpus-2 queries names a document file, so the
    source-targeting branch never fires (verified: target_source is None).
    """
    processed = orchestrator.preprocess_query(raw_query)
    qtype = orchestrator.classify_query(processed)
    subs = (orchestrator.decompose_query(processed)
            if qtype == "complex" else [processed])
    top_k = (
        orchestrator.RETRIEVAL_TOP_K + len(subs)
        if qtype == "complex" and len(subs) > 1
        else orchestrator.RETRIEVAL_TOP_K
    )
    raw_chunks = orchestrator.retrieve_for_queries(subs, top_k=top_k)
    target_source = orchestrator._extract_target_source(processed, raw_chunks)

    # ── Replay validation stages 1-3 exactly as validate() does ──────────────
    stage1 = V.normalize_chunks(raw_chunks)
    stage2 = V.remove_duplicates(stage1)
    stage3 = V.filter_by_relevance(stage2, processed)

    # ── Re-derive the Stage-5 signals with check_sufficiency()'s expressions ─
    scores = [c.get("score", 0.0) for c in stage3]
    avg_score = (sum(scores) / len(scores)) if scores else 0.0
    coverage = V._query_coverage(processed, stage3) if processed.strip() else 1.0

    h1_pass = len(stage3) >= V.MIN_CHUNKS_FOR_SUFFICIENCY
    h3_pass = any(c.get("relevance_score", 1.0) > V.MIN_RELEVANCE_SCORE
                  for c in stage3)
    h2_pass = avg_score >= V.MIN_AVG_SCORE_FOR_SUFFICIENCY
    h4_pass = coverage >= V.MIN_QUERY_COVERAGE

    # Which content terms did/didn't appear in the evidence (drives H4)?
    raw_tokens = {w.lower().strip(".,;:?!'\"()") for w in processed.split()}
    tokens = {t for t in raw_tokens
              if not any(t.endswith(ext) for ext in V._FILE_EXTENSIONS)}
    content_terms = {t for t in (tokens - V._COVERAGE_STOPWORDS) if t}
    evidence_text = " ".join(c.get("text", "").lower() for c in stage3)
    covered = sorted(t for t in content_terms if t in evidence_text)
    missed = sorted(t for t in content_terms if t not in evidence_text)

    # ── Ground truth: what the frozen system actually decided ────────────────
    full = orchestrator.run(raw_query, verbose=False)
    dec = full.get("decision")
    reason = (full.get("validation") or {}).get("abstention_reason")
    observed = "answer" if dec == "proceed" else (
        "conflict" if reason == "conflict" else "insufficient")

    return {
        "processed_query": processed,
        "query_type": qtype,
        "sub_queries": subs,
        "top_k": top_k,
        "target_source": target_source,
        "n_retrieved": len(raw_chunks),
        "n_stage3_relevant": len(stage3),
        "avg_score": round(avg_score, 4),
        "coverage": round(coverage, 4),
        "MIN_AVG_SCORE_FOR_SUFFICIENCY": V.MIN_AVG_SCORE_FOR_SUFFICIENCY,
        "MIN_QUERY_COVERAGE": V.MIN_QUERY_COVERAGE,
        "H1_min_chunks_pass": h1_pass,
        "H3_relevance_floor_pass": h3_pass,
        "H2_avg_score_pass": h2_pass,
        "H4_coverage_pass": h4_pass,
        "branch": ("BOTH" if h2_pass and h4_pass else
                   "H2 (avg score) only" if h2_pass else
                   "H4 (coverage) only" if h4_pass else
                   "NEITHER (gate failed -> abstain)"),
        "sufficiency_flag": V.check_sufficiency(stage3, query=processed),
        "content_terms": sorted(content_terms),
        "covered_terms": covered,
        "missed_terms": missed,
        "observed_decision": observed,
        "top_chunks": [
            {
                "rank": i,
                "source": c.get("source"),
                "section": c.get("section"),
                "score": round(c.get("score", 0.0), 4),
                "relevance_score": round(c.get("relevance_score", 0.0), 4),
                "text": (c.get("text", "") or "").strip()[:220],
            }
            for i, c in enumerate(
                sorted(stage3, key=lambda x: x.get("score", 0.0), reverse=True)[:5],
                start=1,
            )
        ],
    }


def main() -> None:
    queries = json.load(open(DATA / "queries.json", encoding="utf-8"))["queries"]
    by_id = {q["id"]: q for q in queries}

    out: dict = {}
    for qid in LEAKED + CONTROLS:
        q = by_id[qid]
        label = "LEAKED" if qid in LEAKED else "CONTROL (correctly abstained)"
        print("=" * 78)
        print(f"{qid}  [{label}]  expected={q['expected_decision']}")
        print(f"  query: {q['query']}")
        r = replay(q["query"])
        out[qid] = {"query": q["query"], "expected": q["expected_decision"],
                    "label": label, **r}

        print(f"  observed decision      : {r['observed_decision']}")
        print(f"  retrieved / stage3 rel : {r['n_retrieved']} / {r['n_stage3_relevant']}")
        print(f"  H1 min-chunks          : {r['H1_min_chunks_pass']}")
        print(f"  H3 relevance floor     : {r['H3_relevance_floor_pass']}")
        print(f"  H2 avg score           : {r['avg_score']:.4f} "
              f">= {r['MIN_AVG_SCORE_FOR_SUFFICIENCY']} ? {r['H2_avg_score_pass']}")
        print(f"  H4 coverage            : {r['coverage']:.4f} "
              f">= {r['MIN_QUERY_COVERAGE']} ? {r['H4_coverage_pass']}")
        print(f"  >>> BRANCH THAT PASSED : {r['branch']}")
        print(f"  sufficiency_flag       : {r['sufficiency_flag']}")
        print(f"  covered terms          : {r['covered_terms']}")
        print(f"  missed terms           : {r['missed_terms']}")
        print("  top retrieved chunks:")
        for c in r["top_chunks"]:
            print(f"    #{c['rank']} score={c['score']:.4f} rel={c['relevance_score']:.4f} "
                  f"[{c['source']} / {c['section']}]")
            print(f"        {c['text'][:150]}")
        print()

    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=2)
    print(f"Wrote {OUT_JSON}")

    print("\n" + "=" * 78)
    print("SUMMARY — which branch of the sufficiency OR passed")
    print("=" * 78)
    for qid, r in out.items():
        print(f"  {qid} [{'LEAK' if qid in LEAKED else 'ctrl'}] "
              f"avg={r['avg_score']:.4f} cov={r['coverage']:.4f} "
              f"-> {r['branch']}")


if __name__ == "__main__":
    main()
