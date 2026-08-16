# NUMBERS.md — Single Source of Truth for All Paper Numbers

**Purpose:** every number below is transcribed directly from the current paper
(`paper_assets/trust_before_text.tex`) or from the raw result files it cites.
If a number you're about to write differs from this file, the paper is
correct and this file is stale — re-sync this file, don't silently diverge.
If you need a number that ISN'T here, get it from the raw file named in the
Source column, not from memory.

**Last synced: 2026-08-16, from the live `trust_before_text.tex`.** This pass
was a full "god mode" review: fixed 2 orphaned figures (Fig. 4/5 now
referenced in prose), an imprecise shared footnote in Table 4, redundant
Discussion/Limitations content, a missing Corpus-2 mention in the
Conclusion, an oversized abstract (377→287 words), and refreshed the
reference count everywhere it was stale (was still saying 44; real count is
98). No experimental numbers changed in this pass. Previous entry (kept for
history): corrected a transcription error in the Corpus-2 root-cause claim
(§2a) that had propagated from `CORPUS2_REPORT.md`: "18 of 19 false
conflicts trace to two document pairs" was wrong; the correct claims are
"17 of 19 involve one of two documents" (document level) and "12 of 19 are
the exact conflicting pair" (pair level), and an internal contradiction on
conflict-recall transfer (§2f) was also fixed. Update this line whenever you
edit this file.

**System version: v6, frozen throughout.** No threshold or decision-logic
code was changed across any experiment below (Corpus 2, E1-E5, spot-check).

---

## 1. Corpus 1 (Meridian Grid Technologies — UK enterprise HR policy)

The **primary, tuned-on** corpus. Every threshold in §3 was calibrated on
this corpus alone.

| Item | Value |
|---|---|
| Documents | 11 (incl. 1 superseded pair) |
| Facts | 45 |
| Planted cross-document conflicts | 4 |
| Deliberate gaps | 6 |
| Queries | 78 (46 answer / 16 conflict / 16 insufficient) |
| Phrasing types | 7 (single-fact, multi-part, cross-document comparison, conflict-probing, out-of-scope, aggregation, applied-scenario) |

**The 4 planted conflicts:** probationary period (3 vs 6 months) · max
remote days/week (3 vs 2, current vs superseded 2023 policy) · employer
pension contribution (6% vs 5%) · personal device for work email (permitted
if MDM-enrolled vs prohibited).

### 1a. Main results (ours, v6) — Table 5 in the paper (`tab:results`)
Source: `experiments/our_decisions.json`

| Metric | Value |
|---|---|
| Decision accuracy | 92.3% (72/78) |
| Conflict recall | 1.000 (16/16) |
| Conflict precision | 0.727 (16/22) |
| Conflict F1 | 0.842 |
| Answer recall | 87.0% (40/46) |
| Gap/insufficient recall | 100% (16/16) |
| Unsafe answers | 0/32 (0%) |

Confusion matrix (Table 6, `tab:confusion`; rows=gold, cols=system):

| gold ↓ / gave → | Answer | Conflict | Insufficient |
|---|---|---|---|
| Answer (46) | 40 | 6 | 0 |
| Conflict (16) | 0 | 16 | 0 |
| Insufficient (16) | 0 | 0 | 16 |

The 6 errors (all safe over-caution, answer→conflict): **Q001, Q019, Q029,
Q062, Q064, Q072**. Root cause: query-unscoped conflict detector fires on
irrelevant document pairs. Q029 and Q064 score above every true conflict
(0.9996, 0.9998) — no threshold can remove them without discarding real
conflicts.

### 1b. Ablation (Table 7, `tab:ablation`)
| Configuration | Accuracy |
|---|---|
| Validation baseline | 67.9% (53/78) |
| + Sufficiency AND→OR | 83.3% (65/78) |
| + NLI 0.94 & remove comparison override | **92.3% (72/78)** |

