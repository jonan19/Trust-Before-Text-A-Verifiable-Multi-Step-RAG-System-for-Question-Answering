from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json
import shutil
import os
from pathlib import Path

import orchestrator
import qdrant_retrieval

DATA_DIR = Path("./data")
DATA_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Trust Before Text - RAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Where documents live
# ---------------------------------------------------------------------------
# DATA_DIR ("data/") is NOT scratch space. It is Corpus 1, the evaluation
# corpus: evaluation/rerun_suite.py ingests it to rebuild qdrant_db_c1_copy,
# so deleting it makes the Corpus 1 numbers unreproducible. The UI therefore
# never writes to it and never deletes from it. It doubles as the demo set,
# because it is the corpus that contains the contradicting remote-work
# policies the system exists to catch.
#
# Uploads go beside it instead:
#   data_uploads/  permanent uploads from the UI, survive a restart
#   data_temp/     session-only uploads, purged on every startup
BASE_DIR = DATA_DIR
UPLOAD_DIR = Path("data_uploads")
TEMP_DIR = Path("data_temp")

# Whether the demo corpus is currently part of the index. Reset unloads it;
# "Load demo corpus" loads it back. Kept beside the store (gitignored) so the
# answer survives a restart.
STATE_FILE = Path("qdrant_db") / "ui_state.json"


def _ensure_dirs() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)


def _state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _set_base_loaded(loaded: bool) -> None:
    s = _state()
    s["base_loaded"] = bool(loaded)
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(s, indent=2), encoding="utf-8")
    except OSError:
        pass


def _base_loaded() -> bool:
    # Default True so a fresh checkout starts with the demo corpus indexed.
    return bool(_state().get("base_loaded", True))


def _files_in(d: Path) -> list[Path]:
    if not d.is_dir():
        return []
    supported = {".txt", ".pdf", ".docx"}
    return sorted(f for f in d.iterdir()
                  if f.is_file() and f.suffix.lower() in supported)


def _temp_names() -> set[str]:
    return {f.name for f in _files_in(TEMP_DIR)}


def _upload_names() -> set[str]:
    return {f.name for f in _files_in(UPLOAD_DIR)}


def _purge_dir(d: Path) -> int:
    removed = 0
    for f in _files_in(d):
        try:
            f.unlink()
            removed += 1
        except OSError:
            pass
    return removed


def _release_store():
    """Drop the client handle and any stale lock before touching the store."""
    from qdrant_retrieval import _close_client, DEFAULT_QDRANT_DIR
    _close_client()
    lock_file = Path(DEFAULT_QDRANT_DIR) / ".lock"
    if lock_file.exists():
        try:
            lock_file.unlink()
        except OSError:
            pass


def _empty_index() -> None:
    """Delete every point AND clear the manifest.

    Clearing the manifest is the part that was missing: /documents is built
    from it, so a dropped collection with a stale manifest showed documents
    that were not indexed at all.
    """
    from qdrant_retrieval import (DEFAULT_QDRANT_DIR, COLLECTION_NAME,
                                  _get_client, _save_manifest)
    _release_store()
    client = _get_client(DEFAULT_QDRANT_DIR)
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    _release_store()
    try:
        _save_manifest(Path(DEFAULT_QDRANT_DIR), {})
    except Exception:
        pass


def _reingest_all(force: bool = True) -> int:
    """Rebuild the live store from whatever is currently in scope.

    In scope: the demo corpus when loaded, plus permanent uploads, plus
    temporary uploads. With nothing in scope the index is emptied outright
    rather than left holding the last build.
    """
    from qdrant_retrieval import ingest_documents as qdrant_ingest
    _ensure_dirs()

    dirs = []
    if _base_loaded() and _files_in(BASE_DIR):
        dirs.append(BASE_DIR)
    for d in (UPLOAD_DIR, TEMP_DIR):
        if _files_in(d):
            dirs.append(d)

    if not dirs:
        _empty_index()
        return 0

    _release_store()
    return qdrant_ingest(data_dir=dirs[0], force=force, extra_dirs=tuple(dirs[1:]))


