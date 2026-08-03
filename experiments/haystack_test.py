"""
haystack_test.py — HARD TEST 1: scale / buried-conflict.

Hypothesis: as the number of retrieved chunks N grows, a prompted 70B LLM's
ability to spot a planted cross-document conflict degrades (attention dilution
/ lost-in-the-middle), while our deterministic validator holds flat because
find_conflict() checks every cross-document pair regardless of N.

Design
------
* 4 planted conflicts, each with its 2 known conflicting chunks (by chunk_id).
* Haystacks of size N in {2,5,10,20,40}: the 2 conflict chunks + (N-2) REAL
  distractor chunks drawn from OTHER corpus documents (topically plausible,
  not random noise), with the 8 known conflict chunks excluded from the pool
  so no *other* planted conflict is accidentally seeded.
* 5 draws per (conflict, N): different seeded distractor samples AND different
  placements of the conflict pair (front / back / buried-middle / split-far /
  split-buried). 4 x 5 x 5 = 100 haystacks.
* FAIRNESS: both systems get the IDENTICAL ordered chunk set per haystack.
    - Ours: validate(chunks, query) with the conflict-probing query. Every
      chunk carries uniform score=relevance=0.85 so Stage-3 relevance filtering
      drops nothing (relevant_count is recorded to prove it) — the win, if any,
      is from exhaustive pairwise checking, not filtering.
    - LLM: same N chunk texts in the same order, same conflict-detection
      instruction as the 78-query baseline, temperature 0, one call.
* FROZEN system: no threshold retuned.

Grading (conflict recall)
-------------------------
* Ours "detected": conflict_flag AND the reported pair's two sources == the two
  planted docs (i.e. it reported THE planted conflict, not a distractor pair).
* LLM "detected": reply parses as CONFLICT AND names BOTH differing values.
  (lenient "both values regardless of flag" also recorded.)

Usage
-----
  python experiments/haystack_test.py --smoke      # C1, N in {2,10,40}
  python experiments/haystack_test.py --full        # all 4 conflicts, all N
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

from qdrant_retrieval import retrieve_by_source  # noqa: E402
from validation import validate, find_conflict    # noqa: E402
# reuse the exact baseline LLM plumbing (multi-key rotation, prompt, parser)
from baseline_experiment import (                  # noqa: E402
    call_baseline,
    parse_decision,
    n_keys,
    DailyTokenExhausted,
)

OUT = ROOT / "experiments"

# ---------------------------------------------------------------------------
# Planted conflicts: (chunk A by id, chunk B by id), probing query, value graders
# ---------------------------------------------------------------------------
CONFLICTS = {
    "C1_probation": {
        "topic": "probationary period length",
        "a": ("Employee_Handbook.docx", 4),
        "b": ("Recruitment_and_Onboarding_Policy.docx", 4),
        "query": "What is the probationary period for new employees?",
        "val_a": r"3[\s\-]*month|three month",
        "val_b": r"6[\s\-]*month|six month",
    },
    "C2_remote": {
        "topic": "max remote days per week",
        "a": ("Flexible_and_Remote_Work_Policy.docx", 2),
        "b": ("Remote_Working_Policy_2023_Superseded.docx", 2),
        "query": "How many days per week am I allowed to work remotely?",
        "val_a": r"3[\s\-]*day|three day",
        "val_b": r"2[\s\-]*day|two day",
    },
    "C3_pension": {
        "topic": "employer pension contribution",
        "a": ("Compensation_and_Benefits_Policy.docx", 2),
        "b": ("Employee_Handbook.docx", 6),
        "query": "What percentage does the employer contribute to my pension?",
        "val_a": r"6\s*%|6 per ?cent",
        "val_b": r"5\s*%|5 per ?cent",
    },
    "C4_device": {
        "topic": "personal device for corporate email",
        "a": ("IT_and_Acceptable_Use_Policy.docx", 4),
        "b": ("Code_of_Conduct_and_Disciplinary_Policy.docx", 4),
        "query": "Can I use my personal phone to access work email?",
        "val_a": r"permit",
        "val_b": r"prohibit",
    },
}

N_VALUES = [2, 5, 10, 20, 40]
N_DRAWS = 5

# ---------------------------------------------------------------------------
# Corpus loading
# ---------------------------------------------------------------------------
_CORPUS: dict[str, list[dict]] = {}


def load_corpus() -> dict[str, list[dict]]:
    if not _CORPUS:
        gt = json.load(open(ROOT / "data" / "ground_truth.json", encoding="utf-8"))
        for d in gt["documents"]:
            f = d["file"]
            _CORPUS[f] = retrieve_by_source(f)
    return _CORPUS


def get_chunk(source: str, chunk_id: int) -> dict:
    for c in load_corpus()[source]:
        if c.get("chunk_id") == chunk_id:
            return c
    raise KeyError(f"{source}#{chunk_id} not found")


def conflict_chunk_ids() -> set[tuple[str, int]]:
    ids = set()
    for cfg in CONFLICTS.values():
        ids.add(cfg["a"])
        ids.add(cfg["b"])
    return ids


def distractor_pool(exclude_docs: set[str]) -> list[dict]:
    """All corpus chunks from docs NOT in exclude_docs, minus the 8 known
    conflict chunks (so no other planted conflict is seeded)."""
    banned = conflict_chunk_ids()
    pool = []
    for f, chunks in load_corpus().items():
        if f in exclude_docs:
            continue
        for c in chunks:
            if (f, c.get("chunk_id")) in banned:
                continue
            pool.append(c)
    return pool


# ---------------------------------------------------------------------------
# Haystack construction
# ---------------------------------------------------------------------------
def placement(n: int, draw: int) -> tuple[int, int]:
    """Positions for (chunkA, chunkB) among N slots, per draw pattern."""
    if n == 2:
        return 0, 1
    patterns = [
        (0, 1),                       # front, adjacent
        (n - 2, n - 1),               # back, adjacent
        (n // 2 - 1, n // 2),         # buried middle, adjacent
        (1, n - 2),                   # split far apart
        (n // 4, (3 * n) // 4),       # both buried, split
    ]
    pa, pb = patterns[draw % len(patterns)]
    pa = max(0, min(pa, n - 1))
    pb = max(0, min(pb, n - 1))
    if pa == pb:
        pb = (pb + 1) % n
        if pb == pa:
            pb = (pa + 1) % n
    return pa, pb


def build_haystack(cid: str, n: int, draw: int) -> tuple[list[dict], dict]:
    """Return (ordered chunks with uniform scores, meta)."""
    cfg = CONFLICTS[cid]
    ca = get_chunk(*cfg["a"])
    cb = get_chunk(*cfg["b"])
    exclude = {cfg["a"][0], cfg["b"][0]}
    pool = distractor_pool(exclude)

    rng = random.Random(f"{cid}|{n}|{draw}")
    n_dist = n - 2
    distractors = rng.sample(pool, n_dist) if n_dist > 0 else []

    pa, pb = placement(n, draw)
    slots: list[dict | None] = [None] * n
    slots[pa] = ca
    slots[pb] = cb
    di = iter(distractors)
    for i in range(n):
        if slots[i] is None:
            slots[i] = next(di)

    # uniform high scores so Stage-3 keeps every chunk (no filtering win)
    ordered = []
    for c in slots:
        ordered.append({
            "text": c["text"],
            "source": c["source"],
            "section": c.get("section", "unknown"),
            "chunk_id": c.get("chunk_id", -1),
            "score": 0.85,
            "relevance_score": 0.85,
        })
    meta = {
        "conflict_pos": [pa, pb],
        "pair_sources": [cfg["a"][0], cfg["b"][0]],
        "distractor_sources": [d["source"] for d in distractors],
    }
    return ordered, meta


# ---------------------------------------------------------------------------
# LLM context (same labeling as the 78-query baseline)
# ---------------------------------------------------------------------------
def build_context(chunks: list[dict]) -> str:
    lines = []
    for i, c in enumerate(chunks, 1):
        lines.append(f"[Passage {i} | Source: {c['source']}]\n{c['text'].strip()}")
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------
_ISO_CACHE: dict[str, bool] = {}


def ours_pair_in_isolation(cid: str) -> bool:
    """Does the FROZEN detector flag the planted pair when it is the ONLY
    cross-document pair present? Isolates 'can our check detect this conflict'
    from 'does a distractor pair mask it in a big haystack'. Same code path
    (find_conflict), no threshold change."""
    if cid not in _ISO_CACHE:
        cfg = CONFLICTS[cid]
        a = get_chunk(*cfg["a"])
        b = get_chunk(*cfg["b"])
        pair = [{**a, "score": 0.85, "relevance_score": 0.85},
                {**b, "score": 0.85, "relevance_score": 0.85}]
        detail = find_conflict(pair, query=cfg["query"])
        reported = sorted(c["source"] for c in detail["chunks"]) if detail else []
        _ISO_CACHE[cid] = reported == sorted([cfg["a"][0], cfg["b"][0]])
    return _ISO_CACHE[cid]


def grade_ours(cid: str, cfg: dict, result: dict) -> dict:
    detail = result.get("conflict_detail")
    flagged = result.get("conflict_flag", False)
    reported = sorted(c["source"] for c in detail["chunks"]) if detail else []
    expected = sorted([cfg["a"][0], cfg["b"][0]])
    correct_pair = flagged and reported == expected
    # value check on the reported span text
    both_values = False
    if detail:
        txt = " ".join(c["text"] for c in detail["chunks"]).lower()
        both_values = bool(re.search(cfg["val_a"], txt) and re.search(cfg["val_b"], txt))
    return {
        "flagged": flagged,
        "reported_pair": reported,
        "correct_pair": correct_pair,
        "both_values": both_values,
        "detected": correct_pair,          # primary recall criterion
        # flagged a conflict but the WRONG (distractor) pair — a masking event
        "masked_wrong_pair": flagged and not correct_pair,
        # would the frozen detector catch the planted pair in isolation?
        "iso_detected": ours_pair_in_isolation(cid),
        "relevant_count": result.get("relevant_count"),
        "conflict_kind": (detail or {}).get("kind"),
    }


def grade_llm(cfg: dict, reply: str, decision: str) -> dict:
    rl = reply.lower()
    va = bool(re.search(cfg["val_a"], rl))
    vb = bool(re.search(cfg["val_b"], rl))
    flagged = decision == "conflict"
    return {
        "decision": decision,
        "flagged": flagged,
        "val_a": va,
        "val_b": vb,
        "both_values": va and vb,
        "detected": flagged and va and vb,   # strict: CONFLICT + both values
        "lenient_both_values": va and vb,    # both values regardless of flag
    }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def run(conflicts: list[str], n_values: list[int], out_name: str):
    checkpoint = OUT / out_name
    results: list[dict] = []
    done: set[str] = set()
    if checkpoint.exists():
        try:
            prev = json.load(open(checkpoint, encoding="utf-8"))
            results = prev.get("results", [])
            done = {r["key"] for r in results}
            if done:
                print(f"Resuming: {len(done)} haystacks already done.\n", flush=True)
        except Exception:
            pass

    llm_cache: dict[str, tuple[str, str]] = {}  # identical chunk-id order -> (reply,decision)
    print(f"Groq keys: {n_keys()}\n", flush=True)

    total = len(conflicts) * len(n_values) * N_DRAWS
    idx = 0
    stopped = False
    for cid in conflicts:
        cfg = CONFLICTS[cid]
        for n in n_values:
            for draw in range(N_DRAWS):
                idx += 1
                key = f"{cid}|N{n}|d{draw}"
                if key in done:
                    continue
                chunks, meta = build_haystack(cid, n, draw)

                # ── OURS (deterministic, no tokens) ──
                vres = validate(chunks, query=cfg["query"])
                ours = grade_ours(cid, cfg, vres)

                # ── LLM (identical chunk set) ──
                cache_key = "|".join(f"{c['source']}#{c['chunk_id']}" for c in chunks)
                try:
                    if cache_key in llm_cache:
                        reply, decision = llm_cache[cache_key]
                    else:
                        ctx = build_context(chunks)
                        reply = call_baseline(ctx, cfg["query"], temperature=0.0)
                        decision = parse_decision(reply)
                        llm_cache[cache_key] = (reply, decision)
                except DailyTokenExhausted as exc:
                    print(f"\n[!] Groq daily cap hit at {key}. Saving "
                          f"{len(results)} haystacks and stopping.\n  {exc}",
                          flush=True)
                    stopped = True
                    break
                llm = grade_llm(cfg, reply, decision)

                results.append({
                    "key": key, "conflict": cid, "topic": cfg["topic"],
                    "N": n, "draw": draw,
                    "conflict_pos": meta["conflict_pos"],
                    "distractor_sources": meta["distractor_sources"],
                    "ours": ours, "llm": llm,
                    "llm_reply": reply,
                })
                print(f"[{idx}/{total}] {key:<18} ours={'Y' if ours['detected'] else 'n'}"
                      f"(rel={ours['relevant_count']}) "
                      f"llm={'Y' if llm['detected'] else 'n'}"
                      f"(dec={llm['decision']},vals={int(llm['val_a'])}{int(llm['val_b'])})",
                      flush=True)
                _save(checkpoint, results)
            if stopped:
                break
        if stopped:
            break

    return results, stopped


def _save(path: Path, results: list[dict]):
    json.dump({"results": results}, open(path, "w", encoding="utf-8"), indent=2)


def summarize(results: list[dict]) -> dict:
    cells: dict[int, dict] = {}
    for r in results:
        n = r["N"]
        c = cells.setdefault(n, {"n": 0, "ours": 0, "llm": 0, "llm_lenient": 0,
                                 "ours_flagged_any": 0, "ours_masked": 0,
                                 "ours_iso": 0})
        c["n"] += 1
        c["ours"] += int(r["ours"]["detected"])
        c["ours_flagged_any"] += int(r["ours"]["flagged"])
        c["ours_masked"] += int(r["ours"].get("masked_wrong_pair", False))
        c["ours_iso"] += int(r["ours"].get("iso_detected", False))
        c["llm"] += int(r["llm"]["detected"])
        c["llm_lenient"] += int(r["llm"]["lenient_both_values"])
    table = {}
    for n in sorted(cells):
        c = cells[n]
        table[n] = {
            "n_haystacks": c["n"],
            "ours_recall": round(c["ours"] / c["n"], 3),
            "ours_flagged_any_rate": round(c["ours_flagged_any"] / c["n"], 3),
            "ours_masked_wrong_pair_rate": round(c["ours_masked"] / c["n"], 3),
            "ours_pair_detectable_in_isolation_rate": round(c["ours_iso"] / c["n"], 3),
            "llm_recall": round(c["llm"] / c["n"], 3),
            "llm_recall_lenient": round(c["llm_lenient"] / c["n"], 3),
        }
    return table


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    if args.smoke:
        conflicts = ["C1_probation"]
        n_values = [2, 10, 40]
        out_name = args.out or "haystack_results_smoke.json"
    elif args.full:
        conflicts = list(CONFLICTS.keys())
        n_values = N_VALUES
        out_name = args.out or "haystack_results.json"
    else:
        ap.error("specify --smoke or --full")

    t0 = time.time()
    results, stopped = run(conflicts, n_values, out_name)
    table = summarize(results)
    payload = json.load(open(OUT / out_name, encoding="utf-8"))
    payload["summary"] = table
    payload["meta"] = {
        "stopped_early": stopped,
        "elapsed_sec": round(time.time() - t0, 1),
        "n_haystacks": len(results),
    }
    json.dump(payload, open(OUT / out_name, "w", encoding="utf-8"), indent=2)

    print("\n" + "=" * 56)
    print("RECALL vs N" + ("  (PARTIAL)" if stopped else ""))
    print("=" * 56)
    print(f"{'N':>4} {'#hay':>5} {'ours':>7} {'llm':>7} {'llm(len)':>9}")
    for n, row in table.items():
        print(f"{n:>4} {row['n_haystacks']:>5} {row['ours_recall']:>7.2f} "
              f"{row['llm_recall']:>7.2f} {row['llm_recall_lenient']:>9.2f}")
    print(f"\nWrote {OUT / out_name} ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
