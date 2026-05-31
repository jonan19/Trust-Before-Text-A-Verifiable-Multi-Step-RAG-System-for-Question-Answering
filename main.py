"""
main.py — Entry point for the Trust Before Text RAG prototype (V4 + ChromaDB).

Usage:
    python main.py                        # interactive REPL (default)
    python main.py "Your question here"   # single query from CLI
    python main.py --demo                 # run all built-in demo queries
    python main.py --ingest               # force re-ingest all documents
    python main.py --status               # show collection info and exit

LLM backend priority (set keys in .env):
    GROQ_API_KEY   → llama-3.3-70b-versatile  (primary)
    OPENAI_API_KEY → gpt-4o-mini              (fallback)
    GEMINI_API_KEY → gemini-1.5-flash         (fallback)
    (none)         → Mock LLM (always works)

V4 changes:
    - Model consistency check at startup: if the embedding model stored in the
      manifest differs from the current EMBEDDING_MODEL, the collection is
      automatically re-ingested with the correct model. Prevents silent
      wrong-embedding bugs when switching models.
    - --status mode: shows collection stats without running queries.
    - Incremental ingestion is default; --ingest forces full rebuild.

Pipeline:
    User Query
    → Orchestrator (preprocess → classify → decompose → retrieve → validate → decide)
    → ChromaDB Retrieval (sentence-transformers embeddings)
    → Validation Pipeline (7-stage deterministic)
    → Synthesis (evidence-grounded LLM answer)
    → Final Answer + Citations
"""

from __future__ import annotations

import sys
from pathlib import Path

# Load .env before any module reads os.getenv()
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except ImportError:
    pass   # dotenv optional — env vars can still be set via shell

from orchestrator import run
from utils import print_separator

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_DIR:   Path = Path("data")
CHROMA_DIR: Path = Path("chroma_db")

# ---------------------------------------------------------------------------
# Demo queries — exercise all pipeline branches
# ---------------------------------------------------------------------------
DEMO_QUERIES: list[dict] = [
    {
        "query":    "What is the leave policy?",
        "expected": "proceed — retrieve leave policy chunks from ChromaDB",
    },
    {
        "query":    "When are salary reviews conducted?",
        "expected": "proceed — salary review section retrieved",
    },
    {
        "query":    "Compare leave policy and remote work policy",
        "expected": "proceed or abstain — complex query, decomposed into sub-queries",
    },
    {
        "query":    "What is the company stock price?",
        "expected": "abstain — insufficient evidence (not in documents)",
    },
    {
        "query":    "What are the rules for expense reimbursement?",
        "expected": "proceed — expense reimbursement section retrieved",
    },
    {
        "query":    "What's the grievance procedure?",
        "expected": "proceed — contraction expanded before retrieval",
    },
]


# ===========================================================================
# Startup: model consistency check + auto-ingestion
# ===========================================================================

def _check_model_consistency() -> bool:
    """
    Verify that the ChromaDB collection was built with the current EMBEDDING_MODEL.

    Reads the manifest.json stored alongside the collection. If the model name
    differs from the one currently configured in ingestion.py, the index is
    stale — old embeddings are incompatible with new query embeddings.

    Returns True if a re-ingest is required, False if everything is consistent.
    """
    from ingestion import EMBEDDING_MODEL, get_manifest_model

    stored_model = get_manifest_model(CHROMA_DIR)

    if stored_model is None:
        # No manifest yet — treat as consistent (collection may be brand new)
        return False

    if stored_model != EMBEDDING_MODEL:
        print("\n  ⚠  Embedding model mismatch detected!")
        print(f"     Index built with : {stored_model}")
        print(f"     Current model    : {EMBEDDING_MODEL}")
        print("     Triggering automatic full re-ingest...\n")
        return True

    return False


def _ensure_ingested(force: bool = False) -> None:
    """
    Check if ChromaDB is populated and consistent. If not (or if force=True),
    run ingestion.

    This is called once at startup so the user never has to manually trigger
    ingestion — the system is self-initializing.
    """
    from ingestion import collection_is_empty, ingest_documents, COLLECTION_NAME
    import chromadb

    # Model consistency check (V4)
    needs_rebuild = _check_model_consistency()
    if needs_rebuild:
        force = True

    if force or collection_is_empty(CHROMA_DIR):
        print_separator("Document Ingestion")
        if not DATA_DIR.exists() or not any(
            f.suffix.lower() in {".txt", ".pdf"}
            for f in DATA_DIR.iterdir()
            if f.is_file()
        ):
            print(
                f"\n  [WARNING] No documents found in '{DATA_DIR}/'.  \n"
                f"  Add .txt or .pdf files to '{DATA_DIR}/' and restart.\n"
            )
            sys.exit(1)

        n = ingest_documents(
            data_dir   = DATA_DIR,
            chroma_dir = CHROMA_DIR,
            force      = force,
        )
        print(f"  [Ingestion] {n} chunks ready in ChromaDB.\n")
    else:
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        col    = client.get_collection(COLLECTION_NAME)
        print(f"  [ChromaDB] Collection ready — {col.count()} chunks loaded.")

    from llm_interface import active_backend
    print(f"  [LLM]      Active backend  : {active_backend()}")


# ===========================================================================
# Output helpers
# ===========================================================================

