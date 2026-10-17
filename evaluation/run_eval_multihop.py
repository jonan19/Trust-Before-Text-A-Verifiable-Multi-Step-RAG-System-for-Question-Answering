"""
run_eval_multihop.py: the preregistered MultiHop-RAG decision test.

Rules: docs/PREREGISTRATION_MULTIHOP.md (written before any run). In short:
  - all 609 articles indexed through the unchanged ingestion, into a NEW store
    (qdrant_db_multihop/); no existing store is opened for writing;
  - a seeded stratified sample of 300 queries (150 null, 50 each of inference,
    comparison, temporal), run in a seeded shuffled order;
  - two arms on the same first-attempt retrieved passages:
      ours      orchestrator.run() unchanged, decision only (synthesis stubbed, zero LLM calls)
      baseline  prompted openai/gpt-oss-120b, E1 prompt verbatim, temperature 0
  - decisions graded only: null -> insufficient is right, otherwise answer is right.

Resumable: each arm checkpoints after every query; rerun the same command to continue.
Raw baseline replies are stored, so --report re-grades without calling the LLM.

    python evaluation/run_eval_multihop.py --prepare                 # files, index, sample
    python evaluation/run_eval_multihop.py --arm ours --tag mh_pilot --limit 6
    python evaluation/run_eval_multihop.py --arm baseline --tag mh_pilot --limit 6 --rotate-keys
    python evaluation/run_eval_multihop.py --arm ours --tag mh
    python evaluation/run_eval_multihop.py --arm baseline --tag mh --rotate-keys
    python evaluation/run_eval_multihop.py --report --tag mh
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
import random
import re
import time
from pathlib import Path

import harness_bootstrap  # noqa: F401

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA_DIR = ROOT / "data_multihop"
ARTICLES_DIR = DATA_DIR / "articles"
TITLES_PATH = DATA_DIR / "article_titles.json"
STORE = "qdrant_db_multihop"
CORPUS_ID = "mh"
OUT_DIR = HERE / "results"
SAMPLE_PATH = OUT_DIR / "mh_sample.json"
E1_SOURCE = ROOT / "experiments" / "baseline_experiment.py"

HF_REVISION = "71ac0d0bd1f951d2d6b70311f7d2ae404e1ffa82"
DATA_SHA256 = {
    "MultiHopRAG.json": "03cfb4926461f868684903aadc8024447bdda5bb3f6804741424cce338515bff",
    "corpus.json": "20b61b5ab84de84a927420c5d265b7ec8d859ae49980699958a787ade9e4d28f",
}
SEED = 20261015
QUOTAS = (("null_query", 150), ("inference_query", 50),
          ("comparison_query", 50), ("temporal_query", 50))
PILOT_N = 6
# Amendment 1 (2026-10-17): the baseline gets the top 12 retrieved passages, as E1 did
# (experiments/baseline_results.json: max_chunks_sent = 12). Sending all ~30 exceeded the
# free Groq tier's 8,000 tokens-per-minute request limit in the pilot.
BASELINE_MAX_PASSAGES = 12


# ---------------------------------------------------------------- data ----------

def check_config() -> None:
    overrides = {k: v for k, v in os.environ.items() if k.startswith("RAG_")}
    if overrides:
        raise SystemExit(f"Refusing to run: RAG_* overrides are set {sorted(overrides)}. "
                         "This test runs under the default configuration only.")


def load_data(data_dir: Path = DATA_DIR) -> tuple[list[dict], list[dict]]:
    """Return (queries, corpus) after checking the preregistered hashes."""
    for name, want in DATA_SHA256.items():
        path = data_dir / name
        if not path.exists():
            raise SystemExit(f"Missing {path}")
        got = hashlib.sha256(path.read_bytes()).hexdigest()
        if got != want:
            raise SystemExit(f"{name}: SHA-256 {got} does not match the preregistered {want}")
    queries = json.loads((data_dir / "MultiHopRAG.json").read_text(encoding="utf-8"))
    corpus = json.loads((data_dir / "corpus.json").read_text(encoding="utf-8"))
    return queries, corpus


def article_name(i: int) -> str:
    return f"mh_{i:03d}.txt"


def article_text(a: dict) -> str:
    return (f"Title: {a['title']}\nSource: {a['source']}\nAuthor: {a['author']}\n"
            f"Published: {a['published_at']}\nCategory: {a['category']}\n\n{a['body']}")


def write_articles(corpus: list[dict], dest: Path = ARTICLES_DIR,
                   titles_path: Path = TITLES_PATH) -> dict[str, str]:
    """Write one neutral-named text file per article; return {file name: title}."""
    dest.mkdir(parents=True, exist_ok=True)
    titles = {}
    for i, a in enumerate(corpus):
        name = article_name(i)
        (dest / name).write_text(article_text(a), encoding="utf-8", newline="\n")
        titles[name] = a["title"]
    titles_path.write_text(json.dumps(titles, ensure_ascii=False, indent=1), encoding="utf-8")
    return titles


def gold_decision(qtype: str) -> str:
    return "insufficient" if qtype == "null_query" else "answer"


def draw_sample(queries: list[dict], seed: int = SEED, quotas=QUOTAS) -> list[dict]:
    """The preregistered stratified sample, in its seeded run order."""
    picked = []
    for k, (qtype, n) in enumerate(quotas):
        pool = [i for i, q in enumerate(queries) if q["question_type"] == qtype]
        for i in random.Random(seed + k).sample(pool, n):
            q = queries[i]
            picked.append({
                "id": f"mh{i:04d}", "index": i, "type": qtype, "query": q["query"],
                "gold": gold_decision(qtype),
                "gold_titles": sorted({e["title"] for e in q.get("evidence_list") or []}),
            })
    picked.sort(key=lambda r: r["index"])
    random.Random(seed).shuffle(picked)
    return picked


def load_sample() -> list[dict]:
    if not SAMPLE_PATH.exists():
        raise SystemExit(f"Missing {SAMPLE_PATH}; run --prepare first")
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))["queries"]


# ---------------------------------------------------------------- E1 prompt -----

def load_e1(path: Path = E1_SOURCE) -> dict:
    """
    Take the E1 baseline prompt, its context renderer and its reply parser VERBATIM from
    experiments/baseline_experiment.py, without importing that module (it loads the
    pipeline and its own key handling at import time).
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    wanted_vars = {"BASELINE_SYSTEM", "BASELINE_USER_TMPL"}
    wanted_funcs = {"build_context_block", "parse_decision"}
    nodes = [n for n in tree.body
             if (isinstance(n, ast.Assign) and any(getattr(t, "id", None) in wanted_vars for t in n.targets))
             or (isinstance(n, ast.FunctionDef) and n.name in wanted_funcs)]
    ns: dict = {"re": re}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), ns)
    missing = (wanted_vars | wanted_funcs) - set(ns)
    if missing:
        raise SystemExit(f"E1 baseline pieces not found in {path}: {sorted(missing)}")
    return {k: ns[k] for k in wanted_vars | wanted_funcs}


