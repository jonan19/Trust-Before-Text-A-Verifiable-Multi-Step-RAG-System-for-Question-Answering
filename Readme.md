# Trust Before Text — V4 Architecture

## Philosophy

> **"Trust Before Text"** — deterministic evidence validation before generation.

The system generates answers **only** from verified, retrieved evidence.
When evidence is insufficient or contradictory, it **abstains** rather than hallucinating.

---

## What's New in V4

| Area | Improvement |
|---|---|
| **LLM Backend** | Groq (`llama-3.3-70b-versatile`) as primary; OpenAI / Gemini as fallbacks |
| **Environment** | `.env` file support via `python-dotenv` |
| **Query Preprocessing** | Contraction expansion, punctuation normalization before retrieval |
| **Retrieval Scoring** | Linear calibration replaces magic constants; principled `[0.40, 1.0] → [0.65, 1.0]` mapping |
| **Retriever Options** | ChromaDB dense retrieval by default; optional Qdrant hybrid dense+sparse retrieval |
| **Relevance Filtering** | Stage 3 uses embedding-based scores from retrieval (skips redundant TF-cosine) |
| **Contradiction Detection** | Word-boundary regex matching; unit-context numeric comparison (`"20 days"` ≠ `"5 working days"`) |
| **Incremental Ingestion** | SHA-256 manifest — only changed/new files re-ingested |
| **Sentence Chunking** | NLTK sentence-aware chunking with character-level fallback |
| **Performance** | LRU cache on similarity functions; query embedding cache |
| **Model Safety** | Startup model mismatch detection + automatic re-ingest |
| **CLI** | `--status` mode; active backend displayed at startup |

---

## High-Level Pipeline

```
User Query
    ↓
preprocess_query()          ← contraction expansion, punctuation cleanup  [NEW V4]
    ↓
Orchestrator
    ├─ classify query (simple / complex)
    ├─ decompose complex queries into sub-queries
    └─ retrieve chunks for each sub-query  (ChromaDB or Qdrant hybrid)
         ↓
    Validation Pipeline (7 stages, fully deterministic — no LLM)
         ↓
    Decision Engine  →  proceed | retry | abstain
         ↓
    Synthesis Module  (LLM used ONLY here)
         ↓
    Final Answer  (with citations + retrieval scores)
```

---

## V4 Validation Pipeline

All validation is **deterministic and non-LLM**.

### Stage 1 — Chunk Normalization
- Unicode NFKC normalization (handles ligatures, exotic whitespace)
- Strip and collapse whitespace
- Remove empty chunks

### Stage 2 — Duplicate Removal
- TF cosine similarity between all chunk pairs (LRU-cached)
- If similarity ≥ `DUPLICATE_SIM_THRESHOLD` (0.90), keep only the higher-scoring chunk

### Stage 3 — Relevance Filtering *(Upgraded in V4)*
**V4:** If chunks carry a `relevance_score` set by the retrieval module (embedding-based cosine similarity), those scores are used directly — TF-cosine recomputation is skipped entirely.

**Fallback:** If no `relevance_score` is present, TF cosine similarity is computed between the query and each chunk.

Both paths:
- Find the best relevance score across all chunks
- Keep chunks with score ≥ `best_sim × RELEVANCE_RATIO_THRESHOLD` (0.30)
- Absolute floor: drop chunks below `MIN_RELEVANCE_SCORE` (0.05)

### Stage 4 — Evidence Consistency Analysis *(Upgraded in V4)*
Runs on the relevance-filtered chunk set. For each pair of chunks sharing the same section OR with cosine similarity ≥ 0.55:

**Keyword contradiction** *(V4: word-boundary matching)*
- Uses `re.search(r'\b...\b')` instead of substring `in` — prevents `"is"` from matching inside `"decisions"`, `"increases"`, etc.
- 21 antonym pairs: `prohibited/allowed`, `banned/permitted`, `mandatory/optional`, `cannot/can`, `never/always`, `deny/approve`, `rejected/approved`, `terminated/active`, and more.

