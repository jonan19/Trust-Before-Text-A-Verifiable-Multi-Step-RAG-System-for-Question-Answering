# PROJECT STATUS — Trust Before Text

**Shared dashboard across the 3 working chats. RULE: every chat READS this at the start of a task and UPDATES it (with timestamp + which chat) at the end. This is how chats learn what the others did — no manual retyping.**

**Last updated: 2026-08-06 — by PAPER chat (applied all 7 Corpus-2 edits to the draft).**

---

## One-line project state
Injection-flagship decision LOCKED. All experiments (E1–E5) DONE. System frozen at v6. Full paper drafted (injection-flagship framing) at `paper_assets/trust_before_text.tex`; references DONE (BibTeX), figs 4/5/6 DONE; figs 1–3 + IEEE Access template + compile pending. Goal: IEEE Access.

---

## Per-chat status

### 🧠 BRAINSTORM chat (strategy / decisions) — IDLE, up to date
- Direction LOCKED: **Option 2 — injection-flagship** (keep "Trust Before Text"; flagship = the LLM-free safety DECISION is injection-immune by construction; a defended LLM's decision can be adaptively talked out of flagging a conflict).
- Frame the win as an **existence proof + by-construction property, NOT a rate**. Two-class threat taxonomy (instruction injection = win / data poisoning = both fail). Principle = separation of data & control. Flagship figure = 2×2 threat matrix.
- **E2 bug fixes DEFERRED** to future work — numbers FROZEN (do not re-run/re-tune).
- **2026-08-06 DECIDED: Corpus 2 GOES IN THE PAPER, compact form** (~half page in Evaluation, not a full section, NOT in Limitations). Rationale: it is the only evidence for the "guarantee, not accuracy" thesis (Corpus 1 alone never shows accuracy is corpus-sensitive); it answers the #1 predicted rejection with data instead of argument; omitting a run experiment is selective reporting, and `data_corpus2/` ships with the reproducibility release anyway.
- **Framing corrections the PAPER chat MUST apply to `CORPUS2_REPORT.md` wording (the report overclaims in 3 places):**
  1. "Conflict recall held 16/16, **by construction**" is WRONG. Recall is empirical (retrieval + NLI 0.94 firing on new wording) and is confounded with the precision collapse: the detector fired 37 times to catch 16. Report recall and precision jointly; lead with **F1 0.84 → 0.60** as the honest transfer number.
  2. Determinism and structural attribution "holding" are NOT results (no LLM in either path; they cannot fail). Do not present "3 of 6 claims held". Honest framing: one empirical test (do Corpus-1 thresholds transfer? NO) + a sanity check that the by-construction properties are genuinely construction-level.
  3. **4/16 gap leakage must be its own sentence, with the baseline comparison** (ours 4/16 unsafe on gaps, baseline 0/16). Corpus 1's "0 unsafe answers" and Hard Test 1's fail-safe keeper are now Corpus-1-only claims. On this corpus the LLM was safer than us on gaps. State openly; do not bury.
- **Claim RETIRED (add to the FALSIFIED list): "70B-level decision quality from small local models."** 66.7% vs 98.7% kills it. "Within ~5 points" is now a Corpus-1-only statement and must be labelled as such everywhere.
- **Always pair 66.7% with the error decomposition**: of 26 errors, **22 are conservative** (19 answer→conflict, 2 insufficient→conflict, 1 answer→insufficient), 4 unsafe. Without this, 66.7% reads as "the system does not work".
- **Threats to Validity must state** that E3/E4/E5 ran on Corpus 1 only, that decision-layer injection immunity is corpus-independent by construction, and that this is not empirically confirmed on Corpus 2.
- Soften "a specific, generalizable prediction" (doc-overlap → false conflicts) to "we conjecture": n=1, on a corpus whose near-identical wording we authored.
- **2026-08-06: open question (b) closed by CORPUS2 — outcome is CALIBRATION, not structural.** All 4 gap leaks passed on the avg-score branch alone (0.653-0.678 vs 0.65 threshold); coverage correctly rejected all 4. Do NOT write the "disjunctive gate admits adjacent evidence" structural line — it is exonerated. **Use this finalized sentence for the paper's Limitations paragraph instead:** "On Corpus 2, 4 of 16 gap queries produced an answer instead of an abstention. Diagnosis traced this to the sufficiency gate's average-score branch: a threshold calibrated on Corpus 1 (0.65) admitted non-answering evidence scoring 0.65-0.68 on Corpus 2, roughly 0.03 above the nearest correctly-abstaining case. The coverage branch rejected all four correctly. This is a calibration gap, not a defect in the gate's logic." Optionally add ONE clause, explicitly labeled conjecture (n=4): in 3 of 4 cases the evidence set had collapsed to a single chunk before averaging, permitted by `MIN_CHUNKS_FOR_SUFFICIENCY=1` — flag as the likelier future-work thread, do not state as established.
- Full detail: `C:\Users\JOHNSON 251205\Downloads\BRAINSTORM_CHAT_RESUME.md`.

### 🧪 BASELINE / experiments chat — DONE (all 5 experiments), IDLE
- **Eval 0:** 72/78 = 92.3%; conflict recall 16/16; unsafe answers 0/32; 6 safe over-caution errors.
- **E1 baseline (prompted 70B):** ours 92.3% vs LLM 97.4%; flips 0 vs 1.3%; leakage 0/0; attribution 3.0 vs 2.88. → near-tie/loss (accuracy is NOT the contribution).
- **E2 scale:** LOSS — our recall degrades 0.75→0.50 as N grows (distractor masking); LLM mostly holds. Do not claim a scale advantage.
- **E3 injection (fixed):** routing decision immune 0/45 by construction; undefended LLM 0.91; defended LLM 0.00; our synthesis exposed 0.40 (exfil 0.87).
- **E4 synthesis hardening:** end-to-end ASR 0.40→0.00 (parity with defended LLM; a control, not a win).
- **E5 adaptive attack on the DECISION (FLAGSHIP):** instruction-injection → defended LLM 2/6 unsafe flips, ours 0/6 (WIN); data-poisoning → both 4/4 (honest bound).
- **Source of truth:** `experiments/MASTER_REPORT.md` (COMPLETE, E1–E5, incl. E4/E5 with raw-file refs) + raw files in `experiments/` (`our_decisions.json`, `baseline_results.json`, `haystack_results.json`, `injection_results.json`, `hardening_injection.json`, `adaptive_results.json`, `*_summary.md`, `*_chart.png`, `baseline_section_V_E_report.md`, `baseline_per_query.json`).
- **⚠️ Data caveat for PAPER:** use `experiments/our_decisions.json` for OUR v6 numbers. `data/phase6_fullrun_results.json` = v4 (67.9%), `..._v5.json` = v5 (83.3%) — NEITHER is the current system; do not cite them.

### 📄 PAPER chat — DRAFT + all 7 Corpus-2 edits DONE, finishing touches left
- **2026-08-06 (PAPER): all 7 Corpus-2 edits below APPLIED to `trust_before_text.tex` and verified** (refs resolve, 13/13 tables balanced, 0 em dashes). Done: (1) Limitations "Two Authored Corpora" rewrite; (2) Future Work "Further Corpora" rewrite; (3) new Evaluation subsection "Generalization: A Second Corpus" (`sec:corpus2`) with metrics + held-vs-drifted tables, F1 0.84→0.60 lead, no "recall held by construction"; (4) new "A Calibrated Sufficiency Threshold Did Not Transfer" limitation (4/16 gap leak, avg-score branch, single-chunk conjecture); (5) Core Open Problem sharpened with doc-overlap conjecture; (6) two-corpus clause in abstract + Contribution #5; (7) Corpus-2 injection spot-check sentence in Fixed Injection (15 cases, 0/15 obeyed, framed as spot-check not 2nd E3).
- Original queue (2026-08-06 BRAINSTORM), now all done. Task list kept for record:
  1. **Rewrite `\subsection{A Single Authored Corpus}` (Limitations, line ~1217).** Currently says "we make no claim of generalization" — no longer true. Replace with an honest two-corpus summary: by-construction properties (determinism, conflict recall, structural attribution, decision-layer injection immunity) held exactly on both; calibrated numbers (accuracy, conflict precision, unsafe-answer rate) drifted, with the mechanism named.
  2. **Rewrite `\subsection{A Second Corpus for Generalization}` in Future Work (line ~1281).** It currently describes running a second corpus as a proposed next step. It's done — the reported result moves into Evaluation (see #3). **DECIDED 2026-08-06: replace this subsection (don't delete it) with a generic forward-looking line**, e.g. "further corpora across additional domains would strengthen the generalization evidence beyond the two reported here." Keep it general, not a commitment to a specific third corpus/domain.
  3. **Add a new Evaluation subsection, "Generalization: A Second Corpus," after "Prompted-LLM Baseline" (~line 944) and before "Threat Model" (~line 945).** Content: setup diff (2-3 sentences, different domain/convention), one table (66.7% vs baseline 98.7%, conflict precision 0.43, F1 0.84→0.60, unsafe/gap-leakage 4/16 vs baseline 0/16), the error decomposition (22 of 26 errors are conservative over-abstention, 4 unsafe), root cause (two doc pairs sharing wording + a real conflict → query-unscoped detector re-fires), the held-vs-drifted table. ~half a page. Do NOT claim conflict recall "held by construction" — it's confounded with the precision collapse; lead with F1.
  4. **Add the finalized sufficiency-calibration limitation** (new — not in the draft yet): "On Corpus 2, 4 of 16 gap queries produced an answer instead of an abstention. Diagnosis traced this to the sufficiency gate's average-score branch: a threshold calibrated on Corpus 1 (0.65) admitted non-answering evidence scoring 0.65-0.68 on Corpus 2, roughly 0.03 above the nearest correctly-abstaining case. The coverage branch rejected all four correctly. This is a calibration gap, not a defect in the gate's logic." Optional one conjecture clause (n=4, label explicitly as conjecture): 3 of 4 leaks had evidence collapsed to a single chunk before averaging.
  5. **Sharpen the existing `\subsection{The Core Open Problem: Query-Irrelevant Pair Comparison}` (~line 1188)** with the Corpus-2 evidence: the doc-overlap mechanism (superseded-policy pair, catalog/handbook pair) that amplifies false conflicts when two documents share wording AND a real conflict. State as "we conjecture" (n=1, on an authored corpus), not an established prediction.
  6. **One-clause additions**: abstract (~line 88-89) and Contribution #5 (~line 185-189) both currently frame the evaluation as one corpus only — add "...and replicated on a second, independently authored corpus in a different domain."
  7. **Threat Model / Adversarial Robustness (lines 945-1122)**: currently Corpus-1-only. Add one sentence noting the decision-layer injection immunity was spot-checked on Corpus 2 too (15 cases, 0/15 obeyed, 0/15 routing changed — see `CORPUS2_REPORT.md` §7), upgrading that specific claim from asserted-by-construction to also-empirically-confirmed-on-a-second-corpus. Keep this small: it's a spot-check, not a second full E3, don't overstate it as one.
  - **Checked and NOT present in the draft, no action needed:** the "70B-level decision quality from small local models" claim (worried about earlier) was never actually written into this .tex — it only lived in the old brainstorm brief. Nothing to retract.
  - Source of truth for all numbers/wording above: this file's BRAINSTORM block (above) + `experiments_corpus2/CORPUS2_REPORT.md` (all 7 sections, em dashes now scrubbed).
