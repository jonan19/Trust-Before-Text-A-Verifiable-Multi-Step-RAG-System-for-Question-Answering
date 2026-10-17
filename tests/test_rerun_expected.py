"""
evaluation/rerun_suite.py: the expected-values file and the comparison logic.

The runner is what tells the owner whether the numbers still hold, so its
comparison must not be able to report a false MATCH (stale file, missing file,
wrong type). These tests use temporary result files and run no evaluation.
"""
import json
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evaluation"))

import rerun_suite as rs  # noqa: E402


@pytest.fixture
def results(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "RESULTS", tmp_path)
    return tmp_path


EXPECTED = {
    "eval": [{"tag": "t", "corpus": 1, "metrics": {"accuracy": 75, "conflict_precision": 1.0,
                                                 "unsafe_answers": "0/32"}}],
    "invariance": {"1": {"permute": [0, 0]}},
    "containment": {"poison_in_prompt_after": 0},
    "label_audit": {"confirmed_mislabels": 2},
}


def _write(results, name, obj):
    (results / name).write_text(json.dumps(obj), encoding="utf-8")


def _good(results):
    _write(results, "t_corpus1.json", {"metrics": {"accuracy": 75, "conflict_precision": 1.0,
                                                   "unsafe_answers": "0/32"}})
    _write(results, "invariance_corpus1.json",
           {"transforms": {"permute": {"violations": 0, "safety_regressions": 0}}})
    _write(results, "synthesis_containment.json", {"summary": {"poison_in_prompt_after": 0}})
    _write(results, "label_audit.json", {"OUR SYNTHESIS": {"confirmed_mislabels": ["a", "b"]}})


def test_expected_file_is_valid_json_with_every_group():
    exp = json.loads(rs.EXPECTED_FILE.read_text(encoding="utf-8"))
    for group in ("eval", "invariance", "gap_probes", "fabricated", "containment", "label_audit"):
        assert group in exp
    # headline numbers from numbers.md section 2
    by = {(e["tag"], e["corpus"]): e["metrics"] for e in exp["eval"]}
    assert by[("rerun", 1)]["accuracy"] == 75 and by[("rerun", 2)]["accuracy"] == 70
    assert exp["containment"]["poison_in_prompt_after"] == 0
    assert exp["fabricated"]["1"]["unsafe_after"] == 0 and exp["fabricated"]["2"]["unsafe_after"] == 0


def test_all_match(results):
    _good(results)
    rows, match, diff, missing = rs.compare_rows(expected=EXPECTED)
    assert diff == 0 and missing == 0 and match == len(rows) == 7


def test_a_different_value_is_a_diff(results):
    _good(results)
    _write(results, "t_corpus1.json", {"metrics": {"accuracy": 74, "conflict_precision": 1.0,
                                                   "unsafe_answers": "0/32"}})
    rows, match, diff, missing = rs.compare_rows(expected=EXPECTED)
    assert diff == 1
    assert [r for r in rows if r[4] == "DIFF"][0][:2] == ["t C1", "accuracy"]


def test_float_tolerance_and_string_exactness(results):
    _good(results)
    _write(results, "t_corpus1.json", {"metrics": {"accuracy": 75, "conflict_precision": 1.0003,
                                                   "unsafe_answers": "1/32"}})
    rows, match, diff, missing = rs.compare_rows(expected=EXPECTED)
    verdicts = {r[1]: r[4] for r in rows}
    assert verdicts["conflict_precision"] == "MATCH"
    assert verdicts["unsafe_answers"] == "DIFF"


def test_missing_file_is_not_a_match(results):
    rows, match, diff, missing = rs.compare_rows(expected=EXPECTED)
    assert match == 0 and missing == len(rows)
    assert all(r[4] == "NO FILE" for r in rows)


def test_stale_file_is_not_a_match(results):
    _good(results)
    rows, match, diff, missing = rs.compare_rows(since=time.time() + 3600, expected=EXPECTED)
    assert match == 0 and all(r[4].startswith("STALE") for r in rows)


def test_absent_metric_is_a_diff_not_a_match(results):
    _good(results)
    _write(results, "t_corpus1.json", {"metrics": {"accuracy": 75}})
    rows, match, diff, missing = rs.compare_rows(expected=EXPECTED)
    assert diff == 2  # conflict_precision and unsafe_answers read as "n/a"


def test_collect_marks_itself_done_in_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "RESULTS", tmp_path)
    monkeypatch.setattr(rs, "env_record", lambda run_dir: "env")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    state = {"start_epoch": time.time() - 5, "steps": {}}
    rs.collect(run_dir, state)
    text = (run_dir / "rerun_manifest.md").read_text(encoding="utf-8")
    assert "| collect | done |" in text
