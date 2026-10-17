# Preregistration: MultiHop-RAG decision test

*Written 2026-10-15, before any run, on branch `jonan` at `8d27d23`. Owner approval of the
download, the 300-query design and the baseline model: 2026-10-15. Any change after the
first full-run query is scored goes in an Amendment section below, dated, with the reason.*

## 1. What this tests, and what it is not

NLPIR Section 4.8 reports that on MultiHop-RAG our gate answered 21 of 57 null
(unanswerable) queries, against 1 of 57 for a prompted LLM given the same retrieved
passages. It also reports that the gate refused fewer answerable queries (57.8% vs 79.7%),
mostly through false conflicts. Overall correctness did not differ.

This is a **new measurement** of the same question with a fresh seeded sample. It is not a
reproduction of NLPIR's sample, whose query list and result files are not in the repository.
We compare **direction**, not exact numbers.

No pipeline code, threshold or default is changed for this test. The run uses the default
configuration and refuses to start if any `RAG_*` environment override is set.

## 2. Data

- Source: Tang and Yang, "MultiHop-RAG", COLM 2024 (arXiv 2401.15391). Hugging Face
  dataset `yixuantt/MultiHopRAG`, revision `71ac0d0bd1f951d2d6b70311f7d2ae404e1ffa82`.
  License ODC-BY.
- Files, in `data_multihop/` (gitignored):

  | File | Bytes | SHA-256 |
  |---|---|---|
  | `MultiHopRAG.json` | 5,171,312 | `03cfb4926461f868684903aadc8024447bdda5bb3f6804741424cce338515bff` |
  | `corpus.json` | 6,785,567 | `20b61b5ab84de84a927420c5d265b7ec8d859ae49980699958a787ade9e4d28f` |
- Contents, checked on download:
  - 609 articles, all with unique titles;
  - 2,556 queries: 816 inference, 856 comparison, 583 temporal, 301 null;
  - every null query has the gold answer "Insufficient information." and no evidence;
  - every evidence title is in the corpus.

## 3. Index

- **All 609 articles are indexed.** This is the whole official knowledge base, which is also
  what NLPIR's "609-article index" was.
- Each article becomes one text file, `data_multihop/articles/mh_NNN.txt` (NNN = position
  in `corpus.json`, zero-padded).
- Names are neutral on purpose. The orchestrator restricts evidence to any document whose file
  stem appears in the query, and a title-based name could trigger that by accident.
- A map from file name to title is kept beside the files, used only for grading retrieval.
- Each file holds a metadata header and then the body, verbatim:

  ```
  Title: <title>
  Source: <source>
  Author: <author>
  Published: <published_at>
  Category: <category>

  <body>
  ```

  The header is there because MultiHop-RAG questions name the outlet and the date (for
  example "according to the TechCrunch article published on ..."), and the benchmark's
  knowledge base carries these fields.
- Ingestion is the unchanged `qdrant_retrieval.ingest_documents` (500-character chunks,
  50 overlap), into a new store `qdrant_db_multihop/` (gitignored). No existing store is
  opened for writing.
- Measured before any run: this gives 22,131 chunks, against NLPIR's 22,061 (21,804 without
  the header). The exact count from ingestion is recorded in the result file.

## 4. Sample

- Seed **20261015**. For each type, the queries of that type are taken in file order and
  `random.Random(20261015 + k).sample` draws the quota, with k = 0, 1, 2, 3 for null,
  inference, comparison and temporal.
- Quotas:
  - 150 of the 301 null queries;
  - 50 each of inference, comparison and temporal;
  - 300 queries in all, as in NLPIR's preregistered design.
- Query ids are `mh` plus the zero-padded position in `MultiHopRAG.json`.
- **Run order** is the 300 sampled queries shuffled with `random.Random(20261015)`. If a run
  stops early, the completed queries are then a random subset of the sample, not a type-ordered
  prefix.
- Both arms run in the same order, and the primary analysis uses every query both arms
  completed (paired). The intent is to finish all 300.

## 5. Arms

**Ours.**
- `orchestrator.run()` unchanged, through `evaluation/harness.py`'s decision-only setup:
  - synthesis is stubbed, so this arm makes zero LLM calls;
  - the store's provenance registry and corpus statistics are published;
  - retrieval is wrapped in the harness disk cache.
- Retrieval is **not bypassed**: preprocess, classify, decompose, hybrid retrieval at top 30,
  validation, and the one conflict retry at top 33.
- Decision: `proceed` = answer; abstention with reason `conflict` = conflict; any other
  abstention = insufficient (the `harness.decision_of` mapping).

**Prompted baseline.**
- Model `openai/gpt-oss-120b` on Groq, temperature 0. `max_tokens` is 4096, re-asked once at
  8192 if the reply is empty, as in the clean RAMDocs runner.
- Prompt: the E1 system prompt and user template from `experiments/baseline_experiment.py`,
  verbatim (also NLPIR Appendix A).
