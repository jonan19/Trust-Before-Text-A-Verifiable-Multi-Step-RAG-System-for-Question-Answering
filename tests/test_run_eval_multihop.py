"""
evaluation/run_eval_multihop.py: the preregistered MultiHop-RAG protocol.

No network, no index, no LLM: the sampler, article format, E1 prompt extraction, grading,
statistics, checkpoints, key handling and the config guard are tested on small made-up data.
"""
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evaluation"))

import run_eval_multihop as mh  # noqa: E402

TYPES = ["null_query", "inference_query", "comparison_query", "temporal_query"]


def fake_queries(per_type=60):
    out = []
    for t in TYPES:
        for j in range(per_type):
            ev = [] if t == "null_query" else [{"title": f"A{j}"}, {"title": f"B{j}"}]
            out.append({"query": f"{t} question {j}?", "answer": "x", "question_type": t, "evidence_list": ev})
    return out


QUOTAS = (("null_query", 20), ("inference_query", 5), ("comparison_query", 5), ("temporal_query", 5))


def test_sample_is_deterministic_and_hits_quotas():
    qs = fake_queries()
    a = mh.draw_sample(qs, seed=7, quotas=QUOTAS)
    b = mh.draw_sample(qs, seed=7, quotas=QUOTAS)
    assert a == b
    assert Counter(r["type"] for r in a) == {t: n for t, n in QUOTAS}
    assert len({r["id"] for r in a}) == len(a)
    assert all(r["gold"] == ("insufficient" if r["type"] == "null_query" else "answer") for r in a)
    assert all(r["gold_titles"] == [] for r in a if r["type"] == "null_query")
    assert all(qs[r["index"]]["query"] == r["query"] for r in a)
    assert a != mh.draw_sample(qs, seed=8, quotas=QUOTAS)


def test_run_order_is_shuffled_not_grouped_by_type():
    a = mh.draw_sample(fake_queries(), seed=7, quotas=QUOTAS)
    first_ten = {r["type"] for r in a[:10]}
    assert len(first_ten) > 1


def test_preregistered_constants():
    assert mh.SEED == 20261015
    assert dict(mh.QUOTAS) == {"null_query": 150, "inference_query": 50,
                               "comparison_query": 50, "temporal_query": 50}
    assert mh.STORE == "qdrant_db_multihop"
    existing = {"qdrant_db", "qdrant_db_corpus2", "qdrant_db_c1_copy", "qdrant_db_c2_copy",
                "qdrant_db_c3", "qdrant_db_merged"}
    assert mh.STORE not in existing


def test_article_files_are_neutral_and_carry_metadata(tmp_path):
    corpus = [{"title": "Big News", "source": "TechCrunch", "author": "Ann", "published_at": "2023-10-01",
               "category": "technology", "url": "u", "body": "Line one.\nLine two."}]
    titles = mh.write_articles(corpus, tmp_path / "articles", tmp_path / "titles.json")
    assert titles == {"mh_000.txt": "Big News"}
    text = (tmp_path / "articles" / "mh_000.txt").read_text(encoding="utf-8")
    assert text.startswith("Title: Big News\nSource: TechCrunch\nAuthor: Ann\n"
                           "Published: 2023-10-01\nCategory: technology\n\n")
    assert text.endswith("Line one.\nLine two.")
    assert json.loads((tmp_path / "titles.json").read_text(encoding="utf-8")) == titles
    # the file stem says nothing a query could match
    assert "big" not in "mh_000"


def test_load_data_refuses_wrong_hash(tmp_path):
    for name in mh.DATA_SHA256:
        (tmp_path / name).write_text("[]", encoding="utf-8")
    with pytest.raises(SystemExit, match="does not match"):
        mh.load_data(tmp_path)


def test_e1_prompt_is_taken_verbatim_from_baseline_experiment():
    e1 = mh.load_e1()
    src = mh.E1_SOURCE.read_text(encoding="utf-8")
    assert "INSUFFICIENT" in e1["BASELINE_SYSTEM"] and "CONFLICT" in e1["BASELINE_SYSTEM"]
    assert "{chunks}" in e1["BASELINE_USER_TMPL"] and "{query}" in e1["BASELINE_USER_TMPL"]
    assert "def parse_decision" in src and "def build_context_block" in src
    # identical to the clean RAMDocs runner's copy of the same prompt
    import run_eval_ramdocs_clean as rc
    assert e1["BASELINE_SYSTEM"] == rc.BASELINE_SYSTEM