@app.on_event("startup")
async def startup_event():
    """Ensure the Qdrant database is ingested and consistent at startup."""
    # Temporary uploads do not survive a restart, by definition. Purge before
    # the consistency check below so the rebuilt index never contains them.
    _ensure_dirs()
    purged = _purge_dir(TEMP_DIR)
    if purged:
        print(f"  [Startup] Discarded {purged} temporary upload(s).")
    from qdrant_retrieval import (
        collection_is_empty, ingest_documents, DEFAULT_QDRANT_DIR,
        DENSE_MODEL_NAME, SPARSE_MODEL_NAME, MULTI_MODEL_NAME,
        get_manifest_model, get_manifest_sparse_model, get_manifest_multi_model
    )
    qdrant_dir = Path(DEFAULT_QDRANT_DIR)
    
    # Model consistency check
    stored_model = get_manifest_model(qdrant_dir)
    stored_sparse = get_manifest_sparse_model(qdrant_dir)
    stored_multi = get_manifest_multi_model(qdrant_dir)
    
    force = False
    if stored_model is not None and (
        stored_model != DENSE_MODEL_NAME or
        stored_sparse != SPARSE_MODEL_NAME or
        stored_multi != MULTI_MODEL_NAME
    ):
        print("  ⚠  Model mismatch detected. Forcing rebuild of Qdrant collection...")
        force = True
        
    # Always let the ingester decide. It compares every source file's hash
    # against the manifest and returns immediately when nothing changed, so a
    # normal start stays cheap. This is also what makes a document REMOVED
    # from data/ actually disappear from the index: the previous version only
    # ingested when the collection was empty, so a deleted file stayed
    # searchable until something else forced a rebuild.
    try:
        lock_file = qdrant_dir / ".lock"
        if lock_file.exists():
            try:
                lock_file.unlink()
            except OSError:
                pass
        n = _reingest_all(force=force)
        print(f"  [Startup] Index ready ({n} chunks).")
    except Exception as e:
        print(f"  [Startup] Auto-ingestion failed: {e}")


class QueryRequest(BaseModel):
    query: str
    k: int = 5

@app.get("/stats")
async def get_stats():
    """Get statistics about the indexed documents based on active retriever"""
    try:
        from qdrant_retrieval import (
            _get_client, DEFAULT_QDRANT_DIR, COLLECTION_NAME,
            _load_manifest, collection_is_empty,
        )
        from pathlib import Path as _Path

        # Gracefully handle the case where the DB hasn't been created yet
        if collection_is_empty(DEFAULT_QDRANT_DIR, COLLECTION_NAME):
            return {"total_chunks": 0, "unique_documents": 0, "retriever": "qdrant"}

        client = _get_client(DEFAULT_QDRANT_DIR)
        try:
            total_chunks = client.count(COLLECTION_NAME).count
        except Exception:
            total_chunks = 0

        manifest = _load_manifest(_Path(DEFAULT_QDRANT_DIR))
        unique_docs = len(manifest.get("files", {}))
        return {
            "total_chunks": total_chunks,
            "unique_documents": unique_docs,
            "retriever": "qdrant"
        }
    except Exception as e:
        # Return zeroes rather than a 500 so the frontend stays functional
        return {"total_chunks": 0, "unique_documents": 0, "retriever": "qdrant", "error": str(e)}

@app.post("/query")
async def query_pipeline(request: QueryRequest):
    """Query the V4 Trust Before Text RAG pipeline"""
    try:
        # Run the full V4 orchestration pipeline in a worker thread — this is
        # a fully synchronous call (retrieval, validation, and the LLM call
        # all block), and calling it directly here would block the whole
        # asyncio event loop for its entire duration, freezing every other
        # request (including unrelated ones like /stats) until it returns.
        res = await run_in_threadpool(orchestrator.run, request.query, verbose=False)
        
        # Structure the response for the frontend
        # Extract validated evidence chunks from validation_result
        validation_result = res.get("validation", {})
        cleaned_chunks = validation_result.get("cleaned_chunks", [])
        
        chunks = []
        similarity_scores = []
        raw_scores = []

        for c in cleaned_chunks:
            chunks.append({
                "source_document": c.get("source", "unknown"),
                "text": c.get("text", ""),
                "section": c.get("section", "unknown"),
                "rank": c.get("rank"),
            })
            similarity_scores.append(c.get("score", 0.0))
            raw_scores.append(c.get("relevance_score", 0.0))

        return {
            "status": res.get("synthesis_result", {}).get("status", "success"),
            "query": request.query,
            "preprocessed": res.get("preprocessed", ""),
            "decision": res.get("decision", "proceed"),
            "answer": res.get("answer", ""),
            "chunks": chunks,
            "similarity_scores": similarity_scores,
            "raw_scores": raw_scores,
            "confidence_score": validation_result.get("confidence_score", 0.0),
            "confidence_tier": validation_result.get("confidence_tier", "LOW"),
            "query_coverage_score": validation_result.get("query_coverage_score", 0.0),
            "conflict_flag": validation_result.get("conflict_flag", False),
            "sufficiency_flag": validation_result.get("sufficiency_flag", True),
            "abstention_reason": validation_result.get("abstention_reason"),
            "relevant_count": validation_result.get("relevant_count", 0),
            # Citations: populated on conflict abstain to name the conflicting sources
            "citations": res.get("synthesis_result", {}).get("citations", []),
            # Faithfulness (V5): only populated on successful synthesis
            "faithfulness_score": res.get("synthesis_result", {}).get("faithfulness_score"),
            "unsupported_sentences": res.get("synthesis_result", {}).get("unsupported_sentences", []),
            # --- Pipeline observability (full stage-by-stage trace) ---
            "query_type": res.get("query_type", "simple"),
            "sub_queries": res.get("sub_queries", []),
            "target_source": res.get("target_source"),
            "raw_chunk_count": res.get("raw_chunk_count", 0),
            "conflict_detail": validation_result.get("conflict_detail"),
            "unverified_count": validation_result.get("unverified_count", 0),
            "unverified_sources": validation_result.get("unverified_sources", []),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), mode: str = Form("permanent")):
    """Index an uploaded document, permanently or for this session only.

    mode="permanent" writes the file into data/, so it becomes part of the
    corpus and survives restarts. mode="temporary" writes it into data_temp/,
    which is purged on every startup and by DELETE /temporary. Both are
    indexed identically; the only difference is where the file lives and how
    long it lasts.
    """
    ext = Path(file.filename).suffix.lower()
    if ext not in {'.txt', '.pdf', '.docx'}:
        raise HTTPException(status_code=400, detail="Only .txt, .pdf, and .docx files are supported.")

    mode = (mode or "permanent").strip().lower()
    if mode not in {"permanent", "temporary"}:
        raise HTTPException(status_code=400, detail="mode must be 'permanent' or 'temporary'.")

    _ensure_dirs()
    target_dir = TEMP_DIR if mode == "temporary" else UPLOAD_DIR
    other_dir = UPLOAD_DIR if mode == "temporary" else TEMP_DIR

    # The manifest and every chunk's `source` field are keyed by filename, so
    # the same name in both scopes would silently shadow one document.
    if (other_dir / file.filename).exists() or (BASE_DIR / file.filename).exists():
        other = "the permanent uploads" if mode == "temporary" else "the temporary uploads"
        if (BASE_DIR / file.filename).exists():
            other = "the demo corpus"
        raise HTTPException(
            status_code=409,
            detail=f"'{file.filename}' is already indexed in {other}. Remove it there first, or rename this file.")

    file_path = target_dir / file.filename
    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

    try:
        num_chunks = _reingest_all(force=True)
        where = "for this session only" if mode == "temporary" else "permanently"
        return {
            "message": f"Indexed {file.filename} {where}",
            "num_chunks": num_chunks,
            "mode": mode,
        }
    except Exception as e:
        # Never leave a file on disk that is not in the index.
        try:
            file_path.unlink()
        except OSError:
            pass
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")


