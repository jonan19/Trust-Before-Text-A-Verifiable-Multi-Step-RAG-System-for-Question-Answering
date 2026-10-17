"""
Batched Corpus 3 replication: the batches must cover every test bundle exactly
once, and merging batched output must give exactly what an unbatched run pools.
Synthetic records only; no evaluation runs.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evaluation"))

import merge_corpus3_parts as mp  # noqa: E402
import rerun_corpus3 as rc  # noqa: E402
from harness import metrics  # noqa: E402

BUNDLES = ["3-test-b%02d" % i for i in range(6)]
CONFIG = {"ANSWERHOOD_MARGIN": 5.5, "env_overrides": {}}


def _rec(bundle, i, expected, observed):
    return {"id": "%s-q%d" % (bundle, i), "bundle": bundle, "expected": expected,
            "observed": observed, "match": expected == observed,
            "expected_conflict_pair": None, "conflict_pair": None}


def _bundle_records(bundle):
    pairs = [("answer", "answer"), ("answer", "insufficient"), ("conflict", "conflict"),
             ("insufficient", "answer"), ("insufficient", "insufficient"), ("conflict", "answer")]
    return [_rec(bundle, i, e, o) for i, (e, o) in enumerate(pairs)]


def _part(names, queries="queries.json"):
    recs = [r for n in names for r in _bundle_records(n)]
    return {"meta": {"queries_file": queries, "elapsed_s": 1.0}, "config": CONFIG,
            "per_bundle": {n: metrics(_bundle_records(n)) for n in names}, "results": recs}


def test_batches_cover_every_test_bundle_exactly_once():
    flat = [n for part in rc.PARTS for n in part]
    assert flat == sorted(flat) and len(flat) == len(set(flat)) == 30
    assert all(1 <= len(p) <= rc.BATCH for p in rc.PARTS)


def test_step_names_are_unique_and_ordered():
    names = [s[0] for s in rc.STEPS]
    assert len(names) == len(set(names))
    assert names[0] == "ingest_test_stores" and names[-1] == "collect"
    for track in ("track_a", "track_b", "qform"):
        batch = [n for n in names if n.startswith(track + "_part")]
        assert batch == ["%s_part%d" % (track, i) for i in range(1, len(rc.PARTS) + 1)]
        # the merge comes straight after the last batch of its track
        assert names[names.index(batch[-1]) + 1] == track + "_merge"


def test_every_part_step_writes_the_file_the_merge_reads():
    for key, tag in (("track_a", "c3_hypothesis"), ("track_b", "c3_open"), ("qform", "c3_qform")):
        for i, (name, argv, _) in enumerate([s for s in rc.STEPS if s[0].startswith(key + "_part")], 1):
            assert argv[argv.index("--tag") + 1] == "%s__part%d" % (tag, i)


def test_merge_equals_unbatched_metrics():
    parts = [_part(BUNDLES[:2]), _part(BUNDLES[2:5]), _part(BUNDLES[5:])]
    merged = mp.merge(parts, BUNDLES, "queries.json", "t", "test")
    all_recs = [r for n in BUNDLES for r in _bundle_records(n)]
    expect = metrics(all_recs)
    for k, v in expect.items():
        assert merged["metrics"][k] == v, k
    assert merged["metrics"]["gold_distribution"] == {"answer": 12, "conflict": 12, "insufficient": 12}
    assert [r["id"] for r in merged["results"]] == [r["id"] for r in all_recs]
    assert merged["meta"]["n_bundles"] == 6 and merged["meta"]["merged_from_parts"] == 3


def test_merge_is_independent_of_part_order():
    a = mp.merge([_part(BUNDLES[:3]), _part(BUNDLES[3:])], BUNDLES, "queries.json", "t", "test")
    b = mp.merge([_part(BUNDLES[3:]), _part(BUNDLES[:3])], BUNDLES, "queries.json", "t", "test")
    assert a["metrics"] == b["metrics"]
    assert [r["id"] for r in a["results"]] == [r["id"] for r in b["results"]]


def test_merge_refuses_a_missing_bundle():
    with pytest.raises(SystemExit, match="missing"):
        mp.merge([_part(BUNDLES[:5])], BUNDLES, "queries.json", "t", "test")


def test_merge_refuses_a_duplicated_bundle():
    with pytest.raises(SystemExit, match="more than one part"):
        mp.merge([_part(BUNDLES[:4]), _part(BUNDLES[3:])], BUNDLES, "queries.json", "t", "test")


def test_merge_refuses_mixed_configurations():
    p2 = _part(BUNDLES[3:])
    p2["config"] = {"ANSWERHOOD_MARGIN": 0.0, "env_overrides": {"RAG_ANSWERHOOD_MARGIN": "0"}}
    with pytest.raises(SystemExit, match="different configurations"):
        mp.merge([_part(BUNDLES[:3]), p2], BUNDLES, "queries.json", "t", "test")


def test_merge_refuses_the_wrong_query_file():
    with pytest.raises(SystemExit, match="queries file"):
        mp.merge([_part(BUNDLES, queries="queries_qform.json")], BUNDLES, "queries.json", "t", "test")
