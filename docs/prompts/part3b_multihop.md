# Part 3b: MultiHop-RAG (optional)

Paste the block below into a new chat. Optional: only if you want NLPIR's MultiHop-RAG claim tested and included in main.tex. Run before Part 3 finishes. Expect about half a day end to end, of which 2 to 3 hours is unattended compute (about 1.5 to 2 hours if it matches NLPIR's 609-article, 121-query design). It is a NEW measurement, not a reproduction of NLPIR's sample.

````text
GOAL: test the MultiHop-RAG claim in the NLPIR paper (Section 4.8: the gate answers 21 of 57 null queries against the prompted baseline's 1) with a NEW, preregistered measurement. Do not edit main.tex in this task, and do not run Corpus 1 or 2.

SHARED RULES: repo D:\Major Project, branch jonan. First read docs/HANDOFF_2026-10-11.md (top blocks are current), claude.md, numbers.md, the log (re-read the last Observation number before appending), and your memory notes sealed-test-sets, api-keys-handling and corpus12-accept-as-is. Never change pipeline code, thresholds or defaults; new code only in evaluation/ and tests/. Never print keys or ask for them. Rotation exists only in run_eval_ramdocs_clean.py via key_pool.py; you may reuse key_pool.py in a NEW script after I approve your plan. Other chats may edit shared files: re-read before editing. Ask before pushing, downloading, deleting. Commit locally with git commit -F and the trailer "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>". Plain language, no em dashes. Set PYTHONUTF8=1; long jobs run detached with Monitor; foreground sleep is blocked.

STEP 1: FACTS (no download yet). Find the dataset's official source (Tang and Yang, HKUST, arXiv 2401.15391; GitHub yixuantt/MultiHop-RAG and its Hugging Face card), its license, file names and sizes, the number of articles and queries, and the query types. Reconcile NLPIR's "609 articles, 22,061 chunks" with the full corpus size (a third-party page says 3,197 articles); read NLPIR 4.8 and its appendix for the sample design. Report all of it and ask me to approve the download. Prefer to match NLPIR's design (609-article subset, about 121 queries) to keep compute near 1.5 to 2 hours.

STEP 2: PREREGISTRATION. Write docs/PREREGISTRATION_MULTIHOP.md BEFORE any run: which articles are indexed and why, the seeded stratified sample (NLPIR used 150 null and 50 each of inference, comparison, temporal), grading (null means INSUFFICIENT is right; otherwise an answer is right), retrieval not bypassed, the prompted baseline (the E1 prompt from experiments/baseline_experiment.py, same retrieved passages), predictions in advance, and a note that this is a new measurement, not a reproduction of NLPIR's sample.

STEP 3: PLAN AND CODE. Show me a plan, then write evaluation/run_eval_multihop.py (loader, indexer into a NEW gitignored store folder, sampler, both arms, resumable checkpoints, run_info stamp) and tests that need no network. Do not touch existing Qdrant stores.

STEP 4: RUN after I approve the plan and the call count: index, a small pilot, then full runs, detached and resumable. Report our gate vs baseline on null queries (answered counts with Wilson intervals), the refusal rate on answerable queries, and retrieval figures, and compare with NLPIR's direction (not its exact numbers).

STEP 5: RECORD in numbers.md and a new Observation, and add rows to docs/NUMBERS_LEDGER.csv if it exists (status REPRODUCED for what you ran). Add a state block to the handoff. Final report: short table, caveats, open questions. Do not push.
````
