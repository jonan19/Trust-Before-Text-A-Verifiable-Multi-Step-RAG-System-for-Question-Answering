# evaluation/

Test harnesses for the decision layer. Everything here runs with **zero LLM
tokens** except the two scripts marked otherwise.

Commands and how to read the output: [../docs/REPRODUCE.md](../docs/REPRODUCE.md).
Current results: [../docs/STATUS.md](../docs/STATUS.md).

> This directory was previously called `experiments_fixes/`. It holds the
> project's live test suite, not a historical record — the frozen paper
> experiments are in `../experiments/`.

---

## The routine suite

Run these after any change to the decision layer. These are the scripts that
produce the numbers in `STATUS.md`.

| Script | What it measures |
|---|---|
| **`run_eval.py`** | The main scoreboard: accuracy, conflict precision/recall/F1, gap leaks, unsafe answers, over all 78 questions of a corpus. |
| **`invariance_harness.py`** | Whether meaning-preserving changes to the input (reordering evidence, duplicating it, adding distractors, rewording the question) change the decision. They must not. This is the generalisation signal — see REPRODUCE.md for why it matters more than accuracy. |
| **`adversarial_gap_probes.py`** | 48 injection attacks aimed at genuine knowledge gaps. |
| **`fabricated_evidence_test.py`** | Injects invented passages; checks Stage 0 provenance rejects them. |
| **`synthesis_containment_test.py`** | Checks injected text never reaches the LLM prompt. |
| **`label_audit.py`** | Integrity of the injection-set hijack labels (re-grades on whether the payload reached the user). |
| **`preingestion_poisoning.py`** | The harder version of the probe above: a fabricated document entering through *normal ingestion*, so Stage 0 cannot reject it on provenance. Measures what the gate does when the poison is genuinely in the corpus. |

## Corpus 3 — ContractNLI (held-out)

**The `test` split is sealed. Debug on `dev`. Read
[../docs/PREREGISTRATION_CORPUS3.md](../docs/PREREGISTRATION_CORPUS3.md) first.**

Corpus 3 is not one store but ~45: one per bundle of 4 real NDAs. `harness.py`
registers each as `3-<bundle>`, so `--corpus 3-dev-b00` works everywhere
`CORPORA` is used.

| Script | What it does |
|---|---|
| **`build_corpus3.py`** | Builds bundles and stores from ContractNLI. Verifies gold-span offset integrity before ingesting. `--verify-only` checks without building. |
| **`run_eval_corpus3.py`** | Runs a split, pools the records, scores them with the same `harness.metrics()` used for C1/C2, and prints the always-answer floor beside accuracy. Refuses to start if any `RAG_*` override is set. |
| **`span_attribution.py`** | Grades citations against ContractNLI's gold evidence spans — the project's first externally validated attribution numbers. Watch `unresolved_rate`: above 5% means the offset sidecar diverged from the ingest path. |
| **`bootstrap_ci.py`** | Confidence intervals, resampling **bundles** not queries (queries in a bundle share documents and are not independent). |
| **`baselines_corpus3.py`** | always-answer / always-abstain / retrieval-threshold arms. The floor is 77.6% on the test split; an accuracy number without it is uninterpretable. |
| **`ingest_track_b.py`** | Converts the delivered Track B question set (`data_corpus3/corpus3_queries_combined.json`) into per-bundle `queries_open.json` and `gold_spans_open.json`. `--check` validates without writing. Authorship is recorded in [../docs/CORPUS3_TRACK_B_ASSIGNMENT.md](../docs/CORPUS3_TRACK_B_ASSIGNMENT.md). |
| **`rerun_corpus3.py`** | Resumable replay of the sealed 2026-08-31 run, whose raw result files are in no git ref. Runs each track in batches so a three-hour run is not lost to one failure. |
| **`merge_corpus3_parts.py`** | Merges those batched runs into the single result file `run_eval_corpus3.py` would have written. |
| **`llm_baseline_corpus3.py`** | The bare-LLM arm the preregistration requires. Exists because `adversarial_baseline_probe.py` is hardcoded to Corpus 1/2. **Needs LLM tokens.** |
| **`compare_phrasing.py`** | Isolates query-phrasing sensitivity: the same 17 propositions, same documents, same gold labels, only the surface form differs. |

Two hazards, both already handled — do not remove the guards:

* `qdrant_retrieval._get_client()` caches one module-global client and **ignores
  `qdrant_dir` once open**. Both scripts call `_close_client()` between bundles;
  without it every bundle after the first silently reads bundle 0's store.
* Documents are written with `newline=""`. CRLF translation would shift every
  gold span offset and turn span grading into noise rather than failing loudly.

Order of work: `build_corpus3.py --split dev` -> `run_eval_corpus3.py --split dev`
-> `span_attribution.py` -> fix anything broken -> only then touch `--split test`,
once, with the pre-registration committed.

## External benchmarks

Datasets this project did not author. These carry the project's only
generalisation evidence, so **read the matching preregistration in `../docs/`
before running one**, and note that each is sealed once used.

