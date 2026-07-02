from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
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

class QueryRequest(BaseModel):
    query: str
    k: int = 5

@app.get("/stats")
async def get_stats():
    """Get statistics about the indexed documents based on active retriever"""
    try:
        from qdrant_retrieval import _get_client, DEFAULT_QDRANT_DIR, COLLECTION_NAME, _load_manifest
        client = _get_client(DEFAULT_QDRANT_DIR)
        try:
            total_chunks = client.count(COLLECTION_NAME).count
        except Exception:
            total_chunks = 0
        
        manifest = _load_manifest(Path(DEFAULT_QDRANT_DIR))
        unique_docs = len(manifest.get("files", {}))
        return {
            "total_chunks": total_chunks,
            "unique_documents": unique_docs,
            "retriever": "qdrant"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query")
async def query_pipeline(request: QueryRequest):
    """Query the V4 Trust Before Text RAG pipeline"""
    try:
        # Run the full V4 orchestration pipeline
        res = orchestrator.run(request.query, verbose=False)
        
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
                "section": c.get("section", "unknown")
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
            "conflict_flag": validation_result.get("conflict_flag", False),
            "sufficiency_flag": validation_result.get("sufficiency_flag", True),
            "abstention_reason": validation_result.get("abstention_reason")
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

# Serve the frontend
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
