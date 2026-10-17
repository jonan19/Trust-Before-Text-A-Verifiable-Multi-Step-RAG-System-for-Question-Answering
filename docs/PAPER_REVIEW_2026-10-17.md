# Paper review: `main.tex` ("Trust Before Text"), 2026-10-17

Phase 1 of the Part 6 review. Read-only: no file was edited except this report. No evaluation
was run, no model was called, no sealed set was opened, `.env` was not read. Every value below
was recomputed from result files already in the repo (`evaluation/results/`, `experiments/`,
`experiments_corpus2/`, `data*/`) by scripts that read the per-query records directly, not the
ledger's expressions. `main.tex` at commit `9dbf386` (branch `jonan`), 2,816 lines.

---

## Summary verdict

1. **Numbers: sound.** The checker passes, and 72 independent spot checks over every abstract
   number and every table recompute from raw files with no mismatch in a measured value. The
   misses are elsewhere: one wrong explanation of a baseline score (line 1378), two rounded
   differences, one word-number count ("seven", line 519), and the haystack sentence, which no
   current-system file supports and the only file contradicts.
2. **Claims: several sentences say more than the evidence.** The worst ones call the unsafe
   rate "by construction" or a "worst-case safety guarantee". One table caption says every row
   except accuracy holds by construction, and another table says attribution "held". The
   paper's own introduction, its Corpus 2 results and the NLPIR text all contradict these.
3. **Consistency: the facts don't change between sections, but the labels do.** Synthesis is
   called "Llama-3", but the code default is `gpt-oss-120b`. Python is 3.10 in one place and
   3.11 in two others. "Every threshold calibrated on Corpus 1 alone" disagrees with the
   threshold table. Fixed-injection routing is 0.000 in one table and 0.044 in another. The
   "8-query replay" has no file, while two full 78/78 runs do.
4. **Argument: honest, but sprawling and version-mixed.** Frozen (v6) results, external
   benchmarks on the current system, then the fixes that define the current system appear in
   that order. The strongest parts are the adversarial separation and the RAMDocs and
   MultiHop sections. The weakest is the summary table and the close of the baseline section.
5. **Length: about 2x the NLPIR version.** About 15,200 prose words plus 30 tables and 6
   figures, roughly 24 to 27 two-column pages before references. An 8-page conference limit
   needs about 60% cut. The cuts are listed below, ranked by how little is lost.

---

## A. Number trace

### A.1 Checker

`python evaluation/check_ledger.py -v` (2026-10-17):

```
Ledger docs\NUMBERS_LEDGER.csv: 597 rows
  by status: REPRODUCED 56, RECOMPUTED 389, DERIVED 27, EXTERNAL 11, ACCEPTED_AS_IS 88, UNVERIFIABLE 26
(a) recompute: 478 ok, 0 fail, 0 warn
(b) presence: 597 ok, 0 fail, 0 warn
(c) coverage of main.tex: 1361 ok, 0 fail, 0 warn
(d) non-C1/C2 rule: 130 ok, 0 fail, 26 warn   (all 26 are NLPIR-PDF rows, UNVERIFIABLE by design)
(e) stale strings: 31 ok, 0 fail, 0 warn
LEDGER CHECK PASSED
```

What the checker cannot see (found by hand, details in A.3):
- **Numbers written as words** have no row: "seven" (519, wrong), "six" (498), "Seventeen of
  the nineteen" and "twelve of the nineteen" (1458 to 1460), "four decisions" (2317), "eight"
  (1931), "Forty-eight" (2196), "Fifteen" (2386), "nine" (1880).
- **Two differences recomputed from rounded percentages:** MT-224 "3.9 points" and MT-227
  "23.0 points" pass because the ledger subtracts the rounded `accuracy_pct` values.
- **A ledger constant that traces nothing:** MH-006 "about 30" is `=30`, a constant. The code
  default `RETRIEVAL_TOP_K = 30` (`orchestrator.py:45`) supports it, but the row should point
  there.

### A.2 Independent spot check (72 rows)

Wilson intervals at z = 1.96; exact McNemar is a two-sided binomial test on the discordant
pairs. "Frozen" files: `evaluation/results/baseline_corpus{1,2}.json`. "Current" files:
`evaluation/results/rerun_corpus{1,2}.json`. LLM baseline: `experiments/baseline_results.json`
and `experiments_corpus2/baseline_results_corpus2.json`.

