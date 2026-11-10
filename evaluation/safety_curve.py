"""
safety_curve.py — measure what zero unsafe answers costs.

The question this answers
-------------------------
"Never produce an unsafe answer" is not a bug to fix, it is an operating point
to choose. Eight candidate fixes for the false-conflict class have been
falsified and all eight conserved total error (`docs/STATUS.md`, Standing
Decision 1), so there is strong evidence no cost-free move exists. What has
never been measured is the *trade*: how many correct answers the system gives
up as it is made more cautious, and whether a zero-unsafe point exists at a
usable answer rate.

This script sweeps one conservatism dial and reports, at each point, the unsafe
answer count against the answer rate. It is a **measurement, not a filter**: it
adds no rule, names no individual query, and changes no default. Per the
Overfitting Test in `CLAUDE.md`, nothing here is derived from looking at a
query it would fix.

What the dial is, and what it is not
------------------------------------
`c` scales the three env-overridable Stage 5 sufficiency gates together:

    MIN_FOCUS_PRESENCE            0.50 * c   (hard veto, H5)
    MIN_QUERY_COVERAGE            0.55 * c   (quality branch, H4)
    MIN_AVG_SCORE_FOR_SUFFICIENCY 0.65 * c   (quality branch, H2)

`c = 1.0` is the shipped default exactly. Raising `c` makes every one of them
harder to satisfy, so the system answers less and abstains more; all three move
the same way, which is what makes one dial meaningful at all.

**Deliberately excluded, and why:**

- `ANSWERHOOD_MARGIN` is **non-monotone**. Larger values suppress fewer
  conflict pairs, so they raise more conflicts, but `0` does not continue that
  trend: it disables the gate entirely (`validation.py`, `if ANSWERHOOD_MARGIN
  > 0.0`) and raises the most conflicts of all. A scalar passing through zero
  would silently invert the dial's meaning.
- `NLI_CONFLICT_THRESHOLD` and the other Stage 4 knobs control
  conflict-versus-answer, which is the space Standing Decision 1 closes. This
  dial deliberately moves only answer-versus-insufficient, which is where the
  unsafe answers actually come from: gap queries answered instead of refused.
- `MIN_CHUNKS_FOR_SUFFICIENCY` is hardcoded at 1 in `validation.py`, not
  env-overridable, so it cannot be swept without a pipeline change.

**Known weakness, to be stated wherever this curve is reported:** the three
gates are not commensurable. One is a presence fraction over the rarest half of
the query's terms, one a coverage fraction over all content terms, one a mean
retrieval score. Scaling them by a common factor is a convenience that keeps
the result plottable, not a principled parameterisation. If the curve comes out
non-monotonic, suspect the dial before concluding anything about the system.

Sealed data
-----------
This script refuses any sealed split. Sweeping a dial over a sealed test set and
reading off the best point is precisely how a test set becomes a training set,
which `CLAUDE.md` names as the thing that destroys the project's only external
evidence. Allowed: Corpus 1, Corpus 2, Corpus 3 **dev**. Refused: Corpus 3
test, RAMDocs, MultiHop-RAG. Those are for one pass at a point chosen here,
decided by the owner, at the end.

Why each point is a fresh process
---------------------------------
`validation.py` reads its thresholds from the environment at **import** time.
Sweeping in-process would import once and measure the default at every point.
Each point therefore runs `run_eval.py` as a subprocess with its own
environment.

The retrieval cache is deliberately **not** cleared between points: the dial
moves Stage 5 only, which runs after retrieval, so every point retrieves
identically and a warm cache changes nothing but the runtime. (Contrast
`rerun_suite.py --trace-compare`, where cold arms are required because the
thing under test could in principle have perturbed retrieval.)

Usage
-----
    python evaluation/safety_curve.py --corpus 1
    python evaluation/safety_curve.py --corpus 1,2 --tag sc1
    python evaluation/safety_curve.py --corpus 3-dev --points 0.5,1.0,1.5

Writes `evaluation/results/safety_curve_<tag>.json` and
`evaluation/results/safety_curve_<tag>.md`.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "evaluation" / "results"
PY = sys.executable

# Shipped defaults, read from validation.py's own literals. Kept here as the
# c = 1.0 anchor; if a default changes in validation.py this table must be
# updated with it, and the mismatch check below will catch it.
BASE = {
    "RAG_MIN_FOCUS_PRESENCE": 0.5,
    "RAG_MIN_QUERY_COVERAGE": 0.55,
    "RAG_MIN_AVG_SCORE_FOR_SUFFICIENCY": 0.65,
}

DEFAULT_POINTS = (0.0, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0)

# Corpus 1 and 2 go through run_eval.py; Corpus 3 dev through its own runner.
# Nothing else is reachable from here.
ALLOWED = {
    "1":     ([PY, "evaluation/run_eval.py", "--corpus", "1"], "corpus1"),
    "2":     ([PY, "evaluation/run_eval.py", "--corpus", "2"], "corpus2"),
    "3-dev": ([PY, "evaluation/run_eval_corpus3.py", "--split", "dev"], "corpus3_dev"),
}
SEALED_HINT = {
    "3": "Corpus 3 test is sealed (opened once, 2026-08-31). Use 3-dev.",
    "3-test": "Corpus 3 test is sealed (opened once, 2026-08-31). Use 3-dev.",
    "ramdocs": "RAMDocs was sealed after the clean recalculation (2026-10-14).",
    "multihop": "MultiHop-RAG was sealed after the preregistered run (2026-10-17).",
}


def env_for(c: float) -> dict:
    """The environment overrides for one point on the dial.

    Fractions are clamped to 1.0: a threshold above 1.0 is unreachable rather
    than merely strict, and clamping keeps the high end of the curve meaning
    "as strict as this gate can be" instead of an arbitrary number.
    """
    return {k: "%.6f" % min(1.0, v * c) for k, v in BASE.items()}


def check_defaults() -> list[str]:
    """Verify BASE still matches validation.py, with no RAG_* in the shell.

    A stale anchor would silently relabel the curve: every point would be
    plotted against the wrong c.
    """
    problems = []
    stray = {k: v for k, v in os.environ.items() if k.startswith("RAG_")}
    if stray:
        problems.append("RAG_* set in this shell: %s" % stray)
    out = subprocess.run(
        [PY, "-c",
         "import json, validation as v; print(json.dumps({"
         "'RAG_MIN_FOCUS_PRESENCE': v.MIN_FOCUS_PRESENCE,"
         "'RAG_MIN_QUERY_COVERAGE': v.MIN_QUERY_COVERAGE,"
         "'RAG_MIN_AVG_SCORE_FOR_SUFFICIENCY': v.MIN_AVG_SCORE_FOR_SUFFICIENCY}))"],
        cwd=str(ROOT), capture_output=True, text=True,
        env={**os.environ, "PYTHONUTF8": "1"})
    if out.returncode != 0:
        problems.append("could not read validation.py defaults: %s"
                        % (out.stderr or "").strip()[-300:])
        return problems
    live = json.loads(out.stdout.strip().splitlines()[-1])
    for k, want in BASE.items():
        if abs(live.get(k, -1) - want) > 1e-9:
            problems.append("BASE[%s]=%s but validation.py has %s"
                            % (k, want, live.get(k)))
    return problems


def run_point(argv_base: list[str], tag: str, c: float, log_dir: Path) -> tuple[int, Path]:
    """Run one sweep point in its own process. Returns (exit code, result path)."""
    point_tag = "%s_c%s" % (tag, ("%.2f" % c).replace(".", "p"))
    argv = argv_base + ["--tag", point_tag, "--quiet"]
    env = {**os.environ, "PYTHONUTF8": "1", **env_for(c)}
    log = log_dir / (point_tag + ".log")
    with open(log, "w", encoding="utf-8", errors="replace") as lf:
        lf.write("# cmd: %s\n# overrides: %s\n\n" % (" ".join(argv), env_for(c)))
        lf.flush()
        p = subprocess.run(argv, cwd=str(ROOT), env=env, stdout=lf,
                           stderr=subprocess.STDOUT)
    # run_eval.py writes <tag>_corpus<N>.json; run_eval_corpus3.py its own name.
    candidates = sorted(RESULTS.glob(point_tag + "*.json"))
    return p.returncode, (candidates[0] if candidates else log)


def summarise(path: Path) -> dict:
    """Pull the curve's quantities out of one result file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    m = data.get("metrics", {})
    records = data.get("results", [])
    n = len(records) or 1
    answered = sum(1 for r in records if r.get("observed") == "answer")
    # "unsafe_answers" is reported by harness.metrics() as "k/total".
    unsafe = m.get("unsafe_answers")
    unsafe_n = None
    if isinstance(unsafe, str) and "/" in unsafe:
        unsafe_n = int(unsafe.split("/")[0])
    elif isinstance(unsafe, int):
        unsafe_n = unsafe
    over = sum(1 for r in records
               if r.get("expected") == "answer" and r.get("observed") != "answer")
    return {
        "n": len(records),
        "accuracy_n": m.get("accuracy"),
        "accuracy_pct": round(100.0 * (m.get("accuracy") or 0) / n, 1)
                        if isinstance(m.get("accuracy"), int) else None,
        "answered": answered,
        "answer_rate_pct": round(100.0 * answered / n, 1),
        "unsafe": unsafe_n,
        "unsafe_raw": unsafe,
        "gap_leaks": len(m.get("gap_leaks") or []),
        "over_abstentions": over,
        "conflict_recall": m.get("conflict_recall"),
        "conflict_precision": m.get("conflict_precision"),
        "false_conflicts": len(m.get("false_conflicts") or []),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True,
                    help="comma-separated, from %s" % ",".join(ALLOWED))
    ap.add_argument("--points", default=",".join(str(p) for p in DEFAULT_POINTS),
                    help="comma-separated conservatism values; 1.0 is the shipped default")
    ap.add_argument("--tag", default=datetime.date.today().isoformat())
    args = ap.parse_args()

    wanted = [c.strip() for c in args.corpus.split(",") if c.strip()]
    for c in wanted:
        if c.lower() in SEALED_HINT:
            print("REFUSING TO RUN: %s" % SEALED_HINT[c.lower()])
            print("Sweeping a dial over a sealed split and reading off the best "
                  "point turns it into a training set.")
            return 2
        if c not in ALLOWED:
            print("REFUSING TO RUN: --corpus must be from %s, got %r"
                  % (",".join(ALLOWED), c))
            return 2

    try:
        points = [float(p) for p in args.points.split(",") if p.strip()]
    except ValueError:
        print("REFUSING TO RUN: --points must be numbers, got %r" % args.points)
        return 2
    if not points:
        print("REFUSING TO RUN: no points given")
        return 2

    problems = check_defaults()
    if problems:
        print("REFUSING TO RUN:")
        for p in problems:
            print("  - %s" % p)
        return 2

    log_dir = RESULTS / ("safety_curve_" + args.tag)
    log_dir.mkdir(parents=True, exist_ok=True)

    rows: dict[str, list] = {}
    for corpus in wanted:
        argv_base, tag = ALLOWED[corpus]
        rows[corpus] = []
        for c in points:
            print("[%s] corpus %s  c=%.2f  %s"
                  % (datetime.datetime.now().isoformat(timespec="seconds"),
                     corpus, c, env_for(c)), flush=True)
            t0 = time.time()
            rc, path = run_point(argv_base, tag, c, log_dir)
            secs = round(time.time() - t0, 1)
            if rc != 0 or not path.name.endswith(".json"):
                print("    FAILED (exit %s); see %s" % (rc, path), flush=True)
                rows[corpus].append({"c": c, "error": "exit %s" % rc,
                                     "seconds": secs})
                continue
            s = summarise(path)
            s.update({"c": c, "seconds": secs, "file": path.name,
                      "overrides": env_for(c)})
            rows[corpus].append(s)
            print("    answered %s/%s (%.1f%%)  unsafe %s  acc %s  over-abstain %s  (%ss)"
                  % (s["answered"], s["n"], s["answer_rate_pct"], s["unsafe"],
                     s["accuracy_n"], s["over_abstentions"], secs), flush=True)

    out_json = RESULTS / ("safety_curve_%s.json" % args.tag)
    out_json.write_text(json.dumps({
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "base_defaults": BASE,
        "points": points,
        "note": ("c scales the three Stage 5 sufficiency gates together; c=1.0 "
                 "is the shipped default. The gates are not commensurable, so "
                 "treat c as a convenience axis, not a calibrated parameter."),
        "curves": rows,
    }, indent=2), encoding="utf-8")

    L = ["# Safety-utility curve", "",
         "Generated: %s" % datetime.datetime.now().isoformat(timespec="seconds"), "",
         "`c` scales the three Stage 5 sufficiency gates together "
         "(`MIN_FOCUS_PRESENCE` 0.50, `MIN_QUERY_COVERAGE` 0.55, "
         "`MIN_AVG_SCORE_FOR_SUFFICIENCY` 0.65). **`c = 1.0` is the shipped "
         "default.** Higher `c` abstains more.", "",
         "The three gates are not commensurable (a presence fraction, a "
         "coverage fraction and a mean retrieval score), so `c` is a "
         "convenience axis, not a calibrated parameter. A non-monotonic curve "
         "is more likely to be the dial than the system.", ""]
    for corpus, data in rows.items():
        L += ["## Corpus %s" % corpus, "",
              "| c | answered | answer rate | unsafe | gap leaks | accuracy | "
              "over-abstentions | conflict recall | false conflicts |",
              "|---|---|---|---|---|---|---|---|---|"]
        for r in data:
            if "error" in r:
                L.append("| %.2f | %s | | | | | | | |" % (r["c"], r["error"]))
                continue
            L.append("| %.2f | %s/%s | %.1f%% | %s | %s | %s | %s | %s | %s |" % (
                r["c"], r["answered"], r["n"], r["answer_rate_pct"], r["unsafe"],
                r["gap_leaks"], r["accuracy_n"], r["over_abstentions"],
                r["conflict_recall"], r["false_conflicts"]))
        L.append("")
    out_md = RESULTS / ("safety_curve_%s.md" % args.tag)
    out_md.write_text("\n".join(L) + "\n", encoding="utf-8")

    print("")
    print("Wrote %s" % out_json)
    print("Wrote %s" % out_md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