@app.delete("/temporary")
async def clear_temporary():
    """Discard every session-only upload and rebuild the index without them."""
    try:
        removed = _purge_dir(TEMP_DIR)
        num_chunks = _reingest_all(force=True) if removed else 0
        return {
            "message": (f"Discarded {removed} temporary document(s)" if removed
                        else "No temporary documents to discard"),
            "removed": removed,
            "num_chunks": num_chunks,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear temporary uploads: {e}")


@app.delete("/reset")
async def reset_index():
    """Empty the index completely: no documents, no manifest, nothing listed.

    This deletes UPLOADS only. It never deletes data/, which is Corpus 1, the
    evaluation corpus behind the published numbers; an earlier version of this
    endpoint did, and destroyed it twice. The demo corpus is unloaded rather
    than deleted, so "Load demo corpus" brings it straight back.
    """
    try:
        _ensure_dirs()
        removed = _purge_dir(UPLOAD_DIR) + _purge_dir(TEMP_DIR)
        _set_base_loaded(False)
        _empty_index()
        return {
            "message": "Index cleared. The demo corpus is unloaded but intact.",
            "removed_uploads": removed,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/demo")
async def load_demo_corpus():
    """Index the demo corpus again: the policy set that contradicts itself."""
    try:
        _ensure_dirs()
        if not _files_in(BASE_DIR):
            raise HTTPException(
                status_code=404,
                detail="No demo corpus found in data/. Restore it with: git checkout -- data/")
        _set_base_loaded(True)
        num_chunks = _reingest_all(force=True)
        return {
            "message": f"Demo corpus loaded ({len(_files_in(BASE_DIR))} documents)",
            "num_chunks": num_chunks,
        }
    except HTTPException:
        raise
    except Exception as e:
        _set_base_loaded(False)
        raise HTTPException(status_code=500, detail=f"Could not load the demo corpus: {e}")


@app.get("/documents")
async def list_documents():
    """List all source documents currently indexed in the vector store."""
    try:
        from qdrant_retrieval import DEFAULT_QDRANT_DIR, _load_manifest
        from pathlib import Path as _Path

        manifest = _load_manifest(_Path(DEFAULT_QDRANT_DIR))
        files = manifest.get("files", {})
        temporary = _temp_names()
        uploaded = _upload_names()
        documents = [
            {
                "filename": fname,
                "chunks": meta.get("chunks", 0) if isinstance(meta, dict) else 0,
                "ingested_at": meta.get("mtime", None) if isinstance(meta, dict) else None,
                "temporary": fname in temporary,
                "source": ("temporary" if fname in temporary
                           else "upload" if fname in uploaded else "demo"),
            }
            for fname, meta in files.items()
        ]
        return {
            "documents": documents,
            "total": len(documents),
            "temporary_count": sum(1 for d in documents if d["temporary"]),
            "demo_loaded": _base_loaded(),
        }
    except Exception as e:
        return {"documents": [], "total": 0, "error": str(e)}

# Serve the frontend
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