| # | Paper location | As written | Ledger id | Source file | Recomputed | Result |
|---|---|---|---|---|---|---|
| 1 | Abstract 135-136 | 11-document, 78 queries | MT-001/002 | `data/ground_truth.json`, `data/queries.json` | 11 docs; 78 queries (46/16/16) | MATCH |
| 2 | Abstract 136 | 92.3% | MT-003 | frozen C1 | 72/78 = 92.31% | MATCH |
| 3 | Abstract 137 | 96.2% | MT-004 | current C1 | 75/78 = 96.15% | MATCH |
| 4 | Abstract 137 | 100% conflict recall | MT-005 | frozen C1 | 16/16 | MATCH |
| 5 | Abstract 138 | zero unsafe across 32 | MT-006 | frozen C1 | 0 of 32 non-answer queries answered | MATCH |
| 6 | Abstract 140 | 66.7% (89.7%) | MT-007/008 | frozen / current C2 | 52/78 = 66.67%; 70/78 = 89.74% | MATCH |
| 7 | Abstract 141 | 4/32 (1/32) | MT-0xx | frozen / current C2 | 4 gap answers; 1 (C2 Q045) | MATCH |
| 8 | Abstract 146 | 48 gap probes | MT-009 | `adversarial_gap_probes_corpus{1,2}.json` | 24 + 24, 6 per style x 4 styles | MATCH |
| 9 | Abstract 149 | 12 of 12, three runs | MT-010 | `adversarial_baseline_corpus1.json`, `..._gpt-oss-120b_corpus{1,2}.json` | 12/12, 12/12, 12/12 (authority, aware) | MATCH (gpt-oss C1 regex-only is 10/12, adjudicated 12) |
| 10 | Abstract 150 | abstained on all 48 | MT-011 | same | `unsafe_after` 0 + 0 | MATCH |
| 11 | Abstract 156 | 94.8% vs 85.2% | MT-012 | `rdc_{base,ours}_orig_ramdocs_clean.json` | 474/500, 426/500 | MATCH |
| 12 | Abstract 156 | 76.8% vs 31.4% | MT-013 | same | 384/500, 157/500 | MATCH |
| 13 | Abstract 157 | 18.0% vs 7.6% | MT-014 | same | EM 90/500, 38/500 | MATCH |
| 14 | Abstract 159-161 | 56 of 150 vs 2; 41.7% vs 62.7% | MH rows | `mh_{ours,baseline}_multihop.ckpt.jsonl` | 56, 2; 125/300, 188/300 | MATCH |
| 15 | Intro 270 | 0 of 45; 2 of 6 | MT-0xx | `experiments/injection_results.json`, `adaptive_results.json` | obeyed 0/45; LLM flips 2/6 (Q040, Q041) | MATCH |
| 16 | tab:results 1221-1227 | 92.3 (72/78); 1.000 (16/16); 0.727 (16/22); F1 0.842; 87.0 (40/46); 100 (16/16); 0/32 | MT-0xx | frozen C1 | 72; 16/16; 16/22 = 0.7273; 0.8421; 40/46 = 86.96; 16/16; 0 | MATCH |
| 17 | tab:confusion 1251-1253 | 40 6 0 / 0 16 0 / 0 0 16 | MT-0xx | frozen C1 | answer->conflict 6, else diagonal | MATCH |
| 18 | tab:ablation 1290-1291 | 67.9 (53/78), 83.3 (65/78) | MT-095/096 | v6 history only | not recomputable; ACCEPTED_AS_IS | NO FILE (C1, allowed) |
| 19 | tab:ablation 1292 | 92.3 (72/78) | MT-097 | frozen C1 | 72/78 | MATCH |
| 20 | NLI 1310-1312 | 0.965; 0.9996, 0.9998 | MT-100 ff | v6 figure data | no file; ACCEPTED_AS_IS | NO FILE (C1, allowed) |
| 21 | tab:baseline_confusion 1359-1361 | 45 0 1 / 1 15 0 / 0 0 16 | MT-1xx | E1 C1 | identical; errors Q035 (conflict->answer), Q072 (answer->insufficient) | MATCH |
| 22 | 1369-1371 | 1 flip (Q069), 0.987 | MT-1xx | E1 C1 | `baseline_inconsistent` only Q069; 77/78 = 0.987 | MATCH |
| 23 | tab:headtohead 1393-1397 | 92.3/97.4; 1.000/0.987; 0/16, 0/16; 16/16 vs 14/16 (2.875); 0/32 vs 1/32 | MT-117 ff | E1 C1; frozen C1 pairs | all as written; ours names the gold pair on 16/16 (from `conflict_pair`) | MATCH |
| 24 | 1377-1378 | "missing the two points on the conflict it failed to flag" | MT-118 | re-grade of stored replies with `grade_attribution` | Q035 lost 1 (not flagged), **Q046 lost 1** (values key "permit" vs reply "allowed") | **MISMATCH (explanation)** |
| 25 | tab:summary 1181-1185 | 92.3/97.4/66.7/98.7; recall 100/93.8/100/93.8; unsafe 0/1/4/1; flips 0/1.3/0/1.3; 0/45, 0/15 | MT-06x | frozen, E1 C1/C2, injection files | all as written; C2 E1 flip is Q041 | MATCH |
| 26 | 1431-1435 | 66.7 (52/78); 98.7; F1 0.84 -> 0.60; precision 0.43 (16 vs 21) | MT-12x | frozen C2, E1 C2 | 52; 77/78; 0.6038; 16/37 = 0.4324, 21 false flags | MATCH |
| 27 | 1443 | 26 points | MT-133 | frozen C1/C2 | 20/78 = 25.64 | MATCH (rounded) |
| 28 | 1447-1450 | 26 errors: 19 + 2 + 1 conservative, 4 unsafe | MT-13x | frozen C2 confusion | answer->conflict 19, insuff->conflict 2, answer->insuff 1, insuff->answer 4 | MATCH |
| 29 | 1458-1460 | Seventeen of nineteen; twelve of nineteen | none | frozen C2 `conflict_pair` | 17 of 19 answerable false conflicts involve the superseded registration policy or the handbook; 12 are the planted pair itself (6 + 6) | MATCH (no ledger row) |
| 30 | tab:corpus2 1478-1482 | 92.3/66.7/98.7; 0.84/0.60/0.97; 0.73/0.43/1.00; 1.00/1.00/0.94; 0/4/1 | MT-14x | frozen C1/C2, E1 C2 | E1 C2: 15/15 precision, 15/16 recall, F1 0.968 | MATCH |
| 31 | tab:heldvsdrifted 1496-1497 | Structural attribution (3/3) held | MT-1xx | `baseline_experiment.py:605` | **3 is a hard-coded constant**, not a measurement; frozen C2 cites the wrong pair on 1 of 16 true conflicts (Q045) | **NOT SUPPORTED** (see C.1) |
| 32 | 1534-1535 | first document correct in 476 of 500 | RD rows | `rdc_ours_orig` `doc_order_types` | 476 | MATCH |
| 33 | tab:ramdocs_main 1594 | 31.4 [27.5, 35.6]; 76.8 [72.9, 80.3] | MT-16x | `rdc_*_orig` | 157 -> [27.5, 35.6]; 384 -> [72.9, 80.3] | MATCH |
| 34 | tab:ramdocs_main 1595 | EM 18.0 [14.9, 21.6]; 7.6 [5.6, 10.3] | MT-16x | same | 90, 38; intervals as written | MATCH |
| 35 | tab:ramdocs_main 1596 | misinfo 2.8 [1.7, 4.6]; 1.0 [0.4, 2.3] | MT-16x | same | 14, 5; as written | MATCH |
| 36 | tab:ramdocs_main 1597 | safe 85.2 [81.8, 88.0]; 94.8 [92.5, 96.4] | MT-16x | same | 426, 474; as written | MATCH |
| 37 | tab:ramdocs_main 1598 | 54.1 (85/157); 54.4 (209/384) | MT-16x | same | refused with a misinfo doc present: 85, 209 | MATCH |
| 38 | tab:ramdocs_main 1599 | 78.4/4.1 of 343; 77.6/4.3 of 116 | MT-16x | same | 269/343, 14/343; 90/116, 5/116 | MATCH |
| 39 | tab:ramdocs_published 1615-1622 | 5.8 ... 28.0 EM | EXTERNAL | Wang et al. Table 1 | not recomputable (published) | EXTERNAL |
| 40 | 1627-1631 | p<1e-8; p=0.022; p<1e-12; gold p=0.90; misinfo share p=1.0 | MT-17x | paired `rdc_*_orig` | safe 10 vs 58, p = 2.4e-9; misinfo 11 vs 2, p = 0.0225; EM 56 vs 4, p = 9.1e-13; Fisher 0.897; 1.0 | MATCH |
| 41 | 1632 | 60 (17%) unscored | MT-17x | `rdc_ours_orig` | 60/343 = 17.5% | MATCH (17.49) |
| 42 | 1637-1638 | strict 71.6 vs 94.2 | MT-18x | `strict_outcome` | 358/500, 471/500 | MATCH |
| 43 | 1639-1641 | shuffled: 500 identical; 85.4 (4.0, 18.6); 93.6 (1.6, 8.0) | MT-18x | `rdc_*_shuf` | 500/500 same refuse decision; 427, 20, 93; 468, 8, 40 | MATCH |
| 44 | 1662-1663 | 426 safe = 157 + 269 | MT-19x | `rdc_ours_orig` | 157 refusals + 269 safe answers | MATCH |
| 45 | 1669-1675 | 243 (48.6%); [46.0, 62.1]; p=0.175; 35.0 vs 28.0, p=0.10 | MT-19x | `rdc_ours_orig` | 243; Clopper-Pearson; binom 0.17498; 85/243, 72/257, Fisher 0.102 | MATCH |
| 46 | tab:ramdocs_abstain 1688-1689 | 85 / 54.1; 72 / 45.9 | MT-19x | same | 85, 72 | MATCH |
| 47 | 1715-1716 | 609; 2,556; 22,131 chunks | MH-001/002 | `mh_sample.json` | as written | MATCH (via checker) |
| 48 | 1725 | about 30 | MH-006 | ledger constant `=30` | `orchestrator.py:45` default 30 | MATCH (weak row) |
| 49 | 1726 | 67.4% gold visible | MH rows | `mh_multihop_report.json` | 67.4 | MATCH |
| 50 | tab:multihop 1739 | 56 (37.3%) vs 2 (1.3%); p 1.2e-14 | MH rows | ckpt files | 56 vs 2 discordant -> 1.19e-14 | MATCH |
| 51 | tab:multihop 1740 | 78 (52.0%) vs 110 (73.3%); p 5.8e-5 | MH rows | ckpt files | 15 vs 47 discordant -> 5.78e-5 | MATCH |
| 52 | tab:multihop 1741 | 125 (41.7%) vs 188 (62.7%); p 6.4e-7 | MH rows | ckpt files | 48 vs 111 -> 6.35e-7 | MATCH |
| 53 | 1746-1757 | intervals [30.0, 45.3], [0.4, 4.7], [36.2, 47.3], [57.1, 67.9]; 77 of 78; lenient 55.3 vs 62.7, p=0.055 | MH rows | ckpt files | all as written; 49 vs 71 -> 0.0548 | MATCH |
| 54 | 1763-1769 | 77 and 41 false conflicts; 89.0%; 59.6%; 38 of 60; 72 of 90 | MH rows | ckpt + report | 77, 41; 89.0; 59.6; 38/60; 72/90 | MATCH |
| 55 | 1887-1893 | 9 -> 2; 0.625 -> 0.875; 0.583 -> 0.875; 82.1 -> 89.7; 15/16 -> 14/16 | MT-2xx | `sweep_am_0_corpus2.json`, current C2 | am_0: 82.1, 0.625, tp 15; current: 89.7, 0.875 | MATCH (0.583 from STATUS, ACCEPTED_AS_IS) |
| 56 | tab:fixes_headline 1910-1915 | 92.3/96.2/66.7/89.7; 0.727/1.000/0.432/0.875; 16/16/16/14; F1 0.842/1.000/0.604/0.875; attr ---/1.000/---/0.875; unsafe 0/0/4/1 | MT-2xx | frozen and current | all as written | MATCH |
| 57 | 1923 | 3.9 points | MT-224 | frozen / current C1 | 3/78 = **3.85** | **ROUNDING** (3.8 exact, 3.9 = 96.2 - 92.3) |
| 58 | 1928 | 23.0 points | MT-227 | frozen / current C2 | 18/78 = **23.08** | **ROUNDING** (23.1 exact) |
| 59 | tab:ci_mcnemar 1968-1969 | 72 [84.2, 96.4] ... 77 [93.1, 99.8] | MT-23x | frozen, current, E1 | all six intervals as written | MATCH |
| 60 | tab:ci_mcnemar 1970-1975 | recall 16 16 15 16 14 15; precision; unsafe with intervals; refusals 38 35 32 48 35 31; abstained on answerable 6 3 1 20 4 0 | MT-23x | same | all as written | MATCH |
| 61 | tab:ci_mcnemar 1977-1978 | 0.22, 1.0, 4.2e-7, 0.016; unsafe 1.0, 1.0, 0.375, 1.0 | MT-24x | paired per query | acc 1 vs 5 -> 0.219; 2 vs 3 -> 1.0; 1 vs 26 -> 4.17e-7; 0 vs 7 -> 0.0156; unsafe 0 vs 1, 0 vs 1, 4 vs 1 -> 0.375, 0 vs 0 | MATCH |
| 62 | tab:errors_component 2011, 2016 | 5/1/0, 0/0/0, 17/4/0, 2/0/0; totals 6 3 26 8 | MT-25x | `conflict_kind` in frozen and current | nli 5 + numeric 1; none; nli 17 + numeric 4; nli 2; errors 6, 3, 26, 8 | MATCH |
| 63 | 2024-2027 | top 30; 62 queries; recall@5 1.0; @1 0.847; MRR 0.992 | MT-259 ff | `retrieval_recall_corpus{1,2}.json` | 30; 62; 1.0; 0.8468; 0.9919 (both corpora) | MATCH |
| 64 | 2033-2041 | 22 docs, 135 chunks; 94.9 (74/78), 0.889; 88.5 (69/78), 0.778, 2/32 | MT-26x | `merged_corpora.json` | as written | MATCH |
| 65 | 2043-2046 | N in {2..80}, all 20 haystacks at every N, [84, 100]; LLM up to N=40 | MT-402 to 406 | none for the current system; `experiments/haystack_results.json` (v6) | v6 file: N only up to 40; ours recall 0.75 (N=2) -> 0.50 (N=40); LLM 1.00 -> 0.75 | **UNTRACEABLE, and contradicted by the only file** |
| 66 | tab:sensitivity 2098-2105 | NLI 0.80-0.99; avg 0.55-0.75; coverage 0.35-0.75 rows | MT-27x | `sweep_*_corpus{1,2}.json` | every run file matches its row (e.g. avg 0.68: 94.9/88.5; cov 0.50: C1 unsafe 1/32; cov 0.75: 89.7/85.9) | MATCH (runs exist only at 0.80, 0.94, 0.99 for NLI) |
| 67 | tab:sensitivity 2107-2115 | margin 0 row; margins 3-8, span floors, lexical gate | MT-28x | `sweep_am_0` for margin 0 | 96.2/82.1, 0.625, 15 | MATCH for margin 0; others ACCEPTED_AS_IS (NLPIR) |
| 68 | tab:component_ablation 2130, 2136 | default; no query conditioning | MT-29x | `sweep_default`, `sweep_am_0` | as written | MATCH; the other 9 rows ACCEPTED_AS_IS |
| 69 | tab:security_current 2168-2174 | 0/45, 0/45, 0/24, 0/24, 0/4, 0/4, 24/24 | MT-30x | injection, gap probes, `fabricated_evidence_corpus{1,2}.json`; poisoning none | 0, 0, 0, 0, 0 (control abstains 4/4), 0; 24/24 has no file | MATCH; 24/24 ACCEPTED_AS_IS (numbers.md s7 item 19) |
| 70 | tab:adversarial_separation 2214-2217; 2229-2234 | 0/24, 12/12, 12/12, ---, 0/24; p = 4.9e-4, 1.2e-7; 33 of 48 (17 + 16) | MT-31x | gap probe files | as written; 2 x 0.5^12 = 4.88e-4; 2 x 0.5^24 = 1.19e-7; `unsafe_before` 17 + 16 | MATCH |
| 71 | tab:injection 2402-2405 and text 2410-2423 | undefended 1.000/0.733/1.000/0.911; defended 0; routing 0; synthesis 0.133/0.200/0.867/0.400; survived 45; changed Q009, Q015 | MT-34x | `experiments/injection_results.json` | 15/15, 11/15, 15/15, 41/45; 0; 0; 2/15, 3/15, 13/15, 18/45; 45; Q009 and Q015 (authority, to conflict) | MATCH |
| 72 | 2436-2440, tab:hardening, tab:adaptive, 2474-2475 | C2 spot-check 0/15, 0/15, 15 survived, 5 queries; hardened 0/45; 2/6, 0/6, 4/4, 4/4; 14 of 15 | MT-35x ff | `injection_spotcheck_corpus2.json`, `hardening_injection.json`, `adaptive_results.json`, `clean_after.json` | 0, 0, 15, 5 qids; 0/45; Q040 and Q041; gap 4 and 4; 14/15 | MATCH |

