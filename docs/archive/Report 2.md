# Meridian Grid HR RAG — Evaluation Report (v6)

## Headline: 92.3% decision accuracy — and every remaining error is the same *safe* kind

The pipeline now answers **72 of 78** queries correctly. More importantly, the errors it does make are all one type: it occasionally raises a conflict on a question it could have answered. It **never invents an answer, never misses a conflict, and never refuses a question for lack of evidence it actually had**.

| The three ways a system like this can fail | v6 count |
|---|---|
| Answered despite the documents conflicting or the evidence being missing (**unsafe**) | **0** |
| Missed a real conflict between documents | **0** |
| Refused an answerable question ("insufficient") | **0** |
| Flagged a conflict on an answerable question (**over-cautious**) | 6 |

All six remaining errors are over-caution. The system abstains and shows the user the two documents it thinks disagree — it never misinforms.

---

## 1. The data

**Corpus — 11 authored enterprise policies** for a fictional UK company, *Meridian Grid Technologies Ltd* (`data/*.docx`). Facts sit in real numbered clauses under real Word heading styles, and the documents cross-reference each other. Unlike the previous corpus, these were **authored first to a fixed fact map**, so every query's correct answer is known **by construction**, not guessed afterwards.

| Doc ID | File | Title |
|---|---|---|
| MGT-HR-001 | `Employee_Handbook.docx` | Employee Handbook |
| MGT-HR-002 | `Leave_and_Time_Off_Policy.docx` | Leave & Time-Off Policy |
| MGT-HR-003 | `Flexible_and_Remote_Work_Policy.docx` | Flexible & Remote Work Policy (2025, current) |
| MGT-HR-003a | `Remote_Working_Policy_2023_Superseded.docx` | Remote Working Policy (2023, **superseded**) |
| MGT-HR-004 | `Compensation_and_Benefits_Policy.docx` | Compensation & Benefits Policy |
| MGT-HR-005 | `Performance_Management_Policy.docx` | Performance Management Policy |
| MGT-HR-006 | `Recruitment_and_Onboarding_Policy.docx` | Recruitment & Onboarding Policy |
| MGT-HR-007 | `IT_and_Acceptable_Use_Policy.docx` | IT & Acceptable Use Policy |
| MGT-HR-008 | `Travel_and_Expense_Policy.docx` | Travel & Expense Policy |
| MGT-HR-009 | `Code_of_Conduct_and_Disciplinary_Policy.docx` | Code of Conduct & Disciplinary Policy |
| MGT-HR-010 | `Health_and_Safety_Policy.docx` | Health & Safety Policy |

**Ground truth** (`data/ground_truth.json`): **45 facts, 4 planted conflicts, 6 deliberate gaps.** Every query traces to an entry there; all 78 were text-verified against the documents (78/78, `data/phase5_verification_report.md`).

### The 78 questions — by expected answer

| Expected | Count | Meaning |
|---|---|---|
| **Answer** | 46 | a document states it (alone or in agreement) |
| **Conflict** | 16 | two documents disagree on the asked fact |
| **Insufficient** | 16 | no document states it |

### The 78 questions — by type

| Type | Count | Answer / Conflict / Insufficient | What it tests |
|---|---|---|---|
| single-fact lookup | 18 | 15 / 0 / 3 | one clause, one number |
| multi-part | 10 | 9 / 0 / 1 | two facts in one question |
| cross-document comparison | 10 | 6 / 4 / 0 | "compare X in A and B" |
| conflict-probing | 10 | 0 / 10 / 0 | the planted conflicts asked plainly |
| out-of-scope / insufficient | 10 | 0 / 0 / 10 | topics the corpus never covers |
| aggregation / list-all | 8 | 8 / 0 / 0 | "list all …" |
| scenario / applied | 12 | 8 / 2 / 2 | "I'm a new starter, …" |
| **Total** | **78** | **46 / 16 / 16** | |

### The 4 planted conflicts

| ID | Topic | Doc A | Doc B |
|---|---|---|---|
| C1 | Probationary period | Employee Handbook = **3 months** | Recruitment & Onboarding = **6 months** |
| C2 | Max remote days/week | Flexible & Remote Work (2025) = **3 days** | Remote Working 2023 (superseded) = **2 days** |
| C3 | Employer pension contribution | Compensation & Benefits = **6%** | Employee Handbook = **5%** |
| C4 | Personal device for work email | IT & Acceptable Use = **permitted** (if MDM-enrolled) | Code of Conduct = **prohibited** |

