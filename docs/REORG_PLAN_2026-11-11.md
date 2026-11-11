# Repository Reorganization Plan (draft, 2026-11-11)

Written in response to "too many files, not properly organized". **Nothing here
is approved or implemented.** No file has been moved, deleted or edited.

Read with `claude.md` (Development Principles: one architectural change at a
time, minimal diffs) and `docs/STATUS.md`.

---

## 1. What the survey actually found

Measured, not estimated:

| | Value |
|---|---|
| Tracked files | 793 |
| Packed git size | 1.74 MiB (`.git` 8.5 MB) |
| `.env` in history | never committed |
| Tracked files that are corpus fixtures | 544 of 793 (`data_corpus3/` 421, `track_b_handoff/` 123) |
| Root-level Python modules | 14, flat, no package |
| Root-level `data_*` + `qdrant_db_*` directories | 16 |
| Files containing a `sys.path` manipulation | 43 |
| Files importing `validation` | 40 |

**The file count is not the problem.** 69% of tracked files are corpus text
fixtures that belong in the repo, and the repo is small. Three things are the
problem: duplicated content, a flat root, and four homes for experiment code.

Two duplications are confirmed by byte comparison, not inferred:

- All 120 `.txt` files under `track_b_handoff/` are **byte-identical** to files
  already in `data_corpus3/` (checked pairwise: 120 identical, 0 differing,
  0 absent from `data_corpus3/`).
- `CORPUS3_AUTHORING_PROTOCOL.md` exists **four** times: once in `docs/` and
  once per author under `track_b_handoff/`.
- `RAG_System_Observation_Log.md` exists twice: 134 KB at root, 73 KB in
  `docs/archive/`.

## 2. What must not be touched, and why

These are the findings that changed the recommendation. Each is a cost that is
invisible until you look.

**2a. `docs/NUMBERS_LEDGER.csv` hardcodes corpus paths.** Its `source` column
holds expressions such as a `V('data/ground_truth.json', ...)` lookup, which
`evaluation/check_ledger.py` evaluates against the repo root to verify every
number in `main.tex`. There are 27 such path references. Renaming `data/` to
`corpora/corpus1/` breaks the one mechanism that guarantees the paper's numbers.

**2b. Preregistration documents cite literal paths.** `docs/REPRODUCE.md` (4
references) and `docs/PREREGISTRATION_MULTIHOP.md` (3) name corpus directories
in commands. Preregistrations are immutable records of what was committed to
before a sealed run; editing them to chase a rename devalues them.

**2c. `evaluation/` depends on flat sibling imports.** Ten scripts import
`harness_bootstrap` purely for its side effect of adding that directory to
`sys.path`, and eight insert `ROOT / "experiments"` themselves. Grouping the
50-odd scripts into subfolders breaks this idiom in every one of them.

**2d. `evaluation/README.md` already indexes those scripts** (113 lines, with a
"routine suite" table). The directory is documented, so it reads as flat only
to someone who skips the README. Correcting my earlier framing: the fix here is
a better index, not file movement.

**2e. `src/` is the most expensive move available.** 40 files import
`validation`, 23 import `qdrant_retrieval`, 19 import `retrieval_interface`, and
43 files already carry `sys.path` repair code. A package move touches all of
them and cannot be verified by the test suite alone.

**2f. `paper_assets/` must stay.** `main.tex` references it 8 times for the
figures. Only the stale `.tex` and duplicate `.bib` inside it are in question.

## 3. The plan

Four phases, smallest blast radius first, **each its own commit**. Phases 1 and
2 are recommended. Phase 3 is optional. Phase 4 is recommended against for now.

### Phase 0: safety net (no changes)

1. Branch from `jonan`.
2. Record the baseline: run the `tests/` suite under pytest, and
   `evaluation/check_ledger.py` verbosely. Both must be green **before** any
   change, so a later failure is attributable.
3. Commit nothing. If either is already red, stop and report.

### Phase 1: deletions and dedup (zero code impact)

Nothing in this phase is referenced by any tracked `.py` file. Verified: a
`git grep` for `track_b_handoff` across Python files returns nothing, and
`evaluation/ingest_track_b.py` reads `corpus3_queries_combined.json` and writes
to `data_corpus3/`, never the handoff folder.

1. **Replace `track_b_handoff/` with a manifest.** The folder is the *outbound*
   packet: the NDAs each author was given plus the instructions. It contains no
   authored output; the questions came back as `corpus3_queries_combined.json`.
   Its only unique information is the bundle assignment, which is preserved in
   full by a new `docs/CORPUS3_TRACK_B_ASSIGNMENT.md`:

   | Author | Bundles |
   |---|---|
   | Anish | `test-b00` to `test-b09` |
   | Kaustubh | `test-b10` to `test-b19` |
   | Jonan | `test-b20` to `test-b29` |

   Net: **123 tracked files become 1.** Provenance for Standing Decision 3
   (questions authored by someone else) is strengthened, not lost, because the
   assignment moves from a folder layout into a stated record. Git history
   retains the originals either way.

2. **Delete `experimental/`.** It contains only an empty `__init__.py`. Confirm
   no module imports it first; delete only if that comes back empty.

3. **Reconcile the two observation logs.** The root file is current and
   governed by `claude.md`; the `docs/archive/` copy is a 73 KB older snapshot.
   Keep the root file as the live log. Either delete the archived copy or
   rename it `docs/archive/RAG_System_Observation_Log_pre-2026-08.md` so the
   name itself says it is frozen. Recommend the rename: it is an archive.

