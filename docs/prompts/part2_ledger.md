# Part 2: The number ledger

Paste the block below into a new chat. Run after the RAMDocs recalculation has started (it does not need to be finished). See `README.md` in this folder for the order.

````text
GOAL: build the number ledger and its checker, so every number in the paper has a recorded source and a verification status. Do NOT edit main.tex in this task.

SHARED RULES (apply to every task)
- Repo D:\Major Project, branch jonan. First read docs/HANDOFF_2026-10-11.md (the DECISION UPDATE and STATE blocks at the top are current), claude.md, numbers.md, RAG_System_Observation_Log.md (re-read the last Observation number before appending; other chats may add entries), and your memory notes sealed-test-sets, api-keys-handling and corpus12-accept-as-is.
- Never change pipeline code, thresholds or defaults. New code only in evaluation/ and tests/. Show a plan before writing new code.
- Owner decision: Corpus 1 and 2 results are accepted as they are and are NOT re-tested (no sweep, no suite re-run, no per-switch runs). The Corpus 3 (ContractNLI) test stays sealed and out of the paper. This task needs no API key and no harness run; never touch .env.
- Other chats may be running RAMDocs or editing numbers.md, the log, main.tex and the handoff. Re-read a file immediately before editing it, and make small targeted edits.
- Ask me before pushing, deleting, or committing paper files. Commit locally with git commit -F and the trailer "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>".
- Plain language, no em dashes, lead with the result. Set PYTHONUTF8=1.

STATUS LABELS (use exactly these)
REPRODUCED = re-run in this work and matched | RECOMPUTED = recomputed from a saved raw result file | DERIVED = arithmetic from verified numbers | EXTERNAL = published by someone else (cite it) | ACCEPTED_AS_IS = a Corpus 1 or Corpus 2 number taken from a saved file or the NLPIR paper, not re-tested by owner decision | UNVERIFIABLE = no source here.
RULE: a number that is NOT about Corpus 1 or 2 (RAMDocs, MultiHop-RAG, any new dataset) must be REPRODUCED, RECOMPUTED, DERIVED or EXTERNAL, or it must not be in main.tex. ACCEPTED_AS_IS is allowed only for Corpus 1 and 2.

STEPS
1. Extract every numeric claim from main.tex (it already contains tables added by another chat: tab:ci_mcnemar, tab:errors_component, sec:retrieval_recall, tab:sensitivity, tab:component_ablation), and the headline numbers from the NLPIR PDF (PyMuPDF), README.md, docs/STATUS.md, docs/RAMDOCS_COMPARISON.md and numbers.md.
2. Build docs/NUMBERS_LEDGER.csv with columns: id, value as written, meaning, corpus scope (C1, C2, both, other), file and line where it appears, source (raw file plus JSON path, or the command), status label, tested after the Testing-branch merge (yes, no, n/a), date, commit, notes. Reuse what is already verified (numbers.md and Observations 30 to 43): the re-run files, experiments/*.json, retrieval_recall_corpus{1,2}.json, merged_corpora.json, label_audit.json, the 24 finished sweep runs (all matched NLPIR), fabricated/gap-probe/invariance files, rd_full_ramdocs.json (note: the LEAKY run), and the rdc_* files that exist.
3. Build evaluation/check_ledger.py and tests/test_ledger.py that: (a) recompute every RECOMPUTED row from its file; (b) confirm each ledger string appears where it should; (c) flag any number in main.tex that no ledger row covers; (d) flag any non-C1/C2 number whose status is ACCEPTED_AS_IS or UNVERIFIABLE; (e) flag STALE strings (88.4% as a current RAMDocs result, 82.1% or 92.3% as the current system, "Han et al.", "10 of 25") outside sections marked historical.
4. Mark as UNVERIFIABLE (do not guess): NLPIR's MultiHop-RAG numbers, the current-system haystack claim (the tracked file is the old v6 run), NLPIR's RAMDocs table and p-values until the clean runs reproduce them, and anything else with no source.
5. Report the status counts, the UNVERIFIABLE list, every main.tex number the checker could not map, and any non-C1/C2 number that would break the RULE.

FINISH: add a short state block to docs/HANDOFF_2026-10-11.md. Final report: counts per status, the UNVERIFIABLE list, and questions for me (especially: do raw files exist anywhere for MultiHop-RAG, the current haystack run and the RAMDocs baseline arm?). Do not push.
````
