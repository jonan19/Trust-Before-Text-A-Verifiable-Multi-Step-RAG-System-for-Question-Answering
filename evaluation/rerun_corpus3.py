"""Resumable replication of the sealed Corpus 3 (ContractNLI) evaluation.

WHY THIS EXISTS. The raw c3_* result files from the 2026-08-31 sealed run are in
no git ref, so every Corpus 3 number in numbers.md section 3 is prose-only. This
replays the SAME frozen configuration (docs/PREREGISTRATION_CORPUS3.md) and
compares with what was reported.

GOVERNANCE. This is a replication, not a new use of the test split. It changes no
code, threshold or default, refuses to run if any RAG_* variable is set (as
run_eval_corpus3.py also does), and must never be used to select or tune
anything. A DIFF is a finding to explain, never a target. Zero LLM tokens: the
bare-LLM baseline (evaluation/llm_baseline_corpus3.py) needs an API key and is
deliberately not part of this.

Usage (repo root), same shape as evaluation/rerun_suite.py:
    python evaluation/rerun_corpus3.py            # start or resume
    python evaluation/rerun_corpus3.py --status
    python evaluation/rerun_corpus3.py --fresh    # ignore previous run

Never run alongside another harness: embedded Qdrant allows one process per store.
"""
import argparse
import datetime
import json
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rerun_suite as rs  # reuse its logging, state and hashing helpers

ROOT = rs.ROOT
RESULTS = rs.RESULTS
PY = rs.PY
POINTER = RESULTS / "rerun_c3_LATEST.txt"
EXPECTED_FILE = ROOT / "evaluation" / "expected_corpus3.json"

INGEST = (
    "import sys; sys.path.insert(0, 'evaluation'); import build_corpus3 as b, json; "
    "names = sorted(k for k in json.load(open('data_corpus3/bundles.json', encoding='utf-8'))"
    "['splits']['test']['bundles']); "
    "print('bundles:', len(names)); "
    "[(print(n, 'ingested', b.ingest_bundle(n), 'chunks; missing artifacts:', b.store_artifacts_ok(n), flush=True)) "
    "for n in names if b.store_artifacts_ok(n)]; "
    "bad = [n for n in names if b.store_artifacts_ok(n)]; "
    "print('stores incomplete:', bad); sys.exit(1 if bad else 0)"
)

# Each track runs in batches of BATCH bundles (about 30 minutes each on the
# reference machine) because run_eval_corpus3.py only saves when every bundle it
# was given has finished: one 3-hour step would lose everything if the machine
# were shut down. A batch that is interrupted restarts from its first bundle; a
# finished batch is never repeated. merge_corpus3_parts.py then rebuilds the
# single pooled file an unbatched run would have written.
BATCH = 5


def _test_bundles():
    path = ROOT / "data_corpus3" / "bundles.json"
    return sorted(json.loads(path.read_text(encoding="utf-8"))["splits"]["test"]["bundles"])


PARTS = [_test_bundles()[i:i + BATCH] for i in range(0, len(_test_bundles()), BATCH)]


def track_steps(key, tag, queries_file):
    steps = []
    for i, names in enumerate(PARTS, 1):
        argv = [PY, "evaluation/run_eval_corpus3.py", "--split", "test",
                "--tag", "%s__part%d" % (tag, i), "--bundles", ",".join(names), "--quiet"]
        if queries_file != "queries.json":
            argv += ["--queries", queries_file]
        steps.append(("%s_part%d" % (key, i), argv, True))
    steps.append(("%s_merge" % key,
                  [PY, "evaluation/merge_corpus3_parts.py", "--tag", tag, "--queries",
                   queries_file, "--parts", str(len(PARTS)), "--split", "test"], True))
    return steps


# (name, argv, critical)
STEPS = (
    [("ingest_test_stores", [PY, "-c", INGEST], True)]
    + track_steps("track_a", "c3_hypothesis", "queries.json")
    + [("track_a_ci", [PY, "evaluation/bootstrap_ci.py", "--tag", "c3_hypothesis",
                       "--split", "test"], False),
       ("track_a_attribution", [PY, "evaluation/span_attribution.py", "--tag",
                                "c3_hypothesis", "--split", "test"], False),
       ("baselines", [PY, "evaluation/baselines_corpus3.py", "--split", "test",
                      "--tag", "c3_baselines"], False)]
    + track_steps("track_b", "c3_open", "queries_open.json")
    + track_steps("qform", "c3_qform", "queries_qform.json")
    + [("collect", ["__collect__"], False)]
)


