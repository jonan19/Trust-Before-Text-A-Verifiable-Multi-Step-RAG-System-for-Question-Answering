# Part 4: Consistency across the repo

Paste the block below into a new chat. Run after Part 2 (the ledger) and after the RAMDocs recalculation is recorded in `numbers.md` section 4.

````text
GOAL: make every number-bearing file in the repo agree with the ledger. Do not edit main.tex or the NLPIR PDF in this task (Part 3 owns main.tex).

PREREQUISITES: Part 2 is done (docs/NUMBERS_LEDGER.csv, evaluation/check_ledger.py). The RAMDocs recalculation (other chat) should be recorded in numbers.md section 4; if it is not, fix everything else and leave the RAMDocs rows marked "pending" in the report.

SHARED RULES (apply to every task)
- Repo D:\Major Project, branch jonan. First read docs/HANDOFF_2026-10-11.md (top blocks are current), claude.md, numbers.md, the log (re-read the last Observation number before appending), docs/NUMBERS_LEDGER.csv, and your memory notes sealed-test-sets, api-keys-handling and corpus12-accept-as-is.
- Never change pipeline code, thresholds or defaults. Documentation, evaluation/ and tests/ only. Owner decision: Corpus 1 and 2 are accepted as they are (ACCEPTED_AS_IS), no re-testing. Do not run the sealed sets. This task needs no API key; never touch .env.
- Other chats may edit shared files: re-read a file right before editing it. Ask me before pushing or deleting. Commit locally with git commit -F and the trailer "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>".
- Plain language, no em dashes. Never delete an old value silently: move it to a labelled History section. Update numbers.md first, then the ledger, then the other files, then the log.

STEPS
1. Run evaluation/check_ledger.py and list every stale or contradictory number in README.md, docs/STATUS.md, docs/RAMDOCS_COMPARISON.md, docs/CORPUS3_RESULTS.md, docs/CORPUS3_ANALYSIS_AND_FIXES.md, docs/HOW_IT_WORKS.md, docs/REPRODUCE.md, docs/FUTURE_WORK.md and numbers.md. Known ones: docs/RAMDOCS_COMPARISON.md quotes 88.4% and 2.6% from the label-leaky run and cites "Han et al." (first author is Han Wang; cite Wang et al.); docs/STATUS.md does not mention RAMDocs; docs/FUTURE_WORK.md says "C1 92.3% / C2 80.8%"; numbers.md section 7 items still open.
2. Show me the list, then fix each file from the ledger, with old values moved to History sections. If the RAMDocs result is recorded, update docs/RAMDOCS_COMPARISON.md with it and note which run is current.
3. Re-run python -m pytest tests -q and evaluation/check_ledger.py; both must pass. Change a test that encodes a stale number only if the ledger confirms the new value.
4. Close the numbers.md section 7 items that are now settled and say which remain.

FINISH: add a short state block to docs/HANDOFF_2026-10-11.md. Final report: files changed, numbers corrected (old to new), anything still inconsistent. Do not push.
````
