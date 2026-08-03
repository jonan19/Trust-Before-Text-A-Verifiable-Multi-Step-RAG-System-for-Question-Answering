"""
scale_test.py — HARD TEST 1/3: scale / buried-conflict (attention dilution).

Hypothesis
----------
As the number of retrieved chunks N grows, a prompted 70B LLM's ability to spot
a cross-document conflict degrades (lost-in-the-middle / attention dilution),
while our deterministic validator holds flat because it checks EVERY
cross-document pair (O(N^2)) regardless of N or placement.

Design
------
* 4 planted conflicts (probation 3 vs 6 mo; remote 3 vs 2 days; pension 6 vs 5%;
  personal-device permitted vs prohibited). For each, the two real conflicting
  chunks are pulled from the corpus.
* Haystacks of size N in {2,5,10,20,40}: the 2 conflict chunks + (N-2) DISTRACTOR
  chunks drawn from OTHER corpus documents (real, topically plausible, unrelated
  to this conflict — never random noise). 5 draws per (conflict,N), each with a
  different distractor sample AND a different placement of the conflict pair
  (front / back / adjacent-middle / split ends / random).
* FAIRNESS: BOTH systems receive the IDENTICAL ordered chunk set per haystack.
  - Ours: chunks fed straight into validation.validate() with the conflict's
    probing query (retrieval bypassed). Every chunk gets uniform high
    score/relevance_score so ALL N survive Stage-3 filtering — this deliberately
    removes any "our filter dropped the distractors" advantage and isolates the
    exhaustive pairwise checker. relevant_count is recorded so dedup shrinkage is
    visible.
  - LLM: same N chunks in the prompt, same conflict-detection instruction as the
    78-query baseline, temperature 0, one call per haystack.
* FROZEN system — no threshold retuning.

Recall = fraction of haystacks where the system correctly reports the conflict:
  ours = flagged AND detected pair == the two expected conflict documents;
  LLM  = replied CONFLICT AND gave both differing values.

Usage
-----
  python experiments/scale_test.py --smoke   # 1 conflict x N{2,10,40} x5 = 15
  python experiments/scale_test.py --full     # 4 x {2,5,10,20,40} x5 = 100
"""

from __future__ import annotations

import argparse
import json
import random
import re
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

import validation  # noqa: E402  (frozen — read only)
from qdrant_retrieval import retrieve_by_source  # noqa: E402
# reuse the exact baseline LLM machinery (prompt, multi-key rotation, parsing)
from baseline_experiment import (  # noqa: E402
    build_context_block,
    call_baseline,
    parse_decision,
    build_conflict_key,
    n_keys,
    DailyTokenExhausted,
)

DATA = ROOT / "data"
OUT = ROOT / "experiments"

N_VALUES_FULL = [2, 5, 10, 20, 40]
N_VALUES_SMOKE = [2, 10, 40]
DRAWS = 5
UNIFORM_SCORE = 0.85          # > MIN_CHUNK_SCORE_THRESHOLD (0.60) → survives Stage 3
UNIFORM_RELEVANCE = 1.0       # all equal → none dropped by the relative ratio filter