def pick_run_dir(fresh):
    RESULTS.mkdir(parents=True, exist_ok=True)
    if POINTER.exists() and not fresh:
        d = Path(POINTER.read_text(encoding="utf-8").strip())
        if d.exists():
            return d
    d = RESULTS / ("rerun_c3_" + datetime.date.today().isoformat())
    n = 1
    while d.exists() and fresh:
        n += 1
        d = RESULTS / ("rerun_c3_%s_%d" % (datetime.date.today().isoformat(), n))
    d.mkdir(parents=True, exist_ok=True)
    POINTER.write_text(str(d), encoding="utf-8")
    return d


def _dig(obj, dotted):
    for part in dotted.split("."):
        if isinstance(obj, dict) and part in obj:
            obj = obj[part]
        else:
            return "n/a"
    return obj


def _same(got, want):
    if isinstance(want, list):          # [value, tolerance]
        value, tol = want
        return isinstance(got, (int, float)) and abs(got - value) <= tol
    return str(got) == str(want)


def compare_rows(since=None, expected=None, results=None):
    """Compare each result file with expected_corpus3.json.
    Returns (rows, n_match, n_diff, n_missing); row = [group, item, want, got, verdict]."""
    exp = expected if expected is not None else json.loads(
        EXPECTED_FILE.read_text(encoding="utf-8"))
    folder = results if results is not None else RESULTS
    rows = []
    for group, spec in exp.items():
        if group.startswith("_"):
            continue
        f = folder / spec["file"]
        problem, data = None, None
        if not f.exists():
            problem = "NO FILE"
        elif since is not None and f.stat().st_mtime < since - 1:
            problem = "STALE (not written by this run)"
        else:
            data = json.loads(f.read_text(encoding="utf-8"))
            for part in spec["path"]:
                data = data.get(part, {}) if isinstance(data, dict) else {}
        for item, want in spec["values"].items():
            if problem:
                rows.append([group, item, want, "-", problem])
                continue
            got = _dig(data, item)
            rows.append([group, item, want, got, "MATCH" if _same(got, want) else "DIFF"])
    n_match = sum(r[4] == "MATCH" for r in rows)
    n_diff = sum(r[4] == "DIFF" for r in rows)
    return rows, n_match, n_diff, len(rows) - n_match - n_diff


def qform_report():
    """Prediction 6 of the preregistration: how many decisions does the qform
    rewrite change? Reported only; new information, no previously reported value."""
    a, b = RESULTS / "c3_hypothesis_corpus3_test.json", RESULTS / "c3_qform_corpus3_test.json"
    if not (a.exists() and b.exists()):
        return ["(qform comparison unavailable: a result file is missing)"]
    ja, rb = json.loads(a.read_text(encoding="utf-8")), json.loads(b.read_text(encoding="utf-8"))
    ma, mb = ja["metrics"], rb["metrics"]
    lines = ["| metric | hypothesis (Track A) | qform |", "|---|---|---|"]
    for k in ("accuracy", "accuracy_pct", "conflict_tp", "conflict_flagged",
              "conflict_precision", "conflict_recall", "attribution_precision",
              "gap_leak_count", "unsafe_answers", "always_answer_floor_pct"):
        lines.append("| %s | %s | %s |" % (k, ma.get(k, "n/a"), mb.get(k, "n/a")))
    # per-query decision flips, matched by position within each bundle
    ids_a = [(r["bundle"], r["id"], r["observed"]) for r in ja["results"]]
    ids_b = [(r["bundle"], r["id"], r["observed"]) for r in rb["results"]]
    if len(ids_a) == len(ids_b):
        flips = sum(x[2] != y[2] for x, y in zip(ids_a, ids_b))
        lines += ["", "Decisions changed by the qform rewrite (same query position): %d of %d (%.1f%%). "
                  "Preregistered prediction 6: more than 5%%." % (flips, len(ids_a), 100 * flips / len(ids_a))]
    return lines


