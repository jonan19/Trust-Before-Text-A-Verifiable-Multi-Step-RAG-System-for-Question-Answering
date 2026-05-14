"""
Example Usage: Building and Using the Retrieval Module

This script demonstrates how to:
1. Load and chunk documents
2. Build a retrieval index
3. Perform queries
4. Save and load the index
"""

from retrieval_module import RetrievalModule, EmbeddingModel, DocumentChunk
from document_preprocessing import DocumentChunker, CorpusBuilder
from pathlib import Path


def example_1_basic_usage():
    """Example 1: Basic retrieval pipeline"""
    print("="*60)
    print("EXAMPLE 1: Basic Retrieval Pipeline")
    print("="*60)
    
    # Step 1: Create sample documents
    sample_docs = [
        {
            'text': """
            The university's academic honesty policy requires all students to 
            maintain integrity in their coursework. Plagiarism, defined as 
            presenting someone else's work as your own, is strictly prohibited. 
            This includes copying from other students, published works, or 
            online sources without proper citation.
            """,
            'source': 'academic_policy.txt'
        },
        {
            'text': """
            Students found violating the academic honesty policy may face 
            sanctions ranging from grade penalties to expulsion. First-time 
            offenses typically result in a failing grade for the assignment. 
            Repeat violations can lead to suspension or permanent dismissal 
            from the university.
            """,
            'source': 'academic_policy.txt'
        },
        {
            'text': """
            The library is open Monday through Friday from 8 AM to 10 PM, and 
            weekends from 10 AM to 6 PM. Students can check out up to 10 books 
            at a time for a period of three weeks. Late returns incur a fine 
            of $0.25 per day per item.
            """,
            'source': 'library_guidelines.txt'
        }
    ]
    
    # Step 2: Create document chunks
    chunks = []
    for i, doc in enumerate(sample_docs):
        chunk = DocumentChunk(
            chunk_id=f"{doc['source']}_chunk_{i:03d}",
            text=doc['text'].strip(),
            source_document=doc['source'],
            metadata={'chunk_index': i}
        )
        chunks.append(chunk)
    
    print(f"\nCreated {len(chunks)} document chunks")
    
    # Step 3: Initialize retrieval module and index documents
    retrieval_module = RetrievalModule(use_chroma=True, chroma_persist_dir="./my_chroma_db")
    retrieval_module.index_documents(chunks)
    
    # Step 4: Perform retrieval queries
    queries = [
        "What happens if I plagiarize?",
        "What are the library hours?",
        "Can I get expelled for cheating?"
    ]
    
    print("\n" + "-"*60)
    print("RETRIEVAL RESULTS")
    print("-"*60)
    
    for query in queries:
        print(f"\nQuery: '{query}'")
        print("-"*40)
        
        result = retrieval_module.retrieve(query, k=2)
        
        for i, (chunk, score) in enumerate(zip(result.chunks, result.similarity_scores)):
            print(f"\nResult {i+1} (score: {score:.4f})")
            print(f"Source: {chunk.source_document}")
            print(f"Text: {chunk.text}")
    
    # Step 5: Display statistics
    print("\n" + "="*60)
    print("CORPUS STATISTICS")
    print("="*60)
    stats = retrieval_module.get_statistics()
    for key, value in stats.items():
        print(f"{key}: {value}")


