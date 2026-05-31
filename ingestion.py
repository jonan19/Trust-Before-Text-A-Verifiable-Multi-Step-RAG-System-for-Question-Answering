"""
ingestion.py — V4 Document Ingestion Pipeline for the Trust Before Text RAG system.

Responsibilities:
    1. Load documents from the data/ directory (.txt and .pdf)
    2. Split documents into semantically coherent chunks
    3. Generate embeddings using sentence-transformers
    4. Store chunks + embeddings into a persistent ChromaDB collection

V4 changes:
    - Incremental ingestion: a SHA-256 manifest (chroma_db/manifest.json) tracks
      which files have been ingested. Only new or changed files are processed;
      unchanged files are skipped. Deleted files have their chunks removed.
    - Embedding model name is stored in the manifest so main.py can detect
      model mismatches and trigger a forced re-ingest automatically.
    - Sentence-aware chunking: if NLTK is installed, sentences are accumulated
      into chunks instead of splitting at a hard character boundary. Falls back
      to the character-level chunker (with sentence/word boundary heuristics) if
      NLTK is not installed.
    - PDF loading extracts section headings from the PDF outline (TOC) when
      available, falling back to "Page N" labelling.

Public API:
    ingest_documents(data_dir, chroma_dir, collection_name, force) -> int
    collection_is_empty(chroma_dir, collection_name)                -> bool
    get_manifest_model(chroma_dir)                                  -> str | None
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Iterator

import chromadb
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
EMBEDDING_MODEL:   str = "multi-qa-MiniLM-L6-cos-v1"  # optimised for query-to-passage retrieval
CHUNK_SIZE:        int = 400   # target characters per chunk
CHUNK_OVERLAP:     int = 80    # overlap characters between consecutive chunks
COLLECTION_NAME:   str = "rag_documents"
MANIFEST_FILENAME: str = "manifest.json"   # stored inside chroma_dir

# Single shared model instance (lazy-loaded)
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    """Lazy-load and cache the embedding model."""
    global _model
    if _model is None:
        print(f"  [Ingestion] Loading embedding model: {EMBEDDING_MODEL} ...")
        _model = SentenceTransformer(EMBEDDING_MODEL)
        print(f"  [Ingestion] Model loaded.")
    return _model


# ===========================================================================
# 1. Manifest helpers  (V4 — incremental ingestion)
# ===========================================================================

def _file_sha256(filepath: Path) -> str:
    """Return the SHA-256 hex digest of a file's byte content."""
    h = hashlib.sha256()
    h.update(filepath.read_bytes())
    return h.hexdigest()


def _load_manifest(chroma_dir: Path) -> dict:
    """
    Load the ingestion manifest from *chroma_dir*/manifest.json.

    Schema:
        {
            "embedding_model": str,         # model used to build the index
            "files": {
                "filename.txt": "sha256hex",
                ...
            }
        }

    Returns an empty dict if the manifest does not exist or is corrupt.
    """
    manifest_path = chroma_dir / MANIFEST_FILENAME
    if not manifest_path.exists():
        return {}
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_manifest(chroma_dir: Path, manifest: dict) -> None:
    """Persist the manifest to *chroma_dir*/manifest.json."""
    manifest_path = chroma_dir / MANIFEST_FILENAME
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def get_manifest_model(chroma_dir: str | Path = "chroma_db") -> str | None:
    """
    Return the embedding model recorded in the manifest, or None if absent.
    Used by main.py to detect model mismatches at startup.
    """
    manifest = _load_manifest(Path(chroma_dir))
    return manifest.get("embedding_model")


# ===========================================================================
# 2. Document Loaders
# ===========================================================================

