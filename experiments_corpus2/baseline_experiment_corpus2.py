"""
baseline_experiment_corpus2.py — Prompted-LLM baseline for Corpus 2 (Ashcombe
Falls University), mirroring experiments/baseline_experiment.py exactly.

Only two things differ from the Corpus-1 script, neither of which touches any
frozen file's logic:
  1. Retrieval is monkeypatched to read from qdrant_db_corpus2/ instead of the
     default qdrant_db/ (same technique as our_decisions_corpus2.py).
  2. Paths point at data_corpus2/ and experiments_corpus2/our_decisions_corpus2.json.

Same design as the original:
  * We do NOT touch validation.py / orchestrator.py / synthesis.py or any
    threshold. This script only reads the frozen system's decisions
    (our_decisions_corpus2.json) and reproduces the retrieval our system
    sees, then calls a real LLM (Groq llama-3.3-70b-versatile).
  * Checkpointed / resumable JSON: re-running the same --out file skips
    already-completed query ids (run protocol rule 2).

Usage:
    python experiments_corpus2/baseline_experiment_corpus2.py --smoke
    python experiments_corpus2/baseline_experiment_corpus2.py --ids Q001,Q005 --runs 5 --temp 0.7
    python experiments_corpus2/baseline_experiment_corpus2.py --all --batch 20
"""

from __future__ import annotations

import argparse
import functools
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

import qdrant_retrieval          # noqa: E402
import retrieval_interface       # noqa: E402

CORPUS2_QDRANT_DIR = "qdrant_db_corpus2"
retrieval_interface._qdrant_retrieve = functools.partial(
    qdrant_retrieval.retrieve, qdrant_dir=CORPUS2_QDRANT_DIR
)

from orchestrator import (  # noqa: E402
    preprocess_query,
    classify_query,
    decompose_query,
    retrieve_for_queries,
    RETRIEVAL_TOP_K,
)

# Reuse the exact Groq calling / key-rotation / parsing / grading machinery
# from the Corpus-1 baseline script instead of duplicating it.
sys.path.insert(0, str(ROOT / "experiments"))
import baseline_experiment as base  # noqa: E402

DATA = ROOT / "data_corpus2"
OUT = ROOT / "experiments_corpus2"
QUERIES_PATH = DATA / "queries.json"
GT_PATH = DATA / "ground_truth.json"
FROZEN_PATH = OUT / "our_decisions_corpus2.json"


def load_frozen_ours() -> dict:
    if not FROZEN_PATH.exists():
        raise RuntimeError(
            f"{FROZEN_PATH} not found. Run "
            "`python experiments_corpus2/our_decisions_corpus2.py --all` first."
        )
    payload = json.load(open(FROZEN_PATH, encoding="utf-8"))
    recs = payload["results"] if isinstance(payload, dict) else payload
    return {r["id"]: r for r in recs}


def retrieve_same_evidence(raw_query: str):
    pq = preprocess_query(raw_query)
    qtype = classify_query(pq)
    subs = decompose_query(pq) if qtype == "complex" else [pq]
    top_k = (
        RETRIEVAL_TOP_K + len(subs)
        if qtype == "complex" and len(subs) > 1
        else RETRIEVAL_TOP_K
    )
    chunks = retrieve_for_queries(subs, top_k=top_k)
    return chunks, subs, qtype


def run_experiment(query_ids, n_hot_runs, hot_temp, max_chunks, checkpoint_path):
    queries = json.load(open(QUERIES_PATH, encoding="utf-8"))["queries"]
    gt = json.load(open(GT_PATH, encoding="utf-8"))
    conflict_key = base.build_conflict_key(gt)
    ours = load_frozen_ours()

    if query_ids:
        queries = [q for q in queries if q["id"] in query_ids]

    results: list[dict] = []
    done_ids: set[str] = set()
    if checkpoint_path and checkpoint_path.exists():
        try:
            prev = json.load(open(checkpoint_path, encoding="utf-8"))
            results = prev.get("results", [])
            done_ids = {r["id"] for r in results}
            if done_ids:
                print(f"Resuming: {len(done_ids)} queries already done, "
                      f"skipping them.\n", flush=True)
        except Exception:
            pass

    def _save_checkpoint():
        if checkpoint_path is None:
            return
        json.dump({"results": results}, open(checkpoint_path, "w", encoding="utf-8"),
                   indent=2)

    n = len(queries)
    stopped_early = False
    for idx, q in enumerate(queries, 1):
        qid = q["id"]
        if qid in done_ids:
            continue
        raw = q["query"]
        expected = q["expected_decision"]
        pair = q.get("expected_conflict_pair")

        chunks, subs, qtype = retrieve_same_evidence(raw)
        context = base.build_context_block(chunks, max_chunks=max_chunks)
        sources = sorted({c.get("source", "unknown") for c in chunks})
        n_sent = len(chunks) if max_chunks is None else min(max_chunks, len(chunks))

        print(f"[{idx}/{n}] {qid} ({expected}) — {len(chunks)} chunks "
              f"(sent {n_sent}), type={qtype}", flush=True)

        try:
            canon_reply = base.call_baseline(context, raw, temperature=0.0)
            canon_dec = base.parse_decision(canon_reply)

            hot_replies, hot_decs = [], []
            for r in range(n_hot_runs):
                rep = base.call_baseline(context, raw, temperature=hot_temp)
                hot_replies.append(rep)
                hot_decs.append(base.parse_decision(rep))
        except base.DailyTokenExhausted as exc:
            print(f"\n[!] Groq daily token cap hit on {qid}. Saving "
                  f"{len(results)} completed queries and stopping.\n    {exc}",
                  flush=True)
            _save_checkpoint()
            stopped_early = True
            break

        inconsistent = len(set(hot_decs)) > 1

        rec = {
            "id": qid,
            "category": q.get("category"),
            "query": raw,
            "expected": expected,
            "expected_conflict_pair": pair,
            "n_chunks": len(chunks),
            "n_chunks_sent": n_sent,
            "retrieved_sources": sources,
            "sub_queries": subs,
            "query_type": qtype,
            "ours_decision": ours.get(qid, {}).get("observed"),
            "ours_conflict_pair": ours.get(qid, {}).get("conflict_pair"),
            "baseline_canonical_decision": canon_dec,
            "baseline_canonical_reply": canon_reply,
            "baseline_hot_decisions": hot_decs,
            "baseline_hot_temp": hot_temp,
            "baseline_inconsistent": inconsistent,
        }

        if expected == "insufficient":
            rec["leakage"] = {
                "canonical_leaked": base.is_concrete_answer(canon_dec),
                "hot_leak_count": sum(base.is_concrete_answer(d) for d in hot_decs),
                "hot_runs": n_hot_runs,
            }

        if expected == "conflict" and pair:
            rec["attribution"] = base.grade_attribution(
                canon_reply, canon_dec, pair, conflict_key
            )

        results.append(rec)
        _save_checkpoint()

    return results, stopped_early


