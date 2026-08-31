"""
llm_baseline_corpus3.py — Bare-LLM baseline on Corpus 3.

Why this exists
---------------
docs/PREREGISTRATION_CORPUS3.md registers a bare-LLM arm, but
evaluation/adversarial_baseline_probe.py cannot supply it: that script is
hardcoded to Corpus 1/2 and measures something different (injection leakage on
12 hand-picked adversarial gap probes -- the source of CLAUDE.md's "12/12
unsafe"). Without this module, the Corpus 3 safety comparison runs only against
trivial policies (always-answer / always-abstain / retrieval-threshold), none of
which is a system anyone would actually build.

This is the honest comparison: **the same retrieved evidence, the same task, no
deterministic validation layer.** The difference between this arm and the full
system is exactly what Stages 0-5 buy on held-out data.

What is held constant
---------------------
* Retrieval: identical stores, identical top_k, via harness.setup().
* Prompt: BASELINE_SYSTEM / BASELINE_USER_TMPL copied VERBATIM from
  experiments/baseline_experiment.py (asserted at runtime where importable), so
  this is the same baseline the paper already reports for Corpus 1/2 -- not a
  new, weaker strawman written after seeing results.
* Scoring: harness.metrics(), the same function that scores the real system.

Costs Groq tokens (one call per query). Needs GROQ_API_KEY.

    python evaluation/llm_baseline_corpus3.py --split test --tag c3_llm
    python evaluation/llm_baseline_corpus3.py --split test --limit 100 --qdrant-root qdrant_db_c3_copy
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import time
from pathlib import Path

import harness_bootstrap  # noqa: F401  (adds this dir to sys.path)
from harness import CORPORA, load_queries, metrics, setup

OUT_DIR = Path(__file__).resolve().parent / "results"

# MODEL SUBSTITUTION -- must be disclosed alongside any comparison to the
# published Corpus 1/2 baseline.
#
# experiments/baseline_experiment.py used "llama-3.3-70b-versatile". Groq has
# since decommissioned it (404 model_not_found, verified 2026-08-31), so the
# Corpus 1/2 baseline is NOT reproducible as published and this arm cannot be
# model-identical to it.
#
# openai/gpt-oss-120b is chosen because it is this project's OWN current
# production model (llm_interface.py:53). That arguably makes the comparison
# cleaner than the original: the baseline now runs the same LLM the system uses
# for synthesis, so the only difference between the two arms is the
# deterministic validation layer -- which is exactly the quantity of interest.
GROQ_MODEL = "openai/gpt-oss-120b"

# Copied verbatim from experiments/baseline_experiment.py (lines 83-99).
# Parity with the published Corpus 1/2 baseline is the entire point; see
# _assert_prompt_parity below.
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

BASELINE_USER_TMPL = (
    "Context passages:\n{chunks}\n\n"
    "Question: {query}\n\n"
    "Answer (remember: exactly INSUFFICIENT if not present; start with CONFLICT if "
    "two passages disagree on the asked fact):"
)


def _assert_prompt_parity() -> str:
    """
    Verify the prompt matches the published Corpus 1/2 baseline.

    If experiments/baseline_experiment.py is importable, its constants win and a
    mismatch is fatal -- a silently divergent prompt would make the Corpus 3
    baseline incomparable to the numbers already in the paper. If it will not
    import (it has heavy module-level side effects), fall back to the verbatim
    copies above and say so.
    """
    try:
        import sys
        root = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(root / "experiments"))
        import baseline_experiment as be  # type: ignore
        if be.BASELINE_SYSTEM != BASELINE_SYSTEM or be.BASELINE_USER_TMPL != BASELINE_USER_TMPL:
            raise SystemExit(
                "Prompt drift: experiments/baseline_experiment.py no longer matches "
                "this module's copy. Reconcile before running -- otherwise the "
                "Corpus 3 baseline is not comparable to the published Corpus 1/2 one."
            )
        return "verified against experiments/baseline_experiment.py"
    except SystemExit:
        raise
    except Exception as exc:  # import failed; copies stand
        return f"unverified (could not import baseline_experiment: {type(exc).__name__})"


def build_context_block(chunks: list) -> str:
    """Number each passage and label it with its source, as the paper's baseline does."""
    parts = []
    for i, c in enumerate(chunks, 1):
        parts.append(f"[Passage {i}] (source: {c.get('source','?')})\n{c.get('text','')}")
    return "\n\n".join(parts)


def classify(reply: str) -> str:
    """
    Map the LLM's free text onto the three decisions harness.metrics() scores.

    Deliberately generous to the baseline: any leading CONFLICT marker counts as
    a conflict call, and a bare INSUFFICIENT anywhere in a short reply counts as
    an abstention. Being strict here would inflate the system's advantage.
    """
    text = (reply or "").strip()
    if not text:
        # An empty completion is a FAILED call, not an abstention. Scoring it as
        # `insufficient` would credit the baseline with a safe refusal it never
        # made, inflating its safety numbers -- the exact direction that would
        # flatter this project's own system by comparison. Surfaced as an error.
        return "__EMPTY__"
    upper = text.upper()
    if re.match(r"^\W*CONFLICT\b", upper):
        return "conflict"
    if re.match(r"^\W*INSUFFICIENT\b", upper):
        return "insufficient"
    if len(text) < 40 and "INSUFFICIENT" in upper:
        return "insufficient"
    if "CONFLICT" in upper[:80]:
        return "conflict"
    return "answer"