# ---------------------------------------------------------------- pipeline ------

def setup_pipeline():
    """Point the decision-only harness at the MultiHop store; return the orchestrator."""
    import harness
    import qdrant_retrieval
    if not (ROOT / STORE).exists():
        raise SystemExit(f"Missing {ROOT / STORE}; run --prepare first")
    qdrant_retrieval._close_client()
    qdrant_retrieval._published_registry_dir = None
    harness.CORPORA[CORPUS_ID] = {"data": ARTICLES_DIR, "qdrant": STORE}
    return harness.setup(CORPUS_ID)


def first_attempt_passages(orch, query: str) -> tuple[list[dict], list[str]]:
    """The chunks orchestrator.run() retrieves on its first attempt, through the same cache."""
    pq = orch.preprocess_query(query)
    qtype = orch.classify_query(pq)
    subs = orch.decompose_query(pq) if qtype == "complex" else [pq]
    top_k = (orch.RETRIEVAL_TOP_K + len(subs)
             if qtype == "complex" and len(subs) > 1 else orch.RETRIEVAL_TOP_K)
    return orch.retrieve_for_queries(subs, top_k=top_k), subs


def unique_sources(chunks: list[dict]) -> list[str]:
    out = []
    for c in chunks:
        s = c.get("source")
        if s and s not in out:
            out.append(s)
    return out


