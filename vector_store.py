"""
Vector Store Implementations for Retrieval Module
"""
import chromadb
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
import pickle
from abc import ABC, abstractmethod

# Import dynamically in methods to avoid circular dependency
# from retrieval_module import DocumentChunk

class BaseVectorStore(ABC):
    """Abstract base class for vector stores"""
    
    @abstractmethod
    def add_embeddings(self, embeddings: np.ndarray, chunks: List[Any]):
        """Add embeddings and their corresponding chunks"""
        pass
        
    @abstractmethod
    def search(self, query_embedding: np.ndarray, k: int = 10, filters: Optional[Dict[str, Any]] = None) -> Tuple[List[Any], List[float]]:
        """Search for top-k chunks. Returns (chunks, scores)"""
        pass
        
    @abstractmethod
    def get_count(self) -> int:
        """Get the total number of indexed chunks"""
        pass
        
    @abstractmethod
    def get_documents_count(self) -> int:
        """Get the number of unique documents indexed"""
        pass


class LocalVectorStore(BaseVectorStore):
    """
    Vector index implementation using NumPy (Exact) or FAISS (Approximate).
    Stores data in memory.
    """
    def __init__(self, dimension: int, use_faiss: bool = False):
        self.dimension = dimension
        self.use_faiss = use_faiss
        self.embeddings = []
        self.chunks_list = [] # List to maintain order for indexing
        self._index = None
        
        if use_faiss:
            self._init_faiss_index()
            
    def _init_faiss_index(self):
        try:
            import faiss
            self._index = faiss.IndexFlatL2(self.dimension)
            print(f"Initialized FAISS index with dimension {self.dimension}")
        except ImportError:
            print("FAISS not installed. Falling back to exact search.")
            self.use_faiss = False
            
    def add_embeddings(self, embeddings: np.ndarray, chunks: List[Any]):
        if len(chunks) != len(embeddings):
            raise ValueError("Number of chunks must match number of embeddings")
            
        for i, chunk in enumerate(chunks):
            # We don't store the embedding on the chunk to save memory
            self.chunks_list.append(chunk)
            self.embeddings.append(embeddings[i])
            
        if self.use_faiss and self._index is not None:
            self._index.add(embeddings.astype('float32'))
            
    def search(self, query_embedding: np.ndarray, k: int = 10, filters: Optional[Dict[str, Any]] = None) -> Tuple[List[Any], List[float]]:
        if not self.embeddings:
            return [], []
            
        # We retrieve more candidates if we need to filter
        search_k = k * 3 if filters else k
        search_k = min(search_k, len(self.embeddings))
        
        if self.use_faiss and self._index is not None:
            indices, scores = self._search_faiss(query_embedding, search_k)
        else:
            indices, scores = self._search_exact(query_embedding, search_k)
            
        retrieved_chunks = []
        final_scores = []
        
        for idx, score in zip(indices, scores):
            chunk = self.chunks_list[idx]
            
            if filters and not self._matches_filters(chunk, filters):
                continue
                
            retrieved_chunks.append(chunk)
            final_scores.append(score)
            
            if len(retrieved_chunks) >= k:
                break
                
        return retrieved_chunks, final_scores
        
    def _search_faiss(self, query_embedding: np.ndarray, k: int) -> Tuple[List[int], List[float]]:
        query_embedding = query_embedding.reshape(1, -1).astype('float32')
        distances, indices = self._index.search(query_embedding, k)
        similarities = 1 / (1 + distances[0])
        return indices[0].tolist(), similarities.tolist()
        
    def _search_exact(self, query_embedding: np.ndarray, k: int) -> Tuple[List[int], List[float]]:
        embeddings_matrix = np.array(self.embeddings)
        query_norm = query_embedding / np.linalg.norm(query_embedding)
        embeddings_norm = embeddings_matrix / np.linalg.norm(embeddings_matrix, axis=1, keepdims=True)
        similarities = np.dot(embeddings_norm, query_norm)
        top_k_indices = np.argsort(similarities)[::-1][:k]
        top_k_scores = similarities[top_k_indices]
        return top_k_indices.tolist(), top_k_scores.tolist()
        
    def _matches_filters(self, chunk: Any, filters: Dict[str, Any]) -> bool:
        for key, value in filters.items():
            if key == 'source_document' and chunk.source_document != value:
                return False
            elif key == 'section' and getattr(chunk, 'section', None) != value:
                return False
            elif key == 'page_number' and getattr(chunk, 'page_number', None) != value:
                return False
            elif getattr(chunk, 'metadata', None) and key in chunk.metadata:
                if chunk.metadata[key] != value:
                    return False
        return True
        
    def get_count(self) -> int:
        return len(self.chunks_list)
        
    def get_documents_count(self) -> int:
        return len(set(chunk.source_document for chunk in self.chunks_list))


