# Pre-registration — Corpus 3 (ContractNLI)

**Status: FROZEN 2026-08-25. AMENDED 2026-08-28, before the test run.**
Everything below was fixed as of the freeze; changing any of it after the test
split is opened invalidates the held-out claim and must be disclosed rather
than quietly amended. See Section 8 for the freeze record.

> ## AMENDMENT 1 (2026-08-28) — Track B is LLM-authored, not human-authored
>
> Recorded **before** the sealed test split was run, per the disclosure clause
> above. Nothing else in this document was changed.
>
> The frozen text below (and `CORPUS3_AUTHORING_PROTOCOL.md`) specifies Track B
> as authored by three named humans working blind. **That is not what was
> delivered.** `corpus3_queries_combined.json` (240 questions, 30 bundles × 8)
> is LLM-generated. Its own `_meta` block reads *"DRAFT for human review …
> Generated question-by-question against the four NDAs in each bundle"*, and
> the `author` field is empty on all 30 bundles. No human review or relabelling
> was performed before the run.
>
> The authoring model had **no context of this project** — it never saw this
> system, its code, its outputs, `CLAUDE.md`, `docs/STATUS.md`, or this
> pre-registration. So the strongest leakage channel (questions written to
> flatter or trip a known implementation) is genuinely absent.
>
> **Correction (same day, before the run).** An earlier draft of this amendment
> claimed the authoring model was biased by reading all four NDAs at once, and
> cited Track B's 26.2% gold-`conflict` share (against Track A's 14.5%) as
> evidence. **Both halves of that claim were wrong and are withdrawn.**
>
> Simultaneous access to all four documents is not an LLM-specific advantage:
> `CORPUS3_AUTHORING_PROTOCOL.md` hands each human author the same four files
> at once, and further *instructs* them to spend 2 of 8 questions on cases where
> "the documents disagree". A human following the protocol would search for
> conflicts the same way.
>
> The class mix is the quota, not a bias signature. The protocol's quota implies
> a 25.0% conflict share; the observed share is 26.2%. 27 of 30 bundles are
> exactly (4 answer, 2 conflict, 2 insufficient) — the quota with the free slot
> spent on `answer`; the other 3 spent it on `conflict`. Track A's lower 14.5%
> is simply what ContractNLI's label distribution yields under the bundling
> rule, and carries no quota at all. The two shares are not comparable and their
> difference is not evidence of anything.
>
> **What remains a genuine limitation.** Not the document visibility, but the
> authorship itself: these questions were not written by a person, so Track B
> does not test whether the system handles the phrasing, vagueness, and
> under-specification of real human questions — which was Track B's entire
> purpose. Whether an LLM's "natural" phrasing differs from a human's in ways
> that matter here is **untested and unknown**, not assumed in either direction.
> The conflict class carries the additional caveat that a quota-driven author of
> any kind is hunting for disagreement, so the conflict share is a design
> parameter and must never be read as a base rate.
>
> **Consequences, binding:**
>
> 1. **Track A remains the primary result.** Its labels are Koreeda & Manning's,
>    authored years before this project existed — genuinely third-party. Track B
>    is a clearly-labelled secondary arm.
> 2. Track B must never be described as "independently authored", "blind", or
>    "human-authored". The accurate phrasing is: *"open-form questions generated
>    by a language model with no knowledge of the system under test, with full
>    simultaneous visibility of each document bundle."*
> 3. The three-human blind protocol remains **unexecuted** and stays open as
>    future work. `CORPUS3_AUTHORING_PROTOCOL.md` is retained unchanged for that
>    purpose.
> 4. Predictions in Section 6 were registered against the dev split and are
>    unaffected by this amendment.

---

## 1. Why this document exists

`claude.md` Research Governance opens with one fact: **there is no held-out
data.** Corpus 1 and Corpus 2 were authored by this project and used to accept or
reject changes dozens of times, so every accuracy number on them is a training
metric. Standing Decision 3 names an external corpus as the highest-value open
item in the project.

Corpus 3 is that corpus. Its value is entirely destroyed by looking at it more
than once. This document exists so that the analysis is fixed before the data is
seen, and so that "we predicted this" can be checked rather than asserted.

---

## 2. Construction (frozen)

