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

### Shared machinery

| Script | Role |
|---|---|
| `harness.py` | Corpus selection, on-disk retrieval cache, metric computation. Imported by everything else. |
| `harness_bootstrap.py` | Puts this directory on `sys.path`. Imported first by every script here. |
| `focus.py` | Prototype of the query focus-term idea. The production version now lives in `validation.py`; this is kept because the offline labs import it. |

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