def retrieval_fields(orch, item: dict, chunks: list[dict], titles: dict[str, str]) -> dict:
    import retrieval_interface
    pq = orch.preprocess_query(item["query"])
    top5 = unique_sources(retrieval_interface.retrieve(pq, top_k=orch.RETRIEVAL_TOP_K)[:5])
    return {"retrieved_sources": unique_sources(chunks),
            "retrieved_titles": [titles.get(s, s) for s in unique_sources(chunks)],
            "top5_titles_original": [titles.get(s, s) for s in top5]}


def run_ours_one(orch, item: dict, titles: dict[str, str]) -> dict:
    import harness
    chunks, subs = first_attempt_passages(orch, item["query"])
    res = orch.run(item["query"], verbose=False)
    val = res.get("validation") or {}
    return {"observed": harness.decision_of(res), "conflict_pair": harness.conflict_pair(res),
            "sufficiency_flag": val.get("sufficiency_flag"), "sub_queries": subs,
            **retrieval_fields(orch, item, chunks, titles)}


def call_llm(system: str, user: str) -> str:
    import llm_interface as li
    from groq import Groq

    def one(max_tokens: int) -> str:
        def _req() -> str:
            client = Groq(api_key=li._GROQ_KEY, timeout=120.0)
            r = client.chat.completions.create(
                model=li._GROQ_MODEL, temperature=0.0, max_tokens=max_tokens,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}])
            return li._strip_reasoning((r.choices[0].message.content or "").strip())
        return li._with_retry(_req)

    reply = one(4096)
    return reply if reply.strip() else one(8192)


def run_baseline_one(orch, item: dict, titles: dict[str, str], e1: dict, llm=call_llm) -> dict:
    chunks, subs = first_attempt_passages(orch, item["query"])
    context = e1["build_context_block"](chunks, max_chunks=BASELINE_MAX_PASSAGES)
    user = e1["BASELINE_USER_TMPL"].format(chunks=context, query=item["query"])
    reply = llm(e1["BASELINE_SYSTEM"], user)
    sent = chunks[:BASELINE_MAX_PASSAGES]
    return {"observed": e1["parse_decision"](reply), "reply": reply,
            "n_passages": len(chunks), "n_passages_sent": len(sent), "sub_queries": subs,
            "retrieved_sources": unique_sources(chunks), "sent_sources": unique_sources(sent),
            "sent_titles": [titles.get(s, s) for s in unique_sources(sent)]}


# ---------------------------------------------------------------- keys ----------

class PoolExhausted(RuntimeError):
    """Every configured key is out of quota or rejected; the checkpoint is intact."""


def apply_key(pair: tuple[str, str]) -> str:
    name, key = pair
    os.environ["GROQ_API_KEY"] = key
    import llm_interface
    llm_interface._GROQ_KEY = key
    return name


def with_pool(fn, pool, sleep=time.sleep):
    """Call fn(); with a pool, move keys only on a spent or rejected key, wait on a throttle."""
    from key_pool import classify_error
    waits = 0
    while True:
        try:
            return fn()
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
                sleep(30 * waits)
                continue
            raise


# ---------------------------------------------------------------- checkpoint ----