@pytest.mark.parametrize("reply,want", [
    ("INSUFFICIENT", "insufficient"),
    ("**CONFLICT**: 5 vs 6", "conflict"),
    ("The answer is Yes, per mh_003.txt", "answer"),
    ("  insufficient", "insufficient"),
])
def test_baseline_reply_parser(reply, want):
    assert mh.load_e1()["parse_decision"](reply) == want


class FakeOrch:
    RETRIEVAL_TOP_K = 30

    def __init__(self):
        self.calls = []

    def preprocess_query(self, q):
        return q.lower()

    def classify_query(self, q):
        return "complex" if " and " in q else "simple"

    def decompose_query(self, q):
        return q.split(" and ")

    def retrieve_for_queries(self, subs, top_k):
        self.calls.append((tuple(subs), top_k))
        return [{"source": "mh_001.txt", "text": "alpha"}, {"source": "mh_002.txt", "text": "beta"},
                {"source": "mh_001.txt", "text": "gamma"}]


def test_first_attempt_mirrors_orchestrator_top_k():
    o = FakeOrch()
    mh.first_attempt_passages(o, "Who won")
    mh.first_attempt_passages(o, "Who won and who lost")
    assert o.calls == [(("who won",), 30), (("who won", "who lost"), 32)]


def test_baseline_arm_sends_same_passages_and_parses():
    o = FakeOrch()
    seen = {}

    def fake_llm(system, user):
        seen["system"], seen["user"] = system, user
        return "INSUFFICIENT"

    e1 = mh.load_e1()
    row = mh.run_baseline_one(o, {"query": "Who won"}, {}, e1, llm=fake_llm)
    assert row["observed"] == "insufficient" and row["n_passages"] == 3 and row["n_passages_sent"] == 3
    assert row["retrieved_sources"] == ["mh_001.txt", "mh_002.txt"]
    assert seen["system"] == e1["BASELINE_SYSTEM"]
    assert "[Passage 1 | Source: mh_001.txt]\nalpha" in seen["user"]
    assert "Question: Who won" in seen["user"]


def test_baseline_gets_only_the_top_12_passages_amendment_1():
    assert mh.BASELINE_MAX_PASSAGES == 12

    class ManyOrch(FakeOrch):
        def retrieve_for_queries(self, subs, top_k):
            return [{"source": f"mh_{i:03d}.txt", "text": f"text {i}"} for i in range(30)]

    seen = {}
    row = mh.run_baseline_one(ManyOrch(), {"query": "Who won"}, {"mh_000.txt": "T0"}, mh.load_e1(),
                              llm=lambda s, u: seen.setdefault("user", u) and "INSUFFICIENT")
    assert row["n_passages"] == 30 and row["n_passages_sent"] == 12
    assert "[Passage 12 | Source: mh_011.txt]" in seen["user"]
    assert "[Passage 13 |" not in seen["user"] and "mh_012.txt" not in seen["user"]
    assert row["sent_titles"][0] == "T0" and len(row["sent_sources"]) == 12


def test_baseline_visibility():
    rows = [{"gold": "answer", "gold_titles": ["A", "B"], "sent_titles": ["A"]},
            {"gold": "answer", "gold_titles": ["C"], "sent_titles": ["C", "D"]},
            {"gold": "insufficient", "gold_titles": [], "sent_titles": []}]
    v = mh.baseline_visibility(rows)
    assert v == {"n": 2, "gold_articles": 3, "gold_in_sent_passages_pct": 66.7, "all_gold_sent_queries": 1}


def row(i, gold, obs, qtype=None):
    return {"id": f"q{i}", "gold": gold, "observed": obs,
            "type": qtype or ("null_query" if gold == "insufficient" else "inference_query")}


def test_grading_and_metrics():
    rows = [row(1, "insufficient", "answer"), row(2, "insufficient", "insufficient"),
            row(3, "insufficient", "conflict"), row(4, "answer", "answer"),
            row(5, "answer", "conflict"), row(6, "answer", "insufficient")]
    m = mh.arm_metrics(rows)
    assert m["gap_leak"]["k"] == 1 and m["gap_leak"]["n"] == 3
    assert m["over_abstention"]["k"] == 2 and m["over_abstention"]["n"] == 3
    assert (m["over_abstention_conflict"], m["over_abstention_insufficient"]) == (1, 1)
    assert m["correct_strict"]["k"] == 2          # q2 and q4; a conflict on a null query is not strict-correct
    assert m["correct_lenient"]["k"] == 3         # q2, q3, q4
    assert m["refusal_all"]["k"] == 4
    assert m["confusion"]["insufficient"] == {"answer": 1, "conflict": 1, "insufficient": 1}