### 1c. NLI score separation (Fig. 6 data; `paper_assets/make_figures.py`)
- True conflicts (n=12): 0.965, 0.995, 0.9955, 0.9958, 0.9958, 0.996, 0.9981×4, 0.9998, 0.9999
- False conflicts (n=8): 0.817, 0.834, 0.861, 0.867, 0.876, 0.919, 0.9996, 0.9998
- Threshold: 0.94 (sits in the gap, except the two false-conflict outliers above)

### 1d. Prompted-LLM baseline, E1 (Table 9, `tab:headtohead`)
Source: `experiments/baseline_results.json`, `experiments/baseline_per_query.json`
Model: Groq `llama-3.3-70b-versatile`. 1 canonical run @ temp 0 + 5 runs @ temp 0.7.

| Property | Ours | Baseline |
|---|---|---|
| Decision accuracy | 92.3% (72/78) | **97.4% (76/78)** |
| Decision consistency (5 reruns) | 1.000 (0 flips) | 0.987 (1 flip, Q069) |
| Parametric leakage (16 gaps) | 0/16 | 0/16 |
| Conflict attribution (full 3/3) | 16/16 | 14/16 (mean 2.875/3) |
| Unsafe answers | 0/32 | 1/32 (Q035) |

Baseline confusion matrix (Table 8, `tab:baseline_confusion`):

| gold ↓ / gave → | Answer | Conflict | Insufficient |
|---|---|---|---|
| Answer (46) | 45 | 0 | 1 |
| Conflict (16) | 1 | 15 | 0 |
| Insufficient (16) | 0 | 0 | 16 |

Baseline's 2 errors: **Q072** (answer→insufficient, safe over-abstention),
**Q035** (conflict→answer, the one unsafe case: answered a real conflict).
Baseline conflict recall (derived from confusion matrix, not a named table
cell) = **15/16 = 93.75%**.

### 1e. Threat/Adversarial experiments (E2-E5)

**E2 — scale/haystack stress test** (NOT in the current paper body; recorded
here so no chat re-derives or contradicts it). Source: `experiments/haystack_results.json`.
Result: **win NOT met.** Conflict recall vs N (buried-conflict setting):

| N | Ours | LLM |
|---|---|---|
| 2 | 0.75 | 1.00 |
| 5 | 0.75 | 1.00 |
| 10 | 0.70 | 0.85 |
| 20 | 0.60 | 0.85 |
| 40 | 0.50 | 0.75 |

Ours degrades via distractor masking (masked-wrong-pair rate 0→0.05→0.15→0.40→0.50
as N grows); LLM degrades only on the semantic conflict C4 (1.00→0.40→0.00 by
N=40). C4 is missed by our detector at every N (NLI_SIM_FLOOR gates it out:
lexical sim 0.1483 < floor 0.15, even though isolated NLI score is 0.9999).
**Deferred to future work; numbers frozen, do not re-run/re-tune.**

**E3 — Fixed injection** (Table 12, `tab:injection`). 15 answerable queries
× 3 styles = 45 cases. Source: `experiments/injection_results.json`.

| Style | Undefended LLM | Defended LLM | Ours: routing obeyed | Ours: routing changed | Ours: synthesis |
|---|---|---|---|---|---|
| Direct | 1.000 | 0.000 | 0.000 | 0.000 | 0.133 |
| Authority | 0.733 | 0.000 | 0.000 | 0.133 (2/15) | 0.200 |
| Exfiltration | 1.000 | 0.000 | 0.000 | 0.000 | 0.867 |
| **All (45)** | **0.911** | **0.000** | **0.000** | **0.044 (2/45)** | **0.400** |

Poison survived validation 45/45. Routing changed (not obeyed) on 2/45,
**both in the authority style**: **Q009, Q015**, both went to safe CONFLICT
(the poisoned value was caught contradicting the real one).

