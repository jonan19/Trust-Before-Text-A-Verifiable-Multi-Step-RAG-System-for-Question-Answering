# Prompts for the remaining work (written 2026-10-11)

Each file holds one self-contained prompt. Open a **new chat** for each, paste the block, and
let it finish before starting the next. Every prompt tells the chat to read
`docs/HANDOFF_2026-10-11.md` first, and to add a short state block to it at the end.

| Order | File | What it does | Needs from you |
|---|---|---|---|
| 0 | (other chat) | Resume RAMDocs run (a), then (b) to (d), with the same command as before (it skips finished queries) | API keys in `.env` |
| 1 | `part2_ledger.md` | Builds `docs/NUMBERS_LEDGER.csv` and a checker: every number gets a source and a status | Where any missing raw files are |
| 2 (optional) | `part3b_multihop.md` | New, preregistered MultiHop-RAG test | Download approval, plan approval, keys |
| 3 | `part3_main_tex.md` | Reviews and finishes `main.tex` against NLPIR | Choices on haystack, MultiHop-RAG, RAMDocs numbers |
| 4 | `part4_repo_consistency.md` | Fixes README, STATUS, RAMDOCS_COMPARISON, numbers.md from the ledger | Nothing |
| 5 | `part5_branches_closeout.md` | Branch report, merge plan, NLPIR-vs-verified report, commit plan | Approval before any push or merge |

Part 1 of the original plan (sweep and RAMDocs) is not here: the sweep was stopped on purpose
(Corpus 1 and 2 are accepted as they are, Observation 43), and RAMDocs is being finished in
another chat.

## Decisions every prompt assumes

- Corpus 1 and Corpus 2 results are accepted as they are and are not re-tested (status label
  ACCEPTED_AS_IS). Numbers about anything else (RAMDocs, MultiHop-RAG) must be tested after
  the Testing-branch merge, or stay out of `main.tex`.
- The Corpus 3 (ContractNLI) test stays sealed and out of the paper.
- API keys live only in `.env` (gitignored). Chats never print or ask for them. Rotation exists
  only in `evaluation/run_eval_ramdocs_clean.py` (`--rotate-keys`).
- No pushing, merging or deleting without explicit approval.
