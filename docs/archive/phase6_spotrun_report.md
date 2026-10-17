# Phase 6 — Integration & Baseline Report

**Corpus re-ingested:** 11 documents → **84 chunks** in Qdrant collection `trust_before_text_chunks` (dense + sparse + ColBERT).

**Run conditions:** every query executed through `orchestrator.run(...)` with the answer LLM disabled (`GROQ_API_KEY`/`OPENAI_API_KEY`/`GEMINI_API_KEY` empty). Only the deterministic **decision** is scored. Ground-truth labels are what the *documents* support (verified in Phase 5). **The pipeline was not modified or tuned** — every mismatch below is the pipeline's own behavior against known-correct ground truth. Per-query output is in [`phase6_fullrun_results.json`](phase6_fullrun_results.json).

## Full 78-query baseline

**Overall decision accuracy: 53 / 78 = 67.9%**

Confusion matrix (rows = expected / ground truth, columns = pipeline decision):

| expected ↓ / got → | answer | conflict | insufficient |
|---|---|---|---|
| **answer** (46) | **25** | 9 | 12 |
| **conflict** (16) | 4 | **12** | 0 |
| **insufficient** (16) | 0 | 0 | **16** |

Per-class recall:

| Class | Recall | Reading |
|---|---|---|
| insufficient | **16/16 = 100%** | Every deliberate gap / out-of-scope query correctly abstains (`relevant_count = 0`). |
| conflict | **12/16 = 75%** | All 4 planted conflicts detected — but only under certain phrasings (see below). |
| answer | **25/46 = 54%** | Pipeline over-abstains on answerable queries: 9 false conflicts + 12 false "insufficient". |

## Headline finding — conflict detection is phrasing-sensitive

The **same four conflicts (C1–C4)** were probed with different query wordings. Detection split perfectly by phrasing:

| Phrasing style | Example | Detected |
|---|---|---|
| Natural question (conflict-probing) | *"What percentage does the employer contribute to my pension?"* | **10 / 10** |
| Applied scenario | *"I'm a new employee. How long is my probation?"* | **2 / 2** |
| Explicit comparison | *"Compare the employer pension contribution in the Handbook and the Compensation policy."* | **0 / 4** |

All 4 `conflict` misses (Q035–Q038) are the **cross-document-comparison** phrasings of conflicts that the pipeline *does* catch when asked plainly. Cause: comparison queries add content words like *compare / handbook / compensation / policy*, which widen the query-relevant sentence span in `find_conflict` (validation.py Stage 4). The specific clashing sentences get diluted among many matched sentences, dropping NLI contradiction confidence below `NLI_CONFLICT_THRESHOLD` (0.80) and the numeric/keyword prong below the `CONFLICT_SIM_THRESHOLD` (0.68) similarity gate. **Conflict detection therefore depends on how narrowly the question targets the clashing fact — a real, actionable weakness surfaced by the eval.**

## Answer-class errors (21 of 46)

**9 false conflicts (answer → conflict).** Broad/decomposed retrieval pools many chunks (e.g. Q001 "annual leave days" retrieved 24 chunks) and the NLI cross-encoder flags a spurious contradiction between two unrelated documents:
- Q001, Q019, Q027, Q029, Q064, Q067, Q069, Q072 — NLI false positives.
- Q062 — a *numeric* false positive (Compensation vs IT), the deterministic prong misfiring on unrelated same-unit numbers.
- The **superseded 2023 Remote Working Policy** is a recurring contaminant (appears in Q064, Q067, Q069 pairs on non-remote topics). Keeping it in the corpus was intentional (versioned-conflict design) and realistic, but it demonstrably injects retrieval noise.

**12 false abstentions (answer → insufficient).** Correct evidence is retrieved but `relevant_count` is small (1–6) and the average calibrated score / query-coverage does not clear the sufficiency gate (`MIN_AVG_SCORE_FOR_SUFFICIENCY = 0.65`, `MIN_QUERY_COVERAGE = 0.55`): Q004, Q006, Q010, Q015, Q032, Q059, Q060, Q061, Q065, Q066, Q070, Q073. These are legitimately answerable single-fact and list-all queries (facts confirmed present in Phase 5).

## Interpretation

This is a **working evaluation set with trustworthy ground truth**, not a pass/fail scorecard for the corpus:

- **Abstention recall is perfect (100%)** and **conflict recall is solid where questions are natural (12/12)** — the "Trust Before Text" safety behavior works.
- The eval cleanly exposes three measurable weaknesses for `benchmark.py` to track: (1) **conflict misses under comparison phrasing**, (2) **NLI false-conflicts under broad retrieval**, (3) **sufficiency-threshold false-abstentions** on thin-but-correct evidence.
- A test set the pipeline aced would be uninformative; the 67.9% baseline with a clear error taxonomy is the useful result.

**No pipeline code was changed.** All errors are the current pipeline baseline measured against document-derived ground truth.