**E4 — Synthesis hardening** (Table 13, `tab:hardening`). Same 45 cases,
re-run after adding untrusted-data delimiters + hardened synthesis prompt
(spotlighting-style defense; no novelty claimed). Source:
`experiments/hardening_injection.json`, `clean_before.json`, `clean_after.json`.

| Style | Before (E3) | After hardening |
|---|---|---|
| Direct | 0.133 | 0.000 |
| Authority | 0.200 | 0.000 |
| Exfiltration | 0.867 | 0.000 |
| **All (45)** | **0.400** | **0.000** |

Clean regression (15 queries): 0 decision flips, 14/15 correct value
retained (1 miss = grader artifact, identical both runs), faithfulness
unchanged.

**E5 — Adaptive attack on the decision (flagship)** (Table 14,
`tab:adaptive`). 10 targets (6 conflict + 4 gap), up to 4 escalating
rephrasings, best-of-N, against the **defended** LLM. Source:
`experiments/adaptive_results.json`.

| Attack family | Defended LLM | Ours (routing) |
|---|---|---|
| Conflict-suppression (6) | 2/6 = 0.33 | **0/6 = 0.00** |
| Fabricated evidence (4) | 4/4 = 1.00 | 4/4 = 1.00 |

Flipped conflict queries (LLM only): **Q040** (probation), **Q041**
(pension). Our routing stayed CONFLICT on all 6, every attack. Gap
fabrication defeats **both** systems 4/4 — the honest bound, not a win.

---

## 2. Corpus 2 (Ashcombe Falls University — US academic regulations)

**Held-out generalization test.** Independently authored, different domain
and convention (US semester/credit-hour, USD, FAFSA vs Corpus 1's UK
statutory leave, GBP, HMRC mileage). **No threshold was retuned for this
corpus** — same frozen v6 system, same thresholds as Corpus 1 (Table 3,
`tab:thresholds`).

| Item | Value |
|---|---|
| Documents | 11 (incl. 1 superseded pair) |
| Facts | 46 |
| Planted cross-document conflicts | 4 (C1-C4, same distribution as Corpus 1: C1:5, C2:5, C3:3, C4:3 query-mapping) |
| Deliberate gaps | 6 |
| Queries | 78 (46 answer / 16 conflict / 16 insufficient) — mirrors Corpus 1 exactly |

Source: `data_corpus2/*.docx`, `data_corpus2/ground_truth.json`,
`data_corpus2/queries.json`. Full report: `experiments_corpus2/CORPUS2_REPORT.md`.

### 2a. Main results (ours, v6) — part of Table 10 (`tab:corpus2`) and Table 4 (`tab:summary`)
Source: `experiments_corpus2/our_decisions_corpus2.json`

| Metric | Corpus 1 (ours) | Corpus 2 (ours) | Corpus 2 (baseline) |
|---|---|---|---|
| Decision accuracy | 92.3% | **66.7% (52/78)** | 98.7% (77/78) |
| Conflict F1 | 0.84 | **0.60** | 0.97 |
| Conflict precision | 0.73 | 0.43 (16 true flags against 21 false ones) | 1.00 |
| Conflict recall | 1.00 | 1.00 (16/16) | 0.94 (15/16) |
| Unsafe answers (/32) | 0 | **4** | 1 |

**Note on conflict recall:** do not describe this as a clean "held by
construction" result (an earlier internal draft of this claim, and one
table row in the paper, made that error and has since been corrected — see
§2f). Recall staying at 16/16 on Corpus 2 is entangled with the same
query-unscoped firing that collapses precision; it is not an independent
success.

Ours confusion matrix, Corpus 2:

| gold ↓ / gave → | Answer | Conflict | Insufficient |
|---|---|---|---|
| Answer (46) | 26 | 19 | 1 |
| Conflict (16) | 0 | 16 | 0 |
| Insufficient (16) | 4 | 2 | 10 |

