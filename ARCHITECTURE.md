# Architecture

A map from the pipeline in [claude.md](claude.md) to the files that implement
it. The repository root is flat: fourteen modules sit beside the paper sources
and the ledger, and nothing in the directory listing says which is which. This
file is that missing index.

For what the system measures, see [docs/STATUS.md](docs/STATUS.md). For how to
reproduce a number, [docs/REPRODUCE.md](docs/REPRODUCE.md). For how a design
conclusion was reached, `RAG_System_Observation_Log.md`.

---

## The request path

One query, start to finish. The canonical one-liner is at the top of
`orchestrator.py`:

> `query → preprocess → classify → [decompose] → retrieve → validate(query) → decide → [synthesize]`

| Step | What happens | Where |
|---|---|---|
| 0 | Normalise the query text | `orchestrator.preprocess_query` |
| 1 | Classify as `simple` or `complex` | `orchestrator.classify_query` |
| 2 | Decompose into sub-queries, only if complex | `orchestrator.decompose_query` |
| 3 | Hybrid retrieval, with one conflict-driven retry | `orchestrator.retrieve_for_queries` → `retrieval_interface.retrieve` → `qdrant_retrieval` |
| 4 | Validation, stages 0 to 7 | `validation.validate` |
| 5 | Route: `retry`, `abstain` or `proceed` | `orchestrator.make_decision` |
| 6 | Synthesis, only when the route is `proceed` | `synthesis.synthesize` → `llm_interface` |

Step 3 has a second path. Before retrieving, `orchestrator._extract_target_source`
checks whether the query names a specific document; if it does, every chunk of
that document is fetched instead of running similarity search.

## Where the central claim lives

The project's claim is that the routing decision is deterministic and never
calls an LLM. Concretely:

- `validation.py` ends at **Stage 7**, which sets `abstention_reason` to
  `"conflict"`, `"insufficient"` or `None`.
- `orchestrator.make_decision` is the whole decision engine: it maps that one
  field onto `retry` / `abstain` / `proceed`. It is about fifteen lines, reads a
  single dictionary key, and imports nothing.
- `synthesis.py` and `llm_interface.py` run **after** that, and only on
  `proceed`.

So an LLM cannot talk the system into or out of a refusal, because by the time
any prompt exists the decision has already been made. A learned component may
only **suppress** a conflict the deterministic layer already raised, never
create an abstention. See "The LLM Is Not the Variable" in `claude.md` before
changing anything in this paragraph's blast radius.

## The validation stages

All eight live in `validation.py` (2,288 lines, the largest and most
load-bearing file in the repo). Its module docstring is the authoritative list;
this is the short version.

| Stage | Name | Does |
|---|---|---|
| 0 | Evidence Provenance | Rejects any chunk whose fingerprint does not match the ingested corpus. This is what makes fabricated evidence unacceptable by construction. |
| 1 | Chunk Normalisation | Drops empty chunks, normalises whitespace |
| 2 | Duplicate Removal | Cosine-similarity dedup, keeps the highest-scoring copy |
| 3 | Relevance Filtering | Drops chunks below a query-relevance threshold ("autocut" knee plus a hard floor) |
| 4 | Evidence Consistency | Contradiction detection: keyword, numeric and NLI, gated by `ANSWERHOOD_MARGIN` |
| 5 | Evidence Sufficiency | Count, average score and coverage, with a focus-presence precondition |
| 6 | Evidence Structuring | Adds `rank`, enforces descending score order |
| 7 | Abstention Decision | Emits the named reason the decision engine reads |

Stage 4 is where most of this project's open research sits. Before touching it,
read the "Conflict-Detection Invariants" and "Standing Decisions" sections of
`claude.md`: eight candidate fixes have been falsified there, and the reasons
are recorded.

## The modules

**Pipeline, in request order**

| File | Lines | Role |
|---|---|---|
| `orchestrator.py` | 540 | Drives the six steps above. The pipeline *is* `run()`. |
| `retrieval_interface.py` | 83 | The single seam between the orchestrator and retrieval. `orchestrator` imports only `retrieve` from here. Backend chosen by `RAG_RETRIEVER` (default `qdrant`). |
| `qdrant_retrieval.py` | 956 | The active backend: hybrid dense plus sparse retrieval over the Qdrant store, chunk fingerprints, corpus stats. |
| `retrieval_scoring.py` | 55 | Shared score handling, so scoring rules do not diverge between callers. |
| `validation.py` | 2,288 | Stages 0 to 7. The decision layer. |
| `synthesis.py` | 687 | Builds the prompt from validated evidence, enforces containment, scores faithfulness and citations. |
| `llm_interface.py` | 402 | The only module that calls an LLM. |

**Corpus side, run before any query**

| File | Lines | Role |
|---|---|---|
| `document_preprocessing.py` | 382 | Turns documents into chunks at ingest time. |
| `ingestion.py` | 115 | Builds an index from one or more source directories. |

**Entry points**

| File | Lines | Role |
|---|---|---|
| `main.py` | 503 | CLI entry point. |
| `api.py` | 463 | FastAPI service behind the local console in `frontend/`. Endpoints: `/query`, `/stats`, `/documents`, `/upload`, `/demo`, `DELETE /temporary`, `DELETE /reset`. |

**Support**

| File | Lines | Role |
|---|---|---|
| `tracing.py` | 304 | Optional per-stage execution tracing. |
| `utils.py` | 233 | Shared helpers. |

## What is not pipeline code

The root also holds, and these are not part of the request path:

- `numbers.md` — the number of record. When a measured value changes, this is
  updated first and everything else is made to match it.
- `RAG_System_Observation_Log.md` — append-only record of every change, with
  issue, cause, fix and effect.
- `claude.md` — the project's own working rules and research governance. Read it
  before proposing a decision-layer change.

And in subdirectories:

| Directory | Holds |
|---|---|
| `evaluation/` | The live test suite and the one-off diagnostics. See its own README. |
| `experiments/`, `experiments_corpus2/` | The frozen paper experiments. Not the live suite. |
| `data/`, `data_corpus2/`, `data_corpus3/` | Corpus 1 (HR), Corpus 2 (university), Corpus 3 (ContractNLI). Registered centrally in `evaluation/harness.py` as `CORPORA`. |
| `qdrant_db*/` | Vector stores. Gitignored and rebuildable from the corpora by ingestion. |
| `docs/` | Status, reproduction, preregistrations, handoffs, archive. |
| `paper/` | The live paper: `main.tex` and `references.bib`. Every number in it is traced by `docs/NUMBERS_LEDGER.csv` and verified by `evaluation/check_ledger.py`. |
| `paper_assets/` | Figures and the figure script, referenced by `paper/main.tex`. Its `archive/` holds the superseded v6 draft. |
| `frontend/` | The local console served by `api.py`. |
| `tests/` | Unit tests. `pytest tests/` |

## Reading order, if you are new

1. `claude.md` — the rules, and why they exist.
2. `docs/STATUS.md` — what works and what does not.
3. `orchestrator.run()` — the whole pipeline in one function.
4. `validation.py` module docstring — the eight stages.
5. `docs/REPRODUCE.md` — run something yourself.
