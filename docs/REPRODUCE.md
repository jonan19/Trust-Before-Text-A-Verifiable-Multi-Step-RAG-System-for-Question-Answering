# Reproducing Every Number

Every figure in [STATUS.md](STATUS.md) comes from one of these commands. All of
them run with **zero LLM tokens** except where noted.

Run everything from the repository root.

---

## Setup

```bash
pip install -r requirements.txt
```

The test harnesses read from `qdrant_db_c1_copy/` and `qdrant_db_c2_copy/`, not
from the live `qdrant_db/`. Embedded Qdrant permits only one process per store
folder, which is why the live store is kept separate.

### Rebuild the stores

Needed after any change to chunking, ingestion, or the provenance registry.

```bash
python -c "
import qdrant_retrieval as qr
qr.ingest_documents(data_dir='data',         qdrant_dir='qdrant_db_c1_copy', force=True)
qr.ingest_documents(data_dir='data_corpus2', qdrant_dir='qdrant_db_c2_copy', force=True)
"
```

This writes three things into each store folder:

| File | Purpose |
|---|---|
| `collection/` | the vectors themselves |
| `chunk_registry.json` | SHA-256 fingerprint of every chunk — Stage 0 provenance |
| `corpus_stats.json` | per-word document frequency — used to pick a question's focus terms |

> ⚠️ **Always clear the retrieval cache after rebuilding**, or the harnesses will
> silently replay results computed against the old chunks:
> ```bash
> rm -rf evaluation/_retrieval_cache/1 evaluation/_retrieval_cache/2
> ```

> ⚠️ **Never run two harnesses against the same store at once.** Embedded Qdrant
> allows one process per folder; a second one fails with
> *"Storage folder is already accessed by another instance"*. Run them serially.
> (This is how the outstanding Corpus-2 fabricated-evidence run was lost.)

---

## The main scoreboard

Accuracy, conflict precision/recall/F1, gap leaks, unsafe answers.

```bash
python evaluation/run_eval.py --corpus 1 --tag current
python evaluation/run_eval.py --corpus 2 --tag current
```

Writes `evaluation/results/current_corpus{1,2}.json`. First run is slow
(~3 min, it populates the retrieval cache); later runs are ~80 s.

Useful flags: `--ids Q017,Q051` to run a subset, `--quiet` to suppress
per-question output.

---

## Invariance tests

The generalisation signal. See [HOW_IT_WORKS.md](HOW_IT_WORKS.md) §5 for why this
matters more than accuracy.

```bash
python evaluation/invariance_harness.py --corpus 1
python evaluation/invariance_harness.py --corpus 2
```

Run a subset of transforms:

```bash
python evaluation/invariance_harness.py --corpus 1 --transforms permute,duplicate
```

Available: `permute`, `duplicate`, `distractor`, `query_lower`, `query_thanks`,
`query_polite`.

**Reading the output.** Every transform should print `0/78 decisions changed`.
Anything else is a defect — the transform cannot change the correct answer, so a
changed decision means the system depends on something it should not. The
`abstain -> answer` column is the dangerous direction.

---

## Security properties

```bash
# Injected text must never reach the LLM prompt
python evaluation/synthesis_containment_test.py

# 48 adversarial probes aimed at genuine knowledge gaps
python evaluation/adversarial_gap_probes.py --corpus 1
python evaluation/adversarial_gap_probes.py --corpus 2

# Fabricated passages must be rejected by provenance
python evaluation/fabricated_evidence_test.py --corpus 1
python evaluation/fabricated_evidence_test.py --corpus 2
```

**Reading these correctly.** Each prints a *control* line — the same questions
with no attack at all. **Compare against the control, not against zero.** If the
attacked and control numbers match, provenance is working and any leak is a
sufficiency bug, not a security failure. This distinction is exactly what
Corpus 1 shows today (see the note in [STATUS.md](STATUS.md)).

```bash
# Integrity of the injection-set hijack labels
python evaluation/label_audit.py
```

Only `adversarial_baseline_probe.py` needs LLM tokens — it runs external baseline
models for comparison and requires a key in `.env`.

---

## Diagnostics

Run these when investigating a specific failure, not routinely.

```bash
# Why did this question's sufficiency gate pass or fail?
python evaluation/coverage_leak_diag.py --corpus 2
python evaluation/overabstention_diag.py --corpus 1 --ids Q006,Q073

# How sensitive is conflict F1 to the NLI threshold?
python evaluation/threshold_sensitivity.py

# How sensitive is the system to the conflict rank gate? (now retired)
python evaluation/rank_gate_sweep.py

# Full pipeline with a real LLM writing answers (uses tokens)
python evaluation/live_end_to_end.py
```

---

## Tuning knobs

Every threshold is overridable by environment variable, so alternatives can be
measured without editing code:

```bash
RAG_MIN_CHUNK_SCORE_THRESHOLD=0 python evaluation/run_eval.py --corpus 1 --tag nofloor
```

| Variable | Default | What it controls |
|---|---|---|
| `RAG_MIN_CHUNK_SCORE_THRESHOLD` | `0.60` | Stage 3 absolute score floor (sufficiency path only) |
| `RAG_MIN_AVG_SCORE_FOR_SUFFICIENCY` | `0.65` | Stage 5 average-score branch |
| `RAG_MIN_QUERY_COVERAGE` | `0.55` | Stage 5 coverage branch |
| `RAG_MIN_CHUNKS_FOR_AVG_SUFFICIENCY` | `2` | minimum passages for the average branch to apply |
| `RAG_NLI_CONFLICT_THRESHOLD` | `0.94` | NLI contradiction confidence |
| `RAG_QUERY_SPAN_RELEVANCE` | `0.35` | Stage 4 query-intent gate |
| `RAG_ANCHOR_REQUIRE_BOTH` | `1` | anchor test: both sentences, or either |
| `RAG_MAX_CONFLICT_EVIDENCE_RANK` | `0` | **retired** — the old positional rank gate; `4` restores it |
| `RAG_KNEE_GAP_MULTIPLE` | `0` | off — discontinuity-based evidence cutoff |
| `RAG_RANK_TIE_EPSILON` | `0.005` | scores closer than this count as tied |

> **Before changing any of these, read Problem 3 in [STATUS.md](STATUS.md).**
> These constants have been tuned against the same 156 questions many times over.
> Moving one to fix a specific question is how this project has repeatedly
> produced changes that looked good on one corpus and failed on the other. If you
> do change one, check both corpora *and* the invariance harness.

---

## Unit tests

```bash
python -m pytest tests/
```