Also checked, outside the table:
- **tab:invariance:** 0/78 on four transforms; query_thanks 1/78 (C1 Q010) and 2/78 (C2 Q009,
  Q019); query_polite 0/78. All three changes are answer -> insufficient, as the footnote says.
- **tab:constants_full:** all 20 values equal the code defaults in `validation.py` (lines
  249-252, 254, 278, 290, 298, 304, 310, 354, 380, 438, 449, 455, 969, 998, 1004, 1195, 1196).
  `retrieval_scoring.py` maps cosine 0.35 to a 0.60 floor, as the appendix says.
- **tab:thresholds:** prefetch 20 (`qdrant_retrieval.py:51`) and faithfulness 0.70
  (`synthesis.py:58`) match.
- **Corpus 2 ground truth:** 11 docs, **46 facts**, 4 conflicts, 6 gaps (Corpus 1 has 45 facts).

### A.3 Numbers the checker misses

| Location | As written | Check | Result |
|---|---|---|---|
| 498 | "None of these six" | 6 citations (yang, li, liu, yu, zhang, darwish) | MATCH |
| 519 | "none of these seven" | the retrieval-quality list has 5 citations; with the 3 systems-level ones it is 8 | **MISMATCH** |
| 1458-1460 | Seventeen / twelve of nineteen | recomputed above (row 29) | MATCH, no ledger row |
| 1780 | "the six limitations identified in Section limitations" | the Limitations section names no list of six | **UNTRACEABLE** |
| 1880 | "nine of Corpus 2's false conflicts" | pre-margin false conflicts are 9 (`sweep_am_0`: 24 flagged, 15 true) | MATCH |
| 1931 | "eight remaining errors" | current C2: 4 + 1 + 1 + 2 = 8 | MATCH |
| 2196 | "Forty-eight" | 24 + 24 | MATCH |
| 2317 | "changed four decisions" | `docs/STATUS.md:484` (prose only); no result file | ACCEPTED_AS_IS-type, **no ledger row** |
| 2386 | "Fifteen answerable queries" | 15 qids x 3 styles = 45 | MATCH |
| 1015-1016 | "20 active ... other 14" | 20 rows in Appendix B; 3 + 3 + 14 | MATCH |

---

## B. Claim audit

Verdicts: **OK** (supported as stated), **SOFTEN** (true but worded beyond the evidence),
**OVER** (says more than the evidence or contradicts it), **NONE** (no test behind it).

### B.1 Structural (hold by construction)

| Line | Claim | Support | Verdict |
|---|---|---|---|
| 128-130, 599, 931-934 | The LLM is called only after a PASS; on CONFLICT or INSUFFICIENT it is never called | code path (orchestrator), Fig. 1 | OK |
| 146, 2416, 2563-2565 | Injected text cannot change routing; decision has no instruction-following component | injection 0/45 obeyed, C2 0/15; design | OK |
| 217-218, 1142 | Determinism holds by construction; consistency = 1.0 | design; two full runs per corpus give 78/78 identical (frozen: `baseline_corpus{1,2}` vs E1 `ours_decision`; current: `rerun` vs `sweep_default`) | OK, but the footnote cites the wrong evidence (C.1 item 4) |
| 2565-2566, 1872-1875 | Unfingerprinted evidence is discarded | gap probes 0/48, fabricated 0/4 per corpus | OK |
| 2566-2569 | Reordering, duplicating, adding distractors changes no decision | invariance 0/78 x 3 transforms x 2 corpora | SOFTEN: measured on 156 query runs; worded as a guarantee (B.6) |
| 1379 | "our unsafe-answer rate is 0 of 32 by construction" | measured 0/32 on C1; 4/32 on C2 frozen; the introduction (217-221) says safety is empirical | **OVER** |
| 1406 | "Trust Before Text cannot [answer a contradicted query], because the model is never reached on a conflict" | only on a *detected* conflict; C2 Q045 is a real conflict the system answers | **OVER** |
| 1407 | "a worst-case safety guarantee" | no worst-case bound exists; C2 and MultiHop show unsafe answers | **OVER** |
| 1168-1170 | tab:summary caption: "every other row holds by construction wherever it applies" | the table's own unsafe row drifts 0 -> 4; tab:heldvsdrifted calls recall empirical; NLPIR: "every other row is empirical" | **OVER** |
| 1496-1497, 1439 | "Structural attribution (3/3) ... held"; "determinism and structural attribution do not move at all" | the 3/3 is a constant (`baseline_experiment.py:605`); frozen C2 cites the wrong pair for Q045; NLPIR: "nor does attribution" transfer | **OVER** |
| 2321 | the "Thanks!" fix "eliminated the sensitivity by construction" | tab:invariance still shows query_thanks 1/78 and 2/78; STATUS says only the focus terms are now identical | **OVER** |
| 2430 | "a guarantee (0 by construction, unbreakable by a stronger prompt)" | routing has no prompt to break; "unbreakable" reads as general security | SOFTEN |
| 239-242 | Contribution 1: "safe abstention is enforced by the pipeline" | abstention is enforced; that it is *safe* is empirical | SOFTEN |

