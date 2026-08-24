# CLAUDE.md

# Trust Before Text

This is a research project implementing a deterministic Retrieval-Augmented
Generation (RAG) pipeline focused on minimizing hallucinations through evidence
validation before LLM synthesis.

**The claim this project makes is verifiability, not accuracy.** Injected text
cannot reach the prompt; fabricated evidence cannot be accepted; the routing
decision never calls an LLM. Those are structural properties. Accuracy numbers
are supporting context only — see "How to read a number here" below.

## Core Philosophy

- Retrieval maximizes recall.
- Validation determines whether evidence is trustworthy.
- The LLM is only responsible for synthesizing validated evidence.
- Prefer deterministic logic over LLM-based decision making.
- Explainability is more important than cleverness.
- Preserve architectural separation of responsibilities.

## Pipeline

User Query
→ Preprocessing
→ Query Classification
→ Query Decomposition
→ Hybrid Retrieval
→ Validation Pipeline
→ Decision Engine
→ LLM Synthesis
→ Final Response

## Development Principles

- Make one architectural change at a time.
- Keep changes as small and localized as possible.
- Do not refactor unrelated code.
- Preserve existing public APIs unless explicitly requested.
- Do not rename files, classes, or functions without justification.
- Avoid introducing unnecessary dependencies.
- Prefer improving existing components over rewriting them.

## Before Writing Code

Unless explicitly asked to implement immediately:

1. Analyze the existing implementation.
2. Explain which files need modification.
3. Explain the impact of the proposed change.
4. Identify possible regressions.
5. Present an implementation plan.
6. Wait for approval before writing code.

## When Implementing

- Modify only the files required.
- Keep diffs minimal.
- Preserve backward compatibility where possible.
- Add comments only when they improve understanding.
- Do not change formatting across unrelated files.

## After Implementation

Always provide:

- Summary of changes.
- Why the changes were made.
- Any assumptions.
- Possible edge cases.
- Any recommended follow-up work.

## Project Goal

Every architectural decision should improve one or more of:

- factual correctness
- evidence traceability
- validation reliability
- modularity
- maintainability

Do not optimize for code elegance if it weakens determinism or explainability.

---

# Research Governance

Everything below exists because of one fact: **there is no held-out data.** Both
corpora were authored by this project and have been used to accept or reject
changes dozens of times. Accuracy on them is a *training* metric. That single
fact explains every rule here — if it ever stops being true, revisit all of them.

## How to read a number here

Two kinds of claim, deserving very different trust:

- **Structural** — holds by construction, does not depend on a sample.
  Injection containment (0/45), fabricated evidence rejected (0/4), invariance
  under content-preserving transforms (0/78). These are *properties*.
- **Statistical** — accuracy over 78 self-authored queries, 16 per class, on a
  training set. One query is 1.3 points overall, 6.25 points in the conflict
  class. These indicate the system is not obviously broken. Nothing more.

Never defend a change with a statistical number alone, and never let a
statistical number veto one either.

## The Five-Line Decision Rule

This replaces the previous tier system. Apply in order; stop at the first match.

1. **Does it break a structural property?** (injection 0/45, fabricated evidence
   0/4, invariance 0/78, or introduce a new unsafe answer.)
   → **Reject.** No accuracy argument overrides this. Not negotiable.
2. **Does it fix a whole class with no compensating loss** — ideally shown by
   transferring to a corpus it was *not* derived from?
   → **Ship.**
3. **Does it trade error strictly toward safety** (an unsafe answer becomes an
   over-abstention; a wrong-evidence citation becomes an honest refusal)?
   → **Ship, and document the cost explicitly.**
4. **Does it trade error laterally** — one query fixed, another broken, same
   severity?
   → **Do not ship. Record it as a measurement.** The trade *is* the finding.
   Do not tune it, do not argue about it, do not build variant #2 of it.
5. **Can't tell which of the above it is?**
   → You need an external corpus. Say so and stop.

This rule reproduces every historical accept and reject in this project without
needing tiers or n=16 statistics. Check it against `docs/STATUS.md` if in doubt.

## The Overfitting Test

Before proposing any decision-layer change, answer this:

> **Was this change derived from looking at the specific query it fixes?**

- `REQUIRE_ASSERTIVE_SPANS` was derived from Corpus 2 boilerplate, then removed
  all three Corpus 1 false conflicts *which had never been examined*. That is
  transfer. **Legitimate.**
- The Q045 anchor rescue was built specifically to fix Q045. It fixed Q045 and
  broke Q002. **That is fitting, and it behaved exactly like fitting.**

Naming an individual query as the target of a change is, at this n with no
held-out set, definitionally overfitting. If a proposal's motivation is "this
would fix Q0xx", the proposal is already suspect — say so before presenting it.

## Standing Decisions (do not silently reopen)

These are settled. Reopening one requires the user to say so explicitly, and
requires new information, not a new idea for the same old problem.

1. **Problem 1 (false conflicts) is closed as an engineering task.** Nine
   candidates have been falsified — unit-noun demotion, digit-only dimensional
   veto, query/span embedding gate, NLI floor raise, shared-rare-term, superseded
   -document suppression, asymmetric anchoring, asymmetric anchor rescue, and the
   cross-encoder answerhood margin. **Every one has the same shape: it fixes one
   class and opens another, conserving total error.** That convergence is the
   result. It is not a losing streak, and it does not need a tenth sample.
   *Do not design experiment #10 in this family.* Independently replicated at
   Stage 5: an exhaustive search over 2,304 focus configurations found zero
   solutions, and the semantic rescue was proven anti-correlated.
