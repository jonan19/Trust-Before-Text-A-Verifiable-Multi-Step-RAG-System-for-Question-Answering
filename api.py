from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
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

@app.on_event("startup")
async def startup_event():
    """Ensure the Qdrant database is ingested and consistent at startup."""
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
        
    if force or collection_is_empty(qdrant_dir):
        if DATA_DIR.exists() and any(f.suffix.lower() in {".txt", ".pdf", ".docx"} for f in DATA_DIR.iterdir() if f.is_file()):
            print("  [Startup] Qdrant collection is empty or missing. Auto-ingesting documents from data/...")
            try:
                # Remove locks if any stale lock exists
                lock_file = qdrant_dir / ".lock"
                if lock_file.exists():
                    try:
                        lock_file.unlink()
                    except OSError:
                        pass
                ingest_documents(data_dir=DATA_DIR, qdrant_dir=qdrant_dir, force=force)
                print("  [Startup] Auto-ingestion complete.")
            except Exception as e:
                print(f"  [Startup] Auto-ingestion failed: {e}")
        else:
            print("  [Startup] Qdrant database is empty, but no documents were found in data/ to ingest.")
    else:
        print("  [Startup] Qdrant collection is ready.")


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
async def upload_file(file: UploadFile = File(...)):
    """Upload a file to data/ and trigger dynamic active retriever ingestion"""
    ext = Path(file.filename).suffix.lower()
    if ext not in {'.txt', '.pdf', '.docx'}:
        raise HTTPException(status_code=400, detail="Only .txt, .pdf, and .docx files are supported.")
    
    file_path = DATA_DIR / file.filename
    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")
        
    try:
        num_chunks = 0
        
        # Release file locks before recreating collection
        from qdrant_retrieval import _close_client, DEFAULT_QDRANT_DIR, ingest_documents as qdrant_ingest
        _close_client()
        lock_file = Path(DEFAULT_QDRANT_DIR) / ".lock"
        if lock_file.exists():
            try:
                lock_file.unlink()
            except OSError:
                pass
        num_chunks = qdrant_ingest(data_dir=DATA_DIR, force=True)
            
        return {
            "message": f"Successfully uploaded and indexed {file.filename}",
            "num_chunks": num_chunks
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")

@app.delete("/reset")
async def reset_index():
    """Clear all user files and reset the active database"""
    try:
        # 1. Clear files in data/
        for item in DATA_DIR.iterdir():
            if item.is_file():
                # Avoid deleting readmes if present
                if item.name.lower() not in {"readme.md", "license", "licence"}:
                    try:
                        item.unlink()
                    except Exception:
                        pass
        
        # 2. Reset the active database
        from qdrant_retrieval import _close_client, DEFAULT_QDRANT_DIR, COLLECTION_NAME, _get_client
        _close_client()
        lock_file = Path(DEFAULT_QDRANT_DIR) / ".lock"
        if lock_file.exists():
            try:
                lock_file.unlink()
            except OSError:
                pass
        client = _get_client(DEFAULT_QDRANT_DIR)
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
                
        return {"message": "Vector store and document repository reset successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents")
async def list_documents():
    """List all source documents currently indexed in the vector store."""
    try:
        from qdrant_retrieval import DEFAULT_QDRANT_DIR, _load_manifest
        from pathlib import Path as _Path

        manifest = _load_manifest(_Path(DEFAULT_QDRANT_DIR))
        files = manifest.get("files", {})

        documents = [
            {
                "filename": fname,
                "chunks": meta.get("chunks", 0) if isinstance(meta, dict) else 0,
                "ingested_at": meta.get("mtime", None) if isinstance(meta, dict) else None,
            }
            for fname, meta in files.items()
        ]
        return {"documents": documents, "total": len(documents)}
    except Exception as e:
        return {"documents": [], "total": 0, "error": str(e)}

# Serve the frontend
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