def _load_txt(filepath: Path) -> list[dict]:
    """
    Load a plain-text file and split it into logical sections.

    Strategy: two-pass setext-style heading detection.
      Pass 1 — identify heading lines: a non-empty line immediately followed
               by a line of pure dashes or equals signs (≥ 3 chars).
      Pass 2 — walk lines, flushing blocks at each heading boundary.

    Section names are cleaned of leading "Section N:" prefixes.
    Lines that are pure separators (----, ====) are silently skipped.
    """
    text  = filepath.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    # ── Pass 1: find heading line indices ───────────────────────────────
    _SEPARATOR = re.compile(r"^[-=]{3,}\s*$")
    heading_indices: set[int] = set()
    for i in range(1, len(lines)):
        if _SEPARATOR.match(lines[i].strip()) and lines[i - 1].strip():
            heading_indices.add(i - 1)   # the line BEFORE the dashes is the heading

    # ── Pass 2: collect blocks ───────────────────────────────────────────
    blocks:          list[dict] = []
    current_section: str        = filepath.stem
    current_lines:   list[str]  = []

    i = 0
    while i < len(lines):
        stripped = lines[i].strip()

        if i in heading_indices:
            # Flush previous block
            if current_lines:
                blocks.append({"text": " ".join(current_lines), "section": current_section})
                current_lines = []
            # Strip leading "Section N:" or "Section N." prefix for cleaner names
            clean = re.sub(r"^Section\s+\d+[:.]\s*", "", stripped, flags=re.IGNORECASE).strip()
            current_section = clean if clean else stripped
            i += 2   # skip heading line + separator line
            continue

        if _SEPARATOR.match(stripped):
            i += 1   # skip orphaned separator lines
            continue

        if stripped:
            current_lines.append(stripped)

        i += 1

    # Flush final block
    if current_lines:
        blocks.append({"text": " ".join(current_lines), "section": current_section})

    return blocks