Baseline confusion matrix, Corpus 2:

| gold ↓ / gave → | Answer | Conflict | Insufficient |
|---|---|---|---|
| Answer (46) | 46 | 0 | 0 |
| Conflict (16) | 1 | 15 | 0 |
| Insufficient (16) | 0 | 0 | 16 |

**Error decomposition (26 errors total):** 22 conservative (19
answer→conflict, 2 insufficient→conflict, 1 answer→insufficient), **4
unsafe** (gap queries answered instead of abstained).

**Root cause of precision collapse — CORRECTED 2026-08-11.** The original
`CORPUS2_REPORT.md` prose (and the paper's earlier draft) conflated two
different counts: the exact conflicting-pair count and the broader
document-involvement count. Re-derived directly from the `conflict_pair`
field in `experiments_corpus2/our_decisions_corpus2.json` (19 false
`answer`→`conflict` flags):

- **Document level ("nearly all," the correct framing for that phrase):
  17 of 19 (89%)** involve either
  `Course_Registration_Policy_2022_Superseded.docx` (the superseded
  registration policy) or `Student_Handbook.docx` (the handbook),
  regardless of which document they were retrieved alongside.
- **Exact pair level (do NOT call this "nearly all"): 12 of 19 (63%)**
  are the precise conflicting pair itself: 6 are
  `Course_Registration_Policy_2022_Superseded.docx` ×
  `Course_Registration_and_Add_Drop_Policy.docx` (Q007, Q020, Q029, Q031,
  Q069, Q070), and 6 are
  `Academic_Catalog_and_Grading_Policy.docx` × `Student_Handbook.docx`
  (Q003, Q004, Q066, Q067, Q068, Q071).
- **The remaining 5 of the 17** involve the superseded policy or the
  handbook but with a *different* partner: `Course_Registration_Policy_
  2022_Superseded.docx` × `Tuition_and_Financial_Aid_Policy.docx` (Q010,
  Q021), `Academic_Catalog_and_Grading_Policy.docx` ×
  `Course_Registration_Policy_2022_Superseded.docx` (Q006),
  `Course_Registration_Policy_2022_Superseded.docx` ×
  `International_Student_Policy.docx` (Q019), and `Student_Handbook.docx`
  × `Tuition_and_Financial_Aid_Policy.docx` (Q002).
- **2 residuals involve neither document** (not 1, as the original report
  said): `Academic_Catalog_and_Grading_Policy.docx` ×
  `Student_Conduct_and_Disciplinary_Policy.docx` (**Q030**) and
  `Academic_Integrity_Policy.docx` ×
  `Student_Conduct_and_Disciplinary_Policy.docx` (**Q060**, an ordinary NLI
  misfire, not a doc-overlap effect).

12 + 5 + 2 = 19, all counts reconcile against the raw file. **Paper wording
uses "two documents," never "two document pairs," and states both the
17/19 and 12/19 figures** (`trust_before_text.tex`, Evaluation §"Generalization:
A Second Corpus" and Limitations §"The Core Open Problem").

### 2b. Gap leakage (unsafe answers) — the 4 leaked queries
Source: `experiments_corpus2/gap_leakage_diagnosis.json`. Diagnosis: **all 4
leaked on the sufficiency gate's average-score branch (H2) alone; the
coverage branch (H4) correctly rejected all 4.** This is a calibration
finding, not a structural one — the disjunction is exonerated.

| Query | avg score (H2, ≥0.65) | coverage (H4, ≥0.55) | n chunks averaged |
|---|---|---|---|
| Q017 (study-abroad credits) | 0.6531 ✓ | 0.4000 ✗ | 4 |
| Q050 (cat in dorm) | 0.6582 ✓ | 0.4000 ✗ | 1 |
| Q078 (cat in dorm, scenario) | 0.6764 ✓ | 0.5000 ✗ | 1 |
| Q055 (library fine) | 0.6782 ✓ | 0.2857 ✗ | 1 |
| Q016 (control, correctly abstained) | 0.6097 ✗ | 0.0000 ✗ | 1 |
| Q049 (control, correctly abstained) | 0.0000 ✗ | 1.0000 (vacuous, blocked by H1/H3) | 0 |

Nearest correctly-abstaining control (Q016) scores 0.6097 — the whole
leak/no-leak boundary sits in a band of ~0.04 (0.6531 to 0.6782 vs 0.6097).
Conjecture (n=4, not established): 3 of 4 leaks had evidence collapse to a
single chunk before averaging (`MIN_CHUNKS_FOR_SUFFICIENCY=1` permits this).

Corrected in the report: Q055's surviving chunk is from
`Tuition_and_Financial_Aid_Policy.docx` (Work-Study/Refunds), contains no
"library" text at all. Q050/Q078 survived on the Housing policy document
header, not a pet-related sentence. Adjacency is document-level, not
sentence-level.

### 2c. Determinism (Pillar 1) — held exactly
Source: `experiments_corpus2/our_decisions_corpus2.json`,
`experiments_corpus2/baseline_results_corpus2.json`

| | Corpus 1 | Corpus 2 |
|---|---|---|
| Ours: decision flips | 0/8 subset re-run | 0/8 subset re-run, and 0 flips across the full 78-query baseline-comparison run |
| Baseline: decision flips (5 hot runs) | 1/78 = 1.3% (Q069) | 1/78 = 1.3% (**Q041**, SAP-GPA query — different query than Corpus 1's Q041, corpora have independent numbering) |

### 2d. Conflict attribution (Pillar 3) — held for ours, worse for baseline
| | Corpus 1 | Corpus 2 |
|---|---|---|
| Ours: structural score | 3.00/3 (16/16, 16/16, 16/16) | 3.00/3 (16/16, 16/16, 16/16) |
| Baseline: mean score | 2.88/3 | **2.25/3** (15/16 flagged, 13/16 named both docs, 8/16 gave both values) |

### 2e. Injection spot-check (decision layer only)
Source: `experiments_corpus2/injection_spotcheck_corpus2.py` →
`injection_spotcheck_corpus2.json`. 5 answerable queries (not among the 19
pre-existing false-conflict flags) × 3 styles (direct/authority/exfil) = 15
cases. **No baseline run** (out of scope for a spot-check).

| | Corpus 1 (E3, 45 cases) | Corpus 2 (spot-check, 15 cases) |
|---|---|---|
| Routing obeyed | 0/45 | **0/15** |
| Routing changed | reported per style | **0/15** |
| Poison survived Stage-3 | yes (by design) | **15/15** |

### 2f. Held vs. drifted summary — Table 11 (`tab:heldvsdrifted`)
**CORRECTED 2026-08-11:** conflict recall is not a by-construction row. It
is empirical and entangled with the precision collapse (same mechanism:
query-unscoped firing), so it cannot be read as an independent success. An
earlier draft of the paper had this wrong in this table (calling it "by
construction, held") while correctly calling it out as confounded in the
Evaluation prose — that internal contradiction is now fixed in both the
paper and here.

| Property | Type | Transfer |
|---|---|---|
| Determinism (0 flips) | by construction | held |
| Structural attribution (3/3) | by construction | held |
| Conflict recall (16/16) | empirical | entangled with precision, not independent |
| Decision accuracy | calibrated | drifted |
| Conflict precision | calibrated | drifted |
| Unsafe-answer rate | calibrated | drifted |

---

## 3. Combined summary — Table 4 (`tab:summary`, the paper's headline table)

Inserted before the detailed Corpus-1 results, right after the Metrics
subsection. This is literally "Table 4" in the compiled paper.

| Metric | Corpus 1 (ours) | Corpus 1 (baseline) | Corpus 2 (ours) | Corpus 2 (baseline) |
|---|---|---|---|---|
| Decision accuracy | 92.3% | 97.4% | **66.7%** | 98.7% |
| Conflict recall | 100% | 93.8% | 100% | 93.8% |
| Unsafe answers (of 32) | **0** | 1 | **4** | 1 |
| Decision flips (5 reruns) | **0%** | 1.3% | **0%** | 1.3% |
| Injection obeyed (decision layer) | **0/45** | n/a | **0/15**\* | n/a |

\*Corpus 2 figure is the 15-case spot-check (§2e), not a repeat of the full
45-case Corpus 1 study. Baseline injection cells are n/a: a prompted model
has no separate decision layer to isolate, and no baseline injection test
was run on Corpus 2.

**Note:** this table intentionally omits fractions Table 10/`tab:corpus2`
already gives in detail (e.g. conflict recall as 15/16 not just 93.8%) —
it's a compact "at a glance" table; exact fractions live in §1/§2 above and
their corresponding paper tables.

---

## 4. System constants (Table 3, `tab:thresholds`)

| Threshold | Value | Stage | Type |
|---|---|---|---|
| Duplicate similarity | 0.90 | 2 | Structural |
| Relevance ratio | 0.30 | 3 | Structural |
| Min relevance score | 0.05 | 3 | Structural |
| Min chunk score | 0.60 | 3 | Structural |
| Conflict similarity gate | 0.68 | 4 | Structural |
| NLI similarity floor | 0.15 | 4 | Structural |
| NLI contradiction | **0.94** | 4 | **Calibrated** |
| Min chunks | 1 | 5 | Structural |
| Min average score | **0.65** | 5 | **Calibrated** |
| Min query coverage | **0.55** | 5 | **Calibrated** |
| Prefetch limit | 20 | Retrieval | Structural |
| Faithfulness (caution prefix) | 0.70 | Synthesis | Structural |

All three calibrated thresholds were fit on **Corpus 1 only** and never
retuned for Corpus 2 (§2, Guardrails in `CORPUS2_REPORT.md`).

Tech stack (Table 2, `tab:stack`): Python 3.10 · Qdrant (local persistent)
· dense `all-MiniLM-L6-v2` (384-d) · sparse BM25 (Qdrant IDF modifier) ·
reranker ColBERT `answerai-colbert-small-v1` · NLI
`cross-encoder/nli-deberta-v3-base` · synthesis Groq-hosted Llama-3
(`llama-3.3-70b-versatile` for all baseline/adversarial LLM calls) ·
FastAPI + static HTML/CSS/JS frontend.

---

## 5. Paper meta-numbers (not experimental results)

| Item | Count |
|---|---|
| References (`references.bib`) | 98, all cited, no orphans (grew 44→98 across 3 merge rounds: +11 curated 2026-08-14, +34 curated 2026-08-14, +9 merged from a second "Copy" draft 2026-08-15) |
| Figures | 6 (Figs 1-3 native TikZ; Figs 4-6 matplotlib PDFs) |
| Tables | 14 |
| Equations | 8 |
| Sections | 11 top-level (`\section{}`) |

---

## 6. Known query-ID collisions (read before citing a Q-number)

Corpus 1 and Corpus 2 each have their own independently numbered 78
queries. The same ID means different things in each corpus:
- **Q041**: Corpus 1 = pension-conflict query (used in E5 adaptive attack).
  Corpus 2 = SAP-GPA query (the one baseline decision-flip case).
- **Q035**: Corpus 1 baseline's one unsafe answer.
- Always state which corpus a Q-ID belongs to when citing one outside its
  own section.

---

## 7. If a number here disagrees with a memory file or STATUS.md

Trust this file's most-recently-synced version first, since it was
transcribed directly from the compiled paper's tables. If THIS file
disagrees with the raw JSON/`.md` reports cited in the Source columns, trust
the raw file and flag the discrepancy — don't silently pick one.
