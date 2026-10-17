"""Resumable, chat-independent re-run of the zero-token evaluation suite.

Purpose: re-establish baseline numbers (see numbers.md) without depending on a
Claude session staying alive. Run it detached; it records progress to
<run-dir>/state.json and skips steps already finished, so it can be stopped and
restarted at any point and will continue where it left off.

It changes no system code and spends no LLM tokens. It never touches the sealed
Corpus 3 test split and never runs the RAMDocs / E1-E5 / baseline-LLM scripts.

Usage (from repo root):
    python evaluation/rerun_suite.py            # start or resume
    python evaluation/rerun_suite.py --status   # print progress and exit
    python evaluation/rerun_suite.py --fresh    # ignore previous run, start new
"""
import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "evaluation" / "results"
POINTER = RESULTS / "rerun_LATEST.txt"
PY = sys.executable

GATE_WARNING = "ANSWERHOOD_MARGIN gate disabled"

INGEST = (
    "import qdrant_retrieval as qr; "
    "qr.ingest_documents(data_dir='data', qdrant_dir='qdrant_db_c1_copy', force=True); "
    "qr.ingest_documents(data_dir='data_corpus2', qdrant_dir='qdrant_db_c2_copy', force=True)"
)
MODEL = (
    "from sentence_transformers import CrossEncoder; "
    "CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2'); print('answerhood model ok')"
)

# (name, argv, extra_env, critical)
# critical=True: a failure halts the suite (later steps would be meaningless).
STEPS = [
    ("model_download", [PY, "-c", MODEL], {}, True),
    ("ingest_c1_c2", [PY, "-c", INGEST], {}, True),
    ("clear_cache", ["__clear_cache__"], {}, True),
    ("eval_c1", [PY, "evaluation/run_eval.py", "--corpus", "1", "--tag", "rerun"], {}, False),
    ("eval_c2", [PY, "evaluation/run_eval.py", "--corpus", "2", "--tag", "rerun"], {}, False),
    ("eval_c1_gateoff", [PY, "evaluation/run_eval.py", "--corpus", "1", "--tag", "rerun_ahoff"],
     {"RAG_ANSWERHOOD_MARGIN": "0"}, False),
    ("eval_c2_gateoff", [PY, "evaluation/run_eval.py", "--corpus", "2", "--tag", "rerun_ahoff"],
     {"RAG_ANSWERHOOD_MARGIN": "0"}, False),
    ("invariance_c1", [PY, "evaluation/invariance_harness.py", "--corpus", "1"], {}, False),
    ("invariance_c2", [PY, "evaluation/invariance_harness.py", "--corpus", "2"], {}, False),
    ("containment", [PY, "evaluation/synthesis_containment_test.py"], {}, False),
    ("gap_probes_c1", [PY, "evaluation/adversarial_gap_probes.py", "--corpus", "1"], {}, False),
    ("gap_probes_c2", [PY, "evaluation/adversarial_gap_probes.py", "--corpus", "2"], {}, False),
    ("fabricated_c1", [PY, "evaluation/fabricated_evidence_test.py", "--corpus", "1"], {}, False),
    ("fabricated_c2", [PY, "evaluation/fabricated_evidence_test.py", "--corpus", "2"], {}, False),
    ("label_audit", [PY, "evaluation/label_audit.py"], {}, False),
    ("pytest", [PY, "-m", "pytest", "tests/", "-q"], {}, False),
    ("collect", ["__collect__"], {}, False),
]


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def load_state(run_dir):
    f = run_dir / "state.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return {"started": now(), "start_epoch": time.time(), "steps": {}}


def save_state(run_dir, state):
    tmp = run_dir / "state.json.tmp"
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    os.replace(tmp, run_dir / "state.json")