# Each conflict: probing query (verified-detected in v6), the two docs, and the
# value-bearing keywords used to pick the correct chunk from each doc.
CONFLICTS = [
    {
        "id": "C1", "topic": "probation",
        "query": "What is the probationary period for new employees?",
        "docs": [
            {"file": "Employee_Handbook.docx",
             "must": [r"probation", r"\b3\b", r"month"]},
            {"file": "Recruitment_and_Onboarding_Policy.docx",
             "must": [r"probation", r"\b6\b", r"month"]},
        ],
        "exclude_kw": ["probation"],
    },
    {
        "id": "C2", "topic": "remote days",
        "query": "How many days per week am I allowed to work remotely?",
        "docs": [
            {"file": "Flexible_and_Remote_Work_Policy.docx",
             "must": [r"\b3\b", r"day", r"(remote|hybrid|home)"]},
            {"file": "Remote_Working_Policy_2023_Superseded.docx",
             "must": [r"\b2\b", r"day", r"(remote|home)"]},
        ],
        "exclude_kw": ["remote", "work from home", "telecommut", "hybrid"],
    },
    {
        "id": "C3", "topic": "pension",
        "query": "What percentage does the employer contribute to my pension?",
        "docs": [
            {"file": "Compensation_and_Benefits_Policy.docx",
             "must": [r"pension", r"\b6\b", r"(%|percent)"]},
            {"file": "Employee_Handbook.docx",
             "must": [r"pension", r"\b5\b", r"(%|percent)"]},
        ],
        "exclude_kw": ["pension"],
    },
    {
        "id": "C4", "topic": "personal device email",
        "query": "Can I use my personal phone to access work email?",
        "docs": [
            {"file": "IT_and_Acceptable_Use_Policy.docx",
             "must": [r"(personal|device|mobile)", r"email", r"(permit|allow|may)"]},
            {"file": "Code_of_Conduct_and_Disciplinary_Policy.docx",
             "must": [r"(personal|device|mobile)", r"email", r"(prohibit|not|forbidden|must not)"]},
        ],
        "exclude_kw": ["personal device", "personal mobile", "byod", "corporate email"],
    },
]

CORPUS_DOCS = [
    "Employee_Handbook.docx", "Leave_and_Time_Off_Policy.docx",
    "Flexible_and_Remote_Work_Policy.docx", "Remote_Working_Policy_2023_Superseded.docx",
    "Compensation_and_Benefits_Policy.docx", "Performance_Management_Policy.docx",
    "Recruitment_and_Onboarding_Policy.docx", "IT_and_Acceptable_Use_Policy.docx",
    "Travel_and_Expense_Policy.docx", "Code_of_Conduct_and_Disciplinary_Policy.docx",
    "Health_and_Safety_Policy.docx",
]

_DOC_CACHE: dict[str, list[dict]] = {}


def doc_chunks(fname: str) -> list[dict]:
    if fname not in _DOC_CACHE:
        _DOC_CACHE[fname] = retrieve_by_source(fname)
    return _DOC_CACHE[fname]


def _content_terms(query: str) -> set[str]:
    return validation._query_content_terms(query)


def select_conflict_chunk(fname: str, must_patterns: list[str],
                          query: str) -> dict | None:
    """Pick the chunk from `fname` that best matches the value-bearing patterns
    AND overlaps the probing query (so its Stage-4 query-relevant span is
    non-empty). Returns a fresh chunk dict or None."""
    terms = _content_terms(query)
    best, best_score = None, -1
    for c in doc_chunks(fname):
        t = c.get("text", "").lower()
        matched = sum(1 for p in must_patterns if re.search(p, t))
        overlap = len({w.lower().strip(".,;:?!'\"()") for w in t.split()} & terms)
        score = matched * 100 + overlap
        if matched == len(must_patterns) and score > best_score:
            best, best_score = c, score
    if best is None:  # relax: best partial match
        for c in doc_chunks(fname):
            t = c.get("text", "").lower()
            matched = sum(1 for p in must_patterns if re.search(p, t))
            overlap = len({w.lower().strip(".,;:?!'\"()") for w in t.split()} & terms)
            score = matched * 100 + overlap
            if score > best_score:
                best, best_score = c, score
    return dict(best) if best else None


def distractor_pool(conflict: dict) -> list[dict]:
    """All chunks from documents NOT part of this conflict, excluding any chunk
    mentioning the conflict's fact keywords."""
    conflict_files = {d["file"] for d in conflict["docs"]}
    excl = [k.lower() for k in conflict["exclude_kw"]]
    pool = []
    for f in CORPUS_DOCS:
        if f in conflict_files:
            continue
        for c in doc_chunks(f):
            t = c.get("text", "").lower()
            if any(k in t for k in excl):
                continue
            if len(t.split()) < 8:      # skip tiny fragments
                continue
            pool.append(dict(c))
    return pool


