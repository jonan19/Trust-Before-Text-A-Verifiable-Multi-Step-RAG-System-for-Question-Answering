# Part 3: Finish main.tex

Paste the block below into a new chat. Run after Part 2 (and ideally after the RAMDocs recalculation is recorded, and after Part 3b if you want MultiHop-RAG tested).

````text
GOAL: make main.tex correct, accurate and up to date with the NLPIR paper (Trust_Before_Text_NLPIR.pdf, the most recent). A large part is already done by another chat; this task reviews that work and finishes what is left. ContractNLI / Corpus 3 stays OUT of main.tex (my decision; the paper keeps a plain limitation line).

PREREQUISITE: Part 2 is done (docs/NUMBERS_LEDGER.csv, evaluation/check_ledger.py). If not, say so and stop. RAMDocs runs belong to another chat; do NOT run or resume them here.

SHARED RULES (apply to every task)
- Repo D:\Major Project, branch jonan. First read docs/HANDOFF_2026-10-11.md (its top blocks are current), claude.md, numbers.md, the log (re-read the last Observation number before appending), docs/NUMBERS_LEDGER.csv, and your memory notes sealed-test-sets, api-keys-handling and corpus12-accept-as-is.
- Never change pipeline code, thresholds or defaults. Owner decision: Corpus 1 and 2 results are accepted as they are (ACCEPTED_AS_IS), no re-testing. Numbers that are not about Corpus 1 or 2 must be REPRODUCED, RECOMPUTED, DERIVED or EXTERNAL, or stay out of main.tex. Never print keys or ask for them; any new LLM run needs my approval of a plan first.
- Another chat may edit main.tex, numbers.md, the log and the handoff at the same time. Re-read main.tex immediately before each edit and make small targeted edits. Back up main.tex first (backups live in D:\Major Project_paper_backups\).
- Ask me before pushing, deleting, or committing paper files. Commit locally with git commit -F and the trailer "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>".
- Plain language, no em dashes, lead with the result. Update numbers.md first, then the ledger, then the log, whenever a number changes. Set PYTHONUTF8=1.

STEP 1: REVIEW WHAT IS ALREADY IN
The other chat added to main.tex: the Wilson/McNemar table (tab:ci_mcnemar), errors by component (tab:errors_component), retrieval recall and merged index (sec:retrieval_recall), and Tables 4 and 5 in full as NLPIR prints them (tab:sensitivity, tab:component_ablation). Run evaluation/check_ledger.py, then check each new table cell against its ledger row and the NLPIR PDF. Report any mismatch, any missing caveat (the merged index must say Corpus 2's queries go from 1 to 2 unsafe, Q048; paragraph-level NLI was not reproduced), and any number without a ledger row.

STEP 2: WHAT IS LEFT FROM NLPIR (diff the PDF against main.tex section by section; show me the list and wait for my OK before editing)
 a. Haystack N-sweep (NLPIR: ours detects 20/20 at every N; the tracked file is the OLD v6 run, ours 0.75 falling to 0.5). It was run on Corpus 1 pairs; ask me whether to include NLPIR's claim as ACCEPTED_AS_IS or leave it out. Do not run it.
 b. MultiHop-RAG (NLPIR 4.8): not Corpus 1 or 2, so it must be tested or left out. If I have run Part 3b, use its results (ledger status REPRODUCED); otherwise leave it out and mark UNVERIFIABLE.
 c. RAMDocs section: wait until the other chat records the recalculated results in numbers.md section 4, then ask me whether main.tex uses NLPIR's numbers or the recalculated ones, and make the section, abstract, contributions and limitations agree with the ledger.
 d. Anything else NLPIR has that main.tex lacks (contributions wording, ablation prose, abstract).
After each edit: braces and environments balance, every \ref has a label, run evaluation/check_ledger.py. State that there is no LaTeX engine here. The repo's paper_assets/references.bib has 31 entries while main.tex cites 99 keys; the full bibliography must come from Overleaf, say so at the end.

FINISH: add a short state block to docs/HANDOFF_2026-10-11.md. Final report: what was reviewed and fixed, what was added, what was left out and why, remaining UNVERIFIABLE items, and questions for me. Do not push.
````