def _load_pdf(filepath: Path) -> list[dict]:
    """
    Load a PDF file using PyMuPDF (fitz).

    Attempts to extract section headings from the document outline (TOC/bookmarks).
    Falls back to "Page N" section labels when no outline is available.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError(
            "PyMuPDF is required for PDF loading. Run: pip install PyMuPDF"
        )

    doc = fitz.open(str(filepath))

    # Build a page → section name map from the PDF outline (if available)
    page_section: dict[int, str] = {}
    try:
        toc = doc.get_toc()  # [[level, title, page_num], ...]
        for _level, title, page_num in toc:
            # page_num is 1-indexed; mark from that page onward until next entry
            page_section[page_num - 1] = title.strip()
    except Exception:
        pass

    blocks: list[dict] = []
    current_section = filepath.stem

    for page_num, page in enumerate(doc):
        # Update section from TOC if this page has an entry
        if page_num in page_section:
            current_section = page_section[page_num]
        elif not page_section:
            current_section = f"Page {page_num + 1}"

        text = page.get_text("text").strip()
        if text:
            blocks.append({
                "text":    text,
                "section": current_section,
            })

    doc.close()
    return blocks


def _load_document(filepath: Path) -> list[dict]:
    """Dispatch to the appropriate loader based on file extension."""
    ext = filepath.suffix.lower()
    if ext == ".txt":
        return _load_txt(filepath)
    elif ext == ".pdf":
        return _load_pdf(filepath)
    else:
        return []   # unsupported format — silently skip


# ===========================================================================
# 3. Chunking  (V4 — NLTK sentence-aware)
# ===========================================================================

def _chunk_by_sentences(text: str, chunk_size: int = CHUNK_SIZE,
                         overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Split *text* into overlapping chunks that respect sentence boundaries,
    using NLTK's punkt sentence tokenizer.

    Sentences are accumulated until adding the next sentence would exceed
    *chunk_size* characters. When a chunk is committed, the last few sentences
    (totalling ≤ *overlap* characters) are carried forward as context for the
    next chunk.
    """
    import nltk
    try:
        sentences = nltk.sent_tokenize(text)
    except LookupError:
        nltk.download("punkt_tab", quiet=True)
        sentences = nltk.sent_tokenize(text)

    if not sentences:
        return []

    chunks: list[str]   = []
    current: list[str]  = []
    current_len: int    = 0

    for sentence in sentences:
        sent_len = len(sentence)

        if current and current_len + 1 + sent_len > chunk_size:
            # Commit current chunk
            chunks.append(" ".join(current).strip())

            # Carry-forward overlap: keep trailing sentences ≤ overlap chars
            overlap_sents: list[str] = []
            overlap_len = 0
            for s in reversed(current):
                if overlap_len + len(s) + 1 <= overlap:
                    overlap_sents.insert(0, s)
                    overlap_len += len(s) + 1
                else:
                    break
            current     = overlap_sents + [sentence]
            current_len = sum(len(s) for s in current) + max(0, len(current) - 1)
        else:
            current.append(sentence)
            current_len += sent_len + (1 if len(current) > 1 else 0)

    if current:
        chunks.append(" ".join(current).strip())

    return [c for c in chunks if c.strip()]


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE,
                overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Split *text* into overlapping chunks.

    Preferred path: NLTK sentence-aware chunking (V4) for coherent chunk boundaries.
    Fallback: character-level chunking with sentence/word boundary heuristics.
    """
    if len(text) <= chunk_size:
        return [text.strip()] if text.strip() else []

    # Try NLTK sentence-aware chunking
    try:
        return _chunk_by_sentences(text, chunk_size, overlap)
    except Exception:
        pass  # fall through to character-level fallback

    # Character-level fallback (original V3 behaviour)
    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        if end >= len(text):
            chunk = text[start:].strip()
            if chunk:
                chunks.append(chunk)
            break

        # Prefer sentence boundary
        boundary = text.rfind(". ", start, end)
        if boundary == -1 or boundary <= start:
            # Fall back to word boundary
            boundary = text.rfind(" ", start, end)
        if boundary == -1 or boundary <= start:
            boundary = end  # hard cut

        chunk = text[start: boundary + 1].strip()
        if chunk:
            chunks.append(chunk)

        # Next chunk starts with overlap
        start = max(start + 1, boundary + 1 - overlap)

    return chunks


# ===========================================================================
# 4. Chunk iteration
# ===========================================================================

def _iter_document_chunks(
    data_dir: Path,
    files: list[Path],
) -> Iterator[tuple[str, str, int, str]]:
    """
    Yield (text, source, chunk_id, section) tuples for every chunk
    across all specified *files* in *data_dir*.

    Section labels are made unique when a logical block splits into > 1 chunk
    (e.g. "Leave Policy [1]", "Leave Policy [2]") to prevent validation.py
    Stage 4 from treating consecutive chunks of the same section as conflicting.
    """
    for filepath in files:
        print(f"  [Ingestion] Processing: {filepath.name}")
        blocks = _load_document(filepath)

        chunk_id = 0
        for block in blocks:
            raw_text = block["text"]
            section  = block["section"]

            block_chunks = list(_chunk_text(raw_text))

            for idx, chunk_text in enumerate(block_chunks):
                # Unique section label for multi-chunk blocks
                section_label = section if len(block_chunks) == 1 else f"{section} [{idx + 1}]"
                yield (chunk_text, filepath.name, chunk_id, section_label)
                chunk_id += 1


# ===========================================================================
# 5. Ingestion pipeline  (V4 — incremental)
# ===========================================================================

def ingest_documents(
    data_dir:        str | Path = "data",
    chroma_dir:      str | Path = "chroma_db",
    collection_name: str        = COLLECTION_NAME,
    force:           bool       = False,
) -> int:
    """
    Ingest documents from *data_dir* into ChromaDB — incrementally by default.

    V4 incremental behaviour:
        - Files whose SHA-256 hash matches the stored manifest are skipped.
        - Changed or new files are ingested; their old chunks are first deleted.
        - Files removed from data_dir have their chunks deleted from ChromaDB.
        - A manifest.json in *chroma_dir* tracks hashes and the embedding model.

    Parameters
    ----------
    data_dir        : Directory containing source documents.
    chroma_dir      : Path for ChromaDB persistent storage.
    collection_name : Name of the ChromaDB collection.
    force           : If True, drop and recreate the entire collection (full re-ingest).

    Returns
    -------
    Total number of chunks currently in the collection after ingestion.
    """
    data_dir   = Path(data_dir)
    chroma_dir = Path(chroma_dir)
    chroma_dir.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=str(chroma_dir))

    # ── Full rebuild if forced ────────────────────────────────────────────
    if force:
        try:
            client.delete_collection(collection_name)
            print(f"  [Ingestion] Dropped existing collection '{collection_name}'.")
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )

    # ── Discover source files ─────────────────────────────────────────────
    supported      = {".txt", ".pdf"}
    _SKIP_PREFIXES = {"readme", "changelog", "license", "licence"}
    all_files = sorted(
        f for f in data_dir.iterdir()
        if f.is_file()
        and f.suffix.lower() in supported
        and f.stem.lower() not in _SKIP_PREFIXES
    )

    if not all_files:
        print(f"  [Ingestion] WARNING: No .txt or .pdf files found in {data_dir}")
        return collection.count()

    # ── Load manifest (hash + model tracking) ────────────────────────────
    manifest: dict = {} if force else _load_manifest(chroma_dir)
    stored_hashes: dict[str, str] = manifest.get("files", {})

    # ── Classify files: new/changed vs unchanged ──────────────────────────
    current_hashes: dict[str, str] = {f.name: _file_sha256(f) for f in all_files}
    current_names:  set[str]       = {f.name for f in all_files}

    to_ingest: list[Path] = []
    unchanged: list[str]  = []

    for filepath in all_files:
        name = filepath.name
        if stored_hashes.get(name) == current_hashes[name]:
            unchanged.append(name)
        else:
            to_ingest.append(filepath)

    # Files removed from data_dir → delete their chunks from ChromaDB
    removed = set(stored_hashes.keys()) - current_names
    for fname in removed:
        print(f"  [Ingestion] Removing deleted file: {fname}")
        try:
            collection.delete(where={"source": fname})
        except Exception:
            pass

    if unchanged:
        print(f"  [Ingestion] {len(unchanged)} file(s) unchanged — skipping.")

    if not to_ingest:
        print("  [Ingestion] Nothing new to ingest.")
        _save_manifest(chroma_dir, {
            "embedding_model": EMBEDDING_MODEL,
            "files": current_hashes,
        })
        return collection.count()

    # ── Delete stale chunks for changed files ─────────────────────────────
    for filepath in to_ingest:
        name = filepath.name
        if name in stored_hashes:
            print(f"  [Ingestion] Replacing changed file: {name}")
            try:
                collection.delete(where={"source": name})
            except Exception:
                pass

    # ── Collect all chunks for the files to ingest ────────────────────────
    model = _get_model()

    texts:      list[str] = []
    sources:    list[str] = []
    chunk_ids:  list[int] = []
    sections:   list[str] = []

    for text, source, chunk_id, section in _iter_document_chunks(data_dir, to_ingest):
        texts.append(text)
        sources.append(source)
        chunk_ids.append(chunk_id)
        sections.append(section)

    if not texts:
        print("  [Ingestion] No chunks to ingest.")
        _save_manifest(chroma_dir, {
            "embedding_model": EMBEDDING_MODEL,
            "files": current_hashes,
        })
        return collection.count()

    print(f"  [Ingestion] Generating embeddings for {len(texts)} chunks ...")
    embeddings = model.encode(texts, show_progress_bar=False).tolist()

    # Build ChromaDB ids (must be unique strings)
    ids = [f"{src}::chunk_{cid}" for src, cid in zip(sources, chunk_ids)]

    # Batch upsert into ChromaDB
    BATCH_SIZE = 100
    for i in range(0, len(texts), BATCH_SIZE):
        sl = slice(i, i + BATCH_SIZE)
        collection.upsert(
            ids        = ids[sl],
            embeddings = embeddings[sl],
            documents  = texts[sl],
            metadatas  = [
                {"source": s, "chunk_id": c, "section": sec}
                for s, c, sec in zip(sources[sl], chunk_ids[sl], sections[sl])
            ],
        )

    total = collection.count()
    print(f"  [Ingestion] Done. {len(texts)} new chunks stored ({total} total in '{collection_name}').")

    # ── Update manifest ───────────────────────────────────────────────────
    _save_manifest(chroma_dir, {
        "embedding_model": EMBEDDING_MODEL,
        "files": current_hashes,
    })

    return total


# ===========================================================================
# 6. Utility: check if collection is empty
# ===========================================================================

def collection_is_empty(
    chroma_dir:      str | Path = "chroma_db",
    collection_name: str        = COLLECTION_NAME,
) -> bool:
    """
    Return True if the ChromaDB collection does not exist or has no documents.

    Used by main.py to decide whether to trigger auto-ingestion on startup.
    """
    chroma_dir = Path(chroma_dir)
    if not chroma_dir.exists():
        return True

    try:
        client = chromadb.PersistentClient(path=str(chroma_dir))
        collection = client.get_collection(collection_name)
        return collection.count() == 0
    except Exception:
        return True


# ===========================================================================
# CLI entry point
# ===========================================================================

if __name__ == "__main__":
    import sys
    force_flag = "--force" in sys.argv
    n = ingest_documents(force=force_flag)
    print(f"\nTotal chunks in collection: {n}")
