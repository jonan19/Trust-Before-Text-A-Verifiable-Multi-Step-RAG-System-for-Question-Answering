"""
Interactive QA Script for Retrieval Module
This script allows user input for questions which are answered in run time
using the retrieval module.
"""
import os
import sys
from retrieval_module import RetrievalModule, DocumentChunk
from document_preprocessing import DocumentChunker, DocumentLoader

def main():
    print("="*60)
    print("Trust Before Text - Interactive Retrieval Module")
    print("="*60)

    # Initialize retriever
    # Check if we should use ChromaDB
    use_chroma = input("Use persistent ChromaDB? (y/n): ").lower() == 'y'
    persist_dir = "./my_chroma_db" if use_chroma else None
    
    retriever = RetrievalModule(use_chroma=use_chroma, chroma_persist_dir=persist_dir)
    
    # Check if index exists or if we need to add data
    if use_chroma:
        stats = retriever.get_statistics()
        if stats['total_chunks'] == 0:
            print("\nVector store is empty.")
            add_data_prompt(retriever)
    else:
        add_data_prompt(retriever)

    print("\nStarting Interactive Session. Type 'exit' or 'quit' to stop.")
    print("Type 'add' to index a new text file.")
    
    while True:
        try:
            query = input("\n[Question]: ").strip()
            
            if not query:
                continue
            if query.lower() in ['exit', 'quit']:
                break
            if query.lower() == 'add':
                add_data_prompt(retriever)
                continue
            
            # Retrieve results
            results = retriever.retrieve(query, k=3)
            
            if not results.chunks:
                print("\n[Result]: No relevant evidence found.")
                continue
                
            print(f"\n[Found {len(results.chunks)} pieces of evidence]:")
            for i, chunk in enumerate(results.chunks):
                print(f"\n--- Evidence {i+1} (Source: {chunk.source_document}, Score: {results.similarity_scores[i]:.4f}) ---")
                print(chunk.text)
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n[Error]: {e}")

def add_data_prompt(retriever):
    chunker = DocumentChunker(chunk_size=500, chunk_overlap=50)
    
    path = input("\nEnter path to a .txt file to index: ").strip()
    if os.path.exists(path) and path.lower().endswith('.txt'):
        try:
            text = DocumentLoader.load_txt(path)
            chunks = chunker.chunk_document(text, source_document=os.path.basename(path))
            retriever.index_documents(chunks)
            print(f"Successfully indexed {len(chunks)} chunks.")
        except Exception as e:
            print(f"Error indexing file: {e}")
    else:
        print("Invalid file path or format. Only .txt files are supported.")

if __name__ == "__main__":
    main()
