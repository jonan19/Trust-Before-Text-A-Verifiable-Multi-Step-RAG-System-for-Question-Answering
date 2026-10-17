"""evaluation/run_info.py: the provenance stamp written into every result file."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evaluation"))

import run_info as ri  # noqa: E402


def test_stamp_has_commit_hashes_and_is_json_serialisable():
    info = ri.run_info(include_config=False)
    assert len(info["git_commit"]) == 40
    assert isinstance(info["tracked_files_modified"], bool)
    assert set(info["core_sha256"]) == set(ri.CORE_FILES)
    assert all(len(h) == 64 for h in info["core_sha256"].values())
    json.dumps(info)  # must be writable into a result file


def test_stamp_reports_rag_env_overrides(monkeypatch):
    monkeypatch.setenv("RAG_ANSWERHOOD_MARGIN", "0")
    assert ri.run_info(include_config=False)["env_overrides"] == {"RAG_ANSWERHOOD_MARGIN": "0"}


def test_stamp_records_effective_switches():
    cfg = ri.run_info()["config"]
    assert cfg["ANSWERHOOD_MARGIN"] == 5.5          # shipped default
    for key in ("MIN_FOCUS_PRESENCE", "REQUIRE_ASSERTIVE_SPANS", "DIMENSIONAL_VETO"):
        assert key in cfg


def test_modified_flag_ignores_the_runs_own_result_files(monkeypatch):
    seen = []
    real = ri._git

    def spy(*args):
        seen.append(args)
        return real(*args)
    monkeypatch.setattr(ri, "_git", spy)
    ri.run_info(include_config=False)
    status_calls = [a for a in seen if a and a[0] == "status"]
    assert status_calls and ":(exclude)evaluation/results" in status_calls[0]


def test_stamp_never_raises_if_git_is_missing(monkeypatch):
    def boom(*a, **k):
        raise OSError("no git")
    monkeypatch.setattr(ri.subprocess, "run", boom)
    info = ri.run_info(include_config=False)
    assert info["git_commit"].startswith("unavailable")
