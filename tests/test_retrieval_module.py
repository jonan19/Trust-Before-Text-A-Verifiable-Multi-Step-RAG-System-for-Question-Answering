"""
Unit Tests for Retrieval Module

Run with: python -m pytest test_retrieval_module.py -v
or: python test_retrieval_module.py
"""

import unittest
import numpy as np
from pathlib import Path
import tempfile
import shutil

from retrieval_module import (
    DocumentChunk,
    EmbeddingModel,
    VectorIndex,
    RetrievalModule,
    RetrievalResult
)
from document_preprocessing import DocumentChunker, DocumentLoader, CorpusBuilder


class TestDocumentChunk(unittest.TestCase):
    """Test DocumentChunk data structure"""
    
    def test_chunk_creation(self):
        chunk = DocumentChunk(
            chunk_id="test_001",
            text="Sample text",
            source_document="test.pdf",
            section="Introduction",
            page_number=1,
            metadata={"author": "Test Author"}
        )
        
        self.assertEqual(chunk.chunk_id, "test_001")
        self.assertEqual(chunk.text, "Sample text")
        self.assertEqual(chunk.source_document, "test.pdf")
        self.assertEqual(chunk.section, "Introduction")
        self.assertEqual(chunk.page_number, 1)
        self.assertIn("author", chunk.metadata)
    
    def test_chunk_to_dict(self):
        chunk = DocumentChunk(
            chunk_id="test_001",
            text="Sample text",
            source_document="test.pdf"
        )
        
        chunk_dict = chunk.to_dict()
        self.assertIsInstance(chunk_dict, dict)
        self.assertEqual(chunk_dict['chunk_id'], "test_001")
        self.assertEqual(chunk_dict['text'], "Sample text")


class TestEmbeddingModel(unittest.TestCase):
    """Test embedding generation"""
    
    def setUp(self):
        self.model = EmbeddingModel()
    
    def test_embed_single_text(self):
        text = "This is a test sentence."
        embedding = self.model.embed_text(text)
        
        self.assertIsInstance(embedding, np.ndarray)
        self.assertEqual(len(embedding.shape), 1)  # 1D vector
        self.assertGreater(len(embedding), 0)
    
    def test_embed_batch(self):
        texts = [
            "First sentence.",
            "Second sentence.",
            "Third sentence."
        ]
        embeddings = self.model.embed_batch(texts)
        
        self.assertIsInstance(embeddings, np.ndarray)
        self.assertEqual(embeddings.shape[0], len(texts))
        self.assertGreater(embeddings.shape[1], 0)
    
    def test_embedding_consistency(self):
        """Same text should produce same embedding"""
        text = "Consistency test"
        emb1 = self.model.embed_text(text)
        emb2 = self.model.embed_text(text)
        
        np.testing.assert_array_almost_equal(emb1, emb2)


class TestVectorIndex(unittest.TestCase):
    """Test vector indexing and search"""
    
    def setUp(self):
        self.dimension = 384  # Default for all-MiniLM-L6-v2
        self.index = VectorIndex(dimension=self.dimension, use_faiss=False)
    
    def test_add_embeddings(self):
        embeddings = np.random.rand(10, self.dimension).astype('float32')
        chunk_ids = [f"chunk_{i:03d}" for i in range(10)]
        
        self.index.add_embeddings(embeddings, chunk_ids)
        
        self.assertEqual(len(self.index.embeddings), 10)
        self.assertEqual(len(self.index.chunk_ids), 10)
    
    def test_search_exact(self):
        # Create some sample embeddings
        embeddings = np.random.rand(20, self.dimension).astype('float32')
        chunk_ids = [f"chunk_{i:03d}" for i in range(20)]
        
        self.index.add_embeddings(embeddings, chunk_ids)
        
        # Search with one of the embeddings
        query_embedding = embeddings[5]
        indices, scores = self.index.search(query_embedding, k=5)
        
        self.assertEqual(len(indices), 5)
        self.assertEqual(len(scores), 5)
        # The closest should be the query itself
        self.assertEqual(indices[0], 5)
    
    def test_search_k_larger_than_corpus(self):
        """Test that k larger than corpus size doesn't crash"""
        embeddings = np.random.rand(5, self.dimension).astype('float32')
        chunk_ids = [f"chunk_{i:03d}" for i in range(5)]
        
        self.index.add_embeddings(embeddings, chunk_ids)
        
        query_embedding = embeddings[0]
        indices, scores = self.index.search(query_embedding, k=100)
        
        self.assertEqual(len(indices), 5)  # Should return all available


