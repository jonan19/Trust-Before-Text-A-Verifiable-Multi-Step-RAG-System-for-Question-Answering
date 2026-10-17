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

**Reading the output.** The four structural transforms (`permute`, `duplicate`,
`distractor`, `query_lower`) should print `0/78 decisions changed`. The current
files show `query_thanks` at 1/78 (Corpus 1) and 2/78 (Corpus 2) and
`query_polite` at 0/78, none in the unsafe direction (`docs/STATUS.md`). Until
2026-10-17 this paragraph said every transform should print 0/78, which the
politeness transforms have never done. Any change is a defect — the transform cannot change the correct answer, so a
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

## External benchmarks (sealed: re-grade only)

RAMDocs and MultiHop-RAG are sealed. Do not re-run them to tune or validate a
change; the commands below are the record of how the numbers in
`numbers.md` sections 4 and 4b were made. `--report` re-grades the stored
answers with no LLM call and no API key.

```bash
# RAMDocs clean rerun (four runs; the full runs need Groq keys)
python evaluation/run_eval_ramdocs_clean.py --arm ours --order original --tag rdc_ours_orig --rotate-keys
python evaluation/run_eval_ramdocs_clean.py --arm baseline --order original --tag rdc_base_orig --rotate-keys
python evaluation/run_eval_ramdocs_clean.py --arm ours --order shuffled --tag rdc_ours_shuf --rotate-keys
python evaluation/run_eval_ramdocs_clean.py --arm baseline --order shuffled --tag rdc_base_shuf --rotate-keys
python evaluation/run_eval_ramdocs_clean.py --report --tag rdc_ours_orig

# MultiHop-RAG (ours needs no LLM; the baseline needs Groq keys)
python evaluation/run_eval_multihop.py --prepare
python evaluation/run_eval_multihop.py --arm ours --tag mh
python evaluation/run_eval_multihop.py --arm baseline --tag mh --rotate-keys
python evaluation/run_eval_multihop.py --report --tag mh
```

The old `evaluation/run_eval_ramdocs.py` is the label-leaky runner behind the
superseded 88.4% figure; do not use it.

## Checking every number against its source

```bash
python evaluation/check_ledger.py -v
```

Read-only, no API key. Checks every row of `docs/NUMBERS_LEDGER.csv` against
the result files and the documents that quote it; exits non-zero on any
mismatch. After editing a number in a document, run it with `--sync-lines`.

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

# Does a query-conditioned ANSWERHOOD cross-encoder separate Stage 4's true
# conflict pairs from its false ones? Offline, no live-code changes; downloads
# cross-encoder/ms-marco-MiniLM-L-6-v2 on first use. Shipped as ANSWERHOOD_MARGIN
# (default 5.5) — see STATUS.md Problem 1.
python evaluation/answerhood_lab.py --corpus 1 --corpus 2

# Re-verify the shipped ANSWERHOOD_MARGIN gate doesn't break invariance
# (already run and clean at delta=5.5, both corpora — evaluation/results/
# invariance_corpus{1,2}.json)
RAG_ANSWERHOOD_MARGIN=5.5 python evaluation/invariance_harness.py --corpus 1
RAG_ANSWERHOOD_MARGIN=5.5 python evaluation/invariance_harness.py --corpus 2

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
| `RAG_MIN_FOCUS_PRESENCE` | `0.5` | Stage 5 H5: fraction of the question's focus terms that must appear in the evidence; `0` restores pre-fix behaviour (see STATUS.md Problem 2) |
| `RAG_NLI_CONFLICT_THRESHOLD` | `0.94` | NLI contradiction confidence |
| `RAG_QUERY_SPAN_RELEVANCE` | `0.35` | Stage 4 query-intent gate (bi-encoder topicality) |
| `RAG_ANSWERHOOD_MARGIN` | `5.5` | Stage 4 cross-encoder answerhood gate; **shipped 2026-08-24** (closes 7/9 Corpus-2 false conflicts, invariance-checked clean), see STATUS.md Problem 1; `0` restores prior (gate-off) behaviour |
| `RAG_ANCHOR_REQUIRE_BOTH` | `1` | anchor test: both sentences, or either |
| `RAG_ANCHOR_ASYMMETRIC_QSPAN` | `0` | off — anchor-rescue candidate for Q045; shipped disabled, costs Corpus 2 precision (see STATUS.md Problem 1) |
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

169 fast tests as of 2026-10-17 (70 on 2026-10-10; the ledger, key-pool, RAMDocs and
MultiHop-RAG runners added the rest) (about a minute, nearly all of it importing the ML libraries; no
model is loaded, no vector store is touched, no LLM is called). They cover the
mechanism, not the corpus behaviour: the provenance fingerprint and Stage 0
rejection of fabricated evidence, the abstention truth table, the absence of any
LLM import in `validation.py`, numeric-contradiction rules, de-duplication, the
sparse encoder, rank fusion and score calibration, the run-provenance stamp, and
the re-run runner's comparison logic (it must never report a false MATCH).
Accuracy and safety on the two corpora are measured by the harnesses above, not
by `pytest`.

---

## Re-run everything and compare (one command)

```bash
python evaluation/rerun_suite.py            # start or resume; zero LLM tokens
python evaluation/rerun_suite.py --status   # progress
```

Runs setup, both corpora (gate on and gate off), invariance, containment, gap
probes, fabricated evidence, the label audit and `pytest` in order, saves every
step's log under `evaluation/results/rerun_<date>/`, then compares **every**
printed headline number with `evaluation/expected_baseline.json` (the
machine-readable copy of `numbers.md` section 2). Read `RERUN_SUMMARY.md` in
the run folder: it ends with "N MATCH, M DIFF, K missing or stale". A file that
this run did not write counts as stale, never as a match. The process exits
non-zero on any failed step, DIFF or missing file, and refuses to start if a
`RAG_*` variable is set in the shell. It is resumable: relaunch the same command
after a crash. Never run it alongside another harness (one process per Qdrant
store).

**Every result file records which system made it.** Each harness output now
carries a `run_info` block (UTC time, git commit and branch, whether tracked
files were modified, SHA-256 of `validation.py` and `qdrant_retrieval.py`, every
effective switch, and any `RAG_*` overrides; see `evaluation/run_info.py`). Use
it to answer "what produced this number?" instead of guessing; files written
before 2026-10-10 have no such block.