def example_2_document_processing():
    """Example 2: Processing real documents from files"""
    print("\n" + "="*60)
    print("EXAMPLE 2: Document Processing Pipeline")
    print("="*60)
    
    # Create a sample document directory structure
    docs_dir = Path("/tmp/sample_documents")
    docs_dir.mkdir(exist_ok=True)
    
    # Create sample document files
    sample_files = {
        'policy_handbook.txt': """
        EMPLOYEE CONDUCT POLICY
        
        All employees are expected to conduct themselves professionally in the workplace.
        This includes treating colleagues with respect, maintaining confidentiality of 
        sensitive information, and adhering to company policies and procedures.
        
        DRESS CODE
        
        Business casual attire is required for all office employees. This means collared 
        shirts, slacks or skirts, and closed-toe shoes. Jeans are permitted on Fridays.
        Inappropriate attire includes shorts, tank tops, and flip-flops.
        
        ATTENDANCE
        
        Employees are expected to arrive on time and notify their supervisor if they 
        will be late or absent. Excessive tardiness or absenteeism may result in 
        disciplinary action up to and including termination.
        """,
        
        'benefits_guide.txt': """
        HEALTH INSURANCE
        
        The company offers comprehensive health insurance coverage to all full-time 
        employees. Coverage begins on the first day of the month following 30 days 
        of employment. Employees contribute 20% of the premium cost through payroll 
        deduction.
        
        RETIREMENT SAVINGS
        
        Employees can participate in the company 401(k) plan after 90 days of employment.
        The company matches employee contributions up to 5% of salary. Employees are 
        immediately vested in their own contributions and become vested in employer 
        contributions after three years.
        
        PAID TIME OFF
        
        Full-time employees accrue 15 days of paid time off per year, which can be 
        used for vacation, sick leave, or personal days. PTO accrues monthly and 
        unused days can be carried over up to a maximum of 30 days.
        """
    }
    
    # Write sample files
    for filename, content in sample_files.items():
        filepath = docs_dir / filename
        with open(filepath, 'w') as f:
            f.write(content)
    
    print(f"Created sample documents in: {docs_dir}")
    
    # Step 1: Initialize chunker
    chunker = DocumentChunker(
        chunk_size=300,
        chunk_overlap=50,
        chunking_strategy='paragraph'
    )
    
    # Step 2: Build corpus
    corpus_builder = CorpusBuilder(chunker)
    chunks = corpus_builder.build_corpus(str(docs_dir))
    
    # Step 3: Index documents
    retrieval_module = RetrievalModule(use_faiss=False)
    retrieval_module.index_documents(chunks)
    
    # Step 4: Test queries
    queries = [
        "What is the dress code policy?",
        "When do health benefits start?",
        "How much PTO do employees get?",
        "What happens if I'm late to work?"
    ]
    
    print("\n" + "-"*60)
    print("RETRIEVAL RESULTS")
    print("-"*60)
    
    for query in queries:
        print(f"\nQuery: '{query}'")
        print("-"*40)
        
        result = retrieval_module.retrieve(query, k=2, min_similarity=0.2)
        
        if not result.chunks:
            print("No relevant documents found.")
        else:
            for i, (chunk, score) in enumerate(zip(result.chunks, result.similarity_scores)):
                print(f"\nResult {i+1} (score: {score:.4f})")
                print(f"Source: {chunk.source_document}")
                print(f"Text: {chunk.text}")


def example_3_multi_query_retrieval():
    """Example 3: Multi-query retrieval for complex questions"""
    print("\n" + "="*60)
    print("EXAMPLE 3: Multi-Query Retrieval")
    print("="*60)
    
    # Create sample chunks
    chunks = [
        DocumentChunk(
            chunk_id="safety_001",
            text="Emergency exits are located at the front and rear of each floor. In case of fire, use the stairs, never the elevator.",
            source_document="safety_manual.txt"
        ),
        DocumentChunk(
            chunk_id="safety_002",
            text="Fire extinguishers are located every 50 feet in hallways. Pull the pin, aim at the base of the fire, squeeze the handle, and sweep side to side.",
            source_document="safety_manual.txt"
        ),
        DocumentChunk(
            chunk_id="safety_003",
            text="The building evacuation assembly point is in the parking lot on the north side of the building. Wait there for further instructions.",
            source_document="safety_manual.txt"
        ),
        DocumentChunk(
            chunk_id="safety_004",
            text="First aid kits are available in the break room and reception area. For serious injuries, call 911 immediately.",
            source_document="safety_manual.txt"
        )
    ]
    
    # Index chunks
    retrieval_module = RetrievalModule()
    retrieval_module.index_documents(chunks)
    
    # Complex question requiring multiple sub-queries
    main_query = "What should I do in case of a fire emergency?"
    
    # Decompose into sub-queries (this would normally be done by the Orchestrator)
    sub_queries = [
        "Where are emergency exits located?",
        "How to use fire extinguisher?",
        "Where to go during building evacuation?"
    ]
    
    print(f"\nMain Query: '{main_query}'")
    print(f"Decomposed into {len(sub_queries)} sub-queries")
    
    # Retrieve for each sub-query
    results = retrieval_module.retrieve_multi_query(
        queries=sub_queries,
        k_per_query=2,
        deduplicate=True
    )
    
    print("\n" + "-"*60)
    print("SUB-QUERY RESULTS")
    print("-"*60)
    
    for i, (sub_query, result) in enumerate(zip(sub_queries, results)):
        print(f"\nSub-query {i+1}: '{sub_query}'")
        print("-"*40)
        print(f"Found {len(result.chunks)} chunks")
        
        for j, (chunk, score) in enumerate(zip(result.chunks, result.similarity_scores)):
            print(f"  {j+1}. [{chunk.chunk_id}] (score: {score:.4f})")
            print(f"     {chunk.text}")


