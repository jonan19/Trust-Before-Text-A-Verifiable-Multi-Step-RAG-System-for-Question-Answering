# Corpus 3 (ContractNLI) — Sealed Test Results

**Status:** Track A, Track B, and all three baseline arms are complete and final
(sealed test set, opened once). Two supplementary runs — the phrasing-variant
(qform) benchmark and the bare-LLM baseline — are in progress and are reported
separately in §6 once they land. Nothing below is provisional; nothing below
has been re-run.

**Governance:** Config frozen per `docs/PREREGISTRATION_CORPUS3.md`, frozen
2026-08-25, amended 2026-08-28. No `RAG_*` overrides. The 30 test bundles were
opened exactly once, on 2026-08-31, after Phase 1 debugging was completed
entirely on the separate 15-bundle dev split.

---

## 1. What Corpus 3 is

ContractNLI (Koreeda & Manning, EMNLP Findings 2021) — 123 real NDAs, none
authored by this project, each annotated by ContractNLI's own annotators against
17 fixed legal hypotheses (`Entailment` / `Contradiction` / `NotMentioned`), with
gold evidence character spans.

Four documents are bundled per store (`random.seed(0)`, K=4, sorted document
ids). Because ContractNLI's `Contradiction` label is *hypothesis-vs-document*,
bundling converts it into the *document-vs-document* self-contradiction this
project's Stage 4 is built to catch: if annotators marked one bundled document
`Entailment` and another `Contradiction` on the same hypothesis, those two
documents genuinely disagree, certified by people who never saw this system.

| Rule (per bundle × hypothesis) | Gold decision |
|---|---|
| ≥1 document `Entailment` **and** ≥1 document `Contradiction` | `conflict` |
| all 4 documents `NotMentioned` | `insufficient` |
| otherwise | `answer` |

Two query tracks run over the same 30 sealed test bundles:

- **Track A** — the 17 hypotheses verbatim. 30 bundles × 17 = 510 queries.
  Zero authorship by this project; maximum held-out-ness.
- **Track B** — free-form questions written by an LLM with no context of this
  project, its code, or its outputs (see Amendment 1 of the pre-registration).
  30 bundles × 8 = 240 queries, own gold labels and quoted evidence.

---

## 2. Track A — fixed hypotheses (510 queries, primary benchmark)

| Metric | Value | 95% CI (bundle-cluster bootstrap, n=2000) |
|---|---|---|
| Accuracy | **26.7%** (136/510) | [22.5%, 31.0%] |
| Always-answer floor | 77.6% (396/510 gold = `answer`) | — |
| Conflict precision | 0.122 (47/386 flagged) | [0.096, 0.149] |
| Conflict recall | 0.635 (47/74 true conflicts) | [0.554, 0.726] |
| Conflict F1 | 0.204 | [0.166, 0.242] |
| Attribution precision (internal gold) | 0.031 (12/386) | [0.016, 0.049] |
| Gap leaks | 3 / 40 insufficient-gold queries | — |
| Unsafe answers | 29 / 114 conflict-relevant decisions | — |

**Gold distribution:** 396 `answer`, 74 `conflict`, 40 `insufficient`.

**Per-bundle accuracy (30 independent samples of the same pipeline):**
min 5.9%, median 23.5%, max 58.8%. No bundle reaches the always-answer floor.

---

## 3. Track A — externally graded evidence attribution

Graded against ContractNLI's own annotator character spans — labels this
project did not write. This is the first externally-validated attribution
result the project has.

| Metric | Value |
|---|---|
| Evidence recall | 68.5% (1612/2355 gold spans covered) |
| Evidence precision | 14.8% (1875/12,637 cited chunks on-span) |
| **External attribution precision (primary metric)** | **0.0% (0/350 conflict reports)** |
| Unresolved chunks | 1.67% (215/12,852) — below the 5% integrity threshold |
| Unresolved conflict spans | 19 |

