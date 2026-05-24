# Trust Before Text — V3 Architecture

## Philosophy

> **"Trust Before Text"** — deterministic evidence validation before generation.

The system generates answers **only** from verified evidence.
When evidence is insufficient or contradictory, it **abstains** rather than hallucinating.

---

## High-Level Pipeline

```
User Query
    ↓
Orchestrator
    ├─ classify query (simple / complex)
    ├─ decompose complex queries into sub-queries
    └─ retrieve chunks for each sub-query
         ↓
    Validation Pipeline (7 stages, fully deterministic)
         ↓
    Decision Engine  →  proceed | retry | abstain
         ↓
    Synthesis Module  (LLM used ONLY here)
         ↓
    Final Answer  (with citations + scores)
```

---

## V3 Validation Pipeline

All validation is **deterministic and non-LLM**.

### Stage 1 — Chunk Normalization
- Strip leading/trailing whitespace
- Collapse internal whitespace
- Remove empty chunks

### Stage 2 — Duplicate Removal
- Compute TF cosine similarity between all chunk pairs
- If similarity ≥ `DUPLICATE_SIM_THRESHOLD` (0.90), keep only the higher-scoring chunk
- Prevents redundant evidence from inflating sufficiency scores

### Stage 3 — Relevance Filtering *(New in V3)*
- Compute TF cosine similarity between the query and each chunk
- Find the best similarity score across all chunks
- Keep chunks whose similarity ≥ `best_sim × RELEVANCE_RATIO_THRESHOLD` (0.30)
- Absolute floor: any chunk scoring < `MIN_RELEVANCE_SCORE` (0.05) is dropped
- Output: each passing chunk gets a `relevance_score` field

### Stage 4 — Evidence Consistency Analysis *(Upgraded in V3)*
- Runs on the **relevance-filtered** chunk set (stage 3 output)
- For each pair of chunks sharing the same section OR with high semantic similarity (cosine ≥ 0.55):
  - Check keyword contradiction using 21 antonym pairs (expanded from 10 in V2)
  - Check numeric contradiction for same-section pairs (e.g., "20 days" vs "15 days")
- Sets `conflict_flag = True` if any contradiction is found

**21 antonym pairs include:**
`prohibited/allowed`, `banned/permitted`, `mandatory/optional`, `cannot/can`,
`never/always`, `deny/approve`, `rejected/approved`, `terminated/active`, and more.

### Stage 5 — Evidence Sufficiency Check *(Upgraded in V3)*
Heuristics (all three must pass):
- **H1**: At least `MIN_CHUNKS_FOR_SUFFICIENCY` (1) relevant chunks
- **H2**: Average retrieval score ≥ `MIN_AVG_SCORE_FOR_SUFFICIENCY` (0.65)
- **H3**: At least one chunk has `relevance_score > MIN_RELEVANCE_SCORE`

### Stage 6 — Evidence Structuring *(New in V3)*
Returns chunks as fully-typed structured dicts with enforced descending score order:

```python
{
    "rank"           : 1,          # 1 = best scoring chunk
    "text"           : "...",
    "source"         : "policy.pdf",
    "section"        : "Leave Policy",
    "score"          : 0.9100,     # retrieval score from vector store
    "relevance_score": 0.6736,     # query-text cosine similarity (Stage 3)
}
```

### Stage 7 — Abstention Decision *(New in V3)*
Returns a named reason instead of a bare boolean:

| Condition | Reason | Action |
|-----------|--------|--------|
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

## Synthesis Module

Called **only** after the Decision Engine confirms `PROCEED`.

- Receives **only** structured, ranked evidence chunks + flags
- Never accesses the vector database or raw retrieval output
- Uses a constrained prompt: *"Answer ONLY using the provided evidence passages"*
- Returns:

```python
{
    "status"    : "success" | "abstain",
    "answer"    : "...",
    "citations" : [
        {"source": "policy.pdf", "section": "Leave Policy", "score": 0.9100}
    ]
}
```

---

## Abstention Response

When the system cannot safely answer:

```python
{
    "status"  : "abstain",
    "reason"  : "conflict" | "insufficient",
    "answer"  : "<human-readable explanation>",
    "citations": []
}
```

---

## File Structure

```
project/
├── orchestrator.py        # pipeline controller, query classification, decision engine
├── validation.py          # 7-stage deterministic validation pipeline
├── synthesis.py           # evidence-gated LLM answer generation
├── retrieval_interface.py # retrieval stub (swap for real backend)
├── llm_interface.py       # single LLM access point (OpenAI + mock)
├── utils.py               # shared helpers: similarity, formatting, abstention
├── main.py                # entry point + demo queries
└── README.md              # this file
```

---

## Configuration Thresholds

All thresholds are defined at the top of their respective modules:

| Threshold | File | Default | Effect |
|-----------|------|---------|--------|
| `DUPLICATE_SIM_THRESHOLD` | `validation.py` | 0.90 | Higher → fewer duplicates removed |
| `RELEVANCE_RATIO_THRESHOLD` | `validation.py` | 0.30 | Higher → stricter relevance filter |
| `MIN_RELEVANCE_SCORE` | `validation.py` | 0.05 | Absolute floor for off-topic chunks |
| `MIN_CHUNKS_FOR_SUFFICIENCY` | `validation.py` | 1 | Minimum relevant chunks to proceed |
| `MIN_AVG_SCORE_FOR_SUFFICIENCY` | `validation.py` | 0.65 | Minimum average retrieval score |
| `CONFLICT_SIM_THRESHOLD` | `validation.py` | 0.55 | Semantic similarity floor for conflict check |
| `MAX_RETRIES` | `orchestrator.py` | 1 | Retry attempts on conflict |
| `RETRIEVAL_TOP_K` | `orchestrator.py` | 5 | Chunks fetched per sub-query |

---

## Usage

```bash
# Run all demo queries
python main.py

# Run a single query
python main.py "What is the remote work policy?"

# Use a real LLM (requires OpenAI API key)
$env:OPENAI_API_KEY = "sk-..."
python main.py
```

---

## Wiring the Real Retrieval Backend

Replace the mock body in `retrieval_interface.py`:

```python
from your_retrieval_package import retrieve as _real_retrieve

def retrieve(query: str, top_k: int = 5) -> list[dict]:
    return _real_retrieve(query, top_k=top_k)
```

Each returned chunk must have: `text`, `source`, `section`, `score`.

---

## Design Principles

| Principle | Implementation |
|-----------|----------------|
| Trust before text | All 7 validation stages run before any LLM call |
| Abstention over hallucination | Named abstention reasons; LLM never sees conflicting evidence |
| Evidence-grounded synthesis | Constrained prompt; LLM cannot introduce external facts |
| Deterministic validation | No ML models in validation; all heuristics are rule-based |
| Modular and explainable | One responsibility per file; each stage is a single function |
| Traceable citations | Every answer carries source + section + retrieval score |

---

## LLM Usage Rules

- The LLM is called **only** by `synthesis.py` via `llm_interface.call_synthesis_llm()`
- It receives **only** the structured, validated evidence block + the query
- Temperature = 0.0 (deterministic output)
- The system prompt forbids prior knowledge and external inference
- Without `OPENAI_API_KEY`, a deterministic mock is used automatically