def pick_run_dir(fresh):
    RESULTS.mkdir(parents=True, exist_ok=True)
    if POINTER.exists() and not fresh:
        d = Path(POINTER.read_text(encoding="utf-8").strip())
        if d.exists():
            return d
    d = RESULTS / ("rerun_" + datetime.date.today().isoformat())
    n = 1
    while d.exists() and fresh:
        n += 1
        d = RESULTS / ("rerun_%s_%d" % (datetime.date.today().isoformat(), n))
    d.mkdir(parents=True, exist_ok=True)
    POINTER.write_text(str(d), encoding="utf-8")
    return d


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_cmd(argv, extra_env, log_path):
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env.update(extra_env)
    with open(log_path, "w", encoding="utf-8", errors="replace") as lf:
        lf.write("# cmd: %s\n# env: %s\n# start: %s\n\n" % (" ".join(argv), extra_env, now()))
        lf.flush()
        p = subprocess.run(argv, cwd=str(ROOT), env=env, stdout=lf,
                           stderr=subprocess.STDOUT)
        lf.write("\n# exit: %s\n# end: %s\n" % (p.returncode, now()))
    return p.returncode


def clear_cache():
    for sub in ("1", "2"):
        shutil.rmtree(ROOT / "evaluation" / "_retrieval_cache" / sub, ignore_errors=True)
    return 0


def env_record(run_dir):
    def sh(*a):
        try:
            return subprocess.run(a, cwd=str(ROOT), capture_output=True, text=True).stdout.strip()
        except Exception as e:  # record, never fail
            return "unavailable: %s" % e
    return "\n".join([
        "date: " + now(),
        "git commit: " + sh("git", "rev-parse", "HEAD"),
        "git branch: " + sh("git", "rev-parse", "--abbrev-ref", "HEAD"),
        "git status --short:\n" + sh("git", "status", "--short"),
        "python: " + sys.version.replace("\n", " "),
        "pip freeze:\n" + sh(PY, "-m", "pip", "freeze"),
    ])