Built by `evaluation/build_corpus3.py`. Source: ContractNLI (Koreeda & Manning,
Findings of EMNLP 2021), CC BY 4.0.

| Parameter | Value |
|---|---|
| Bundle size K | 4 |
| Seed | 0, applied to the **id-sorted** document list |
| Chunker | `DocumentChunker(chunk_size=500, chunk_overlap=50)` |
| Splits | `dev` = debugging, `test` = sealed |
| Frozen rewrite table | `build_corpus3.QFORM`, SHA-256 recorded in every `queries_qform.json` |

### The derivation, and why it is not the ContractNLI task

ContractNLI labels each of 17 fixed hypotheses per contract as `Entailment` /
`Contradiction` / `NotMentioned`. That is a **hypothesis-vs-document** relation.
This project's Stage 4 detects **document-vs-document** self-contradiction. They
are different relations and the labels are not directly usable.

Bundling converts one into the other. Four NDAs go into one store; a hypothesis
is asked once against the bundle:

| Annotator choices across the four documents | `expected_decision` |
|---|---|
| ≥1 `Entailment` **and** ≥1 `Contradiction` | `conflict` |
| all four `NotMentioned` | `insufficient` |
| otherwise | `answer` |

When A is `Entailment` and B is `Contradiction` on the same proposition, A and B
genuinely disagree, and the disagreement was certified by annotators who never
saw this system. `expected_conflict_pair` is the lowest-id representative of each
side, so the gold pair is deterministic.

**This is not a Span NLI BERT comparison and must never be presented as one.**
That system is graded per-document on the published task; this is graded
per-bundle on a cross-document conflict task *derived* from the same labels.

### Resulting class distribution (computed from labels alone)

| split | docs | bundles | queries | answer | conflict | insufficient | always-answer floor |
|---|---|---|---|---|---|---|---|
| dev | 61 | 15 | 255 | 192 | 39 | 24 | 75.3% |
| test | 123 | 30 | 510 | 396 | 74 | 40 | **77.6%** |

---

## 3. Configuration (frozen)

The frozen Corpus 1/2 configuration, as it exists in `validation.py`. **No
`RAG_*` environment overrides.** `run_eval_corpus3.py` refuses to start if any
`RAG_*` variable is set, so this is enforced rather than remembered, and
`config_snapshot()` records the actual values into every result file.

The values in force, verified by a regression run on 2026-08-24:

```
MIN_CHUNK_SCORE_THRESHOLD 0.6    CONFLICT_SIM_THRESHOLD  0.68
MIN_AVG_SCORE_FOR_SUFF.   0.65   NLI_SIM_FLOOR           0.15
MIN_QUERY_COVERAGE        0.55   NLI_CONFLICT_THRESHOLD  0.94
MIN_CHUNKS_FOR_SUFF.      1      MIN_CONFLICT_RELEVANCE  0.25
QUERY_SPAN_RELEVANCE      0.35   ANSWERHOOD_MARGIN       5.5
```

**Regression guard (2026-08-24).** The harness edits made for Corpus 3 are
additive and default-off, so Corpus 1 and 2 must be unaffected. Verified by
re-running both and comparing against `docs/STATUS.md`:

| | Corpus 1 | Corpus 2 |
|---|---|---|
| Decision accuracy | 96.2% (75/78) | 89.7% (70/78) |
| Conflict precision | 1.000 | 0.875 |
| Attribution precision | 1.000 | 0.875 |
| Unsafe answers | 0/32 | 1/32 |

Both reproduce `STATUS.md` exactly, including the post-`ANSWERHOOD_MARGIN`
Corpus 2 figures. `ANSWERHOOD_MARGIN = 5.5` is the shipped default as of
2026-08-24 (`CLAUDE.md`, "Shipped: ANSWERHOOD_MARGIN"), not an override, and its
Rule 1 invariance check is recorded there as clean. Corpus 3 therefore runs
against the same configuration the project's current published numbers describe.

No threshold, filter, stopword list or decision rule may be changed as a result
of anything observed in Corpus 3. If a corpus-3 result is bad, it is reported.

---

## 4. Metrics

**Primary:** `external_attribution_precision` — of all `conflict` reports, the
fraction whose two cited chunks each overlap a ContractNLI gold evidence span in
the two documents ContractNLI names as disagreeing (`span_attribution.py`).