Every single `conflict` decision that cited two spans, checked against
ContractNLI's own annotator spans in the two named documents, failed. Of a
40-case detail sample: 34/40 are conflicts fired on a query where gold expected
no conflict at all (a real, sourced pair, wrong question); 3/40 wrong pair
entirely; 3/40 correct pair, span outside ContractNLI's annotated evidence.

---

## 4. Track B — LLM-authored open queries (240 queries)

Same 30 sealed documents, independently generated wording and gold labels, not
seen by this project during system development.

| Metric | Value |
|---|---|
| Accuracy | **40.4%** (97/240) |
| Always-answer floor | 48.8% (117/240 gold = `answer`) |
| Conflict precision | 0.175 (10/57 flagged) |
| Conflict recall | 0.159 (10/63 true conflicts) |
| Conflict F1 | 0.167 |
| Attribution precision (internal gold) | 0.018 (1/57) |
| Gap leaks | 18 / 60 insufficient-gold queries |
| Unsafe answers | 65 / 123 conflict-relevant decisions (53%) |

**Gold distribution:** 117 `answer`, 63 `conflict`, 60 `insufficient`.

Track B's gold mix has a much larger conflict/insufficient share by design
(author quota), which is why its floor (48.8%) is lower than Track A's (77.6%)
— the two accuracy numbers are not directly comparable without their floors,
which is why both are always reported side by side.

---

## 5. Baseline arms (Track A queries, 510)

Reused retrieval, no LLM cost, decision policy only.

| Arm | Accuracy | vs floor | Conflict P/R | Gap leaks | Unsafe |
|---|---|---|---|---|---|
| **always_answer** | 77.6% | = floor | 0.0 / 0.0 | 40/40 | 114/114 |
| **always_abstain** | 7.8% | −69.8 pts | 0.0 / 0.0 | 0/40 | 0/114 |
| **retrieval_threshold** (top-chunk score ≥ 0.6, no validation) | 77.6% | = floor | 0.0 / 0.0 | 40/40 | 114/114 |

`retrieval_threshold` is inert on this corpus: every query's top chunk clears
the threshold, so this arm is behaviourally identical to always-answer. It
establishes that raw retrieval confidence carries zero signal for this task —
whatever discriminative work happens, happens downstream in validation, not in
retrieval.

**Reading the system's 26.7% against these floors:** the deterministic
validation layer scores *below* a policy that reads nothing and always answers.
That is the central number this evaluation exists to surface.

---

## 6. Supplementary runs — in progress, reported when complete

| Run | Purpose | Status at time of writing |
|---|---|---|
| **qform** (510 queries, frozen interrogative rewrites of the same 17 hypotheses, same gold) | Isolates whether outcome is sensitive to *phrasing* independent of topic, holding proposition and gold fixed | 22/30 bundles |
| **Bare-LLM baseline** (510 queries, `openai/gpt-oss-120b`, same retrieved evidence, no validation layer) | Carries the safety comparison: same evidence, decision made by an LLM alone vs. by the deterministic pipeline. Model substituted for the original `llama-3.3-70b-versatile`, which Groq has since decommissioned; disclosed in `evaluation/llm_baseline_corpus3.py` | 12/30 bundles, 0–11 errors per bundle (excluded from scoring, not guessed at) |
| **Track B evidence attribution** | Same external-grading logic as §3, applied to Track B's author-quoted spans | Not yet run |

This document will be updated in place once these land; no number above will
change retroactively.

---

## 7. Source files

- `evaluation/results/c3_hypothesis_corpus3_test.json` — Track A raw results
- `evaluation/results/c3_hypothesis_corpus3_test_attribution.json` — Track A span grading
- `evaluation/results/c3_hypothesis_corpus3_test_ci.json` — bootstrap intervals
- `evaluation/results/c3_open_corpus3_test.json` — Track B raw results
- `evaluation/results/c3_baselines_corpus3_test.json` — baseline arms
- `docs/PREREGISTRATION_CORPUS3.md` — frozen config, taxonomy, predictions
