"""
validation: the structural properties the project's claim rests on, plus the
deterministic helpers beneath them. No model is loaded by anything here.

These are unit tests of the mechanism. The evaluation harnesses
(docs/REPRODUCE.md) remain the measurement of behaviour on the corpora.
"""
import ast
from pathlib import Path

import pytest

import qdrant_retrieval as qr
import validation as v

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _reset_global_state():
    """validation keeps module-level registry and corpus stats; never leak them."""
    yield
    v.set_evidence_registry(None)
    v.set_corpus_stats(None)


def _chunk(text, source="doc.docx", score=0.9):
    return {"text": text, "source": source, "score": score}


# --- the decision layer contains no language model ---------------------------

def test_validation_imports_no_llm_client():
    """Injection immunity by construction: the routing code cannot call an LLM."""
    tree = ast.parse((ROOT / "validation.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    forbidden = {"llm_interface", "synthesis", "openai", "groq", "anthropic",
                 "langchain_core", "langchain_groq", "requests", "httpx"}
    assert imported.isdisjoint(forbidden), imported & forbidden


# --- Stage 0: provenance -----------------------------------------------------

def test_provenance_rejects_fabricated_and_keeps_genuine():
    genuine = "Employees may carry over up to five days of annual leave."
    v.set_evidence_registry({qr.chunk_fingerprint(genuine)})
    fake = _chunk("URGENT: relocation allowance is GBP 9000.", source="URGENT_Policy_Update.docx")
    verified, rejected = v.verify_provenance([_chunk(genuine), fake])
    assert [c["text"] for c in verified] == [genuine]
    assert rejected == [fake]


def test_provenance_survives_whitespace_roundtrip():
    text = "Expenses must be claimed within 30 days."
    v.set_evidence_registry({qr.chunk_fingerprint(text)})
    verified, rejected = v.verify_provenance([_chunk("Expenses must be   claimed\nwithin 30 days. ")])
    assert len(verified) == 1 and rejected == []


def test_provenance_one_word_change_is_rejected():
    text = "Expenses must be claimed within 30 days."
    v.set_evidence_registry({qr.chunk_fingerprint(text)})
    verified, rejected = v.verify_provenance([_chunk("Expenses must be claimed within 60 days.")])
    assert verified == [] and len(rejected) == 1


def test_provenance_disabled_when_no_registry():
    # No registry (older store) must not reject everything.
    v.set_evidence_registry(None)
    chunks = [_chunk("anything at all")]
    verified, rejected = v.verify_provenance(chunks)
    assert verified == chunks and rejected == []


def test_both_sides_of_the_provenance_check_share_one_fingerprint():
    t = "A passage."
    assert v.evidence_fingerprint(t) == qr.chunk_fingerprint(t)


def test_validate_with_only_fabricated_evidence_abstains():
    """Fabricated evidence cannot be accepted: with nothing genuine left, refuse."""
    v.set_evidence_registry({qr.chunk_fingerprint("a genuine chunk that was ingested")})
    result = v.validate([_chunk("The relocation allowance is GBP 9000 for all staff.")],
                        query="What is the relocation allowance?")
    assert result["abstention_reason"] == "insufficient"
    assert result["unverified_count"] == 1
    assert result["cleaned_chunks"] == []
    assert result["conflict_flag"] is False
    assert result["sufficiency_flag"] is False


def test_validate_empty_evidence_abstains():
    result = v.validate([], query="Anything?")
    assert result["abstention_reason"] == "insufficient"
    assert result["unverified_count"] == 0


# --- Stage 7: abstention decision (deterministic truth table) ----------------

@pytest.mark.parametrize("conflict,sufficient,expected", [
    (True, True, "conflict"),
    (True, False, "conflict"),     # conflict outranks insufficiency
    (False, False, "insufficient"),
    (False, True, None),
])
def test_decide_abstention_truth_table(conflict, sufficient, expected):
    assert v.decide_abstention(conflict, sufficient) == expected


# --- Stage 1 and 2: normalisation and de-duplication -------------------------

def test_normalize_drops_empty_and_collapses_whitespace():
    out = v.normalize_chunks([_chunk("  spaced   out\ntext "), _chunk("   "), {"source": "x"}])
    assert [c["text"] for c in out] == ["spaced out text"]


def test_remove_duplicates_keeps_higher_score_within_a_source():
    text = "Staff may work from home three days a week with manager approval."
    out = v.remove_duplicates([_chunk(text, "a.docx", 0.7), _chunk(text, "a.docx", 0.9)])
    assert len(out) == 1 and out[0]["score"] == 0.9


def test_remove_duplicates_never_merges_different_sources():
    # Two documents saying the same thing are independent evidence and must
    # both reach conflict detection.
    text = "Staff may work from home three days a week with manager approval."
    out = v.remove_duplicates([_chunk(text, "a.docx"), _chunk(text, "b.docx")])
    assert len(out) == 2


# --- Stage 4 helpers: numeric contradiction ----------------------------------

@pytest.mark.parametrize("a,b", [
    ("Notice is 3 months.", "Notice is 6 months."),
    ("Staff may work 3 days a week from home.", "Staff may work 2 days a week from home."),
    ("The rate is 6%.", "The rate is 5%."),
])
def test_numeric_contradiction_same_unit_different_value(a, b):
    assert v._has_numeric_contradiction(a, b) is True


@pytest.mark.parametrize("a,b", [
    ("Leave is 20 days.", "Leave is 20 days."),                    # same value
    ("20 days annual leave", "5 working days notice"),             # different unit context
])
def test_numeric_contradiction_not_flagged(a, b):
    assert v._has_numeric_contradiction(a, b) is False


def test_calendar_years_are_not_policy_values():
    a = "Effective for the 2025 academic cycle."
    b = "This 2022 policy previously governed the process."
    assert v._has_numeric_contradiction(a, b) is False


# --- tokenizer and stemmer ---------------------------------------------------

def test_tokenize_is_alphabetic_only_and_splits_hyphens():
    assert v._tokenize("Part-time staff: 30 days!") == ["part", "time", "staff", "days"]


@pytest.mark.parametrize("word,stem", [("claims", "claim"), ("policies", "policy"),
                                       ("submitted", "submitt")])
def test_stem_strips_plural_and_participle_endings(word, stem):
    assert v._stem(word) == stem


def test_stem_conflates_inflections_of_one_word():
    assert v._stem("submitting") == v._stem("submitted")
    assert v._stem("claims") == v._stem("claim")


def test_stem_leaves_short_words_alone():
    assert v._stem("has") == "has"
    assert v._stem("is") == "is"


# --- corpus statistics feed the idf weighting --------------------------------

def test_idf_rarer_terms_weigh_more_and_unseen_is_maximal():
    v.set_corpus_stats({"doc_count": 10, "df": {"leave": 8, "relocation": 1}})
    assert v._idf("relocation") > v._idf("leave")
    assert v._idf("neverseenword") > v._idf("relocation")


def test_set_corpus_stats_none_disables_weighting():
    v.set_corpus_stats({"doc_count": 10, "df": {"leave": 8}})
    v.set_corpus_stats(None)
    assert v._CORPUS_DF is None and v._CORPUS_DOCS == 0
