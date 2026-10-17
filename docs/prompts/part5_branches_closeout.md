# Part 5: Branches and close-out

Paste the block below into a new chat. Run last, after Parts 2 to 4 (and the RAMDocs recalculation) are done. It plans and reports only; it does not push, merge, rebase or delete anything without your approval.

````text
GOAL: make the branches consistent with jonan, and close out with an NLPIR-vs-verified report. This task PLANS and REPORTS; it does not push, merge, rebase or delete anything without my approval.

PREREQUISITES: Parts 2 to 4 are done (and RAMDocs is recorded). If something is missing, say which part and stop.

SHARED RULES (apply to every task)
- Repo D:\Major Project, branch jonan. First read docs/HANDOFF_2026-10-11.md (top blocks are current), claude.md, numbers.md, the log, docs/NUMBERS_LEDGER.csv, and your memory notes sealed-test-sets, api-keys-handling and corpus12-accept-as-is.
- Never change pipeline code, thresholds or defaults. Do not run the sealed sets or any harness. This task needs no API key; never touch .env.
- Ask me before pushing, merging, rebasing, deleting a branch, or committing paper files. Commit locally with git commit -F and the trailer "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>".
- Plain language, no em dashes, lead with the result.

STEP 1: BRANCH REPORT
Run git fetch --all --prune. For each branch (jonan, local main, origin/main, origin/Testing, kaustubh, origin/kaustubh, origin/anish, and any other) report: last commit and date, commits ahead of and behind jonan, and which number-bearing files (README.md, docs/STATUS.md, numbers.md, paper_assets/, tracked evaluation/results files) differ from jonan and are stale. As of 2026-10-11: origin/main is 832736a (2026-08-17) with v6 numbers and a README quoting 92.3% and 82.1%; origin/Testing is b6e6326 (2026-09-28); kaustubh and anish are June to July.

STEP 2: MERGE PLAN (plan only)
Propose how to bring the others in line (for example jonan into main by pull request, then retire or archive the stale branches), with the exact commands, what each would change, and the risks (large diff, files only on one branch, history rewrite). Wait for my approval before running any of it.

STEP 3: NLPIR-VS-VERIFIED REPORT
List every number in the NLPIR PDF that disagrees with, or lacks support in, the ledger, with page or section. Check at least: its Corpus 3 numbers are the August values (replication: 26.1%, 0/351); its RAMDocs, haystack and MultiHop-RAG numbers (status per the ledger); "defended LLM resisted all 45" holds only under the original grader; its abstract says defended models answered "every probe" while the baselines ran on 12 probes per run. Do not edit the PDF; I will.

STEP 4: COMMITS
Group the uncommitted work into sensible commits (code and tests; docs and numbers; ledger; main.tex; results manifests), show me the plan, commit locally after my OK, and ask before pushing. Never commit .env, data_ramdocs/, data_merged/, qdrant folders or the .xlsx file.

FINISH: update docs/HANDOFF_2026-10-11.md to say the work is complete or what remains. Final report: the branch table, the proposed merge plan, the NLPIR disagreement list, and the commit plan, then wait for my instructions.
````
