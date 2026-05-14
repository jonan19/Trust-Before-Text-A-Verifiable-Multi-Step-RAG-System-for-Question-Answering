from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import shutil
from pathlib import Path
from contextlib import asynccontextmanager

from retrieval_module import RetrievalModule
from vector_store import LocalVectorStore
from document_preprocessing import DocumentChunker, DocumentLoader, CorpusBuilder

UPLOAD_DIR = Path("./uploaded_docs")
UPLOAD_DIR.mkdir(exist_ok=True)

class AppState:
    retriever: RetrievalModule = None
    chunker: DocumentChunker = None

state = AppState()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize components on startup
    state.chunker = DocumentChunker(chunk_size=500, chunk_overlap=50)
    vector_store = LocalVectorStore(dimension=384, use_faiss=True)
    state.retriever = RetrievalModule(vector_store=vector_store)
    print("Retrieval Module initialized")
    yield
    # Cleanup on shutdown
    print("Shutting down")

app = FastAPI(title="Trust Before Text - Retrieval API", lifespan=lifespan)

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
    min_similarity: float = 0.60

class TextIncisionRequest(BaseModel):
    text: str
    filename: str
    metadata: Optional[Dict[str, Any]] = None

def get_retriever():
    if not state.retriever:
        raise HTTPException(status_code=500, detail="Retriever not initialized")
    return state.retriever

def get_chunker():
    if not state.chunker:
        raise HTTPException(status_code=500, detail="Chunker not initialized")
    return state.chunker

@app.get("/stats")
async def get_stats(retriever: RetrievalModule = Depends(get_retriever)):
    """Get statistics about the indexed documents"""
    try:
        stats = retriever.get_statistics()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query")
async def query_retriever(request: QueryRequest, retriever: RetrievalModule = Depends(get_retriever)):
    """Query the retrieval module for relevant evidence"""
    try:
        results = retriever.retrieve(
            query=request.query,
            k=request.k,
            min_similarity=request.min_similarity
        )
        return results.to_dict()
    except ValueError as e:
        # Likely no documents indexed yet
        return {"query": request.query, "chunks": [], "similarity_scores": [], "error": str(e)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...), 
    retriever: RetrievalModule = Depends(get_retriever),
    chunker: DocumentChunker = Depends(get_chunker)
):
    """Upload a file and index its contents"""
    if not file.filename.endswith('.txt'):
        raise HTTPException(status_code=400, detail="Only .txt files are supported for now.")
    
    file_path = UPLOAD_DIR / file.filename
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        # Load and chunk the document
        text = DocumentLoader.load_txt(str(file_path))
        chunks = chunker.chunk_document(text, source_document=file.filename, metadata={"filepath": str(file_path)})
        
        # Index chunks
        retriever.index_documents(chunks)
        
        return {
            "message": f"Successfully indexed {file.filename}",
            "num_chunks": len(chunks)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/add_text")
async def add_text(
    request: TextIncisionRequest,
    retriever: RetrievalModule = Depends(get_retriever),
    chunker: DocumentChunker = Depends(get_chunker)
):
    """Index raw text content"""
    try:
        chunks = chunker.chunk_document(
            request.text, 
            source_document=request.filename, 
            metadata=request.metadata or {}
        )
        retriever.index_documents(chunks)
        return {
            "message": f"Successfully indexed text as {request.filename}",
            "num_chunks": len(chunks)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/reset")
async def reset_index():
    """Clear the vector store"""
    try:
        # Re-initialize the LocalVectorStore and RetrievalModule
        vector_store = LocalVectorStore(dimension=384, use_faiss=True)
        state.retriever = RetrievalModule(vector_store=vector_store)
        
        return {"message": "Vector store reset successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
