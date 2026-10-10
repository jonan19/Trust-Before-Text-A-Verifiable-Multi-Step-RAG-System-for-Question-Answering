# HARD TEST 1 — Scale / Buried-Conflict: conflict recall vs. haystack size N

*Model:* `llama-3.3-70b-versatile`, temperature 0, one call per haystack. *Ours:* `validation.validate` / `find_conflict`, frozen thresholds, uniform chunk score=relevance=0.85 (so Stage-3 filtering drops nothing — `relevant_count` == N on every haystack). Both systems receive the **identical ordered chunk set**. 4 conflicts × 5 N × 5 draws = 100 haystacks.

**Recall criterion.** Ours: flagged a conflict AND reported the correct planted document pair. LLM: replied CONFLICT AND named both differing values.

## Aggregate (all 4 conflicts)

| N | ours recall | ours flag-any | ours masked-wrong-pair | LLM recall | LLM answered |
|---|---|---|---|---|---|
| 2 | 0.75 | 0.75 | 0.00 | 1.00 | 0.00 |
| 5 | 0.75 | 0.80 | 0.05 | 1.00 | 0.00 |
| 10 | 0.70 | 0.85 | 0.15 | 0.85 | 0.10 |
| 20 | 0.60 | 1.00 | 0.40 | 0.85 | 0.10 |
| 40 | 0.50 | 1.00 | 0.50 | 0.75 | 0.20 |

## Per-conflict

### C1 probation (3 vs 6 mo, numeric) — planted pair detectable by our detector in isolation: **YES**

| N | ours recall | ours flag-any | ours masked-wrong-pair | LLM recall | LLM answered |
|---|---|---|---|---|---|
| 2 | 1.00 | 1.00 | 0.00 | 1.00 | 0.00 |
| 5 | 1.00 | 1.00 | 0.00 | 1.00 | 0.00 |
| 10 | 1.00 | 1.00 | 0.00 | 1.00 | 0.00 |
| 20 | 0.80 | 1.00 | 0.20 | 1.00 | 0.00 |
| 40 | 0.80 | 1.00 | 0.20 | 1.00 | 0.00 |

### C2 remote (3 vs 2 d/wk, numeric) — planted pair detectable by our detector in isolation: **YES**

| N | ours recall | ours flag-any | ours masked-wrong-pair | LLM recall | LLM answered |
|---|---|---|---|---|---|
| 2 | 1.00 | 1.00 | 0.00 | 1.00 | 0.00 |
| 5 | 1.00 | 1.00 | 0.00 | 1.00 | 0.00 |
| 10 | 0.80 | 1.00 | 0.20 | 1.00 | 0.00 |
| 20 | 0.60 | 1.00 | 0.40 | 1.00 | 0.00 |
| 40 | 0.20 | 1.00 | 0.80 | 1.00 | 0.00 |

### C3 pension (6% vs 5%, numeric) — planted pair detectable by our detector in isolation: **YES**

| N | ours recall | ours flag-any | ours masked-wrong-pair | LLM recall | LLM answered |
|---|---|---|---|---|---|
| 2 | 1.00 | 1.00 | 0.00 | 1.00 | 0.00 |
| 5 | 1.00 | 1.00 | 0.00 | 1.00 | 0.00 |
| 10 | 1.00 | 1.00 | 0.00 | 1.00 | 0.00 |
| 20 | 1.00 | 1.00 | 0.00 | 1.00 | 0.00 |
| 40 | 1.00 | 1.00 | 0.00 | 1.00 | 0.00 |

### C4 device (permit vs prohibit, semantic) — planted pair detectable by our detector in isolation: **NO**

| N | ours recall | ours flag-any | ours masked-wrong-pair | LLM recall | LLM answered |
|---|---|---|---|---|---|
| 2 | 0.00 | 0.00 | 0.00 | 1.00 | 0.00 |
| 5 | 0.00 | 0.20 | 0.20 | 1.00 | 0.00 |
| 10 | 0.00 | 0.40 | 0.40 | 0.40 | 0.40 |
| 20 | 0.00 | 1.00 | 1.00 | 0.40 | 0.40 |
| 40 | 0.00 | 1.00 | 1.00 | 0.00 | 0.80 |

## Honest findings

**The win condition was NOT met.** The hypothesis — the LLM's conflict recall degrades as N grows while ours stays flat — is not supported. In aggregate and on 3 of 4 conflicts it is closer to the reverse.

1. **On the three numeric conflicts (C1, C2, C3) the LLM did not degrade at all** — it reported "3 vs 6 months", "3 vs 2 days", "6% vs 5%" correctly at every N up to 40, even buried in the middle. A clear numeric contradiction is not lost in a 40-chunk context.
2. **Our system degraded on two of them (C1, C2) as N grew** — not because it fails to *find* the pair (it detects all three in isolation), but because `find_conflict` returns the **first** contradictory pair, and as distractors multiply, an NLI *false* conflict between two unrelated distractors increasingly fires first and **masks** the real pair. Masking rose with N (C2: 0% → 80% wrong-pair from N=2 to N=40; C1: 0% → 20%). This is Limitation 1 (irrelevant-pair NLI misfires) scaling with corpus size — a genuine weakness of the current design under many documents.
3. **The one place the LLM degraded is the subtle *semantic* conflict (C4, permitted vs prohibited): recall 1.00 at N≤5 → 0.40 at N=10–20 → 0.00 at N=40, answering one side ("permitted") 80% of the time at N=40** — the classic lost-in-the-middle failure, and an *unsafe* one (a confident one-sided answer on a conflicted question). But our system does not win here either: it detects C4 at **no** N.
4. **C4 exposes a frozen-detector recall gap.** In isolation the NLI model scores this contradiction 0.9999 (far above the 0.94 threshold), yet `find_conflict` skips it: the two query-scoped spans have lexical similarity 0.1483, just below `NLI_SIM_FLOOR` (0.15), so the NLI check is never run. This performance guard barely blocks a real semantic conflict when the two spans differ sharply in length. (The full pipeline caught this conflict in the 78-query eval; the difference is chunk-boundary / span-length sensitivity, not the query.)

**Bottom line for the author.** "Many documents" is not, by itself, a stress condition where the current system wins. On clear conflicts the LLM is robust to N=40 while our conflict-*attribution* precision degrades with N (distractor masking); on the one conflict where the LLM breaks (semantic, high N), our detector misses it outright. The safety asymmetry still partly favors us — when we fail we mostly abstain (mis-named pair) rather than emit a one-sided answer, whereas the LLM's C4 failure is a confident wrong answer — but that is a different claim than the one this test set out to make, and C4 at low N (where we detect nothing and would answer) is not clean. The real, reportable results here are (a) distractor-masking makes our conflict *reporting* degrade with N, and (b) `NLI_SIM_FLOOR` can suppress a genuine high-confidence semantic conflict — both concrete, fixable limitations, neither of which is 'we beat the LLM at scale'.
