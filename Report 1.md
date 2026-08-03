# HR Policy RAG — Evaluation Report (v3)

**Corpus:** 10 documents (`HR_Policy_Document_01–10.docx`)
**Queries:** 30 (`HR_RAG_Evaluation_Queries.txt`)
**Mode:** Decision-only — routing/conflict logic. The answer-writing LLM was disabled (deterministic mock), so no network calls; the *wording* of answers is not evaluated here.
**Companion docs:** `RAG_System_Observation_Log.md` (running fix log), `RAG_Metrics_Guide.md` (metric definitions).

---

## ⚠️ Corrections to earlier drafts (read this first)

All numbers below were **recomputed from the three saved raw runs against a single fixed gold-label set**. Two figures quoted in the v1/v2 drafts were wrong and are corrected here:

| Claim in earlier drafts | Correct value | Why it was wrong |
|---|---|---|
| "Baseline = **10/30**" | **12/30** | The original count graded borderline queries inconsistently. Recomputed consistently, v1 = 12/30. |
| Unsafe-answer rate reported only as "0.00" | v1 was **4/23 (0.17)** | The 0.00 figure was true for v2/v3 only. v1 *answered* 4 queries whose documents conflict (Q10, Q12, Q13, Q15). |

If you have already used 10/30 anywhere, replace it with **12/30**. (The observation log and metrics guide still contain the old 10/30 figure and need the same correction.)

---

## 1. The three versions

| Version | What it contains |
|---|---|
| **v1** | Validator with query-scoped conflict detection, pruned antonym list, `same_section` removed. *(This is the first measured state — not the untouched original system.)* |
| **v2** | v1 **+ Fix A** (un-gate the NLI check) **+ Fix B** (report the actual conflicting pair) |
| **v3** | v2 **+ Fix C** (reactivate the dead sufficiency check) |

---

## 2. Headline results

Gold labels are fixed across all three versions. **Q4 ("what benefits are available?") is genuinely ambiguous** — the corpus contains a "Benefits Guide" but it only documents annual leave (and the two documents disagree on it). Because the v2→v3 difference is *entirely* Q4, both gradings are shown so nothing is hidden:

| | v1 | v2 | v3 |
|---|---|---|---|
| **Decision accuracy** (Q4 graded "Answer") | 12/30 (0.40) | **21/30 (0.70)** | 20/30 (0.67) |
| **Decision accuracy** (Q4 graded "Insufficient") | 11/30 (0.37) | 20/30 (0.67) | **21/30 (0.70)** |
| **Conflict precision** | 0.57 | **0.73** | **0.73** |
| **Conflict recall** | 0.44 | **0.89** | **0.89** |
| **Conflict F1** | 0.50 | **0.80** | **0.80** |
| **Unsafe answers** (answered despite conflict/no evidence) | **4 / 23** | **0 / 23** | **0 / 23** |
| **False abstentions** (refused an answerable query) | 4 / 7 | 3 / 7 | 4 / 7 |

**Read honestly:**
- The **big win is v1 → v2**: conflict F1 0.50 → 0.80, and unsafe answers **4 → 0**.
- **v3 changes exactly one query (Q4)** and leaves every conflict metric identical. Its score impact is +1 or −1 depending purely on that ambiguous label. **v3's justification is robustness, not the score** (see Fix C).

---

## 3. Ground truth — the corpus

Each document is a themed HR policy padded with identical boilerplate, carrying one distinctive fact. All are "Version: 2025.2"; every distinctive sentence sits under the heading "Policy Statement".

| Topic | Doc A | Doc B | Conflict? |
|---|---|---|---|
| Annual leave | D03 = 20 days | D04 = 15 days | ✅ |
| Remote work | D01 = 3 days/wk, mgr approval | D02 = office 5 days/wk, exec-only | ✅ |
| Performance reviews | D05 = twice/yr | D06 = once/yr | ✅ |
| Probation | D07 = 6 months | D08 = 3 months | ✅ |
| Personal devices | D09 = may **not** use | D10 = **may** use (if MDM-enrolled) | ✅ |
| Working hours | *not stated anywhere* | | ❌ → Insufficient |
| Maternity / contract staff | *not in corpus* | | ❌ → Insufficient |
| International travel reimbursement | *not in corpus* | | ❌ → Insufficient |
| "Newest version" | all identical (2025.2) | | ❌ → indeterminable |

