from retrieval_module import RetrievalModule, DocumentChunk

def run_slide_demo():
    print("🚀 Initializing RAG Pipeline...\n")
    
    # 1. Prepare Data
    chunks = [
        DocumentChunk(
            chunk_id="doc1", 
            text="The university academic policy strictly prohibits plagiarism.", 
            source_document="policy.txt"
        )
    ]
    
    # 2. Build Index
    print(" Indexing knowledge base...")
    retrieval_module = RetrievalModule()
    retrieval_module.index_documents(chunks)
    
    # 3. Retrieve
    query = "What is the policy on plagiarism?"
    print(f"\n❓ Query: '{query}'")
    
    result = retrieval_module.retrieve(query, k=1)
    
    # 4. Show Output
    print("\n Top Result:")
    for chunk, score in zip(result.chunks, result.similarity_scores):
        print(f"Confidence: {score:.2f} | Source: {chunk.source_document}")
        print(f"Evidence: '{chunk.text}'")

if __name__ == "__main__":
    run_slide_demo()