2. **Problem 2's residual cost (Q013, Q059, Q074) is not a to-do.** Exhaustively
   shown irrecoverable at this design layer.
3. **The highest-value open item is an external corpus**, not any code change.
   See `docs/STATUS.md` Problem 3. Its three requirements: documents this project
   did not write; documents that genuinely self-contradict (real institutional
   policy sets do this naturally); and **questions plus gold labels authored by
   someone else, without seeing this system's output.** The third is the only
   hard one and is the entire value. Used **once**, at the end, never for
   selection. Inspecting a single failure case converts it into a training set.

## What Repeatedly Goes Wrong Here

Measured failure patterns, not hypotheses. Check a new decision-layer bug
against these before treating it as novel.

1. **Surface tokens standing in for meaning.** `_query_content_terms` is an
   unweighted bag of tokens minus a hand-maintained stopword list, and it feeds
   three independent gates (`_focus_terms`/anchor, the Stage-5 presence check,
   Stage-4 conflict scoping). Most "unrelated" decision bugs route through it.
   Symptom: the decision changes when the query is reworded without changing its
   meaning. Measured — "Up to how many days a week can **eligible employees**
   work from home?" gets focus `{eligible, home}` and cites the right pair,
   while "I would like to work from home. How many days a week can I do that?"
   gets focus `{home, week}`, anchors both spans on the bare unit noun
   **"week"**, and cites office attendance against maternity pay.
2. **A real conflict re-firing on questions it does not answer.** The corpus
   genuinely contradicts itself somewhere; that pair is strong evidence for many
   queries, so it surfaces under all of them. Largest remaining error class.
   It is a *topicality* failure, not an NLI-quality failure — a better NLI
   checkpoint scores those two sentences identically. See Standing Decision 1.
3. **Right decision, wrong evidence.** The system can abstain for "conflict"
   with a correct verdict while citing a pair unrelated to the question.
   Decision-level accuracy scores this as fully correct, so it is invisible
   unless attribution is graded (`harness.metrics()` now emits
   `attribution_precision` / `misattributed`). Measured — Corpus 2 **Q036**
   ("academic probation… Handbook versus Grading Policy") reports the unrelated
   21-vs-18 credit-hours conflict instead.
   **Corollary: `conflict_recall` overcounts.** It scores a wrong-evidence
   abstention as a success. Do not treat a `conflict_recall` drop as a
   regression without checking whether the lost query was correctly attributed
   in the first place — under Rule 3 above, wrong-evidence → honest refusal is
   a move toward safety, not away from it.
4. **Pair-filter rules that cost real conflicts.** Narrowing what may anchor a
   span, or requiring a shared rare term, reliably costs 2–5 true conflicts.
   Several variants falsified; see Standing Decision 1.

## Conflict-Detection Invariants

Any change to Stage 4 must preserve all of these:

- Both true conflict families keep working: **quantitative** (3 vs 6 months,
  3 vs 2 days/week, 6% vs 5%) and **semantic** (permitted vs prohibited).
- A rule that only inspects a *pair* cannot fix a *topicality* problem. If the
  two spans genuinely contradict, no pair-local rule should suppress them —
  the fix belongs where the query enters the comparison.
- Prefer a **predicate** (assertive / not assertive; commensurable / not) over a
  **threshold**. Predicates carry no corpus calibration and need no sensitivity
  band; every threshold in this system has needed re-measurement per corpus.
- Grade **attribution**, not just the decision: compare the reported pair
  against `expected_conflict_pair` in `queries.json`.

## The LLM Is Not the Variable

The safety decision is deterministic and LLM-free. That is the project's central
claim — it is what makes injection immunity hold *by construction* rather than
empirically. When diagnosing a wrong decision:

- Do not reach for a larger or better LLM, or a stronger NLI checkpoint. The
  decision layer never calls an LLM, and the NLI model's input contract does not
  include the query, so no checkpoint can fix a query-relevance failure.
- Do not let a learned model own the routing decision. A learned component may
  only **suppress** a conflict the deterministic layer already raised
  (precision), never **create** an abstention (safety) — so retrieved text can
  never talk the system into or out of a refusal.
- Retrieval is usually not the culprit either. Check the validation stages
  before suspecting the vector store.

## Open Item: ANSWERHOOD_MARGIN

Ships disabled (`RAG_ANSWERHOOD_MARGIN`, default `0.0`). At δ=5.5 on Corpus 2:
false conflicts 9 → 2, conflict precision 0.625 → 0.875, attribution 0.583 →
0.875, accuracy 82.1% → 89.7%; Q036 moves from `conflict` (wrong evidence) to
`insufficient`. No new unsafe answer (stays 1/32, still Q045).

Under the retired tier system this was rejected on the `conflict_recall`
15/16 → 14/16 drop. Under the Five-Line Rule that reasoning does not hold —
per failure pattern #3, Q036 was *already* wrong, and wrong-evidence → honest
refusal is Rule 3, a move toward safety. **The rejection was made on a metric
this project has itself documented as broken.**

It remains unshipped for one honest reason: **Rule 1 was never checked.** Run
`RAG_ANSWERHOOD_MARGIN=5.5 python evaluation/invariance_harness.py --corpus 2`
(and `--corpus 1`) before deciding. If invariance stays 0/78, Rule 3 says ship.