The project's claim is verifiability, not accuracy, and `docs/STATUS.md` already
identifies "right decision, wrong evidence" as close to the worst failure it can
have. This is the first time that number can be graded against labels this
project did not write, so it is the primary outcome.

**Secondary:**

- three-class accuracy, **always reported beside the 77.6% always-answer floor**;
- conflict precision / recall / F1;
- `evidence_recall`, `evidence_precision` against gold spans;
- unsafe-answer rate and gap-leak rate;
- the decision delta between the verbatim-hypothesis and `qform` query sets.

**Intervals:** cluster bootstrap resampling **bundles**, not queries
(`bootstrap_ci.py`, 2000 iterations, seed 0). The 17 queries in a bundle share
four documents and are not independent; query-level resampling would report a
falsely narrow interval.

**Baselines:** always-answer, always-abstain, retrieval-threshold
(`baselines_corpus3.py`), plus a bare-LLM arm via
`evaluation/adversarial_baseline_probe.py`.

---

## 5. Error taxonomy (fixed in advance)

Every corpus-3 error is classified into exactly one bucket. The first four are
`claude.md`'s already-documented failure patterns; the fifth is what makes this
falsifiable.

1. **Surface tokens standing in for meaning** — the decision routes through
   `_query_content_terms` / `_focus_terms` and turns on a non-discriminative
   token.
2. **A real conflict re-firing on questions it does not answer** — a genuinely
   contradictory pair cited under a query it does not address (topicality).
3. **Right decision, wrong evidence** — correct verdict, mis-attributed pair.
4. **Pair-filter cost** — a true conflict suppressed by a pair-local rule.
5. **Unanticipated** — anything else.

If errors land in buckets 1–4, that is external confirmation of the limitations
section. If bucket 5 fills, that is a new finding. Deciding the buckets
afterwards would make either outcome unfalsifiable.

---

## 6. Predictions from the dev split

The full dev split has been run: **15 bundles, 255 queries** (`dev_full`).
Recording it here, before the test run, so the test result confirms or refutes a
stated expectation rather than being narrated afterwards.

| Metric | Value | 95% CI (bundle-clustered) |
|---|---|---|
| Accuracy | **27.5%** | [22.7, 32.2] |
| *always-answer floor* | *75.3%* | — |
| Conflict precision | 0.142 | [0.107, 0.180] |
| Conflict recall | 0.667 | [0.525, 0.800] |
| Attribution precision (internal) | 0.038 | [0.016, 0.062] |
| **External attribution precision** | **0.0 (0/169)** | — |
| Evidence recall vs gold spans | 0.637 (771/1210) | — |
| Gap leaks | **9/24** | — |
| Unsafe answers | 22/63 | — |

Baselines: always-answer 75.3%, always-abstain 9.4%, retrieval-threshold 75.3%.
Per-bundle accuracy ranges 11.8%–47.1%, median 23.5%.

**Two results stand out.**

*The system is far below the trivial floor* (27.5% vs 75.3%), and the
retrieval-threshold ablation **equals** the floor — every query clears
`MIN_CHUNK_SCORE_THRESHOLD`, so raw retrieval alone would score 75.3% and the
validation layer subtracts ~48 points on this corpus by over-abstaining.

*Gap leaks appear for the first time.* Corpus 1 and 2 both score 0/16; here the
system answers 9 of 24 genuine gaps. That is a **safety** regression under
transfer, not merely an accuracy one, and it is the single most important number
to re-check on the sealed split.

**Diagnosed mechanism (bucket 1, feeding bucket 2).** `_COVERAGE_STOPWORDS`
contains `employees`, `employee`, `staff`, `information` and `return` — words
that are noise in an employee handbook (Corpus 1, where the list was derived) and
load-bearing content in an NDA. Hypothesis `nda-5` is "Sharing with
**employees**"; `nda-16` is "**Return** of confidential information"; all 17
concern "Confidential **Information**". Their discriminative terms are removed
before any gating runs, leaving focus sets like `{may, receiving}` — tokens
present in essentially every chunk of every NDA. The anchor test then passes for
every pair, conflict scoping goes effectively unrestricted, and one genuinely
contradictory pair surfaces under many unrelated questions. Measured: the same
two spans of `nda_152.txt` / `nda_27.txt` were cited for `nda-3`, `nda-4`,
`nda-5`, `nda-10` and `nda-11`.