def _print_result(result: dict) -> None:
    """
    Pretty-print the full pipeline result:
    retrieved chunks → validation status → final answer → citations.
    """
    v = result["validation"]

    print_separator("PIPELINE SUMMARY")
    print(f"  Query     : {result['query']}")
    if result.get("preprocessed") and result["preprocessed"] != result["query"]:
        print(f"  Normalised: {result['preprocessed']}")
    print(f"  Decision  : {result['decision'].upper()}")
    print(f"  Relevant  : {v['relevant_count']} chunks passed validation")
    print(f"  Conflict  : {v['conflict_flag']}")
    print(f"  Sufficient: {v['sufficiency_flag']}")
    print(f"  Confidence: {v['confidence_score']:.4f}")
    if v['abstention_reason']:
        print(f"  Abstain   : {v['abstention_reason']}")

    sr = result.get("synthesis_result")
    if sr:
        print_separator("ANSWER")
        print(f"  Status: {sr['status'].upper()}")
        print()
        # Word-wrap the answer at 72 chars for readability
        answer = sr.get("answer", "")
        for line in _wrap(answer, width=72):
            print(f"  {line}")

        if sr.get("reason"):
            print(f"\n  Reason: {sr['reason']}")

        citations = sr.get("citations", [])
        if citations:
            print_separator("CITATIONS")
            for c in citations:
                score_str = f"  (score={c['score']:.4f})" if "score" in c else ""
                print(f"  [{c['source']}] {c['section']}{score_str}")

    print_separator()


def _wrap(text: str, width: int = 72) -> list[str]:
    """Simple word-wrapper."""
    words  = text.split()
    lines  = []
    current: list[str] = []
    length = 0

    for word in words:
        if length + len(word) + (1 if current else 0) > width:
            lines.append(" ".join(current))
            current = [word]
            length  = len(word)
        else:
            current.append(word)
            length += len(word) + (1 if len(current) > 1 else 0)

    if current:
        lines.append(" ".join(current))
    return lines


# ===========================================================================
# Modes
# ===========================================================================

def _run_status() -> None:
    """Show collection statistics and exit."""
    from ingestion import COLLECTION_NAME, EMBEDDING_MODEL, get_manifest_model
    import chromadb

    print_separator("Trust Before Text — Collection Status", width=70)

    manifest_model = get_manifest_model(CHROMA_DIR)
    print(f"  Configured model : {EMBEDDING_MODEL}")
    print(f"  Manifest model   : {manifest_model or '(none)'}")
    if manifest_model and manifest_model != EMBEDDING_MODEL:
        print("  ⚠  MISMATCH — run with --ingest to rebuild.")

    try:
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        col    = client.get_collection(COLLECTION_NAME)
        print(f"  Collection       : {COLLECTION_NAME}")
        print(f"  Chunks           : {col.count()}")
        # Peek at sources
        peek = col.get(limit=200, include=["metadatas"])
        sources = sorted({m.get("source", "?") for m in (peek.get("metadatas") or [])})
        print(f"  Documents        : {', '.join(sources) or '(none)'}")
    except Exception as exc:
        print(f"  Collection not found: {exc}")

    from llm_interface import active_backend
    print(f"  LLM backend      : {active_backend()}")
    print_separator(width=70)


def _run_demo() -> None:
    """Run all demo queries and print a summary table."""
    print_separator("Trust Before Text — Demo Mode", width=70)
    print(f"  Running {len(DEMO_QUERIES)} demo queries ...\n")

    for idx, entry in enumerate(DEMO_QUERIES, start=1):
        query    = entry["query"]
        expected = entry["expected"]

        print(f"\n{'=' * 70}")
        print(f"  Demo {idx}/{len(DEMO_QUERIES)}")
        print(f"  Expected : {expected}")
        print(f"{'=' * 70}\n")

        result = run(query, verbose=True)
        _print_result(result)

        v = result["validation"]
        print(
            f"\n  [Summary] "
            f"relevant={v['relevant_count']}  "
            f"conflict={v['conflict_flag']}  "
            f"sufficient={v['sufficiency_flag']}  "
            f"reason={v['abstention_reason'] or 'none'}  "
            f"confidence={v['confidence_score']:.4f}"
        )
        print()


def _run_single(query: str) -> None:
    """Run a single query and print the result."""
    print_separator("Trust Before Text — Single Query", width=70)
    result = run(query, verbose=True)
    _print_result(result)


def _run_repl() -> None:
    """Interactive REPL — accepts queries until the user types 'quit' or 'exit'."""
    print_separator("Trust Before Text — Interactive Mode", width=70)
    print("  Type your question and press Enter.")
    print("  Commands: 'quit'/'exit' to stop, 'demo' to run demos, 'status' for info.\n")

    while True:
        try:
            query = input("  Query> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Goodbye.")
            break

        if not query:
            continue
        if query.lower() in {"quit", "exit", "q"}:
            print("  Goodbye.")
            break
        if query.lower() == "demo":
            _run_demo()
            continue
        if query.lower() == "status":
            _run_status()
            continue

        result = run(query, verbose=True)
        _print_result(result)
        print()


# ===========================================================================
# Entry point
# ===========================================================================

def main() -> None:
    args = sys.argv[1:]

    # ── Parse flags ──────────────────────────────────────────────────────
    force_ingest = "--ingest" in args
    demo_mode    = "--demo"   in args
    status_mode  = "--status" in args
    args_clean   = [a for a in args if not a.startswith("--")]

    # ── Status mode (no ingestion needed) ────────────────────────────────
    if status_mode:
        _run_status()
        return

    # ── Bootstrap: ensure ChromaDB is populated and consistent ───────────
    _ensure_ingested(force=force_ingest)

    # ── Route to mode ────────────────────────────────────────────────────
    if demo_mode:
        _run_demo()
    elif args_clean:
        _run_single(" ".join(args_clean))
    else:
        _run_repl()


if __name__ == "__main__":
    main()