| Script | What it does |
|---|---|
| **`run_eval_ramdocs.py`** | RAMDocs (Han et al., COLM 2025), a published benchmark built around conflicting evidence. |
| **`run_eval_ramdocs_clean.py`** | The corrected RAMDocs run. The earlier one named documents `rd0000_doc3_misinfo` with section `misinfo`, and `synthesis.py` renders both into the prompt, so the model was being told which document was the bad one. This removes that label signal. **Use this one.** |
| **`run_eval_multihop.py`** | The preregistered MultiHop-RAG test: all 609 articles through unchanged ingestion into a new store, no existing store reused. |
| **`merged_corpora_test.py`** | Not external, but cross-corpus: builds one index from all 22 Corpus 1 and Corpus 2 documents and runs each corpus's own 78 queries against it, to see whether the frozen system still behaves when the corpora share a store. |

---

## Measurement and paper tables

Scripts whose output goes directly into the paper or into a design decision,
rather than into pass/fail testing.

| Script | What it produces |
|---|---|
| **`sweep_tables.py`** | Reproduces the threshold-sensitivity (Table 4) and component-ablation (Table 5) rows end to end, driven by `RAG_*` environment switches only, with no code edits. |
| **`nli_scores.py`** | The NLI contradiction score of every Stage-4 candidate pair, per query. Source for the NLI-separation figure (Fig. 6). Zero LLM tokens. |
| **`retrieval_recall.py`** | Document-level retrieval recall against `expected_sources`, measuring the retriever alone on the single preprocessed query, exactly as validation first receives it. Use this before blaming the vector store. |
| **`safety_curve.py`** | What zero unsafe answers costs. Treats "never unsafe" as an operating point to choose rather than a bug to fix. **Corpus 3 dev is the only external data this may sweep**; see Observation 61. |

---

## Provenance and bookkeeping

| Script | Role |
|---|---|
| **`run_info.py`** | Stamps every result file with the code and settings that produced it. Added after a Corpus 2 gap-probe file turned out to predate `ANSWERHOOD_MARGIN` with nothing on it to say so. If you add a harness, stamp its output. |
| **`check_ledger.py`** | Verifies every numeric claim in `docs/NUMBERS_LEDGER.csv` against the file it appears in: recomputes it, confirms the text is present, and checks `main.tex` is fully covered. Run it after any number or paper edit, with `--sync-lines` when text has moved. |
| **`rerun_suite.py`** | Resumable, chat-independent re-run of the whole zero-token suite. Records progress to `<run-dir>/state.json` and skips completed steps, so it survives being run detached. |

---

### Shared machinery

| Script | Role |
|---|---|
| `harness.py` | Corpus selection, on-disk retrieval cache, metric computation. Imported by everything else. |
| `harness_bootstrap.py` | Puts this directory on `sys.path`. Imported first by every script here. |
| `focus.py` | Prototype of the query focus-term idea. The production version now lives in `validation.py`; this is kept because the offline labs import it. |
| `key_pool.py` | An explicit, ordered pool of Groq keys for long resumable runs, read from the environment as `GROQ_API_KEY`, `GROQ_API_KEY_2`, and so on. Advances only when the current key is exhausted. |

### Needs LLM tokens

| Script | Why |
|---|---|
| `adversarial_baseline_probe.py` | Runs external baseline models for comparison. |
| `live_end_to_end.py` | Runs whole queries through the real pipeline with an LLM actually writing answers. |

---

## One-off diagnostics

Single-purpose scripts written to answer one question during a specific
investigation. **They are not part of routine testing** and several encode
assumptions from the moment they were written. Kept because they document how a
conclusion was reached.

| Script | The question it was written to answer |
|---|---|
| `coverage_leak_diag.py` | Why did this query's sufficiency gate pass when it should have failed? |
| `overabstention_diag.py` | Why did this answerable query get refused? |
| `q017_margin.py` | Can a coverage floor close the Q017 leak without costing a good query elsewhere? (No.) |
| `threshold_sensitivity.py` | How much does conflict F1 depend on the NLI threshold? |
| `rank_gate_sweep.py` | What does the conflict rank gate cost and buy? (Led to retiring it.) |
| `conflict_lab.py`, `conflict_sweep.py`, `conflict_sweep2.py` | Candidate rules for suppressing false conflicts. All falsified. |
| `analyze_span_relevance.py` | Does query/span embedding similarity separate true from false conflicts? (Not on Corpus 2.) |
| `sufficiency_lab.py`, `focus_suff_lab.py` | Alternative sufficiency formulations. |
| `entailment_sensitivity.py`, `faithfulness_candidates.py`, `release_gate_test.py` | The output-side faithfulness gate, and why it is permanently disabled. |
| `pair_lab.py`, `dump_stage3.py`, `build_corpus_stats.py` | Data dumps for manual inspection. |
| `answerhood_lab.py` | Can a cross-encoder answerhood score do what the bi-encoder topicality gate could not? (Yes, and it shipped as `ANSWERHOOD_MARGIN`; this is the offline separation study behind it.) |

---

## Output

`results/` holds JSON from every run, named `<tag>_corpus<N>.json`.
`_retrieval_cache/` caches retrieval results so threshold sweeps do not re-embed
every query.

Both are gitignored — they are regenerable.

> ⚠️ **Clear `_retrieval_cache/` after re-ingesting a corpus.** Otherwise the
> harnesses silently replay results computed against the old chunks. This has
> caused a wrong conclusion at least once.

> ⚠️ **Never run two harnesses against the same corpus at once.** Embedded Qdrant
> allows one process per store folder; the second fails with *"Storage folder is
> already accessed by another instance"*.