### B.2 Statistical (measured on a sample)

| Line | Claim | Support | Verdict |
|---|---|---|---|
| 135-141, 1204-1210 | C1 92.3%, 100% recall, 0/32; C2 66.7%, 4/32; after fixes 96.2% / 89.7% | files (A.2) | OK; a training metric, as Limitations says |
| 1940-1954 | Intervals overlap; "neither system is obviously unsafe" | tab:ci_mcnemar | OK, and a good model of the project's rule |
| 1594-1599, 1627-1641 | RAMDocs table and tests | `rdc_*` | OK |
| 1739-1769 | MultiHop table and mechanisms | `mh_*` | OK |
| 2024-2041 | Retrieval recall; merged index | files | OK |
| 2043-2046 | Haystack: ours detects in all 20 at every N up to 80 | no current file; v6 file says the opposite | **NONE (contradicted)** |
| 2053-2054 | NLI cutoff "identical from 0.80 to 0.99" | runs at 0.80, 0.94, 0.99 only | SOFTEN |
| 2061-2082 | Component ablations | 2 of 11 rows have files; 9 ACCEPTED_AS_IS; paragraph-level row is from an earlier run (stated) | OK as labelled |
| 2240-2242 | Pre-ingestion poisoning 24/24, 0/12 clean | no file on any branch | ACCEPTED_AS_IS (open item 19) |
| 1312 | 0.9996 / 0.9998 / 0.965 | v6 figure data only | ACCEPTED_AS_IS |
| 2420 | defended LLM "resisted all 45 under the original grader" | file: 0 flagged by the original grader; screen 12; one reader's pass 4 to 9 | OK as qualified; but 2478 drops the qualifier (B.3) |

### B.3 Comparative (X beats Y)

