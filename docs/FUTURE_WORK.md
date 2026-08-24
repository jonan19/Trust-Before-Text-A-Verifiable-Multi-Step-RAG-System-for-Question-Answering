# FUTURE_WORK.md — What it would take to make this system ideal

**Status: nothing in this document has been implemented.** It is a prioritized
backlog written after a full audit of the evaluation methodology, not a record
of work done. Numbers cited are measured from files already in this repo.

Current measured state: **C1 92.3% / 0 unsafe / 0 gap leaks · C2 80.8% /
1 unsafe (Q045) / 0 gap leaks.**

---

## 0. The framing decision that governs everything below

**The paper's headline claim is safety and verifiability. Accuracy is context.**

This is settled, and it reorders every priority in this document. The evidence
for the headline claim is structural and does not depend on corpus tuning:

| Result | Value | Depends on tuning? |
|---|---|---|
| Fabricated-evidence test | 0/4 | No |
| Adversarial probes | 0/48 | No |
| Invariance: `permute` | 0 violations, both corpora | No |
| Invariance: `duplicate` | 0 violations, both corpora | No |
| Invariance: `distractor` | 0 violations, both corpora | No |
| Invariance: `query_lower` | 0 violations, both corpora | No |
| Bare LLM baseline under attack | **12/12 unsafe** | No |
| Accuracy 92.3% / 80.8% | — | **Yes, heavily** |

Every row except the last is a *property*, provable by construction and
expected to transfer to any corpus. The last row is a fitted number on a
self-authored corpus. Lead with the properties.

---

## 1. The central methodological problem

Stated plainly, and already stated in this repo's own code
(`evaluation/invariance_harness.py`, module docstring):

> "Nothing in this project is currently held out. Corpus 2 has been used to
> accept or reject candidate rules dozens of times across those reports, so it
> is a training set, not a held-out one."

Three consequences:

**1.1 — Accuracy is measured at single-sample resolution.** n=78 overall means
one query = 1.3 points. The conflict class is n=16, so one query = 6.25 points.
Any change moving 1–2 queries is statistically indistinguishable from noise.

**1.2 — Corpus 2 is not an independent sample.** Both corpora have identical
category composition (18 single-fact / 10 multi-part / 10 cross-document /
10 conflict-probing / 10 out-of-scope / 8 aggregation / 12 scenario) and
identical decision distribution (46 answer / 16 insufficient / 16 conflict).
C2 is a re-skin of C1's design, not a second draw from the world. A reviewer
comparing the two composition tables will notice immediately, and it weakens
every "transfers across corpora" claim in the paper.

**1.3 — This is the direct cause of the whack-a-mole problem.** Fixing one
query breaking another is not an engineering failure; it is the arithmetic
signature of doing coordinate descent on a 78-sample surface with hand-set
constants. It will recur indefinitely as long as accuracy-on-78 is the
acceptance criterion.

---

## 2. HIGHEST PRIORITY — Adopt a tiered acceptance policy

The fix for whack-a-mole is not a smarter rule. It is changing what a change
is allowed to be accepted on.

| Tier | Metric | Policy |
|---|---|---|
| **1** | Structural safety: fabricated-evidence, adversarial probes, invariance under content-preserving transforms | **Must never regress.** A change touching this is rejected regardless of accuracy gain. |
| **2** | Accuracy on the 78 | **Report, do not optimize.** A change moving ≤2 queries is noise. Do not ship it, and say so in the paper. |
| **3** | Thresholds | Report the **sensitivity band**, never the tuned point. |

This policy has already been applied correctly by instinct — the anchor-loosening
fix for Q045 was rejected because it was a Tier-2 wash (recovers Q045, creates a
new false conflict elsewhere). Writing the policy down converts a good instinct
into a defensible method, and is itself a contribution worth a paragraph in the
paper. Tier 3 is already practiced well: the 0.94 conflict threshold sits in the
middle of a wide flat region (LIMITATIONS_STATUS IX-C), which is the property
that makes it defensible.

