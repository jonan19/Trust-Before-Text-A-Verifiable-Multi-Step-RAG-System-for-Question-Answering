"""
pair_lab.py — Build a pair-level feature table for every conflict candidate the
Stage-4 detector would consider, on both corpora.

Why: Limitation 1 (false conflicts from query-irrelevant pairs) is a rule-design
problem, and every candidate rule otherwise costs a full NLI re-run to evaluate.
Here the expensive parts (NLI both directions, embeddings) are computed ONCE per
pair and cached; rule ideas are then evaluated instantly over the table.

    python evaluation/pair_lab.py --build --corpus 1
    python evaluation/pair_lab.py --build --corpus 2

Output: evaluation/pairs/corpus<N>.json
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import harness_bootstrap  # noqa: F401
import validation

HERE = Path(__file__).resolve().parent
STAGE3 = HERE / "stage3"
PAIRS = HERE / "pairs"


def _tokens(text: str) -> set[str]:
    return {w.lower().strip(".,;:?!'\"()[]") for w in text.split()}


def _nli_scores(a: str, b: str) -> dict:
    model = validation._get_nli_model()
    if model is None:
        return {}
    ab = model.predict([(a, b)], apply_softmax=True)[0]
    ba = model.predict([(b, a)], apply_softmax=True)[0]
    return {
        "nli_contra_ab": round(float(ab[0]), 6),
        "nli_contra_ba": round(float(ba[0]), 6),
        "nli_entail_ab": round(float(ab[1]), 6),
        "nli_entail_ba": round(float(ba[1]), 6),
        "nli_neutral_ab": round(float(ab[2]), 6),
        "nli_neutral_ba": round(float(ba[2]), 6),
    }


def build(corpus: str) -> None:
    records = json.loads((STAGE3 / f"corpus{corpus}.json").read_text(encoding="utf-8"))
    out: list[dict] = []

    for qi, rec in enumerate(records, 1):
        query = rec["processed"]
        chunks = rec["chunks"]
        content_terms = validation._query_content_terms(query)

        # Document frequency of each query content term within THIS query's
        # retrieved evidence set — the basis for "which query term actually
        # discriminates between these chunks".
        chunk_tokens = [_tokens(c["text"]) for c in chunks]
        df = {t: sum(1 for toks in chunk_tokens if t in toks) for t in content_terms}

        pairs = []
        for i, a in enumerate(chunks):
            for b in chunks[i + 1:]:
                if a["source"] == b["source"] and a["source"] != "unknown":
                    continue
                if (a["relevance_score"] < validation.MIN_CONFLICT_RELEVANCE
                        or b["relevance_score"] < validation.MIN_CONFLICT_RELEVANCE):
                    continue
                span_a = validation._query_relevant_text(a["text"], content_terms)
                span_b = validation._query_relevant_text(b["text"], content_terms)
                if not span_a or not span_b or span_a == span_b:
                    continue

                sim = validation.compute_chunk_similarity(span_a, span_b)
                toks_a, toks_b = _tokens(span_a), _tokens(span_b)
                shared_terms = sorted((toks_a & toks_b) & content_terms)

                p = {
                    "src_a": a["source"], "src_b": b["source"],
                    "span_a": span_a, "span_b": span_b,
                    "score_a": a["score"], "score_b": b["score"],
                    "rel_a": a["relevance_score"], "rel_b": b["relevance_score"],
                    "sim": round(sim, 6),
                    "keyword": validation._has_keyword_contradiction(span_a, span_b),
                    "numeric": validation._has_numeric_contradiction(span_a, span_b),
                    "terms_a": sorted(toks_a & content_terms),
                    "terms_b": sorted(toks_b & content_terms),
                    "shared_terms": shared_terms,
                    "qsim_a": round(validation._query_span_similarity(query, span_a), 6),
                    "qsim_b": round(validation._query_span_similarity(query, span_b), 6),
                }
                if sim >= validation.NLI_SIM_FLOOR:
                    p.update(_nli_scores(span_a, span_b))
                pairs.append(p)

        out.append({
            "id": rec["id"], "query": rec["query"], "processed": query,
            "expected": rec["expected"], "category": rec["category"],
            "content_terms": sorted(content_terms),
            "term_df": df, "n_chunks": len(chunks),
            "chunk_scores": [c["score"] for c in chunks],
            "chunk_texts": [c["text"] for c in chunks],
            "chunk_sources": [c["source"] for c in chunks],
            "pairs": pairs,
        })
        print(f"[{qi}/{len(records)}] {rec['id']}  {len(pairs)} pairs", flush=True)

    PAIRS.mkdir(parents=True, exist_ok=True)
    path = PAIRS / f"corpus{corpus}.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--corpus", choices=["1", "2"], required=True)
    args = ap.parse_args()
    if args.build:
        build(args.corpus)