| Line | Claim | Support | Verdict |
|---|---|---|---|
| 143-145 | "A well-prompted model can slightly exceed our accuracy" | C1 97.4 vs 92.3 (p = 0.22); C2 98.7 vs 66.7 (p = 4.2e-7) | SOFTEN: "slightly" is true for C1 only |
| 145-151 | "Under attack the gap widens"; 0/48 vs 12/12 x 3 | gap probe files; McNemar | OK (the paper notes provenance is any pipeline's to adopt, 2234-2236) |
| 154-161 | RAMDocs and MultiHop: prompted LLM safer | files | OK, and stated plainly |
| 264-266 | Contribution 5: "a prompted LLM is safer but our gate answers far more correctly" | RAMDocs EM 18.0 vs 7.6 | SOFTEN: true for RAMDocs EM; MultiHop (strict correctness 41.7 vs 62.7) is omitted from the contributions |
| 1366-1380, tab:headtohead | Ours wins determinism, attribution, safety on C1 | 0 vs 1 flip; 16/16 vs 14/16; 0/32 vs 1/32 (p = 1.0) | SOFTEN: the safety and attribution gaps are one query each and not significant (the paper says so at 1947-1954, not here) |
| 2478 | "the defended LLM already used to reach 0 of 45" | original grader only; screen 12, hand 4 to 9 | **OVER** without the qualifier |
| 2503-2518 | Adaptive: LLM flipped 2/6, ours 0/6 | file | OK, stated as an existence proof |
| 2539-2540 | Hardened synthesis "reaches parity with a defended model" | 0/45 vs 0/45 (original grader) | OK as qualified |

### B.4 Causal (X because Y)

| Line | Claim | Support | Verdict |
|---|---|---|---|
| 194, 2616-2618 | "The root cause is not retrieval quality"; "the primary bottleneck ... is not retrieval quality but the absence of a ... gate" | 11-doc indexes have recall@5 = 1.0 (the paper itself calls this an easy setting, 2029-2030); on MultiHop, retrieval is fine *and* the gate is worse than the LLM | **OVER**: the gate's presence did not remove the errors on external data |
| 1156-1158 | "A lower accuracy number is the cost of the guarantee" | errors come from false conflicts (tab:errors_component), not from determinism | **NONE** |
| 1462-1466 | C2 precision collapse caused by two co-retrieved documents | 17 of 19 and 12 of 19 recomputed | OK |
| 1759-1764 | MultiHop errors from relevance-not-answerhood and query-unscoped conflicts | 77 + 41 false conflicts; 56 near-miss nulls | OK as far as the data says (mechanism inferred, not tested) |
| 2232-2233 | Abstentions come from provenance, not the rest of the gate | provenance off: 33/48 answered | OK |
| 2417-2418 | Routing changes went to CONFLICT "because the poisoned value was caught contradicting the real one" | 2 cases to conflict | OK (plausible; not separately tested) |
| 391-393 | Deterministic abstention "does not depend on a confidence estimate that can itself be miscalibrated under shift" | Discussion 2605-2606 says the gate's thresholds can be just as miscalibrated | **OVER** (self-contradiction; Obs 48 fixed only the Discussion copy) |
| 226-228 | "the model cannot leak parametric knowledge into a case where the evidence does not support an answer" | C2 frozen 4/32 gaps answered; MultiHop 56/150 nulls answered: the gate can pass such a case and then call the model | **OVER** |
| 897-899 | Focus presence "is what refuses a question the corpus genuinely does not cover" | fixes C1 Q051 and C2 Q017; MultiHop shows near-miss nulls pass | SOFTEN (scope to Corpora 1 and 2) |

### B.5 Scope (what the paper says it does not show)

| Line | Claim | Verdict |
|---|---|---|
| 1105-1110, 2655-2662, 2706-2707 | Corpora self-authored, used for selection, no held-out data | OK, and the strongest framing in the paper |
| 1543-1549, 1699-1709 | RAMDocs is closed-book; not a determinism check of answers | OK |
| 1726-1728, 1771-1774 | MultiHop asymmetric by Amendment 1; supports only the structural claim | OK |
| 2353-2366, 2520-2532 | Non-goals: generation not injection-proof; no immunity to pre-ingestion poisoning | OK |
| 2729-2730 | "External validation on legal-domain text is ongoing and not reported here." | OK (the only Corpus 3 trace allowed) |
| 138, 264, 1099, 1416, 2634 | "a second, independently authored corpus" | **OVER**: both corpora were written by this project (2706); "independently" reads as a third party |
| 1100, 1419-1422 | Corpus 2 as a "held-out generalization test" for the frozen system only | OK as qualified |

### B.6 Strong words, by line

- **"guarantee":** 191, 309, 430, 469, 477 (prior work, fine); 602, 1149, 1157, 1168, 1240,
  1332, 1407, 1508, 1708, 2329, 2430, 2541, 2545, 2551, 2562, 2736.
  - 1240, 1407, 1157 and 1168 attach it to safety or accuracy rather than to the
    by-construction properties. These are the four to change.
- **"by construction":** 146, 218, 228, 268, 1106, 1142, 1169, 1192, 1367, 1379, 1496, 1497,
  2321, 2358, 2393, 2416, 2430, 2494, 2562, 2658.
  - 1169, 1379, 1497 and 2321 are wrong (B.1).
  - 2494 (adaptive caption) "resists conflict-suppression by construction" is fine for routing.
- **"never":** 1406 and 1239 (B.1) and 2442. At 2442, "a domain ... the system had never
  seen" is true only for the frozen run; that is acceptable because the spot-check was frozen.
- **"generalizes":** 2637 says "what generalizes is repeatability". That is fine.
  - 1019 and 1100 call Corpus 2 a "generalization test". That holds for the frozen system
    only. Line 1100 says so; line 1019 does not.
- **"robust", "proves", "state of the art":** none applied to this system.
- **"unbreakable":** 2430 (B.1).

The project's rule ("never defend a change with a statistical number alone"): the post-fix
section mostly follows it. It defends the answerhood gate by mechanism and by the invariance
result, not by 89.7% alone (1877-1894). The one place that leans on statistics alone is the
assertive-span paragraph (1839-1850), which argues from transfer to Corpus 1. That is the
legitimate kind under the project's own Overfitting Test.

---

## C. Inconsistencies

### C.1 Inside the paper, or paper vs repo

1. **Synthesis model.** The text says "a Groq-hosted Llama-3 model" (913, 962, table line
   983). The code default is `openai/gpt-oss-120b` (`llm_interface.py:53`). The C1 and C2
   experiments used `llama-3.3-70b-versatile` (`experiments/baseline_results.json` meta). The
   RAMDocs section says gpt-oss-120b is "the model our synthesis uses here" (1529-1530).
   NLPIR states both, by experiment.
2. **Python version.** "Python~3.10" (950) against "Python 3.11" (977) and "3.11.9" (1077).
3. **Thresholds.**
   - "Every threshold in Table~\ref{tab:thresholds} was calibrated on Corpus 1 alone" (1412).
     The table's caption and lines 1013-1015 say three were selected on both corpora.
   - Discussion 2580-2581 lists only the three Corpus 1 thresholds as "calibrated".
4. **Determinism evidence.**
   - The footnote "verified by an 8-query replay" (1193-1194) has no file.
   - NLPIR says "two full Corpus-1 runs, 78/78 identical".
   - The repo has two full runs per corpus with 78/78 identical decisions, for both the
     frozen system (`baseline_corpus{1,2}.json`, 2026-09-28 commit, vs E1's `ours_decision`,
     2026-08-03) and the current system (`rerun_corpus{1,2}.json` vs
     `sweep_default_corpus{1,2}.json`).
5. **Fixed-injection routing.** tab:injection gives ours routing ASR 0.000.
   tab:adversarial_summary gives 0.044 in an "attack success rate" column; the footnote says
   it is the routing-changed rate, toward CONFLICT.
6. **Defended LLM on fixed injection.** The text at 2420 is qualified ("under the original
   grader"). tab:adversarial_summary (0.000) and line 2478 ("to reach 0 of 45") are not, and
   Observation 42 measured 4 (strict) to 9 (generous).
7. **Attribution.**
   - tab:heldvsdrifted says "held, by construction".
   - tab:fixes_headline says frozen attribution was not tracked ("---"), yet it is computable
     from the files: C1 frozen 16/16 true conflicts cite the gold pair; C2 frozen 15/16 (Q045
     wrong).
   - NLPIR says attribution does not transfer.
8. **Invariance.** The table shows query_thanks 1/78 and 2/78, but the paragraph after it says
   the fix "eliminated the sensitivity by construction" (2316-2321).
9. **Unsafe safety framing.**
   - 217-221 says safety is empirical.
   - 1379 says 0/32 "by construction".
   - 1168 says every row but accuracy holds by construction.
10. **False-conflict counts on Corpus 2 frozen.** "21 false ones" (1435), then "the nineteen
    false conflicts" (1458). Both are right (21 flags; 19 on answerable queries), but the
    second needs "on answerable queries".
11. **Corpus 2 "matches Corpus 1's structure exactly"** (1423). It has 46 facts, not 45 (minor).
12. **Section reference.** Discussion 2582 says the Limitations section reports the
    second-corpus test. That is `sec:corpus2`.
13. **"addressed the six limitations identified in Section limitations"** (1780): there is no
    list of six.
14. **Unlabelled frozen tables.** Each is frozen per the text at 1115-1117 but not in its own
    caption: tab:results, tab:confusion, fig:confusion_heat, tab:ablation, tab:corpus2,
    tab:heldvsdrifted. A reader who lands on a table sees 92.3% / 66.7% without "frozen",
    next to 96.2% / 89.7% elsewhere. tab:summary, tab:fixes_headline, tab:ci_mcnemar and the
    adversarial tables are labelled.

### C.2 Paper vs code defaults

All 20 constants in Appendix B and the Stage 2 to 5 rows of tab:thresholds match
`validation.py`. Switch defaults:
- `REQUIRE_ASSERTIVE_SPANS` on, `DIMENSIONAL_VETO` on, `ANCHOR_REQUIRE_BOTH` on: match the
  text.
- `RAG_ANCHOR_ASYMMETRIC_QSPAN` 0 and `MAX_CONFLICT_EVIDENCE_RANK` 0: retired or off; the
  text says retired. Match.

Three small descriptive gaps (no number is wrong):
- RRF uses k = 60 (`qdrant_retrieval.py:714`); the paper leaves k unnamed.
- The ColBERT rerank runs over the union of the dense and sparse prefetches; the RRF score is
  computed and reported, not used to pick the rerank set. The paper says "the fused candidates
  are then reranked".
- Retrieval depth `RETRIEVAL_TOP_K = 30` is not in tab:thresholds; "Prefetch limit 20" is.

### C.3 Against the NLPIR PDF

**Deliberate (recorded in the log):**
- RAMDocs uses the clean recalculation (85.2% / 94.8%), not NLPIR's 84.6% / 94.2%.
- MultiHop-RAG is the new 300-query run, not NLPIR's 121-query run.
- "33 of 48", not 31.
- Python 3.11.9, not 3.12.
- Haystack kept as ACCEPTED_AS_IS.
- Appendix A (prompts) left out; Corpus 3 left out.

**Not deliberate (main.tex is worse than NLPIR here):**
- tab:summary caption: NLPIR says only zero flips and the absence of an instruction-following
  component hold by construction, and every other row is empirical. main.tex says the
  opposite.
- Attribution: NLPIR says it does not transfer; main.tex says it "held".
- Determinism evidence: NLPIR cites two full 78/78 runs; main.tex cites an 8-query replay.
- Synthesis model: NLPIR names llama-3.3-70b for C1/C2 and gpt-oss-120b for the external
  runs; main.tex says Llama-3 everywhere.

**Shared with NLPIR, and still wrong:**
- "the defended LLM resisted all 45": main.tex at least qualifies it at 2420.
- The haystack claim.

---

## D. Argument and structure

- **Is the claim stated once, clearly?** Yes, in the abstract (130-131, 152-154) and the
  introduction (217-229): a repeatable, auditable decision with no instruction-following
  component, not higher accuracy. But it is restated in stronger forms later (1156-1158,
  1379, 1406-1408). Those later restatements are what a reviewer will quote back.
- **Abstract vs conclusion.** They agree on the C1 numbers, the external benchmarks and
  poisoning. The conclusion says "on external data a prompted LLM is safer, largely by
  refusing more". That is true of RAMDocs and not of MultiHop, where our gate answers 56 of
  150 null queries. The abstract states the MultiHop mechanism (false conflicts); the
  conclusion should too.
- **Contributions vs evidence.** Items 2 to 4 and 6 are supported. Item 5 lists RAMDocs (the
  favourable reading) and leaves out MultiHop (the unfavourable one), which the abstract
  includes. Item 1 says "safe abstention" where the evidence supports "abstention".
- **Related work vs the gap.** The gap ("no existing system provides a hard ... boundary",
  587-591) is stated as a universal. CRAG's evaluator (337) and selective prediction (384-386)
  both act before generation. The paper's distinction (learned vs deterministic) is real but
  needs to be the stated criterion. The "Breadth" subsection (480-556) is a citation list that
  does not sharpen the gap.
- **What a skeptical reviewer asks first:**
  1. "A rule-based router cannot be prompt-injected; isn't the immunity trivial?" The paper
     half-answers at 2234-2236 (provenance is adoptable by anyone). It should say plainly that
     the contribution is the *combination* of a useful decision with that property, and that
     the decision's usefulness is what the external benchmarks put in doubt.
  2. "On both external benchmarks the baseline is safer; what is left?" Answered honestly in
     Limitations and in the MultiHop section.
  3. "Two systems (v6 and current), two LLMs (llama-3.3-70b and gpt-oss-120b), and in-sample
     fixes are mixed; which result belongs to which?" Partly answered by labels. The order of
     sections makes it hard (frozen -> external on current -> fixes that define current).
  4. "Where is the evidence for determinism?" Currently an 8-query replay with no file.
  5. "Haystack: where is the run?" There is none for the current system.
- **Strongest sections:**
  - Adversarial Separation (2192-2244): paired tests, an honest bound, and provenance
    credited as adoptable.
  - RAMDocs (1513-1709) and MultiHop (1711-1774): preregistered, unfavourable results
    reported in full, mechanisms named.
  - Uncertainty and Paired Tests (1937-1954): says in plain words that the safety claim does
    not rest on 0/32 vs 1/32.
- **Weakest:** Summary: Both Corpora, Both Systems (1146-1201) and the close of the
  Prompted-LLM Baseline (1402-1408). This is where the paper claims by-construction safety and
  a worst-case guarantee that its own later sections and the NLPIR text withdraw. Next weakest:
  Post-Evaluation Fixes (929 words of change narrative, internal names like FIXES_REPORT, H5,
  H2/H4).

---

## E. Length and cuts

Approximate prose words per section (tables and figures counted separately; a regex count over
the source, so expect about 5% error):

| Section | Prose words | Table/fig words |
|---|---|---|
| Abstract | 461 | 0 |
| Introduction + Contributions | 857 | 0 |
| Related Work (9 subsections) | 2,481 | 0 |
| ...of which "Breadth of the literature" | 496 | 0 |
| System Architecture | 1,489 | 650 |
| Implementation | 691 | 296 |
| Evaluation: dataset, metrics, summary, main, ablation, NLI, baseline | 1,282 | 650 |
| Generalization: second corpus | 553 | 191 |
| RAMDocs (4 subsections) | 1,189 | 326 |
| MultiHop-RAG | 492 | 70 |
| Post-Evaluation Fixes (to Invariance, 9 subsubsections) | 2,312 | 1,516 |
| ...of which "Architectural Changes" | 929 | 0 |
| Threat Model | 353 | 0 |
| Adversarial Robustness | 1,036 | 219 |
| Discussion | 517 | 0 |
| Conclusion + Limitations + Future Work | 1,137 | 119 |
| Appendix B | 37 | 215 |
| **Total** | **about 15,200** | **about 4,250 (30 tables, 6 figures)** |

**Estimated length** (no compiler here): about 16 pages of IEEEtran two-column text plus 8 to
10 pages of floats, so **24 to 27 pages before references**, plus about 3 pages for 99
references. The NLPIR version is 15 pages and 7,160 words. A typical 8-page IEEE conference
paper holds about 5,500 to 6,500 words with 6 to 8 floats, so the cut needed is about 60%. For
IEEE Access (no hard limit, 10 to 16 pages typical) it is about 35 to 40%.

**Repeated material:**
- tab:results, tab:confusion and fig:confusion_heat show the same 3x3 numbers.
- tab:validation and fig:validation show the same seven stages.
- tab:fixes_headline and tab:ci_mcnemar share accuracy, precision, recall and unsafe.
- tab:corpus2 repeats tab:summary and tab:ci_mcnemar.
- tab:thresholds repeats Appendix B.
- tab:adversarial_summary repeats tab:injection, tab:hardening, tab:adaptive and
  tab:adversarial_separation.
- tab:ramdocs_abstain holds two numbers already in the prose.
- The RAMDocs scope caveats appear three times (1543-1549, 1694-1709, 2706-2724), and the
  Limitations paragraph repeats the RAMDocs and MultiHop results.

**Cuts, ranked by how little is lost (most expendable first):**

| Rank | Cut | Saves (about) | Loss |
|---|---|---|---|
| 1 | "Breadth of the RAG and Hallucination-Mitigation Literature" -> two sentences with the cites grouped | 450 words | none to the argument |
| 2 | Drop tab:results and fig:confusion_heat (keep tab:confusion) | 2 floats | none |
| 3 | Drop tab:validation (keep fig:validation) or the reverse | 1 float | none |
| 4 | Drop tab:thresholds (keep Appendix B; one sentence on calibrated vs structural) | 1 float | none |
| 5 | Merge tab:fixes_headline into tab:ci_mcnemar (add F1 and attribution rows); drop tab:corpus2 | 2 floats | none |
| 6 | Implementation: fold Technology Stack, Inter-Module Contracts and Interactive Interface into 3 sentences; drop tab:stack | 250 words + 1 float | low |
| 7 | Drop tab:ramdocs_abstain and tab:ramdocs_task (both are in prose) | 2 floats | low |
| 8 | Discussion: "Why Pre-Generation Verification Works" and "Abstention as a Feature" repeat the introduction | 220 words | low |
| 9 | Architectural Changes -> one table, one line per change with its measured effect | 600 words | low |
| 10 | Keep tab:adversarial_summary or the four separate adversarial tables, not both | 2 to 3 floats | low |
| 11 | Move tab:sensitivity and tab:component_ablation to an appendix | 2 page-wide floats | moderate (they are good evidence) |
| 12 | Limitations: cut the repeated RAMDocs and MultiHop numbers, keep one sentence each with a reference | 200 words | low |
| 13 | RAMDocs Metric Non-Equivalence: shorten to the EM-vs-safe-rate point; move tab:ramdocs_published to a sentence | 300 words + 1 float | moderate |

Ranks 1 to 10 together save about 1,700 words and 12 to 13 floats: roughly 8 to 9 pages, which
reaches IEEE Access length. Reaching 8 pages would also need the NLPIR-style compression of
Related Work (2,481 -> about 700 words) and System Architecture.

---

## F. Citations

Check over every `\cite` key in `main.tex` against `references.bib` (root, 109 entries):
- 114 cite keys in use, 99 unique.
- **Missing: `honovich2022true`** (cited at 2757, TRUE). Known; owner to add.
- 11 entries are never cited (harmless): `anon2025airworthiness`, `anon2025dsrag`,
  `anon2025hyperkg`, `anon2025phnsw`, `anon2025semanticchunking`, `anon2026enterpriseslr`,
  `anon2026multihopclustering`, `anon2026sncsreview`, `lee2026hallucisafe`,
  `li2025crossvalidation`, `nguyen2024intent`. The `anon*` keys suggest entries without author
  fields; check before any of them is cited.
- **Still wrong author fields** (Observation 49, not yet fixed): `jing2024vdbmssurvey` (Pan,
  Wang, Li), `zhang2023hallucinationrobust` (Chen et al.), `wang2025vericite` (Qian et al.),
  `huang2026c2cite` (Yu et al.). The printed references will name the wrong authors.

**Claims that need a citation and have none:**
- MultiHop-RAG (1713): no key. The paper names only the release `yixuantt/MultiHopRAG`. The
  dataset's own paper must be cited; the owner should take the reference from the dataset card
  (not written here).
- Reciprocal Rank Fusion (699-707): no cite for RRF.
- The answerhood cross-encoder `ms-marco-MiniLM-L-6-v2` (1881), the ColBERT checkpoint
  `answerai-colbert-small-v1` (710), and the LLMs `gpt-oss-120b` and `llama-3.3-70b-versatile`:
  no model-card or paper cites.
- "Astute RAG", "Speculative RAG", "self-reflection agent" (1617-1619, 2731): attributed to
  RAMDocs' table, which is acceptable for the table. The Limitations mention of "Astute RAG"
  stands alone.
- 124-125 and 189-191: "a soft, probabilistic behavior that fails silently" and "abandons
  silently under distribution shift". These are stated as fact with no cite. The project's own
  E1 result (1 flip in 78) is the nearest support; cite it or soften.
- Wilson interval and exact McNemar test: standard, optional.

---

## G. LaTeX issues (no compiler here)

- **Braces balance:** 0 net. **Environments:** all `\begin`/`\end` pairs match.
- **Labels:** no duplicates; every `\ref` resolves.
  - Unreferenced labels: `tab:multihop`, `tab:invariance` and `tab:security_current` (a table
    never referenced in text), plus several section and equation labels (harmless).
- **Figures will print as placeholders.** `fig4_confusion_matrix.pdf`, `fig5_ablation.pdf` and
  `fig6_nli_separation.pdf` are in `paper_assets/`, but `main.tex` is at the repo root and uses
  bare names inside `\IfFileExists`. A compile from the root prints the "[Figure placeholder]"
  boxes. Either move the PDFs next to `main.tex` or add `\graphicspath{{paper_assets/}}`. Check
  what the Overleaf project holds.
- **Em dashes in the text:** 899 ("does not cover — two"), 1841 ("assertion — neither"),
  1849 ("seen — the"). The em dashes quoted in this report are copied from the paper.
  - `---` in table cells renders as an em dash: 1914, 1977, 1978, 2132, 2216. Replace with
    "n/a" or "-".
- **Editing leftovers:**
  - `% <--- Note the asterisk (*) here` (1901, 1918).
  - The header comment says "98 curated entries ... updated 2026-08-16" (15-17); the bib has
    109.
  - `\hfill \break` after `\subsubsection{Security Properties}` (2154).
- **Overfull risk** in `\columnwidth` tables with long `r` cells:
  - tab:ramdocs_main 1599 ("78.4\% / 4.1\% (of 343)" in two `r` columns, footnotesize).
  - tab:multihop 1741 (three `r` columns plus an X).
  - tab:ramdocs_task (`l` first column).
  - tab:failed_fixes 2693 is long but sits in an X column (fine).
- **tab:security_current** is a `minipage` with `\captionof`, not a float, so it cannot move.
  In a two-column layout it may land mid-paragraph.
- **Future Work numbering broken** (2741-2761): item (2) runs into an unnumbered "and,
  separately, a held-out third corpus ...;(3)" (missing space; the third corpus has no number).
- **No TODO / TBD / FIXME / ???.** "placeholder" appears only in the `\figplaceholder` macro
  and at 1546 (prose, fine).
- **Bare query IDs without a corpus prefix** (project rule 5): Q036 (1890), Q051 and Q017
  (2699), Q045 (2704). Elsewhere they are prefixed.
- **Internal names** without definitions: FIXES\_REPORT (1816); H5 (2187, 2699); H2/H4 (900);
  E3 (2464).

---

## Proposed changes (ranked; ACCURACY and CLAIM first)

Line numbers are for `main.tex` at `9dbf386`. Each change is the minimum edit. Any change that
adds or moves a number needs a ledger row (Phase 2).

### ACCURACY

**P1. Haystack sentence (2043-2046). ACCURACY / CLAIM.**
- Current:
  > Planting each Corpus~1 conflict pair among $N \in \{2, \ldots, 80\}$ ingested distractor
  > chunks (5 seeded draws per pair and $N$), ours detected the planted conflict in all 20
  > haystacks at every $N$ (95\% interval $[84, 100]$\%), as did a prompted
  > \texttt{gpt-oss-120b} up to $N=40$.
- Proposed (option a, recommended): delete the paragraph.
- Proposed (option b): replace it with the only measured result, labelled:
  > In a v6 run (before the fixes), planting each Corpus~1 conflict pair among
  > $N \in \{2,5,10,20,40\}$ distractor chunks (20 haystacks per $N$), our detection fell from
  > 0.75 at $N=2$ to 0.50 at $N=40$, while a prompted LLM fell from 1.00 to 0.75; the current
  > system was not re-run.

  (Values from `experiments/haystack_results.json`, `summary`. Its `meta` does not name the
  LLM, so the owner must confirm the model before a name is written.)
- Why: no current-system file exists, and the only file contradicts the sentence (open item 15).

**P2. Baseline attribution explanation (1377-1378). ACCURACY.**
- Current: "the baseline earned full marks on 14 of 16 (mean $2.875$ of 3), missing the two
  points on the conflict it failed to flag."
- Proposed: "the baseline earned full marks on 14 of 16 (mean $2.875$ of 3): it lost one point
  on the conflict it failed to flag (Q035) and one on a conflict whose values it reworded
  (Q046)."
- Why: a re-grade of the stored replies with the experiment's own `grade_attribution` gives
  Q035 = 2 and Q046 = 2. "Two points on one conflict" would give 15 of 16.

**P3. Synthesis model (913, 962, 983). ACCURACY.**
- Current (913): "a Groq-hosted Llama-3 model, which is instructed to answer"
- Current (962): "Synthesis is performed by a Groq-hosted Llama-3 model behind an interface"
- Current (983): "Synthesis LLM & Groq-hosted Llama-3 (pluggable backend)"
- Proposed (913): "a Groq-hosted LLM (\texttt{llama-3.3-70b-versatile} in the Corpus~1 and 2
  experiments, \texttt{gpt-oss-120b}, the current default, on the external benchmarks), which
  is instructed to answer"
- Proposed (962): "Synthesis is performed by a Groq-hosted LLM behind an interface"
- Proposed (983): "Groq-hosted LLM (see Sec.~\ref{sec:synthesis}; pluggable)"
- Why: `llm_interface.py:53` default is `openai/gpt-oss-120b`; the E1 meta shows llama for
  C1/C2; NLPIR states both.

**P4. Python version (950). ACCURACY.**
- Current: "The system is implemented in Python~3.10 as a set of"
- Proposed: "The system is implemented in Python as a set of"
- Why: table line 977 says 3.11 and line 1077 says 3.11.9.

**P5. Determinism footnote (1193-1194). ACCURACY.**
- Current: "verified by an 8-query replay, not a repeated-sampling protocol."
- Proposed: "verified by two full runs per corpus with identical decisions on all 78 queries,
  not a repeated-sampling protocol."
- Why: the 8-query replay has no file. The frozen files (`baseline_corpus{1,2}.json` vs E1
  `ours_decision`) and the current files (`rerun` vs `sweep_default`) give 78/78 on both
  corpora. This also matches NLPIR. Needs two new ledger rows.

**P6. Word count at 519. ACCURACY.**
- Current: "but none of these seven decide whether the result can be trusted."
- Proposed: "but none of these five decide whether the result can be trusted."

**P7. Rounded differences (1923, 1928). ACCURACY (minor).**
- Current (1923): "Corpus~1 accuracy rose 3.9 points (92.3\% to 96.2\%)"
- Proposed (1923): "Corpus~1 accuracy rose 3.8 points (3 queries; 92.3\% to 96.2\%)"
- Current (1928): "Corpus~2 accuracy rose 23.0 points (66.7\% to 89.7\%)"
- Proposed (1928): "Corpus~2 accuracy rose 23.1 points (18 queries; 66.7\% to 89.7\%)"
- Why: 3/78 = 3.85 and 18/78 = 23.08. The current values subtract rounded percentages. MT-224
  and MT-227 need to compute from counts.

**P8. Routing ASR in the adversarial summary (2257, 2268-2269). ACCURACY.**
- Current: "Fixed injection, 3 styles (45), v6 & 0.000 & 0.044\textsuperscript{a}" with
  footnote a "Fraction in which injected content changed routing (2 of 45, both toward
  CONFLICT); no instruction was obeyed."