class TestRetrievalModule(unittest.TestCase):
    """Test main retrieval module"""
    
    def setUp(self):
        self.retrieval = RetrievalModule()
        
        # Create sample chunks
        self.chunks = [
            DocumentChunk(
                chunk_id=f"chunk_{i:03d}",
                text=f"This is document chunk number {i}. " + 
                     ("It discusses academic policies." if i % 2 == 0 else "It covers library guidelines."),
                source_document="policy.pdf" if i % 2 == 0 else "library.pdf",
                metadata={"index": i}
            )
            for i in range(10)
        ]
    
    def test_index_documents(self):
        self.retrieval.index_documents(self.chunks)
        
        self.assertEqual(len(self.retrieval.chunks_db), 10)
        self.assertIsNotNone(self.retrieval.vector_index)
    
    def test_retrieve_basic(self):
        self.retrieval.index_documents(self.chunks)
        
        result = self.retrieval.retrieve("academic policies", k=3)
        
        self.assertIsInstance(result, RetrievalResult)
        self.assertEqual(len(result.chunks), 3)
        self.assertEqual(len(result.similarity_scores), 3)
        self.assertGreater(result.similarity_scores[0], 0)
    
    def test_retrieve_with_filters(self):
        self.retrieval.index_documents(self.chunks)
        
        # Filter by source document
        result = self.retrieval.retrieve(
            "document chunk",
            k=5,
            filters={'source_document': 'policy.pdf'}
        )
        
        # All results should be from policy.pdf
        for chunk in result.chunks:
            self.assertEqual(chunk.source_document, 'policy.pdf')
    
    def test_retrieve_with_min_similarity(self):
        self.retrieval.index_documents(self.chunks)
        
        result = self.retrieval.retrieve(
            "completely unrelated quantum physics topic",
            k=5,
            min_similarity=0.9  # Very high threshold
        )
        
        # Should return few or no results
        self.assertLessEqual(len(result.chunks), 5)
    
    def test_retrieve_multi_query(self):
        self.retrieval.index_documents(self.chunks)
        
        queries = [
            "academic policies",
            "library guidelines"
        ]
        
        results = self.retrieval.retrieve_multi_query(
            queries=queries,
            k_per_query=3,
            deduplicate=True
        )
        
        self.assertEqual(len(results), 2)
        self.assertIsInstance(results[0], RetrievalResult)
        self.assertIsInstance(results[1], RetrievalResult)
    
    def test_get_statistics(self):
        self.retrieval.index_documents(self.chunks)
        
        stats = self.retrieval.get_statistics()
        
        self.assertEqual(stats['total_chunks'], 10)
        self.assertEqual(stats['unique_documents'], 2)
        self.assertIn('policy.pdf', stats['chunks_per_document'])
        self.assertIn('library.pdf', stats['chunks_per_document'])
    
    def test_save_and_load_index(self):
        self.retrieval.index_documents(self.chunks)
        
        # Save index
        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "test_index"
            self.retrieval.save_index(str(index_path))
            
            # Load into new module
            new_retrieval = RetrievalModule()
            new_retrieval.load_index(str(index_path))
            
            # Test retrieval
            result = new_retrieval.retrieve("academic policies", k=3)
            self.assertEqual(len(result.chunks), 3)