**Numeric contradiction** *(V4: unit-context aware)*
- Numbers flagged as contradictory ONLY when both texts reference the **same unit context**
- `"20 days annual leave"` vs `"5 working days notice"` → **no conflict** (`"day"` ≠ `"working_day"`)
- `"20 days annual leave"` vs `"15 days annual leave"` → **conflict** (same context, different value)

### Stage 5 — Evidence Sufficiency Check
All three heuristics must pass:
- **H1**: At least `MIN_CHUNKS_FOR_SUFFICIENCY` (1) relevant chunk
- **H2**: Average retrieval score ≥ `MIN_AVG_SCORE_FOR_SUFFICIENCY` (0.65)
- **H3**: At least one chunk has `relevance_score > MIN_RELEVANCE_SCORE`

### Stage 6 — Evidence Structuring
Returns chunks as fully-typed structured dicts in descending score order:

```python
{
    "rank"           : 1,          # 1 = best scoring chunk
    "text"           : "...",
    "source"         : "policy.pdf",
    "section"        : "Leave Policy",
    "score"          : 0.8055,     # calibrated retrieval score [SCORE_FLOOR, 1.0]
    "relevance_score": 0.6665,     # raw embedding cosine similarity (Stage 3)
}
```

### Stage 7 — Abstention Decision

| Condition | Reason | Action |
|---|---|---|
| `conflict_flag == True` | `"conflict"` | retry → abstain |
| `sufficiency_flag == False` | `"insufficient"` | abstain |
| Both pass | `None` | proceed to synthesis |

---

## Decision Engine

```
abstention_reason == "conflict"     →  RETRY  (once, with wider top_k)
                                       if retry still conflicts → ABSTAIN
abstention_reason == "insufficient" →  ABSTAIN
abstention_reason == None           →  PROCEED
```

---

## Retrieval Module *(V4 — redesigned scoring)*

- Embedding model: `multi-qa-MiniLM-L6-cos-v1` (optimised for query-to-passage retrieval)
- Default vector store: ChromaDB (persistent, cosine similarity space)
- Optional vector store: Qdrant local mode with named dense and sparse vectors
- Qdrant hybrid mode uses sentence-transformer dense retrieval plus local BM25-style sparse retrieval, then combines rankings with reciprocal rank fusion (RRF)
- **Score calibration**: linear mapping `[MIN_COSINE_THRESHOLD=0.40, 1.0] → [SCORE_FLOOR=0.65, 1.0]`
  - Chunks below 0.40 raw cosine similarity are discarded (off-topic noise)
  - Every passing chunk receives a calibrated score ≥ 0.65 (validation sufficiency threshold)
- Each chunk carries both `score` (calibrated) and `relevance_score` (raw cosine) for transparency
- Query embeddings are cached to avoid redundant `encode()` calls on retries

---

## Ingestion Pipeline *(V4 — incremental)*

```bash
python ingestion.py           # incremental: only changed/new files
python ingestion.py --force   # full rebuild
```

**V4 features:**
- **SHA-256 manifest** (`chroma_db/manifest.json`): tracks file hashes and embedding model name
- Only changed/new files re-ingested; deleted files cleaned from ChromaDB
- **NLTK sentence-aware chunking**: sentences accumulated into chunks respecting sentence boundaries
- **PDF TOC extraction**: uses document outline/bookmarks for section names when available
- Embedding model name stored in manifest for consistency checking

---

## Synthesis Module

Called **only** after the Decision Engine confirms `PROCEED`.

- Receives **only** structured, ranked evidence + flags — never the raw retrieval output
- Uses a constrained prompt: *"Answer ONLY using the provided evidence passages"*
- **V4**: Score stripped from LLM evidence block (scores are internal metrics; kept in citations only)
- Returns:

```python
{
    "status"    : "success" | "abstain",
    "answer"    : "...",
    "citations" : [
        {"source": "policy.pdf", "section": "Leave Policy", "score": 0.8055}
    ]
}
```

---

## LLM Backends

Backend priority (first key found in `.env` wins):

| Priority | Backend | Model | Key |
|---|---|---|---|
| 1 | **Groq** | `llama-3.3-70b-versatile` | `GROQ_API_KEY` |
| 2 | OpenAI | `gpt-4o-mini` | `OPENAI_API_KEY` |
| 3 | Google Gemini | `gemini-1.5-flash` | `GEMINI_API_KEY` |
| 4 | Mock | deterministic | *(none needed)* |

