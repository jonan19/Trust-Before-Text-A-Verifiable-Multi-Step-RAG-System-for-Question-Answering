"""
RAG Retrieval Module - Condensed Slide Summary
Runs all 4 examples, prints only the key result per example.
"""

import os, sys, logging, warnings, tempfile

# Silence noisy library output
os.environ["TOKENIZERS_PARALLELISM"] = "false"
warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)

# Redirect stdout during library loading to suppress model load messages
import contextlib
from io import StringIO

@contextlib.contextmanager
def silent():
    """Suppress stdout/stderr temporarily."""
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = StringIO()
    try:
        yield
    finally:
        sys.stdout, sys.stderr = old_out, old_err

with silent():
    from retrieval_module import RetrievalModule, DocumentChunk
    from document_preprocessing import DocumentChunker

# ── Header ───────────────────────────────────────────────────
print("=" * 56)
print("   RETRIEVAL MODULE — PIPELINE DEMO")
print("=" * 56)

# ── Example 1: Basic Retrieval ───────────────────────────────
with silent():
    chunks1 = [
        DocumentChunk("pol_0",
            "Academic honesty policy prohibits plagiarism — presenting someone else's work as your own.",
            "academic_policy.txt"),
        DocumentChunk("pol_1",
            "Violations carry sanctions from grade penalties to expulsion.",
            "academic_policy.txt"),
        DocumentChunk("lib_0",
            "Library open Mon–Fri 8AM–10PM, weekends 10AM–6PM. Borrow up to 10 books.",
            "library_guidelines.txt"),
    ]
    rm1 = RetrievalModule()
    rm1.index_documents(chunks1)
    r1 = rm1.retrieve("What happens if I plagiarize?", k=1)

print(f"\n[Ex 1] Basic Retrieval")
print(f"       Query  → 'What happens if I plagiarize?'")
print(f"       Result → {r1.chunks[0].source_document}   score={r1.similarity_scores[0]:.2f}")

# ── Example 2: Document Processing Pipeline ──────────────────
with silent():
    policy_text   = "EMPLOYEE CONDUCT\nBusiness casual attire required. Jeans on Fridays.\nATTENDANCE\nEmployees must notify supervisor if late or absent."
    benefits_text = "HEALTH INSURANCE\nCoverage after 30 days. Employee pays 20% premium.\nPAID TIME OFF\nFull-time staff accrue 15 days PTO per year."
    chunker = DocumentChunker(chunk_size=300, chunk_overlap=50, chunking_strategy='paragraph')
    chunks2 = chunker.chunk_document(policy_text, "policy_handbook.txt") + \
              chunker.chunk_document(benefits_text, "benefits_guide.txt")
    rm2 = RetrievalModule()
    rm2.index_documents(chunks2)
    r2 = rm2.retrieve("What is the dress code?", k=1)

print(f"\n[Ex 2] Document Processing  ({len(chunks2)} chunks from 2 files)")
print(f"       Query  → 'What is the dress code?'")
print(f"       Result → {r2.chunks[0].source_document}   score={r2.similarity_scores[0]:.2f}")

# ── Example 3: Multi-Query Retrieval ─────────────────────────
with silent():
    safety_chunks = [
        DocumentChunk("s1", "Emergency exits at the front and rear of each floor. Use stairs, not elevator.", "safety_manual.txt"),
        DocumentChunk("s2", "Fire extinguishers every 50 ft. Pull pin, aim at base, squeeze, sweep.", "safety_manual.txt"),
        DocumentChunk("s3", "Evacuation assembly point: parking lot on the north side.", "safety_manual.txt"),
        DocumentChunk("s4", "First aid kits in break room and reception. Call 911 for serious injuries.", "safety_manual.txt"),
    ]
    rm3 = RetrievalModule()
    rm3.index_documents(safety_chunks)
    sub_queries = [
        "Where are emergency exits?",
        "How to use a fire extinguisher?",
        "Where to go during evacuation?"
    ]
    results3 = rm3.retrieve_multi_query(sub_queries, k_per_query=1, deduplicate=True)

unique_chunks = sum(len(r.chunks) for r in results3)
print(f"\n[Ex 3] Multi-Query Retrieval")
print(f"       Queries → {len(sub_queries)} sub-queries for 'What to do in a fire?'")
print(f"       Result  → {unique_chunks} unique chunks retrieved (deduplicated)")

# ── Example 4: Save & Load Index ─────────────────────────────
tmp_path = os.path.join(tempfile.gettempdir(), "slide_demo_index")
with silent():
    chunks4 = [
        DocumentChunk(f"doc_{i}", f"University policy content — chapter {i}.", "sample.txt")
        for i in range(5)
    ]
    rm4 = RetrievalModule()
    rm4.index_documents(chunks4)
    rm4.save_index(tmp_path)
    rm4_loaded = RetrievalModule()
    rm4_loaded.load_index(tmp_path)
    r4 = rm4_loaded.retrieve("university policy", k=3)

print(f"\n[Ex 4] Save & Load Index")
print(f"       Saved   → 5 chunks to disk")
print(f"       Loaded  → new module, retrieved {len(r4.chunks)} chunks   top-score={r4.similarity_scores[0]:.2f}")

# ── Footer ───────────────────────────────────────────────────
print(f"\n{'=' * 56}")
print(f"  All 4 examples completed successfully")
print(f"{'=' * 56}")