def test_wilson_and_mcnemar_arithmetic():
    assert mh.wilson(0, 32) == [0.0, 10.7]
    assert mh.wilson(1, 32) == [0.6, 15.7]
    assert mh.wilson(24, 24)[0] == 86.2
    assert mh.wilson(0, 0) is None
    assert mh.mcnemar(0, 12) == pytest.approx(2 * 0.5 ** 12)
    assert mh.mcnemar(0, 0) == 1.0
    assert mh.mcnemar(11, 2) == pytest.approx(0.02246, abs=1e-5)


def test_paired_tests_count_discordant_pairs():
    ours = [row(1, "insufficient", "answer"), row(2, "insufficient", "answer"), row(3, "answer", "answer")]
    base = [row(1, "insufficient", "insufficient"), row(2, "insufficient", "answer"),
            row(3, "answer", "insufficient")]
    t = mh.paired_tests(ours, base)
    assert t["n_pairs"] == 3
    assert (t["gap_leak"]["ours_only"], t["gap_leak"]["baseline_only"]) == (1, 0)
    assert (t["over_abstention"]["ours_only"], t["over_abstention"]["baseline_only"]) == (0, 1)


def test_retrieval_metrics():
    rows = [{"gold": "answer", "gold_titles": ["A", "B"], "retrieved_titles": ["A", "B", "C"],
             "top5_titles_original": ["A"]},
            {"gold": "answer", "gold_titles": ["C", "D"], "retrieved_titles": ["C"],
             "top5_titles_original": []},
            {"gold": "insufficient", "gold_titles": [], "retrieved_titles": [], "top5_titles_original": []}]
    r = mh.retrieval_metrics(rows)
    assert r["n"] == 2 and r["gold_articles"] == 4
    assert r["gold_retrieved_across_subqueries_pct"] == 75.0
    assert r["recall_at5_original_pct"] == 25.0
    assert r["all_gold_retrieved_queries"] == 1


def test_checkpoint_resume(tmp_path):
    p = tmp_path / "x.ckpt.jsonl"
    mh.append_ckpt(p, {"id": "_run_info"})
    mh.append_ckpt(p, {"id": "mh0001", "observed": "answer"})
    mh.append_ckpt(p, {"id": "mh0002", "observed": "insufficient"})
    done = mh.read_ckpt(p)
    assert set(done) == {"_run_info", "mh0001", "mh0002"}
    assert mh.read_ckpt(tmp_path / "missing.jsonl") == {}


def test_refuses_rag_overrides(monkeypatch):
    monkeypatch.setenv("RAG_ANSWERHOOD_MARGIN", "0")
    with pytest.raises(SystemExit, match="RAG_"):
        mh.check_config()


class FakePool:
    def __init__(self, n):
        self.names = [f"K{i}" for i in range(n)]
        self.i = 0

    def current(self):
        return self.names[self.i], "secret"

    def retire(self, reason):
        self.i += 1
        return None if self.i >= len(self.names) else self.names[self.i]

    def status(self):
        return "fake"


def test_with_pool_rotates_on_daily_cap_and_waits_on_throttle(monkeypatch, capsys):
    monkeypatch.setattr(mh, "apply_key", lambda pair: pair[0])
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("Error code: 429 rate limit reached: tokens per day (TPD)")
        if calls["n"] == 2:
            raise RuntimeError("Error code: 429 rate limit reached, try again")
        return "ok"

    slept = []
    assert mh.with_pool(flaky, FakePool(2), sleep=slept.append) == "ok"
    assert slept == [30]
    assert "secret" not in capsys.readouterr().out
    with pytest.raises(mh.PoolExhausted):
        mh.with_pool(lambda: (_ for _ in ()).throw(RuntimeError("Error code: 401 invalid api key")),
                     FakePool(1), sleep=slept.append)


def test_predictions_follow_preregistered_definitions():
    m_ours = {"gap_leak": {"k": 20}, "over_abstention": {"k": 30},
              "over_abstention_conflict": 25, "over_abstention_insufficient": 5}
    m_base = {"gap_leak": {"k": 1}, "over_abstention": {"k": 50}}
    tests = {"gap_leak": {"p": 1e-5}, "correct_strict": {"p": 0.4}}
    retr = {"n": 10, "gold_retrieved_across_subqueries_pct": 90.0, "recall_at5_original_pct": 55.0}
    p = mh.predictions(m_ours, m_base, tests, retr)
    assert all(p.values())
    retr["recall_at5_original_pct"] = 75.0
    assert not mh.predictions(m_ours, m_base, tests, retr)["P5_recall_across_ge_80_and_at5_lt_70"]