**Action:** write this table into the paper's methodology section and into
`claude.md` as a standing development rule.

---

## 3. HIGH PRIORITY — Expand invariance testing

This is the highest value-per-hour work available, for three reasons: it needs
no new ground truth, it does not saturate, and **every violation is a genuine
defect rather than a threshold near-miss.**

### 3.1 Existing transforms (5)
`permute`, `duplicate`, `distractor` (evidence-side, all 0 violations) and
`query_lower`, `query_thanks`, `query_polite` (query-side, violations below).

### 3.2 Transforms to add
- **Query paraphrase** — the single most valuable one. See §4.
- Synonym substitution in query
- Typo / character-noise injection
- Multi-part sub-question reordering
- Document filename changes
- Chunk truncation at non-semantic boundaries
- Near-duplicate document injection
- Unit and number-format changes (`25 days` / `twenty-five days`)
- Section-heading removal
- Whitespace and punctuation normalization
- Passive/active voice rewrite of the query
- Contraction expansion (`don't` → `do not`)

### 3.3 Why this matters more than authoring more queries
Authoring more queries against the same self-authored corpus reproduces the
same authorship bias — you will write the queries you already think about.
Metamorphic transforms are unbounded, unbiased by construction, and produce
defect counts rather than sample statistics.

---

## 4. HIGH PRIORITY — Convert the 3 over-abstentions into a measured rate

Currently Q013 (C1), Q059 (C2), Q074 (C2) are documented as three anecdotes:
the query paraphrases what the corpus says, the presence check misses it,
the system over-abstains.

A **query-paraphrase invariance transform** would restate this as:

> "Under semantically-neutral rephrasing, abstention rate rises from X% to Y%."

Same underlying weakness, vastly stronger as a result — a quantified,
generalizable limitation instead of a confession. This is the single best
return on effort in the entire backlog.

**Note the constraint discovered during this work:** paraphrase misses cannot
be separated from genuine gaps by any lexical, frequency, or semantic threshold.
A search over 2,304 term-selection configurations plus a semantic variant found
none. The reason is documented at `validation.py` ~line 1219: a genuine gap
(Q051) is semantically *close* to unrelated corpus content, while a paraphrase
miss (Q013) is semantically *far*, because the paraphrased words are weak
framing words. Passing Q013 needs a bar ≤0.0718; refusing Q051 needs >0.4024.
**Semantic similarity is anti-correlated with what the discrimination requires.**
This negative result is publishable as-is and should not be re-litigated.

---

## 5. MEDIUM-HIGH — The `_query_content_terms` structural finding

**This is the most important architectural insight from the audit.**

`_query_content_terms()` (`validation.py:1553`) — an unweighted set of surface
tokens minus a hand-maintained stopword list — feeds **three** independent gates:

| Consumer | Location | Symptom when it misfires |
|---|---|---|
| `_focus_terms` → anchor test | `validation.py:1092` | **Q045** — conflict pair never compared |
| Presence check | `validation.py:1223` | **Q013 / Q059 / Q074** — over-abstention |
| `detect_conflicts` scoping | `validation.py:1359` | **Q019 politeness regression** |

So Q045, the three paraphrase over-abstentions, and the politeness safety
regressions are **not three unrelated bugs. They are three symptom families of
one design decision**: a bag of surface tokens standing in for query semantics.

**Write the limitations section this way.** "One mechanism, three predictable
failure modes, each measured" is far more credible than three separate
confessions, and it tells a reviewer the system is understood rather than
patched.

**Future fix direction (not attempted):** replace the unweighted token set with
phrase-level or dependency-aware term extraction. This would address Q045
directly — Q045 fails because "Satisfactory Academic Progress...2.5" anchors on
`progress` while the 2.0-side text states the same rule informally and never says
`progress`, so no shared anchor exists and the pair is never compared. It is also
the only route to separating Q051's `allowance` (appearing only inside the
unrelated compound "mileage allowance payments") from a genuine paraphrase miss.
This is a substantial redesign, not a patch.