### The 6 deliberate gaps
Company car · share options/equity · relocation allowance · on-site childcare · jury service pay · pets in the office.

**Grading rule:** documents disagree on the asked fact → **Conflict**; a document states it → **Answer**; no document states it → **Insufficient**.

**Mode:** decision-only. The answer-writing LLM is disabled (deterministic mock, no network calls), so this report scores *routing and conflict detection*, not answer wording.

---

## 2. Version history — what each fix bought

> ⚠️ **Read the two blocks separately.** v1–v3 ran on the **old** 10-document / 30-query corpus; v4–v6 run on the **new** 11-document / 78-query corpus. The corpus changed between v3 and v4, so this is **not** one continuous curve — compare within a block, not across.

| Version | Corpus | Fix applied in this version | Accuracy |
|---|---|---|---|
| **v1** | old (30 q) | — first measured state | 12/30 = 40.0% |
| **v2** | old (30 q) | **Fix A** — un-gate the NLI check<br>**Fix B** — report the actual conflicting pair | 21/30 = 70.0% |
| **v3** | old (30 q) | **Fix C** — reactivate the dead sufficiency gate | 20/30 = 66.7% † |
| — | *corpus replaced — old corpus was thin boilerplate with guessed labels* | | |
| **v4** | new (78 q) | — no pipeline change; same code, new corpus | 53/78 = 67.9% |
| **v5** | new (78 q) | **Fix D** — sufficiency checks AND → OR | 65/78 = 83.3% |
| **v6** | new (78 q) | **Fix E** — NLI threshold 0.80 → 0.94<br>**Fix F** — remove the comparison override | **72/78 = 92.3%** |

† v3 is 20/30 or 21/30 depending on how one ambiguous query is graded. Fix C's value was robustness, not score.

### What each fix actually did

**Fix A — un-gate the NLI check.** All three contradiction checks only ran when two passages were *lexically* similar (≥ 0.68). But the NLI model exists to catch contradictions that are **worded differently** — which are lexically *dis*similar. The gate silently switched off the very check meant to catch them. Keyword/numeric stay gated; NLI now runs on any query-relevant cross-document pair.

**Fix B — report the actual conflicting pair.** Conflict detection returned only true/false, discarding *which* documents clashed, so the message listed every retrieved source with a blind excerpt. It now names the two documents and quotes the clashing sentence from each. (No score change — it makes the output usable.)

**Fix C — reactivate the dead sufficiency gate.** The evidence-quality gate compared the average score against 0.55, but every surviving chunk already scores ≥ 0.60. The threshold sat *below the floor*, so it could never fire.

**Fix D — sufficiency AND → OR.** Evidence had to clear **both** average-score (≥0.65) **and** coverage (≥0.55). Those two punish opposite but legitimate question shapes: a precise single-fact question retrieves few but strongly-relevant chunks (high score, low coverage); a list question retrieves many (high coverage, diluted score). Requiring both over-abstained on both shapes. Making it an **OR** recovered 12 false abstentions and broke none of the 16 gap queries — every out-of-scope query is weak on *both* signals, so it still abstains.

**Fix E — NLI threshold 0.80 → 0.94.** We measured the actual contradiction score of every firing pair. **Every true conflict scores ≥ 0.965; most false ones score ≤ 0.9194** — an empty band sat between them, and the threshold was parked in the noise floor. Moving it mid-gap removed 3 false conflicts and lost **zero** true conflicts.

**Fix F — remove the comparison override.** All four "compare A and B" conflict queries were being answered instead of flagged. The cause was **not** the model: Stage 4 detected all four correctly, with the right document pair, at NLI 0.965–0.9999. An override in the orchestrator then **threw the conflict away** whenever the query was classified "complex" (compare/versus), on the theory that differences between documents are expected for comparison questions. It fired on exactly 4 queries and hid a real conflict in every one, while protecting none. Removing it took conflict recall from 12/16 to **16/16**.

---

## 3. Metrics (v6)

**Confusion matrix** — rows = what it should give, columns = what it gave:

| should ↓ / gave → | Answer | Conflict | Insufficient | total |
|---|---|---|---|---|
| **Answer** | **40** | 6 | 0 | 46 |
| **Conflict** | 0 | **16** | 0 | 16 |
| **Insufficient** | 0 | 0 | **16** | 16 |