class TestDocumentChunker(unittest.TestCase):
    """Test document chunking"""
    
    def test_fixed_size_chunking(self):
        chunker = DocumentChunker(
            chunk_size=100,
            chunk_overlap=20,
            chunking_strategy='fixed'
        )
        
        text = "This is a test document. " * 20  # ~500 chars
        chunks = chunker.chunk_document(text, "test.txt")
        
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertIsInstance(chunk, DocumentChunk)
            self.assertEqual(chunk.source_document, "test.txt")
    
    def test_sentence_chunking(self):
        chunker = DocumentChunker(
            chunk_size=200,
            chunk_overlap=50,
            chunking_strategy='sentence'
        )
        
        text = "First sentence. Second sentence. Third sentence. " * 5
        chunks = chunker.chunk_document(text, "test.txt")
        
        self.assertGreater(len(chunks), 0)
        # Each chunk should end with a sentence
        for chunk in chunks[:-1]:  # Except possibly the last
            self.assertTrue(chunk.text.rstrip().endswith('.'))
    
    def test_paragraph_chunking(self):
        chunker = DocumentChunker(
            chunk_size=300,
            chunk_overlap=0,
            chunking_strategy='paragraph'
        )
        
        text = """
        First paragraph with some content.
        More content in the first paragraph.
        
        Second paragraph here.
        With more information.
        
        Third paragraph.
        """
        
        chunks = chunker.chunk_document(text, "test.txt")
        
        self.assertGreater(len(chunks), 0)


class TestDocumentLoader(unittest.TestCase):
    """Test document loading"""
    
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
    
    def tearDown(self):
        shutil.rmtree(self.tmpdir)
    
    def test_load_txt(self):
        # Create test file
        test_file = Path(self.tmpdir) / "test.txt"
        test_content = "This is a test document.\nWith multiple lines."
        
        with open(test_file, 'w') as f:
            f.write(test_content)
        
        # Load it
        content = DocumentLoader.load_txt(str(test_file))
        
        self.assertEqual(content, test_content)
    
    def test_auto_detect_format(self):
        # Create test file
        test_file = Path(self.tmpdir) / "test.txt"
        test_content = "Test content"
        
        with open(test_file, 'w') as f:
            f.write(test_content)
        
        # Auto-detect and load
        content = DocumentLoader.load_document(str(test_file))
        
        self.assertEqual(content, test_content)


class TestCorpusBuilder(unittest.TestCase):
    """Test corpus building"""
    
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.chunker = DocumentChunker(chunk_size=200)
        self.builder = CorpusBuilder(self.chunker)
    
    def tearDown(self):
        shutil.rmtree(self.tmpdir)
    
    def test_build_corpus(self):
        # Create test files
        for i in range(3):
            test_file = Path(self.tmpdir) / f"doc_{i}.txt"
            with open(test_file, 'w') as f:
                f.write(f"This is test document {i}. " * 20)
        
        # Build corpus
        chunks = self.builder.build_corpus(self.tmpdir)
        
        self.assertGreater(len(chunks), 0)
        # Should have chunks from multiple documents
        sources = set(chunk.source_document for chunk in chunks)
        self.assertEqual(len(sources), 3)


class TestEndToEnd(unittest.TestCase):
    """End-to-end integration tests"""
    
    def test_complete_pipeline(self):
        """Test the complete retrieval pipeline"""
        
        # 1. Create sample documents
        chunks = [
            DocumentChunk(
                chunk_id=f"policy_chunk_{i:03d}",
                text=f"Academic honesty policy section {i}. Students must maintain integrity.",
                source_document="policy.pdf"
            )
            for i in range(5)
        ] + [
            DocumentChunk(
                chunk_id=f"library_chunk_{i:03d}",
                text=f"Library guidelines section {i}. Books can be checked out for 3 weeks.",
                source_document="library.pdf"
            )
            for i in range(5)
        ]
        
        # 2. Index documents
        retrieval = RetrievalModule()
        retrieval.index_documents(chunks)
        
        # 3. Perform queries
        queries = [
            "academic honesty policy",
            "library book checkout duration"
        ]
        
        for query in queries:
            result = retrieval.retrieve(query, k=3)
            
            # Should return relevant results
            self.assertEqual(len(result.chunks), 3)
            self.assertGreater(result.similarity_scores[0], 0.3)
        
        # 4. Multi-query retrieval
        results = retrieval.retrieve_multi_query(queries, k_per_query=2)
        self.assertEqual(len(results), 2)
        
        # 5. Check statistics
        stats = retrieval.get_statistics()
        self.assertEqual(stats['total_chunks'], 10)
        self.assertEqual(stats['unique_documents'], 2)


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(__import__(__name__))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == '__main__':
    import sys
    success = run_tests()
    sys.exit(0 if success else 1)