class ChromaVectorStore(BaseVectorStore):
    """
    Vector index implementation using ChromaDB for persistent storage
    """
    def __init__(self, collection_name: str = "rag_documents", persist_directory: str = "./chroma_db"):
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.client = chromadb.PersistentClient(path=self.persist_directory)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        print(f"Initialized ChromaDB index at '{self.persist_directory}' in collection '{self.collection_name}'")

    def add_embeddings(self, embeddings: np.ndarray, chunks: List[Any]):
        if not chunks:
            return
            
        ids = [chunk.chunk_id for chunk in chunks]
        texts = [chunk.text for chunk in chunks]
        embeddings_list = embeddings.tolist()
        
        metadatas = []
        for chunk in chunks:
            meta = {"source_document": chunk.source_document}
            if getattr(chunk, "section", None):
                meta["section"] = chunk.section
            if getattr(chunk, "page_number", None) is not None:
                meta["page_number"] = chunk.page_number
            if getattr(chunk, "metadata", None):
                for k, v in chunk.metadata.items():
                    if isinstance(v, (str, int, float, bool)):
                        meta[f"meta_{k}"] = v
            metadatas.append(meta)
            
        self.collection.upsert(
            embeddings=embeddings_list,
            documents=texts,
            metadatas=metadatas,
            ids=ids
        )
        print(f"Added {len(chunks)} chunks to ChromaDB collection.")

    def search(self, query_embedding: np.ndarray, k: int = 10, filters: Optional[Dict[str, Any]] = None) -> Tuple[List[Any], List[float]]:
        from retrieval_module import DocumentChunk
        
        where_clause = None
        if filters:
            if len(filters) == 1:
                k_filter, v_filter = list(filters.items())[0]
                where_clause = {k_filter: v_filter}
            else:
                where_clause = {"$and": [{k_filter: v_filter} for k_filter, v_filter in filters.items()]}
                
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=k,
            where=where_clause,
            include=["documents", "metadatas", "distances"]
        )
        
        if not results['ids'] or not results['ids'][0]:
            return [], []
            
        retrieved_chunks = []
        similarity_scores = []
        
        for i in range(len(results['ids'][0])):
            chunk_id = results['ids'][0][i]
            text = results['documents'][0][i]
            metadata = results['metadatas'][0][i] or {}
            
            distance = results['distances'][0][i]
            similarity_score = 1.0 - distance
            
            doc = DocumentChunk(
                chunk_id=chunk_id,
                text=text,
                source_document=metadata.get("source_document", ""),
                section=metadata.get("section"),
                page_number=metadata.get("page_number")
            )
            
            extra_meta = {key.replace("meta_", ""): val for key, val in metadata.items() if key.startswith("meta_")}
            if extra_meta:
                doc.metadata = extra_meta
                
            retrieved_chunks.append(doc)
            similarity_scores.append(similarity_score)
            
        return retrieved_chunks, similarity_scores
        
    def get_count(self) -> int:
        return self.collection.count()
        
    def get_documents_count(self) -> int:
        # Chroma doesn't have a distinct query easily accessible without fetching all metadata
        # Return a placeholder or count unique sources by fetching
        try:
            results = self.collection.get(include=["metadatas"])
            sources = set([m.get("source_document") for m in results["metadatas"] if m])
            return len(sources)
        except Exception:
            return 0
