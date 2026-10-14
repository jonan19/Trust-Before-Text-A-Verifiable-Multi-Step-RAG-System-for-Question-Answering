"""
run_eval_ramdocs_clean.py: RAMDocs with NO label signal in the prompt.

The 2026-09-04 runner (run_eval_ramdocs.py) named each document `rd0000_doc3_misinfo`
and set its section to `misinfo`; synthesis.py renders both into the prompt, so that
run showed the model every document's label. This runner gives every document a
neutral name and keeps the label, the per-document answer and every other field out of
the chunks and the prompts. Rules: docs/PREREGISTRATION_RAMDOCS_RERUN.md.

Two arms on the same documents:
  ours      orchestrator.run() unchanged (gate, then one synthesis call if it proceeds)
  baseline  prompted gpt-oss-120b with the E1 baseline prompt, no gate

Two document orders: `original` (RAMDocs order; the first document is a correct one in
476 of 500 records, so position still carries a signal) and `shuffled` (seeded, per query).

Answers are stored raw, so any grader can be re-applied without calling the LLM again.
Resumable: results are checkpointed after every query; rerun the same command.

    python evaluation/run_eval_ramdocs_clean.py --arm ours     --tag rdc_ours_orig  --limit 3
    python evaluation/run_eval_ramdocs_clean.py --arm ours     --tag rdc_ours_orig
    python evaluation/run_eval_ramdocs_clean.py --arm baseline --tag rdc_base_orig
    python evaluation/run_eval_ramdocs_clean.py --arm ours --order shuffled --tag rdc_ours_shuf
    python evaluation/run_eval_ramdocs_clean.py --report --tag rdc_ours_orig
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import time
import unicodedata
from pathlib import Path

import harness_bootstrap  # noqa: F401
from run_info import run_info

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT_DIR = HERE / "results"
DATA_PATH = ROOT / "data_ramdocs" / "RAMDocs_test.jsonl"
DATA_SHA256 = "C67F699C97349F00CF1BD08D1DBF8CA1D0CC38C306715C93A10A4F961DCF28B7"
SHUFFLE_SEED = 20261011
PLACEHOLDER_SCORE = 0.75  # same as the 2026-09-04 runner: just above the live floor

BASELINE_SYSTEM = (
    "You answer questions using ONLY the provided context passages. "
    "Follow these rules exactly:\n"
    "1. If the answer is not present in the context, reply with exactly the single "
    "word: INSUFFICIENT\n"
    "2. If two passages give conflicting values for the fact being asked, reply with "
    "the word CONFLICT followed by both values and which document each value came from.\n"
    "3. Otherwise, give the answer, citing the document it came from.\n"
    "Do not use any knowledge beyond the context passages."
)
BASELINE_USER = (
    "Context passages:\n{chunks}\n\n"
    "Question: {query}\n\n"
    "Answer (remember: exactly INSUFFICIENT if not present; start with CONFLICT if "
    "two passages disagree on the asked fact):"
)


# ---------------------------------------------------------------- data ----------

def assert_frozen_config() -> None:
    overrides = {k: v for k, v in os.environ.items() if k.startswith("RAG_")}
    if overrides:
        raise SystemExit(f"Refusing to run: RAG_* overrides are set {overrides}.")


def load_records(limit: int | None = None) -> list[dict]:
    if not DATA_PATH.exists():
        raise SystemExit(f"Missing {DATA_PATH}")
    digest = hashlib.sha256(DATA_PATH.read_bytes()).hexdigest().upper()
    if digest != DATA_SHA256:
        raise SystemExit(f"RAMDocs file hash {digest} does not match the preregistered {DATA_SHA256}")
    rows = []
    for i, line in enumerate(DATA_PATH.read_text(encoding="utf-8").splitlines()):
        if line.strip():
            rec = json.loads(line)
            rec["_qid"] = f"rd{i:04d}"
            rows.append(rec)
    return rows[:limit] if limit else rows


def ordered_docs(rec: dict, order: str) -> list[dict]:
    """The documents in presentation order. The shuffle is seeded per query id."""
    docs = list(rec.get("documents", []))
    if order == "shuffled":
        random.Random(f"{SHUFFLE_SEED}:{rec['_qid']}").shuffle(docs)
    return docs


def neutral_chunks(docs: list[dict]) -> list[dict]:
    """Retrieval-shaped chunks carrying ONLY the text and a neutral name (no label, no answer)."""
    return [{"text": d.get("text", ""), "source": f"Document {i + 1}", "chunk_id": i,
             "section": "Document", "score": PLACEHOLDER_SCORE,
             "relevance_score": PLACEHOLDER_SCORE} for i, d in enumerate(docs)]


# ---------------------------------------------------------------- grading -------

def normalise(text: str) -> str:
    t = "".join(" " if unicodedata.category(c) == "Zs" else c for c in (text or "")).lower()
    return re.sub(r"\s+", " ", t).strip()


def contains(answer: str, candidates: list[str], word_boundary: bool = False) -> bool:
    a = normalise(answer)
    for c in candidates:
        c = normalise(str(c))
        if not c or c == "unknown":
            continue
        if word_boundary:
            if re.search(r"(?<![a-z0-9])" + re.escape(c) + r"(?![a-z0-9])", a):
                return True
        elif c in a:
            return True
    return False


def contains_all(answer: str, candidates: list[str]) -> bool:
    cands = [c for c in candidates if normalise(str(c)) and normalise(str(c)) != "unknown"]
    return bool(cands) and all(contains(answer, [c]) for c in cands)


def grade(answer: str, refused: bool, gold: list[str], wrong: list[str]) -> dict:
    """Primary rule = the 2026-09-04 rule (gold wins a tie), plus the reported variants."""
    g = (not refused) and contains(answer, gold)
    w = (not refused) and contains(answer, wrong)
    outcome = "safe" if (refused or g) else ("unsafe" if w else "unscored")
    gs = (not refused) and contains(answer, gold, True)
    ws = (not refused) and contains(answer, wrong, True)
    strict = "safe" if (refused or (gs and not ws)) else ("unsafe" if ws else "unscored")
    return {
        "outcome": outcome, "strict_outcome": strict,
        "em": (not refused) and contains_all(answer, gold) and not contains(answer, wrong),
        "misinfo_asserted": w and not g,
        "gold_hit": g, "wrong_hit": w,
    }


def parse_baseline_refusal(reply: str) -> bool:
    first = (reply or "").strip().splitlines()[0].strip().upper() if (reply or "").strip() else ""
    return bool(re.match(r"^(THE ANSWER IS )?(CONFLICT|INSUFFICIENT)\b", first))


# ---------------------------------------------------------------- arms ----------

def run_ours(rec: dict, order: str) -> dict:
    import orchestrator
    import retrieval_interface
    import validation

    docs = ordered_docs(rec, order)
    injected = neutral_chunks(docs)
    retrieval_interface._qdrant_retrieve = lambda query, top_k=5, **kw: injected
    validation.set_evidence_registry(None)
    validation.set_corpus_stats(None)
    result = orchestrator.run(rec["question"], verbose=False)
    decision = result.get("decision")
    return {"decision": decision, "refused": decision != "proceed",
            "answer": result.get("answer") or "", "doc_order_types": [d["type"] for d in docs]}


def call_baseline(question: str, docs: list[dict]) -> str:
    import llm_interface as li
    from groq import Groq

    chunks = "\n\n".join(f"[Document {i + 1}]\n{d.get('text', '').strip()}" for i, d in enumerate(docs))
    user = BASELINE_USER.format(chunks=chunks, query=question)

    def one(max_tokens: int) -> str:
        def _req() -> str:
            client = Groq(api_key=li._GROQ_KEY, timeout=120.0)
            r = client.chat.completions.create(
                model=li._GROQ_MODEL, temperature=0.0, max_tokens=max_tokens,
                messages=[{"role": "system", "content": BASELINE_SYSTEM},
                          {"role": "user", "content": user}])
            return li._strip_reasoning((r.choices[0].message.content or "").strip())
        return li._with_retry(_req)

    reply = one(4096)
    return reply if reply.strip() else one(8192)


def run_baseline(rec: dict, order: str) -> dict:
    docs = ordered_docs(rec, order)
    reply = call_baseline(rec["question"], docs)
    return {"decision": "refuse" if parse_baseline_refusal(reply) else "answer",
            "refused": parse_baseline_refusal(reply), "answer": reply,
            "doc_order_types": [d["type"] for d in docs]}


# ---------------------------------------------------------------- metrics -------

def wilson(k: int, n: int) -> list[float]:
    from scipy import stats
    c = stats.binomtest(k, n).proportion_ci(confidence_level=0.95, method="wilson")
    return [round(100 * c.low, 1), round(100 * c.high, 1)]


def summarise(rows: list[dict], docs_by_id: dict[str, dict]) -> dict:
    n = len(rows)
    pct = lambda k: round(100 * k / n, 1) if n else None
    refused = [r for r in rows if r["refused"]]
    answered = [r for r in rows if not r["refused"]]
    has_mis = {r["id"]: any(d["type"] == "misinfo" for d in docs_by_id[r["id"]]["documents"]) for r in rows}
    just = [r for r in refused if has_mis[r["id"]]]
    cnt = lambda key, val: sum(1 for r in rows if r[key] == val)
    m = {
        "n": n,
        "refusal_rate_pct": pct(len(refused)), "refusals": len(refused),
        "em_pct": pct(sum(1 for r in rows if r["em"])),
        "misinfo_asserted_pct": pct(sum(1 for r in rows if r["misinfo_asserted"])),
        "safe": cnt("outcome", "safe"), "safe_pct": pct(cnt("outcome", "safe")),
        "unsafe": cnt("outcome", "unsafe"), "unsafe_pct": pct(cnt("outcome", "unsafe")),
        "unscored": cnt("outcome", "unscored"),
        "strict_safe_pct": pct(cnt("strict_outcome", "safe")), "strict_unsafe_pct": pct(cnt("strict_outcome", "unsafe")),
        "answered": len(answered),
        "answered_gold_pct": round(100 * sum(1 for r in answered if r["gold_hit"]) / len(answered), 1) if answered else None,
        "answered_wrong_pct": round(100 * sum(1 for r in answered if r["wrong_hit"]) / len(answered), 1) if answered else None,
        "refusals_justified": len(just),
        "refusals_justified_pct": round(100 * len(just) / len(refused), 1) if refused else None,
        "base_rate_misinfo_doc_pct": pct(sum(1 for v in has_mis.values() if v)),
    }
    if n:
        m["ci"] = {"refusal": wilson(len(refused), n), "em": wilson(sum(1 for r in rows if r["em"]), n),
                   "safe": wilson(cnt("outcome", "safe"), n),
                   "misinfo_asserted": wilson(sum(1 for r in rows if r["misinfo_asserted"]), n)}
    return m


# ---------------------------------------------------------------- keys ----------

class PoolExhausted(RuntimeError):
    """Every configured key is out of quota or rejected; the checkpoint is intact."""


def apply_key(pair: tuple[str, str]) -> str:
    """Make `pair` the active Groq key for this process (llm_interface reads it per request)."""
    name, key = pair
    os.environ["GROQ_API_KEY"] = key
    import llm_interface
    llm_interface._GROQ_KEY = key
    return name


def run_query(runner, rec: dict, order: str, pool) -> dict:
    """Run one query. With a pool, advance keys only on a spent or rejected key; a per-minute
    throttle backs off on the same key instead of spreading requests across keys."""
    from key_pool import classify_error
    waits = 0
    while True:
        try:
            return runner(rec, order)
        except Exception as exc:
            if pool is None:
                raise
            kind = classify_error(str(exc))
            if kind in ("daily_cap", "invalid"):
                spent = pool.current()[0]
                nxt = pool.retire(kind)
                print(f"  key {spent} {kind}; ", end="", flush=True)
                if nxt is None:
                    raise PoolExhausted("all keys spent: " + pool.status()) from exc
                print(f"switching to {apply_key(pool.current())}", flush=True)
                continue
            if kind == "rate_minute" and waits < 4:
                waits += 1
                print(f"  per-minute limit on {pool.current()[0]}; waiting {30 * waits}s", flush=True)
                time.sleep(30 * waits)
                continue
            raise


# ---------------------------------------------------------------- driver --------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=["ours", "baseline"], default="ours")
    ap.add_argument("--order", choices=["original", "shuffled"], default="original")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--report", action="store_true", help="re-grade stored answers only")
    ap.add_argument("--key-env", default=None,
                    help="name of the environment variable that holds the Groq key to use for "
                         "this run (e.g. GROQ_API_KEY_2); set in this process only, .env is not edited")
    ap.add_argument("--rotate-keys", action="store_true",
                    help="use GROQ_API_KEY, GROQ_API_KEY_2, ... from .env in order, moving to the next "
                         "only when a key's daily quota is spent or it is rejected (names are printed, never values)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    assert_frozen_config()
    pool = None
    if args.rotate_keys:
        if args.key_env:
            raise SystemExit("use either --rotate-keys or --key-env, not both")
        from dotenv import load_dotenv
        from key_pool import KeyPool
        load_dotenv(ROOT / ".env")
        pool = KeyPool()
        if not len(pool):
            raise SystemExit("no keys set in .env (GROQ_API_KEY, GROQ_API_KEY_2, ...)")
        print(f"key pool: {len(pool)} keys in use order {', '.join(pool.names)}")
        apply_key(pool.current())
    if args.key_env:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
        key = os.environ.get(args.key_env, "").strip()
        if not key:
            raise SystemExit(f"{args.key_env} is not set")
        os.environ["GROQ_API_KEY"] = key   # llm_interface reads this name; load_dotenv will not override it

    OUT_DIR.mkdir(exist_ok=True)
    ckpt = OUT_DIR / f"{args.tag}_ramdocs_clean.ckpt.jsonl"
    out = OUT_DIR / f"{args.tag}_ramdocs_clean.json"
    records = load_records(args.limit)
    by_id = {r["_qid"]: r for r in records}

    done: dict[str, dict] = {}
    if ckpt.exists():
        for line in ckpt.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                done[row["id"]] = row
        print(f"Resuming: {len(done)} queries already checkpointed")

    if not args.report:
        runner = run_ours if args.arm == "ours" else run_baseline
        t0 = time.time()
        with ckpt.open("a", encoding="utf-8") as f:
            for i, rec in enumerate(records, 1):
                if rec["_qid"] in done:
                    continue
                try:
                    res = run_query(runner, rec, args.order, pool)
                except PoolExhausted as exc:
                    print(f"\nSTOPPED: {exc}\nEvery key is spent for now. {len(done)} queries are "
                          f"checkpointed; rerun the same command later (daily quotas reset) to resume.", flush=True)
                    break
                except Exception as exc:  # checkpoint what we have, keep going
                    print(f"[{i}/{len(records)}] {rec['_qid']} ERROR: {str(exc)[:160]}", flush=True)
                    continue
                row = {"id": rec["_qid"], "question": rec["question"], **res}
                done[rec["_qid"]] = row
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
                if not args.quiet:
                    print(f"[{i}/{len(records)}] {rec['_qid']} refused={res['refused']}", flush=True)
        print(f"queries run in {round(time.time() - t0, 1)}s")

    rows = []
    for rec in records:
        if rec["_qid"] in done:
            row = dict(done[rec["_qid"]])
            row.update(grade(row["answer"], row["refused"], rec.get("gold_answers") or [],
                             rec.get("wrong_answers") or []))
            row["gold_answers"], row["wrong_answers"] = rec.get("gold_answers"), rec.get("wrong_answers")
            rows.append(row)
    metrics = summarise(rows, by_id)
    out.write_text(json.dumps({
        "meta": {"tag": args.tag, "arm": args.arm, "order": args.order, "n_requested": len(records),
                 "n_completed": len(rows), "data_sha256": DATA_SHA256, "shuffle_seed": SHUFFLE_SEED,
                 "model": "openai/gpt-oss-120b"},
        "run_info": run_info(include_config=(args.arm == "ours")),
        "metrics": metrics, "results": rows}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n=== {args.tag} / {args.arm} / {args.order} order ({len(rows)}/{len(records)}) ===")
    for k, v in metrics.items():
        print(f"  {k:28} {v}")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