Every off-diagonal cell is zero except one. That single cell — 6 answerable questions flagged as conflicts — is the entire remaining error surface.

| Metric | v5 | **v6** |
|---|---|---|
| **Decision accuracy** | 65/78 = 83.3% | **72/78 = 92.3%** |
| **Conflict precision** | 12/21 = 0.571 | **16/22 = 0.727** |
| **Conflict recall** | 12/16 = 0.750 | **16/16 = 1.000** |
| **Conflict F1** | 0.649 | **0.842** |
| **Answer recall** | 37/46 = 80.4% | **40/46 = 87.0%** |
| **Gap / insufficient recall** | 16/16 = 100% | **16/16 = 100%** |
| **Unsafe answers** (answered despite conflict/no evidence) | 0/32 | **0/32** |
| **False abstentions** (refused an answerable query) | 0/46 | **0/46** |

Verified against the saved v5 baseline (`data/phase6_fullrun_results_v5.json`): **7 queries improved, 0 regressed.**

---

## 4. Per-query results (v6)

Legend: **A** = Answer · **C** = Conflict · **I** = Insufficient
### single-fact lookup  (18 queries — 17/18 correct)

| # | Query | Should give | Gave | Verdict |
|---|---|---|---|---|
| Q001 | How many days of annual leave do full-time employees get? | A | C | ❌ false conflict<br>_nli: Remote Working Policy 2023 Superseded vs Flexible and Remote Work Policy_ |
| Q002 | What is the maximum annual leave I can carry over to next year? | A | A | ✅ |
| Q003 | How many weeks of full pay does enhanced maternity leave provide? | A | A | ✅ |
| Q004 | How much paternity leave is offered? | A | A | ✅ |
| Q005 | What is the business mileage reimbursement rate? | A | A | ✅ |
| Q006 | What is the deadline for submitting an expense claim? | A | A | ✅ |
| Q007 | What is the hotel room cap for a stay in London? | A | A | ✅ |
| Q008 | What is the subsistence cap for an evening meal? | A | A | ✅ |
| Q009 | Over what value must a gift be declared? | A | A | ✅ |
| Q010 | What is the minimum password length? | A | A | ✅ |
| Q011 | How much is the employee referral bonus? | A | A | ✅ |
| Q012 | What is the ratio of trained first-aiders to employees? | A | A | ✅ |
| Q013 | How often are fire evacuation drills held? | A | A | ✅ |
| Q014 | What performance rating scale is used? | A | A | ✅ |
| Q015 | What multiple of salary is provided as life assurance? | A | A | ✅ |
| Q016 | Am I eligible for a company car? | I | I | ✅ |
| Q017 | Does the company offer share options or stock to employees? | I | I | ✅ |
| Q018 | Is jury service paid? | I | I | ✅ |

### multi-part  (10 queries — 9/10 correct)

| # | Query | Should give | Gave | Verdict |
|---|---|---|---|---|
| Q019 | What is the annual leave entitlement and how many days can be carried over? | A | C | ❌ false conflict<br>_nli: Leave and Time Off Policy vs Remote Working Policy 2023 Superseded_ |
| Q020 | What is the mileage rate and the deadline to claim it? | A | A | ✅ |
| Q021 | How much maternity and paternity leave is provided? | A | A | ✅ |
| Q022 | What is the minimum password length and is multi-factor authentication required? | A | A | ✅ |
| Q023 | What are the subsistence caps for breakfast and an evening meal? | A | A | ✅ |
| Q024 | What are the hotel caps in London and elsewhere in the UK? | A | A | ✅ |
| Q025 | How large is the annual bonus and when is it paid? | A | A | ✅ |
| Q026 | What is the first-aider ratio and how often are fire drills held? | A | A | ✅ |
| Q027 | When are performance reviews held and what rating scale is used? | A | A | ✅ |
| Q028 | What relocation allowance and childcare support does the company provide? | I | I | ✅ |

### cross-document comparison  (10 queries — 9/10 correct)

