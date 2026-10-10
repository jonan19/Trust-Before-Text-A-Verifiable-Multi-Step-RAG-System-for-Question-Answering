# Corpus 3 — Analysis and Proposed Fixes

Companion to `docs/CORPUS3_RESULTS.md`. Short and direct by design.

## The problem, in one sentence

The system finds real contradictions between documents correctly, but doesn't
check that a contradiction it cites is actually about the question being asked
— so once it flags one true contradictory pair in a bundle, it keeps citing
that same pair for unrelated questions.

## The evidence

- **Accuracy is below the do-nothing floor.** 26.7% vs. a 77.6% always-answer
  floor. `retrieval_threshold` (no validation, just retrieval confidence)
  scores the same 77.6% — so validation isn't adding discriminative signal
  here, it's actively subtracting it.
- **Citation is not just imprecise, it's structurally wrong.** External
  attribution precision — cited conflict pair checked against ContractNLI's
  own gold spans — is **0/350**. Not low. Zero.
- **The failure mode is concentrated, not diffuse.** Of a 40-case sample of
  misattributed conflicts, 34 are cases where gold expected *no* conflict for
  that specific question, yet the system cited a real, correctly-sourced
  contradictory pair anyway. Per bundle, one pair dominates: `test-b01` cites
  its top pair in 11 of 12 conflict reports it makes, regardless of which of
  the 17 questions was asked.
- **It is vocabulary-independent.** Confirmed two ways: (1) hypotheses whose
  content words the stopword filter strips (26.4% acc) look statistically the
  same as hypotheses it doesn't touch (27.8% acc) — no meaningful gap; (2)
  Track A (formal legal phrasing) and Track B (LLM-generated natural
  questions, disjoint vocabulary) show the same pair-concentration pattern.
  Two independent phrasings, same mechanism — rules out "it's just the words."

## Ruled out

**The stopword list (`validation._COVERAGE_STOPWORDS`) is a real, separate bug
— but it is not the cause of this collapse.** It strips load-bearing NDA terms
(`employees`, `staff`, `information`, `return`) because it was hand-derived
from Corpus 1, an employee handbook, where those words are noise. That's worth
recording as a corpus-specific-calibration-transfers-as-a-bug finding. But the
direct test — stripped vs. unstripped hypotheses — shows no measurable
accuracy difference, so it doesn't explain the 26.7% number. Per the project's
Overfitting Test, it should not be patched in response to Corpus 3 results
regardless — it's a Corpus-1 artifact, and editing it to fit Corpus 3 would be
fitting to the test set.

## Root cause

**A topical-binding gap in Stage 4's conflict citation.** The conflict
detector correctly identifies that two documents disagree somewhere in the
bundle, but nothing downstream checks that the specific spans it cites are
about the specific proposition the current query concerns before it reports
`conflict`. The contradiction-finding is scoped to the *document pair*; it
needs to be scoped to the *query*.

## Proposed fixes

Not yet implemented — held pending the qform and bare-LLM baseline results
(qform in particular tests whether phrasing is a second, independent factor
layered on top of this one, or fully explained by it).

1. **Gate conflict citation on query-relevant overlap.** Before reporting
   `conflict`, require that the two cited spans each contain content actually
   relevant to the current query's proposition — not just that the two
   documents disagree about *something* in the annotation set. This directly
   targets the 34/40 "real pair, wrong question" failure mode, which is the
   dominant one.
2. **Scope conflict evidence to the sub-span level, not the document-pair
   level.** The grader (`span_attribution.resolve_subspan`) already resolves
   conflict citations to query-relevant sub-spans rather than whole chunks —
   the detection logic should use the same granularity it's graded at, so a
   contradiction found on one hypothesis can't be silently reused as evidence
   for a different one.
3. **Stop caching contradictory pairs across queries within a bundle.** If the
   current implementation reuses or biases toward a previously-found
   contradictory pair when scanning subsequent queries against the same
   bundle, that directly produces the 92%-of-reports-one-pair concentration
   observed in `test-b01`. Each query's conflict check should be independent
   of what conflicts were found for earlier queries in the same bundle.

## Verification constraint (non-negotiable)

Any fix is verified on **Corpus 1 and Corpus 2 only**. The 30 sealed Corpus 3
test bundles are not re-run after a fix — re-opening them would make Corpus 3
a second training set rather than a held-out one. A true second exam on fresh
ContractNLI bundles is a separate, later exercise, not part of validating this
fix.

## Still open

- **qform** (in progress): confirms or rules out phrasing as an independent
  contributing factor, holding the 17 propositions and gold labels fixed.
- **Bare-LLM baseline** (in progress): establishes what the validation layer
  is actually worth against the same evidence with no deterministic gating at
  all — the comparison the safety claim rests on.
- Fix design stays deferred until both land, per standing instruction: results
  first, generalization fixes second, never tuning against the sealed set.
