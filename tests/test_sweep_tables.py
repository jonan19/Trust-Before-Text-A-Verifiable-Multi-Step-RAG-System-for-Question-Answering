"""evaluation/sweep_tables.py: the judging and bookkeeping logic (no evaluation runs)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evaluation"))

import sweep_tables as st  # noqa: E402


def test_setting_keys_are_unique_and_envs_are_rag_only():
    keys = [s["key"] for s in st.SETTINGS]
    assert len(keys) == len(set(keys))
    for s in st.SETTINGS:
        assert all(k.startswith("RAG_") for k in s["env"]), s["key"]


def test_every_run_has_a_unique_result_file():
    paths = {st.result_path(s["key"], c) for s in st.SETTINGS for c in ("1", "2") if st.wanted(s, c)}
    assert len(paths) == sum(1 for s in st.SETTINGS for c in ("1", "2") if st.wanted(s, c))


def test_lexical_gate_is_corpus_1_only_and_unprinted_cells_are_skipped():
    by = {s["key"]: s for s in st.SETTINGS}
    assert st.wanted(by["lex_060"], "1") and not st.wanted(by["lex_060"], "2")
    assert not st.wanted(by["am_3"], "2") and st.wanted(by["am_4"], "2")


def test_default_row_matches_the_verified_current_numbers():
    assert st.DEFAULT == ((96.2, 1.000, 16, 0), (89.7, 0.875, 14, 1))


def test_judge_exact_range_tolerance_and_no_value():
    assert st.judge((96.2, 1.0, 16, 0), (96.2, 1.000, 16, 0)) == "MATCH"
    assert st.judge((96.15, 0.9999, 16, 0), (96.2, 1.000, 16, 0)) == "MATCH"
    assert st.judge((96.2, 1.0, 16, 1), (96.2, 1.000, 16, 0)) == "DIFF"      # unsafe count differs
    assert st.judge((95.0, 1.0, 16, 0), (96.2, 1.000, 16, 0)) == "DIFF"      # accuracy differs
    assert st.judge((90.4, 0.875, 14, 1), ([89.7, 91.0], 0.875, 14, 1)) == "MATCH"  # inside a range
    assert st.judge((91.9, 0.875, 14, 1), ([89.7, 91.0], 0.875, 14, 1)) == "DIFF"
    assert st.judge((75.6, 0.0, 0, 16), (75.6, None, 0, 16)) == "MATCH"      # paper prints no precision
    assert st.judge((1, 1, 1, 1), None) == "no paper value"


def test_observed_parses_the_unsafe_numerator():
    m = {"accuracy_pct": 96.2, "conflict_precision": 1.0, "conflict_tp": 16, "unsafe_answers": "3/32"}
    assert st.observed(m) == (96.2, 1.0, 16, 3)