def call_groq(client, system_prompt: str, user_message: str, retries: int = 5) -> str:
    """One chat call with backoff on rate limits / transient errors."""
    delay = 2.0
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.0,
                # gpt-oss-120b is a reasoning model: it emits reasoning tokens
                # into a separate field that still consume the completion budget.
                # At 400 a long NDA context could exhaust the budget before any
                # answer was produced, returning empty content with
                # finish_reason="length" -- measured on the smoke run.
                max_tokens=1500,
            )
            choice = resp.choices[0]
            content = (choice.message.content or "").strip()
            if not content:
                return f"__ERROR__ empty content (finish_reason={choice.finish_reason})"
            return content
        except Exception as exc:
            if attempt == retries - 1:
                return f"__ERROR__ {type(exc).__name__}: {exc}"
            time.sleep(delay + random.uniform(0, 1))
            delay = min(delay * 2, 30)
    return "__ERROR__ exhausted"


def repoint_stores(qdrant_root: str) -> int:
    """Read from an alternate store root so this can run beside another eval."""
    n = 0
    for key, cfg in CORPORA.items():
        if key.startswith("3-"):
            cfg["qdrant"] = f"{qdrant_root}/{key.removeprefix('3-')}"
            n += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test"], required=True)
    ap.add_argument("--tag", default="c3_llm")
    ap.add_argument("--queries", default="queries.json")
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--limit", type=int, default=None,
                    help="cap total queries (stratified across bundles) to bound cost")
    ap.add_argument("--qdrant-root", default=None)
    args = ap.parse_args()

    if not os.getenv("GROQ_API_KEY"):
        env = Path(__file__).resolve().parent.parent / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.startswith("GROQ_API_KEY="):
                    os.environ["GROQ_API_KEY"] = line.split("=", 1)[1].strip()
    if not os.getenv("GROQ_API_KEY"):
        raise SystemExit("GROQ_API_KEY not set (checked environment and .env).")

    from groq import Groq
    client = Groq(api_key=os.environ["GROQ_API_KEY"])

    parity = _assert_prompt_parity()
    if args.qdrant_root:
        print(f"  (reading {repoint_stores(args.qdrant_root)} stores from {args.qdrant_root})")

    import qdrant_retrieval
    import retrieval_interface

    names = sorted(k for k in CORPORA if k.startswith(f"3-{args.split}-"))
    if not names:
        raise SystemExit(f"no corpus-3 bundles for split {args.split}")

    # Spread the cap across bundles, but never run more than --limit in total:
    # a naive ceil-per-bundle turned "--limit 3" into 30 queries (1 x 30 bundles).
    per_bundle_cap = None
    if args.limit:
        if args.limit < len(names):
            names = names[: args.limit]
            per_bundle_cap = 1
        else:
            per_bundle_cap = max(1, args.limit // len(names))

    print(f"model  : {GROQ_MODEL}")
    print(f"prompt : {parity}")
    print(f"bundles: {len(names)}  | per-bundle cap: {per_bundle_cap or 'all'}\n")

    records: list = []
    errors = 0
    t0 = time.time()

    for bi, name in enumerate(names, 1):
        # _get_client caches one client and ignores qdrant_dir once open
        # (qdrant_retrieval.py:118); reset per bundle or every store after the
        # first would silently be bundle 0's.
        qdrant_retrieval._close_client()
        qdrant_retrieval._published_registry_dir = None
        setup(name)

        queries = load_queries(name, args.queries)
        if per_bundle_cap:
            queries = queries[:per_bundle_cap]

        for q in queries:
            chunks = retrieval_interface._qdrant_retrieve(q["query"], top_k=args.top_k)
            reply = call_groq(
                client, BASELINE_SYSTEM,
                BASELINE_USER_TMPL.format(chunks=build_context_block(chunks),
                                          query=q["query"]),
            )
            observed = classify(reply)
            if reply.startswith("__ERROR__") or observed == "__EMPTY__":
                errors += 1
                # Excluded from scoring rather than guessed at: a failed call is
                # missing data, and silently mapping it to any decision would
                # bias the comparison.
                continue
            records.append({
                "id": q["id"],
                "bundle": name,
                "query": q["query"],
                "expected": q["expected_decision"],
                "expected_conflict_pair": q.get("expected_conflict_pair"),
                "conflict_pair": None,
                "observed": observed,
                "match": observed == q["expected_decision"],
                "reply": reply[:600],
            })
        print(f"[{bi}/{len(names)}] {name}: {len(queries)} queries "
              f"({len(records)} total, {errors} errors)", flush=True)

    m = metrics(records)
    n_answer = sum(1 for r in records if r["expected"] == "answer")
    m["always_answer_floor_pct"] = round(100 * n_answer / len(records), 1) if records else None
    m["llm_errors"] = errors

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{args.tag}_corpus3_{args.split}.json"
    out.write_text(json.dumps({
        "meta": {"tag": args.tag, "split": args.split, "model": GROQ_MODEL,
                 "prompt_parity": parity, "queries_file": args.queries,
                 "top_k": args.top_k, "n": len(records),
                 "elapsed_s": round(time.time() - t0, 1)},
        "metrics": m,
        "results": records,
    }, indent=2), encoding="utf-8")

    print(f"\n=== bare-LLM baseline / corpus 3 / {args.split} ({len(records)} queries) ===")
    for k, v in m.items():
        if k in ("misattributed", "false_conflicts", "missed_conflicts", "gap_leaks"):
            continue
        print(f"  {k:26} {v}")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
