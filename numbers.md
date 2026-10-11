# NUMBERS.md: Single Source of Truth for Every Number

**Purpose.** One place where every headline number in the repo is written down
once, with the file it came from. If a number in any other document (README,
STATUS, paper, a report) disagrees with this file, one of them is wrong: find
out which, fix it, and log the fix in `RAG_System_Observation_Log.md`.

**Rules.**
1. Every row names its source. Prefer a raw result file or a command in
   [docs/REPRODUCE.md](docs/REPRODUCE.md). If the only source is a prose
   document, the row says so, and the row is lower trust.
2. When a number changes (new run, code change, corrected typo), update it here
   first, then update the other files to match, then add a log entry.
3. Never delete an old value silently. Move it to "History" with its date.
4. `evaluation/results/` is gitignored, so raw JSON is not in the repo. A row
   whose raw file is listed but absent from a fresh checkout cannot be
   re-verified from the repo alone. Those rows are marked `[raw not in repo]`.
   The 2026-10-10 re-run's result files are fingerprinted (SHA-256) in
   [docs/RERUN_MANIFEST_2026-10-10.md](docs/RERUN_MANIFEST_2026-10-10.md), which
   is tracked, so those rows can be checked against a regenerated run.
   Result files written from 2026-10-10 on carry a `run_info` block (commit,
   source hashes, effective switches), so a row's source file says what system
   made it. The expected values for the re-run are mirrored in
   `evaluation/expected_baseline.json`; change both together.
5. Query IDs are NOT unique across corpora. Corpus 1 and Corpus 2 each number
   their own 78 queries from Q001, so every ID exists in both and means a
   different question (C1 Q041 = employer pension contribution, C2 Q041 =
   minimum GPA to keep financial aid; C1 Q051 = relocation allowance, C2 Q051 =
   graduate TA stipend; C1 Q035 and C2 Q035 are both conflict queries about
   different policies). Always write `C1 Q041` or `C2 Q041`, never a bare `Q041`.

**Last synced: 2026-10-10**, after merging `origin/Testing` into `jonan`, then
re-run in full for Section 2 (corpora, security, invariance) at `7db6ff7`
(`evaluation/results/rerun_2026-10-10/`, Observation 30).
Built from `docs/STATUS.md` (rev 2026-08-24), `docs/CORPUS3_RESULTS.md`,
`docs/RAMDOCS_COMPARISON.md`. Arithmetic was re-checked for the Corpus 3 and
RAMDocs rows (all ratios and percentages reproduce). Sections 3 to 6 were not
re-run (sealed test, RAMDocs, and v6 experiments are out of scope by design).

---

## 0. Which system is which

| Label | Meaning | Where its numbers are |
|---|---|---|
| **v6 (paper-frozen)** | The system the paper `paper_assets/trust_before_text.tex` was written against. | Section 6 below; full tables in git: `git show 832736a:numbers.md` |
| **Current defaults** | Repo as of `docs/STATUS.md` 2026-08-24: Stage 0 provenance, Stage 4 preconditions, sufficiency focus-term veto, `ANSWERHOOD_MARGIN=5.5`. | Sections 1 to 5 |

The paper still quotes v6 (the tex contains the v6 figures 92.3% and 66.7%).
**The paper and the current system now disagree.** See Section 7, item 1.

Current default switches (all env-overridable, see `docs/REPRODUCE.md`):

| Switch | Default | Added |
|---|---|---|
| `REQUIRE_ASSERTIVE_SPANS` | on | Stage 4 precondition |
| `DIMENSIONAL_VETO` | on | Stage 4 precondition |
| `RAG_MIN_FOCUS_PRESENCE` | 0.5 | Stage 5 hard veto (Problem 2 fix) |
| `RAG_ANSWERHOOD_MARGIN` | 5.5 | shipped 2026-08-24; 0 restores pre-gate behaviour |
| `RAG_ANCHOR_ASYMMETRIC_QSPAN` | 0 (off) | candidate, shipped disabled |

---

## 1. Corpora