Titles: D01 Employee Handbook · D02 Attendance Policy · D03 Leave Policy · D04 Benefits Guide · D05 Performance Management · D06 Manager Handbook · D07 Recruitment & Onboarding · D08 Operations Manual · D09 IT & Security Policy · D10 Flexible Work Guidelines.

**Grading rule:** documents disagree on the asked fact → **Conflict**; documents agree / only one has it → **Answer**; no document has it → **Insufficient**.

---

## 4. The fixes, and what each one actually bought

### Fix A — Un-gate the NLI conflict check *(v1 → v2)*
**Problem.** The three contradiction checks only ran when two passages were *lexically* similar (`similarity ≥ 0.68`). But the NLI model exists precisely to catch contradictions worded *differently* — which are lexically **dis**similar. So the gate silently switched off the very check meant to catch them.

**Evidence.** The NLI model correctly flagged every planted conflict; it was simply never consulted:

| Conflict | lexical similarity | NLI verdict | Detected in v1? |
|---|---|---|---|
| Reviews (twice vs once) | 0.674 | CONTRADICTION | ❌ (just under 0.68) |
| Remote work (3 days vs exec-only) | 0.440 | CONTRADICTION | ❌ |
| Personal devices (may not vs may) | 0.439 | CONTRADICTION | ❌ |
| Leave (20 vs 15) | 0.933 | CONTRADICTION | ✅ |

**Fix.** Keyword and numeric checks stay gated on lexical similarity; the **NLI check now runs on any query-relevant cross-document pair** (above a tiny 0.15 floor kept only for speed). *File: `validation.py`.*

**Result — 9 queries improved, 0 regressed:**
- **8 conflicts recovered:** Q7, Q10, Q12, Q13, Q15, Q18, Q22, Q29.
- **Q16** moved from a false "insufficient" to a correct comparison.
- **Critically, 4 unsafe answers eliminated.** In v1 the system *answered* Q10, Q12, Q13 and Q15 — confidently replying about personal devices, remote work and review frequency while the documents flatly contradicted each other. This is the single most important correctness gain.

### Fix B — Report the actual conflicting pair *(v1 → v2)*
**Problem.** Conflict detection returned only true/false, discarding *which* documents clashed. The abstention message therefore listed **every** retrieved source (up to 8) with a blind 200-character excerpt — which landed on boilerplate.

**Fix.** Conflict detection now returns the offending pair; the message cites **only those two documents** and shows the most on-topic sentence from each. *Files: `validation.py`, `orchestrator.py`.*