- Full draft at `paper_assets/trust_before_text.tex` (IEEEtran conference for now). All sections written with real numbers, guarantee-not-accuracy framing, zero em dashes, no `[cite:]` junk.
- **Adversarial section DONE:** Threat Model + Adversarial Robustness (E3/E4/E5) + 2×2 matrix; flagship woven into abstract/contributions/limitations/conclusion (existence-proof framing; data-poisoning bound stated).
- **Figures DONE:** figs 4 (confusion), 5 (ablation), 6 (NLI separation) as matplotlib PDFs in `paper_assets/` (script `make_figures.py`).
- **References DONE:** 31 curated entries in `references.bib` (BibTeX/IEEEtran); switched off manual bib. Fixed 5 inherited citation-attribution errors (CoV→Dhuliawala, semantic entropy→Farquhar, RAGTruth→Niu, Rakin, ReEval→Yu). Verified 31 cites ↔ 31 entries.
- **PENDING:** figs 1–3 (TikZ: architecture / validation pipeline / conflict-flow); swap to IEEE Access template; first Overleaf compile (order: pdflatex, bibtex, pdflatex×2); optional title update to foreground the decision guarantee.
- Guardrails: numbers match `MASTER_REPORT`/`PAPER_MASTER_BRIEF §4`; `rawww.pdf` = DISCARDED.

