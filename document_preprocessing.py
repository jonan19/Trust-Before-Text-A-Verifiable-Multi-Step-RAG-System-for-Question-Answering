"""
Document Preprocessing Utilities

This module handles document loading, chunking, and preparation
for the retrieval module.
"""

import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from abc import ABC, abstractmethod
from retrieval_module import DocumentChunk
import hashlib


class BaseChunker(ABC):
    """Abstract base class for chunking strategies"""
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
    @abstractmethod
    def chunk_document(
        self,
        text: str,
        source_document: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[DocumentChunk]:
        pass
        
    def _generate_chunk_id(self, source_document: str, chunk_index: int) -> str:
        """Generate unique chunk ID"""
        doc_name = Path(source_document).stem
        return f"{doc_name}_chunk_{chunk_index:04d}"


class FixedChunker(BaseChunker):
    """Fixed-size chunking with overlap"""
    def chunk_document(self, text: str, source_document: str, metadata: Optional[Dict[str, Any]] = None) -> List[DocumentChunk]:
        chunks = []
        start = 0
        chunk_index = 0
        
        while start < len(text):
            end = start + self.chunk_size
            chunk_text = text[start:end]
            
            # Try to break at sentence boundary if possible
            if end < len(text):
                last_period = chunk_text.rfind('.')
                last_newline = chunk_text.rfind('\n')
                break_point = max(last_period, last_newline)
                
                if break_point > len(chunk_text) * 0.5:  # Don't break too early
                    chunk_text = chunk_text[:break_point + 1]
                    end = start + len(chunk_text)
            
            chunk_id = self._generate_chunk_id(source_document, chunk_index)
            chunk = DocumentChunk(
                chunk_id=chunk_id,
                text=chunk_text.strip(),
                source_document=source_document,
                metadata=metadata
            )
            chunks.append(chunk)
            
            # Move to next chunk with overlap
            start = end - self.chunk_overlap
            chunk_index += 1
        
        return chunks


class SentenceChunker(BaseChunker):
    """Chunk by sentences, grouping to approximate chunk_size"""
    def chunk_document(self, text: str, source_document: str, metadata: Optional[Dict[str, Any]] = None) -> List[DocumentChunk]:
        # Simple sentence splitting (can be improved with NLTK or spaCy)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        chunks = []
        current_chunk = []
        current_size = 0
        chunk_index = 0
        
        for sentence in sentences:
            sentence_size = len(sentence)
            
            if current_size + sentence_size > self.chunk_size and current_chunk:
                chunk_text = ' '.join(current_chunk)
                chunk_id = self._generate_chunk_id(source_document, chunk_index)
                
                chunk = DocumentChunk(
                    chunk_id=chunk_id,
                    text=chunk_text.strip(),
                    source_document=source_document,
                    metadata=metadata
                )
                chunks.append(chunk)
                
                # Keep last few sentences for overlap
                overlap_sentences = []
                overlap_size = 0
                for sent in reversed(current_chunk):
                    if overlap_size + len(sent) <= self.chunk_overlap:
                        overlap_sentences.insert(0, sent)
                        overlap_size += len(sent)
                    else:
                        break
                
                current_chunk = overlap_sentences + [sentence]
                current_size = overlap_size + sentence_size
                chunk_index += 1
            else:
                current_chunk.append(sentence)
                current_size += sentence_size
        
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunk_id = self._generate_chunk_id(source_document, chunk_index)
            chunk = DocumentChunk(
                chunk_id=chunk_id,
                text=chunk_text.strip(),
                source_document=source_document,
                metadata=metadata
            )
            chunks.append(chunk)
        
        return chunks


class ParagraphChunker(BaseChunker):
    """Chunk by paragraphs, combining small paragraphs"""
    def chunk_document(self, text: str, source_document: str, metadata: Optional[Dict[str, Any]] = None) -> List[DocumentChunk]:
        paragraphs = re.split(r'\n\s*\n', text)
        
        chunks = []
        current_chunk = []
        current_size = 0
        chunk_index = 0
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            paragraph_size = len(paragraph)
            
            if current_size + paragraph_size > self.chunk_size and current_chunk:
                chunk_text = '\n\n'.join(current_chunk)
                chunk_id = self._generate_chunk_id(source_document, chunk_index)
                
                chunk = DocumentChunk(
                    chunk_id=chunk_id,
                    text=chunk_text.strip(),
                    source_document=source_document,
                    metadata=metadata
                )
                chunks.append(chunk)
                
                current_chunk = [paragraph]
                current_size = paragraph_size
                chunk_index += 1
            else:
                current_chunk.append(paragraph)
                current_size += paragraph_size
        
        if current_chunk:
            chunk_text = '\n\n'.join(current_chunk)
            chunk_id = self._generate_chunk_id(source_document, chunk_index)
            chunk = DocumentChunk(
                chunk_id=chunk_id,
                text=chunk_text.strip(),
                source_document=source_document,
                metadata=metadata
            )
            chunks.append(chunk)
        
        return chunks


class DocumentChunker:
    """
    Router class that splits documents into chunks by delegating 
    to a specific chunking strategy.
    """
    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        chunking_strategy: str = "fixed"
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.chunking_strategy = chunking_strategy
        
        if self.chunking_strategy == "fixed":
            self._strategy = FixedChunker(chunk_size, chunk_overlap)
        elif self.chunking_strategy == "sentence":
            self._strategy = SentenceChunker(chunk_size, chunk_overlap)
        elif self.chunking_strategy == "paragraph":
            self._strategy = ParagraphChunker(chunk_size, chunk_overlap)
        else:
            raise ValueError(f"Unknown chunking strategy: {self.chunking_strategy}")
            
    def chunk_document(
        self,
        text: str,
        source_document: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[DocumentChunk]:
        """Delegate chunking to the configured strategy"""
        return self._strategy.chunk_document(text, source_document, metadata)


class DocumentLoader:
    """
    Load documents from various formats (TXT, PDF, DOCX, etc.)
    """
    @staticmethod
    def load_txt(filepath: str) -> str:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    
    @staticmethod
    def load_pdf(filepath: str) -> str:
        try:
            import PyPDF2
            text = []
            with open(filepath, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                for page in pdf_reader.pages:
                    text.append(page.extract_text())
            return '\n\n'.join(text)
        except ImportError:
            raise ImportError("PyPDF2 not installed. Install with: pip install PyPDF2")
    
    @staticmethod
    def load_docx(filepath: str) -> str:
        try:
            from docx import Document
            doc = Document(filepath)
            text = []
            for paragraph in doc.paragraphs:
                text.append(paragraph.text)
            return '\n\n'.join(text)
        except ImportError:
            raise ImportError("python-docx not installed. Install with: pip install python-docx")
    
    @staticmethod
    def load_document(filepath: str) -> str:
        filepath = Path(filepath)
        extension = filepath.suffix.lower()
        
        if extension == '.txt':
            return DocumentLoader.load_txt(str(filepath))
        elif extension == '.pdf':
            return DocumentLoader.load_pdf(str(filepath))
        elif extension == '.docx':
            return DocumentLoader.load_docx(str(filepath))
        else:
            raise ValueError(f"Unsupported file format: {extension}")


class CorpusBuilder:
    """
    Build a corpus of document chunks from a directory of documents
    """
    def __init__(self, chunker: DocumentChunker):
        self.chunker = chunker
        self.loader = DocumentLoader()
    
    def build_corpus(self, document_dir: str, file_patterns: List[str] = ['*.txt', '*.pdf', '*.docx']) -> List[DocumentChunk]:
        document_dir = Path(document_dir)
        all_chunks = []
        
        for pattern in file_patterns:
            for filepath in document_dir.glob(pattern):
                print(f"Processing: {filepath.name}")
                try:
                    text = self.loader.load_document(str(filepath))
                    chunks = self.chunker.chunk_document(text=text, source_document=filepath.name, metadata={'filepath': str(filepath)})
                    all_chunks.extend(chunks)
                    print(f"  Created {len(chunks)} chunks")
                except Exception as e:
                    print(f"  Error processing {filepath.name}: {e}")
        
        print(f"\nTotal chunks created: {len(all_chunks)}")
        return all_chunks
    
    def build_from_file_list(self, filepaths: List[str]) -> List[DocumentChunk]:
        all_chunks = []
        for filepath in filepaths:
            filepath = Path(filepath)
            print(f"Processing: {filepath.name}")
            try:
                text = self.loader.load_document(str(filepath))
                chunks = self.chunker.chunk_document(text=text, source_document=filepath.name, metadata={'filepath': str(filepath)})
                all_chunks.extend(chunks)
                print(f"  Created {len(chunks)} chunks")
            except Exception as e:
                print(f"  Error processing {filepath.name}: {e}")
        
        print(f"\nTotal chunks created: {len(all_chunks)}")
        return all_chunks