**Result.** No decision changes (it doesn't affect routing) but the output becomes usable:
- **Before:** Q11 cited 6 documents, excerpt = *"…reviews exceptions, and periodically updates guidance…"*
- **After:** Q11 cites exactly **D03 ("…20 working days of paid annual leave…") vs D04 ("…15 working days…")**.

### Fix C — Reactivate the dead sufficiency check *(v2 → v3)*
**Problem.** The "average evidence quality" gate compared the average score against **0.55**, but every chunk that survives filtering already scores **≥ 0.60**. The threshold sat *below the floor*, so the gate could never fire — it was dead code, and weak evidence passed unchecked. (The code comment admitted it had been *"Lowered from 0.65"* — the lowering is what killed it.)

**Fix.** Restored the threshold to **0.65** (one line). Anything ≥ 0.72 would wrongly reject a good query (Q3 averages 0.717), so 0.65 is the correct restore point.

**Result — exactly 1 query changed:** Q4 moved from *answer* to *insufficient*, because its evidence is genuinely weak (average relevance **0.378**; the corpus never actually enumerates benefits). Every conflict decision is untouched, because a detected conflict outranks sufficiency.

**Honest assessment:** this fix does **not** improve the headline score — it either +1s or −1s it depending on how Q4 is labelled. Its real value is **robustness**: the quality gate is alive again, so on new data weak evidence will be rejected instead of silently answered.

---

## 5. Per-query results (v1 → v2 → v3)

Legend: **A** = Answer · **C** = Conflict · **I** = Insufficient. Verdict is for **v3** (Q4 graded "Answer").

| # | Question | Gold | v1 | v2 | v3 | Verdict (v3) |
|---|---|---|---|---|---|---|
| 1 | Standard working hours? | I | C | C | C | ❌ false conflict |
| 2 | Info-security policy for remote workers? | A | C | C | C | ❌ false conflict |
| 3 | Manager responsibilities re attendance? | A | A | A | A | ✅ |
| 4 | Benefits available to eligible employees? | A / I ⚠️ | A | A | **I** | ⚠️ ambiguous gold |
| 5 | Documentation for policy exceptions? | I | C | C | C | ❌ false conflict |
| 6 | Summarize leave policies | C | C | C | C | ✅ |
| 7 | Summarize performance-evaluation policies | C | **I** | C | C | ✅ fixed in v2 |
| 8 | Onboarding & probation policies? | C | C | C | C | ✅ |
| 9 | List documents discussing remote work | A | I | I | I | ❌ false abstention |
| 10 | Policies governing personal devices? | C | **A** ⚠unsafe | C | C | ✅ fixed in v2 |
| 11 | How many annual leave days? | C | C | C | C | ✅ |
| 12 | Is remote work allowed? | C | **A** ⚠unsafe | C | C | ✅ fixed in v2 |
| 13 | How often are reviews conducted? | C | **A** ⚠unsafe | C | C | ✅ fixed in v2 |
| 14 | Probation period? | C | C | C | C | ✅ |
| 15 | Can employees use personal laptops? | C | **A** ⚠unsafe | C | C | ✅ fixed in v2 |
| 16 | Compare remote-work policies | A | **I** | A | A | ✅ fixed in v2 |
| 17 | Compare annual-leave policies | A | A | A | A | ✅ |
| 18 | Which docs differ on review schedules? | C | **I** | C | C | ✅ fixed in v2 |
| 19 | Which policies disagree on probation? | C | C | C | C | ✅ |
| 20 | Which docs have conflicting attendance reqs? | C | I | I | I | ❌ missed conflict |
| 21 | Remote 3 days/wk — security requirements? | A | C | C | C | ❌ false conflict |
| 22 | Personal laptop while remote — permitted? | C | **I** | C | C | ✅ fixed in v2 |
| 23 | Probation period + first review timing | C | C | C | C | ✅ |
| 24 | Maternity leave for contract employees? | I | C | C | C | ❌ false conflict |
| 25 | International travel reimbursement? | I | I | I | I | ✅ |
| 26 | Contradictions regarding leave? | C | C | C | C | ✅ |
| 27 | Identify all conflicting policies | C | I | I | I | ❌ missed conflict |
| 28 | Which document is the newest version? | I | C | C | C | ❌ false conflict |
| 29 | Which policy if remote work disagrees? | C | **I** | C | C | ✅ fixed in v2 |
| 30 | Consolidate, resolving conflicts | C | C | C | C | ✅ |

---

## 6. Limitations that remain in v3

Nine queries are still wrong (ten if Q4 is graded "Answer"). They fall into exactly three groups.

### Limitation 1 — Six false conflicts *(drives conflict precision down to 0.73)*
**Queries: Q1, Q2, Q5, Q21, Q24, Q28.**

- **Q1** ("standard **working** hours") — no document states working hours. The word "working" matches "20 **working** days" / "15 **working** days" in the leave documents, so the leave conflict fires on a question about hours.
- **Q24** ("**maternity** leave for contract employees") — not in the corpus. The word "leave" matches the annual-leave documents → same spurious leave conflict.
- **Q5** ("documentation for policy exceptions") — only generic boilerplate exists.
- **Q28** ("newest version") — all documents are Version 2025.2, so it's indeterminable; the NLI model wrongly reads two different document *titles* as contradictory.
- **Q2 / Q21** (security for remote workers) — answerable from D09, but a conflict is raised instead.

**Important:** these are **soft failures**. All six **abstain** — the system never emits a wrong answer, it just gives the wrong *reason* ("conflict" instead of "insufficient"). The message is misleading (Q1 shows "20 vs 15 working days" for an hours question), but no misinformation is produced.

**Why this isn't easily fixable — measured, not guessed.** Three candidate fixes were tested and all fail, because the false conflict scores *higher* on every relevance signal than a real conflict we must keep (Q6):

| Signal | Q1 (false conflict) | Q6 (real conflict) | Verdict |
|---|---|---|---|
| Sentence-embedding similarity to query | **0.547** | 0.464 | false > true |
| Conflicting-chunk relevance | **0.53** | 0.449 | false > true |
| ≥2 query-word overlap rule | 1 word | 1 word | can't separate; dropping Q1 also drops Q6 |

Any threshold that removes Q1 also removes the real leave conflict. **Decision: accepted as a known limitation.**

**Possible future fix:** a query-intent step that understands "working hours" ≠ "working days" and "maternity leave" ≠ "annual leave". Realistically this needs a small LLM classification call, which departs from the deterministic design — a deliberate trade-off, not an oversight.

### Limitation 2 — Two missed conflicts on "find the conflicts" queries *(caps conflict recall at 0.89)*
**Queries: Q20** ("which documents contain conflicting attendance requirements") and **Q27** ("identify all conflicting policies"). Both return *insufficient*.

**Cause.** These queries are phrased in *meta* language ("which documents", "conflicting", "identify") that never appears in the policy text, so the query-relevance step finds nothing to compare and the coverage gate abstains. Ironically, the queries explicitly asking to find conflicts are the ones that don't.

**Possible fix (small).** Treat meta/aggregation words (*compare, identify, conflicting, disagree, which documents*) as instruction words rather than content words, and route "find the conflicts" queries straight to conflict detection regardless of coverage. Additionally, conflict detection currently returns only the **first** conflicting pair — Q27 asks for *all* of them, which would need it to collect every pair rather than stop at the first.

### Limitation 3 — One false abstention on a listing query
**Query: Q9** ("list all documents that discuss remote work"). Returns *insufficient* with **zero** chunks surviving relevance filtering.

**Cause.** The relevance floor is based on dense-embedding similarity only, and a short meta query like this embeds poorly, so every chunk is dropped — even though the reranker had ranked them fine.

**Possible fix (small).** Base the relevance floor on the reranker's score (`max(dense, hybrid)`) rather than dense similarity alone, so short/meta queries don't zero out.

### Limitation 4 — One ambiguous gold label
**Q4** ("what benefits are available?"). The corpus has a "Benefits Guide" but it only documents annual leave — and the two documents disagree on that. Reasonable evaluators could label this **Answer**, **Insufficient**, or even **Conflict**. This is a *labelling* limitation, not a system defect; state your choice explicitly in the paper.

---

## 7. Summary of what improved

| | v1 | v3 |
|---|---|---|
| Non-numeric conflicts (remote / reviews / devices) | all missed | all caught |
| Unsafe answers (answered despite conflict) | **4** | **0** |
| Conflict F1 | 0.50 | **0.80** |
| Conflict attribution | up to 8 docs, boilerplate excerpts | exactly the 2 disagreeing docs + their sentences |
| Sufficiency quality gate | dead (could never fire) | active |
| Decision accuracy | 12/30 | 20–21/30 |

**Strongest claim you can defend:** the system now detects every planted conflict type, names the exact documents that disagree, and **never answers on conflicting or missing evidence** — at the cost of some over-caution (it refuses 4 of 7 answerable queries) and 6 abstentions given the wrong reason.

---

## 8. Caveats

- **Decision-only evaluation.** The generated answer *text* was not scored (faithfulness, citation accuracy). That needs a separate run with the real answer LLM plus expected answers.
- **Gold labels are the author's reading** of the 10 documents; no official key was supplied. Q2, Q4 and Q21 are judgment calls and are flagged as such.
- **Small test set.** 30 queries and 5 conflict pairs is thin; a larger set would make the numbers more robust.
- **v1 is not the untouched original system** — it already contained query-scoped conflict detection, a pruned antonym list, and the `same_section` removal.