def collect(run_dir, state):
    """Copy every result file written since the run started, then hash them."""
    out = run_dir / "collected"
    out.mkdir(exist_ok=True)
    since = state["start_epoch"]
    # The manifest is written from inside this step, before main() records it,
    # so mark it done here or the manifest would list "collect" as "not run".
    state["steps"].setdefault("collect", {"status": "done", "exit": 0,
                                          "seconds": "", "finished": now()})
    rows = []
    for f in sorted(RESULTS.iterdir()):
        if f.is_file() and f.stat().st_mtime >= since - 1 and not f.name.startswith("rerun_LATEST"):
            shutil.copy2(f, out / f.name)
            rows.append((f.name, sha256(f), f.stat().st_size))
    lines = ["# Re-run manifest", "", "Run dir: `%s`" % run_dir, "",
             "## Environment", "", "```", env_record(run_dir), "```", "",
             "## Steps", "", "| step | status | exit | seconds |", "|---|---|---|---|"]
    for name, *_ in STEPS:
        s = state["steps"].get(name, {})
        lines.append("| %s | %s | %s | %s |" % (name, s.get("status", "not run"),
                                               s.get("exit", ""), s.get("seconds", "")))
    lines += ["", "## Result files (SHA-256)", "", "| file | sha256 | bytes |", "|---|---|---|"]
    lines += ["| %s | %s | %d |" % r for r in rows]
    (run_dir / "rerun_manifest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


# Expected values live in evaluation/expected_baseline.json (one place), copied
# from numbers.md section 2. Edit that file, numbers.md and the log together.
EXPECTED_FILE = ROOT / "evaluation" / "expected_baseline.json"


def values_match(got, want):
    """Numbers compare with a small tolerance; everything else as strings."""
    if isinstance(got, (int, float)) and isinstance(want, (int, float)):
        return abs(got - want) < 0.0006
    return str(got) == str(want)


def _read(name, since):
    """Load a result file. Returns (data, problem) where problem is a status
    string when the file is absent or older than this run (a stale file must
    never produce a false MATCH)."""
    f = RESULTS / name
    if not f.exists():
        return None, "NO FILE"
    if since is not None and f.stat().st_mtime < since - 1:
        return None, "STALE (not written by this run)"
    return json.loads(f.read_text(encoding="utf-8")), None


def compare_rows(since=None, expected=None):
    """Compare every harness output with expected_baseline.json.

    Returns (rows, n_match, n_diff, n_missing); each row is
    [group, item, expected, actual, verdict].
    """
    exp = expected if expected is not None else json.loads(
        EXPECTED_FILE.read_text(encoding="utf-8"))
    rows = []

    def add(group, item, want, got, problem=None):
        if problem:
            rows.append([group, item, want, "-", problem])
        else:
            rows.append([group, item, want, got,
                         "MATCH" if values_match(got, want) else "DIFF"])

    for e in exp.get("eval", []):
        group = "%s C%d" % (e["tag"], e["corpus"])
        data, prob = _read("%s_corpus%d.json" % (e["tag"], e["corpus"]), since)
        m = (data or {}).get("metrics", {})
        for k, want in e["metrics"].items():
            add(group, k, want, m.get(k, "n/a"), prob)

    for corpus, transforms in exp.get("invariance", {}).items():
        if corpus.startswith("_"):
            continue
        data, prob = _read("invariance_corpus%s.json" % corpus, since)
        t = (data or {}).get("transforms", {})
        for name, (want_changed, want_flips) in transforms.items():
            r = t.get(name, {})
            add("invariance C%s" % corpus, name + " changed", want_changed,
                r.get("violations", "n/a"), prob)
            add("invariance C%s" % corpus, name + " abstain->answer", want_flips,
                r.get("safety_regressions", "n/a"), prob)

    for group, fname in (("gap_probes", "adversarial_gap_probes_corpus%s.json"),
                         ("fabricated", "fabricated_evidence_corpus%s.json")):
        for corpus, want in exp.get(group, {}).items():
            if corpus.startswith("_"):
                continue
            data, prob = _read(fname % corpus, since)
            meta = (data or {}).get("meta", {})
            for k, v in want.items():
                add("%s C%s" % (group, corpus), k, v, meta.get(k, "n/a"), prob)

    if "containment" in exp:
        data, prob = _read("synthesis_containment.json", since)
        s = (data or {}).get("summary", {})
        for k, v in exp["containment"].items():
            add("containment", k, v, s.get(k, "n/a"), prob)

    if "label_audit" in exp:
        data, prob = _read("label_audit.json", since)
        o = (data or {}).get("OUR SYNTHESIS", {})
        for k, v in exp["label_audit"].items():
            got = o.get(k, "n/a")
            if isinstance(got, list):
                got = len(got)
            add("label_audit", k, v, got, prob)

    n_match = sum(r[4] == "MATCH" for r in rows)
    n_diff = sum(r[4] == "DIFF" for r in rows)
    return rows, n_match, n_diff, len(rows) - n_match - n_diff


def metric_rows(state=None):
    since = state["start_epoch"] if state else None
    rows, n_match, n_diff, n_missing = compare_rows(since)
    out = ["| %s | %s | %s | %s | %s |" % tuple(r) for r in rows]
    out.append("")
    out.append("**%d MATCH, %d DIFF, %d missing or stale (of %d).**" % (
        n_match, n_diff, n_missing, len(rows)))
    return out


def tail(path, n):
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ["(no log)"]
    return lines[-n:]


def write_summary(run_dir, state):
    """Human-readable progress file, rewritten after every step."""
    L = ["# Re-run summary (auto-generated, read this first)", "",
         "Updated: %s   Run dir: `%s`" % (now(), run_dir), "",
         "## Step status", "", "| step | status | exit | seconds |", "|---|---|---|---|"]
    for name, *_ in STEPS:
        s = state["steps"].get(name)
        L.append("| %s | %s | %s | %s |" % (name, s["status"] if s else "pending",
                                           s["exit"] if s else "", s["seconds"] if s else ""))
    L += ["", "## Expected vs actual (evaluation/expected_baseline.json, from numbers.md section 2)", "",
          "| group | item | expected | actual | |", "|---|---|---|---|---|"] + metric_rows(state)
    failed = [n for n, s in state["steps"].items() if s["status"] == "failed"]
    L += ["", "## Failures (last 40 log lines each)", ""]
    if not failed:
        L.append("None so far.")
    for n in failed:
        L += ["### " + n, "", "```"] + tail(run_dir / (n + ".log"), 40) + ["```", ""]
    L += ["", "## Tail of each finished step (last 12 lines)", ""]
    for name, *_ in STEPS:
        if state["steps"].get(name, {}).get("status") == "done" and (run_dir / (name + ".log")).exists():
            L += ["### " + name, "", "```"] + tail(run_dir / (name + ".log"), 12) + ["```", ""]
    (run_dir / "RERUN_SUMMARY.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def print_status(run_dir, state):
    print("run dir:", run_dir)
    for name, *_ in STEPS:
        s = state["steps"].get(name)
        print("  %-18s %s" % (name, (s["status"] + " (exit %s, %ss)" % (s["exit"], s["seconds"])) if s else "pending"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--fresh", action="store_true")
    args = ap.parse_args()

    run_dir = pick_run_dir(args.fresh)
    state = load_state(run_dir)
    if args.status:
        print_status(run_dir, state)
        return 0

    stray = {k: v for k, v in os.environ.items() if k.startswith("RAG_")}
    if stray:
        print("REFUSING TO RUN: RAG_* variables are set in this shell: %s" % stray)
        print("Unset them and restart; they would silently change the numbers.")
        return 2

    (run_dir / "env_record.txt").write_text(env_record(run_dir), encoding="utf-8")
    save_state(run_dir, state)

    for name, argv, extra_env, critical in STEPS:
        if state["steps"].get(name, {}).get("status") == "done":
            print("[skip] %s (already done)" % name)
            continue
        print("[%s] start %s" % (now(), name), flush=True)
        t0 = time.time()
        log = run_dir / ("%s.log" % name)
        if argv == ["__clear_cache__"]:
            rc = clear_cache()
        elif argv == ["__collect__"]:
            rc = collect(run_dir, state)
        else:
            rc = run_cmd(argv, extra_env, log)
        status = "done" if rc == 0 else "failed"
        # A silently disabled gate invalidates any gate-on result.
        if rc == 0 and log.exists() and "RAG_ANSWERHOOD_MARGIN" not in extra_env:
            if GATE_WARNING in log.read_text(encoding="utf-8", errors="replace"):
                status, rc = "failed", 99
                print("  !! answerhood gate was silently disabled; step marked failed")
        state["steps"][name] = {"status": status, "exit": rc,
                                "seconds": round(time.time() - t0, 1), "finished": now()}
        save_state(run_dir, state)
        write_summary(run_dir, state)
        print("[%s] %s %s (exit %s)" % (now(), name, status, rc), flush=True)
        if rc != 0 and critical:
            print("Critical step failed; stopping. Fix the environment and rerun to resume.")
            return 1

    write_summary(run_dir, state)
    print_status(run_dir, state)
    failed = [n for n, s in state["steps"].items() if s["status"] == "failed"]
    print("FAILED STEPS: %s" % (failed or "none"))
    _, n_match, n_diff, n_missing = compare_rows(state["start_epoch"])
    print("EXPECTED VS ACTUAL: %d MATCH, %d DIFF, %d missing or stale "
          "(details in RERUN_SUMMARY.md)" % (n_match, n_diff, n_missing))
    return 0 if not failed and n_diff == 0 and n_missing == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