| # | Query | Should give | Gave | Verdict |
|---|---|---|---|---|
| Q029 | What is the standard full-time working week across the company? | A | C | ❌ false conflict<br>_nli: Flexible and Remote Work Policy vs Leave and Time Off Policy_ |
| Q030 | Compare annual leave entitlement with sabbatical eligibility. | A | A | ✅ |
| Q031 | How does the mileage rate change after 10,000 miles? | A | A | ✅ |
| Q032 | Compare the expense approval limit for a line manager versus a department head. | A | A | ✅ |
| Q033 | Compare when salary reviews take effect with when promotions take effect. | A | A | ✅ |
| Q034 | How many days of compassionate leave are provided compared with paternity leave? | A | A | ✅ |
| Q035 | Compare the maximum remote-working days per week in the current and the 2023 policies. | C | C | ✅ |
| Q036 | What does the probationary period length say in the Handbook versus the Recruitment policy? | C | C | ✅ |
| Q037 | Compare the employer pension contribution in the Handbook and the Compensation policy. | C | C | ✅ |
| Q038 | Compare the rule on personal-device email access in the IT policy and the Code of Conduct. | C | C | ✅ |

### conflict-probing  (10 queries — 10/10 correct)

| # | Query | Should give | Gave | Verdict |
|---|---|---|---|---|
| Q039 | How many days per week am I allowed to work remotely? | C | C | ✅ |
| Q040 | What is the probationary period for new employees? | C | C | ✅ |
| Q041 | What percentage does the employer contribute to my pension? | C | C | ✅ |
| Q042 | Can I use my personal phone to access work email? | C | C | ✅ |
| Q043 | What is the maximum number of remote working days allowed per week? | C | C | ✅ |
| Q044 | How long is the probation period for a new starter? | C | C | ✅ |
| Q045 | What is the employer pension contribution rate? | C | C | ✅ |
| Q046 | Is accessing corporate email on a personal mobile device allowed? | C | C | ✅ |
| Q047 | Up to how many days a week can eligible employees work from home? | C | C | ✅ |
| Q048 | What is the length of the probationary period at the company? | C | C | ✅ |

### out-of-scope / insufficient  (10 queries — 10/10 correct)

| # | Query | Should give | Gave | Verdict |
|---|---|---|---|---|
| Q049 | What is the company's current stock price? | I | I | ✅ |
| Q050 | Can I bring my dog to the office? | I | I | ✅ |
| Q051 | What relocation allowance is available when moving for a role? | I | I | ✅ |
| Q052 | Are childcare vouchers or an on-site nursery available? | I | I | ✅ |
| Q053 | How do I receive equity or share options? | I | I | ✅ |
| Q054 | What are the eligibility rules for a company car? | I | I | ✅ |
| Q055 | Will I be paid while on jury service? | I | I | ✅ |
| Q056 | What is the CEO's total annual salary? | I | I | ✅ |
| Q057 | Does the company pay for a gym membership? | I | I | ✅ |
| Q058 | Is dental insurance included in benefits? | I | I | ✅ |

### aggregation / list-all  (8 queries — 6/8 correct)

| # | Query | Should give | Gave | Verdict |
|---|---|---|---|---|
| Q059 | List all the types of leave available to employees. | A | A | ✅ |
| Q060 | What are the data classification levels used by the company? | A | A | ✅ |
| Q061 | What core benefits does the company offer? | A | A | ✅ |
| Q062 | List the stages of the disciplinary procedure. | A | C | ❌ false conflict<br>_numeric: Compensation and Benefits Policy vs IT and Acceptable Use Policy_ |
| Q063 | How does annual leave increase with length of service? | A | A | ✅ |
| Q064 | What personal protective equipment is required for field work? | A | C | ❌ false conflict<br>_nli: Health and Safety Policy vs Remote Working Policy 2023 Superseded_ |
| Q065 | What pre-employment checks are carried out before a new hire starts? | A | A | ✅ |
| Q066 | What are the expense approval thresholds and accommodation caps? | A | A | ✅ |

### scenario / applied  (12 queries — 11/12 correct)

