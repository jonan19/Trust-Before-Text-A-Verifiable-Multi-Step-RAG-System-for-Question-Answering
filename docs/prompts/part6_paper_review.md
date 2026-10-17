# Part 6: Review and dissect main.tex (paste the block below into a new chat)

```
You are reviewing the research paper in D:\Major Project\main.tex ("Trust Before Text"). Your job
is to review it hard, dissect it, propose changes, and prove that every number in it traces to a
test we actually ran in this repo. Work in two phases. Phase 1 is read-only and ends with a
report. Do not edit anything until I approve the proposed changes.

READ FIRST, in this order
1. claude.md (project rules; the Five-Line Decision Rule and "How to read a number here").
2. docs/HANDOFF_2026-10-11.md (state blocks, newest first), numbers.md, and
   RAG_System_Observation_Log.md (Observations 21 to 52 are this work).
3. docs/NUMBERS_LEDGER.csv and evaluation/check_ledger.py (the number-to-source map).
4. Memory notes in C:\Users\JOHNSON 251205\.claude\projects\D--Major-Project\memory\:
   sealed-test-sets, corpus12-accept-as-is, multihop-rag-2026-10, numbers-ledger,
   api-keys-handling, no-em-dashes.

HARD RULES
- Phase 1 changes no file except a new report at docs/PAPER_REVIEW_<date>.md.
- Do not run any evaluation. Do not touch the sealed sets (Corpus 3 test, RAMDocs, MultiHop-RAG
  sample). Re-grading existing result files is allowed; new model calls are not.
- No API keys: do not open, read or use .env. Print key names only if you must mention them.
- Corpus 1 and 2 numbers are ACCEPTED_AS_IS: check that they match the stored result files, but
  do not re-test them or argue for re-testing.
- Corpus 3 / ContractNLI must not appear in the paper. Only the plain limitation line is allowed.
- Never invent a citation, a number or a result. If something cannot be traced, say
  UNTRACEABLE and stop there.
- No em dashes in anything you write. Plain language.
- No pushing, merging, deleting or committing in Phase 1.

PHASE 1: THE REVIEW (read-only). Do all seven parts.

A. Number trace. Run `python evaluation/check_ledger.py -v` and report the result. Then do an
   independent spot check that does not rely on the checker: pick at least 40 numbers spread
   over the abstract, introduction, every results table, the security section, the discussion,
   the limitations and the appendix. For each, open the ledger row, open the result file it
   names, recompute the value yourself, and compare it with the text. Include every number in
   the abstract and every number in every table. Report a table: paper location, number as
   written, ledger id, source file, recomputed value, MATCH or MISMATCH. Also look for numbers
   the checker would miss: numbers written as words ("twelve"), ranges, percentages derived by
   hand, and numbers in captions, footnotes and appendix tables.

B. Claim audit. List every claim the paper makes (sentence level) in these groups: structural
   (holds by construction), statistical (measured on a sample), comparative (X beats Y),
   causal (X because Y), and scope (what the paper says it does not show). For each, say which
   test supports it, or that nothing does. Flag any claim that says more than its evidence:
   "guarantee", "always", "never", "proves", "robust", "state of the art", "generalizes".
   Apply the project's own rule: never defend a change with a statistical number alone, and
   treat accuracy on the self-authored corpora as a training metric.

C. Consistency. Find places where the paper disagrees with itself or with the repo: the same
   quantity given two different values, a table that disagrees with the prose, a threshold
   in the text that differs from validation.py, a count that differs between sections, a
   figure that no longer matches its caption, Corpus 1 and Corpus 2 numbers that moved
   between the "frozen" (v6) system and the current system and are not labelled. Compare the
   thresholds and switches in the paper with the defaults in validation.py, retrieval and
   synthesis code. Report differences from the NLPIR paper (Trust_Before_Text_NLPIR.pdf) that
   are deliberate (unverifiable numbers left out, MultiHop-RAG measured anew) and any that
   are not.

D. Structure and argument. Is the claim stated once, clearly, and supported in order? Check
   the abstract against the conclusion, the contributions list against the evidence, and the
   related work against the gap it claims. Say what a skeptical reviewer would ask first, and
   whether the paper answers it. Identify the weakest section and the strongest.

E. Length and redundancy. Report the section list with approximate word counts. Find repeated
   passages, tables that say the same thing, and sections that could move to an appendix or
   be cut. Say how long the paper would be at a typical conference limit and what to cut to
   fit, ranked by how little is lost.

F. Citations. Run a check that every \cite key used in main.tex exists in references.bib, and
   list the keys that do not (honovich2022true is known to be missing; the MultiHop-RAG paper
   has no key). Flag claims that need a citation and have none. Do not write bib entries.

G. LaTeX sanity (no compiler here). Check for unbalanced braces and environments, duplicate or
   undefined \label and \ref, tables whose column count does not match the header, overfull
   tabularx risk, and stray TODO or placeholder text.

OUTPUT OF PHASE 1: write docs/PAPER_REVIEW_<date>.md with these sections: Summary verdict
(five lines), Number trace table (A), Claim audit (B), Inconsistencies (C), Argument and
structure (D), Length and cuts (E), Citations (F), LaTeX issues (G), and a ranked list of
Proposed changes. For each proposed change give: the location, the exact current text, the
proposed text, why, and which of these it is: ACCURACY (a number or claim is wrong), CLAIM
(overstated or unsupported), STRUCTURE, CUT, or STYLE. Mark ACCURACY and CLAIM items first.
Then stop and ask me which changes to apply.

PHASE 2: APPLY (only after I approve, and only the approved items)
- Back up main.tex to D:\Major Project_paper_backups\ first.
- Make the minimum edit for each approved item.
- After the edits run `python evaluation/check_ledger.py --sync-lines -v` and fix any number
  that lost its ledger row (add a row with the real source; do not loosen the checker).
- Run `python -m pytest tests -q`.
- Append one Observation to RAG_System_Observation_Log.md (issue, cause, fix, effect), and
  update numbers.md if any number changed.
- Show me the diff summary. Commit only if I say so, with a plain explanation of what changed
  and why, and ask before any push.

Add a short state block at the top of docs/HANDOFF_2026-10-11.md when you finish.
```
