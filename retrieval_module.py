"""
Retrieval Module for Trust Before Text RAG System
"""

import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import pickle
import json
from pathlib import Path
from vector_store import BaseVectorStore, LocalVectorStore

@dataclass
class DocumentChunk:
    chunk_id: str
    text: str
    source_document: str
    section: Optional[str] = None
    page_number: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    embedding: Optional[np.ndarray] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'chunk_id': self.chunk_id,
            'text': self.text,
            'source_document': self.source_document,
            'section': self.section,
            'page_number': self.page_number,
            'metadata': self.metadata
        }

@dataclass
class RetrievalResult:
    query: str
    chunks: List[DocumentChunk]
    similarity_scores: List[float]
    retrieval_metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'query': self.query,
            'chunks': [chunk.to_dict() for chunk in self.chunks],
            'similarity_scores': self.similarity_scores,
            'retrieval_metadata': self.retrieval_metadata
        }

class EmbeddingModel:
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        self.model_name = model_name
        self._model = None
        
    def load(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
                print(f"Loaded embedding model: {self.model_name}")
            except ImportError:
                raise ImportError("sentence-transformers not installed.")
    
    def embed_text(self, text: str) -> np.ndarray:
        self.load()
        # Ensure normalize_embeddings=True for standard cosine similarity
        embedding = self._model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
        return embedding
    
    def embed_batch(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        self.load()
        embeddings = self._model.encode(
            texts, 
            convert_to_numpy=True,
            batch_size=batch_size,
            show_progress_bar=True,
            normalize_embeddings=True
        )
        return embeddings


class RetrievalModule:
    def __init__(
        self,
        embedding_model: Optional[EmbeddingModel] = None,
        vector_store: Optional[BaseVectorStore] = None
    ):
        self.embedding_model = embedding_model or EmbeddingModel()
        # Default to local Numpy/FAISS store if none provided
        self.vector_store = vector_store or LocalVectorStore(dimension=384, use_faiss=True)
    
    def index_documents(self, chunks: List[DocumentChunk], batch_size: int = 32):
        print(f"Indexing {len(chunks)} document chunks...")
        texts = [chunk.text for chunk in chunks]
        embeddings = self.embedding_model.embed_batch(texts, batch_size=batch_size)
        self.vector_store.add_embeddings(embeddings, chunks)
        print(f"Successfully indexed {len(chunks)} chunks")
    
    def retrieve(
        self,
        query: str,
        k: int = 10,
        min_similarity: float = 0.60,
        filters: Optional[Dict[str, Any]] = None
    ) -> RetrievalResult:
        if self.vector_store.get_count() == 0:
            raise ValueError("No documents indexed. Call index_documents() first.")
        
        embed_query = query
        if "bge" in self.embedding_model.model_name.lower():
            embed_query = "Represent this sentence for searching relevant passages: " + query
            
        query_embedding = self.embedding_model.embed_text(embed_query)
        
        retrieved_chunks, final_scores = self.vector_store.search(
            query_embedding=query_embedding, 
            k=k, 
            filters=filters
        )
        
        # Apply min_similarity filtering
        valid_results = [(c, s) for c, s in zip(retrieved_chunks, final_scores) if s >= min_similarity]
        if valid_results:
            retrieved_chunks, final_scores = zip(*valid_results)
            retrieved_chunks = list(retrieved_chunks)
            final_scores = list(final_scores)
        else:
            retrieved_chunks = []
            final_scores = []
            
        retrieval_metadata = {
            'num_results_returned': len(retrieved_chunks),
            'min_similarity_threshold': min_similarity,
            'filters_applied': filters,
            'max_similarity_score': max(final_scores) if final_scores else 0.0,
            'min_similarity_score': min(final_scores) if final_scores else 0.0
        }
        
        return RetrievalResult(
            query=query,
            chunks=retrieved_chunks,
            similarity_scores=final_scores,
            retrieval_metadata=retrieval_metadata
        )
    
    def retrieve_multi_query(
        self,
        queries: List[str],
        k_per_query: int = 5,
        deduplicate: bool = True
    ) -> List[RetrievalResult]:
        results = []
        seen_chunk_ids = set()
        
        for query in queries:
            result = self.retrieve(query, k=k_per_query)
            if deduplicate:
                unique_chunks = []
                unique_scores = []
                for chunk, score in zip(result.chunks, result.similarity_scores):
                    if chunk.chunk_id not in seen_chunk_ids:
                        unique_chunks.append(chunk)
                        unique_scores.append(score)
                        seen_chunk_ids.add(chunk.chunk_id)
                result.chunks = unique_chunks
                result.similarity_scores = unique_scores
            results.append(result)
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        stats = {
            'total_chunks': self.vector_store.get_count(),
            'unique_documents': self.vector_store.get_documents_count(),
            'store_type': self.vector_store.__class__.__name__
        }
        return stats