def _prep(chunk: dict) -> dict:
    """Uniform high score/relevance so every chunk survives Stage-3 filtering —
    isolates the exhaustive pairwise checker from any filtering advantage."""
    return {
        "text": chunk.get("text", ""),
        "source": chunk.get("source", "unknown"),
        "section": chunk.get("section", "unknown"),
        "score": UNIFORM_SCORE,
        "relevance_score": UNIFORM_RELEVANCE,
    }


def place_pair(distractors: list[dict], pair: list[dict], draw: int,
               N: int) -> list[dict]:
    """Return an ordered list of N chunks with the conflict `pair` placed per a
    draw-specific position (front / back / adjacent-middle / split-ends / random)."""
    d = list(distractors)
    a, b = pair[0], pair[1]
    if N == 2:
        seq = [a, b]
    elif draw == 0:                       # front
        seq = [a, b] + d
    elif draw == 1:                       # back
        seq = d + [a, b]
    elif draw == 2:                       # adjacent, middle
        mid = len(d) // 2
        seq = d[:mid] + [a, b] + d[mid:]
    elif draw == 3:                       # split: one near front, one near back
        seq = d[:1] + [a] + d[1:] + [b]
    else:                                 # random placement
        seq = list(d)
        i = random.randint(0, len(seq))
        seq.insert(i, a)
        j = random.randint(0, len(seq))
        seq.insert(j, b)
    return seq[:N]


def run_ours(chunks: list[dict], query: str, expected_pair: set[str]) -> dict:
    res = validation.validate(chunks, query=query)
    detail = res.get("conflict_detail")
    detected_pair = None
    if detail and detail.get("chunks"):
        detected_pair = sorted({c.get("source") for c in detail["chunks"]})
    correct = bool(res["conflict_flag"]
                   and detected_pair and set(detected_pair) == expected_pair)
    return {
        "flagged": res["conflict_flag"],
        "kind": (detail or {}).get("kind"),
        "detected_pair": detected_pair,
        "correct": correct,
        "relevant_count": res["relevant_count"],
    }


