from pathlib import Path
from typing import Iterable, Tuple
import json

from document_preprocessing import DocumentChunker, DocumentLoader

COLLECTION_NAME = "trust_before_text_chunks"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
MANIFEST_FILENAME = "manifest.json"

def _iter_document_chunks(data_dir: Path, source_files: list[Path]) -> Iterable[Tuple[str, str, int, str]]:
    """Yields (text, source, chunk_id, section) for all files."""
    chunker = DocumentChunker(chunk_size=500, chunk_overlap=50)
    loader = DocumentLoader()
    
    for filepath in source_files:
        try:
            text = loader.load_document(str(filepath))
            chunks = chunker.chunk_document(text, source_document=filepath.name)
            for i, chunk in enumerate(chunks):
                yield (chunk.text, chunk.source_document, i, "unknown")
        except Exception as e:
            print(f"Error reading {filepath}: {e}")

def get_manifest_model(db_dir: Path | str) -> str | None:
    manifest_path = Path(db_dir) / MANIFEST_FILENAME
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8")).get("embedding_model")
    except Exception:
        return None

def collection_is_empty(chroma_dir: Path | str, collection_name: str = COLLECTION_NAME) -> bool:
    chroma_dir = Path(chroma_dir)
    if not chroma_dir.exists():
        return True
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(chroma_dir))
        return client.get_collection(collection_name).count() == 0
    except Exception:
        return True

def ingest_documents(data_dir: Path | str, chroma_dir: Path | str, force: bool = False) -> int:
    import chromadb
    from sentence_transformers import SentenceTransformer
    data_dir = Path(data_dir)
    chroma_dir = Path(chroma_dir)
    chroma_dir.mkdir(parents=True, exist_ok=True)
    
    supported = {".txt", ".pdf", ".docx"}
    source_files = sorted(f for f in data_dir.iterdir() if f.is_file() and f.suffix.lower() in supported)
    if not source_files:
        return 0
        
    client = chromadb.PersistentClient(path=str(chroma_dir))
    if force:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
            
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )
    
    chunks = list(_iter_document_chunks(data_dir, source_files))
    if not chunks:
        return 0
        
    model = SentenceTransformer(EMBEDDING_MODEL)
    texts = [c[0] for c in chunks]
    embeddings = model.encode(texts, show_progress_bar=False).tolist()
    
    batch_size = 100
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i+batch_size]
        batch_texts = [b[0] for b in batch]
        batch_ids = [f"{b[1]}_{b[2]}" for b in batch]
        batch_metadatas = [{"source": b[1], "chunk_id": b[2], "section": b[3]} for b in batch]
        batch_embeddings = embeddings[i:i+batch_size]
        
        collection.add(
            documents=batch_texts,
            embeddings=batch_embeddings,
            metadatas=batch_metadatas,
            ids=batch_ids
        )
        
    manifest = {"embedding_model": EMBEDDING_MODEL}
    (chroma_dir / MANIFEST_FILENAME).write_text(json.dumps(manifest), encoding="utf-8")
    
    return collection.count()
