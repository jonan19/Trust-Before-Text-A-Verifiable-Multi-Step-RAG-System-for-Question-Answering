"""
qdrant_retrieval: the pure helpers that need no vector store and no model.

Covers the provenance fingerprint and registry, corpus statistics, the local
BM25-style sparse encoder, reciprocal-rank fusion and cosine similarity.
"""
import json
from types import SimpleNamespace

import pytest

import qdrant_retrieval as qr


# --- provenance fingerprint -------------------------------------------------

def test_fingerprint_ignores_whitespace_differences():
    a = "Staff may work from home 3 days a week."
    b = "  Staff may   work from home\n3 days a week.  "
    assert qr.chunk_fingerprint(a) == qr.chunk_fingerprint(b)


def test_fingerprint_changes_when_wording_changes():
    a = "Staff may work from home 3 days a week."
    b = "Staff may work from home 2 days a week."
    assert qr.chunk_fingerprint(a) != qr.chunk_fingerprint(b)


def test_fingerprint_handles_empty_and_none():
    assert qr.chunk_fingerprint("") == qr.chunk_fingerprint(None)
    assert len(qr.chunk_fingerprint("x")) == 64  # sha256 hex


# --- chunk registry ---------------------------------------------------------

def test_registry_round_trip(tmp_path):
    texts = ["alpha policy text", "beta policy text", "alpha  policy   text"]
    qr._write_chunk_registry(tmp_path, texts)
    registry = qr.load_chunk_registry(tmp_path)
    assert registry == {qr.chunk_fingerprint("alpha policy text"),
                        qr.chunk_fingerprint("beta policy text")}


def test_registry_missing_returns_none(tmp_path):
    # None (not an empty set) means "store predates the registry": provenance
    # checking stays disabled instead of rejecting every chunk.
    assert qr.load_chunk_registry(tmp_path) is None


def test_registry_corrupt_returns_none(tmp_path):
    (tmp_path / qr.CHUNK_REGISTRY_FILENAME).write_text("{not json", encoding="utf-8")
    assert qr.load_chunk_registry(tmp_path) is None


# --- corpus statistics ------------------------------------------------------

def test_corpus_stats_round_trip(tmp_path):
    qr._write_corpus_stats(tmp_path, ["employees claim expenses", "employees take leave"])
    stats = qr.load_corpus_stats(tmp_path)
    assert stats["doc_count"] == 2
    import validation
    assert stats["df"][validation._stem("employees")] == 2  # stemmed, once per chunk
    assert stats["df"][validation._stem("leave")] == 1


def test_corpus_stats_missing_returns_none(tmp_path):
    assert qr.load_corpus_stats(tmp_path) is None


# --- tokenizer and sparse encoder -------------------------------------------

def test_tokenize_lowercases_and_keeps_numbers_and_contractions():
    assert qr._tokenize("Don't claim 30 Days!") == ["don't", "claim", "30", "days"]


@pytest.fixture
def encoder():
    return qr._fit_sparse_encoder(["annual leave is 25 days", "sick leave is 10 days", "expenses"])


def test_fit_sparse_encoder_statistics(encoder):
    assert encoder["doc_count"] == 3
    assert encoder["avg_doc_length"] == pytest.approx((5 + 5 + 1) / 3)
    vocab = encoder["vocabulary"]
    assert "leave" in vocab and "expenses" in vocab
    # indices are unique and start at 1
    assert sorted(vocab.values()) == list(range(1, len(vocab) + 1))


def test_fit_sparse_encoder_empty_corpus():
    enc = qr._fit_sparse_encoder([])
    assert enc["doc_count"] == 0
    assert enc["avg_doc_length"] == 0.0
    assert enc["vocabulary"] == {}


def test_encode_sparse_query_uses_term_counts(encoder):
    vec = qr._encode_sparse("leave leave days", encoder, is_query=True)
    by_index = dict(zip(vec.indices, vec.values))
    assert by_index[encoder["vocabulary"]["leave"]] == 2.0
    assert by_index[encoder["vocabulary"]["days"]] == 1.0


def test_encode_sparse_drops_unknown_terms_and_sorts(encoder):
    vec = qr._encode_sparse("zzzunknown leave", encoder, is_query=True)
    assert vec.indices == [encoder["vocabulary"]["leave"]]
    assert qr._encode_sparse("zzzunknown", encoder, is_query=True).indices == []


def test_encode_sparse_empty_text_gives_empty_vector(encoder):
    vec = qr._encode_sparse("", encoder)
    assert vec.indices == [] and vec.values == []


def test_encode_sparse_document_weights_are_positive(encoder):
    vec = qr._encode_sparse("annual leave is 25 days", encoder)
    assert vec.indices and all(v > 0 for v in vec.values)
    assert len(vec.indices) == len(set(vec.indices))


# --- reciprocal-rank fusion -------------------------------------------------

def _pts(*ids):
    return [SimpleNamespace(id=i) for i in ids]


def test_rrf_top_in_both_lists_scores_one():
    scores = qr._rrf_scores([_pts("a", "b"), _pts("a", "c")])
    assert scores["a"] == pytest.approx(1.0)
    assert scores["a"] > scores["b"] and scores["a"] > scores["c"]


def test_rrf_scores_stay_in_unit_interval_and_rank_orders():
    scores = qr._rrf_scores([_pts("a", "b", "c"), _pts("c", "b", "a")])
    assert all(0.0 <= s <= 1.0 for s in scores.values())
    assert set(scores) == {"a", "b", "c"}
    # a and c occupy mirrored ranks, so they fuse to the same score
    assert scores["a"] == pytest.approx(scores["c"])


def test_rrf_single_list_ranks_by_position():
    scores = qr._rrf_scores([_pts("x", "y", "z")])
    assert scores["x"] > scores["y"] > scores["z"]


# --- cosine similarity ------------------------------------------------------

def test_cosine_identical_orthogonal_and_zero():
    assert qr._cosine_similarity([1, 2, 3], [1, 2, 3]) == pytest.approx(1.0)
    assert qr._cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)
    assert qr._cosine_similarity([1, 0], [-1, 0]) == pytest.approx(-1.0)
    assert qr._cosine_similarity([0, 0], [1, 1]) == 0.0
