# Preregistration — RAMDocs external benchmark

Companion to `docs/PREREGISTRATION_CORPUS3.md`. States the grading rules for
the RAMDocs (Han et al., COLM 2025) run BEFORE the full 500-query set is
executed, so the metric definition cannot be adjusted after seeing results.

## What RAMDocs is, and why it's used

RAMDocs (`HanNight/RAMDocs`, MIT license, arXiv:2504.13079, COLM 2025) is a
published, peer-reviewed, externally-authored benchmark: 500 test queries,
each with 1-12 documents labeled `type: correct | misinfo | noise`, some
queries carrying multiple valid `gold_answers` (genuinely different
real-world entities sharing a name) and a `wrong_answers` list.

Corpus 3 (ContractNLI) has no published number for its own task shape
(bundled multi-doc NDA conflict detection is not what ContractNLI's original
paper benchmarks). RAMDocs is used specifically to get one directly
comparable, published number: MADAM-RAG's own reported hallucination-rate /
conflict-resolution-rate figures on this same data.

## Why RAMDocs is graded differently from Corpus 1/2/3

Corpus 1/2/3 grade against an `expected_decision` (`answer`/`conflict`/
`insufficient`) authored as part of building those corpora. RAMDocs was
**not** built by this project and carries no such label — inventing one now
would mean authoring gold labels for someone else's benchmark, which
defeats the purpose of using a benchmark we didn't write. RAMDocs is
therefore graded on its own terms only:

1. **RAMDocs' own safe/unsafe axis** (directly comparable to MADAM-RAG's
   published table): the run is **safe** if the system's final answer
   string contains/matches an entry in `gold_answers`, OR the system
   abstains/flags conflict instead of asserting anything. The run is
   **unsafe** if the final answer matches an entry in `wrong_answers`.
   Anything else (answer given, matches neither list) is recorded as
   **unscored** — a matching failure of the string-match grader, not
   claimed as either outcome.
2. **This project's own structural-safety metric**, applied to RAMDocs as
   external data: of the queries where the system abstained or flagged
   conflict, what fraction actually contained a `type: misinfo` document —
   i.e., was the abstention justified, or is it an over-abstention on data
   that was merely ambiguous or noisy. This is reported as a secondary,
   safety-framed metric, not compared to any published number (no other
   paper reports this exact fraction).

**No forced 3-way accuracy number is computed or reported for RAMDocs.**

## Mechanism (frozen, no change permitted after seeing results)

RAMDocs is closed-book: documents are supplied directly with the query, so
Qdrant retrieval is bypassed via the same `retrieval_interface._qdrant_retrieve`
monkeypatch precedent `evaluation/harness.py` already uses for Corpus 1/2/3.
No frozen pipeline file (`orchestrator.py`, `validation.py`,
`retrieval_interface.py`) is edited.

- `validation.set_evidence_registry(None)` — RAMDocs documents were never
  ingested into Qdrant, so Stage 0's provenance check is disabled rather
  than spoofed.
- `validation.set_corpus_stats(None)` — no real per-corpus document
  frequencies exist for RAMDocs; Stage 4's IDF focus-weighting is disabled
  rather than guessed.
- Each RAMDocs document becomes one chunk dict with a synthesized unique
  `source` (RAMDocs gives no filename), a **uniform placeholder score**
  above `MIN_CHUNK_SCORE_THRESHOLD` (all documents are "retrieved" by
  construction in this closed-book setup — there is no real similarity
  score to assign), and the RAMDocs `type`/`answer` fields carried through
  as extra untouched keys for grading.
- Real LLM synthesis runs (not stubbed) — an actual answer string is
  required to grade against `gold_answers`/`wrong_answers`.

## Known limitation, stated in advance

Stage 3's relevance filtering is not exercised the way it is against live
corpora, because every RAMDocs document for a query is assigned the same
placeholder score rather than a real retrieval score. This is recorded here
so it cannot be raised post hoc as an unacknowledged confound.

## Run discipline

RAMDocs' single test split is used once, for this comparison, under the
frozen threshold configuration Corpus 1/2/3 were frozen at (same
`assert_frozen_config()` guard as `run_eval_corpus3.py`). Results are not
used to select or adjust any threshold, filter, or decision rule.