---

## 6. MEDIUM-HIGH — Two known invariance defects (diagnosed, unfixed)

Measured in `evaluation/results/invariance_corpus1.json` and `..._corpus2.json`.

### 6.1 `query_thanks` — CHEAP, PROVABLY FREE FIX AVAILABLE

**Cause (confirmed):** `"thanks"` and `"thank"` are absent from
`_COVERAGE_STOPWORDS`, while `"please"`, `"could"`, `"you"`, `"tell"`, `"me"`
are all present. Appending `"Thanks!"` therefore injects a junk *content* term:

```
base  : ['applies', 'overtime', 'pay', 'policy', 'remote']
thanks: ['applies', 'overtime', 'pay', 'policy', 'remote', 'thanks']
```

Two effects: (a) the coverage denominator grows by a term no policy document can
ever contain (5/5 → 5/6), flipping near-bar queries `answer → insufficient`;
(b) `_query_relevant_text` scoping changes inside `detect_conflicts`, which
flips Q019 `conflict → answer`.

**Violations removed by the fix:** C1 3 (Q010, Q019, Q051 — Q019 is a safety
regression); C2 2 (Q009, Q019).

**Why the fix is free:** no query in either corpus contains "thank" (verified,
0/156). Adding gratitude tokens to `_COVERAGE_STOPWORDS` is therefore a
**provable no-op on all baseline queries** while removing 5 invariance
violations including one safety regression. It is a completeness patch to an
existing list — the same category as the `"please"` entry already there — not a
new mechanism and not a tuned threshold. It passes the Tier-1 gate by
construction.

**Recommended tokens:** `thanks`, `thank`, `thankyou`, `cheers`, `regards`,
`appreciated`, `kindly`.

**Caution:** Q051's flip under this transform is currently *accidentally
correct* (it is a gap query and goes to `insufficient` for the wrong reason).
Fixing the stopword gap will return Q051 to its true baseline behaviour. This is
correct — do not read it as a regression.

### 6.2 `query_polite` — NOT a term leak; harder

**Cause (confirmed):** content terms are byte-identical before and after the
transform — `could`/`you`/`tell`/`me` are all already stopworded. The only
remaining channel is the **embedding**: `"Could you tell me: "` shifts the query
vector, retrieval returns different chunks, and the decision changes.

**Violations:** C1 2 (Q032 `conflict → answer`, Q070 `insufficient → answer`) —
**both safety regressions**. C2 1 (Q028, not a safety regression).

**Fix direction (not attempted):** query normalization before embedding — strip
leading courtesy frames. This is a new mechanism with real regression risk and
should not be attempted under time pressure. Document as a known limitation.

**Paper note:** these are safety regressions sitting in the repo's own results
files. If they are not in the write-up, a reviewer who runs the project's own
harness will find them. Disclose them.

---

## 7. MEDIUM-HIGH — The model-invariance experiment

**The single highest-value experiment not currently run, and it is cheap.**

The architecture claims the decision layer is deterministic and the LLM is
responsible only for synthesizing already-validated evidence. If that claim is
true, swapping the synthesis model changes *wording* but not a single
*decision*.

The harness for a second model already exists
(`evaluation/results/adversarial_baseline_gpt-oss-120b_*.json`).

**Target result:** *"The decision layer is model-invariant by construction;
verified across 2 synthesis models, 0/156 decision changes."*

This directly and completely answers "is the system model-dependent?" — a
question no amount of corpus tuning could fake an answer to. It is squarely a
Tier-1 structural result and belongs next to the 0/48 and 0/4 numbers.

---

## 8. HIGH (but expensive) — External validity

Per this repo's own `LIMITATIONS_STATUS.md`: self-authorship is *"the single
biggest threat to external validity in the whole project."* Correct, and it is
the objection a reviewer will raise first.

**Ranked options:**