---

## Recently decided (newest first)
- 2026-08-06: PAPER — applied all 7 Corpus-2 edits to `trust_before_text.tex` (compact generalization subsection in Evaluation, two-corpus Limitations rewrite, sufficiency-calibration limitation, Core-Open-Problem doc-overlap conjecture, abstract/contribution clauses, injection spot-check sentence). Led with F1 0.84→0.60, stated 4/16 gap leak honestly, kept spot-check scoped. Verified (refs, tables, 0 em dashes).
- 2026-08-06: BRAINSTORM — read the live `.tex` draft, confirmed 7 concrete stale/missing spots re: Corpus 2, queued as a task list in the PAPER block for the PAPER chat to execute.
- 2026-08-06: BRAINSTORM — ran both remaining open items directly (same working directory, no delegation needed). (1) Injection spot-check on Corpus 2 (open question (a)): 15 cases (5 clean "answer" queries x 3 styles: direct/authority/exfil), decision-layer only, zero LLM tokens, same poison construction as E3. **Result: 0/15 obeyed, 0/15 routing changed, poison survived Stage-3 in 15/15** — reproduces the by-construction immunity result on a second corpus/domain. Closes the "flagship ran on one corpus" gap. Harness `experiments_corpus2/injection_spotcheck_corpus2.py`, raw `injection_spotcheck_corpus2.json`. Frozen files verified byte-for-byte unchanged via `git status`. Written up as new §7 in `CORPUS2_REPORT.md`. (2) Em-dash cleanup: all 32 em dashes in `CORPUS2_REPORT.md` (sections 1-6, Guardrails; §3a was already clean) replaced with commas/colons/semicolons per standing preference. Verified 0 remain.
- 2026-08-06: CORPUS2 — open question (b) ANSWERED: the 4 gap leaks passed on the **avg-score** branch, not coverage. Structural framing is OFF the table; it is a calibration finding (~0.03 margin). See CORPUS2 block + `CORPUS2_REPORT.md` §3a.
- 2026-08-06: BRAINSTORM — Corpus 2 IS included in the paper (compact, in Evaluation) + 3 framing corrections to `CORPUS2_REPORT.md` wording + "70B-level from small models" claim retired. See BRAINSTORM block.
- 2026-08-02: BASELINE — delivered §V.E artifacts to PAPER (`baseline_section_V_E_report.md` + clean `baseline_per_query.json`); confirmed MASTER_REPORT §5A/§5B (E4/E5) carry raw-file refs. Flagged: `data/phase6_*` JSONs are v4/v5, NOT v6.
- 2026-08-02: PAPER — adversarial section (Threat Model + E3/E4/E5 + 2×2) added; figs 4/5/6 built; references DONE (31, BibTeX); 5 citation-attribution errors fixed.
- 2026-07-20: Injection is the FLAGSHIP (not shorthand); adversarial section to be added to the paper.
- 2026-07-20: E2 bug fixes DEFERRED; numbers frozen for this paper.
- 2026-07-20: MASTER_REPORT completed with E4/E5 (baseline chat).
- 2026-07-20: `rawww.pdf` discarded; new injection-flagship draft is the current paper.

