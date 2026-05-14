import sys
from pathlib import Path
from retrieval_module import RetrievalModule
from document_preprocessing import DocumentChunker

def test_student_handbook():
    print("="*60)
    print("TESTING RETRIEVAL MODULE WITH STUDENT HANDBOOK DATA")
    print("="*60)
    
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

The university aims to create a safe and inclusive learning environment for everyone.
"""

    campus_guide_text = """
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

Appointments can be scheduled online or by visiting the health center reception desk.

Career Services

The career services office helps students prepare for internships and job opportunities. Services include resume workshops, mock interviews, and career counseling sessions.

Students can book appointments with career advisors through the university career portal.
"""
    
    # Initialize chunker to split the handbook into paragraphs
    chunker = DocumentChunker(
        chunk_size=300,
        chunk_overlap=50,
        chunking_strategy='paragraph'
    )
    
    # Create chunks
    chunks1 = chunker.chunk_document(handbook_text, "student_handbook.txt")
    chunks2 = chunker.chunk_document(campus_guide_text, "campus_guide.txt")
    chunks = chunks1 + chunks2
    print(f"Created {len(chunks)} total document chunks.")
    
    # Initialize retrieval module and index documents
    # Using the standard in-memory vector index for simplicity
    retrieval_module = RetrievalModule()
    retrieval_module.index_documents(chunks)
    
    # Try out some sample queries against the indexed text
    queries = [
        "What happens if my assignment is late?",
        "What is plagiarism?",
        "Who do I notify if I am sick and miss class?",
        "What are the consequences of academic misconduct?",
        "How many books can I check out from the library?",
        "What are the library hours on weekends?",
        "Where can I get help with a password reset?",
        "How do I schedule an appointment with a career advisor?"
    ]
    
    print("\n" + "-"*60)
    print("RETRIEVAL RESULTS")
    print("-"*60)
    
    for query in queries:
        print(f"\nQuery: '{query}'")
        print("-"*40)
        
        # Retrieve the top 2 matching chunks
        result = retrieval_module.retrieve(query, k=2)
        
        if not result.chunks:
            print("No relevant documents found.")
        else:
            for i, (chunk, score) in enumerate(zip(result.chunks, result.similarity_scores)):
                print(f"\nResult {i+1} (Similiarity Score: {score:.4f})")
                print(f"Source: {chunk.source_document}")
                print(f"Text Match: {chunk.text.strip()}")

if __name__ == "__main__":
    test_student_handbook()