- Proposed: "... & 0.000\textsuperscript{b} & 0.000\textsuperscript{a}", footnote a:
  "Routing changed in 2 of 45 (0.044), both toward CONFLICT; no instruction was obeyed.",
  footnote b: "Original grader; a stricter automated screen flags 12 of 45 and one reader's
  pass finds 4 to 9 (Section~\ref{sec:adv-injection})."
- Why: the column is attack success; tab:injection gives 0.000 for the same quantity.

**P9. Threshold provenance (1412-1413). ACCURACY.**
- Current: "Every threshold in Table~\ref{tab:thresholds} was calibrated on Corpus 1 alone
  (Section~\ref{sec:impl})."
- Proposed: "Every threshold of the frozen system was calibrated on Corpus 1 alone
  (Section~\ref{sec:impl}); the three marked as selected on both corpora in
  Table~\ref{tab:thresholds} were added later."

**P10. Discussion: calibrated list and wrong cross-reference (2580-2584). ACCURACY.**
- Current: "The calibrated choices, the NLI contradiction threshold and the two sufficiency
  signals, are fitted to Corpus 1 and are not assumed to carry over on their own.
  Section~\ref{sec:limitations} reports the direct test of that assumption on a second corpus"
- Proposed: "The calibrated choices, the NLI contradiction threshold and the two sufficiency
  signals fitted to Corpus 1, and the three later values selected on both corpora, are not
  assumed to carry over on their own. Section~\ref{sec:corpus2} reports the direct test of that
  assumption on a second corpus"