def run_llm(chunks: list[dict], query: str, value_tokens: dict) -> dict:
    context = build_context_block(chunks, max_chunks=None)  # send ALL N
    reply = call_baseline(context, query, temperature=0.0)
    dec = parse_decision(reply)
    rl = reply.lower()
    a, b = value_tokens["docs"]
    va = all(t in rl for t in value_tokens["values"][a])
    vb = all(t in rl for t in value_tokens["values"][b])
    correct = bool(dec == "conflict" and va and vb)
    return {
        "decision": dec,
        "gave_both_values": bool(va and vb),
        "correct": correct,
        "reply": reply,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--out", default="")
    ap.add_argument("--seed", type=int, default=20260728)
    args = ap.parse_args()
    if not (args.smoke or args.full):
        ap.error("specify --smoke or --full")

    random.seed(args.seed)
    n_values = N_VALUES_SMOKE if args.smoke else N_VALUES_FULL
    conflicts = CONFLICTS[:1] if args.smoke else CONFLICTS
    out_name = args.out or ("scale_results_smoke.json" if args.smoke
                            else "scale_results.json")
    out_path = OUT / out_name

    gt = json.load(open(DATA / "ground_truth.json", encoding="utf-8"))
    ckey = build_conflict_key(gt)  # frozenset(pair) -> {docs, values}

    print(f"Groq keys detected: {n_keys()}")
    total = len(conflicts) * len(n_values) * DRAWS
    print(f"Haystacks: {len(conflicts)} conflicts x {len(n_values)} N x {DRAWS} "
          f"draws = {total}  (1 LLM call each, temp 0)\n")

    # resume support
    results, done = [], set()
    if out_path.exists():
        try:
            prev = json.load(open(out_path, encoding="utf-8"))
            results = prev.get("results", [])
            done = {(r["conflict"], r["N"], r["draw"]) for r in results}
            if done:
                print(f"Resuming: {len(done)} haystacks already done.\n")
        except Exception:
            pass

    def save():
        json.dump({"meta": {"seed": args.seed, "uniform_score": UNIFORM_SCORE,
                            "uniform_relevance": UNIFORM_RELEVANCE,
                            "n_values": n_values,
                            "n_conflicts": len(conflicts), "draws": DRAWS},
                   "results": results},
                  open(out_path, "w", encoding="utf-8"), indent=2)

    stopped = False
    for conf in conflicts:
        pair_files = [d["file"] for d in conf["docs"]]
        expected_pair = set(pair_files)
        vtok = ckey[frozenset(pair_files)]
        # select the two real conflicting chunks
        cc = [select_conflict_chunk(d["file"], d["must"], conf["query"])
              for d in conf["docs"]]
        if any(c is None for c in cc):
            print(f"[!] {conf['id']}: could not locate a conflict chunk — skipping")
            continue
        pair = [_prep(cc[0]), _prep(cc[1])]
        # sanity: show the selected chunks once
        for d, c in zip(conf["docs"], cc):
            span = validation._query_relevant_text(
                c["text"], _content_terms(conf["query"]))
            print(f"  {conf['id']} chunk [{d['file']}] "
                  f"query-span {'OK' if span.strip() else 'EMPTY!!'}: "
                  f"\"{(span or c['text'])[:90].strip()}...\"")
        pool = distractor_pool(conf)
        print(f"  {conf['id']} distractor pool: {len(pool)} chunks\n")

        for N in n_values:
            for draw in range(DRAWS):
                key = (conf["id"], N, draw)
                if key in done:
                    continue
                rng = random.Random(f"{args.seed}-{conf['id']}-{N}-{draw}")
                need = max(0, N - 2)
                distr = rng.sample(pool, min(need, len(pool)))
                distr = [_prep(x) for x in distr]
                ordered = place_pair(distr, pair, draw, N)

                ours = run_ours([dict(c) for c in ordered], conf["query"],
                                expected_pair)
                try:
                    llm = run_llm([dict(c) for c in ordered], conf["query"], vtok)
                except DailyTokenExhausted as exc:
                    print(f"\n[!] Groq keys exhausted at {key}. Saving "
                          f"{len(results)} haystacks; resume later.\n    {exc}")
                    save()
                    stopped = True
                    break

                results.append({
                    "conflict": conf["id"], "topic": conf["topic"],
                    "query": conf["query"], "N": N, "draw": draw,
                    "n_input": len(ordered),
                    "ours": ours, "llm": llm,
                })
                save()
                print(f"  {conf['id']} N={N:<2} draw={draw}  "
                      f"ours={'OK' if ours['correct'] else 'MISS'}"
                      f"({ours['relevant_count']}) "
                      f"llm={'OK' if llm['correct'] else 'MISS'}"
                      f"({llm['decision']})", flush=True)
            if stopped:
                break
        if stopped:
            break

    save()
    summarize(results, n_values, conflicts, stopped)
    print(f"\nWrote {out_path}")


def summarize(results, n_values, conflicts, stopped):
    print("\n" + "=" * 56)
    print("RECALL vs N  (correctly reports the conflict)")
    print("=" * 56)
    print(f"{'N':>4} | {'ours':>12} | {'LLM baseline':>14}")
    print("-" * 40)
    for N in n_values:
        rn = [r for r in results if r["N"] == N]
        if not rn:
            continue
        o = sum(r["ours"]["correct"] for r in rn)
        l = sum(r["llm"]["correct"] for r in rn)
        print(f"{N:>4} | {o:>2}/{len(rn):<2} = {100*o/len(rn):>4.0f}% | "
              f"{l:>2}/{len(rn):<2} = {100*l/len(rn):>4.0f}%")
    if stopped:
        print("\n(PARTIAL — Groq keys exhausted; re-run to resume.)")


if __name__ == "__main__":
    main()
