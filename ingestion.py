from pathlib import Path
from typing import Iterable, Tuple
import json

from document_preprocessing import DocumentChunker, DocumentLoader

COLLECTION_NAME = "trust_before_text_chunks"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
MANIFEST_FILENAME = "manifest.json"


def _build_docx_section_map(filepath: Path) -> list[tuple[int, str]]:
    """
    Parse a DOCX file and return a list of (char_offset, section_heading) pairs.

    Walk every paragraph in document order, tracking the most recently seen
    Heading-style paragraph. Each paragraph's approximate character offset in
    the flattened text is recorded alongside the heading active at that point.

    Returns an empty list if python-docx is unavailable or the file has no
    heading paragraphs (caller will fall back to section="unknown").
    """
    try:
        from docx import Document as _DocxDocument
    except ImportError:
        return []

    try:
        doc = _DocxDocument(str(filepath))
    except Exception:
        return []

    section_map: list[tuple[int, str]] = []
    current_heading = "unknown"
    offset = 0

    for para in doc.paragraphs:
        text = para.text
        style = para.style.name if para.style else ""
        if style.startswith("Heading") and text.strip():
            current_heading = text.strip()
        section_map.append((offset, current_heading))
        offset += len(text) + 1  # +1 for the newline between paragraphs

    return section_map


def _section_for_chunk(chunk_text: str, full_text: str,
                        section_map: list[tuple[int, str]]) -> str:
    """
    Given a chunk's text and the document's section map, return the
    heading that was active when this chunk appeared in the document.

    Anchors the search using the first 60 characters of the chunk text.
    Falls back to "unknown" if the anchor text is not found in the full text.
    """
    if not section_map:
        return "unknown"
    anchor = chunk_text[:60].strip()
    if not anchor:
        return "unknown"
    chunk_start = full_text.find(anchor)
    if chunk_start < 0:
        return "unknown"
    # Walk the section map backwards to find the latest heading at or before this offset
    heading = "unknown"
    for offset, h in section_map:
        if offset <= chunk_start:
            heading = h
        else:
            break
    return heading


def _iter_document_chunks(data_dir: Path, source_files: list[Path]) -> Iterable[Tuple[str, str, int, str]]:
    """
    Yields (text, source, chunk_id, section) for all files.

    Section tagging (V5):
        DOCX files: section is the nearest parent Heading-style paragraph,
                    making citations and same-section conflict detection meaningful.
        PDF / TXT:  section is "unknown" (no heading structure available).
    """
    chunker = DocumentChunker(chunk_size=500, chunk_overlap=50)
    loader = DocumentLoader()

    for filepath in source_files:
        try:
            text = loader.load_document(str(filepath))
            chunks = chunker.chunk_document(text, source_document=filepath.name)

            # Build heading map for DOCX; empty list for other formats.
            section_map = (
                _build_docx_section_map(filepath)
                if filepath.suffix.lower() == ".docx"
                else []
            )

            for i, chunk in enumerate(chunks):
                section = _section_for_chunk(chunk.text, text, section_map)
                yield (chunk.text, chunk.source_document, i, section)

        except Exception as e:
            print(f"Error reading {filepath}: {e}")


def get_manifest_model(db_dir: Path | str) -> str | None:
    """Read the embedding model name recorded in the Qdrant manifest."""
    manifest_path = Path(db_dir) / MANIFEST_FILENAME
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8")).get("embedding_model")
    except Exception:
        return None