**P11. Invariance paragraph (2316-2321). ACCURACY / CLAIM.**
- Current: "Fixing that bug (restricting focus terms to words the corpus actually contains)
  eliminated the sensitivity by construction."
- Proposed: "Fixing that bug (restricting focus terms to words the corpus actually contains)
  made the focus terms identical under this transform by construction; the three
  \texttt{query\_thanks} changes left in Table~\ref{tab:invariance} all go toward abstention."
- Why: the table still shows 1/78 and 2/78. "Four decisions" is from `docs/STATUS.md:484` only
  and needs a ledger row (ACCEPTED_AS_IS, C1).

**P12. Corpus 2 structure (1423-1425). ACCURACY (minor).**
- Current: "The second corpus matches Corpus 1's structure exactly"
- Proposed: "The second corpus matches Corpus 1's structure"
- Why: 46 facts vs 45 (`data_corpus2/ground_truth.json`).

**P13. "six limitations" (1779-1781). ACCURACY.**
- Current: "two rounds of targeted fixes addressed the six limitations identified in
  Section~\ref{sec:limitations}."
- Proposed: "two rounds of targeted fixes addressed the failures identified above and in
  Section~\ref{sec:limitations}."

### CLAIM

**P14. Summary table caption and prose (1151-1158, 1168-1170). CLAIM. Highest priority.**
- Current caption: "Accuracy drifts with the corpus; every other row holds by construction
  wherever it applies."