- **Same retrieved passages:**
  - the passages are what the orchestrator's first-attempt retrieval returns for the query
    (same preprocessing, classification, decomposition, `retrieve_for_queries` with the same
    `top_k`, and the same cache);
  - every passage is sent, in retrieval order, rendered as `[Passage i | Source: mh_NNN.txt]`
    and its text;
  - the baseline therefore sees the unvalidated retrieved set, as in NLPIR.
- Decision: `parse_decision` from `experiments/baseline_experiment.py`. A reply starting with
  CONFLICT is a conflict, one starting with INSUFFICIENT is insufficient, anything else is an
  answer. Raw replies are stored so any grader can be re-applied without new calls.
- Keys: `evaluation/key_pool.py` rotation (names printed, never values), advancing only on a
  spent or rejected key.

## 6. Grading (decisions only; answer content is not graded)

- Gold for a null query is insufficient; gold for inference, comparison and temporal queries
  is answer.
- **Primary outcomes:**
  1. **Gap leak:** a null query answered. Rate over null queries, per arm.
  2. **Over-abstention:** an answerable query not answered (conflict or insufficient). Rate
     over answerable queries, per arm, also split into conflict and insufficient.
- **Secondary outcomes:**
  - **Decision correct (strict, as NLPIR):** null gives insufficient, answerable gives answer.
  - **Decision correct (lenient):** null gives any abstention.
  - Refusal rate over all queries.
  - Each of these per query type.
- **Retrieval, ours, answerable queries only.** Gold articles are the evidence titles.
  - Article recall@5 for the original question: the share of gold articles among the top 5
    retrieved for the unsplit query.
  - Gold articles retrieved across sub-queries: the share of gold articles anywhere in the
    first-attempt retrieved set.
- **Statistics:**
  - Wilson 95% intervals for every rate;
  - exact two-sided McNemar tests on the paired per-query outcomes for gap leak,
    over-abstention and strict decision correctness;
  - no other tests are planned.

## 7. Predictions (written before any run)

These follow NLPIR's direction. Each will be reported as held or not held.

- **P1.** Ours answers more null queries than the baseline, and the McNemar test on gap leaks
  gives p < 0.05.
- **P2.** The baseline over-abstains on more answerable queries than ours.
- **P3.** Most of ours' answerable over-abstentions are conflicts, not insufficient.
- **P4.** Strict decision correctness does not differ significantly (p ≥ 0.05).
- **P5.** Gold-article recall across sub-queries is at least 80%, and article recall@5 for the
  original question is below 70%.

## 8. Rules during and after the run

- A pilot of 6 queries (from the shuffled order) runs first on both arms, to check plumbing
  only. Pilot results are not part of the analysis and the full run starts from scratch.
- Thresholds, prompts and grading stay as written.
  - If a harness bug is found after scoring begins, it is fixed in evaluation code only. An
    Amendment explaining it is recorded here before the affected arm is re-run in full.
  - Results are never re-run because they look wrong.
- After the run, the sample is sealed like RAMDocs: not used to choose or tune anything.
- What is recorded:
  - results go to `evaluation/results/mh_*` (gitignored), with a `run_info` stamp (commit,
    source hashes, effective switches);
  - numbers go to `numbers.md`, an Observation in the log, and rows in
    `docs/NUMBERS_LEDGER.csv` (status REPRODUCED for what was run).

## Amendments

### Amendment 1 (2026-10-17, after the pilot, before any full-run query): baseline passage cap

- **What changed.** The baseline is sent the **top 12** retrieved passages in retrieval order,
  not every passage. Section 5's "every passage is sent" is replaced by this.
  - The cap is applied with E1's own `build_context_block(chunks, max_chunks=12)`.
  - Our arm is unchanged.
- **Why.** In the pilot, the baseline request for the fourth query (all retrieved passages)
  needed 10,176 tokens. The free Groq tier rejects any single request over 8,000 tokens per
  minute for `openai/gpt-oss-120b` (HTTP 413), and changing keys cannot fix that. Twelve passages
  is also what the E1 baseline itself sent: `experiments/baseline_results.json` records
  `max_chunks_sent: 12`, the default of `experiments/baseline_experiment.py`. The cap therefore
  makes the baseline closer to E1, not further from it.
- **Decided before any scored data.** Only the pilot had run, and pilot results are excluded
  from the analysis by Section 8. The decision was taken on the request-size error alone,
  without looking at any pilot outcome.
- **Known cost, to be reported with the results.**
  - The baseline sees fewer passages than our gate, which validates up to about 30.
  - A gold article ranked below 12th is invisible to the baseline, which should push it toward
    insufficient on answerable queries (the P2 direction).
  - The report gives the share of gold articles inside the 12 sent passages
    (`baseline_visibility`), so this effect is measured rather than assumed.
  - NLPIR's cap is unknown, so this may differ from its "same retrieved passages".
- **Rows record** both the number of passages retrieved and the number sent.
- **Pilot files.**
  - The three baseline pilot rows run before this amendment were sent all passages. Their
    checkpoint is kept, renamed `*.superseded_amendment1`.
  - The baseline pilot is re-run under the cap.
  - Predictions P1 to P5 are unchanged.
