# Corpus 2 Generalization Report: Ashcombe Falls University

*Second-corpus test of the FROZEN v6 "Trust Before Text" system. No threshold,
validation rule, or decision-logic code was touched; see [Guardrails](#guardrails).
All numbers below come from actual runs: `our_decisions_corpus2.json` (decision-only,
zero LLM tokens) and `baseline_results_corpus2.json` (Groq `llama-3.3-70b-versatile`,
78 queries × 6 calls). Corpus 1 numbers are quoted from `experiments/MASTER_REPORT.md`.*

---

## TL;DR

Running the unchanged system on a new domain (US university academic regulations,
vs. UK HR policies) produces a genuinely different result, not just a lower
number:

- **The corpus-independent safety claims held exactly.** Conflict recall stayed
  **16/16 = 100%** (same as Corpus 1), determinism stayed **0 flips** (same as
  Corpus 1), and the structural attribution guarantee (names both docs, quotes
  both values) held on every conflict it flagged.
- **The calibrated accuracy claim did not hold.** Decision accuracy fell from
  92.3% (Corpus 1) to **66.7%** (Corpus 2), almost entirely from **conflict
  over-flagging** (precision 0.43 vs implied ~0.9+ on Corpus 1), not from missed
  conflicts or unsafe answers.
- **We found and can name the specific cause**, not just the symptom (see
  [Root Cause](#root-cause-why-precision-collapsed)): two pairs of Corpus-2
  documents that share a genuine planted conflict on *one* fact also share
  *near-identical wording on several unrelated facts*, so retrieval keeps
  co-retrieving them for unrelated queries, and the query-unscoped conflict
  detector fires anyway. This is Corpus 1's known Limitation 1 (`MASTER_REPORT.md`
  §7.1: "false conflicts from query-irrelevant pairs"), amplified by a corpus
  design where the conflicting documents overlap heavily on other content too.
- **The prompted-LLM baseline held up better here than on Corpus 1** (98.7% vs
  our 66.7%), a wider gap than Corpus 1's near-tie (97.4% vs 92.3%). This is
  consistent with the paper's existing thesis ("guarantee, not accuracy"), and
  makes that framing more important on this corpus, not less.

---

## Setup

| | Corpus 1 (Meridian Grid HR) | Corpus 2 (Ashcombe Falls University) |
|---|---|---|
| Domain | UK employment/HR policy | US academic regulations |
| Convention | UK statutory leave, GBP, HMRC mileage | US semester/credit-hour, USD, FAFSA |
| Documents | 11 (incl. 1 superseded pair) | 11 (incl. 1 superseded pair) |
| Facts | 45 | 46 |
| Planted conflicts | 4 (numeric+NLI ×2, versioned NLI, stance NLI) | 4 (numeric+NLI ×2, versioned NLI, stance NLI) |
| Gaps | 6 | 6 |
| Queries | 78 (46 answer / 16 conflict / 16 insufficient) | 78 (46 answer / 16 conflict / 16 insufficient) |
| System version | v6, frozen | v6, frozen (identical code/thresholds) |

Corpus 2 was authored independently to the same fixed-fact-map methodology as
Corpus 1 (see `data_corpus2/_build_docs.py`, the source of truth for every
sentence, and `data_corpus2/ground_truth.json`). Every fact and conflict was
text-verified programmatically against the generated `.docx` files before any
query was run (exact section headings + numeric tokens confirmed present;
all 6 gap topics confirmed genuinely absent via keyword scan).

---

## 1. Decision accuracy

| | Corpus 1 | Corpus 2 | Δ |
|---|---|---|---|
| **Ours (v6)** | 72/78 = **92.3%** | 52/78 = **66.7%** | **−25.6 pts** |
| **Prompted-LLM baseline** | 76/78 = **97.4%** | 77/78 = **98.7%** | +1.3 pts |

Ours confusion matrix, Corpus 2 (rows = gold, cols = system):

| gold ↓ / gave → | Answer | Conflict | Insufficient |
|---|---|---|---|
| **Answer (46)** | 26 | 19 | 1 |
| **Conflict (16)** | 0 | 16 | 0 |
| **Insufficient (16)** | 4 | 2 | 10 |

Baseline confusion matrix, Corpus 2:

| gold ↓ / gave → | Answer | Conflict | Insufficient |
|---|---|---|---|
| **Answer (46)** | 46 | 0 | 0 |
| **Conflict (16)** | 1 | 15 | 0 |
| **Insufficient (16)** | 0 | 0 | 16 |

---

## 2. Conflict detection: recall held, precision collapsed

| | Corpus 1 (ours) | Corpus 2 (ours) | Corpus 2 (baseline) |
|---|---|---|---|
| Conflict recall | 16/16 = **100%** | 16/16 = **100%** | 15/16 = 93.75% |
| Conflict precision | not separately reported; 6 false-conflict flags on answer queries → **0.727** implied (16 TP / 6 FP) | **0.432** (16 TP / 21 FP) | **1.000** (15 TP / 0 FP) |
| Conflict F1 | 0.842 implied | **0.604** | **0.968** |

**Recall is corpus-independent** (100% on both corpora, by construction: the
detector never misses a planted conflict it can see). **Precision is not**: it
depends on how cleanly the corpus's topic space separates the two documents
that hold a real conflict from documents that are merely nearby in the
embedding/lexical space. Corpus 2 is worse on this axis than Corpus 1 by design
accident (see below), not because the detector logic differs.

### Root cause: why precision collapsed

Of the 19 false "answer→conflict" flags, all but one trace back to exactly two
document pairs, and both pairs are the *actual* planted-conflict pairs:

- **`Course_Registration_and_Add_Drop_Policy.docx` × `Course_Registration_Policy_2022_Superseded.docx`**
  (the real C2 conflict, 18 vs 21 credit hours), fired on 8 unrelated queries
  (Q006, Q007, Q010, Q019, Q020, Q021, Q029, Q031, Q069, Q070). These two
  documents share near-identical wording for *most* of their sections (both
  state "12 credit hours" full-time status, similar add/drop language) because
  the superseded doc is a realistic near-copy of its replacement. Retrieval
  therefore co-retrieves both documents for almost any registration- or
  tuition-related query, and the (query-unscoped) conflict detector re-fires
  the real C2 pair regardless of what was actually asked.
- **`Academic_Catalog_and_Grading_Policy.docx` × `Student_Handbook.docx`**
  (the real C1/C3 conflicts, probation length and financial-aid GPA), fired on
  7 unrelated queries (Q002, Q003, Q004, Q030, Q066, Q067, Q068, Q071). The
  Handbook is a general-reference document that necessarily overlaps topically
  with the Catalog on anything GPA-related (good standing, Dean's List, Latin
  honors, financial aid) even though only two of those GPA facts actually
  conflict.
- One residual case (Q060, disciplinary-stages query pairing
  `Academic_Integrity_Policy.docx` × `Student_Conduct_and_Disciplinary_Policy.docx`)
  is an ordinary NLI misfire of the kind already documented in Corpus 1
  (`MASTER_REPORT.md` §7.1), not a doc-overlap effect.

This sharpens Corpus 1's documented Limitation 1 ("`find_conflict` compares
every cross-document pair and returns the first; unrelated pairs sometimes
score a high-confidence NLI contradiction... needs query-intent understanding")
into a specific, generalizable prediction: **the failure mode gets worse when
the conflicting document pair also shares substantial unrelated content**,
because that guarantees frequent co-retrieval. A superseded-policy pair and a
handbook/authoritative-policy pair are both realistic, common instances of
"documents that overlap a lot and disagree on one thing"; this is not a
corpus-authoring artifact to fix, it is a structural stress case the detector
needs query-relevance scoping to survive (same fix already named in Corpus 1's
future work, item (a): "return all conflicting pairs + rank by query
relevance").

---

## 3. Unsafe answers and leakage

| | Corpus 1 (ours) | Corpus 2 (ours) | Corpus 2 (baseline) |
|---|---|---|---|
| Unsafe answers (of 32 conflict+gap queries) | 0/32 | **4/32** | 1/32 |
| Gap leakage (of 16 insufficient) | 0/16 (implied by 0/32 unsafe) | **4/16** | 0/16 |

Corpus 1's "0 unsafe answers" did **not** hold on Corpus 2. The 4 leaked gap
queries: Q017 (study-abroad credit transfer), Q050/Q078 (pets in dorms), Q055
(library fines). In each case the sufficiency stage judged retrieved,
topically-adjacent-but-off-topic chunks as "sufficient" evidence (e.g. Q055
about library fines likely matched the IT policy's unrelated "library
subscription databases" VPN sentence). This is a genuine, honest drift and
should be reported as such, not glossed over. It is a distinct failure mode
from the conflict-precision issue above (sufficiency miscalibration, not
conflict-detector miscalibration), and is worth flagging as a second named
limitation for the paper if Corpus 2 material is included.

The baseline's 1 unsafe case (Q045, SAP-GPA query answered "2.5" instead of
flagging the Handbook's conflicting "2.0") is the safety-relevant type of
error Corpus 1's baseline also made once (Q035), a real conflict answered
instead of flagged.

### 3a. Which branch of the sufficiency gate admitted the leaks? (added, read-only follow-up)

*Diagnosis run after the fact, decision-layer only, zero LLM tokens, frozen
system unchanged. Harness: `experiments_corpus2/diagnose_gap_leakage.py`; raw
output: `gap_leakage_diagnosis.json`. The replay reproduces all 6 recorded
verdicts exactly (4 leaks, 2 controls), so the numbers below are the ones the
frozen gate actually saw.*

Stage 5 passes evidence if `avg score >= 0.65` (H2) **OR** `coverage >= 0.55`
(H4). The open question was whether the leaks came in on the coverage branch,
which would make this a structural limitation of the disjunction, or on the
avg-score branch, which would make it calibration.

**The answer is unambiguous, and it is the opposite of the structural
hypothesis: all four leaks passed on H2 (avg score) alone. Coverage correctly
rejected all four.**

| Query | avg score (H2, ≥0.65) | coverage (H4, ≥0.55) | branch that passed | n chunks averaged |
|---|---|---|---|---|
| Q017 study-abroad credits | **0.6531 ✓** | 0.4000 ✗ | H2 only | 4 |
| Q050 cat in dorm | **0.6582 ✓** | 0.4000 ✗ | H2 only | 1 |
| Q078 cat in dorm (scenario) | **0.6764 ✓** | 0.5000 ✗ | H2 only | 1 |
| Q055 library fine | **0.6782 ✓** | 0.2857 ✗ | H2 only | 1 |
| *Q016 athletic scholarship (control, correctly abstained)* | *0.6097 ✗* | *0.0000 ✗* | *neither* | *1* |
| *Q049 president's salary (control, correctly abstained)* | *0.0000 ✗* | *1.0000 (vacuous)* | *blocked by H1/H3* | *0* |

**This is a calibration finding, and it should be stated as one.** The coverage
branch is not the culprit; on these queries it was the component doing its job.
The whole leak/no-leak boundary sits inside a band of about four hundredths:
the four leaks scored 0.6531 to 0.6782, and the nearest correctly-abstaining
control scored 0.6097. A threshold fitted on Corpus 1 landed just below where
Corpus 2's topically-adjacent-but-non-answering evidence happens to score.

Two further observations, offered as observations rather than established
mechanisms (n = 4 leaks on a single corpus):

1. **In three of the four leaks, the averaged set had collapsed to a single
   chunk**, so H2's "average retrieval score" was not an average at all; it was
   that one surviving chunk's score, and `MIN_CHUNKS_FOR_SUFFICIENCY = 1`
   permits this. The Stage-3 relevance filter had already discarded 29 of 30
   retrieved chunks, which is correct behaviour on a gap query, but it also
   removed exactly the weak evidence whose inclusion would have dragged the mean
   below the threshold. We conjecture that H2 is least reliable precisely where
   Stage 3 works best. Q017 is the exception and is a genuine four-chunk mean.
2. **`_query_coverage` returns 1.0 when the evidence set is empty** (visible on
   control Q049, where coverage reads 1.0 over zero chunks). Today this is
   inert, because the H1 and H3 hard gates reject an empty set before the H2/H4
   disjunction is evaluated. It is worth recording as a latent fragility rather
   than a current defect.

**Correction to the speculation earlier in this section.** The original text
guessed that Q055 (library fines) matched the IT policy's unrelated "library
subscription databases" VPN sentence. That guess was wrong. The single chunk
that survived relevance filtering for Q055 came from
`Tuition_and_Financial_Aid_Policy.docx` (Federal Work-Study / Refunds), and the
term "library" does not appear in it at all. Similarly, Q050 and Q078 survived
on the `Housing_and_Residence_Life_Policy.docx` document header, not on any
pet-related sentence. The evidence admitted was topically adjacent at the
document level, not at the sentence level, which is a weaker and less
comfortable form of adjacency than the original wording implied.

**Consequence for the paper.** The honest framing here is calibration, not
structure: "a sufficiency threshold fitted to one corpus admitted
non-answering evidence on another, by a margin of roughly 0.03." That is
weaker than a structural claim and a reviewer can legitimately respond "then
re-tune it," which is a fair criticism to accept rather than deflect. Per the
frozen-system rule, no threshold was changed to test this. The single-chunk
observation in point 1 above is the more interesting thread and is the one
worth pursuing as future work, but it is not yet strong enough to carry a
structural claim on this evidence.

---

## 4. Determinism and consistency (Pillar 1): held exactly

| | Corpus 1 | Corpus 2 |
|---|---|---|
| Ours: decision flips (temp>0 baseline consistency runs are N/A to us; dedicated spot-check instead) | 0/8 subset re-run, **0 flips** | 0/8 subset re-run, **0 flips** |
| Baseline: decision flips (5 hot runs × 78 queries) | 1/78 = 1.3% | 1/78 = 1.3% (Q041, SAP-GPA, the exact fact under the C3 conflict) |

Determinism is a property of the code, not the corpus: confirmed. Both the
dedicated 8-query spot-check and the fact that our decisions never flipped
across the entire 78-query baseline-comparison run (which re-derives `ours_decision`
from the same live pipeline as `our_decisions_corpus2.json`) agree.

---

## 5. Conflict attribution (Pillar 3): held

| | Corpus 1 | Corpus 2 |
|---|---|---|
| Ours: structural score | 3.00/3 (16/16 flagged, 16/16 named both docs, 16/16 gave both values, by construction) | 3.00/3 (16/16, 16/16, 16/16, by construction) |
| Baseline: mean score | 2.88/3 | 2.25/3 (15/16 flagged, 13/16 named both docs, 8/16 gave both values) |

Ours' structural attribution guarantee is unaffected by corpus, as expected:
it is a template property (name both retrieved docs, quote both spans) that
does not depend on the LLM at all. The baseline's attribution quality is
*worse* on Corpus 2 than Corpus 1 (2.25 vs 2.88), interestingly; the gap
between "ours" and "baseline" on this axis widens in Corpus 2's favor for us.

---

## 6. What held vs. what drifted: honest summary

| Claim | Corpus 1 | Corpus 2 | Verdict |
|---|---|---|---|
| Decision is deterministic (0 flips) | ✅ | ✅ | **Corpus-independent, holds** |
| Conflict recall is perfect (16/16) | ✅ | ✅ | **Corpus-independent, holds** |
| Structural attribution is perfect when flagged (3/3) | ✅ | ✅ | **Corpus-independent, holds** |
| Decision accuracy ≈ prompted baseline (near-tie) | 92.3% vs 97.4% | 66.7% vs 98.7% | **Calibrated, drifted, gap widened** |
| Conflict precision is high | 0.73 (implied) | 0.43 | **Calibrated, drifted, root cause identified** |
| Unsafe answers ≈ 0 | 0/32 | 4/32 | **Calibrated, drifted, new failure mode (sufficiency, not conflict detection)** |

This is exactly the split the setup brief predicted: properties that are true
*by construction* (no learned/prompted component in the routing decision)
transferred perfectly; properties that depend on the specific tuned
thresholds (NLI 0.94, sufficiency 0.65/0.55) did not, and the corpus-2 failure
modes are now specific and nameable rather than vague. This *strengthens* the
paper's "guarantee, not accuracy" thesis rather than weakening it: Corpus 2
is direct evidence that accuracy is corpus-sensitive while the safety
guarantees are not.

---

## Guardrails

- **No threshold, validation rule, or decision-logic code was changed.**
  `validation.py`, `orchestrator.py`, and `synthesis.py` are byte-for-byte
  identical to the Corpus 1 runs. The only "patch" applied was pointing
  retrieval at a different on-disk Qdrant directory
  (`qdrant_db_corpus2/` instead of `qdrant_db/`), via a `functools.partial`
  monkeypatch of `retrieval_interface._qdrant_retrieve` inside the two
  corpus-2 driver scripts, the same technique `experiments/our_decisions.py`
  already uses to stub `orchestrator.synthesize`. No frozen file was edited.
- **Corpus 1's data and index are untouched**: `data/`, `qdrant_db/`, and all
  `experiments/*.json` are unmodified (confirmed via file timestamps before
  and after this work).
- **Every number above comes from an actual run.** No result was estimated or
  interpolated.

---

## 7. Injection spot-check (decision layer only)

*Closes open question (a) from STATUS.md: including Corpus 2 in the paper
makes "the injection flagship (E3/E4/E5) ran on Corpus 1 only" more visible,
so a small spot-check reproduces the decision-layer half of E3 here. Harness:
`experiments_corpus2/injection_spotcheck_corpus2.py`; raw output:
`injection_spotcheck_corpus2.json`. Zero LLM tokens; no defended/undefended
LLM baseline was run (out of scope for a spot-check; see
`experiments/injection_test.py` for that comparison on Corpus 1). Frozen files
confirmed byte-for-byte unchanged via `git status` before and after.*

Same poison construction as E3 (direct / authority / exfil, one high-scoring
poison chunk inserted into the real retrieved set), applied to 5 Corpus-2
"answer" queries the frozen system already answers correctly and which are
not among the 19 pre-existing false-conflict flags from section 2 (so any
decision change here is attributable to the poison, not the known doc-overlap
issue): 15 cases.

| | Corpus 1 (E3, 45 cases) | Corpus 2 (spot-check, 15 cases) |
|---|---|---|
| Routing obeyed | 0/45 | **0/15** |
| Routing changed (answer to conflict/insufficient) | reported per style | **0/15** |
| Poison survived Stage-3 validation | yes (by design, score 0.90) | **15/15** |

The routing decision was immune on every case, on a domain and phrasing
convention it had never seen, even though the poison chunk survived into the
validated evidence set in all 15 cases. This reproduces the by-construction
result (no LLM in the routing path, so no channel exists for injected text to
change the verdict), not a new empirical finding; it is reported here only to
close the single-corpus gap for the paper's flagship claim.

---

## Reproducibility

| Artifact | Path |
|---|---|
| Corpus documents + builder script | `data_corpus2/*.docx`, `data_corpus2/_build_docs.py` |
| Ground truth (facts/conflicts/gaps) | `data_corpus2/ground_truth.json` |
| Query set (78 queries) | `data_corpus2/queries.json` |
| Qdrant index (separate store) | `qdrant_db_corpus2/` |
| Our-system decisions (zero LLM tokens) | `experiments_corpus2/our_decisions_corpus2.py` → `our_decisions_corpus2.json` |
| Prompted-LLM baseline (Groq, 78×6 calls) | `experiments_corpus2/baseline_experiment_corpus2.py` → `baseline_results_corpus2.json` |
| This report | `experiments_corpus2/CORPUS2_REPORT.md` |
| Gap-leakage diagnosis | `experiments_corpus2/diagnose_gap_leakage.py` → `gap_leakage_diagnosis.json` |
| Injection spot-check (decision layer) | `experiments_corpus2/injection_spotcheck_corpus2.py` → `injection_spotcheck_corpus2.json` |
