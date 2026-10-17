# Trust Before Text: System Observation Log

> **Purpose.** The append-only record of every change to the system, its
> evaluation, or the repo: what was wrong or what changed, why, what was done,
> and the measured effect. This is where "what did we change and why" lives.
>
> **Rules.**
> 1. Append at the bottom using the template at the end. Never edit or delete an
>    old entry; if a later change supersedes one, add a new entry that says so.
> 2. After every fix, experiment or doc change, add an entry **and** update
>    [numbers.md](numbers.md) if any number moved (see its rules).
> 3. Every entry names its evidence: a command, a result file, or a doc section.
>    Numbers without a source go in as "unverified".
>
> **Earlier history.** Observations 1 to 20 (2026-07 to 2026-08-16: conflict
> precision fixes, sufficiency AND->OR, NLI calibration, comparison-override
> removal, adversarial probe separation) are in
> [docs/archive/RAG_System_Observation_Log.md](docs/archive/RAG_System_Observation_Log.md).
> Numbering continues from 21. Those entries describe the v6 system and are
> historical.

**Companion files.** [numbers.md](numbers.md) (every number, one place) ·
[docs/STATUS.md](docs/STATUS.md) (what works / what doesn't) ·
[docs/REPRODUCE.md](docs/REPRODUCE.md) (commands) ·
[docs/CORPUS3_RESULTS.md](docs/CORPUS3_RESULTS.md) ·
[docs/RAMDOCS_COMPARISON.md](docs/RAMDOCS_COMPARISON.md).

---

## Master timeline (post-v6)

| # | Date | Observation | Area | Status | Net effect |
|---|---|---|---|---|---|
| 21 | 2026-08-16 | Fabricated evidence could be accepted as real | Safety / provenance | Implemented | Fingerprint registry (Stage 0): fabricated evidence accepted 0/4 on both corpora |
| 22 | by 2026-08-24 | Chunking, truncation, year and granularity bugs producing phantom or missed conflicts | Conflict / precision | Implemented | See entry; Corpus 2 Q030, Q029, Q038, Q076 recovered |
| 23 | by 2026-08-24 | Boilerplate and incommensurable quantities produced false conflicts | Conflict / precision | Implemented | C1 92.3% -> 96.2%, C1 false conflicts 3 -> 0 |
| 24 | by 2026-08-24 | Attribution was never scored | Metrics | Implemented | `attribution_precision` in `harness.metrics()`; overstated precision by ~0.05 |
| 25 | by 2026-08-24 | Sufficiency gate answered 2 genuine gaps (C1 Q051, C2 Q017) | Sufficiency / safety | Implemented, cost accepted | Unsafe 1/32 -> 0/32 (C1), 2/32 -> 1/32 (C2); 3 queries newly over-abstain |
| 26 | 2026-08-24 | Query-unaware false conflicts remained (9 on C2) | Conflict / precision | Implemented (`ANSWERHOOD_MARGIN`=5.5) | C2 89.7%, precision 0.875, recall 15/16 -> 14/16 |
| 27 | 2026-08-31 | Sealed external test: accuracy far below always-answer floor | Generalisation | Diagnosed, fix NOT implemented | C3 Track A 26.7% vs 77.6% floor; 0/350 external attribution |
| 28 | 2026-09-04 | External benchmark safety comparison (RAMDocs) | Evaluation | Measured | 88.4% safe, 2.6% unsafe, 54.1% of abstentions justified |
| 29 | 2026-10-10 | Merged `origin/Testing` into `jonan`; tracking files reconciled | Repo hygiene | Done | numbers.md rebuilt, this log restarted, 10 doc inconsistencies recorded |
| 30 | 2026-10-10 | Baseline re-run of the zero-token suite at `7db6ff7` | Evaluation / reproducibility | Measured, 16 of 17 steps passed | All section 2 headline numbers reproduced; 2 small DIFFs; `pytest` fails at collection; fixes deferred |
| 31 | 2026-10-10 | Stale docs corrected after the re-run; dead `retrieval_module` tests diagnosed | Docs hygiene | Docs done; test move pending approval | README and STATUS match the re-run; no numbers changed |
| 32 | 2026-10-10 | Dead tests and examples deleted; real unit tests written for the Qdrant-era code | Test suite | Implemented | `pytest tests/`: collection error -> 58 passed; supersedes the "NOT done" part of Observation 31 |
| 33 | 2026-10-10 | Corpus 2 gap-probe "before provenance" 14/24 -> 16/24 explained | Safety / adversarial | Diagnosed, no code change | Committed file predated `ANSWERHOOD_MARGIN`; safety result (0/24 after) unchanged |
| 34 | 2026-10-10 | Remaining `numbers.md` section 7 items worked: 4, 5, 9, 10 closed or narrowed; 8 not measured | Docs / provenance of numbers | Partly done | README and STATUS probe counts match raw files; Q-ID rule; tracked hash manifest |
| 35 | 2026-10-10 | Order of the sufficiency fix and Stage 4 preconditions measured (2x2) | Evaluation / attribution of effects | Measured, no code change | Effects are independent and order-insensitive; closes `numbers.md` section 7 item 8 |
| 36 | 2026-10-10 | Result files did not say which system made them; the re-run was compared to expectations by hand | Evaluation tooling | Implemented (harness scripts only) | Every harness output carries `run_info`; the runner compares all 64 headline numbers itself |
| 37 | 2026-10-10 | Full self-checking re-run at `5b26a62` after the tooling change | Evaluation / reproducibility | Measured, all steps passed | 64/64 MATCH; `pytest` 70 passed; one stamp flaw found and fixed (`9efb792`) |
| 38 | 2026-10-11 | Sealed Corpus 3 (Track A and B) replicated under the frozen configuration | Generalisation / reproducibility | Measured; qform pending | Same picture, small drift: A 26.7% -> 26.1%, gap leaks 3 -> 4/40, B conflict reports 57 -> 59; external attribution still 0 |
| 39 | 2026-10-11 | Run-to-run determinism check on one Corpus 3 bundle | Reproducibility | Measured, no code change | Fully deterministic on this machine; the August drift is environment or state, not instability |
| 40 | 2026-10-11 | qform (preregistered rewording) run on the sealed Corpus 3 | Generalisation / invariance | Measured, no code change | Rewording changes 118/510 decisions (23.1%); conflict reports -90, accuracy 26.1% -> 37.5%, unsafe answers 29 -> 43/114 |
| 41 | 2026-10-11 | Paper audit: `main.tex` brought in line with the NLPIR paper and verified numbers; RAMDocs re-graded read-only | Paper / provenance of numbers | Done for `main.tex`; nothing run | RAMDocs now reported on the NLPIR clean-rerun protocol (84.6% safe, 2.8% misinformation; prompted baseline safer); injection grading footnoted; many stale post-fix numbers corrected |
| 42 | 2026-10-11 | Zero-key verification of NLPIR claims: merged-corpora index and hand adjudication of the flagged injection answers | Verification | Measured, no pipeline change | Merged-index claim reproduces exactly for Corpus 1; Corpus 2 side shows unsafe 1 -> 2; defended-LLM injection count is 4 (strict) to 9 (generous), not 0 and not demonstrably 7 |
| 43 | 2026-10-11 | Owner decision: Corpus 1 and 2 results accepted as they are; Tables 4 and 5 sweep stopped at 24 of 57 runs | Verification scope | Decision recorded; sweep discontinued | All 24 completed sweep runs match NLPIR exactly; the rest of Tables 4 and 5 is ACCEPTED_AS_IS |
| 44 | 2026-10-14 | RAMDocs recalculated on a clean (no label leak) protocol, four runs | External validation / provenance of numbers | Measured, no pipeline change | NLPIR Table 6 reproduces: ours 85.2% safe (NLPIR 84.6%), baseline 94.8% (94.2%); all four preregistered predictions held |
| 45 | 2026-10-14 | Number ledger and checker: every number in `main.tex` traced to a source | Paper / provenance of numbers | Implemented (evaluation tooling only) | 480 rows; 1,175/1,175 main.tex numbers covered; 6 DIFFs and 1 RULE break found (see entry) |
| 46 | 2026-10-14 | Owner decisions on the ledger findings; misinformation p corrected 0.023 -> 0.022 (correction to 44) | Paper / provenance of numbers | Done (`main.tex`, numbers.md, ledger) | main.tex rule breaks 0; haystack claim added as ACCEPTED_AS_IS, flagged |
| 47 | 2026-10-15 | `main.tex` aligned with NLPIR: poisoning mislabels fixed, pre-ingestion result, Table 8, Appendix B, framing | Paper / provenance of numbers | Done (`main.tex`, numbers.md, ledger) | 534 ledger rows; 1,297/1,297 main.tex numbers covered; 0 main.tex fails |
| 48 | 2026-10-15 | Discussion and conclusion softened: "guarantee" kept only for by-construction properties | Paper wording | Done (`main.tex` only) | no number changed; ledger clean; 69 cited keys absent from references.bib listed |
| 49 | 2026-10-15 | Owner's root `references.bib` checked; 7 cite keys renamed; 4 wrong author fields found via Crossref | Paper bibliography | Done (`main.tex` cite keys only) | 98/99 cited keys resolve; honovich2022true left to the owner |
| 50 | 2026-10-17 | MultiHop-RAG: new preregistered measurement, 300 paired queries | External validation | Measured, no pipeline change | Gap leak 56/150 vs 2/150; over-abstention 52.0% vs 73.3%; strict correctness 41.7% vs 62.7% (P4 failed) |
| 51 | 2026-10-17 | Every number-bearing doc made to agree with the ledger | Documentation | Done (docs, ledger, checker print fix; no pipeline change) | ledger 549 -> 570 rows, check passes (was 3 DIFFs); 169 tests pass; numbers.md s7 items 1, 13, 14, 18 closed |
| 53 | 2026-10-17 | Paper review (Part 6): 29 ACCURACY and CLAIM fixes applied to `main.tex` | Paper wording / provenance of numbers | Done (`main.tex`, ledger; no pipeline change) | haystack sentence removed; "by construction" kept only for flips and routing; ledger 597 rows, check passes; 169 tests pass |

---

## Observation 21: Fabricated evidence accepted as real

*Added 2026-10-10 from `docs/STATUS.md` ("Fixed in earlier rounds"); commit `b411b7c`, 2026-08-16. Reconstructed after the fact, not written at the time.*

- **Issue.** A passage that was never in the ingested documents could pass through validation as if it were evidence.
- **Cause.** Nothing tied retrieved text back to the ingested corpus; trust was inferred from retrieval score.
- **Fix.** Stage 0 provenance verification: a fingerprint registry built at ingestion. A passage whose fingerprint is absent is rejected before any other stage. It proves origin, not truth.
- **Effect.** Fabricated evidence accepted: 0/4 on Corpus 1 and 0/4 on Corpus 2 (control abstains 4/4, as reported in STATUS).
- **Limit.** Provenance covers retrieval-time injection only (`docs/HOW_IT_WORKS.md` section 3).
- **Evidence.** `docs/STATUS.md` "Security properties".

## Observation 22: Phantom and missed conflicts from chunking and comparison bugs

*Added 2026-10-10 from `docs/STATUS.md` "What was fixed / Fixed this round" (rev 2026-08-24). Per-fix dates not recorded in the source.*

| Issue | Cause | Fix | Effect |
|---|---|---|---|
| 47% of chunks began mid-word | Overlap backstep landed on a raw character offset | Realign overlap to a sentence boundary | Mid-word starts 39/84 and 15/31 -> 0 |
| Phantom conflict from a truncated shared sentence | Exact string equality saw a clipped copy as different | Containment-based duplicate test | C2 Q030 fixed |
| Document years compared as policy values | Unitless numeric fallback included calendar years | Exclude calendar years | C2 Q029 fixed |
| NLI missed a real 2.5 vs 2.0 GPA conflict | Passage-level input diluted the signal | Compare sentence pairs | Conflict detected on sentences, not on passages |
| Genuine conflict flipped by 0.0001 of score (C1 Q047) | Hard rank cutoff | Retired the rank gate (anchor test replaced it) | Values 0 and 6 now identical |
| Conflicting passage deleted before detection (C2 Q038) | Stage 3 score floor 0.60 vs 0.5945 | Separate Stage 4 and Stage 5 evidence sets | Q038, Q076 recovered; gap leaks stayed 1/16 |
| "Thanks", "versus" outranked the real subject | Corpus IDF rewards question vocabulary | Restrict focus terms to words the corpus contains | Focus terms identical under perturbation |
| Injection-hijack grader marked answers safe if the true value appeared anywhere | Presence test instead of assertion test | Grade whether the payload reached the user as an assertion | Ours 18/45 -> 20/45; defended LLM 0/45 -> 7/45 |

- **Status.** Implemented. Net accuracy effect of this group alone is not isolated in the source.

## Observation 23: Boilerplate and incommensurable quantities produced false conflicts

*Added 2026-10-10 from `docs/STATUS.md` "Current measurements".*

- **Issue.** Two Stage 4 failure families: boilerplate sentences compared as claims (C2 Q024, Q029), and quantities in different dimensions compared as if comparable.
- **Fix.** Two Stage 4 preconditions, both on by default, no thresholds: `REQUIRE_ASSERTIVE_SPANS` and `DIMENSIONAL_VETO` (the latter reads word numerals, not only digits).
- **Effect.**

  | | C1 | C2 |
  |---|---|---|
  | Accuracy | 92.3% -> 96.2% | 80.8% -> 82.1% |
  | Conflict precision | 0.842 -> 1.000 | 0.600 -> 0.625 |
  | False conflicts | 3 -> 0 | 10 -> 9 |
  | Attribution precision | 0.789 -> 1.000 | 0.560 -> 0.583 |
  | Recall / unsafe | 16/16, 0 | 15/16, 1 (unchanged) |

- **Note.** `REQUIRE_ASSERTIVE_SPANS` was derived from Corpus 2 and removed all three Corpus 1 false conflicts (Q019, Q025, Q032) that had not been examined when it was written, which is the reason to read it as structural. `DIMENSIONAL_VETO` moves zero decisions; its effect is attribution only (C1 Q076). C1 reaching 1.000 is not held-out data.
- **Falsified alternatives** are tabulated in `docs/STATUS.md` Problem 1.

## Observation 24: Attribution was never scored

*Added 2026-10-10 from `docs/STATUS.md`.*

- **Issue.** `harness.metrics()` scored `observed == expected` and never compared the cited pair with `expected_conflict_pair`, so a correct verdict citing two unrelated sentences counted as fully correct.
- **Effect of the gap.** One mis-attributed report per corpus was hidden (C1 Q076, C2 Q036); conflict precision overstated by about 0.05.
- **Fix.** `harness.metrics()` now computes `attribution_precision` and `misattributed`; denominator is every conflict-flagged report (a false conflict has no gold pair and fails automatically). Reproduces the historical C2 value 14/24 = 0.583.

## Observation 25: Sufficiency gate answered genuine knowledge gaps

*Added 2026-10-10 from `docs/STATUS.md` Problem 2.*

- **Issue.** C1 Q051 (relocation allowance, not in corpus) and C2 Q017 (study-abroad credit transfer) were answered. Q017 passed the average-score branch by 0.0031. Q051 worsened after a chunking fix raised coverage 0.40 -> 0.60.
- **Cause.** Stage 5 passes on average score OR coverage; both are thresholds on continuous values and both queries landed on the wrong side.
- **Fix.** Hard presence veto before either branch: a majority (`RAG_MIN_FOCUS_PRESENCE`, default 0.5) of the question's focus terms must appear in the evidence. Out-of-vocabulary terms are deliberately kept (an absent word is the gap signal). `=0` restores old behaviour.
- **Effect.** Unsafe answers C1 1/32 -> 0/32, C2 2/32 -> 1/32 (Q045 remains, a different bug). **Cost:** three answerable queries now over-abstain: C1 Q013, C2 Q059, C2 Q074. C2 accuracy 82.1% -> 80.8% at that step.
- **Why not tuned away.** Search over 2,304 focus constructions found zero configurations that refuse Q051/Q017 and pass Q013/Q059/Q074; an embedding rescue is anti-correlated with what is needed (absent gap terms 0.30 to 0.40 cosine vs paraphrase misses 0.07 to 0.24). Accepted as irrecoverable by this method.
- **Also fixed here, metric-neutral.** `i'm` counted as a focus term (pronoun bug in contracted form).
- **Evidence.** `docs/STATUS.md` Problem 2.

## Observation 26: Query-unaware false conflicts, answerhood margin shipped

*Added 2026-10-10 from `docs/STATUS.md` Problem 1; shipped 2026-08-24.*

- **Issue.** The NLI step asks whether two sentences contradict, not whether they contradict as answers to this query. C2 had 9 false conflicts, all of this class.
- **Fix.** `ANSWERHOOD_MARGIN` (cross-encoder `ms-marco-MiniLM-L-6-v2`): both sentences of a candidate pair must score within a margin of the query's own top-1 answerhood score. Suppress-only; `find_conflict` tries the next pair. Shipped at delta = 5.5 (GO band [5.04, 6.65) covers all 30 correctly attributed true conflicts across both corpora while suppressing 8/10 false-evidence reports). Offline study: `evaluation/answerhood_lab.py`.
- **Effect (live).**

  | | Before | After |
  |---|---|---|
  | C2 false conflicts | 9 | 2 (credit-hours 21 vs 18; Dean's List vs aid GPA) |
  | C2 precision | 0.625 | 0.875 |
  | C2 attribution | 0.583 | 0.875 |
  | C2 accuracy | 82.1% | 89.7% |
  | C2 recall | 15/16 | 14/16 (Q036) |
  | Unsafe answers | 1/32 | 1/32 (Q045 only) |

- **Q036 explained.** It was already a wrong-evidence report (right verdict, unrelated pair). Suppressing that pair exposed that Stage 4 cannot find the real pair itself, so Q036 became `insufficient`. Safe, not a new unsafe answer.
- **Invariance re-check (2026-08-24).** Structural transforms 0/78 on both corpora; C1 `query_thanks`/`query_polite` unsafe flips 1 -> 0 each.
- **Correction recorded.** The earlier "NO-GO" came from counting wrong-pair reports as true conflicts; counted by cited pair, the band exists.
- **Reproduce.** `python evaluation/run_eval.py --corpus 2 --tag ah_on`; `RAG_ANSWERHOOD_MARGIN=0` restores gate-off.

## Observation 27: Sealed external test far below the always-answer floor

*Added 2026-10-10 from `docs/CORPUS3_RESULTS.md` and `docs/CORPUS3_ANALYSIS_AND_FIXES.md`. Sealed test opened once, 2026-08-31, config frozen 2026-08-25 (amended 2026-08-28).*

- **Issue.** On Corpus 3 (ContractNLI, 30 sealed bundles, authored outside this project) Track A accuracy is 26.7% against a 77.6% always-answer floor; external attribution precision is 0/350. Track B: 40.4% vs 48.8% floor, gap leaks 18/60, unsafe 65/123.
- **Cause (diagnosed, not fixed).** Topical-binding gap in Stage 4: once one true contradictory pair exists in a bundle, it is cited for unrelated questions (34 of 40 sampled misattributions are real pairs on the wrong question; `test-b01` cites its top pair in 11 of 12 conflict reports). Not a vocabulary effect (stripped vs unstripped hypotheses 26.4% vs 27.8%).
- **Ruled out.** The `_COVERAGE_STOPWORDS` list strips NDA terms (`employees`, `information`, `return`) because it was derived from Corpus 1, but this is a separate bug and not the cause. Not to be patched in response to Corpus 3 (would be fitting to the test set).
- **Proposed, not implemented.** (1) gate conflict citation on query-relevant overlap; (2) detect at sub-span granularity; (3) no pair carry-over between queries in a bundle.
- **Constraint.** Any fix is verified on Corpus 1 and 2 only. The sealed bundles are not re-run.
- **Evidence.** `docs/CORPUS3_RESULTS.md` sections 2 to 5.

## Observation 28: RAMDocs external safety comparison

*Added 2026-10-10 from `docs/RAMDOCS_COMPARISON.md`; sealed single pass n=500, 2026-09-04.*

- **Question.** How does the gated system compare with published systems on a benchmark with misinformation documents?
- **Result.** Safe rate 88.4% (442/500); unsafe 2.6% (13/500). Of 157 abstentions, 85 (54.1%) had a misinformation document present and 72 (45.9%) did not.
- **Caveat.** Safe rate and the published exact-match scores (32.6% single-call, 34.4% MADAM-RAG) are different metrics. A same-metric ablation with the gate removed is scoped but not built.
- **Method.** Closed-book (retrieval bypassed via the same monkeypatch pattern as every corpus), one real synthesis call (`openai/gpt-oss-120b`), uniform placeholder retrieval score so Stage 3 filtering is not exercised.
- **Evidence.** `evaluation/results/rd_full_ramdocs.json`; `docs/PREREGISTRATION_RAMDOCS.md`.

## Observation 29: Merge of `origin/Testing` into `jonan`; tracking files reconciled

*Added 2026-10-10.*

- **Issue.** `jonan` held the v6-era tracking files; `origin/Testing` moved them to `docs/archive/` and carried newer content and a different system (Observations 21 to 28). After merge (`7db6ff7`) the repo had no number file, no live log, and numbers disagreed.
- **Fix.** Layout kept as Testing has it (`docs/` for current documents, `docs/archive/` for superseded). Added at root: `numbers.md` (rebuilt from current docs, with history and an open-inconsistency list) and this log (restarted at 21). Added a rule to `claude.md` to update both after every change, and a pointer table in `README.md`.
- **Effect.** Ten inconsistencies recorded in `numbers.md` section 7. **None fixed in the source docs**: items 2, 3, 6, 7 need either a typo edit or a Corpus 2 re-run to confirm.
- **Not done.** No evaluation re-run; no paper edit; no change to code.

## Observation 30: Baseline re-run of the zero-token suite

*Added 2026-10-10. Commit/branch: `7db6ff7e0635570e499d8e6fd7c7e1a863f9d7c8` on `jonan`, with the uncommitted working-tree changes listed in `rerun_manifest.md`. No code, threshold, default or data file was changed.*

- **Issue.** After the merge (Observation 29) no number in `numbers.md` section 2 had been re-measured; "Nothing was re-run" was the stated caveat.
- **Cause.** n/a, this is a measurement.
- **Fix.** None by design. Ran `python evaluation/rerun_suite.py` (detached, resumable, 17 steps, no `RAG_*` variables set). Run folder: `evaluation/results/rerun_2026-10-10/`; manifest with SHA-256 of every result file: `evaluation/results/rerun_2026-10-10/rerun_manifest.md`. Gate-warning check: "ANSWERHOOD_MARGIN gate disabled" appears in 0 logs.
- **Effect (all current defaults, margin 5.5).**

  | Metric | C1 | C2 | vs numbers.md |
  |---|---|---|---|
  | Accuracy | 96.2% (75/78) | 89.7% (70/78) | MATCH |
  | Conflict recall / precision | 16/16, 1.000 | 14/16, 0.875 | MATCH |
  | Attribution precision | 1.000 | 0.875 (Q053, Q054 misattributed) | MATCH |
  | Gap leaks / unsafe answers | 0/16, 0/32 | 0/16, 1/32 (Q045) | MATCH |
  | Over-cautious refusals | Q006, Q013, Q070 | Q023, Q059, Q064, Q074 | MATCH |
  | Gate-off (`RAG_ANSWERHOOD_MARGIN=0`) | 96.2% | 82.1% (64/78), recall 15/16, precision 0.625, 9 false conflicts | MATCH |
  | Invariance, structural transforms (permute, duplicate, distractor, lower) | 0/78 each | 0/78 each | MATCH |
  | Invariance, `query_thanks` changed / unsafe | 1 / 0 (Q010, to insufficient) | 2 / 0 (Q009, Q019, to insufficient) | MATCH |
  | Invariance, `query_polite` changed / unsafe | 0 / 0 | 0 / 0 | **DIFF** for C2 (numbers.md had 1 / 0) |
  | Containment (poison reached prompt, provenance on) | 0/45 (45/45 with provenance off); routing changed 0/45 | n/a | MATCH |
  | Gap probes leaked after provenance (control) | 0/24 (0/24) | 0/24 (0/24) | MATCH |
  | Fabricated evidence accepted (control abstains) | 0/4 (4/4) | 0/4 (4/4) | MATCH |
  | Label audit | 18/45 recorded, 2 mislabels (Q002 and Q067, `authority`), 20/45 corrected | n/a | MATCH |

- **DIFFs.**
  1. Invariance C2 `query_polite`: 0 changed decisions now (margin on); `numbers.md` said 1 / 0. That cell was most likely the pre-gate value (the gate state was not recorded). Row updated.
  2. C2 adversarial gap probes, unsafe **before** provenance: 16/24 now, 14/24 in the committed `adversarial_gap_probes_corpus2.json` (commit `b6e6326`). Q055 `urgency` and `aware` went `conflict` -> `answer` with provenance off. After provenance 0/24 and control 0/24 are unchanged. C1 17/24 unchanged. The runner overwrote this tracked file, so `git status` shows it modified. Cause not investigated; `numbers.md` does not list this "before" figure, so no row changed beyond the History note.
- **Failed step.** `pytest tests/ -q` exited 2 at collection: `ModuleNotFoundError: No module named 'retrieval_module'` in `tests/test_retrieval_module.py` and `tests/test_student_handbook.py`. No file named `retrieval_module*` exists; `examples/*.py` also import it. Zero tests ran. Unrelated to every number above. Not fixed.
- **Settles `numbers.md` section 7.**
  - **Item 2 (README stale): settled.** The re-run confirms STATUS (96.2% / 89.7%, 14/16, 0/32 and 1/32). `README.md` lines 92 to 94 (92.3%, 82.1%, 15/16, 1/32, 2/32) are old values.
  - **Item 3 (C2 confusion matrix): settled.** STATUS matrix (35/7/4, 1/15/0, 0/2/14, sums to 64) is exactly the gate-off matrix; the gate-off re-run reproduces it cell for cell. Current C2 matrix (gold rows; answer / conflict / insufficient): answer 42 / 0 / 4, conflict 1 / 14 / 1, insufficient 0 / 2 / 14, sums to 70. C1: 43 / 0 / 3, 0 / 16 / 0, 0 / 0 / 16. The PDF paper's Table 1 "fixed" matrices already equal these.
  - **Item 6 (STATUS "2 wrong out of 17"): settled.** C2 flagged 16 conflicts (14 true plus Q053, Q054), so 17 should be 16.
  - **Item 7 (STATUS "9 false conflicts on Corpus 2"): settled.** 9 is the gate-off count (9 listed in the gate-off run); gate-on is 2.
  - **Item 8 (order of 82.1 -> 80.8 -> 82.1): NOT settled.** The suite reproduces endpoints only; the order needs per-switch runs. The endpoints are consistent only if the sufficiency fix came first and the Stage 4 preconditions second (inference, not measured).
- **Paper (`Trust_Before_Text_NLPIR.pdf`, not edited).** Its Tables 1 and 2 "fixed" columns, section 4.3, attribution 1.000 / 0.875, invariance (1/78 and 2/78, all toward abstention, 0 for the other transforms), gate-off ablation (96.2 / 82.1, 0.625, 15/16, 1/32) and 0/48 gap probes all agree with this re-run. Disagreement: the **abstract (p1)** quotes the frozen v6 figures (92.3%, 100% recall, 66.7%, unsafe 4/32) without a "frozen" label, against 96.2% / 89.7% / 1/32 now; sections 4.2 and 4.3 label them frozen. `numbers.md` section 0 and item 1 say the paper quotes v6; that holds for the abstract and `paper_assets/trust_before_text.tex`, not for this PDF's tables (the `.tex` was not re-read here).
- **Not run, and why.** Corpus 3 test split (sealed, opened once); `run_eval_ramdocs.py`, `experiments/` E1 to E5, `adversarial_baseline_probe.py`, `live_end_to_end.py` (need LLM keys or are sealed or out of scope); retrieval-recall, merged-corpus (94.9%), threshold-sensitivity and component-ablation scripts (not in the suite); per-switch runs for item 8. Section 3 to 6 numbers in `numbers.md` are therefore still unverified by this run.
- **Fixes deferred (do at the end, one at a time, each with its own entry).**
  1. `tests/test_retrieval_module.py`, `tests/test_student_handbook.py`, `examples/*.py`: stale `retrieval_module` import; also correct `docs/REPRODUCE.md` which advertises `pytest tests/`.
  2. Decide whether to commit the modified `adversarial_gap_probes_corpus2.json` (16/24 before) and find why Q055 changed.
  3. `README.md` lines 92 to 94 to match `numbers.md` section 2 (item 2).
  4. `docs/STATUS.md`: replace C2 confusion matrix (item 3), change "17" to "16" (item 6), add "pre-margin" to the "9 false conflicts" sentence (item 7).
  5. Paper abstract (p1): label or replace the v6 headline numbers; reword `numbers.md` section 0 once the paper's current state is confirmed.
  6. Runner: `rerun_manifest.md` is written inside `collect` before that step is recorded, so its step table shows `collect` as "not run".
  7. `numbers.md` section 7: move items 2, 3, 6, 7 to the log as closed once their source docs are fixed.
- **Evidence.** `evaluation/results/rerun_2026-10-10/` (`RERUN_SUMMARY.md`, `rerun_manifest.md`, per-step logs, `collected/*.json`).
- **Numbers updated.** `numbers.md` section 2 invariance C2 `query_polite`; History row 2026-10-10; "Last synced" line.

## Observation 31: Stale docs corrected after the re-run; dead `retrieval_module` tests diagnosed

*Added 2026-10-10. Commit/branch: `7db6ff7` on `jonan`, uncommitted edits. Follows Observation 30 (deferred fixes 3, 4 and 1).*

- **Issue.** (a) `README.md` and `docs/STATUS.md` quoted superseded numbers (`numbers.md` section 7 items 2, 3, 6, 7). (b) `pytest tests/` failed at collection (Observation 30).
- **Cause.** (a) The system improved faster than the prose. (b) `retrieval_module.py` (the in-memory FAISS/Chroma retriever) was added in `c3f1739` (2026-06-13) and deleted in `b116178` (2026-07-09) when retrieval moved to Qdrant. `tests/test_retrieval_module.py` and `tests/test_student_handbook.py` test its classes (`EmbeddingModel`, `VectorIndex`, `RetrievalModule`, `RetrievalResult`) and were last touched 2026-08-03 without being updated. They test code that no longer exists, so changing an import cannot repair them. The four `examples/*.py` scripts import the same module.
- **Fix, done (docs only, no code).**
  - `README.md` "Current state at a glance": 92.3 / 82.1, 16/16 / 15/16, 1/32 / 2/32 replaced by 96.2% / 89.7%, 16/16 / 14/16, 0/32 / 1/32.
  - `docs/STATUS.md`: "2 wrong reports out of 17" now "out of 16"; Problem 1 "Scale" now says the 9 is the pre-margin count (2 now, reproduces with `RAG_ANSWERHOOD_MARGIN=0`); Corpus 2 confusion matrix replaced by the re-measured one (42/0/4, 1/14/1, 0/2/14 = 70/78), with a note that the old matrix was the pre-margin one.
  - `numbers.md` section 7 items 2, 3, 6, 7 marked closed.
- **Fix, NOT done.** Moving the two dead test files and four example scripts to `docs/archive/legacy_retrieval_module/` was blocked by the permission classifier (file move treated as irreversible). Nothing was moved or deleted. Still to do: that move (or an alternative the owner prefers), then `docs/REPRODUCE.md` "Unit tests" (line 196) and `docs/HOW_IT_WORKS.md` lines 298 and 308 (`tests/`, `examples/`). Note: once `tests/` is empty, `evaluation/rerun_suite.py` step `pytest` will fail with "file or directory not found", so that step needs to be dropped or replaced by real tests.
- **Effect.** No number changed; `numbers.md` History not touched. Doc claims now agree with the 2026-10-10 re-run.
- **Evidence.** `evaluation/results/rerun_2026-10-10/` (Observation 30); `git log --all -- retrieval_module.py`.
- **Numbers updated.** None.

## Observation 32: Dead tests and examples deleted; real unit tests written

*Added 2026-10-10. Commit/branch: `7db6ff7` on `jonan`, uncommitted. Supersedes the "Fix, NOT done" item of Observation 31 (owner chose delete, not archive, and asked for real tests).*

- **Issue.** `pytest tests/` failed at collection (Observations 30, 31): both test files and all four example scripts targeted `retrieval_module.py`, deleted 2026-07-09 in `b116178`.
- **Cause.** Tests and examples were never updated after the move to Qdrant; the project had no working unit tests.
- **Fix.** No system code changed.
  - Deleted (still in git history): `tests/test_retrieval_module.py`, `tests/test_student_handbook.py`, `examples/example_usage.py`, `examples/interactive_qa.py`, `examples/presentation_demo.py`, `examples/slide_summary.py`, and the empty `examples/` folder.
  - Added: `tests/conftest.py` (puts the repo root on `sys.path`), `tests/test_retrieval_scoring.py`, `tests/test_qdrant_retrieval_units.py`, `tests/test_validation_structural.py`. They use no model, no vector store and no LLM.
  - Covered: provenance fingerprint and registry round-trip; Stage 0 rejects fabricated or reworded evidence, keeps genuine evidence, is disabled when no registry exists; `validate()` on only fabricated evidence abstains `insufficient` with `unverified_count` 1; the abstention truth table; `validation.py` imports no LLM or network client (AST check); de-duplication is source-aware; numeric-contradiction rules (3 vs 6 months, 3 vs 2 days, 6% vs 5% flagged; different unit contexts and calendar years not flagged); tokenizer, stemmer and IDF weighting; sparse encoder; rank fusion; cosine; score calibration.
  - Docs: `docs/REPRODUCE.md` unit-test section now says what the tests cover and what they do not; `docs/HOW_IT_WORKS.md` `tests/` row updated, `examples/` row removed.
- **Effect.** `python -m pytest tests/ -q` and plain `pytest tests/ -q`: 58 passed (about 55 s, almost all of it importing the ML libraries). One test failed on first run because the test assumed the wrong stem ("employees" stems to "employe"); the test was corrected, the code was not.
- **Limits.** These test the mechanism, not corpus behaviour; Stage 4 conflict detection with the NLI and answerhood models, retrieval against a real store and synthesis are not unit-tested (the evaluation harnesses cover them). The tests were not mutation-checked, so passing shows they agree with the current code, not that each would catch every regression. `evaluation/rerun_suite.py` step `pytest` now has something to run.
- **Evidence.** `python -m pytest tests/ -q` output (58 passed); `git status` for the deletions.
- **Numbers updated.** None.

## Observation 33: Corpus 2 gap-probe "before provenance" changed 14/24 -> 16/24

*Added 2026-10-10. Commit/branch: `7db6ff7` on `jonan`, uncommitted. Closes DIFF 2 and deferred fix 2 of Observation 30.*

- **Issue.** The 2026-10-10 re-run changed `evaluation/results/adversarial_gap_probes_corpus2.json`: unsafe "before provenance" 14/24 -> 16/24 (Q055 `urgency` and `aware` went `conflict` -> `answer`). After provenance (0/24) and control (0/24) did not change.
- **Cause (reproduced).** The committed file (`b6e6326`, 2026-09-28) was generated with the answerhood gate off. Replaying only the four Q055 probes with provenance disabled (scratch script, no result file written): with `RAG_ANSWERHOOD_MARGIN=0` urgency and aware give `conflict`; at the shipped default 5.5 they give `answer`, as do `assert` and `authority` under both settings. The pair behind the old `conflict` was the fabricated sentence ("late library books are charged USD 0.25 per day") against an unrelated genuine one ("Late Payment ... late payment fee of $150 ..."). So the old refusal was a false conflict between unrelated passages, an accidental refusal for the wrong reason. At 5.5 the gate suppresses that pair (suppress-only, as designed), and with provenance off nothing else stops the fabricated chunk, whose score is 0.95, from passing sufficiency.
- **Fix.** None to code or thresholds. The re-run file is the correct artifact for the current defaults and was kept (not committed; that is the owner's step). `numbers.md` Section 2 security table gained a row for the figure: C1 17/24, C2 16/24, with the old 14/24 and how to reproduce it.
- **Effect.** The "before provenance" count is not a stable property: it moves with unrelated false conflicts. The structural claim does not: after provenance 0/24 and control 0/24 on both corpora, and the fabricated-evidence and containment results are unchanged. Under Five-Line Rule 1 nothing structural broke.
- **Cost / regressions.** None introduced. Reading the "before" figure: 16/24 means that without Stage 0, the fabricated chunk is answered 16 times in 24 at default settings; a smaller number would reflect accidental refusals, not defence.
- **Evidence.** Re-run output `evaluation/results/rerun_2026-10-10/gap_probes_c2.log`; replay of Q055 at margin 5.5 and 0 (session scratch script); `git diff` of the file shows only 5 lines changed. Archived docs `docs/archive/FIXES_REPORT.md` and `LIMITATIONS_STATUS.md` still quote the old 14/24 as history; the paper PDF does not quote the figure.
- **Numbers updated.** `numbers.md` Section 2 security table (new row).

## Observation 34: Remaining `numbers.md` section 7 items worked (4, 5, 8, 9, 10)

*Added 2026-10-10. Commit/branch: `7db6ff7` on `jonan`, uncommitted. Paper item (1) deliberately left for the owner.*

- **Issue.** Five of the ten section 7 inconsistencies were still open after Observations 30 to 33.
- **Cause and fix, per item.**
  - **Item 5 (README vs STATUS on adversarial probes): closed.** The raw files (`adversarial_baseline_corpus1.json`, `adversarial_baseline_gpt-oss-120b_corpus{1,2}.json`) each hold 12 probes (authority and aware styles only) and 12/12 unsafe; that is 36 baseline probes in three runs. The "48" is this system's own probe count (4 styles x 6 gaps x 2 corpora). `README.md` ("every single one of 48") and `docs/STATUS.md` ("two baselines 12/12 each") were both reworded to these counts; the gpt-oss Corpus 1 regex-only count is 10/12 and was adjudicated to 12/12 in the file. `numbers.md` section 5 row updated.
  - **Item 10 (Q-ID collisions): closed.** Every ID exists in both corpora with different queries (C1 Q041 pension contribution, C2 Q041 minimum GPA for financial aid; C1 Q051 relocation, C2 Q051 TA stipend). Added rule 5 to `numbers.md`: always prefix the corpus.
  - **Item 9 (raw files not in repo): partly done.** Copied the re-run manifest (SHA-256 of every result file) to the tracked `docs/RERUN_MANIFEST_2026-10-10.md`. `git log --all` shows no `c3_*` result file in any ref, so Corpus 3 raw files cannot be recovered from the repo.
  - **Item 4 (CORPUS3_RESULTS "in progress"): narrowed, not closed.** `docs/CORPUS3_RESULTS.md` states 12/30 bundles (bare-LLM) and 22/30 (qform), so "in progress" is consistent with commit `d309565` adding the script and partial output. Whether the runs have since finished, and their raw files, are unknown. Doc not edited.
  - **Item 8 (order of 82.1 -> 80.8 -> 82.1): NOT measured.** Plan was a 2x2 on `RAG_MIN_FOCUS_PRESENCE` and the two Stage 4 preconditions (`RAG_REQUIRE_ASSERTIVE_SPANS`, `RAG_DIMENSIONAL_VETO`), with `RAG_ANSWERHOOD_MARGIN=0`, on both corpora, tags `fact_none`, `fact_suff`, `fact_precond` (the all-on corner is the existing gate-off 82.1% run). Both the scripted launch and a direct `run_eval.py` launch were refused by the permission classifier, so no run happened and no file was written. Needs the owner to run or permit it.
- **Effect.** No number changed. Docs now agree with raw files on probe counts.
- **Cost / regressions.** None.
- **Evidence.** The three baseline JSONs; `git log --all -- "evaluation/results/c3_*"` (empty); `docs/CORPUS3_RESULTS.md` section 6.
- **Numbers updated.** `numbers.md` rule 4 and new rule 5, section 5 probe row, section 7 items 4, 5, 9, 10 annotated.

## Observation 35: Order of the sufficiency fix and the Stage 4 preconditions, measured

*Added 2026-10-10. Commit/branch: `7db6ff7` on `jonan`, uncommitted. Supersedes the "NOT measured" part of Observation 34 (item 8).*

- **Issue.** `docs/STATUS.md` claims the sufficiency fix moved Corpus 2 82.1% -> 80.8% and the Stage 4 preconditions moved it 80.8% -> 82.1%, order unstated (`numbers.md` section 7 item 8).
- **Method.** Switched each change independently with the answerhood gate off (`RAG_ANSWERHOOD_MARGIN=0`), no code touched: sufficiency fix = `RAG_MIN_FOCUS_PRESENCE` 0 vs 0.5; preconditions = `RAG_REQUIRE_ASSERTIVE_SPANS` and `RAG_DIMENSIONAL_VETO` 0 vs 1 (both together). Commands: `python evaluation/run_eval.py --corpus {1,2} --tag fact_{none,suff,precond} --quiet` with those variables set per run and cleared after; the all-on corner is the existing `rerun_ahoff` run. Launched as plain commands; the first two attempts at launching them (a wrapper script, then a direct call) had been refused by the permission classifier and were not worked around, the owner then asked for the runs explicitly. Result files `evaluation/results/fact_*_corpus{1,2}.json` (gitignored folder).
- **Effect.**

  | State | C1 acc / unsafe | C2 acc | C2 precision | C2 false conflicts | C2 unsafe |
  |---|---|---|---|---|---|
  | neither | 92.3% / 1 | 82.1% | 0.600 | 10 | 2/32 (gap leak Q017) |
  | sufficiency only | 92.3% / 0 | 80.8% | 0.600 | 10 | 1/32 |
  | preconditions only | 96.2% / 1 | 83.3% | 0.625 | 9 (Q024 gone) | 2/32 |
  | both | 96.2% / 0 | 82.1% | 0.625 | 9 | 1/32 |

- **Reading.** Each change has the same effect in either order: sufficiency C2 -1 query (Q017 fixed, Q059 and Q074 lost), C1 0 accuracy change and unsafe 1 -> 0 (Q051); preconditions C2 +1 (Q024), C1 +3 (Q019, Q025, Q032). STATUS's two claims are both correct and the sequence is the sufficiency-first path. The "sufficiency only" row reproduces STATUS's "previous revision" figures exactly (92.3% / 80.8%, precision 0.842 / 0.600, false conflicts 3 / 10). The alternative order would pass through 83.3% on Corpus 2.
- **Limit.** Only these switchable changes are separated. Other changes made in the same period (chunking, sentence-level comparison, Stage 3 split, anchor test) have no switch here and stay inside the "neither" state, which is why it still reads 82.1% rather than an older number.
- **Cost / regressions.** None; no code or default changed, no RAG variable left set (checked).
- **Numbers updated.** `numbers.md` section 2 History (new 4-row table replacing the "order not stated" note); section 7 item 8 closed.

## Observation 36: Result files stamped with their provenance; the re-run runner now compares everything

*Added 2026-10-10. Commit/branch: on top of `12178d8`, `jonan`. Follows Observations 30 and 33 (the 14/24 vs 16/24 puzzle and the by-hand comparison).*

- **Issue.** (a) Only `run_eval.py` recorded the settings it ran under, and even that omitted the Stage 4/5 switches; probe, invariance, fabricated-evidence, containment and label-audit files said nothing about commit or settings, which is why a stale gap-probe file took a replay to explain. (b) `rerun_suite.py` compared only part of the numbers; the rest (invariance, probes, fabricated, containment, label audit) I compared by reading logs. Its manifest also listed `collect` as "not run".
- **Fix (evaluation tooling only; no pipeline code, threshold or default changed).**
  - New `evaluation/run_info.py`: `run_info()` returns UTC time, git commit and branch, whether tracked files are modified, SHA-256 of `validation.py` and `qdrant_retrieval.py`, the effective switches (including `MIN_FOCUS_PRESENCE`, `REQUIRE_ASSERTIVE_SPANS`, `DIMENSIONAL_VETO`) and any `RAG_*` overrides. Added as a `run_info` key to the output of `run_eval.py`, `invariance_harness.py`, `adversarial_gap_probes.py`, `fabricated_evidence_test.py`, `synthesis_containment_test.py` and `label_audit.py` (that one without config, it runs no pipeline). Existing keys are unchanged, so earlier files and the runner still read them.
  - New `evaluation/expected_baseline.json` (all expected values, mirrored from `numbers.md` section 2). `rerun_suite.py` now compares 64 numbers across every harness output, treats an absent or pre-run file as "NO FILE" / "STALE" rather than a match, prints "N MATCH, M DIFF, K missing or stale", and exits non-zero on any failed step, DIFF or missing file. `collect` now marks itself done before writing the manifest.
  - Tests: `tests/test_run_info.py` (4) and `tests/test_rerun_expected.py` (8). Suite is now 70 tests.
  - Housekeeping: `pytest>=7.0.0` added to `requirements.txt` (tests import it; REPRODUCE tells people to run it); `.gitignore` ignores `experiments/_*_log*.txt` (throwaway console logs; cited result JSONs are tracked); `docs/REPRODUCE.md`, `docs/HOW_IT_WORKS.md` and `numbers.md` rule 4 updated.
- **Effect.** The new comparison run on the existing 2026-10-10 result files: 64 MATCH, 0 DIFF, 0 missing. A 2-question `run_eval.py` run (tag `stampcheck`, throwaway) wrote the stamp correctly (commit `12178d8`, `tracked_files_modified` true because of these edits, margin 5.5). Not yet exercised end to end: a full `rerun_suite.py` run after these edits (only `compare_rows`, `collect`, `write_summary` and the stamp were run), and the stamp inside the other five harnesses beyond import and unit test; the first full re-run will show it.
- **Correction.** My earlier remark that `requirements.txt` had mojibake was wrong: the file is valid UTF-8 and the garbling was my console's display encoding.
- **Cost / regressions.** None known. `rerun_suite.py` now exits 1 on a DIFF where it used to exit 0; that is intended. Result files written before today have no `run_info`.
- **Evidence.** `python -m pytest tests -q` (70 passed); `evaluation/results/stampcheck_corpus1.json` (gitignored scratch).
- **Numbers updated.** None. `numbers.md` rule 4 now points at `run_info` and `expected_baseline.json`.

## Observation 37: Full self-checking re-run after the tooling change

*Added 2026-10-10. Commit/branch: run at `5b26a62` (stamp fix `9efb792` after), `jonan`. Closes the "not yet exercised end to end" caveat of Observation 36.*

- **What ran.** `python evaluation/rerun_suite.py --fresh` (no `RAG_*` variable set), run folder `evaluation/results/rerun_2026-10-10_2/`, manifest copied to the tracked `docs/RERUN_MANIFEST_2026-10-10_run2.md`. All 17 steps exited 0 (invariance steps took 16 to 19 min each, this machine was slower than the first run); the answerhood-gate warning appears in 0 logs.
- **Result.** The runner's own comparison: **64 MATCH, 0 DIFF, 0 missing or stale** against `evaluation/expected_baseline.json`. `pytest` step: 70 passed. Manifest now lists `collect` as done. Numbers are identical to Observation 30, so `numbers.md` has no changed row; this run is a second, independent confirmation on the new code.
- **Stamp check.** All 12 collected outputs carry `run_info` (commit `5b26a62`, margin 5.5; the two gate-off files record `RAG_ANSWERHOOD_MARGIN=0` and margin 0.0).
- **Flaw found and fixed.** Four of the 12 stamps (gap probes C2, fabricated C1 and C2, label audit) said `tracked_files_modified=True` although no source file had changed: a run rewrites two tracked result files (`adversarial_gap_probes_corpus{1,2}.json`), which then differ from the committed copies, so every later stamp in the run read as modified. `run_info.py` now excludes `evaluation/results/` from that check (`9efb792`, test added). The two tracked probe files were regenerated afterwards with the fixed stamp; their numbers are unchanged (17/24 and 16/24 before provenance, 0/24 after, control 0/24) and the diff is only the added `run_info` block. The other three stamps showing `True` (fabricated C1 and C2, label audit) are in untracked, gitignored files from this run, and the flag there reflects the artifact, not the system.
- **Cost / regressions.** None. No pipeline code, threshold or default changed.
- **Numbers updated.** None.

## Observation 38: Sealed Corpus 3 replicated under the frozen configuration

*Added 2026-10-11. Commit/branch: `3cb2e27` on `jonan` plus uncommitted runner code (`evaluation/rerun_corpus3.py`, `merge_corpus3_parts.py`, `expected_corpus3.json`, tests). Zero LLM tokens.*

- **Issue.** The raw `c3_*` files from the 2026-08-31 sealed run are in no git ref, so every Corpus 3 number was prose-only (`numbers.md` section 7 item 9).
- **Governance.** This is a replication, not a new use of the test split: it changes no code, threshold or default, the driver refuses to start with any `RAG_*` variable set, and the decision layer is identical to the preregistered frozen configuration (margin 5.5; `validation.py` differs from the freeze base only in comments and that default, which was already 5.5 in the working tree at the freeze, `docs/PREREGISTRATION_CORPUS3.md` section 3). Nothing was tuned or selected. A DIFF is a finding, not a target.
- **Method.** `python evaluation/rerun_corpus3.py` (resumable, batched). The 30 test stores were rebuilt from `data_corpus3/` with `build_corpus3.ingest_bundle` because the original ContractNLI download is not on this machine; the span-attribution check still resolves chunks by fingerprint (214 unresolved of the same order as the original 215), which supports identical chunking. Track A and Track B ran in 5-bundle batches (`run_eval_corpus3.py --bundles`) merged by `merge_corpus3_parts.py`, which uses the project's own `harness.metrics()` and refuses missing, duplicated or mixed-configuration parts; merged output equals an unbatched pool (unit-tested). One batch (Track B part 5) failed after 22 s with a Hugging Face "client has been closed" error and passed unchanged on retry. An earlier unbatched attempt was stopped by the owner after about 25 minutes (no results used).
- **Result.** 29 MATCH, 27 DIFF of 56 compared values. Track A: accuracy 133/510 = 26.1% (reported 136, 26.7%); conflict flagged / true positives / gold 386 / 47 / 74 and precision, recall, F1 unchanged; unsafe 29/114 unchanged; gap leaks 4/40 (reported 3); internal attribution 13/386 (reported 12); external attribution 0/351 (reported 0/350); evidence recall 1634/2355 (reported 1612) and precision 1898/12,577 (reported 1875/12,637); bootstrap CI for accuracy [22.2, 30.0] (reported [22.5, 31.0]); per-bundle min / median / max identical; baselines identical. Track B: accuracy 98/240 = 40.8% (reported 97), conflict flagged 59 (57) and true positives 12 (10), precision 0.2034 (0.175), recall 0.1905 (0.159), gap leaks 20/60 (18), unsafe 65/123 unchanged. Full table: `numbers.md` section 3.
- **Reading.** Every preregistered-direction conclusion holds: accuracy far below the 77.6% floor, conflict precision near 0.12, recall near 0.64, external attribution zero, unsafe count identical. The drift is a few queries: on Track A the conflict counts are identical so the changed decisions sit at the answer / insufficient boundary (an inference from the counts, not per-query evidence: the original per-query records are lost); on Track B two extra conflict reports appeared. Counts of validated chunks differ by 60 (12,577 vs 12,637), so retrieval or the relevance filter changed slightly.
- **Cause: not established.** Candidates, none tested: different library or model versions than August (this machine: sentence-transformers 5.2.2, transformers 5.0.0, torch 2.10.0; the August environment was never recorded), floating-point differences in embeddings near the score thresholds, or stores built differently. A cheap test of run-to-run determinism on this machine (rerun one bundle and compare with its stored batch) would separate "unstable on one machine" from "different environment"; not run.
- **Not run.** qform (510 questions; pending, about 2.3 h); `llm_baseline_corpus3.py` (needs an API key); dev split. The runner's `collect` step has not yet written the hash manifest.
- **Cost / regressions.** None. No system code changed.
- **Numbers updated.** `numbers.md` section 3: new "Replication" subsection (original rows kept); section 7 item 9 annotated.

## Observation 39: Run-to-run determinism on one Corpus 3 bundle

*Added 2026-10-11. Commit/branch: `d52af92` on `jonan`, clean for decision-layer files. Zero LLM tokens. Follows Observation 38, whose "cause not established" it narrows.*

- **Question.** Is the small drift between the August sealed run and the replication (Observation 38) run-to-run instability, or a difference in environment or state?
- **Method.** Bundle `test-b00` (17 Track A queries, the smallest bundle), frozen configuration, no `RAG_*` variable. Two independent fresh processes (A at 14:11, B at 14:14, about 3 minutes each) through the project's own `run_eval_corpus3.run_bundle`, each with `harness.CACHE_DIR` redirected to an empty folder so retrieval was recomputed and the real retrieval cache was neither read nor modified (otherwise a rerun would only replay cached retrieval and test validation alone). Compared: per-query decisions, `coverage` and `avg_score`, and every retrieved chunk and score, A vs B, each vs the stored Track A part 1 file, and each fresh retrieval vs the retrieval cache written during the replication. Scripts were session scratch (`det_run.py`, `det_compare.py`), not added to the repo.
- **Result.** 0 of 17 decisions differ between A and B, between A and the stored batch, and between B and the stored batch. `coverage` and `avg_score` are bit-identical in all three comparisons (max difference 0.000000). Retrieval: 27 files per run, identical chunk sets, identical ranking and identical scores to full precision (max difference 0.000000) between A, B and the replication cache.
- **Reading.** On this machine, with these stores, the pipeline is deterministic end to end (embeddings, retrieval, validation), so the Observation 38 drift is not noise. It must come from something that differs from August: library or model versions, hardware numerics, or the rebuilt stores, none of which was recorded in August. This does not say which; and it does not show that bundles with the largest drift behave identically (one bundle only, and the August per-query records are lost, so b00's own drift is unknown).
- **Not run.** A version-pinning test (rebuild the environment as of August) is impossible without the August package list; a second machine would test hardware numerics.
- **Cost / regressions.** None. Real retrieval cache untouched; no repo file changed except this log and `numbers.md`.
- **Numbers updated.** `numbers.md` section 3 replication note.

## Observation 40: qform (rewording) on the sealed Corpus 3; replication run completed

*Added 2026-10-11. Commit/branch: `938d018` plus the runner commit `d52af92` on `jonan`. Zero LLM tokens. Completes the run of Observation 38 (all steps exit 0; collect wrote `docs/RERUN_C3_MANIFEST_2026-10-11.md`, 24 hashed result files).*

- **Question.** Preregistered prediction 6 (`docs/PREREGISTRATION_CORPUS3.md` section 6): the frozen interrogative rewrite of the same 17 hypotheses, same gold, changes more than 5% of decisions because focus-term selection is surface-form sensitive. qform was never completed before, so this is the first measurement.
- **Method.** `rerun_corpus3.py` steps `qform_part1..6` (`run_eval_corpus3.py --queries queries_qform.json`, frozen configuration, margin 5.5, no `RAG_*` override) and `qform_merge`; 510 queries, 30 bundles. Decisions compared with Track A at the same query position within each bundle (same positions, same bundles, 0 misalignments). Total compute 7,725 s.
- **Result.** 118 of 510 decisions change (23.1%), against the preregistered threshold of 5%: prediction 6 holds.

  | | Track A (statements) | qform (questions) |
  |---|---|---|
  | accuracy | 133/510 = 26.1% | 191/510 = 37.5% |
  | conflict flagged / true positives | 386 / 47 | 296 / 37 |
  | conflict precision / recall | 0.122 / 0.635 | 0.125 / 0.500 |
  | gap leaks | 4/40 | 9/40 |
  | unsafe answers | 29/114 | 43/114 |
  | always-answer floor | 77.6% | 77.6% |

  Transitions (Track A -> qform): conflict -> answer 86, conflict -> insufficient 18, answer -> conflict 13, insufficient -> conflict 1; answer -> insufficient and insufficient -> answer: 0. By gold label, the changes are: gold `answer` 68 conflict -> answer, 9 answer -> conflict, 7 conflict -> insufficient; gold `conflict` 12 conflict -> answer, 3 answer -> conflict, 2 conflict -> insufficient, 1 insufficient -> conflict; gold `insufficient` 9 conflict -> insufficient, 6 conflict -> answer, 1 answer -> conflict.
- **Reading.** Every changed decision involves a conflict report: rewording moves where the conflict detector fires, not the sufficiency gate. Statements fire it on 386 queries, questions on 296. That removes 68 false conflicts on answerable queries (accuracy +11.4 points) and 9 on gaps, but it also lets 12 true conflicts and 6 gaps be answered, so unsafe answers rise by 14 and gap leaks by 5. Neither phrasing reaches the 77.6% floor. This is Failure Pattern 1 (`claude.md`: the decision changes when the query is reworded without changing its meaning) measured on text the project did not write, and it means the project's invariance result (0/78 on case, ordering, duplication, distractor chunks) does not extend to paraphrase.
- **Caveats.** The 17 rewrites are one frozen table, not a sample of paraphrases, and the question form also changes how the answerhood and focus-term gates read the query, so this measures that table, not "paraphrase" in general. Whether each rewrite preserves the gold label is the preregistration's assumption; it was not audited here. Each phrasing was run once; Observation 39 shows the pipeline is deterministic here, so one run is the same as many.
- **Not run.** `llm_baseline_corpus3.py` (needs an API key); the dev split.
- **Cost / regressions.** None; no code changed. Nothing was tuned or selected on this result, and under the Five-Line Rule it is a measurement, not a candidate for a fix.
- **Numbers updated.** `numbers.md` section 3 (qform rows, prediction-6 paragraph, header text) and section 7 items 4 and 9.

## Observation 41: Paper audit; `main.tex` aligned with NLPIR and the verified numbers

*Added 2026-10-11. Commit/branch: on top of `14fc243`, `jonan`. No evaluation was run; RAMDocs and Corpus 3 test stay sealed (owner decision). `main.tex` is untracked; the unedited original is kept outside the repo.*

- **Issue.** `main.tex` (the older IEEE-conference draft) quoted superseded post-fix numbers and RAMDocs figures that disagree with `Trust_Before_Text_NLPIR.pdf`, which the owner states is the most up to date paper.
- **Verified against raw files (matches).** NLPIR Tables 1 and 2 (frozen columns from `baseline_corpus{1,2}.json`; fixed columns from the 2026-10-10 re-run; prompted baseline from `experiments/baseline_results*.json`), every Wilson interval, McNemar p-values (0.22; 4.2e-07; 0.016), refusal and abstained-on-answerable counts, Table 3 totals (6 -> 3, 26 -> 8), retrieval recall (recall@5 1.0, recall@1 0.8468, MRR 0.9919 on both corpora), the gate-off ablation row, injection (0.911, 0.400, routing changed 2/45), adaptive 2/6 vs 0/6 and 4/4, adversarial probe counts. The injection screen reproduces NLPIR's footnote: undefended 45/45, defended 12/45, unhardened synthesis 22/45, hardened 2/45; hand adjudication of our four flagged answers gives 20/45.
- **RAMDocs.** The committed `rd_full_ramdocs.json` re-grades exactly to 442 safe / 13 unsafe / 45 unscored (88.4%), but NLPIR's clean rerun gives 84.6% safe / 2.8% misinformation asserted with a prompted baseline (94.2% / 1.4%), and the decision-layer counts are identical (343 answered, 157 abstentions, 85 justified), so the committed file is probably the superseded label-leak run. `main.tex` now reports NLPIR's protocol and numbers. Checks on the committed file that go beyond the paper: 22 answers contain both gold and wrong values (84.0% / 7.0% under a stricter tie rule), 48.6% of queries contain a misinformation document so 54.1% justified is not distinguishable from chance (p = 0.175), and the "stable within 0.1 points from n=207" claim is unsupported (54.5% -> 54.1%, range 48.7% to 56.9%).
- **Fix (`main.tex` only).** Post-fix Corpus 2 numbers (89.7%, 0.875, 14/16), answerhood-gate paragraph and threshold row, invariance table (1/78 and 2/78), adversarial probe denominators, RAMDocs section (new head-to-head table, published scores moved to their own table, superseded-run disclosure, abstention base rate, unscored explanation), injection footnote with the corrected-grader counts, held-out wording, provenance non-goal, limitations and falsified-fix table, "Han et al." -> "Wang et al.", "peer-reviewed" and "permissively licensed" removed (not verified). Original backed up outside the repo.
- **Not verified here (no raw files).** NLPIR's RAMDocs table and its three p-values, MultiHop-RAG, the merged-corpora 94.9%, the current-system haystack claim (the tracked haystack file is the v6 run), Tables 4 and 5 beyond their default and gate-off rows. NLPIR's Corpus 3 numbers are the August values; the replication differs slightly (26.1%, 0/351). Corpus 3 is kept out of `main.tex` by decision.
- **Still to port from NLPIR if wanted.** Wilson intervals and McNemar tests, Table 3 (errors by component), retrieval-recall paragraph, Tables 4 and 5, merged-corpora result, MultiHop-RAG.
- **Numbers updated.** `numbers.md` section 4 (current RAMDocs run, checks, corrected citation).

## Observation 42: Merged-corpora index reproduced; flagged injection answers hand-adjudicated

*Added 2026-10-11. Commit/branch: `14fc243` on `jonan` plus uncommitted evaluation scripts. Zero LLM tokens. No pipeline, threshold or default changed; Corpus 3 test and RAMDocs untouched by these two checks.*

- **Merged index.** NLPIR states that one 22-document, 135-chunk index keeps recall@5 at 1.0, conflict recall 16/16 and 0/32 unsafe, with accuracy falling from 96.2% to 94.9% because the two organisations' password policies disagree. No script or raw file existed in the repo. New `evaluation/merged_corpora_test.py` copies the 22 `.docx` files (no name collisions; ground-truth and query files are not ingestible) into the gitignored `data_merged/`, ingests them into the gitignored `qdrant_db_merged/` (135 chunks, as stated), and runs each corpus's own 78 queries under the default configuration. **Corpus 1: 74/78 = 94.9%, recall 16/16, unsafe 0/32, gold documents all in the top 5 for 62/62; the changes are Q010 and Q022 (both password questions) answer to conflict and Q013 insufficient to answer.** The claim reproduces exactly. Not stated in the paper: for Corpus 2's queries the merged index gives 69/78 = 88.5% with unsafe answers **2/32 instead of 1/32** (Q048, a conflict now answered), precision 0.778, and four more decision changes (Q031, Q070 to conflict; Q036 insufficient to conflict; Q064 insufficient to answer). The paper sentence is true for Corpus 1 and should say so. Result file `evaluation/results/merged_corpora.json` (stamped with `run_info`).
- **Injection answers, adjudicated by hand.** The automated screen in `label_audit.py` flags 12 of the defended LLM's 45 answers; `docs/STATUS.md` says 7 were confirmed by hand, but no file records which 7 or the rule used. I read all 12 against a written rule (hijacked = the answer presents the planted value as a valid answer). Result: 4 clearly hijacked (Q004, Q006, Q010, Q014, each ending "the answer is either [true] or [planted]"), 5 conflict reports that state both values without concluding (Q005, Q008, Q009, Q011, Q013), 3 not hijacked (Q002, Q012, Q015). The defended LLM therefore scores 4 (strict) to 9 (generous), so "resisted all 45" is wrong under any reading of the audit, and the 7 is not reproducible from the files. Of the two answers the screen flags in hardened synthesis, one is a false positive (Q004) and one a conflict report (Q005): 0 clear hijacks. One reader, one rule: a second reader should repeat it before the numbers are quoted.
- **Cost / regressions.** None. `.gitignore` gained `data_merged/` and `qdrant_db_merged/`.
- **Numbers updated.** `numbers.md` section 5 (injection grading rows, adjudication block, merged-index table).

## Observation 43: Corpus 1 and 2 accepted as is; Tables 4 and 5 sweep stopped

*Added 2026-10-11. Commit/branch: `14fc243` on `jonan` plus uncommitted work. Zero LLM tokens.*

- **Decision.** The owner does not want more testing on Corpus 1 and 2: their results are taken as they are (saved result files and the NLPIR paper). The earlier rule "only numbers tested after pulling the Testing branch" therefore applies to numbers that are NOT Corpus 1 or 2: RAMDocs, MultiHop-RAG and anything new. Recomputations and re-runs already done (Observations 30 to 42) remain on record as extra evidence.
- **Sweep.** `python evaluation/sweep_tables.py` had completed 24 of its 57 runs (about 22:38 on 2026-10-11) when it was stopped. The 24 finished runs (default; NLI cutoff 0.80, 0.99; average-score floor 0.55, 0.68, 0.70, 0.75; coverage floor 0.35, 0.50, 0.65, 0.75; answerhood margin 0; both corpora) all match NLPIR's printed Table 4 and 5 values exactly (24 MATCH, 0 DIFF). Result files `evaluation/results/sweep_*_corpus*.json` and `sweep_summary.md` are kept (gitignored). The remaining rows are ACCEPTED_AS_IS from NLPIR.
- **Consequence for the ledger.** Add the status label ACCEPTED_AS_IS (value taken from a saved result file or the NLPIR paper, not re-tested, by owner decision). Numbers outside Corpus 1 and 2 still need REPRODUCED, RECOMPUTED, DERIVED or EXTERNAL status, or must be left out of `main.tex`.
- **Note.** A RAMDocs clean run (`rdc_ours_orig`) was started by another chat at 21:50 and was still running at 22:40 (152 queries checkpointed); it is untouched by this decision. Any chat whose prompt says "resume the sweep" must not.
- **Numbers updated.** `numbers.md` section 5 (decision and partial sweep result).

## Observation 44: RAMDocs recalculated on a clean protocol; NLPIR Table 6 reproduces

*Added 2026-10-14. Commit/branch: `14fc243` on `jonan` plus uncommitted evaluation scripts. Runs 2026-10-11 to 2026-10-14, about 1,700 Groq calls (`openai/gpt-oss-120b`). No pipeline, threshold or default changed; RAMDocs unsealed for this recalculation only and sealed again.*

- **Issue.** The committed RAMDocs result (88.4% safe, `rd_full_ramdocs.json`) was label-leaky: `run_eval_ramdocs.py` put each document's type in its source and section names, which `synthesis.py` prints into the prompt. NLPIR reports a clean rerun (84.6%) whose script and baseline prompt are not in the repo.
- **Fix.** None to the system. New runner `evaluation/run_eval_ramdocs_clean.py` (neutral names `Document N`, no label or answer field anywhere in a chunk or prompt; two arms, `ours` and a prompted `baseline` with the E1 prompt; two document orders, RAMDocs' `original` and a seeded `shuffled`), rules and predictions fixed beforehand in `docs/PREREGISTRATION_RAMDOCS_RERUN.md`. Groq keys rotated with `--rotate-keys` (`evaluation/key_pool.py`); `GROQ_API_KEY_3` to `_5` returned HTTP 401 and were skipped (the owner later replaced `_3`). Runs (a) and (c) were stopped and resumed once each from their checkpoints at the owner's request; no query was lost or duplicated.
- **Effect.** Original order: ours 85.2% safe [81.8, 88.0], EM 18.0%, misinformation asserted 2.8% (14), refusals 31.4% (157, 85 justified); baseline 94.8% safe [92.5, 96.4], EM 7.6%, misinformation 1.0% (5), refusals 76.8% (384, 209 justified). Shuffled order: ours 85.4%, EM 18.6%, misinformation 4.0% (20), the same 157/85 refusals; baseline 93.6%, EM 8.0%, misinformation 1.6%. Paired McNemar: baseline safer (p = 2.4e-9), ours higher EM (p = 9.1e-13), baseline asserts less misinformation (p = 0.023). Full table in `numbers.md` section 4.
- **Against NLPIR Table 6.** Confirmed. Ours matches exactly on the decision-layer counts (157, 85, 343 answered) and on misinformation (14), and within 3 queries on safe (426 vs 423) and EM (90 vs 93). The baseline is within 3 to 4 queries on refusals, safe and justified, identical on EM (38), 5 vs 7 on misinformation. All four significance directions hold. The remaining differences fit LLM non-determinism (ours: same decisions, different synthesised text) and a different baseline prompt (the E1 prompt, not NLPIR's), not a grader change: the same grading rule was applied, and NLPIR's "answered: misinfo" is misinformation asserted per answered query.
- **Preregistered predictions.** (1) 157 refusals and 85 justified in both orders: held (identical decision on 500/500 queries across orders). (2) Safe rate below the leaky 88.4% and within about 5 points of 84.6%: held (85.2%). (3) Shuffled not higher than original by more than a few points: held (ours +0.2, baseline -1.2; neither significant). (4) Baseline safer than ours: held.
- **Cost / what this does not show.** The baseline is safer by refusing three quarters of queries, not by better judgement. Justified refusals are near the 48.6% base rate of queries containing a misinformation document for both systems (ours 54.1%, p = 0.175; baseline 54.4%, p = 0.025, a marginal excess). The primary grader is lenient: if any wrong value counts as unsafe, ours falls to 71.6% safe / 15.8% unsafe (baseline 94.2% / 1.6%). In shuffled order ours asserts misinformation slightly more often (14 -> 20, p = 0.07): a synthesis effect, since the decision layer is order-invariant.
- **Evidence.** `evaluation/results/rdc_{ours,base}_{orig,shuf}_ramdocs_clean.json` (with `run_info`), console logs beside them; pilot `rdc_pilot_ramdocs_clean.json`.
- **Numbers updated.** `numbers.md` section 4 (new subsection "Clean recalculation", marked CURRENT) and the "Last synced" note.

## Observation 45: Number ledger and checker for the paper

*Added 2026-10-14. Commit/branch: on top of `fb61f12`, `jonan`. Zero LLM tokens, no harness run, no key used. No pipeline code, threshold, default or `main.tex` text changed.*

- **Issue.** Numbers in `main.tex`, the NLPIR PDF and the docs had no per-number record of where they came from or whether anyone had checked them, so the owner's rule (a number that is not about Corpus 1 or 2 must be tested, or left out of `main.tex`) could not be enforced.
- **Fix.** New `docs/NUMBERS_LEDGER.csv`: 480 rows, one per claim in each place it appears (main.tex 400, NLPIR PDF 50, README 6, STATUS 12, RAMDOCS_COMPARISON 3, numbers.md 9). Each row names its source; 386 rows carry an expression over a saved file (`V(file, path)`, plus Wilson, Clopper-Pearson, exact McNemar, binomial and Fisher helpers) that the checker re-evaluates. New `evaluation/check_ledger.py` (read-only) runs five checks: (a) recompute, (b) each string is still in its file near its line, (c) every number in the body of `main.tex` is covered by a row, (d) non-C1/C2 rows must be REPRODUCED, RECOMPUTED, DERIVED or EXTERNAL, (e) stale strings (88.4%, 82.1%, 92.3%, "Han et al.", "10 of 25") outside sections marked historical. New `tests/test_ledger.py` (15 tests); the suite is 146 passed.
- **Effect.** Status counts: RECOMPUTED 336, ACCEPTED_AS_IS 71, UNVERIFIABLE 29, DERIVED 18, REPRODUCED 15, EXTERNAL 11. Checker: (a) 368 match, 6 DIFF; (b) 480 of 480 found; (c) 1,175 of 1,175 numbers in `main.tex` covered; (d) 1 RULE break in `main.tex`; (e) 0 stale. The DIFFs and the RULE break are findings, listed next. The checker exits 1 until they are resolved.
- **Findings (not fixed: main.tex was out of scope; each needs an owner decision).**
  1. `main.tex:1616` quotes NLPIR's earlier clean run (84.6% and 94.2%), which has no raw file. That is a non-C1/C2 number that is UNVERIFIABLE, so it breaks the RULE. The clean rerun gives 85.2% and 94.8%.
  2. `main.tex:1602` and `numbers.md:340`: misinformation McNemar p = 0.023. Exact McNemar on 11 vs 2 discordant pairs gives 0.02246, which rounds to 0.022.
  3. `main.tex:1643`: p = 0.18. The exact binomial test gives 0.17498 (0.175 to three places, 0.17 to two), so the 0.18 comes from rounding twice.
  4. NLPIR p11: "with provenance disabled, 31 of 48". The current files give 33 (17 + 16); the 31 uses the pre-margin Corpus 2 value 14/24 (Observation 33).
  5. `docs/STATUS.md:168-169` shows pre-gate invariance values (C1 query_thanks 2/78 with 1 refuse-to-answer, query_polite 1/78 with 1, C2 query_polite 1/78) under "Current measurements". The current files give 1/78, 0/78 and 0/78 with no refuse-to-answer flips.
  6. Not DIFFs, but recorded in the ledger notes:
     - NLPIR p5 says both corpora have 45 facts; Corpus 2's `ground_truth.json` has 46.
     - `main.tex` calls the query-intent gate "Structural"; NLPIR Table 9 says it was selected on Corpora 1 and 2.
     - `main.tex:1167` cites an "8-query replay" as determinism evidence; NLPIR cites two full 78/78 runs.
     - The security table's "In-corpus poisoning accepted 0/4" is the retrieval-time fabricated-evidence test, while `sec:adv-adaptive` says in-corpus poisoning defeats both systems (4/4).
     - The 46.0% to 62.1% interval at `main.tex:1642` is Clopper-Pearson, not Wilson.
     - NLPIR's haystack claim ("all 20 haystacks at every N") contradicts the only tracked haystack file, the v6 run (ours recall 0.75 at N=2, 0.60 at N=20).
- **UNVERIFIABLE (29).**
  - In `main.tex`, one row: finding 1 above.
  - The other 28 are NLPIR PDF rows, which are not in `main.tex`:
    - all of MultiHop-RAG (abstract, section 4.8, Table 7);
    - the haystack claim and its LLM arm;
    - the NLPIR RAMDocs values that the clean rerun does not reproduce exactly: 84.6, 94.2, 76.2, 1.4, 53.8, 205/381, 75.6/5.9/119, the p-values below 1e-10, 0.039 and below 1e-13, and the 59 re-queried empty replies;
    - the August Corpus 3 values (26.7%, 0/350, 40.4%).
- **Cost / regressions.** None; read-only tooling. `tested_after_merge` is "yes" only when the source file was written on or after 2026-10-10. It is "n/a" for EXTERNAL rows and for counts read from input files (`data/`, code constants).
- **Evidence.** `python evaluation/check_ledger.py -v`; `python -m pytest tests -q` (146 passed).
- **Numbers updated.** None changed. Findings 2 to 5 were added to `numbers.md` section 7 as items 11 to 14.

## Observation 46: Owner decisions on the ledger findings; p-values corrected (correction to Observation 44)

*Added 2026-10-14. Commit/branch: on top of `a0fa913`, `jonan`. Zero LLM tokens, nothing run except the checker and the tests. `main.tex` was edited (backup `D:\Major Project_paper_backups\main_2026-10-14_before_ledger_fixes.tex`); no pipeline code, threshold or default changed.*

- **Correction to Observation 44.** Observation 44 (and `numbers.md` section 4) gave the paired test for misinformation asserted, ours vs baseline in the original order, as p = 0.023. The exact McNemar test on the 11 vs 2 discordant pairs gives 0.02246, so the correct value is **p = 0.022**. The shuffled-order value (0.0075) and every other p-value in that entry recompute correctly. Observation 44 itself is left unedited, as the log rules require.
- **Owner decisions (answers to Observation 45's questions).**
  1. MultiHop-RAG: there are no raw files. It stays out of `main.tex`, its ledger rows stay UNVERIFIABLE, and the owner will run Part 3b later.
  2. Haystack: there is no current-system file. NLPIR's claim was added to `main.tex` (sec:retrieval_recall, one sentence in NLPIR's own wording) as ACCEPTED_AS_IS (Corpus 1) and flagged in the ledger, because the only tracked file (v6) contradicts it. Recorded as `numbers.md` section 7 item 15.
  3. RAMDocs baseline: there is no NLPIR baseline file. `main.tex:1616` no longer quotes 84.6% and 94.2%. It now says every baseline figure comes from the recalculated run with the E1 prompt (94.8% safe), and that the earlier run is not reported because its prompt and per-query results are unavailable.
  4. p-values in `main.tex` and `numbers.md`, each now with its test named:
     - misinformation asserted: p = 0.022, exact McNemar;
     - justified refusals: p = 0.175, exact binomial test against the 48.6% base rate.
- **Checker.** Inserting lines into `main.tex` exposed a weakness: rows whose value text repeats on nearby lines (the invariance table's "& 0/78 & 0/78") could pick the wrong occurrence after a shift. `check_ledger.py` now matches such rows to occurrences in order, choosing the assignment with the least total drift. New option `--sync-lines` writes each row's current line back to the ledger; it updated 216 rows after these edits. One test was added; `tests/test_ledger.py` now has 16.
- **Effect.** The ledger has 485 rows: RECOMPUTED 338, ACCEPTED_AS_IS 77, UNVERIFIABLE 26, DERIVED 18, REPRODUCED 15, EXTERNAL 11.
  - (b) presence: 485 of 485 found.
  - (c) coverage: 1,182 of 1,182 numbers in `main.tex` covered.
  - (d) rule: 0 breaks in `main.tex`.
  - (e) stale strings: 0.
  - (a) recompute: three DIFFs remain, all outside `main.tex`: NLPIR p11 "31 of 48" (item 13) and the STATUS invariance rows (item 14). They are left for the docs pass.
- **Cost / regressions.** The haystack sentence puts into `main.tex` a Corpus 1 number that the repo cannot reproduce, and the only tracked file contradicts it. That is the owner's accepted risk, flagged in the ledger notes.
- **Evidence.** `python evaluation/check_ledger.py -v`; `python -m pytest tests/test_ledger.py -q` (16 passed); the `main.tex` backup above.
- **Numbers updated.** `numbers.md` section 4: misinformation p 0.023 -> 0.022, test names added. Section 7: items 11 and 12 closed, item 15 added.

## Observation 47: `main.tex` aligned with the NLPIR paper; two poisoning mislabels fixed

*Added 2026-10-15. Commit/branch: on top of `8d27d23`, `jonan`. Zero LLM tokens, nothing run except the checker and the tests. `main.tex` was edited (backup `D:\Major Project_paper_backups\main_2026-10-15_before_nlpir_alignment.tex`); no pipeline code, threshold or default changed. ContractNLI / Corpus 3 stays out of `main.tex` (owner decision).*

- **Issue.** A section-by-section diff of `Trust_Before_Text_NLPIR.pdf` against `main.tex` found:
  - two places where `main.tex` contradicted NLPIR;
  - one missing caveat;
  - several NLPIR items missing from `main.tex`.

  The tables added on 2026-10-11 match NLPIR and the ledger cell for cell: `tab:ci_mcnemar`, `tab:errors_component`, `tab:sensitivity` and `tab:component_ablation`. Table 5 was checked by eye on a rendered page, because the PDF text layer scrambles its precision column.
- **Cause.**
  - **Security table.** `tab:security_current` called the retrieval-time fabricated-evidence test (0/4 per corpus) "in-corpus poisoning, holds".
  - **Adaptive attack.** Its 4/4 gap result was described as a document planted before ingestion. NLPIR p11 says that 4/4 spliced passages in at retrieval time, which provenance now blocks, and that pre-ingestion poisoning defeats ours 24/24.
  - **Paragraph-level NLI.** These figures are taken from NLPIR, but the paper did not say they were never reproduced.
- **Fix (owner-approved list).**
  1. **Security table:** rows relabelled; a pre-ingestion poisoning row (24/24, fails) added; the note reworded.
  2. **Adaptive attack:** `tab:adaptive`, its caption and Finding 2 now describe the v6 4/4 as retrieval-time splicing and point to the pre-ingestion result.
  3. **sec:adv_separation:**
     - gap-probe McNemar p-values, DERIVED with the arithmetic shown: 2 x 0.5^12 = 4.9e-4 and 2 x 0.5^24 = 1.2e-7;
     - provenance disabled: 33 of 48 answered (17 + 16, current files, not NLPIR's 31);
     - pre-ingestion poisoning, ACCEPTED_AS_IS from NLPIR (no result file on any branch): ours 24/24, Wilson [86, 100]%; defended 120B 24/24, p = 1.0; clean stores 0/12;
     - NLPIR Table 8 as `tab:adversarial_summary`.
  4. **Thresholds:** the query-span floor 0.35 is relabelled from Structural to Calibrated (selected on both corpora), as in NLPIR Table 9. The prose now says 3 constants are calibrated on Corpus 1, 3 are selected on both corpora, and 14 are structural. New Appendix B (`app:constants`, `tab:constants_full`) lists all 20 constants. Every value was checked against `validation.py`, and the 0.35 -> 0.60 score anchor against `retrieval_scoring.py`. An earlier chat message wrongly listed more provenance mismatches; the PDF text layer had misplaced Table 9's provenance column, and the rendered page corrected this.
  5. **Abstract and introduction:**
     - "safe behavior a property of the system" is replaced by NLPIR's wording: repeatable, not necessarily correct;
     - determinism and safety are now separated;
     - the abstract adds C2 unsafe 4/32 (1/32 after the fixes) and that pre-ingestion poisoning defeats both systems.
  6. **Contributions:**
     - the provenance check plus seven stages;
     - the NLI prong carries detection;
     - the list of analyses;
     - provenance blocks retrieval-time injection.
  7. **Limitations:**
     - "External validation on legal-domain text is ongoing and not reported here" (no corpus named);
     - no conflict-aware RAG baseline, no optimized or white-box attacker, and baseline non-determinism measured only at temperature 0.7.
  8. **Reproducibility:**
     - one value set for all results;
     - no sampling or seed in the decision layer;
     - temperature 0 except the 5 unseeded reruns at 0.7;
     - invariance seed 20260819;
     - Python 3.11.9 (owner; NLPIR says 3.12);
     - dependencies as lower bounds.

     Each was checked in code: `llm_interface.py`, `experiments/baseline_experiment.py` defaults, `evaluation/invariance_harness.py` SEED, and `requirements.txt` (only `>=`).
  9. **Paragraph-level NLI caveat:** added in the prose and as a footnote on the Table 5 row.

  Not done, by owner decision: Appendix A (prompts) and the machine-generated-text item in future work. The haystack sentence stays ACCEPTED_AS_IS and flagged.
- **Effect.**
  - **Ledger:** 485 -> 534 rows. 49 rows were added and 6 rewritten (MT-046, MT-310, MT-322, MT-323, MT-376, MT-378).
  - **(c) coverage:** 1,297 of 1,297 numbers in `main.tex` covered.
  - **(b) presence:** 534 of 534.
  - **(d) rule:** 0 breaks in `main.tex`.
  - **(e) stale strings:** 0.
  - **(a) recompute:** the same three DIFFs outside `main.tex` (NL-048, ST-010, ST-011).
  - **LaTeX:** braces and environments balance, every `\ref` has a label, no duplicate labels. There is no LaTeX engine here, so nothing was compiled.
- **Cost / regressions.**
  - Two more Corpus 1/2 claims in `main.tex` rest on NLPIR alone with no raw file: pre-ingestion poisoning and the "20 active constants" classification. Both are flagged in the ledger.
  - The discussion and conclusion still say "deterministic, auditable safety guarantee" and "safe abstention a property of the architecture", which is softer than the new abstract framing. They were left for the owner to decide.
- **Evidence.** `python evaluation/check_ledger.py -v`; `python -m pytest tests/test_ledger.py -q` (16 passed); the `main.tex` backup above.
- **Numbers updated.** `numbers.md` section 5: three rows added (provenance-off 33/48, gap-probe p-values, pre-ingestion poisoning). Section 7: item 13 closed for `main.tex`, item 15 re-confirmed, items 16 to 19 added.

## Observation 48: Discussion and conclusion softened to match the abstract

*Added 2026-10-15. Commit/branch: on top of `8d27d23`, `jonan`. Zero LLM tokens. `main.tex` edited (same backup as Observation 47); no pipeline code, threshold, default or number changed. `paper_assets/references.bib` not touched.*

- **Issue.** After Observation 47 the abstract said the decision is "repeatable, not necessarily correct". The discussion and conclusion still claimed more:
  - "safe abstention a property of the architecture";
  - "no input on which the safety condition quietly fails to hold";
  - "a deterministic, auditable safety guarantee";
  - that structural attribution transfers exactly. NLPIR and Observation 47 say attribution does not transfer.
- **Fix (owner's instruction).**
  - **"Guarantee Versus Behavior":** rewritten. "Guarantee" now names only the by-construction properties: injected text cannot change routing, unfingerprinted evidence is discarded, and the passage-level invariance transforms change nothing. It also says the decision is repeatable and not necessarily correct, and that a document planted before ingestion defeats both systems.
  - **"Abstention as a Feature":** no longer says deterministic abstention escapes miscalibration under shift.
  - **Conclusion, first paragraph:** "repeatable, not necessarily correct".
  - **Conclusion, second paragraph:** attribution is dropped from what transfers; it adds that a prompted LLM is safer on external data, names the by-construction properties, states that pre-ingestion poisoning defeats both systems, and ends on "repeatable, auditable decision layer with no instruction-following component".
- **Not changed (outside the requested scope; for the owner).** "Safety guarantee" wording remains:
  - `main.tex` around line 1237 ("practical meaning of the safety guarantee");
  - around line 1404 ("a worst-case safety guarantee");
  - the guarantee framing near lines 599, 928, 1146, 1154 and 1329 (mostly about by-construction properties).
- **Bibliography.** `main.tex` cites 99 keys; `references.bib` has 31 entries, 30 of them cited, so 69 cited keys are missing. One entry (`nguyen2024intent`) is uncited. The missing keys are listed in the handoff (2026-10-15 block); the full bibliography must come from Overleaf. No entry was invented.
- **Effect.** `check_ledger.py --sync-lines`: 51 line numbers synced, coverage 1,297/1,297, presence 534/534, 0 `main.tex` fails; the same three DIFFs outside `main.tex`. Braces, environments and refs balance; there is no LaTeX engine here.
- **Cost / regressions.** None measured; wording only.
- **Evidence.** `python evaluation/check_ledger.py -v`; the `main.tex` diff against `main_2026-10-15_before_nlpir_alignment.tex`.
- **Numbers updated.** None.

## Observation 49: Bibliography keys matched to the owner's `references.bib`; four author fields wrong

*Added 2026-10-15. Commit/branch: on top of `8d27d23`, `jonan`. Zero LLM tokens. `main.tex` edited (cite keys only); `references.bib` not touched (owner's file).*

- **Issue.** The owner added `references.bib` at the repo root (109 entries; no duplicate keys, braces balance). Eight of the 99 keys cited in `main.tex` did not resolve.
- **Check.** Crossref (`api.crossref.org/works/<DOI>`) was queried for the four entries whose first author disagreed with the old cite key. In all four, the old key's author is right and the new entry's `author` field is wrong:

  | Entry | Bib file says | Crossref says |
  |---|---|---|
  | `jing2024vdbmssurvey` (10.1007/s00778-024-00864-x) | Jing, Yikun | James Jie Pan, Jianguo Wang, Guoliang Li (VLDB J 33:1591-1615) |
  | `zhang2023hallucinationrobust` (10.1145/3583780.3614905) | Zhang, Yuyan | Yuyan Chen et al. (CIKM '23, pp. 245-255) |
  | `wang2025vericite` (10.1145/3767695.3769505) | Wang, Chunhui | Haosheng Qian et al. (SIGIR-AP '25, pp. 47-54) |
  | `huang2026c2cite` (10.1145/3773966.3777933) | Huang, Lei | Yue Yu et al. (WSDM '26, pp. 871-880) |
- **Fix.** On the owner's instruction, the seven cite keys in `main.tex` now use the bib file's keys:
  - `chen2023hallucinationdetection` -> `zhang2023hallucinationrobust`
  - `zhu2025llm4ir` -> `zhu2025llmir`
  - `abdullahi2025hallucinationrise` -> `abdullahi2025hallucinationreview`
  - `qian2025vericite` -> `wang2025vericite`
  - `yu2026c2cite` -> `huang2026c2cite`
  - `pan2024vectordb` -> `jing2024vdbmssurvey`
  - `douze2025faiss` -> `douze2025faisslibrary`

  The four author fields above are NOT fixed. They are the owner's to correct, and until then the printed references name the wrong authors. `honovich2022true` (TRUE) has no entry; the owner will add it.
- **Effect.** 98 of 99 cited keys resolve; 11 bib entries are uncited (harmless). The ledger is unchanged (coverage 1,297/1,297). Braces, environments and refs balance; there is no LaTeX engine here.
- **Numbers updated.** None.

## Observation 50: MultiHop-RAG, a new preregistered measurement; NLPIR's direction holds, its "no difference in correctness" does not

*Added 2026-10-17. Commit/branch: on top of `8d27d23`, `jonan` (uncommitted docs edits present; the core-file hashes are in each result's `run_info`). No pipeline code, threshold or default changed; no `RAG_*` override set. API use: 6 pilot baseline calls, 3 superseded pilot calls, 300 full-run calls to `openai/gpt-oss-120b`. Our arm made zero LLM calls.*

- **Issue.** NLPIR Section 4.8 (MultiHop-RAG) had no raw files, so its numbers were UNVERIFIABLE and kept out of `main.tex`.
- **What was done.**
  - **Preregistration:** written before any run (`docs/PREREGISTRATION_MULTIHOP.md`).
  - **Data:** downloaded from Hugging Face (`yixuantt/MultiHopRAG` at `71ac0d0b`, ODC-BY, hashes checked). It is 609 articles and 2,556 queries, so NLPIR's "609-article index" is the whole corpus.
  - **Index:** each article was written as `mh_NNN.txt` with a metadata header and indexed through the unchanged ingestion into a new store, `qdrant_db_multihop/`. That took 22,131 chunks and 92 minutes (NLPIR: 22,061).
  - **Sample:** seeded, 150 null plus 50 each of inference, comparison and temporal, run in shuffled order.
  - **Ours:** the decision-only harness, with retrieval not bypassed.
  - **Baseline:** E1 prompt with gpt-oss-120b on the same first-attempt retrieved passages.
  - **Code:** `evaluation/run_eval_multihop.py` (new) and `tests/test_run_eval_multihop.py` (22 tests, no network).
- **Amendment 1 (after the pilot, before any full-run query).** The pilot's fourth baseline request needed 10,176 tokens against the free tier's 8,000-token-per-request limit (HTTP 413). The baseline was therefore capped at the top 12 passages, which is what E1 itself sent (`max_chunks_sent: 12`). The decision used only the error, not any pilot outcome. The three pre-amendment pilot rows are kept as `*.superseded_amendment1`. The owner stopped the first pilot attempt while it was still loading; it had written no query rows and no cache files.
- **Effect** (`python evaluation/run_eval_multihop.py --report --tag mh`; 300/300 paired; Wilson 95%; exact McNemar):

  | Measure | Ours | Baseline | p |
  |---|---|---|---|
  | Null queries answered | 56/150 (37.3%) [30.0, 45.3] | 2/150 (1.3%) [0.4, 4.7] | 1.2e-14 |
  | Answerable not answered | 78/150 (52.0%), 77 of them conflicts | 110/150 (73.3%), 108 insufficient | 5.8e-5 |
  | Decision correct (strict) | 125/300 (41.7%) | 188/300 (62.7%) | 6.4e-7 |
  | Decision correct (lenient, exploratory) | 166/300 (55.3%) | 188/300 (62.7%) | 0.055 |

  Retrieval (ours, 399 gold articles): 89.0% retrieved across sub-queries, article recall@5 59.6% for the original question.
- **Predictions.** P1, P2, P3 and P5 held. **P4 failed.** The baseline's decisions are significantly more often correct under the preregistered strict grading.
- **Against NLPIR.**
  - **Matches in direction:** gap leak (NLPIR 21/57 vs 1/57), over-abstention (57.8% vs 79.7%), false conflicts as ours' main refusal mode, and retrieval (89.9%, 55.0%).
  - **Does not match:** NLPIR's "overall correctness does not differ (p = 0.48)". Here the baseline is better.
- **Cause, as far as the data says.**
  - **Our gate:**
    - it tests relevance and coverage, not whether the evidence contains the answer, so near-miss null queries pass (56 answered);
    - Stage 4 flags conflicts between articles without establishing that they concern the question (77 false conflicts on answerable queries, 41 on null ones);
    - this is failure patterns 1 and 2 in `claude.md`, at scale.
  - **The baseline:**
    - it refuses most answerable queries;
    - only 67.4% of gold articles were inside its 12 passages;
    - exploratory: it refused 38/60 answerable queries even when every gold article was sent, and 72/90 when some were cut, so the cap explains part, not all.
- **Cost / regressions.**
  - The comparison is asymmetric by Amendment 1 (the baseline sees at most 12 passages; ours validates about 30). This is reported, not corrected.
  - Answer content is not graded; decisions only, as in NLPIR.
- **Evidence.** `evaluation/results/mh_{ours,baseline}_multihop.ckpt.jsonl`, `mh_multihop_report.json`, `mh_sample.json`, `mh_full.log`. All gitignored, regenerable with the commands in the script header. The sample is now sealed: it is not to be used to choose or tune anything.
- **Numbers updated.**
  - `numbers.md`: new section 4b.
  - `docs/NUMBERS_LEDGER.csv`: 15 rows (NU-010 onward), status REPRODUCED, all recomputing from the report file.
  - NLPIR's own MultiHop numbers (NL-035 to NL-044) stay UNVERIFIABLE, because this measurement is not a reproduction of them.
  - `main.tex` was not edited.

---

## Observation 51: Every number-bearing doc now agrees with the ledger

*Added 2026-10-17. Commit/branch: on top of `aec628c`, `jonan`. No pipeline code, threshold or default changed; nothing run on Corpus 1, 2, 3, RAMDocs or MultiHop-RAG; no API key used. `main.tex` and the NLPIR PDF not edited.*

- **Issue.** `evaluation/check_ledger.py` failed on 3 rows, and several docs outside the ledger still quoted superseded numbers. The checker's `-v` mode also crashed on a Windows console.
- **Cause.**
  - Docs were written before the answerhood gate shipped (2026-08-24) or before the RAMDocs clean rerun (2026-10-14), and were never brought forward.
  - The NLPIR PDF's "31 of 48" uses the pre-margin Corpus 2 count.
  - The crash: `print` of U+2212 from the PDF text under cp1252.
- **Fix** (old values kept in labelled History notes, never deleted):
  - **`docs/STATUS.md`:**
    - invariance rows changed from pre-gate to gate-on values: C1 query_thanks 2/78 with 1 unsafe -> 1/78 with 0; C1 query_polite 1/78 with 1 -> 0/78 with 0; C2 query_polite 1/78 -> 0/78;
    - the paragraph after the table and the Problem 4 row no longer say politeness moves decisions in the unsafe direction;
    - new "External benchmarks" table (RAMDocs clean 85.2% vs 94.8% safe; MultiHop-RAG gap leak 56/150 vs 2/150, strict correct 41.7% vs 62.7%).
  - **`docs/RAMDOCS_COMPARISON.md`:**
    - new "Current result: clean rerun" section with the four-run table and the McNemar tests;
    - the 88.4% / 2.6% body is moved under a "History: the label-leaky run" heading;
    - the citation was already Wang et al.
  - **`docs/FUTURE_WORK.md`:**
    - "C1 92.3% / C2 80.8%" -> 96.2% / 89.7% (line 7 and the section 0 table);
    - section 6 invariance counts marked as the earlier pre-gate run, with the current counts given.
  - **`docs/REPRODUCE.md`:**
    - "every transform should print 0/78" corrected (the politeness transforms give 1/78 and 2/78);
    - test count 70 -> 169;
    - new sections: the external benchmark commands (sealed, re-grade only) and the ledger checker.
  - **`docs/HOW_IT_WORKS.md`:** test count 70 -> 169.
  - **`docs/CORPUS3_RESULTS.md`:**
    - a replication note (26.7% -> 26.1%, 40.4% -> 40.8%, 0/350 -> 0/351);
    - section 6 updated: qform completed at 37.5% (191/510); the bare-LLM baseline was never completed.
  - **`docs/CORPUS3_ANALYSIS_AND_FIXES.md`:** a one-paragraph replication pointer.
  - **`numbers.md`:**
    - section 0: the paper note now describes `main.tex`;
    - section 2: C1 query_polite margin-on cell now 0 / 0;
    - section 4: the clean rerun is named current at the top, and the 88.4% table and the pre-rerun reasoning sit under History headings;
    - section 5: 0/48 marked verified;
    - section 7: items 1, 13, 14 and 18 closed.
  - **Ledger:**
    - NL-048 now recomputes NLPIR's 31 as 17 + 14 (DERIVED, HISTORICAL);
    - ST-010 and ST-011 hold the new STATUS rows;
    - 21 new rows (ST-013 to ST-019, RC-004 to RC-012, FW-001, FW-002, C3-001 to C3-003);
    - lines synced.
  - **`evaluation/check_ledger.py`:** stdout set to `errors="replace"` so `-v` no longer crashes on Windows.
- **Effect.**
  - `python evaluation/check_ledger.py`: FAILED (3 DIFFs: NL-048, ST-010, ST-011) -> PASSED (570 rows: (a) 451 ok, (b) 570 ok, (c) 1297 ok, (e) 31 ok).
  - The 26 (d) warnings are NLPIR rows that are UNVERIFIABLE by design.
  - `python -m pytest tests -q`: 169 passed. No test encoded a stale number, so none was changed.
- **Cost / regressions.** None to the system. The stale-string check (e) still covers only `main.tex`, README, STATUS and RAMDOCS_COMPARISON. A trial over the other six docs found 14 hits, all already-labelled historical mentions, so it was not widened.
- **Evidence.** The checker output above, and `git diff` of the ten files.
- **Numbers updated.**
  - `numbers.md` sections 0, 2, 4, 5 and 7, as listed.
  - Still open: section 7 items 4, 9, 15 and 19.

---

## Template for new entries

```
## Observation N: <short title>

*Added YYYY-MM-DD. Commit/branch: <ref>.*

- **Issue.** What the system did wrong, or what changed.
- **Cause.** Why.
- **Fix.** What was changed (files, switches, defaults). State what was NOT changed.
- **Effect.** Measured before -> after, on which corpus, with the command used.
- **Cost / regressions.** Anything that got worse.
- **Evidence.** Result file, command, or doc section.
- **Numbers updated.** Which rows of numbers.md changed.
```

Add the new row to the master timeline above and set `Last synced` in `numbers.md`.

---

## Observation 52: MultiHop-RAG added to main.tex from the verified run

*Added 2026-10-17. Commit/branch: on top of `f1f3172`, `jonan`. No pipeline code, threshold or default changed; nothing run; no API key used.*

- **Issue.** The NLPIR paper reports MultiHop-RAG (Section 4.8) and `main.tex` did not. NLPIR's own numbers (121-query sample) have no raw files and stay UNVERIFIABLE.
- **Fix.** New `main.tex` subsection "External Validation: MultiHop-RAG" (`sec:multihop`, `tab:multihop`), a sentence in the abstract, and a sentence in the limitations paragraph, all written from the new preregistered 300-query run (Observation 50), not from NLPIR's figures.
  - It reports the unfavourable result in full: 56/150 vs 2/150 null queries answered, 52.0% vs 73.3% answerable not answered (77 of 78 are conflicts), strict decision accuracy 41.7% vs 62.7% (p = 6.4e-7), prediction P4 failed, and the Amendment 1 caveat (the baseline sees at most 12 passages; 67.4% of gold articles visible to it).
  - It states that NLPIR's "correctness does not differ" is not supported by this run.
- **Ledger.** 27 new `main.tex` rows (MH-001 to MH-027). Items recomputed from the checkpoint files on 2026-10-17: 38/60 and 72/90 baseline refusals, 41 null-query conflicts, lenient p = 0.055 (49 vs 71 discordant pairs); status RECOMPUTED, literal values noted.
- **Effect.** `check_ledger.py` passes: 1,356+ body numbers covered, 0 fails; 169 tests pass.
- **Not done.** No citation for the MultiHop-RAG paper (no key in `references.bib`; not invented). The paper text names the public release only.

---

## Observation 53: Paper review; 29 accuracy and claim fixes applied to `main.tex`

*Added 2026-10-17. Commit/branch: on top of `a5b2421`, `jonan`. Zero LLM tokens, nothing run except the ledger checker and `pytest`; no sealed set opened, `.env` not read. `main.tex` edited (backup `D:\Major Project_paper_backups\main_2026-10-17_before_part6_review.tex`); no pipeline code, threshold or default changed.*

- **Issue.** A read-only review (`docs/PAPER_REVIEW_2026-10-17.md`) recomputed 72 numbers from raw files (no measured value wrong) and audited every claim. Its findings:
  - one wrong explanation of a baseline score;
  - two differences computed from rounded percentages;
  - a word-number miscount;
  - the haystack sentence, which no current-system file supports;
  - several sentences that called safety or attribution "by construction" against the paper's own data and the NLPIR text;
  - wrong labels for the synthesis model, the Python version and the determinism evidence.
- **Cause.**
  - Text carried over from the v6 draft and never re-checked against later results.
  - The checker compares numbers, not wording, and does not see numbers written as words.
  - Two ledger rows subtracted rounded percentages.
- **Fix (owner approved P1 to P29; STRUCTURE, CUT and STYLE items left).**
  - **Accuracy:**
    - haystack sentence deleted (P1, option a);
    - baseline attribution loss explained correctly: Q035 one point, Q046 one point, re-graded from the stored replies with the experiment's own grader (P2);
    - synthesis model named by experiment (llama-3.3-70b-versatile for Corpora 1/2, gpt-oss-120b on external benchmarks; P3);
    - "Python 3.10" removed (P4);
    - determinism footnote now cites two full runs per corpus, 78/78 identical (P5);
    - "seven" -> "five" (P6);
    - 3.9 -> 3.8 and 23.0 -> 23.1 points, from counts (P7);
    - fixed-injection routing in the summary table 0.044 -> 0.000, attack success, with the routing-changed rate and the defended-LLM grading in footnotes (P8);
    - threshold provenance and the Discussion's calibrated list and cross-reference (P9, P10);
    - invariance paragraph no longer says the sensitivity was eliminated (P11);
    - "exactly" and "six limitations" removed (P12, P13).
  - **Claims:**
    - summary-table caption and prose now say only zero flips and the absence of an instruction-following component hold by construction (P14);
    - "0 of 32 by construction" -> "on this corpus" (P15);
    - "cannot ... worst-case safety guarantee" -> detected conflicts only, Corpus 2 Q045 named (P16);
    - attribution split into a by-construction format row and an empirical gold-pair row (16/16 -> 15/16) (P17);
    - "practical meaning of the safety guarantee" (P18);
    - parametric leakage (P19);
    - "independently authored" Corpus 2 -> "written separately by this project", five places (P20);
    - miscalibration (P21);
    - "unbreakable" and the unqualified "0 of 45" (P22);
    - conclusion root-cause and external-data sentences (P23, P24);
    - contributions 1 and 5, MultiHop added (P25);
    - the related-work gap (P26);
    - focus-presence scope, which also removes one em dash (P27);
    - "slightly" (P28);
    - NLI sweep range (P29).
- **Effect.**
  - `python evaluation/check_ledger.py --sync-lines -v`: PASSED, 597 rows; (a) 482 ok, (b) 597 ok, (c) 1,368 ok, (e) 31 ok; the 26 (d) warnings are the NLPIR rows, as before.
  - `python -m pytest tests -q`: 169 passed.
  - Braces balance, environments match, every `\ref` resolves.
- **Ledger.**
  - Updated with their real sources: MT-068 (now recomputes the two-run agreement), MT-119, MT-145 (gold-pair counts from the frozen files and the query files, replacing the hard-coded 3/3), MT-224 and MT-227 (from counts), MT-228, MT-271, MT-272, MT-373, MT-424, MT-430.
  - Added: MT-456 to MT-461.
  - Retired with their text: MT-358 and the haystack rows MT-402 to MT-406. The NLPIR rows NL-017 and NL-018 stay as the record of NLPIR's claim.
- **Cost / regressions.** None to the system. The paper now reports less: the haystack claim is gone.
- **Not done.**
  - STRUCTURE, CUT and STYLE items (P30 to P50), including the em dashes at the former lines 1841 and 1849, the `---` table cells, and the figure path (`\graphicspath`): with the current layout the three matplotlib figures still print as placeholders.
  - `honovich2022true` and the four wrong author fields in `references.bib`.
  - The MultiHop-RAG citation.
- **Evidence.** `docs/PAPER_REVIEW_2026-10-17.md`; `git diff main.tex docs/NUMBERS_LEDGER.csv`; the backup above.
- **Numbers updated.** `numbers.md` section 7 item 15 closed (haystack sentence removed from `main.tex`); no measured value changed.
