"""
run_eval_ramdocs.py — External benchmark evaluation over RAMDocs (COLM 2025).

RAMDocs (Han et al., "Retrieval-Augmented Generation with Conflicting
Evidence", arXiv:2504.13079, COLM 2025; HanNight/RAMDocs, MIT license) is a
published, peer-reviewed, externally-authored benchmark of 500 test queries.
Each query carries 1-12 documents labeled type: correct | misinfo | noise,
with gold_answers (one or more correct answers — queries can have genuinely
ambiguous entities) and wrong_answers (answers a misinfo document argues for).

This is closed-book: RAMDocs supplies its documents directly, so Qdrant
retrieval is bypassed via the same retrieval_interface._qdrant_retrieve
monkeypatch precedent evaluation/harness.py already uses for Corpus 1/2/3. No
frozen pipeline file (orchestrator.py, validation.py, retrieval_interface.py)
is edited.

RAMDocs is graded on ITS OWN terms, not forced into this project's
answer/conflict/insufficient taxonomy — see docs/PREREGISTRATION_RAMDOCS.md
for why and for the exact rules, fixed before this script was run on the full
set. Two metrics:

  1. safe/unsafe rate — directly comparable to MADAM-RAG's published table.
  2. abstention-justification rate — this project's own structural-safety
     metric, applied to real external data: of the queries where the system
     abstained/flagged conflict, how many actually contained a misinfo doc.

No forced 3-way accuracy number is computed for RAMDocs.

This script is resumable: results are checkpointed to disk after every query
so a Groq rate-limit failure partway through does not lose progress. Re-run
the same command; already-completed query ids are skipped.

Usage
-----
    python evaluation/run_eval_ramdocs.py --tag rd_pilot --limit 20
    python evaluation/run_eval_ramdocs.py --tag rd_full
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import harness_bootstrap  # noqa: F401  (adds this dir and project root to sys.path)

OUT_DIR = Path(__file__).resolve().parent / "results"
DATA_PATH = Path(__file__).resolve().parent.parent / "data_ramdocs" / "RAMDocs_test.jsonl"

# Every document is "retrieved" by construction in this closed-book setup —
# there is no real similarity score to assign. Placed just above the live
# hard floor so Stage 3 does not drop documents RAMDocs itself supplied.
PLACEHOLDER_SCORE = 0.75


def assert_frozen_config() -> None:
    """Same governance guard as run_eval_corpus3.py — see its docstring."""
    overrides = {k: v for k, v in os.environ.items() if k.startswith("RAG_")}
    if overrides:
        raise SystemExit(
            f"Refusing to run: RAG_* overrides are set {overrides}.\n"
            "RAMDocs runs under the frozen configuration only. "
            "See docs/PREREGISTRATION_RAMDOCS.md."
        )


def load_ramdocs(limit: int | None = None) -> list[dict]:
    if not DATA_PATH.exists():
        raise SystemExit(
            f"Missing {DATA_PATH}.\n"
            "Download it first, e.g.:\n"
            '  curl -L -o data_ramdocs/RAMDocs_test.jsonl '
            '"https://huggingface.co/datasets/HanNight/RAMDocs/resolve/main/RAMDocs_test.jsonl"'
        )
    records = []
    with DATA_PATH.open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            rec["_qid"] = f"rd{i:04d}"
            records.append(rec)
    if limit:
        records = records[:limit]
    return records


def chunks_for_record(rec: dict) -> list[dict]:
    """
    Build the retrieval-shaped chunk list for one RAMDocs record.

    Each RAMDocs document becomes one chunk. `source` is synthesized (RAMDocs
    documents have no filename) — correct and misinfo documents get distinct
    source ids so Stage 4's conflict detector, which groups by source, can see
    them as separate documents. type/answer are carried through as extra keys
    (validation.py spreads unknown chunk keys untouched) for grading only.
    """
    chunks = []
    for i, doc in enumerate(rec.get("documents", [])):
        chunks.append({
            "text": doc.get("text", ""),
            "source": f"{rec['_qid']}_doc{i}_{doc.get('type', 'unknown')}",
            "chunk_id": i,
            "section": doc.get("type", "unknown"),
            "score": PLACEHOLDER_SCORE,
            "relevance_score": PLACEHOLDER_SCORE,
            "ramdocs_type": doc.get("type"),
            "ramdocs_doc_answer": doc.get("answer"),
        })
    return chunks


def _normalize(text: str) -> str:
    """
    Collapse Unicode space variants (narrow no-break space U+202F, non-breaking
    space U+00A0, etc.) to plain ASCII spaces before substring matching.
    Synthesis output uses typographic spacing (e.g. "3,559 people") that a
    literal substring check against RAMDocs' plain-ASCII gold strings would
    silently miss, misgrading a correct answer as unscored.
    """
    import unicodedata
    return "".join(" " if unicodedata.category(c) == "Zs" else c for c in text).lower()


def answer_matches(answer: str | None, candidates: list[str]) -> bool:
    if not answer or not candidates:
        return False
    a = _normalize(answer)
    return any(_normalize(c.strip()) in a for c in candidates if c and c.lower() != "unknown")


def grade(rec: dict, result: dict) -> dict:
    """
    Grade one RAMDocs record against ITS OWN gold structure — see
    docs/PREREGISTRATION_RAMDOCS.md. Does not use this project's
    answer/conflict/insufficient taxonomy as a gold label.
    """
    decision = result.get("decision")
    answer = result.get("answer")
    abstained = decision in ("abstain", "retry")

    gold = rec.get("gold_answers") or []
    wrong = rec.get("wrong_answers") or []
    has_misinfo = any(d.get("type") == "misinfo" for d in rec.get("documents", []))

    hit_gold = (not abstained) and answer_matches(answer, gold)
    hit_wrong = (not abstained) and answer_matches(answer, wrong)

    if abstained or hit_gold:
        ramdocs_outcome = "safe"
    elif hit_wrong:
        ramdocs_outcome = "unsafe"
    else:
        ramdocs_outcome = "unscored"  # answered, matched neither list verbatim

    return {
        "id": rec["_qid"],
        "question": rec["question"],
        "decision": decision,
        "answer": answer,
        "gold_answers": gold,
        "wrong_answers": wrong,
        "has_misinfo_doc": has_misinfo,
        "abstained": abstained,
        "ramdocs_outcome": ramdocs_outcome,
        "abstention_justified": (abstained and has_misinfo) if abstained else None,
    }


def run_one(rec: dict) -> dict:
    import retrieval_interface
    import validation
    import orchestrator

    injected = chunks_for_record(rec)

    def fake_retrieve(query: str, top_k: int = 5, **kw):
        return injected

    retrieval_interface._qdrant_retrieve = fake_retrieve
    validation.set_evidence_registry(None)
    validation.set_corpus_stats(None)

    result = orchestrator.run(rec["question"], verbose=False)
    return grade(rec, result)


def summarize(records: list[dict]) -> dict:
    n = len(records)
    safe = sum(1 for r in records if r["ramdocs_outcome"] == "safe")
    unsafe = sum(1 for r in records if r["ramdocs_outcome"] == "unsafe")
    unscored = sum(1 for r in records if r["ramdocs_outcome"] == "unscored")

    abstained = [r for r in records if r["abstained"]]
    justified = [r for r in abstained if r["abstention_justified"]]

    return {
        "n": n,
        "safe_rate_pct": round(100 * safe / n, 1) if n else None,
        "unsafe_rate_pct": round(100 * unsafe / n, 1) if n else None,
        "unscored_rate_pct": round(100 * unscored / n, 1) if n else None,
        "safe": safe, "unsafe": unsafe, "unscored": unscored,
        "abstained_count": len(abstained),
        "abstention_justified_count": len(justified),
        "abstention_justified_pct": (
            round(100 * len(justified) / len(abstained), 1) if abstained else None
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True, help="label for the output file")
    ap.add_argument("--limit", type=int, default=None,
                    help="evaluate only the first N records (pilot runs)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    assert_frozen_config()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{args.tag}_ramdocs.json"
    ckpt_path = OUT_DIR / f"{args.tag}_ramdocs.ckpt.jsonl"

    done: dict[str, dict] = {}
    if ckpt_path.exists():
        with ckpt_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                done[row["id"]] = row
        print(f"Resuming: {len(done)} queries already checkpointed in {ckpt_path}")

    records = load_ramdocs(args.limit)
    t0 = time.time()

    with ckpt_path.open("a", encoding="utf-8") as ckpt_f:
        for i, rec in enumerate(records, 1):
            qid = rec["_qid"]
            if qid in done:
                continue
            try:
                row = run_one(rec)
            except Exception as e:  # noqa: BLE001 — checkpoint what we have, keep going
                print(f"[{i}/{len(records)}] {qid} ERROR: {e}", flush=True)
                continue
            done[qid] = row
            ckpt_f.write(json.dumps(row, ensure_ascii=False) + "\n")
            ckpt_f.flush()
            if not args.quiet:
                mark = {"safe": "OK ", "unsafe": "XX ", "unscored": "?? "}[row["ramdocs_outcome"]]
                print(f"[{i}/{len(records)}] {mark}{qid} decision={row['decision']:<8} "
                      f"outcome={row['ramdocs_outcome']}", flush=True)

    elapsed = round(time.time() - t0, 1)
    all_rows = [done[r["_qid"]] for r in records if r["_qid"] in done]
    metrics = summarize(all_rows)

    out_path.write_text(json.dumps({
        "meta": {
            "tag": args.tag, "benchmark": "ramdocs", "source": "HanNight/RAMDocs (COLM 2025)",
            "n_requested": len(records), "n_completed": len(all_rows), "elapsed_s": elapsed,
        },
        "metrics": metrics,
        "results": all_rows,
    }, indent=2), encoding="utf-8")

    print(f"\n=== {args.tag} / RAMDocs ({len(all_rows)}/{len(records)} queries, {elapsed}s) ===")
    for k, v in metrics.items():
        print(f"  {k:28} {v}")
    if len(all_rows) < len(records):
        print(f"\n  {len(records) - len(all_rows)} queries not completed (errors). "
              f"Re-run the same command to resume from {ckpt_path.name}.")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