**Setup:**
```bash
# Copy and edit .env
GROQ_API_KEY=your_key_here   # get free key at console.groq.com
```

All backends: `temperature=0.0`, `max_tokens=1024`, retry-with-exponential-backoff (3 attempts).

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Add your Groq API key
echo "GROQ_API_KEY=your_key_here" > .env

# Add documents to data/ directory, then run
python main.py                              # interactive REPL
python main.py "What is the leave policy?" # single query
python main.py --demo                       # run all demo queries
python main.py --status                     # show collection info + active backend
python main.py --ingest                     # force full re-ingest
python main.py --retriever qdrant "What is the leave policy?"
python main.py --compare-retrievers         # benchmark ChromaDB vs Qdrant hybrid
```

The system **auto-ingests** on first run — no manual setup required.

---

## File Structure

```
project/
├── main.py                # entry point: REPL, CLI, demo, status modes
├── orchestrator.py        # pipeline controller: preprocess, classify, decompose, decide
├── validation.py          # 7-stage deterministic validation pipeline
├── synthesis.py           # evidence-gated LLM answer generation
├── retrieval.py           # ChromaDB retrieval
├── qdrant_retrieval.py    # Qdrant hybrid retrieval + ingestion
├── retrieval_scoring.py   # shared score calibration
├── retrieval_eval.py      # ChromaDB vs Qdrant comparison harness
├── retrieval_interface.py # retrieval adapter
├── ingestion.py           # document ingestion: chunking, embedding, ChromaDB storage
├── llm_interface.py       # LLM access point: Groq / OpenAI / Gemini / mock
├── utils.py               # shared helpers: similarity (LRU-cached), formatting, abstention
├── requirements.txt       # dependencies
├── .env                   # API keys (git-ignored — never committed)
├── data/                  # source documents (.txt, .pdf)
├── chroma_db/             # ChromaDB vector database (git-ignored — rebuilt automatically)
└── qdrant_db/             # Qdrant vector database (git-ignored — rebuilt automatically)
```

---

## Configuration Thresholds

| Threshold | File | Default | Effect |
|---|---|---|---|
| `MIN_COSINE_THRESHOLD` | `retrieval.py` | 0.40 | Raw cosine floor — below this = off-topic noise |
| `SCORE_FLOOR` | `retrieval.py` | 0.65 | Minimum calibrated score for any passing chunk |
| `DUPLICATE_SIM_THRESHOLD` | `validation.py` | 0.90 | Higher → fewer duplicates removed |
| `RELEVANCE_RATIO_THRESHOLD` | `validation.py` | 0.30 | Higher → stricter relevance filter |
| `MIN_RELEVANCE_SCORE` | `validation.py` | 0.05 | Absolute floor for off-topic chunks |
| `MIN_CHUNKS_FOR_SUFFICIENCY` | `validation.py` | 1 | Minimum relevant chunks to proceed |
| `MIN_AVG_SCORE_FOR_SUFFICIENCY` | `validation.py` | 0.65 | Must equal `SCORE_FLOOR` in retrieval.py |
| `CONFLICT_SIM_THRESHOLD` | `validation.py` | 0.55 | Semantic similarity floor for conflict check |
| `MAX_RETRIES` | `orchestrator.py` | 1 | Retry attempts on conflict |
| `RETRIEVAL_TOP_K` | `orchestrator.py` | 5 | Chunks fetched per sub-query |

---

## Design Principles

| Principle | Implementation |
|---|---|
| Trust before text | All 7 validation stages run before any LLM call |
| Abstention over hallucination | Named abstention reasons; LLM never sees conflicting evidence |
| Evidence-grounded synthesis | Constrained prompt; LLM cannot introduce external facts |
| Deterministic validation | No ML in validation; all heuristics are rule-based |
| Modular and explainable | One responsibility per file; each stage is a single function |
| Traceable citations | Every answer carries source + section + retrieval score |
| Incremental by default | Only changed documents are re-ingested |
| Self-initializing | Auto-ingests on first run; detects model mismatches at startup |