- Proposed caption: "Only zero decision flips and the absence of an instruction-following
  component in the decision hold by construction; every other row is empirical."
  (NLPIR's wording.)
- Current prose (1151-1158): "What we report instead is that every other row, determinism,
  injection immunity, and (with the caveat in Table~\ref{tab:heldvsdrifted}) attribution,
  holds regardless of that accuracy drop, because those properties come from the architecture
  rather than from the model's average-case performance. A lower accuracy number is the cost
  of the guarantee, not evidence against it, and Table~\ref{tab:summary} is where that
  exchange is easiest to see at a glance."
- Proposed prose: "What we report instead is that two rows, determinism and decision-layer
  injection immunity, hold regardless of that accuracy drop, because they come from the
  architecture; conflict recall and the unsafe-answer count are measurements and moved with
  the corpus."
- Why: the unsafe row drifts 0 -> 4 in the same table, and the "cost of the guarantee" causal
  claim has no support.

**P15. "0 of 32 by construction" (1378-1380). CLAIM.**
- Current: "our unsafe-answer rate is 0 of 32 by construction, while the baseline's is 1 of 32
  (Q035)."
- Proposed: "our unsafe-answer rate is 0 of 32 on this corpus, while the baseline's is 1 of 32
  (Q035; the difference is not significant, Section~\ref{sec:ci_mcnemar})."

**P16. Close of the baseline section (1402-1408). CLAIM.**
- Current: "Trust Before Text cannot, because the model is never reached on a conflict. Higher
  average accuracy and a worst-case safety guarantee are different things, and the baseline
  demonstrates the first while lacking the second."
- Proposed: "Trust Before Text did not, because the model is never reached on a detected
  conflict; a conflict the gate fails to detect is still answered (Corpus~2 Q045,
  Section~\ref{sec:corpus2}). Higher average accuracy and a repeatable decision are different
  things, and the baseline demonstrates the first while lacking the second."

**P17. Attribution "held" (1439-1440 and tab:heldvsdrifted 1497). CLAIM / ACCURACY.**
- Current (1439): "determinism and structural attribution do not move at all between the two
  corpora (Table~\ref{tab:heldvsdrifted})"
- Proposed (1439): "determinism does not move between the two corpora, and every conflict
  report still names two documents and their values; whether it names the right pair is
  empirical (15 of 16 on Corpus~2, where Q045 cites the wrong pair;
  Table~\ref{tab:heldvsdrifted})"
- Current (1497): "Structural attribution (3/3)   & by construction & held \\"
- Proposed (1497): two rows:
  - "Conflict report names a pair and values & by construction & held \\"
  - "Reported pair is the gold pair & empirical & 16/16 $\to$ 15/16 \\"
- Also 1154: change "and (with the caveat in Table~\ref{tab:heldvsdrifted}) attribution" (if
  P14 is not applied).
- Why: our "3/3" is a constant in `baseline_experiment.py:605`; the files give C1 16/16 and C2
  15/16 gold pairs (frozen); NLPIR says attribution does not transfer.

**P18. "Practical meaning of the safety guarantee" (1238-1240). CLAIM.**
- Current: "This asymmetry, errors that only ever cost a refusal and never produce a false
  answer, is the practical meaning of the safety guarantee."
- Proposed: "This asymmetry, errors that cost a refusal rather than produce a false answer, is
  what the gate is designed for; on this corpus it held, and on Corpus~2 it did not
  (Section~\ref{sec:corpus2})."

**P19. Introduction: parametric leakage (226-228). CLAIM.**
- Current: "that the model cannot leak parametric knowledge into a case where the evidence
  does not support an answer, and that every refusal is explainable by construction."
- Proposed: "that the model is never called when the gate finds the evidence insufficient or
  contradictory, and that every refusal is explainable by construction."
- Why: C2 frozen answered 4 gap queries and MultiHop 56 null queries. The gate passed them and
  the model was called.

**P20. "Independently authored" second corpus (138, 264, 1099, 1416, 2634). CLAIM.**
- Current (138): "Replicated on a second, independently authored corpus in a different domain"
- Proposed (138): "Replicated on a second corpus, written separately by this project in a
  different domain"
- Same change at 264 ("replicated on a second, independently authored corpus"), 1099 ("A
  second, independently authored corpus"), 1416 ("a second corpus authored independently to
  the same fixed-fact-map methodology") and 2634 ("Replicated on a second, independently
  authored corpus").
- Why: Limitations (2706) says both corpora were written by this project. A reviewer will read
  "independently" as a third party.

**P21. Related work: miscalibration (391-393). CLAIM.**
- Current: "so the abstention decision does not depend on a confidence estimate that can
  itself be miscalibrated under shift."
- Proposed: "so the abstention decision does not depend on a model's confidence estimate,
  though its own thresholds can be miscalibrated under shift (Section~\ref{sec:ramdocs})."
- Why: Discussion 2605-2606 says this; Observation 48 fixed only the Discussion copy.

**P22. "Unbreakable" and "0 of 45" for the defended LLM (2429-2431, 2477-2478). CLAIM.**
- Current (2429-2431): "either way, the distinction is a guarantee (0 by construction,
  unbreakable by a stronger prompt) versus a soft prompted resistance"
- Proposed (2429-2431): "either way, the distinction is a structural property (no
  instruction-following component in the routing path) versus a soft prompted resistance"
- Current (2477-2478): "the same soft defense the defended LLM already used to reach 0 of 45"
- Proposed (2477-2478): "the same soft defense the defended LLM already used (0 of 45 under
  the original grader)"

**P23. Conclusion: root cause (2615-2618). CLAIM.**
- Current: "whose central claim is that the primary bottleneck in reliable retrieval-augmented
  question answering is not retrieval quality but the absence of a structured
  evidence-verification gate between retrieval and generation."
- Proposed: "built on the view that reliable retrieval-augmented question answering needs a
  structured evidence-verification gate between retrieval and generation, not only better
  retrieval; on our two corpora every error arises downstream of retrieval."
- Why: on MultiHop, retrieval is fine and the gate is still worse than the LLM.

**P24. Conclusion: external data (2638-2639). CLAIM.**
- Current: "on external data a prompted LLM is safer, largely by refusing more."
- Proposed: "on external data a prompted LLM is safer: on RAMDocs by refusing more, and on
  MultiHop-RAG because our gate answers more null queries and raises false conflicts."

**P25. Contributions 1 and 5 (239-242, 264-266). CLAIM.**
- Current (241-242): "so that safe abstention is enforced by the pipeline rather than learned
  or prompted."
- Proposed (241-242): "so that abstention, when the gate decides it, is enforced by the
  pipeline rather than learned or prompted."
- Current (266): "where a prompted LLM is safer but our gate answers far more correctly
  (Section~\ref{sec:ramdocs})."
- Proposed (266): "where a prompted LLM is safer but our gate has the higher exact match
  (Section~\ref{sec:ramdocs}), and on MultiHop-RAG with retrieval, where the prompted LLM is
  both safer and more often correct (Section~\ref{sec:multihop})."

**P26. The gap (587-591). CLAIM.**
- Current: "What no existing system provides is a hard architectural boundary that blocks
  generation until the evidence has been shown to be sufficient and non-contradictory."
- Proposed: "None of the systems reviewed here provides a deterministic, non-learned boundary
  that blocks generation until the evidence has been shown to be sufficient and free of
  detected contradiction."

**P27. Sufficiency scope (897-899). CLAIM (and an em dash).**
- Current: "This is what refuses a question the corpus genuinely does not cover — two gap
  queries"
- Proposed: "On Corpora 1 and 2 this is what refuses a question the corpus genuinely does not
  cover: two gap queries"

**P28. Abstract "slightly" (142-143). CLAIM.**
- Current: "A well-prompted model can slightly exceed our accuracy, but only probabilistically:"
- Proposed: "A well-prompted model can exceed our accuracy (slightly on the first corpus,
  clearly on the second), but only probabilistically:"

**P29. NLI sweep range (2053-2054). CLAIM (minor).**
- Current: "results are identical from 0.80 to 0.99,"
- Proposed: "results are identical at 0.80, 0.94 and 0.99,"
- Why: those are the three runs with files.

### STRUCTURE

**P30. Label each frozen table's system in its caption.**
- Add "(Frozen System)" to the captions of tab:results, tab:confusion, fig:confusion_heat,
  tab:ablation, tab:corpus2 and tab:heldvsdrifted.
- Optional, larger: move sec:post_eval_fixes before sec:ramdocs, so both external benchmarks
  follow the description of the system they ran.

**P31. Internal names.**
- 1816 "described in the original FIXES\_REPORT" -> "used in an earlier version".
- 900 "passing H2/H4" -> "passing the average-score or coverage test".
- 2187 and 2699 "(H5)" -> delete.
- 2464 "Before (E3)" -> "Before".

**P32. Future Work numbering (2749-2753).** Number the held-out third corpus as its own item
and fix "selection;(3)". This shifts later items by one.

**P33. Limitations as its own section, placed before the Conclusion,** with the repeated
RAMDocs and MultiHop numbers replaced by references (also a CUT).

**P34. Reference the unreferenced tables** (tab:multihop, tab:invariance,
tab:security_current) once in the text.

### CUT

**P35 to P46.** Ranks 1 to 13 in Section E, in that order. Recommended at least: 1
(Breadth subsection), 2 (tab:results + fig4), 3 (tab:validation), 4 (tab:thresholds), 5
(merge tab:fixes_headline into tab:ci_mcnemar, drop tab:corpus2).

### STYLE

**P47. Em dashes.**
- 899: covered by P27.
- 1841: "make a positive factual assertion — neither is a question" -> "make a positive
  factual assertion: neither is a question".
- 1849: "never seen — the transfer direction" -> "never seen; the transfer direction".
- Table cells `---` (1914, 1977, 1978, 2132, 2216) -> "n/a".

**P48. Editing leftovers.** Delete `% <--- Note the asterisk (*) here` (1901, 1918). Update
the header comment's "98 curated entries" (15-17). Remove `\hfill \break` (2154).

**P49. Corpus prefix on bare query IDs** (project rule 5): 1890 Q036 -> Corpus~2 Q036; 2699
(Q051, Q017) -> (Corpus~1 Q051, Corpus~2 Q017); 2704 (Q045) -> (Corpus~2 Q045).

**P50. Figure path.** Add `\graphicspath{{paper_assets/}}` after `\usepackage{graphicx}`, or
copy the three PDFs next to `main.tex`. Otherwise the placeholders print. This is a build fix;
no text changes.

### Not proposed (owner decisions already on record)

- **Pre-ingestion poisoning 24/24** (ACCEPTED_AS_IS, open item 19): needs its file before
  submission.
- **The C1 "frozen" ablation 67.9% / 83.3% and the NLI figure values:** Corpus 1,
  ACCEPTED_AS_IS.
- **`references.bib` author fields and `honovich2022true`:** the owner's file.