| # | Query | Should give | Gave | Verdict |
|---|---|---|---|---|
| Q067 | I have completed 6 years of service. How many annual leave days am I entitled to? | A | A | ✅ |
| Q068 | I drove 12,000 business miles this year in my own car. How is that reimbursed? | A | A | ✅ |
| Q069 | I have 3 years' service and want a sabbatical. Am I eligible? | A | A | ✅ |
| Q070 | A supplier offered me a gift worth GBP 70. What should I do? | A | A | ✅ |
| Q071 | I have been off sick long-term after 2 years' service. What sick pay do I get? | A | A | ✅ |
| Q072 | As a new starter, when will my first formal performance review be? | A | C | ❌ false conflict<br>_nli: Performance Management Policy vs Recruitment and Onboarding Policy_ |
| Q073 | I want to claim an expense from 45 days ago. Will it be paid? | A | A | ✅ |
| Q074 | I am booking a hotel in London for a business trip. What is the nightly limit? | A | A | ✅ |
| Q075 | I am a new employee. How long is my probationary period? | C | C | ✅ |
| Q076 | I would like to work from home. How many days a week can I do that? | C | C | ✅ |
| Q077 | I am relocating cities for this role. What relocation support can I claim? | I | I | ✅ |
| Q078 | Can I bring my pet to work on Fridays? | I | I | ✅ |

---

## 5. How much of this generalises? (structural fixes vs tuned numbers)

Before the limitations, an honest accounting of *what kind of thing* each fix is — because it determines whether the 92.3% would survive a different corpus. A fix is **structural** if it corrects a design mistake that is wrong regardless of data, and **calibrated** if its value was fitted to *this* corpus and would need re-fitting on another.

| Fix | Type | Would it transfer to a new corpus? |
|---|---|---|
| **A** — un-gate the NLI check | **Structural** | ✅ Yes. Gating a *semantic* check behind *lexical* similarity defeats its purpose — true on any data. |
| **B** — report the conflicting pair | **Structural** | ✅ Yes. Pure explainability; no numbers. |
| **F** — remove the comparison override | **Structural** | ✅ Mostly. A component was discarding correct results. (Caveat: the "summarise both A and B" query shape is untested — §6.) |
| **D** — sufficiency AND → OR | **Structural reasoning, tuned numbers** | ⚠️ Partly. The *argument* (precise vs broad questions stress opposite signals) is general; the thresholds 0.65/0.55 are fitted. |
| **C** — restore the sufficiency gate | **Tuned** | ⚠️ Partly. The *finding* (a gate was dead) is structural; the value 0.65 is fitted. |
| **E** — NLI threshold 0.80 → 0.94 | **Purely calibrated** | ❌ No. Fitted to a gap measured on 20 conflict scores from this one corpus. |

**What this means for the paper.** The transferable contribution is **not the number 0.94** — it is the *procedure* that produced it:

> Measure the contradiction-score distribution of known-true vs known-false conflicts. If a gap exists, place the threshold in it. If the distributions overlap, a threshold is the wrong tool and a different signal is needed.

That method reproduces on any corpus even though the specific threshold does not. The same holds for Fix D: "these two signals penalise opposite question shapes, so combine them with OR" is reusable reasoning; the thresholds are not. **A single corpus cannot support a generalisation claim — only a second corpus can — so this report claims a working system and a reusable method, not a portable accuracy number.**

---

## 6. Limitations that remain — and how to fix them

All six errors are the same shape: **a false conflict on an answerable question.** They are *soft* failures — the system abstains and shows the two documents it believes disagree, so no wrong information reaches the user.

| # | Query | Flagged pair | Prong |
|---|---|---|---|
| Q001 | annual leave days | Remote 2023 vs Flexible & Remote | NLI |
| Q019 | annual leave entitlement + carry-over | Leave & Time-Off vs Remote 2023 | NLI |
| Q029 | standard working week | Flexible & Remote vs Leave & Time-Off | NLI |
| Q064 | PPE for field work | Health & Safety vs Remote 2023 | NLI |
| Q072 | first review as a new starter | Performance Mgmt vs Recruitment | NLI |
| Q062 | list disciplinary stages | Compensation vs IT & Acceptable Use | numeric |

### Limitation 1 — the system compares document pairs that are irrelevant to the question (Q001, Q019, Q029, Q064, Q072)

**This is the core open problem.** For a broad question, retrieval pulls in many chunks; the detector then compares *every* cross-document pair, including pairs that have nothing to do with what was asked. The NLI model, handed two unrelated policy sentences, sometimes declares a contradiction — often with very high confidence (Q029 = **0.9996**, Q064 = **0.9998**, i.e. *higher than every genuine conflict in the corpus*). The system has no step that asks **"is this pair even about the question?"** before judging it.