1. **A genuinely external corpus.** Publicly available university handbooks,
   academic catalogs, or government HR policy PDFs — same genre, zero authorship
   bias. Even a reduced version (~25 queries, single frozen evaluation, reported
   separately as an external-validity probe) would substantially harden the
   paper.
2. **A frozen Corpus 3.** Only worth doing under strict discipline: single
   evaluation, never tuned on, and **do not reuse the 46/16/16 composition or
   the category counts** — that is what made C2 a re-skin.
3. **Cross-domain probe.** Run the existing pipeline on a corpus from a
   different genre (technical documentation, legal contracts) to test whether
   the structural guarantees hold outside policy-document prose.

---

## 9. Open limitations to carry forward as documented, not fixed

These are correctly-handled known issues. Listed so they are not rediscovered.

| Issue | Class | Status |
|---|---|---|
| **Q045** (C2) — GPA conflict missed | Anchor test finds no shared term between "Satisfactory Academic Progress…2.5" and the informal 2.0-side text | Root-caused. Candidate fix (loosen anchor) tested and **rejected**: recovers Q045, creates a new false conflict elsewhere. |
| **Q013 / Q059 / Q074** — over-abstention | Paraphrase misses | Root-caused. Proven unfixable by lexical/frequency/semantic thresholds (2,304 configs + semantic variant). |
| `MIN_AVG_SCORE_FOR_SUFFICIENCY` calibration | Corpus-dependent | C2 leaks: 6 at 0.55, 2 at 0.65, 1 at 0.68. Structural fixes reduced but did not remove the dependence. |
| Conflict threshold 0.94 | Calibrated but defensible | Sits mid-band in a wide flat region, not on a tuned peak. |
| **Q036** (C2) — "right decision, wrong evidence" | `find_conflict` reports the unrelated 21-vs-18 credit-hours pair for an academic-probation query, matching the gold *decision* but not `expected_conflict_pair` | Root-caused via the `ANSWERHOOD_MARGIN` experiment below. Not independently fixable: suppressing the wrong pair does not surface the right one — Stage 4 cannot discover it under current thresholds — so the query becomes `insufficient` instead. |
| Cross-encoder **answerhood margin** gate (`ANSWERHOOD_MARGIN`) | Tried and characterised, shipped disabled | Real precision/attribution gain (C2 false conflicts 9→2, attribution 0.583→0.875) but costs one true-conflict recall point via Q036 above — Tier-1 regression, rejected per the tiered policy. See `docs/STATUS.md` Problem 1. |

**Action item flagged during audit:** the rejected anchor-loosening fix for Q045
— *which* query it broke and *how* — should be written down explicitly. It is
currently only in session scrollback. That evidence is what makes Q045 "understood
and deliberately not fixed" rather than "neglected."

---

## 10. Suggested ordering if time reappears

1. §6.1 — the `thanks` stopword fix (free, removes a safety regression)
2. §7 — model-invariance experiment (cheap, strong Tier-1 result)
3. §2 — write the tiered acceptance policy into the paper
4. §5 — rewrite limitations around the `_query_content_terms` root cause
5. §4 + §3.2 — paraphrase transform, then the remaining transforms
6. §9 — record the rejected-fix evidence for Q045
7. §8 — external corpus

Items 1–4 are days of work and materially strengthen the submission.
Item 7 is the only one that fully answers the external-validity objection.

**Done since this was written:** the retrieval-style half of "query-conditioned
entailment" (§9, `ANSWERHOOD_MARGIN`) — tried, characterised, and rejected per
the tiered policy; see `docs/STATUS.md` Problem 1. It also produced the Q036
root-cause above and fixed a denominator bug in `harness.metrics()`'s
attribution grading (`evaluation/harness.py`). Still untried: answer-span
extraction, and the *entailment*-specific variant (declarative-hypothesis NLI
rather than a retrieval ranker) — see `docs/STATUS.md`'s updated "most
promising untried routes" note, which argues neither obviously escapes the
Q036 failure mode either.