def example_5_retrieval_accuracy():
    """Example 5: Measure retrieval accuracy (Hit Rate & MRR)"""
    print("\n" + "="*60)
    print("EXAMPLE 5: Retrieval Accuracy Evaluation")
    print("="*60)

    # Ground-truth labeled queries: (query, expected_source_document)
    labeled_queries = [
        ("What happens if my assignment is late?",        "student_handbook.txt"),
        ("What is plagiarism?",                           "student_handbook.txt"),
        ("Who do I notify if I am sick and miss class?",  "student_handbook.txt"),
        ("What are the consequences of academic misconduct?", "student_handbook.txt"),
        ("How many books can I check out from the library?", "campus_guide.txt"),
        ("What are the library hours on weekends?",       "campus_guide.txt"),
        ("Where can I get help with a password reset?",   "campus_guide.txt"),
        ("How do I schedule an appointment with a career advisor?", "campus_guide.txt"),
    ]

    # Build corpus from the two documents
    from document_preprocessing import DocumentChunker
    handbook_text = """
STUDENT HANDBOOK

Academic Integrity Policy

The university is committed to maintaining the highest standards of academic integrity. Students must complete all assignments honestly and acknowledge the work of others through proper citation.

Plagiarism occurs when a student presents someone else's work, ideas, or writing as their own without proper attribution. This includes copying text from books, websites, or other students' assignments.

Consequences of Academic Misconduct

Students who violate the academic integrity policy may face disciplinary action. Penalties can include a warning, a reduced grade on the assignment, failure of the course, or suspension from the university.

Repeated violations may result in expulsion from the institution.

Attendance Policy

Students are expected to attend all scheduled classes and arrive on time. Excessive absences may negatively affect a student's final grade.

If a student must miss a class due to illness or personal emergency, they should notify the instructor as soon as possible.

Late Submission Policy

Assignments submitted after the deadline may receive a penalty of 10 percent per day late unless prior approval has been granted by the instructor.

Submissions more than five days late may not be accepted.

Code of Conduct

Students are expected to behave respectfully toward faculty, staff, and fellow students. Disruptive behavior, harassment, or threats will not be tolerated and may lead to disciplinary action.
"""
    campus_text = """
CAMPUS SERVICES GUIDE

University Library

The university library provides access to thousands of books, research journals, and digital resources. Students can borrow up to ten books at a time.

Library Hours

The library is open Monday through Friday from 8:00 AM to 10:00 PM. On weekends, the library operates from 10:00 AM to 6:00 PM.

Students must present their university ID card to check out books or reserve study rooms.

Information Technology Services

The IT department provides technical support for students and staff. Services include password resets, Wi-Fi troubleshooting, and access to university software.

Students can contact IT support through the helpdesk portal or by visiting the IT service desk located in the main administration building.

Health and Wellness Center

The university health center offers basic medical care, counseling services, and mental health support for students.

Career Services

The career services office helps students prepare for internships and job opportunities. Services include resume workshops, mock interviews, and career counseling sessions.

Students can book appointments with career advisors through the university career portal.
"""

    chunker = DocumentChunker(chunk_size=300, chunk_overlap=50, chunking_strategy='paragraph')
    chunks  = chunker.chunk_document(handbook_text, "student_handbook.txt") + \
              chunker.chunk_document(campus_text,   "campus_guide.txt")

    retrieval_module = RetrievalModule()
    retrieval_module.index_documents(chunks)

    print(f"\nIndexed {len(chunks)} chunks across 2 documents")
    print(f"Evaluating {len(labeled_queries)} labeled queries...\n")
    print("-"*60)

    top1_hits = 0
    top2_hits = 0
    reciprocal_ranks = []

    for query, expected_source in labeled_queries:
        result = retrieval_module.retrieve(query, k=2)
        sources = [c.source_document for c in result.chunks]

        # Top-1 hit
        hit1 = len(sources) > 0 and sources[0] == expected_source
        # Top-2 hit
        hit2 = expected_source in sources

        if hit1:
            top1_hits += 1
            reciprocal_ranks.append(1.0)
        elif hit2:
            top2_hits += 1
            reciprocal_ranks.append(0.5)
        else:
            reciprocal_ranks.append(0.0)

        status = "TOP-1 ✓" if hit1 else ("TOP-2 ✓" if hit2 else "MISS  ✗")
        score  = result.similarity_scores[0] if result.similarity_scores else 0.0
        print(f"{status} | score={score:.2f} | Q: '{query[:45]}...'" if len(query) > 45
              else f"{status} | score={score:.2f} | Q: '{query}'")

    total         = len(labeled_queries)
    top1_rate     = top1_hits / total * 100
    top2_rate     = (top1_hits + top2_hits) / total * 100
    mrr           = sum(reciprocal_ranks) / total

    print("\n" + "="*60)
    print("ACCURACY REPORT")
    print("="*60)
    print(f"Total queries evaluated : {total}")
    print(f"Top-1 Hit Rate          : {top1_hits}/{total}  ({top1_rate:.1f}%)")
    print(f"Top-2 Hit Rate          : {top1_hits + top2_hits}/{total}  ({top2_rate:.1f}%)")
    print(f"Mean Reciprocal Rank    : {mrr:.3f}")
    print("="*60)