def ckpt_path(tag: str, arm: str) -> Path:
    return OUT_DIR / f"{tag}_{arm}_multihop.ckpt.jsonl"


def read_ckpt(path: Path) -> dict[str, dict]:
    done = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                done[row["id"]] = row
    return done


def append_ckpt(path: Path, row: dict) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- statistics ----

def wilson(k: int, n: int) -> list[float] | None:
    if not n:
        return None
    z = 1.959963984540054
    p = k / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(100 * max(0.0, mid - half), 1), round(100 * min(1.0, mid + half), 1)]


def mcnemar(b: int, c: int) -> float:
    """Exact two-sided McNemar p from the discordant counts."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(0, min(b, c) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def rate(k: int, n: int) -> dict:
    return {"k": k, "n": n, "pct": round(100 * k / n, 1) if n else None, "ci": wilson(k, n)}


def arm_metrics(rows: list[dict]) -> dict:
    null = [r for r in rows if r["gold"] == "insufficient"]
    ans = [r for r in rows if r["gold"] == "answer"]
    m = {
        "n": len(rows), "n_null": len(null), "n_answerable": len(ans),
        "gap_leak": rate(sum(r["observed"] == "answer" for r in null), len(null)),
        "over_abstention": rate(sum(r["observed"] != "answer" for r in ans), len(ans)),
        "over_abstention_conflict": sum(r["observed"] == "conflict" for r in ans),
        "over_abstention_insufficient": sum(r["observed"] == "insufficient" for r in ans),
        "refusal_all": rate(sum(r["observed"] != "answer" for r in rows), len(rows)),
        "correct_strict": rate(sum(r["observed"] == r["gold"] for r in rows), len(rows)),
        "correct_lenient": rate(sum((r["observed"] != "answer") == (r["gold"] == "insufficient")
                                    for r in rows), len(rows)),
        "confusion": {g: {o: sum(1 for r in rows if r["gold"] == g and r["observed"] == o)
                          for o in ("answer", "conflict", "insufficient")}
                      for g in ("answer", "insufficient")},
        "by_type": {},
    }
    for qtype, _ in QUOTAS:
        sub = [r for r in rows if r["type"] == qtype]
        if sub:
            m["by_type"][qtype] = {"n": len(sub),
                                   "answered": sum(r["observed"] == "answer" for r in sub),
                                   "conflict": sum(r["observed"] == "conflict" for r in sub),
                                   "insufficient": sum(r["observed"] == "insufficient" for r in sub)}
    return m


def paired_tests(ours: list[dict], base: list[dict]) -> dict:
    b_by = {r["id"]: r for r in base}
    pairs = [(o, b_by[o["id"]]) for o in ours if o["id"] in b_by]

    def test(sel, pred):
        ps = [(o, b) for o, b in pairs if sel(o)]
        b_only_ours = sum(1 for o, b in ps if pred(o) and not pred(b))
        c_only_base = sum(1 for o, b in ps if pred(b) and not pred(o))
        return {"n": len(ps), "ours_only": b_only_ours, "baseline_only": c_only_base,
                "p": mcnemar(b_only_ours, c_only_base)}

    return {
        "n_pairs": len(pairs),
        "gap_leak": test(lambda r: r["gold"] == "insufficient", lambda r: r["observed"] == "answer"),
        "over_abstention": test(lambda r: r["gold"] == "answer", lambda r: r["observed"] != "answer"),
        "correct_strict": test(lambda r: True, lambda r: r["observed"] == r["gold"]),
    }


def retrieval_metrics(rows: list[dict]) -> dict:
    ans = [r for r in rows if r["gold"] == "answer" and r.get("gold_titles")]
    if not ans:
        return {"n": 0}
    gold = sum(len(r["gold_titles"]) for r in ans)
    across = sum(len(set(r["gold_titles"]) & set(r["retrieved_titles"])) for r in ans)
    at5 = sum(len(set(r["gold_titles"]) & set(r["top5_titles_original"])) for r in ans)
    return {"n": len(ans), "gold_articles": gold,
            "gold_retrieved_across_subqueries_pct": round(100 * across / gold, 1),
            "recall_at5_original_pct": round(100 * at5 / gold, 1),
            "all_gold_retrieved_queries": sum(set(r["gold_titles"]) <= set(r["retrieved_titles"]) for r in ans)}


def baseline_visibility(rows: list[dict]) -> dict:
    """Amendment 1, descriptive only: gold articles inside the baseline's capped passages."""
    ans = [r for r in rows if r["gold"] == "answer" and r.get("gold_titles") and "sent_titles" in r]
    if not ans:
        return {"n": 0}
    gold = sum(len(r["gold_titles"]) for r in ans)
    seen = sum(len(set(r["gold_titles"]) & set(r["sent_titles"])) for r in ans)
    return {"n": len(ans), "gold_articles": gold, "gold_in_sent_passages_pct": round(100 * seen / gold, 1),
            "all_gold_sent_queries": sum(set(r["gold_titles"]) <= set(r["sent_titles"]) for r in ans)}