def summarize(results: list[dict]) -> dict:
    return base.summarize(results)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true",
                    help="5-query smoke test (per run protocol)")
    ap.add_argument("--all", action="store_true", help="full 78-query run")
    ap.add_argument("--ids", type=str, default="")
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--temp", type=float, default=0.7)
    ap.add_argument("--max-chunks", type=int, default=12)
    ap.add_argument("--batch", type=int, default=0,
                    help="if >0 with --all, stop after this many NEW queries "
                         "this invocation (run-protocol batching)")
    ap.add_argument("--out", type=str, default="")
    args = ap.parse_args()

    if args.smoke:
        # 1 answer(agreeing), 1 conflict, 1 conflict, 1 insufficient(gap),
        # 1 insufficient(true out-of-scope) — mirrors Corpus 1's smoke mix.
        ids = ["Q001", "Q036", "Q042", "Q016", "Q049"]
        out_name = args.out or "baseline_results_corpus2_smoke.json"
    elif args.all:
        ids = None
        out_name = args.out or "baseline_results_corpus2.json"
    elif args.ids:
        ids = [x.strip() for x in args.ids.split(",") if x.strip()]
        out_name = args.out or "baseline_results_corpus2_custom.json"
    else:
        ap.error("specify --smoke, --all, or --ids")

    max_chunks = None if args.max_chunks == 0 else args.max_chunks
    checkpoint_path = OUT / out_name

    if args.batch and ids is None:
        all_q = json.load(open(QUERIES_PATH, encoding="utf-8"))["queries"]
        done_ids = set()
        if checkpoint_path.exists():
            prev = json.load(open(checkpoint_path, encoding="utf-8"))
            done_ids = {r["id"] for r in prev.get("results", [])}
        todo = [q["id"] for q in all_q if q["id"] not in done_ids][: args.batch]
        ids = list(done_ids) + todo  # keep done + this batch's new ones

    print(f"Model  : {base.GROQ_MODEL}  |  consistency runs: {args.runs} @ temp {args.temp}")
    print(f"Groq keys detected: {base.n_keys()} (rotating)")
    print(f"Context cap: {max_chunks if max_chunks else 'all'} passages/call")
    print(f"Checkpoint/out: {checkpoint_path}  (re-run same command to resume)\n")

    t0 = time.time()
    results, stopped_early = run_experiment(
        ids, args.runs, args.temp, max_chunks, checkpoint_path
    )
    summary = summarize(results)
    elapsed = time.time() - t0

    payload = {
        "meta": {
            "model": base.GROQ_MODEL,
            "corpus": "Corpus 2 (Ashcombe Falls University)",
            "consistency_runs": args.runs,
            "consistency_temp": args.temp,
            "canonical_temp": 0.0,
            "max_chunks_sent": max_chunks,
            "n_queries": len(results),
            "elapsed_sec": round(elapsed, 1),
            "stopped_early_daily_cap": stopped_early,
        },
        "summary": summary,
        "results": results,
    }
    json.dump(payload, open(checkpoint_path, "w", encoding="utf-8"), indent=2)

    print("\n" + "=" * 60)
    print("SUMMARY" + ("  (PARTIAL — daily token cap hit)" if stopped_early else ""))
    print("=" * 60)
    print(json.dumps(summary, indent=2))
    print(f"\nWrote {checkpoint_path}  ({elapsed:.0f}s, {len(results)} queries done)")
    n_total = 78
    if len(results) < n_total and not stopped_early:
        print(f"\n{len(results)}/{n_total} done. Say 'continue' to run the next "
              f"batch (re-run with --all --batch N).")


if __name__ == "__main__":
    main()