## Open / next actions
- PAPER: Corpus-2 integration DONE (all 7 edits applied + verified). Remaining: figs 1–3 (TikZ); swap to IEEE Access template; first Overleaf compile; optional title update.
- ~~OPEN QUESTION (a): Corpus-2 injection spot-check~~ **DONE 2026-08-06 — 0/15 obeyed, 0/15 routing changed, poison survived Stage-3 in 15/15. See CORPUS2_REPORT.md §7.** ~~(b) sufficiency-branch check~~ **DONE 2026-08-06 — answered: avg-score branch, so calibration NOT structural. See CORPUS2 block.**
- **Both open questions now CLOSED. Corpus 2 material is ready for the PAPER chat** (compact-probe spec + finalized Limitations sentence in the BRAINSTORM block above; new §7 injection spot-check; em dashes scrubbed from `CORPUS2_REPORT.md`).
- USER: upload `trust_before_text.tex` + `references.bib` (+ fig PDFs) to Overleaf; run compile.
- CORPUS2: Steps 1 & 2 DONE — see below. Optional: fold into paper.
- OPTIONAL (not blocking): the two E2 fixes (future work).

### 🆕 CORPUS2 chat (second-corpus generalization test) — Steps 1 & 2 DONE
- Domain: Ashcombe Falls University (AFU) academic regulations — fictional, US semester/credit-hour system (deliberately different domain AND convention from Corpus 1's UK HR corpus).
- `data_corpus2/`: 11 .docx docs (10 policies + 1 superseded pair, generated by `data_corpus2/_build_docs.py` — the source of truth for wording), `ground_truth.json` (46 facts incl. 2 agreeing, 4 conflicts C1-C4, 6 gaps G1-G6), `queries.json` (78 queries, same 7 categories/counts as Corpus 1: 46 answer / 16 conflict / 16 insufficient; conflict dist C1:5 C2:5 C3:3 C4:3, mirrors Corpus 1 exactly). Text-verified programmatically before any run.
- Ingested into a SEPARATE Qdrant store `qdrant_db_corpus2/` (Corpus 1's `qdrant_db/` untouched, confirmed via timestamps). Retrieval pointed there via a `functools.partial` monkeypatch of `retrieval_interface._qdrant_retrieve` in the two corpus2 driver scripts — no frozen file edited (same technique `our_decisions.py` uses to stub synthesis).
- **Results (full 78-query runs, both harnesses complete):**
  - Ours (v6, decision-only): **52/78 = 66.7%** (vs Corpus 1's 92.3%). Conflict recall **16/16 = 100%** (held), conflict precision **0.43** (collapsed — root cause identified: two doc pairs sharing a real conflict on one fact ALSO share near-identical wording on unrelated facts, so retrieval co-retrieves them constantly and the query-unscoped detector re-fires). Determinism **0/8 flips** (held). Unsafe answers **4/32** (new drift — gap queries leaked, sufficiency-stage issue not conflict-detector issue).
  - Baseline (Groq llama-3.3-70b, 78×6 calls): **77/78 = 98.7%**, flips 1/78, conflict attribution mean 2.25/3.
  - Full comparison + root-cause analysis: `experiments_corpus2/CORPUS2_REPORT.md`.
- **Headline for the paper:** corpus-independent claims (determinism, conflict recall, structural attribution) held EXACTLY on Corpus 2; calibrated claims (accuracy, conflict precision, unsafe-answer rate) drifted — this is exactly the "guarantee, not accuracy" thesis, now with a second corpus as evidence.
- Harnesses: `experiments_corpus2/our_decisions_corpus2.py`, `experiments_corpus2/baseline_experiment_corpus2.py`. Raw results: `our_decisions_corpus2.json`, `baseline_results_corpus2.json`.
- **2026-08-06 — OPEN QUESTION (b) ANSWERED: gap-leakage sufficiency branch. Result is the OPPOSITE of the structural hypothesis.** All 4 leaks (Q017/Q050/Q055/Q078) passed on **H2 (avg score) ONLY**; the coverage branch H4 correctly REJECTED all 4 (cov 0.29-0.50, all < 0.55). avg scores 0.6531 / 0.6582 / 0.6764 / 0.6782 vs threshold 0.65; nearest correctly-abstaining control (Q016) = 0.6097. So the whole leak boundary sits in a ~0.04 band.
  - **This is a CALIBRATION finding, not a structural one.** The paper CANNOT say "a disjunctive sufficiency gate admits topically adjacent evidence" — the disjunction is exonerated for these leaks. Honest line: "a sufficiency threshold fitted to one corpus admitted non-answering evidence on another by ~0.03." A reviewer may fairly say "then re-tune it"; accept that.
  - Secondary observation (offer as conjecture, n=4): **in 3 of 4 leaks the averaged set was a SINGLE chunk** (Stage-3 dropped 29 of 30), so H2's "average" degenerates to one chunk's score, permitted by `MIN_CHUNKS_FOR_SUFFICIENCY = 1`. H2 may be least reliable exactly where Stage 3 works best. Q017 is a genuine 4-chunk mean. This is the better future-work thread.
  - Latent (not a current defect): `_query_coverage` returns 1.0 on an EMPTY evidence set (control Q049); inert only because H1/H3 reject first.
  - Corrects a wrong guess in `CORPUS2_REPORT.md` §3: Q055 did NOT match the IT policy's "library subscription databases" sentence; its one surviving chunk was `Tuition_and_Financial_Aid_Policy.docx` (Work-Study/Refunds) and contains no "library" at all. Q050/Q078 survived on the Housing policy *document header*. Adjacency was document-level, not sentence-level.
  - Written up in `experiments_corpus2/CORPUS2_REPORT.md` §3a (added, existing numbers untouched). Harness `experiments_corpus2/diagnose_gap_leakage.py`, raw `gap_leakage_diagnosis.json`. Replay reproduces all 6 recorded verdicts exactly. **FROZEN files verified byte-for-byte unchanged via `git status` (validation/orchestrator/synthesis).** Zero LLM tokens.
- ⚠️ For PAPER chat: `CORPUS2_REPORT.md` prose is full of em dashes (user standing preference = none); §3a is written clean, the older sections are not. Strip before lifting into the .tex.
- Next (optional): fold a Corpus-2 subsection into the paper draft (PAPER chat); no further CORPUS2 work required unless requested.

---
*Update protocol: change the "Last updated" line, edit your chat's status block, add a line under "Recently decided". Keep it short — this is a dashboard, not a report.*
