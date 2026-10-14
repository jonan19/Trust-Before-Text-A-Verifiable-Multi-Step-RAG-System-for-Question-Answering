"""
sweep_tables.py: reproduce the threshold-sensitivity (Table 4) and component
ablation (Table 5) rows of the NLPIR paper, end to end, with environment
switches only (no code is changed).

Each setting runs evaluation/run_eval.py under the stated RAG_* overrides on the
named corpora (decision only, zero LLM tokens) and the result is compared with
the value printed in the paper. A DIFF is a finding, never a target: nothing
here selects or tunes anything.

Resumable: a setting whose result file exists is skipped. Never run alongside
another harness (one process per Qdrant store).

    python evaluation/sweep_tables.py            # run what is missing, then report
    python evaluation/sweep_tables.py --report   # only rebuild the summary
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RESULTS = HERE / "results"

DEFAULT = ((96.2, 1.000, 16, 0), (89.7, 0.875, 14, 1))   # paper default row (C1, C2)


def S(key, env, c1=None, c2=None, group=""):
    """One setting. c1 / c2: (acc_pct or [lo, hi], precision, true positives, unsafe) or None."""
    return {"key": key, "env": env, "group": group, "expect": {"1": c1, "2": c2}}


D1, D2 = DEFAULT
SETTINGS = [
    S("default", {}, D1, D2, "reference"),
    # --- Table 4: threshold sensitivity -----------------------------------------
    S("nli_080", {"RAG_NLI_CONFLICT_THRESHOLD": "0.80"}, D1, D2, "T4 NLI cutoff"),
    S("nli_099", {"RAG_NLI_CONFLICT_THRESHOLD": "0.99"}, D1, D2, "T4 NLI cutoff"),
    S("avg_055", {"RAG_MIN_AVG_SCORE_FOR_SUFFICIENCY": "0.55"}, D1, D2, "T4 avg-score floor"),
    S("avg_068", {"RAG_MIN_AVG_SCORE_FOR_SUFFICIENCY": "0.68"}, (94.9, 1.0, 16, 0), (88.5, 0.875, 14, 1), "T4 avg-score floor"),
    S("avg_070", {"RAG_MIN_AVG_SCORE_FOR_SUFFICIENCY": "0.70"}, (93.6, 1.0, 16, 0), (87.2, 0.875, 14, 1), "T4 avg-score floor"),
    S("avg_075", {"RAG_MIN_AVG_SCORE_FOR_SUFFICIENCY": "0.75"}, (93.6, 1.0, 16, 0), (87.2, 0.875, 14, 1), "T4 avg-score floor"),
    S("cov_035", {"RAG_MIN_QUERY_COVERAGE": "0.35"}, (96.2, 1.0, 16, 1), ([89.7, 91.0], 0.875, 14, 1), "T4 coverage floor"),
    S("cov_050", {"RAG_MIN_QUERY_COVERAGE": "0.50"}, (96.2, 1.0, 16, 1), ([89.7, 91.0], 0.875, 14, 1), "T4 coverage floor"),
    S("cov_065", {"RAG_MIN_QUERY_COVERAGE": "0.65"}, D1, D2, "T4 coverage floor"),
    S("cov_075", {"RAG_MIN_QUERY_COVERAGE": "0.75"}, (89.7, 1.0, 16, 0), (85.9, 0.875, 14, 1), "T4 coverage floor"),
    S("am_0", {"RAG_ANSWERHOOD_MARGIN": "0"}, (96.2, 1.0, 16, 0), (82.1, 0.625, 15, 1), "T4 answerhood margin / T5 no query conditioning"),
    S("am_3", {"RAG_ANSWERHOOD_MARGIN": "3"}, (94.9, 1.0, 15, 1), None, "T4 answerhood margin"),
    S("am_4", {"RAG_ANSWERHOOD_MARGIN": "4"}, (94.9, 1.0, 15, 1), (89.7, 0.875, 14, 1), "T4 answerhood margin"),
    S("am_5", {"RAG_ANSWERHOOD_MARGIN": "5"}, (96.2, 1.0, 16, 0), None, "T4 answerhood margin"),
    S("am_7", {"RAG_ANSWERHOOD_MARGIN": "7"}, (96.2, 1.0, 16, 0), (88.5, 0.824, 14, 1), "T4 answerhood margin"),
    S("am_8", {"RAG_ANSWERHOOD_MARGIN": "8"}, (96.2, 1.0, 16, 0), None, "T4 answerhood margin"),
    S("qs_0", {"RAG_QUERY_SPAN_RELEVANCE": "0"}, (94.9, 0.941, 16, 0), (89.7, 0.875, 14, 1), "T4 query-span floor / T5 no query-span gate"),
    S("qs_025", {"RAG_QUERY_SPAN_RELEVANCE": "0.25"}, (94.9, 0.941, 16, 0), (89.7, 0.875, 14, 1), "T4 query-span floor"),
    S("qs_030", {"RAG_QUERY_SPAN_RELEVANCE": "0.30"}, (94.9, 0.941, 16, 0), None, "T4 query-span floor"),
    S("qs_040", {"RAG_QUERY_SPAN_RELEVANCE": "0.40"}, (96.2, 1.0, 16, 0), None, "T4 query-span floor"),
    S("qs_045", {"RAG_QUERY_SPAN_RELEVANCE": "0.45"}, (96.2, 1.0, 16, 0), (87.2, 0.923, 12, 3), "T4 query-span floor"),
    S("lex_060", {"RAG_CONFLICT_SIM_THRESHOLD": "0.60"}, (96.2, 1.0, 16, 0), None, "T4 lexical gate (C1 only)"),
    S("lex_076", {"RAG_CONFLICT_SIM_THRESHOLD": "0.76"}, (96.2, 1.0, 16, 0), None, "T4 lexical gate (C1 only)"),
    # --- Table 5: component ablations (those reachable by an existing switch) ----
    S("abl_noconflict", {"RAG_NLI_CONFLICT_THRESHOLD": "2.0", "RAG_CONFLICT_SIM_THRESHOLD": "2.0"},
      (75.6, None, 0, 16), (73.1, None, 0, 13), "T5 no conflict detection"),
    S("abl_ruleonly", {"RAG_NLI_CONFLICT_THRESHOLD": "2.0"}, (92.3, 1.0, 13, 3), (79.5, 0.833, 5, 10), "T5 rule-only detector (NLI off)"),
    S("abl_nlionly", {"RAG_CONFLICT_SIM_THRESHOLD": "2.0"}, D1, D2, "T5 NLI-only detector"),
    S("abl_suff_pq_off", {"RAG_MIN_FOCUS_PRESENCE": "0", "RAG_MIN_CHUNKS_FOR_AVG_SUFFICIENCY": "1"},
      (93.6, 1.0, 16, 3), (84.6, 0.875, 14, 8), "T5 sufficiency presence + quality off"),
    S("abl_nopresence", {"RAG_MIN_FOCUS_PRESENCE": "0"}, (96.2, 1.0, 16, 1), (91.0, 0.875, 14, 2), "T5 no presence check"),
    S("abl_noquality", {"RAG_MIN_CHUNKS_FOR_AVG_SUFFICIENCY": "1"}, D1, D2, "T5 sufficiency quality (n>=2) off"),
    S("abl_anchor_either", {"RAG_ANCHOR_REQUIRE_BOTH": "0"}, D1, D2, "T5 anchor: either sentence"),
    S("abl_noassertive", {"RAG_REQUIRE_ASSERTIVE_SPANS": "0"}, D1, (88.5, 0.824, 14, 1), "T5 no assertive-span filter"),
]

NOT_REPRODUCIBLE = ["T5 'Paragraph-level NLI (answerhood off)': no existing switch joins a chunk's "
                    "query-relevant sentences into one span, so it is not reproduced here."]


C1_ONLY = ("lex_",)                                   # paper sweeps the lexical gate on Corpus 1 only
NO_C2_VALUE = ("am_3", "am_5", "am_8", "qs_030", "qs_040")  # paper prints no Corpus 2 value for these


def wanted(setting: dict, corpus: str) -> bool:
    key = setting["key"]
    if corpus == "2" and (key.startswith(C1_ONLY) or key in NO_C2_VALUE):
        return False
    return True


def result_path(key: str, corpus: str) -> Path:
    return RESULTS / f"sweep_{key}_corpus{corpus}.json"


def run_one(setting: dict, corpus: str) -> None:
    env = {k: v for k, v in os.environ.items() if not k.startswith("RAG_")}
    env.update(setting["env"])
    env["PYTHONUTF8"] = "1"
    log = RESULTS / f"sweep_{setting['key']}_corpus{corpus}.log"
    with open(log, "w", encoding="utf-8", errors="replace") as lf:
        rc = subprocess.run([sys.executable, str(HERE / "run_eval.py"), "--corpus", corpus,
                             "--tag", f"sweep_{setting['key']}", "--quiet"],
                            cwd=str(ROOT), env=env, stdout=lf, stderr=subprocess.STDOUT).returncode
    if rc != 0 or not result_path(setting["key"], corpus).exists():
        print(f"  !! {setting['key']} corpus {corpus} failed (exit {rc}); see {log.name}", flush=True)


def observed(m: dict) -> tuple:
    return (m["accuracy_pct"], m["conflict_precision"], m["conflict_tp"],
            int(str(m["unsafe_answers"]).split("/")[0]))


def judge(obs: tuple, exp) -> str:
    if exp is None:
        return "no paper value"
    acc, prec, tp, uns = exp
    ok_acc = (acc[0] - 0.06 <= obs[0] <= acc[1] + 0.06) if isinstance(acc, list) else abs(obs[0] - acc) <= 0.06
    ok_prec = True if prec is None else abs(obs[1] - prec) <= 0.0011
    return "MATCH" if (ok_acc and ok_prec and obs[2] == tp and obs[3] == uns) else "DIFF"


def report() -> tuple[int, int, int, int]:
    lines = ["# Table 4 and 5 reproduction (auto-generated)", "",
             "| group | setting | corpus | observed (acc %, precision, TP, unsafe) | paper | verdict |",
             "|---|---|---|---|---|---|"]
    counts = {"MATCH": 0, "DIFF": 0, "no paper value": 0, "missing": 0}
    for s in SETTINGS:
        for corpus in ("1", "2"):
            if not wanted(s, corpus):
                continue
            p = result_path(s["key"], corpus)
            exp = s["expect"][corpus]
            if not p.exists():
                counts["missing"] += 1
                lines.append(f"| {s['group']} | {s['key']} | C{corpus} | (not run) | {exp} | missing |")
                continue
            m = json.loads(p.read_text(encoding="utf-8"))["metrics"]
            obs = observed(m)
            v = judge(obs, exp)
            counts[v] += 1
            lines.append(f"| {s['group']} | {s['key']} | C{corpus} | {obs} | {exp} | {v} |")
    lines += ["", "**%d MATCH, %d DIFF, %d without a printed paper value, %d not run.**" % (
        counts["MATCH"], counts["DIFF"], counts["no paper value"], counts["missing"]), ""]
    lines += NOT_REPRODUCIBLE
    (RESULTS / "sweep_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return counts["MATCH"], counts["DIFF"], counts["no paper value"], counts["missing"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    if not args.report:
        stray = {k: v for k, v in os.environ.items() if k.startswith("RAG_")}
        if stray:
            print("REFUSING TO RUN: RAG_* variables are set in this shell:", stray)
            return 2
        RESULTS.mkdir(exist_ok=True)
        total = sum(1 for s in SETTINGS for c in ("1", "2") if wanted(s, c))
        done = 0
        t0 = time.time()
        for s in SETTINGS:
            for corpus in ("1", "2"):
                if not wanted(s, corpus):
                    continue
                if result_path(s["key"], corpus).exists():
                    done += 1
                    continue
                print(f"[{time.strftime('%H:%M:%S')}] {s['key']} corpus {corpus} ({done + 1}/{total})", flush=True)
                run_one(s, corpus)
                done += 1
        print(f"runs finished in {round((time.time() - t0) / 60, 1)} min", flush=True)
    m, d, n, miss = report()
    print(f"SWEEP SUMMARY: {m} MATCH, {d} DIFF, {n} without a printed paper value, {miss} not run "
          f"(details in evaluation/results/sweep_summary.md)")
    return 0 if d == 0 and miss == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
