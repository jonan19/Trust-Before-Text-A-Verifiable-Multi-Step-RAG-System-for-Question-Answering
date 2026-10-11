"""
evaluation/rerun_corpus3.py: expected-values file and comparison logic for the
Corpus 3 replication. No evaluation runs here; temporary result files only.

The comparison must never report a false MATCH (missing or pre-run file, absent
key) and must honour the [value, tolerance] form used for rounded documented
numbers.
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evaluation"))

import rerun_corpus3 as rc  # noqa: E402

EXPECTED = {
    "a": {"file": "a.json", "path": ["metrics"],
          "values": {"accuracy": 136, "accuracy_pct": [26.7, 0.06], "unsafe_answers": "29/114"}},
    "ci": {"file": "ci.json", "path": [],
           "values": {"intervals.accuracy_pct.ci_low": [22.5, 0.06]}},
}


def _write(folder, name, obj):
    (folder / name).write_text(json.dumps(obj), encoding="utf-8")


def _good(folder):
    _write(folder, "a.json", {"metrics": {"accuracy": 136, "accuracy_pct": 26.667,
                                          "unsafe_answers": "29/114"}})
    _write(folder, "ci.json", {"intervals": {"accuracy_pct": {"ci_low": 22.49}}})


def test_expected_file_has_the_reported_headlines():
    exp = json.loads(rc.EXPECTED_FILE.read_text(encoding="utf-8"))
    a = exp["trackA"]["values"]
    assert a["accuracy"] == 136 and a["unsafe_answers"] == "29/114"
    assert exp["trackA_gold"]["values"] == {"answer": 396, "conflict": 74, "insufficient": 40}
    assert exp["trackA_attribution"]["values"]["external_attribution_n"] == "0/350"
    assert exp["trackB"]["values"]["accuracy"] == 97


def test_all_match_with_tolerance_and_dotted_paths(tmp_path):
    _good(tmp_path)
    rows, match, diff, missing = rc.compare_rows(expected=EXPECTED, results=tmp_path)
    assert (match, diff, missing) == (4, 0, 0)


def test_value_outside_tolerance_is_diff(tmp_path):
    _good(tmp_path)
    _write(tmp_path, "a.json", {"metrics": {"accuracy": 136, "accuracy_pct": 27.0,
                                            "unsafe_answers": "29/114"}})
    rows, match, diff, missing = rc.compare_rows(expected=EXPECTED, results=tmp_path)
    assert diff == 1 and [r for r in rows if r[4] == "DIFF"][0][1] == "accuracy_pct"


def test_string_and_integer_values_are_exact(tmp_path):
    _good(tmp_path)
    _write(tmp_path, "a.json", {"metrics": {"accuracy": 135, "accuracy_pct": 26.7,
                                            "unsafe_answers": "29/115"}})
    rows, match, diff, missing = rc.compare_rows(expected=EXPECTED, results=tmp_path)
    assert diff == 2


def test_missing_file_is_never_a_match(tmp_path):
    rows, match, diff, missing = rc.compare_rows(expected=EXPECTED, results=tmp_path)
    assert match == 0 and missing == len(rows) and all(r[4] == "NO FILE" for r in rows)


def test_pre_run_file_is_stale_not_a_match(tmp_path):
    _good(tmp_path)
    rows, match, diff, missing = rc.compare_rows(since=time.time() + 3600,
                                                 expected=EXPECTED, results=tmp_path)
    assert match == 0 and all(r[4].startswith("STALE") for r in rows)


def test_absent_key_is_a_diff_not_a_match(tmp_path):
    _good(tmp_path)
    _write(tmp_path, "ci.json", {"intervals": {}})
    rows, match, diff, missing = rc.compare_rows(expected=EXPECTED, results=tmp_path)
    assert diff == 1 and match == 3


def test_refuses_when_a_rag_variable_is_set(monkeypatch, capsys):
    monkeypatch.setenv("RAG_ANSWERHOOD_MARGIN", "0")
    monkeypatch.setattr(sys, "argv", ["rerun_corpus3.py"])
    monkeypatch.setattr(rc, "pick_run_dir", lambda fresh: ROOT / "evaluation" / "results")
    monkeypatch.setattr(rc.rs, "load_state", lambda d: {"steps": {}, "start_epoch": 0})
    assert rc.main() == 2
    assert "REFUSING" in capsys.readouterr().out