def write_summary(run_dir, state):
    L = ["# Corpus 3 replication summary (auto-generated, read this first)", "",
         "Updated: %s   Run dir: `%s`" % (rs.now(), run_dir), "",
         "Replication of the sealed test under the frozen configuration; see "
         "docs/PREREGISTRATION_CORPUS3.md. No tuning, no selection.", "",
         "## Step status", "", "| step | status | exit | seconds |", "|---|---|---|---|"]
    for name, *_ in STEPS:
        s = state["steps"].get(name)
        L.append("| %s | %s | %s | %s |" % (name, s["status"] if s else "pending",
                                           s["exit"] if s else "", s["seconds"] if s else ""))
    rows, m, d, x = compare_rows(state["start_epoch"])
    L += ["", "## Reported (numbers.md section 3) vs replicated", "",
          "| group | item | reported | replicated | |", "|---|---|---|---|---|"]
    L += ["| %s | %s | %s | %s | %s |" % tuple(r) for r in rows]
    L += ["", "**%d MATCH, %d DIFF, %d missing or stale (of %d).**" % (m, d, x, len(rows)),
          "", "## qform vs hypothesis (new; no earlier reported value)", ""] + qform_report()
    failed = [n for n, s in state["steps"].items() if s["status"] == "failed"]
    L += ["", "## Failures (last 40 log lines each)", ""]
    if not failed:
        L.append("None so far.")
    for n in failed:
        L += ["### " + n, "", "```"] + rs.tail(run_dir / (n + ".log"), 40) + ["```", ""]
    (run_dir / "RERUN_C3_SUMMARY.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def collect(run_dir, state):
    out = run_dir / "collected"
    out.mkdir(exist_ok=True)
    since = state["start_epoch"]
    state["steps"].setdefault("collect", {"status": "done", "exit": 0,
                                          "seconds": "", "finished": rs.now()})
    rows = []
    for f in sorted(RESULTS.iterdir()):
        if f.is_file() and f.name.startswith("c3_") and f.stat().st_mtime >= since - 1:
            shutil.copy2(f, out / f.name)
            rows.append((f.name, rs.sha256(f), f.stat().st_size))
    lines = ["# Corpus 3 replication manifest", "", "Run dir: `%s`" % run_dir, "",
             "## Environment", "", "```", rs.env_record(run_dir), "```", "",
             "## Steps", "", "| step | status | exit | seconds |", "|---|---|---|---|"]
    for name, *_ in STEPS:
        s = state["steps"].get(name, {})
        lines.append("| %s | %s | %s | %s |" % (name, s.get("status", "not run"),
                                               s.get("exit", ""), s.get("seconds", "")))
    lines += ["", "## Result files (SHA-256)", "", "| file | sha256 | bytes |", "|---|---|---|"]
    lines += ["| %s | %s | %d |" % r for r in rows]
    (run_dir / "rerun_c3_manifest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--max-steps", type=int, default=0,
                    help="run at most N steps (batches count as one each), then pause "
                         "cleanly; rerun the same command to continue")
    args = ap.parse_args()

    run_dir = pick_run_dir(args.fresh)
    state = rs.load_state(run_dir)
    if args.status:
        print("run dir:", run_dir)
        for name, *_ in STEPS:
            s = state["steps"].get(name)
            print("  %-22s %s" % (name, (s["status"] + " (exit %s, %ss)" % (s["exit"], s["seconds"])) if s else "pending"))
        return 0

    stray = {k: v for k, v in os.environ.items() if k.startswith("RAG_")}
    if stray:
        print("REFUSING TO RUN: RAG_* variables are set in this shell: %s" % stray)
        print("Corpus 3 runs under the frozen configuration only.")
        return 2

    (run_dir / "env_record.txt").write_text(rs.env_record(run_dir), encoding="utf-8")
    rs.save_state(run_dir, state)

    executed = 0
    for name, argv, critical in STEPS:
        if state["steps"].get(name, {}).get("status") == "done":
            print("[skip] %s (already done)" % name)
            continue
        if args.max_steps and executed >= args.max_steps:
            write_summary(run_dir, state)
            print("PAUSED after %d step(s); rerun the same command to continue "
                  "(next: %s)." % (executed, name))
            return 0
        executed += 1
        print("[%s] start %s" % (rs.now(), name), flush=True)
        t0 = time.time()
        log = run_dir / ("%s.log" % name)
        rc = collect(run_dir, state) if argv == ["__collect__"] else rs.run_cmd(argv, {}, log)
        status = "done" if rc == 0 else "failed"
        if rc == 0 and log.exists() and rs.GATE_WARNING in log.read_text(encoding="utf-8", errors="replace"):
            status, rc = "failed", 99
            print("  !! answerhood gate was silently disabled; step marked failed")
        state["steps"][name] = {"status": status, "exit": rc,
                                "seconds": round(time.time() - t0, 1), "finished": rs.now()}
        rs.save_state(run_dir, state)
        write_summary(run_dir, state)
        print("[%s] %s %s (exit %s)" % (rs.now(), name, status, rc), flush=True)
        if rc != 0 and critical:
            print("Critical step failed; stopping. Fix the environment and rerun to resume.")
            return 1

    write_summary(run_dir, state)
    failed = [n for n, s in state["steps"].items() if s["status"] == "failed"]
    print("FAILED STEPS: %s" % (failed or "none"))
    _, m, d, x = compare_rows(state["start_epoch"])
    print("REPORTED VS REPLICATED: %d MATCH, %d DIFF, %d missing or stale "
          "(details in RERUN_C3_SUMMARY.md)" % (m, d, x))
    return 0 if not failed and d == 0 and x == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
