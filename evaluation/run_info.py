"""
run_info.py: which system produced this result file?

Every harness stamps its output with run_info() so a number can be traced to the
code and settings that made it. Added after the Corpus 2 gap-probe file turned
out to predate ANSWERHOOD_MARGIN with nothing in the file saying so
(RAG_System_Observation_Log.md, Observation 33).

Records: UTC time, git commit, whether tracked files differ from that commit,
SHA-256 of the two source files that decide behaviour, every effective
validation setting, and any RAG_* variables set in the environment. Purely
descriptive; it never changes a decision.
"""

from __future__ import annotations

import datetime
import hashlib
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE_FILES = ("validation.py", "qdrant_retrieval.py")

# Effective switches that env vars can change. config_snapshot() in harness.py
# covers the numeric thresholds; these are the Stage 4/5 switches it omitted.
SWITCHES = (
    "MIN_FOCUS_PRESENCE", "REQUIRE_ASSERTIVE_SPANS", "DIMENSIONAL_VETO",
    "ANCHOR_REQUIRE_BOTH", "ANCHOR_ASYMMETRIC_QSPAN",
    "MAX_CONFLICT_EVIDENCE_RANK", "KNEE_GAP_MULTIPLE", "RANK_TIE_EPSILON",
)


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True,
                              text=True, timeout=20).stdout.strip()
    except Exception as exc:  # recording must never fail a run
        return f"unavailable: {exc}"


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return "missing"


def run_info(include_config: bool = True) -> dict:
    info = {
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "git_commit": _git("rev-parse", "HEAD"),
        "git_branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        # tracked files changed since the commit (untracked files ignored)
        "tracked_files_modified": bool(_git("status", "--porcelain", "--untracked-files=no")),
        "core_sha256": {name: _sha256(ROOT / name) for name in CORE_FILES},
        "env_overrides": {k: v for k, v in os.environ.items() if k.startswith("RAG_")},
    }
    if include_config:
        try:
            import validation
            from harness import config_snapshot
            cfg = config_snapshot()
            cfg.update({k: getattr(validation, k) for k in SWITCHES if hasattr(validation, k)})
            info["config"] = cfg
        except Exception as exc:
            info["config"] = f"unavailable: {exc}"
    return info
