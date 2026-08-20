"""
focus.py — Prototype of the "query focus term" idea, shared by the offline labs.

Motivation
----------
Both Limitation 1 (false conflicts from query-irrelevant pairs) and Limitation 3
(gap queries leaking through the sufficiency gate) have the same shape: the
system treats every query content word as equally meaningful, so a chunk that
merely shares a ubiquitous word ("GPA", "credit", "hours") counts as being about
the query. It is not. What makes a query *this* query is its rarest terms:
"cat", "library", "study-abroad", "Dean's List", "paternity".

A term's rarity is measured against the ingested corpus (document frequency over
chunks), which is a deterministic corpus statistic already implicit in the
retriever's BM25 stage, not a hand-tuned constant.

Matching is done on lightly stemmed tokens so that "claim" matches "claims" and
"submitting" matches "submitted": without this, evidence that genuinely answers
a question scores as if the question's words were absent.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

_WORD_RE = re.compile(r"[a-z][a-z']*")


def tokenize(text: str) -> list[str]:
    """
    Alphabetic tokens only, hyphens treated as separators.

    Numerals are excluded on purpose: a figure in the question ("a gift worth
    GBP 70", "45 days ago") is the value being asked ABOUT, so its absence from
    the evidence says nothing about whether the evidence answers the question.
    Hyphenated compounds are split so "per-credit-hour" can match "per credit
    hour" -- writing conventions differ between documents and corpora, and a
    gate that turns on hyphenation is a gate that fails on the next corpus.
    """
    return _WORD_RE.findall(text.lower().replace("-", " "))


def stem(word: str) -> str:
    """
    Deliberately conservative suffix stripping: plural/participle endings only.

    A full Porter stemmer would conflate more aggressively (e.g. "policy" and
    "police"), which for a policy corpus is exactly the wrong trade. The goal is
    only to stop morphology from hiding a term that is plainly present.
    """
    w = word
    for suf, repl in (("ies", "y"), ("ied", "y"), ("sses", "ss"), ("ing", ""),
                      ("ed", ""), ("es", ""), ("s", "")):
        if w.endswith(suf) and len(w) - len(suf) + len(repl) >= 3:
            return w[: len(w) - len(suf)] + repl
    return w


def stems(text: str) -> set[str]:
    return {stem(t) for t in tokenize(text)}


def matches(term: str, evidence_stems: set[str]) -> bool:
    """
    Is `term` present in evidence, tolerating chunk-boundary truncation?

    Chunks are fixed-length character slices, so a chunk routinely begins or
    ends mid-word ("...inancial aid..." for "financial aid"). Exact stem
    equality treats such a chunk as not mentioning the term at all, which
    silently drops genuine conflicts (verified: Corpus 2 Q041, a true conflict,
    is missed for exactly this reason). A containment test in either direction,
    floored at 4 characters to avoid accidental matches on short stems,
    recovers those without loosening matching in any meaningful way.
    """
    t = stem(term)
    if t in evidence_stems:
        return True
    if len(t) < 4:
        return False
    return any(len(e) >= 4 and (e in t or t in e) for e in evidence_stems)


class CorpusStats:
    """Document frequency of every stem across the ingested chunk set."""

    def __init__(self, doc_count: int, df: dict[str, int]):
        self.doc_count = max(1, doc_count)
        self.df = df

    @classmethod
    def from_texts(cls, texts: list[str]) -> "CorpusStats":
        df: dict[str, int] = {}
        for t in texts:
            for s in stems(t):
                df[s] = df.get(s, 0) + 1
        return cls(len(texts), df)

    @classmethod
    def load(cls, path: str | Path) -> "CorpusStats":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(d["doc_count"], d["df"])

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps({"doc_count": self.doc_count, "df": self.df}, indent=1),
            encoding="utf-8")

    def idf(self, term: str) -> float:
        """Standard smoothed IDF over chunks. Unseen term -> maximum rarity."""
        return math.log((self.doc_count + 1) / (self.df.get(stem(term), 0) + 1))

    def max_idf(self) -> float:
        return math.log(self.doc_count + 1)


def focus_terms(content_terms: set[str], stats: CorpusStats, *,
                keep: float = 0.5, min_terms: int = 1) -> set[str]:
    """
    The query's discriminative terms: the rarest `keep` fraction of its content
    words, by corpus IDF.

    Rank-based rather than threshold-based on purpose. An absolute IDF cutoff is
    a corpus-calibrated constant of exactly the kind that failed to transfer
    between corpora; "the rarest half of what was asked" is a property of the
    query, and means the same thing on any corpus.
    """
    # Expand each content term through the same tokenizer, so a hyphenated or
    # punctuated query token contributes its parts, and pure numerals drop out.
    expanded: set[str] = set()
    for t in content_terms:
        expanded |= {w for w in tokenize(t) if len(w) > 2}
    content_terms = expanded
    if not content_terms:
        return set()
    ranked = sorted(content_terms, key=lambda t: (-stats.idf(t), t))
    n = max(min_terms, round(len(ranked) * keep))
    return set(ranked[:n])