**This was NOT fixed, deliberately.** The stopword list is corpus-specific and
was derived by looking at Corpus 1. Editing it in response to corpus-3 failures
is exactly the Overfitting Test's failure case. It is recorded as a finding.

**The grader was validated before any of this was trusted.** Two resolution paths
had to be exact: whole chunks by `chunk_fingerprint` against the offset sidecar
(unresolved rate 0.3%), and conflict spans — query-relevant SUB-spans, not whole
chunks — by source-anchored string search, whitespace-normalised to survive the
extractor's newline collapsing (1 unresolved of 338). An earlier revision matched
conflict spans by fingerprint and resolved only 7 of 28, which would have scored
attribution at 0 for the wrong reason. The 0/169 above is measured, not an
artifact.

**Predictions for the test split, stated in advance:**

1. Accuracy will fall **below** the 77.6% always-answer floor.
2. Conflict **recall** will be high (> 0.7) and conflict **precision** low
   (< 0.4); the system over-flags rather than misses.
3. `external_attribution_precision` will be very low (< 0.15).
4. `evidence_recall` will be substantially higher than attribution precision
   (> 0.5) — retrieval finds the right text; the decision layer cites the wrong
   part of it.
5. Errors will concentrate in buckets 1 and 2; bucket 5 will stay small (< 10%).
6. The `qform` rewrite will change a **non-trivial** number of decisions
   (> 5% of queries), because focus-term selection is surface-form sensitive.

Prediction 4 is the one that matters for the paper: it separates "retrieval is
inadequate on legal text" from "the decision layer's topicality model fails",
and only the second is this project's claim.

---

## 7. Interpretation committed in advance

A result below the floor is **not** grounds for tuning. The honest framings, one
of which will apply:

- **If predictions hold:** the deterministic decision layer's safety properties
  are structural and transfer, while its *topicality* model is calibrated to a
  vocabulary and does not transfer. That is a real, specific, publishable
  negative result, and it converges with the nine falsifications already recorded
  under Standing Decision 1 — a tenth independent sample of the same finding, on
  documents this project did not write.
- **If they do not hold:** the dev diagnosis was wrong and must be re-derived.

Either way the number is reported. The safety-side structural results
(injection containment, fabricated-evidence rejection) are separate claims and
are not affected by the accuracy outcome.

---

## 8. Freeze record

Fill in immediately before the first test-split run, and do not edit afterwards.

```
status               : FROZEN 2026-08-25, prior to Track-B authoring and prior
                        to any test-split evaluation.
qform table SHA-256   : 206e2bf19ce70ed088bf8164ff3337821ab64af9c1c5f4bd9c8597265cf2f53c
repo commit (base)    : ca16dcafab0df2d759086e1a3df4f4960ea2c64c  (branch: Testing)
working tree at freeze: 17 files uncommitted -- the Corpus 3 build/eval code
                        and docs added in this session (build_corpus3.py,
                        run_eval_corpus3.py, span_attribution.py,
                        bootstrap_ci.py, baselines_corpus3.py, harness.py
                        edits, this file, CORPUS3_AUTHORING_PROTOCOL.md,
                        evaluation/README.md). No decision-layer file
                        (validation.py, orchestrator.py, synthesis.py) is
                        among them -- the frozen configuration in Section 3
                        is unmodified by this work.
test.json construction: not yet built. Section 2's bundling logic is fixed in
                        build_corpus3.py as committed above; running
                        `build_corpus3.py --split test` is deterministic
                        (seed=0) and will reproduce the exact bundle contents
                        stated in Section 2's yield table. The bundles
                        themselves cannot be hashed before they exist --
                        their determinism is what stands in for a hash here.
date of test run      : (fill in when Phase 2 runs)
run by                : (fill in when Phase 2 runs)
```

**Recommended, not yet done:** commit the 17 files listed above as a single
commit before Track-B authoring begins, then record that commit's hash here
too. That turns "no decision-layer file changed" from an inspectable claim into
a verifiable one.
