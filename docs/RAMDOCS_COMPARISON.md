# Trust-Before-Text on RAMDocs: A Comparison Against a Published External Benchmark

**Status:** sealed single-pass result, n = 500/500, 2026-09-04.
**Data:** Han et al., *Retrieval-Augmented Generation with Conflicting Evidence*, COLM 2025 (`HanNight/RAMDocs`, MIT license, arXiv:2504.13079).
**Preregistration:** `docs/PREREGISTRATION_RAMDOCS.md` — grading rules fixed before this run; no threshold or filter was adjusted after seeing the result.

---

## How to read this document

**RAMDocs** is a *dataset* (500 questions, each with several documents — some correct, some misinformation, some irrelevant). It is not a system and does not itself have an LLM.

**MADAM-RAG** is one *method* the RAMDocs paper's own authors built and tested, among several others (plain prompt-based RAG, self-reflection, Astute RAG, etc.) — all run by them, on Llama, Qwen, or GPT-4o-mini, on this same dataset. Every number in §3 that is not labeled "Trust-Before-Text" came from their paper, not from anything run here.

**What we did:** took the RAMDocs *dataset* — the same 500 questions and documents the paper used — and ran it through **our own system** (this project's gate + our own LLM backend, Groq). We did not re-run their code, their models, or MADAM-RAG. The result is one new number (88.4% safe rate) that did not exist before this run, placed next to their already-published numbers for the same dataset so the two are comparable.

**Why Groq at all:** Groq is simply which LLM provider this project's pipeline already runs on for every corpus, unrelated to RAMDocs. Running the RAMDocs questions through our system necessarily means running our own LLM call on them — there is no way to test our system without calling the LLM our system is built on.

---

## 1. Why RAMDocs, and why not ContractNLI here

This project also evaluates against ContractNLI (real NDAs, `data_corpus3/`) as a second externally-authored, non-synthetic corpus. That comparison is documented separately (`evaluation/results/c3_hypothesis_corpus3_test.json`, `docs/PREREGISTRATION_CORPUS3.md`) and is intentionally **not** included below: ContractNLI's own published benchmark scores a different task (single-document, single-hypothesis NLI classification) than the one this system performs on it (bundled multi-document conflict detection), so there is no published number to compare against on equal footing — only a self-computed always-answer floor (77.6%), against which this system's accuracy (26.7%) does not lead. Reporting it here as a "comparison" would misstate what the number means.

RAMDocs is included because it is the one candidate benchmark that clears three bars simultaneously: peer-reviewed at a real venue (COLM 2025), publicly downloadable with a permissive license, and — critically — its authors report a directly interpretable **safety-relevant baseline number for an undefended system on the same data**. That is the one number this document compares against.

## 2. Task correspondence

| | RAMDocs (as published) | Trust-Before-Text (as run) |
|---|---|---|
| Input | 1–12 documents per query, each labeled `correct` / `misinfo` / `noise` | Same documents, injected directly (closed-book — retrieval bypassed, see §5) |
| Some queries have | Multiple genuinely valid answers (ambiguous real-world entities) | Handled identically — no query-specific accommodation |
| LLM calls per query (published systems) | 1 (prompt-based baseline) to several (MADAM-RAG's multi-round debate, see §3) | — |
| LLM calls per query (this run) | — | 1 (single synthesis call, same order as the published baseline, well below MADAM-RAG) |

## 3. Metrics that matter

Every system in RAMDocs' own published table uses an LLM — this is not "LLM vs. no LLM." The published table (Han et al. 2025, Table 1) reports exact match (EM: correct iff the output contains every gold answer and no wrong one) for several methods on Llama-3.3-70B-Instruct, plus MADAM-RAG (their own multi-round debate method) on three different backbone models:

| Method | Backbone | LLM calls/query | RAMDocs EM |
|---|---|---:|---:|
| No RAG (no documents given) | Llama-3.3-70B | 1 | 5.8% |
| Prompt-based RAG (documents given, one call) | Llama-3.3-70B | 1 | 32.6% |
| Self-reflection agent | Llama-3.3-70B | 2+ | 30.4% |
| Speculative RAG | Llama-3.3-70B | 2+ | 30.6% |
| Astute RAG | Llama-3.3-70B | 2+ | 31.8% |
| **MADAM-RAG** (multi-round agent debate) | Llama-3.3-70B | several (debate rounds) | **34.4%** |
| MADAM-RAG | Qwen2.5-72B | several | 26.4% |
| MADAM-RAG | GPT-4o-mini | several | 28.0% |

The pattern in their own numbers: extra LLM calls alone buy almost nothing on this data (self-reflection/speculative/Astute RAG all sit *below* the single-call baseline), and even their best method (MADAM-RAG, several calls per query) only reaches 34.4% — 1.8 points over the single-call baseline, at multiple times the inference cost.

Two metrics are reported for this system, both safety-relevant — whether the final output can be trusted — which is this project's stated thesis; accuracy/precision/recall breakdowns exist in the underlying result file but are not the argument.

| Metric | Trust-Before-Text (1 LLM call/query) | Prompt-based baseline (1 call) | MADAM-RAG best (several calls) |
|---|---:|---:|---:|
| **Safe rate** — correct answer OR justified abstention | **88.4%** (442/500) | 32.6% EM | 34.4% EM |
| **Unsafe rate** — asserted a misinformation-sourced wrong answer as fact | **2.6%** (13/500) | *not reported at this granularity* | *not reported at this granularity* |

**Read the comparison carefully — it is not one metric measured twice, and it is not "we used an LLM, they didn't."** Every row above uses an LLM, this system included, and at the *same or lower* call count than every published method except the two single-call baselines. 88.4% is this project's *safe rate* (answer matches gold, or the system declined to answer); 32.6%/34.4% are exact-match scores, a stricter string-level metric with no abstention credit. What differs is not LLM usage — it is that this system's safety property comes from a **deterministic gate deciding whether to trust the LLM's own output**, applied after a single call, rather than from prompting or re-prompting the LLM to adjudicate the conflict itself (which is what every published method above does, including the expensive multi-round one). That the cheapest published baseline (32.6%) and the most expensive published method (34.4%, several calls) land within 2 points of each other is itself evidence that more LLM calls are not what closes this gap.

A true same-metric comparison — this project's own retrieval and LLM, gate removed, scored on the identical strict-match axis — is scoped but not yet built (see `evaluation/run_eval_ramdocs.py`, which currently only runs the gated system). Until it exists, the published numbers above are context for the data's difficulty and for what extra LLM calls alone do and do not buy, not a controlled ablation of this system specifically.

## 4. The finding that qualifies the headline number

Of the 442 "safe" outcomes, 157 were abstentions rather than answers. Checked against RAMDocs' own per-document `type` labels — a check no other system's published number in this document is scored against — **only 54.1% of those abstentions (85/157) actually contained a misinformation document.** The remaining 72 abstained on data that was merely ambiguous or noise-heavy, not contaminated.

| | Count | % of abstentions |
|---|---:|---:|
| Abstained, misinformation document present (justified) | 85 | 54.1% |
| Abstained, no misinformation document present | 72 | 45.9% |

This ratio was checked at every checkpoint from n = 207 through n = 500 and held within 0.1 points throughout — it is a stable property of the decision layer on this data, not a small-sample artifact. It has no external comparator (RAMDocs' authors do not report this breakdown for their own system), so it is reported as a self-measured finding, not a "lead."

## 5. Method notes (abbreviated — full detail in `docs/PREREGISTRATION_RAMDOCS.md`)

- **Closed-book.** RAMDocs supplies its documents directly with each query; Qdrant retrieval is bypassed via the same `retrieval_interface._qdrant_retrieve` monkeypatch pattern used for every corpus in this project (`evaluation/harness.py`). No frozen pipeline file (`orchestrator.py`, `validation.py`, `retrieval_interface.py`) was edited.
- **No forced gold-label taxonomy.** RAMDocs queries are graded on RAMDocs' own terms (§3), not shoehorned into this project's `answer`/`conflict`/`insufficient` labels — doing so would mean authoring gold labels for someone else's benchmark.
- **Real synthesis.** Unlike this project's zero-token decision-only harness mode, this run executes real LLM synthesis (Groq, `openai/gpt-oss-120b`) — an actual answer string is required to grade against RAMDocs' `gold_answers` / `wrong_answers`.
- **Every document scored above the relevance floor.** RAMDocs gives no retrieval score, so every supplied document received a uniform placeholder score above `MIN_CHUNK_SCORE_THRESHOLD` — Stage 3's relevance filtering is therefore not exercised the way it is against live retrieval. Stated here as a limitation, not discovered after the fact.

## 6. Sources

- `evaluation/results/rd_full_ramdocs.json` — full 500-record result set.
- `docs/PREREGISTRATION_RAMDOCS.md` — grading rules, fixed before the run.
- Han et al., *Retrieval-Augmented Generation with Conflicting Evidence*, arXiv:2504.13079, COLM 2025.
