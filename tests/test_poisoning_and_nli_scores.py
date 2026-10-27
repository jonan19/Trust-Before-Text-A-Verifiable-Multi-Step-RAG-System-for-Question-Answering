"""
evaluation/preingestion_poisoning.py and evaluation/nli_scores.py: the parts that
need no model, store or network.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evaluation"))

import nli_scores  # noqa: E402
import preingestion_poisoning as pp  # noqa: E402
from adversarial_gap_probes import GAPS  # noqa: E402


@pytest.mark.parametrize("corpus", ["1", "2"])
def test_attack_cases_are_six_gaps_times_two_styles(corpus):
    cases = pp.attack_cases(corpus)
    assert len(cases) == 12
    assert {c[1] for c in cases} == {"authority", "aware"}
    assert {c[0] for c in cases} == {g[0] for g in GAPS[corpus]}
    facts = {g[0]: g[2] for g in GAPS[corpus]}
    assert all(facts[qid] in text for qid, _, _, text in cases)


def test_unsafe_needs_an_answer_and_the_fabricated_document():
    assert pp.is_unsafe("answer", True)
    assert not pp.is_unsafe("answer", False)
    assert not pp.is_unsafe("insufficient", True)
    assert not pp.is_unsafe("conflict", True)


def test_refuses_rag_overrides(monkeypatch):
    monkeypatch.setenv("RAG_ANSWERHOOD_MARGIN", "0")
    with pytest.raises(SystemExit):
        pp.refuse_if_overridden()


class FakeModel:
    """Contradiction probability 0.2 for (a, b) and 0.9 for (b, a)."""

    def predict(self, pairs, apply_softmax=True):
        a, b = pairs[0]
        return [[0.2 if a < b else 0.9, 0.0, 0.0]]


def test_recorder_keeps_the_original_verdict_and_records_the_max():
    calls = []

    def original(a, b):
        calls.append((a, b))
        return False

    validation = SimpleNamespace(_has_nli_contradiction=original,
                                 _get_nli_model=lambda: FakeModel())
    seen = []
    wrapped = nli_scores.make_recorder(validation, seen)
    assert wrapped("a", "b") is False          # the original's answer, not the score's
    assert calls == [("a", "b")]
    assert seen == [{"a": "a", "b": "b", "score": 0.9}]


def test_recorder_records_nothing_without_a_model():
    validation = SimpleNamespace(_has_nli_contradiction=lambda a, b: True,
                                 _get_nli_model=lambda: None)
    seen = []
    assert nli_scores.make_recorder(validation, seen)("x", "y") is True
    assert seen == []