| | Corpus 1 (Meridian Grid, UK HR) | Corpus 2 (Ashcombe Falls, US university) | Corpus 3 (ContractNLI NDAs) |
|---|---|---|---|
| Authored by | this project | this project | external (Koreeda & Manning 2021) |
| Queries | 78 (46 answer / 16 conflict / 16 insufficient) | 78 (same composition) | Track A 510, Track B 240 |
| Role | tuned on | used for selection many times | sealed test, opened once 2026-08-31 |

Source: `docs/STATUS.md` Problem 3, `docs/CORPUS3_RESULTS.md` section 1.

---

## 2. Corpus 1 and Corpus 2, current defaults

Source: `docs/STATUS.md` "Current measurements" (rev 2026-08-24). Reproduce:
`python evaluation/run_eval.py --corpus {1,2}`.

| Metric | Corpus 1 | Corpus 2 |
|---|---|---|
| Decision accuracy | 96.2% (75/78) | 89.7% (70/78) |
| Conflict recall | 16/16 | 14/16 |
| Conflict precision | 1.000 | 0.875 |
| Attribution precision (right pair cited) | 1.000 | 0.875 |
| Gap queries wrongly answered | 0/16 | 0/16 |
| Unsafe answers (answered when should refuse/flag) | 0/32 | 1/32 (Q045 only) |
| False conflicts | 0 | 2 (credit-hours 21 vs 18, Dean's List vs aid GPA) |
| Over-cautious refusals (answer -> insufficient) | 3 (Q006, Q070, Q013) | 4 (Q023, Q064, Q059, Q074) |

Derived, not stated in STATUS: Corpus 2 precision 0.875 = 14/16 flagged, so 16
conflict reports with 2 wrong. Corpus 1 accuracy 75/78 = 96.15%.

### History (do not delete; add rows)

| Date | Change | C1 acc | C2 acc | C2 precision | C2 recall |
|---|---|---|---|---|---|
| v6 (paper) | frozen paper system | 92.3% | 66.7% | 0.43 | 16/16 |
| "previous revision" in STATUS | before Stage 4 preconditions | 92.3% | 80.8% | 0.600 | 15/16 |
| 2026-08-23 | pre-`ANSWERHOOD_MARGIN` (margin = 0) | 96.2% | 82.1% | 0.625 | 15/16 |
| 2026-08-24 | `ANSWERHOOD_MARGIN` = 5.5 shipped | 96.2% | 89.7% | 0.875 | 14/16 |
| 2026-10-10 | Zero-token re-run at `7db6ff7`, no code change (Observation 30). Every section 2 headline row reproduced. Differences: C2 `query_polite` changed decisions 1 -> 0 (margin on); C2 adversarial gap probes "unsafe before provenance" 14/24 -> 16/24 (Q055 urgency and aware flipped `conflict` -> `answer`; after provenance 0/24 and control 0/24 unchanged; C1 17/24 unchanged). `pytest` step failed at collection (missing `retrieval_module`), unrelated to these numbers. | 96.2% | 89.7% | 0.875 | 14/16 |

Measured 2026-10-10 (Observation 35): the two changes switched independently,
answerhood gate off (`RAG_ANSWERHOOD_MARGIN=0`), same code at `7db6ff7`.

| State | C1 acc | C1 unsafe | C2 acc | C2 precision | C2 false conflicts | C2 unsafe |
|---|---|---|---|---|---|---|
| neither (`RAG_MIN_FOCUS_PRESENCE=0`, preconditions off) | 92.3% (72/78) | 1/32 | 82.1% (64/78) | 0.600 | 10 | 2/32 |
| sufficiency fix only | 92.3% (72/78) | 0/32 | 80.8% (63/78) | 0.600 | 10 | 1/32 |
| Stage 4 preconditions only | 96.2% (75/78) | 1/32 | 83.3% (65/78) | 0.625 | 9 | 2/32 |
| both | 96.2% (75/78) | 0/32 | 82.1% (64/78) | 0.625 | 9 | 1/32 |

Each change has the same effect whichever comes first (sufficiency: C2 -1 query,
C1 0; preconditions: C2 +1, C1 +3), so the order does not change the end state.
STATUS's sequence (82.1% -> 80.8% -> 82.1%) is the "sufficiency first" path; the
other path goes 82.1% -> 83.3% -> 82.1%. The "sufficiency only" row reproduces
STATUS's "previous revision" row exactly (92.3% / 80.8%, precision 0.842 / 0.600).

### Security properties (same code, one pass)

Source: `docs/STATUS.md` "Security properties".

| Test | Corpus 1 | Corpus 2 |
|---|---|---|
| Injected text reaching the LLM prompt | 0/45 | not stated per corpus in STATUS |
| Routing decision changed by injection | 0/45 | not stated per corpus |
| Adversarial gap probes leaked (control) | 0/24 (0/24) | 0/24 (0/24) |
| Adversarial gap probes unsafe before provenance (gate on, margin 5.5) | 17/24 | 16/24 (was 14/24 in the committed file, which predates the margin; 14/24 reproduces with `RAG_ANSWERHOOD_MARGIN=0`) |
| Fabricated evidence accepted (control abstains) | 0/4 (4/4) | 0/4 (4/4) |
| Injection-hijack label audit | 20/45 corrected, 2 mislabels (`authority` style) | not stated |

### Invariance (changed decisions / refuse-to-answer flips, out of 78)

Source: `docs/STATUS.md`, pre-gate table; margin-on re-run text in Problem 1.
Re-run command: `RAG_ANSWERHOOD_MARGIN=5.5 python evaluation/invariance_harness.py --corpus {1,2}`.

| Transform | C1 changed / unsafe | C2 changed / unsafe |
|---|---|---|
| permute, duplicate, distractor, query_lower | 0 / 0 | 0 / 0 |
| query_thanks | 2 / 1 (pre-gate); 1 / 0 (margin on) | 2 / 0 |
| query_polite | 1 / 1 (pre-gate); unsafe 0 (margin on) | 0 / 0 (margin on, re-run 2026-10-10; was 1 / 0) |

---

## 3. Corpus 3 (ContractNLI), sealed test, Track A

Source: `docs/CORPUS3_RESULTS.md` section 2. Raw: `evaluation/results/c3_hypothesis_corpus3_test.json`, `..._ci.json` `[raw not in repo]`. Config frozen 2026-08-25 (amended 2026-08-28), test opened once 2026-08-31.

| Metric | Value | 95% CI (bundle bootstrap) |
|---|---|---|
| Accuracy | 26.7% (136/510) | [22.5%, 31.0%] |
| Always-answer floor | 77.6% (396/510) | n/a |
| Conflict precision | 0.122 (47/386) | [0.096, 0.149] |
| Conflict recall | 0.635 (47/74) | [0.554, 0.726] |
| Conflict F1 | 0.204 | [0.166, 0.242] |
| Attribution precision (internal gold) | 0.031 (12/386) | [0.016, 0.049] |
| Gap leaks | 3/40 | n/a |
| Unsafe answers | 29/114 | n/a |
| Gold mix | 396 answer / 74 conflict / 40 insufficient | n/a |
| Per-bundle accuracy | min 5.9%, median 23.5%, max 58.8% | n/a |

External evidence attribution (graded against ContractNLI annotator spans, `..._attribution.json`):
evidence recall 68.5% (1612/2355); evidence precision 14.8% (1875/12,637);
**external attribution precision 0.0% (0/350 conflict reports)**; unresolved
chunks 1.67% (215/12,852); unresolved conflict spans 19.

Baseline arms on Track A (`c3_baselines_corpus3_test.json` `[raw not in repo]`):

| Arm | Accuracy | Gap leaks | Unsafe |
|---|---|---|---|
| always_answer | 77.6% | 40/40 | 114/114 |
| always_abstain | 7.8% | 0/40 | 0/114 |
| retrieval_threshold (top chunk >= 0.6) | 77.6% (identical to always_answer) | 40/40 | 114/114 |

### Track B (240 LLM-authored queries)

Source: `docs/CORPUS3_RESULTS.md` section 4. Raw: `c3_open_corpus3_test.json` `[raw not in repo]`.

| Metric | Value |
|---|---|
| Accuracy | 40.4% (97/240); floor 48.8% (117/240) |
| Conflict precision / recall / F1 | 0.175 (10/57) / 0.159 (10/63) / 0.167 |
| Attribution precision (internal gold) | 0.018 (1/57) |
| Gap leaks | 18/60 |
| Unsafe answers | 65/123 (53%) |
| Gold mix | 117 answer / 63 conflict / 60 insufficient |

Not final (status per `docs/CORPUS3_RESULTS.md` section 6, but see Section 7
item 4): qform run, bare-LLM baseline (`openai/gpt-oss-120b`), Track B evidence
attribution. Do not cite numbers for these until a source file exists.

---

### Replication of the sealed test, 2026-10-10/11 (Observation 38)

Same frozen configuration (margin 5.5, no `RAG_*` override), same 30 bundles and
query files, stores rebuilt from `data_corpus3/`, run by `evaluation/rerun_corpus3.py`
at commit `3cb2e27` plus uncommitted runner code (no decision-layer change).
The raw `c3_*` files from 2026-08-31 are lost, so the left column is the
prose-only reported value; the right column is the first set of Corpus 3 numbers
with raw files and `run_info` behind them. Raw: `evaluation/results/c3_*_corpus3_test*.json`
(local, gitignored). zero LLM tokens. qform and the bare-LLM baseline were not run
(qform pending; bare-LLM needs a key).

| Metric | Reported 2026-08-31 | Replicated | |
|---|---|---|---|
| Track A accuracy | 26.7% (136/510) | 26.1% (133/510) | DIFF -3 queries |
| Always-answer floor | 77.6% | 77.6% | same |
| Conflict flagged / true positives / gold | 386 / 47 / 74 | 386 / 47 / 74 | same |
| Conflict precision / recall / F1 | 0.122 / 0.635 / 0.204 | 0.1218 / 0.6351 / 0.2043 | same |
| Unsafe answers | 29/114 | 29/114 | same |
| Gap leaks | 3/40 | 4/40 | DIFF +1 |
| Attribution (internal gold) | 0.031 (12/386) | 0.0337 (13/386) | DIFF +1 |
| External attribution precision | 0.0% (0/350) | 0.0% (0/351) | still zero |
| Evidence recall | 68.5% (1612/2355) | 69.4% (1634/2355) | DIFF |
| Evidence precision | 14.8% (1875/12,637) | 15.1% (1898/12,577) | DIFF (60 fewer validated chunks) |
| Unresolved chunks / conflict spans | 215 / 19 | 214 / 18 | DIFF -1 each |
| Bundle bootstrap CI, accuracy | [22.5, 31.0] | [22.2, 30.0] | DIFF |
| Per-bundle accuracy min / median / max | 5.9 / 23.5 / 58.8 | 5.9 / 23.5 / 58.8 | same |
| Baselines (always answer / abstain / retrieval threshold) | 77.6 / 7.8 / 77.6 | 77.6 / 7.8 / 77.6 | same |
| Track B accuracy | 40.4% (97/240) | 40.8% (98/240) | DIFF +1 |
| Track B conflict flagged / true positives | 57 / 10 | 59 / 12 | DIFF +2 / +2 |
| Track B precision / recall / F1 | 0.175 / 0.159 / 0.167 | 0.2034 / 0.1905 / 0.1967 | DIFF |
| Track B attribution (internal gold) | 0.018 (1/57) | 0.0339 (2/59) | DIFF |
| Track B gap leaks / unsafe | 18/60 / 65/123 | 20/60 / 65/123 | gap leaks DIFF +2, unsafe same |

Reading: the structural picture is unchanged (far below the floor, precision near
0.12, external attribution zero, unsafe count identical). The differences are a
few queries wide, concentrated at the answer / insufficient boundary on Track A
(conflict counts identical) and including two extra conflict reports on Track B.
Cause not established: the August environment was never recorded, and this
machine runs sentence-transformers 5.2.2, transformers 5.0.0, torch 2.10.0
(`docs/RERUN_MANIFEST_2026-10-10*.md`). Use the replicated column for anything
that needs a raw file behind it; treat both as the same experiment, not two
results. A same-machine check (Observation 39) found the system fully
deterministic here (one bundle, two fresh processes plus the stored batch: 0
differing decisions, bit-identical retrieval scores), so the drift from August is
a difference in environment or state, not run-to-run instability.
Pre-registered qform effect (prediction 6) is not yet measured.

## 4. RAMDocs (external benchmark, sealed single pass 2026-09-04)

Source: `docs/RAMDOCS_COMPARISON.md`. Raw: `evaluation/results/rd_full_ramdocs.json` (500 records; present in this checkout, but the folder is gitignored, so `[raw not in repo]` on a clean clone).

| Metric | Value |
|---|---|
| Safe rate (correct or justified abstention) | 88.4% (442/500) |
| Unsafe rate (asserted misinformation answer) | 2.6% (13/500) |
| Abstentions among the 442 safe | 157 |
| Abstentions with a misinformation doc present | 54.1% (85/157) |
| Abstentions with no misinformation doc present | 45.9% (72/157) |
| LLM calls per query (ours) | 1 (`openai/gpt-oss-120b` on Groq) |

Published comparators (Han et al., COLM 2025, Table 1, exact match, Llama-3.3-70B
unless noted): No RAG 5.8%, prompt-based RAG 32.6%, self-reflection 30.4%,
speculative RAG 30.6%, Astute RAG 31.8%, MADAM-RAG 34.4% (Qwen2.5-72B 26.4%,
GPT-4o-mini 28.0%). **Different metric from our safe rate**: do not put 88.4%
and 34.4% in one "accuracy" column.

---

## 5. Adversarial and LLM-baseline results quoted in the README and STATUS

| Claim | Number | Source | Trust |
|---|---|---|---|
| Adversarial probes, ours unsafe | 0/48 | `docs/STATUS.md` "Fixed in earlier rounds" | prose only |
| Adversarial probes, defended LLM baselines unsafe | 12/12 in each of three runs: llama-3.3-70b on C1 (`adversarial_baseline_corpus1.json`), gpt-oss-120b on C1 and C2 (`adversarial_baseline_gpt-oss-120b_corpus{1,2}.json`); 36 baseline probes in all, authority and aware styles only; gpt-oss C1 regex-only count is 10/12, adjudicated to 12/12 | raw files tracked in git | resolved 2026-10-10 (Observation 34); the README's "48" was our probe count, not the baselines' |
| Injected text reaching prompt | 0/45 | `docs/STATUS.md` | prose |
| Our synthesis injection grading | 18/45 -> 20/45 after grader fix | `docs/STATUS.md` | prose |
| Defended LLM injection grading | 0/45 -> 7/45 (hand-adjudicated) | `docs/STATUS.md` | prose |

---

## 6. v6 numbers the paper currently quotes (frozen, historical)

Full tables: `git show 832736a:numbers.md`. Headline values only:

| Metric | Corpus 1 (ours v6) | Corpus 1 (prompted LLM, E1) | Corpus 2 (ours v6) | Corpus 2 (baseline) |
|---|---|---|---|---|
| Decision accuracy | 92.3% (72/78) | 97.4% (76/78) | 66.7% (52/78) | 98.7% (77/78) |
| Conflict F1 | 0.842 | see git | 0.60 | 0.97 |
| Conflict precision | 0.727 (16/22) | see git | 0.43 (16 true / 21 false flags) | 1.00 |
| Conflict recall | 16/16 | see git | 16/16 | 15/16 |
| Unsafe answers (/32) | 0 | see git | 4 | 1 |

Source: `git show 832736a:numbers.md` sections 1a, 1d, 2a (`experiments_corpus2/our_decisions_corpus2.json`).

v6 experiments E1 to E5 (baseline, scale, injection, hardening, adaptive) are
described in `docs/archive/MASTER_REPORT.md`; their headline findings are
unchanged by later work (they were not re-run).

---

## 7. Known inconsistencies (open; fix or confirm, then move to the log)

| # | Where | Conflict | Needs |
|---|---|---|---|
| 1 | Paper vs current system | Paper quotes v6 (92.3% / 66.7%); current defaults give 96.2% / 89.7% | Decision: re-sync paper numbers or keep v6 as an explicitly labelled frozen snapshot |
| 2 | `README.md` "Current state at a glance" | Says C1 92.3%, C2 82.1%, unsafe 1/32 and 2/32, C2 recall 15/16; `docs/STATUS.md` says 96.2%, 89.7%, 0/32 and 1/32, 14/16 | Update README to match Section 2. **Closed 2026-10-10 (Observation 31).** |
| 3 | `docs/STATUS.md` Corpus 2 confusion matrix | Matrix sums to 64/78 = 82.1% (pre-margin) but the headline row says 89.7% | Re-run `run_eval.py --corpus 2` and replace the matrix. **Closed 2026-10-10 (Observations 30, 31).** |
| 4 | `docs/CORPUS3_RESULTS.md` section 6 | Says qform and bare-LLM runs are "in progress", yet commit `d309565` (2026-08-31) is titled as adding the bare-LLM baseline | Author to confirm and update. **Narrowed 2026-10-10 (Observation 34):** not a contradiction. The doc says the bare-LLM run covered 12/30 bundles and qform 22/30, so "in progress" fits a partial run, and the commit added the script plus that partial output. Still open: whether either run has since finished, and the raw `c3_*` files are in no git ref. |
| 5 | README vs STATUS on adversarial probes | README: defended LLM answered the attacker's policy on all 48 probes; STATUS: baselines 12/12 unsafe each | Reconcile denominators. **Closed 2026-10-10 (Observation 34):** README and STATUS reworded to the raw-file counts (section 5). |
| 6 | `docs/STATUS.md` "short answer" | "2 wrong reports out of 17"; precision 0.875 = 14/16 means 16 reports | Change 17 to 16 if 0.875 is right. **Closed 2026-10-10 (Observation 31).** |
| 7 | `docs/STATUS.md` Problem 1 "Scale" | Says 9 false conflicts on Corpus 2; that is the pre-margin count (now 2) | Add "pre-margin" or update. **Closed 2026-10-10 (Observation 31).** |
| 8 | `docs/STATUS.md` order of changes | 82.1% -> 80.8% (sufficiency fix) and 80.8% -> 82.1% (Stage 4 preconditions) both claimed, order unstated | Author to state the sequence. **Closed 2026-10-10 (Observation 35):** measured by switching each change independently (table under Section 2 History). Both claims are true and the effects are independent; STATUS's order is the sufficiency-first path. |
| 9 | Corpus 3 and 2 raw files | `evaluation/results/` is gitignored; Corpus 3 JSONs are not in this checkout at all | Decide whether to commit result JSONs or keep a manifest with hashes. **Partly done 2026-10-10:** hash manifest for the Corpus 1/2 re-run is tracked in `docs/RERUN_MANIFEST_2026-10-10.md`. Corpus 3 `c3_*` files are in no git ref (checked `git log --all`), so they cannot be recovered from the repo; the author must supply them or accept the rows as prose-only. **Update 2026-10-11 (Observation 38):** the sealed Track A and Track B were replicated and the files regenerated locally (hash manifest follows when the run's `collect` step finishes); the 2026-08-31 originals remain lost. |
| 10 | Old query-ID collisions | v6 numbers.md section 6 listed Q-number collisions across reports; not re-checked for the new docs | Read before citing any bare Q-number. **Closed 2026-10-10:** rule 5 above (always prefix with the corpus). |
