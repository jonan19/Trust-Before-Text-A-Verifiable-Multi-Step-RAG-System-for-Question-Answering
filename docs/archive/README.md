# Archive — historical records, NOT current documentation

> ## ⚠️ Do not use anything in this folder as a reference for how the system works today.
>
> Every file here contains **superseded numbers**. Several of them describe
> thresholds and behaviours that no longer exist in the code.
>
> **Current documentation is three files:**
> [../../README.md](../../README.md) →
> [../HOW_IT_WORKS.md](../HOW_IT_WORKS.md) →
> [../STATUS.md](../STATUS.md) →
> [../REPRODUCE.md](../REPRODUCE.md)

These files are kept for one reason: they are the audit trail behind the paper.
Each rejected design candidate is recorded with the measurement that falsified
it, which is worth preserving — reviewers ask "did you try X?", and the answer
is usually "yes, and here is the number that killed it".

---

## What each file was

### Research narrative

| File | What it is | Why superseded |
|---|---|---|
| **FIXES_REPORT.md** | The most useful file here. Blow-by-blow record of three rounds of work on the six original limitations, including **every rejected candidate with the number that falsified it**. | Numbers predate the chunking fix and the Stage-4 rework. |
| **LIMITATIONS_STATUS.md** | Maps each limitation in the paper's Section IX to its measured status. | Replaced by [../STATUS.md](../STATUS.md). Its central claim — that false conflicts are purely a task-formulation problem — was later shown to be partly wrong: a large share was caused by a chunking bug, boilerplate comparison, and NLI being fed the wrong granularity. |
| **ROADMAP.md** | Working log of the August 2026 session: the chunking-bug discovery, the rank-gate and score-floor investigations, the invariance harness, and the conflict-layer rework. | Its conclusions are folded into [../STATUS.md](../STATUS.md). |

### Paper experiments (frozen)

| File | What it is |
|---|---|
| **MASTER_REPORT.md** | Source of truth for experiments E1–E5 as cited in the paper. Do not re-run these; the raw JSON in `experiments/` is frozen alongside it. |
| **CORPUS2_REPORT.md** | The original Corpus 2 transfer study — the first evidence that calibrated thresholds did not generalise. |
| **experiment_summaries/** | Per-experiment summaries: baseline, haystack, injection, hardening, adaptive attack. |

### Project history

| File | What it is |
|---|---|
| **STATUS.md** | The old three-chat coordination dashboard. Badly stale — it describes the system as "frozen at v6" and instructs against re-running experiments. Kept only for the decision history it records. |
| **RAG_System_Observation_Log.md** | 73 KB development log. |
| **Report 1.md**, **Report 2.md** | Early project reports. |
| **phase5_verification_report.md**, **phase6_spotrun_report.md** | Verification runs from earlier development phases. |

---

## Three specific things in here that are now known to be wrong

Recorded so nobody rediscovers them the hard way:

1. **"Every error is a safe error."** Never true on Corpus 2, and not true on
   Corpus 1 today. The current unsafe counts are in [../STATUS.md](../STATUS.md).

2. **"The faithfulness signal is too weak to separate legitimate from injected
   sentences (median 0.007)."** A measurement artifact — the system's own CAUTION
   banner was being scored as answer content. On clean sentences the same model
   scores 0.9938 vs 0.0007. Corrected within `FIXES_REPORT.md` itself, but the
   original claim appears earlier in that file.

3. **"The defended LLM baseline was hijacked 0/45 times."** Produced by a grading
   bug that marked an answer safe whenever the true value appeared anywhere, even
   when the answer then asserted the attacker's value as its conclusion. Corrected
   figure is **7/45**, hand-adjudicated. Anyone citing baseline synthesis numbers
   must use the corrected one.