def example_4_save_and_load():
    """Example 4: Saving and loading the index"""
    print("\n" + "="*60)
    print("EXAMPLE 4: Save and Load Index")
    print("="*60)
    
    # Create and index some chunks
    chunks = [
        DocumentChunk(
            chunk_id=f"doc_chunk_{i:03d}",
            text=f"This is sample document chunk number {i} with some content.",
            source_document="sample.txt"
        )
        for i in range(5)
    ]
    
    # Build index
    print("\nBuilding index...")
    retrieval_module = RetrievalModule()
    retrieval_module.index_documents(chunks)
    
    # Save index
    index_path = "/tmp/retrieval_index"
    print(f"Saving index to: {index_path}")
    retrieval_module.save_index(index_path)
    
    # Create new module and load index
    print("\nLoading index into new module...")
    new_retrieval_module = RetrievalModule()
    new_retrieval_module.load_index(index_path)
    
    # Test retrieval with loaded index
    query = "sample document content"
    result = new_retrieval_module.retrieve(query, k=3)
    
    print(f"\nTest query: '{query}'")
    print(f"Retrieved {len(result.chunks)} chunks")
    
    for i, (chunk, score) in enumerate(zip(result.chunks, result.similarity_scores)):
        print(f"  {i+1}. {chunk.chunk_id} (score: {score:.4f})")


def main():
    """Run all examples"""
    print("\n" + "="*80)
    print(" RETRIEVAL MODULE - EXAMPLE USAGE ")
    print("="*80)
    
    try:
        example_1_basic_usage()
        example_2_document_processing()
        example_3_multi_query_retrieval()
        example_4_save_and_load()
        example_5_retrieval_accuracy()
        
        print("\n" + "="*80)
        print(" ALL EXAMPLES COMPLETED SUCCESSFULLY ")
        print("="*80)
        
    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