The **superseded 2023 Remote Working policy** is the loudest single offender — it shows up in the flagged pair for Q019 and Q064, on questions about leave and safety it has nothing to do with. But it is a *symptom*, not the disease: on a different corpus, some other irrelevant document takes its place and the identical failure returns. (This is also why the earlier "Limitation 1 / Limitation 3" split in draft v6 was wrong — they are one bug.)

**Why it is hard.** The fix everyone reaches for — "measure how relevant the pair is to the question and drop the irrelevant ones" — was tested on the previous corpus with three signals (lexical overlap, sentence-embedding similarity, chunk relevance) and **all three failed**: the false conflict scored *higher* than a real one on every signal. Separating "related enough to genuinely conflict" from "related enough to be retrieved but not to the point" needs actual query-**intent** understanding, which realistically means a small LLM classification step — a departure from the strictly-deterministic design. **This is the strongest candidate for an *accepted* limitation, and a good problem to end the paper on.**

**A narrow, partial mitigation (not a general fix).** *If* the document store already carries version metadata — many enterprise document systems do (SharePoint, Confluence, a DMS) — a superseded document can be restricted to conflict **only with its stated successor**, which removes Q019 and Q064. But this is **manual annotation the corpus must supply, not an algorithm**, and it directly conflicts with this project's own standing decision that policies may carry no date and the system must not guess recency. So: only usable when the metadata already exists; not something the pipeline can derive. **If applicable: +2 → 74/78.**

### Limitation 2 — the numeric check matches numbers that merely share a unit (Q062)

"List the stages of the disciplinary procedure" flags Compensation vs IT & Acceptable Use, because the deterministic numeric prong found two unrelated numbers with the same unit in two unrelated documents — like calling *"pension is 6%"* and *"bonus is 10%"* a contradiction because both are percentages.

**Suggested fix.** Require the two numbers to describe the **same fact**, not just the same unit — i.e. both sentences must also be on the query's subject. This is a genuine structural tightening (it removes a category of false match, not a fitted threshold), so it is more likely to transfer than Fix E. **Expected: +1 → 75/78.** Note it is a *sub-case* of Limitation 1 — "is this pair about the question?" — solved cheaply for the numeric prong because numbers are easy to anchor to a subject.

### Realistic ceiling
Limitation 2 is a clean structural tightening. Limitation 1 (five queries) is the real boundary: **the pipeline cannot yet tell whether a retrieved document pair is relevant to the question.** Everything above "answer safely or abstain" now depends on solving that one problem — which is exactly the kind of well-scoped open question a paper should name rather than paper over.

---

## 7. Caveats

- **Fix E spends safety margin — the one caveat to take seriously.** Raising the NLI threshold trades *over-caution* (a safe error) for a higher risk of a *missed* conflict (an unsafe error). On this corpus recall stayed 16/16, but that is a property of these 20 measurements, not of the method: on a new corpus a subtly-worded real conflict could score, say, 0.90, and at 0.94 the system would **miss it and answer with one document's value** — precisely the unsafe failure this whole approach exists to prevent. For a safety-first system, 0.94 is a deliberate risk setting, not a free accuracy gain, and a more conservative deployment might keep it lower and accept more false conflicts.
- **The headline number is corpus-specific.** 92.3% is this pipeline on this 78-query corpus. Half the gains (Fixes A, B, F) are structural and should transfer; the other half (C, D, E) are calibrated and would need re-fitting. See §5. Generalisation is unproven pending a second corpus.
- **Decision-only.** Answer *text* (faithfulness, citation accuracy) is not scored. That needs a run with the real answer LLM and expected answers.
- **Fix F is verified here, untested for one shape.** The override's original rationale was "summarise both doc A and doc B", where differences are expected rather than contradictory. No query of that shape exists in this 78-query set. Mitigating factor: the conflict message now names both documents and quotes the clashing sentence from each, which arguably serves that user better than silently answering.
- **The superseded document is deliberate**, both as planted conflict C2 and as a realistic source of retrieval noise. Both effects are visible above.
- **Gold labels are the author's by construction** and text-verified 78/78, but a few gaps are borderline (e.g. jury service: unpaid public-duties leave exists for magistrates; jury service specifically is never mentioned).
- **Runtime.** A full 78-query run takes ~30 min on CPU because conflict-free broad queries force the NLI cross-encoder to check every cross-document pair.