def predictions(m_ours: dict, m_base: dict, tests: dict, retr: dict) -> dict:
    ab = m_ours["over_abstention_conflict"] + m_ours["over_abstention_insufficient"]
    return {
        "P1_ours_more_gap_leaks_p_lt_0.05": (m_ours["gap_leak"]["k"] > m_base["gap_leak"]["k"]
                                             and tests["gap_leak"]["p"] < 0.05),
        "P2_baseline_over_abstains_more": m_base["over_abstention"]["k"] > m_ours["over_abstention"]["k"],
        "P3_ours_over_abstentions_mostly_conflict": ab > 0 and m_ours["over_abstention_conflict"] > ab / 2,
        "P4_strict_correctness_not_significant": tests["correct_strict"]["p"] >= 0.05,
        "P5_recall_across_ge_80_and_at5_lt_70": (retr.get("n", 0) > 0
                                                  and retr["gold_retrieved_across_subqueries_pct"] >= 80
                                                  and retr["recall_at5_original_pct"] < 70),
    }


# ---------------------------------------------------------------- commands ------

def prepare() -> None:
    from run_info import run_info
    check_config()
    queries, corpus = load_data()
    titles = write_articles(corpus)
    print(f"wrote {len(titles)} articles to {ARTICLES_DIR}")
    import qdrant_retrieval
    qdrant_retrieval._close_client()
    t0 = time.time()
    n_chunks = qdrant_retrieval.ingest_documents(data_dir=ARTICLES_DIR, qdrant_dir=ROOT / STORE)
    print(f"store {STORE}: {n_chunks} chunks ({time.time() - t0:.0f}s)")
    sample = draw_sample(queries)
    OUT_DIR.mkdir(exist_ok=True)
    SAMPLE_PATH.write_text(json.dumps({
        "seed": SEED, "hf_revision": HF_REVISION, "data_sha256": DATA_SHA256,
        "quotas": dict(QUOTAS), "chunks": n_chunks, "articles": len(titles),
        "index_seconds": round(time.time() - t0), "run_info": run_info(),
        "queries": sample}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"sample: {len(sample)} queries -> {SAMPLE_PATH}")


def run_arm(arm: str, tag: str, limit: int | None, pool) -> None:
    from run_info import run_info
    check_config()
    sample = load_sample()[:limit] if limit else load_sample()
    titles = json.loads(TITLES_PATH.read_text(encoding="utf-8"))
    orch = setup_pipeline()
    e1 = load_e1() if arm == "baseline" else None
    OUT_DIR.mkdir(exist_ok=True)
    path = ckpt_path(tag, arm)
    done = {k: v for k, v in read_ckpt(path).items() if k != "_run_info"}
    todo = [q for q in sample if q["id"] not in done]
    print(f"{arm}: {len(done)} done, {len(todo)} to go -> {path.name}", flush=True)
    if not path.exists():
        append_ckpt(path, {"id": "_run_info", "run_info": run_info(), "arm": arm, "tag": tag})
    for i, item in enumerate(todo, 1):
        t0 = time.time()
        if arm == "ours":
            out = run_ours_one(orch, item, titles)
        else:
            out = with_pool(lambda: run_baseline_one(orch, item, titles, e1), pool)
        row = {k: item[k] for k in ("id", "type", "gold", "gold_titles")} | out
        row["seconds"] = round(time.time() - t0, 1)
        append_ckpt(path, row)
        print(f"[{len(done) + i}/{len(sample)}] {item['id']} {item['type']:<17} gold={item['gold']:<12} "
              f"{arm}={row['observed']:<12} {row['seconds']}s", flush=True)


def report(tag: str) -> dict:
    sample_ids = [q["id"] for q in load_sample()]
    rows = {}
    for arm in ("ours", "baseline"):
        got = {k: v for k, v in read_ckpt(ckpt_path(tag, arm)).items() if k != "_run_info"}
        rows[arm] = [got[i] for i in sample_ids if i in got]
    both = {r["id"] for r in rows["ours"]} & {r["id"] for r in rows["baseline"]}
    paired = {arm: [r for r in rows[arm] if r["id"] in both] for arm in rows}
    m = {arm: arm_metrics(paired[arm]) for arm in paired}
    tests = paired_tests(paired["ours"], paired["baseline"])
    retr = retrieval_metrics(paired["ours"])
    out = {"tag": tag, "completed": {arm: len(rows[arm]) for arm in rows}, "paired": len(both),
           "metrics": m, "paired_tests": tests, "retrieval_ours": retr,
           "baseline_visibility": baseline_visibility(paired["baseline"]),
           "predictions": predictions(m["ours"], m["baseline"], tests, retr) if both else None}
    (OUT_DIR / f"{tag}_multihop_report.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("completed", "paired", "paired_tests", "retrieval_ours",
                                          "baseline_visibility", "predictions")}, indent=2))
    for arm in ("ours", "baseline"):
        mm = m[arm]
        print(f"{arm:<9} gap leak {mm['gap_leak']['k']}/{mm['gap_leak']['n']} {mm['gap_leak']['ci']}  "
              f"over-abstention {mm['over_abstention']['k']}/{mm['over_abstention']['n']} "
              f"{mm['over_abstention']['ci']}  correct {mm['correct_strict']['pct']}%")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prepare", action="store_true", help="write article files, build the store, draw the sample")
    ap.add_argument("--arm", choices=["ours", "baseline"])
    ap.add_argument("--tag", default="mh")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--report", action="store_true", help="grade stored rows only, no calls")
    ap.add_argument("--rotate-keys", action="store_true",
                    help="baseline only: GROQ_API_KEY, GROQ_API_KEY_2, ... from .env in order "
                         "(names are printed, never values)")
    args = ap.parse_args()
    if args.prepare:
        prepare()
    elif args.report:
        report(args.tag)
    elif args.arm:
        pool = None
        if args.arm == "baseline" and args.rotate_keys:
            from dotenv import load_dotenv
            from key_pool import KeyPool
            load_dotenv(ROOT / ".env")
            pool = KeyPool()
            if not len(pool):
                raise SystemExit("no keys set in .env (GROQ_API_KEY, GROQ_API_KEY_2, ...)")
            print(f"key pool: {len(pool)} keys in use order {', '.join(pool.names)}")
            apply_key(pool.current())
        try:
            run_arm(args.arm, args.tag, args.limit, pool)
        except PoolExhausted as exc:
            raise SystemExit(f"stopped, checkpoint intact: {exc}")
    else:
        ap.error("give --prepare, --arm or --report")


if __name__ == "__main__":
    main()
