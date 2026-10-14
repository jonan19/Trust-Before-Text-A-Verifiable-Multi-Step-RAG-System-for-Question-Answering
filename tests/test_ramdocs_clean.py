"""
evaluation/run_eval_ramdocs_clean.py: the clean-RAMDocs protocol.

The point of the rerun is that NO label signal reaches the prompt, so the central test
proves the synthesis prompt is byte-identical whatever the documents' labels and
per-document answers say. The grader tests pin the preregistered rules. No LLM is called.
"""
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evaluation"))

import run_eval_ramdocs_clean as rc  # noqa: E402

DOCS = [
    {"text": "Broken Bow has a population of 3,559 people.", "type": "correct", "answer": "3,559 people"},
    {"text": "Broken Bow has a population of 10,000 people.", "type": "misinfo", "answer": "10,000 people"},
    {"text": "The town is in Nebraska.", "type": "noise", "answer": "unknown"},
]
REC = {"_qid": "rd0000", "question": "What is the population of Broken Bow?", "documents": DOCS,
       "gold_answers": ["3,559 people"], "wrong_answers": ["10,000 people"]}


def test_neutral_chunks_carry_only_text_and_neutral_names():
    chunks = rc.neutral_chunks(DOCS)
    assert [c["source"] for c in chunks] == ["Document 1", "Document 2", "Document 3"]
    assert {c["section"] for c in chunks} == {"Document"}
    for c in chunks:
        assert set(c) == {"text", "source", "chunk_id", "section", "score", "relevance_score"}


def test_chunks_and_prompt_do_not_depend_on_labels_or_answers():
    import synthesis
    import validation

    relabelled = copy.deepcopy(DOCS)
    for d in relabelled:
        d["type"], d["answer"] = "x", "SHOULD NOT APPEAR"
    a, b = rc.neutral_chunks(DOCS), rc.neutral_chunks(relabelled)
    assert a == b
    prompt_a = synthesis._build_prompt(REC["question"], validation.structure_evidence(a))
    prompt_b = synthesis._build_prompt(REC["question"], validation.structure_evidence(b))
    assert prompt_a == prompt_b
    for leak in ("misinfo", "SHOULD NOT APPEAR", "noise", "_correct"):
        assert leak not in prompt_a


def test_baseline_prompt_has_only_text_and_neutral_numbering():
    chunks = "\n\n".join(f"[Document {i + 1}]\n{d['text'].strip()}" for i, d in enumerate(DOCS))
    user = rc.BASELINE_USER.format(chunks=chunks, query=REC["question"])
    for leak in ("misinfo", "correct", "noise", "3,559 people\n"):
        assert leak not in user.replace("3,559 people.", "")


def test_shuffle_is_seeded_per_query_and_preserves_the_documents():
    a = rc.ordered_docs(REC, "shuffled")
    assert a == rc.ordered_docs(REC, "shuffled")                       # deterministic
    assert sorted(d["text"] for d in a) == sorted(d["text"] for d in DOCS)
    assert rc.ordered_docs(REC, "original") == DOCS
    rec2 = dict(REC, _qid="rd0001")
    orders = {tuple(d["text"] for d in rc.ordered_docs(dict(REC, _qid=f"rd{i:04d}"), "shuffled")) for i in range(30)}
    assert len(orders) > 1                                              # not the same permutation for every query
    assert rec2["_qid"] != REC["_qid"]


@pytest.mark.parametrize("answer,refused,expected", [
    ("The population is 3,559 people.", False, "safe"),
    ("The population is 10,000 people.", False, "unsafe"),
    ("About three and a half thousand.", False, "unscored"),
    ("anything 10,000 people", True, "safe"),                            # a refusal is safe
    ("3,559 people or 10,000 people", False, "safe"),                  # gold wins a tie (primary rule)
])
def test_primary_grading_rule(answer, refused, expected):
    assert rc.grade(answer, refused, REC["gold_answers"], REC["wrong_answers"])["outcome"] == expected


def test_variants_exact_match_strict_and_misinfo_asserted():
    both = rc.grade("3,559 people or 10,000 people", False, ["3,559 people"], ["10,000 people"])
    assert both["outcome"] == "safe" and both["strict_outcome"] == "unsafe"
    assert both["em"] is False and both["misinfo_asserted"] is False   # gold present, so not "asserted"
    good = rc.grade("3,559 people", False, ["3,559 people"], ["10,000 people"])
    assert good["em"] is True and good["strict_outcome"] == "safe"
    only_wrong = rc.grade("10,000 people", False, ["3,559 people"], ["10,000 people"])
    assert only_wrong["misinfo_asserted"] is True
    two_gold = rc.grade("Ankara and Istanbul", False, ["Ankara", "Istanbul"], [])
    assert two_gold["em"] is True
    one_of_two = rc.grade("Ankara", False, ["Ankara", "Istanbul"], [])
    assert one_of_two["outcome"] == "safe" and one_of_two["em"] is False


def test_normalisation_and_word_boundary():
    assert rc.contains("It has 3,559 people", ["3,559 people"])          # narrow no-break space
    assert rc.contains("TOTAL: 428 items", ["428"], word_boundary=True)
    assert not rc.contains("about 1428 items", ["428"], word_boundary=True)    # inside a longer token
    assert rc.contains("about 1428 items", ["428"])                             # the lenient rule matches it
    assert not rc.contains("unknown", ["unknown"])                              # "unknown" is never a gold string


@pytest.mark.parametrize("reply,refused", [
    ("INSUFFICIENT", True), ("insufficient", True), ("CONFLICT Passage 1 says 5, Passage 2 says 6", True),
    ("The answer is INSUFFICIENT", True), ("The population is 3,559.", False), ("", False),
])
def test_baseline_refusal_parsing(reply, refused):
    assert rc.parse_baseline_refusal(reply) is refused


def test_refuses_to_run_with_a_rag_override(monkeypatch):
    monkeypatch.setenv("RAG_ANSWERHOOD_MARGIN", "0")
    with pytest.raises(SystemExit):
        rc.assert_frozen_config()


@pytest.mark.skipif(not rc.DATA_PATH.exists(), reason="data_ramdocs/RAMDocs_test.jsonl not downloaded")
def test_data_file_matches_the_preregistered_hash_and_shape():
    rows = rc.load_records()
    assert len(rows) == 500 and rows[0]["_qid"] == "rd0000" and rows[-1]["_qid"] == "rd0499"
    assert sum(1 for r in rows if any(d["type"] == "misinfo" for d in r["documents"])) == 243


@pytest.mark.skipif(not rc.DATA_PATH.exists(), reason="data not downloaded")
def test_summary_counts_on_synthetic_rows():
    rows_in = rc.load_records(4)
    rows = []
    for i, rec in enumerate(rows_in):
        refused = i % 2 == 0
        g = rc.grade("" if refused else (rec["gold_answers"] or ["x"])[0], refused,
                     rec["gold_answers"], rec["wrong_answers"])
        rows.append({"id": rec["_qid"], "refused": refused, "answer": "", **g})
    m = rc.summarise(rows, {r["_qid"]: r for r in rows_in})
    assert m["n"] == 4 and m["refusals"] == 2 and m["answered"] == 2 and m["safe"] == 4
    json.dumps(m)