4. **Retire the stale paper source.** `paper_assets/trust_before_text.tex` is
   the frozen v6 draft (`docs/archive/STATUS.md` confirms; the observation log
   notes it still quotes v6 figures: 92.3%, 66.7%, unsafe 4/32). `main.tex` is
   live at 2,455 lines. Move it and the diverging `paper_assets/references.bib`
   to `paper_assets/archive/` with a one-line `README.md` saying `main.tex` and
   root `references.bib` are canonical. Do not delete: it is the submitted
   draft.

5. **Ignore the build outputs** now loose at root: `Project_Report.pdf`,
   `overleaf_bundle.zip`. Both are generated. Add to `.gitignore` beside the
   existing `Trust_Before_Text_NLPIR.pdf` entry.

**Verification:** re-run Phase 0's two commands. Expect identical output. No
import path changes, so any difference is a real regression.

### Phase 2: make the root legible without moving code

> **Status 2026-11-11: items 2, 3 and 4 done. Item 1 (the `paper/` move) is NOT
> done and is on hold.** Two reasons, both found when the work started.
> (a) `main.tex` and `references.bib` have uncommitted edits belonging to
> another session, and moving a file someone is mid-edit on entangles their work
> with the move. (b) The estimate below was wrong: `--sync-lines` fixes line
> numbers, not the `file` column, and **450 ledger rows carry `main.tex` there**,
> while `check_ledger.py` hardcodes `PAPER = "main.tex"` (line 68) and lists it
> in `STALE_FILES` (line 80). So the move needs a code change to the verifier
> itself, not just a data edit. See Observation 65.

The root's problem is that the pipeline, the paper and the ledger are
indistinguishable. This is fixable by documentation and three safe moves.

1. **Move the paper sources into `paper/`**: `main.tex` and `references.bib`.
   Cost is known and bounded: `docs/NUMBERS_LEDGER.csv` has a `file` column
   whose value is `main.tex`, and `check_ledger.py` supports `--sync-lines`.
   This is the one rename with a built-in migration path.
   **Open question for the owner: `numbers.md` is cited across many documents
   and is the number-of-record. Recommend leaving it at root** rather than
   moving it with the paper sources.
2. **Move `corpus3_queries_combined.json` (244 KB) into `data_corpus3/`** as the
   delivered source it is. One reference to update:
   `evaluation/ingest_track_b.py:32`.
3. **Add a root `ARCHITECTURE.md`** mapping the nine pipeline stages in
   `claude.md` onto the 14 root modules, so the flat layout becomes navigable
   without being restructured. This buys most of the benefit of `src/` for none
   of the risk.
4. **Extend `evaluation/README.md`** to group all scripts as runners, harnesses,
   labs and one-off diagnostics. Per 2c and 2d, group them *in the index*, not
   on disk.

**Verification:** both Phase 0 commands, plus `check_ledger.py --sync-lines -v`
after the `main.tex` move, per the numbers-ledger workflow.

### Phase 3: optional, merge the two experiment folders

`experiments_corpus2/` holds 9 files that are Corpus-2 variants of scripts in
`experiments/` (30 files). Merging them into `experiments/` as `*_corpus2.py`
siblings removes one root directory. Cost: 8 files hardcode an insertion of
`ROOT / "experiments"` into `sys.path`, and these are **frozen paper
experiments**, so touching them risks the reproducibility of published numbers
for cosmetic gain. Recommend deferring unless the root entry count matters more
than that.

### Phase 4: recommended against for now

- **`corpora/` + `indexes/` consolidation.** Correcting my earlier suggestion:
  per 2a and 2b, this breaks 27 ledger path expressions and edits
  preregistration records. The 16 directories are ugly but centrally registered
  in `evaluation/harness.py` (`CORPORA`, line 46), which is the thing that
  actually matters for maintenance. The suffix naming is a cosmetic wart
  protecting a working guarantee. **Leave it.**
- **`src/` package move.** See 2e. Do not attempt without an external reason.
- **Splitting `validation.py` (2,288 lines).** Highest-value and highest-risk
  structural work in the repo, and it is a *code* change, not an organization
  change. Must be its own project, after Phases 1 and 2, never in the same
  commit as a move.

## 4. Expected result

| | Before | After Phases 1 and 2 |
|---|---|---|
| Tracked files | 793 | ~669 |
| Root directories | 24 | 23 (`experimental/` gone, `paper/` added) |
| Loose root files | 22 | ~18 |
| Duplicated corpus files | 120 | 0 |
| Copies of the authoring protocol | 4 | 1 |
| Ambiguous paper sources | 2 | 1 |
| Import paths changed | | 1 (`ingest_track_b.py:32`) |

## 5. Regressions to watch

1. **`check_ledger.py` line drift** after the `main.tex` move. Mitigated by
   `--sync-lines`; must be run in the same commit.
2. **`tests/test_run_eval_multihop.py:58`** asserts a literal set of store
   names. Untouched by this plan; a tripwire if Phase 4 is ever attempted.
3. **Case-only rename risk.** `claude.md` is tracked lowercase on a
   case-insensitive filesystem. Do not "fix" it to `CLAUDE.md` as part of a
   bulk move: it needs a forced `git mv` in a commit of its own, or it will
   silently not apply.
4. **Deleting the handoff folder is irreversible outside git.** Confirm the
   manifest is committed in the same change.
5. `.gitignore` currently ends with `data_uploads/`. New entries must not land
   inside the commented block structure in a way that changes an existing rule.

## 6. Logging

Per `claude.md`, after any phase is implemented: append an issue/cause/fix/effect
entry to `RAG_System_Observation_Log.md`. No number changes, so `numbers.md`
needs no update, unless the `main.tex` move changes ledger line numbers, in
which case the ledger is updated first.
