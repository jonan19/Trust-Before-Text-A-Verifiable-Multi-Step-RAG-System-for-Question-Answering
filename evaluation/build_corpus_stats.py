"""
build_corpus_stats.py — Compute chunk-level document frequencies for a corpus.

Reads every chunk from the corpus's Qdrant collection (the same units retrieval
scores) and writes a {doc_count, df} sidecar used by focus.CorpusStats.

    python evaluation/build_corpus_stats.py --corpus 1
"""

from __future__ import annotations

import argparse
from pathlib import Path

import harness_bootstrap  # noqa: F401
import harness
from focus import CorpusStats

OUT = Path(__file__).resolve().parent / "corpus_stats"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", choices=sorted(harness.CORPORA), required=True)
    args = ap.parse_args()

    # Chunk the source documents with the same chunker ingestion uses, rather
    # than reading the Qdrant collection: identical units, and it does not need
    # a write lock on a store another process may hold open.
    import qdrant_retrieval as qr
    from ingestion import _iter_document_chunks

    data_dir = harness.CORPORA[args.corpus]["data"]
    files = qr._iter_source_files(data_dir)
    texts = [c[0] for c in _iter_document_chunks(data_dir, files)]

    stats = CorpusStats.from_texts(texts)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"corpus{args.corpus}.json"
    stats.save(path)
    print(f"{len(texts)} chunks, {len(stats.df)} stems -> {path}")


if __name__ == "__main__":
    main()
