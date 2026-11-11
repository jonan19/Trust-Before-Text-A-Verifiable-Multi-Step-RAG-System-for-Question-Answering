# Automation and Session Plan (draft, 2026-11-08)

Written in a side session forked from the main chat. Nothing here is approved or
implemented yet. No code, config or mod has been written.

Read with `docs/STATUS.md` and `numbers.md`. Where this file and `numbers.md`
disagree, `numbers.md` wins.

---

## 1. Why this document exists

The planning below happened entirely inside a chat, which means it existed
nowhere durable and no other session could see it. That is the same failure mode
section 4 is designed to prevent, so the plan itself is now a file.

## 2. Diagnosis: three goals were being spoken of as one

The owner's stated aim was "good metrics, never unsafe, 100% secure". Those are
three separate things with three different answers.

### 2a. "Good metrics"

On the two self-authored corpora the system scores 96.2% and 89.7%. On every
corpus this project did not author, a prompted LLM baseline is safer or more
correct:

| Measurement | Ours | Prompted baseline |
|---|---|---|
| ContractNLI Track A (sealed) | 26.7%, floor is 77.6% always-answer | not run (needs a key) |
| ContractNLI Track B | 40.4%, unsafe 65/123 | not run |
| RAMDocs safe rate | 85.2% | 94.8% |
| MultiHop-RAG null-query leaks | 56/150 | 2/150 |
| MultiHop-RAG strict correctness | 41.7% | 62.7% |

Source: `numbers.md` sections 3, 4 and 4b. This is not a tuning deficit, it is
the measured result, and it is consistent with `CLAUDE.md`: the claim is
verifiability, not accuracy. The C1/C2 numbers are a training metric by
construction.

Consequence: do not pursue accuracy work on Corpus 1 or Corpus 2. Standing
Decision 1 and the owner decision of 2026-10-11 both close it.

### 2b. "Never unsafe" is an operating point, not a bug

56 of 150 MultiHop null queries are answered when they should be refused. Closing
them requires abstaining more, which also costs correct answers. Eight candidate
fixes have been falsified and all eight conserved total error, so there is strong
evidence no cost-free fix exists.

What is available, and is a legitimate contribution: measure the trade instead of
arguing about it. See work item B.

### 2c. "100% secure" needs scoping, not more work

Already true and structural: injected text reaching the prompt 0/45, routing
changed by injection 0/45, fabricated evidence accepted 0/4.

Not achievable at this layer: pre-ingestion poisoning, 24/24 against ours and
24/24 against the defended baseline. That is a data-poisoning bound, not a defect,
and the only layer that moves it is trusted ingestion with provenance signing.

Action: a wording pass on `main.tex`. "100% secure" cannot be claimed; the
containment properties can, and the bound should be stated as a located limit.

## 3. Work items

### A. Observability (nothing exists today)

Confirmed absent: the only instrumentation in the repo is two `logging.getLogger`
calls, in `synthesis.py:53` and `validation.py:78`. No tracing, no metric export,
no run registry, nothing in `requirements.txt`.

Evidence of the cost: roughly thirty single-use diagnostic scripts in
`evaluation/` (`dump_stage3.py`, `focus.py`, `coverage_leak_diag.py`,
`overabstention_diag.py` and so on), each written to answer one question once.
Also about ninety entries in `.claude/settings.local.json`, most of them paths to
throwaway scratchpad scripts.

What to build:

1. `tracing.py`, a no-op by default, enabled by `RAG_TRACE=1`.
2. Spans at every stage, carrying the decision-relevant intermediates:
   focus terms, focus-presence value, NLI pair scores, answerhood margin values,
   and which gate fired. These are precisely the quantities behind recorded
   failure patterns 1 and 3 in `CLAUDE.md`.
3. Two sinks: a JSONL trace file per run (reproducible artifact, partly addresses
   open item 9), and OpenTelemetry spans for a viewer.
4. Viewer: a mod pane beside the chat (see section 5) for single-query debugging.
   Arize Phoenix, local only, optional and only if bulk exploration of hundreds of
   runs is wanted. Langfuse self-hosted was rejected: it needs Postgres,
   ClickHouse, Redis and MinIO under Docker, too heavy for this machine.
5. Metrics: report context precision and context recall against the gold pairs in
   `queries.json`, computed deterministically. `harness.metrics()` already emits
   `attribution_precision`.

Files: new `tracing.py`; span calls in `orchestrator.py`, `validation.py`,
`synthesis.py`, `retrieval_interface.py`, `api.py`; sink wiring in
`evaluation/harness.py` and `evaluation/run_eval.py`; `requirements.txt`.

**Acceptance test, non-negotiable:** a trace-on run and a trace-off run must give
identical decisions on 78/78 for both corpora. Tracing watches; it never votes.
If the test fails the instrumentation is wrong, not the system.

**Correction, 2026-11-08.** An earlier revision of this plan called for a new
determinism check script. That was written without reading the repo first, and it
is wrong: `evaluation/rerun_suite.py` already exists and already is resumable,
chat-independent, zero-token, and explicitly refuses to touch the sealed Corpus 3
split, and `evaluation/expected_baseline.json` already holds the expected values
for the eval, invariance, gap-probe, fabricated-evidence, containment and
label-audit steps. The acceptance test above is therefore a **mode on that
script**, not a new file: run the decision suite twice, once with `RAG_TRACE=1`,
and assert identical per-query decisions on both corpora. Per `CLAUDE.md`, prefer
improving the existing component.

RAGAS caveat: most RAGAS metrics are LLM-judged, therefore non-deterministic.
They may be reported, clearly labelled and pinned, and must never touch selection
or the routing path. That would contradict the project's central claim.

### B. Safety-utility curve (the answer to "never unsafe")

One global conservatism scalar that scales the existing gates together
(`RAG_MIN_FOCUS_PRESENCE`, `RAG_ANSWERHOOD_MARGIN`, coverage floor, average-score
floor). New file `evaluation/safety_curve.py`. Plot unsafe rate against answer
rate.

### Where the curve may and may not be run (settled 2026-11-08)

**A sweep is selection by definition.** It evaluates N configurations and keeps
one. That is the exact activity Standing Decision 3 forbids on an external
held-out set: used once, at the end, never for selection.

| Corpus | Sweep? | Why |
|---|---|---|
| Corpus 3 **test** (30 bundles, 510 q) | **No. Never.** | Sealed. Opened twice, both times on a frozen config with nothing chosen from it, so its integrity is intact and has no slack left. A sweep ends that permanently and it is the only asset here that cannot be rebuilt. |
| Corpus 3 **dev** (15 bundles, 255 q: 192 answer / 39 conflict / 24 insufficient, floor 75.3%) | **Yes.** | `docs/PREREGISTRATION_CORPUS3.md` designates dev as the debugging split and already registered its predictions there. This is the documented intended use. |
| **RAMDocs** | **No.** | `docs/PREREGISTRATION_RAMDOCS_RERUN.md:12`: the owner lifted the seal on 2026-10-11 "for this recalculation only; the system is not changed or tuned." The seal is back on and tuning is named as excluded. |
| **MultiHop-RAG** | **No.** | `docs/PREREGISTRATION_MULTIHOP.md:158`: "After the run, the sample is sealed like RAMDocs: not used to choose or tune anything." |
| Corpus 1, Corpus 2 | **Owner's call, open.** | See the two notes below. |

**Correction, 2026-11-09.** An earlier revision of this table said "RAMDocs,
MultiHop-RAG | Yes | Not held out for this purpose." That was wrong; both
preregistrations seal them in writing, at the lines cited above. Caught by the
main session, verified here against both files. A dial sweep is tuning, and the
argument three paragraphs up (a sweep is selection by definition) applies to these
two exactly as it does to Corpus 3 test. Nothing was spoiled:
`evaluation/safety_curve.py` already refuses `3-test`, `ramdocs` and `multihop` by
name with the reason printed, written independently before the correction arrived.

**Consequence, stated plainly.** With all three external sets sealed against
tuning, **Corpus 3 dev is the only external data the curve may sweep**: 255
queries, with the unsafe denominator at n = 63. That is a materially weaker
measurement than the three-dataset curve this item originally promised, and the
paper must describe it as what it is, a single-dataset sensitivity measurement
with a wide interval, not a cross-corpus result.

This also raises the value of Observation 60's finding below, since a
non-transferring zero-unsafe point is evidence about calibration transfer that
does not need the sealed sets to make its case.

**Confirmation run.** If and only if the dev curve selects an operating point, that
**single** point may be run **once** on each sealed set (Corpus 3 test, RAMDocs,
MultiHop-RAG) as confirmation, with a preregistration written beforehand per the
project's own protocol (predictions stated in advance, disclosure clause). One
point, one run per set, no re-selection afterwards whatever the result. This is
the only legitimate route to having the chosen point validated on MultiHop, which
is the most informative set for this curve (56/150 gap leaks) and therefore the
worst one to spend on a sweep.

**Statistical caveat.** On the dev split, unsafe answers are counted over the
39 conflict plus 24 insufficient queries, so n = 63. The zero-unsafe point will
carry a wide interval. Report bootstrap or Wilson intervals
(`evaluation/bootstrap_ci.py`, `evaluation/harness_bootstrap.py`), and do not
read a one-or-two-query difference between adjacent dial settings as real.

### Correction: the curve is external-only (2026-11-08)

An earlier revision of this item proposed sweeping Corpus 1 and Corpus 2 as part
of the curve. That was wrong on two counts, both found by reading the repo:

1. **It reopens a closed decision.** The owner decision of 2026-10-11
   (Observation 43) discontinued exactly this: `evaluation/sweep_tables.py` was
   stopped at 24 of 57 runs and Corpus 1/2 results were marked ACCEPTED_AS_IS and
   not to be re-tested.
2. **Most of it already exists.** `evaluation/sweep_tables.py` already sweeps the
   same four axes one at a time on both corpora, with expected values recorded,
   and all 24 finished runs match NLPIR exactly.

So: cite `sweep_tables.py` for single-axis sensitivity on Corpus 1 and 2, and run
the joint-dial curve on external data only. This is also the stronger result. A
safety-utility curve measured on three externally authored datasets says more than
one more sweep of the corpora the system was tuned on.

This is a measurement, not a new filter, so it does not reopen Standing
Decision 1, and it names no individual query, so it passes the Overfitting Test.

Three possible outcomes, all publishable: a usable zero-unsafe point becomes the
shipped safe-mode default; zero-unsafe only at always-abstain becomes a stated
limitation with a number; or the point differs per corpus, which is a
calibration-transfer finding and the most interesting of the three.

**Known weakness to state in the paper:** the four gates are not commensurable.
`RAG_MIN_FOCUS_PRESENCE` is a presence fraction; `RAG_ANSWERHOOD_MARGIN` is a
cross-encoder score gap. One dial scaling both is a convenience, not a principled
parameterisation. If the curve comes out non-monotonic, suspect the dial before
concluding anything about the system.

### C. Close the three items blocking submission

`main.tex` is still editable, per the owner. From `numbers.md` section 7:

- item 19: pre-ingestion poisoning has no result file. The script exists at
  `evaluation/preingestion_poisoning.py` (2026-10-27) and has never been run
  cleanly.
- item 4: the Corpus 3 bare-LLM baseline was never run to completion. Needs an API
  key. Per the owner's standing rule, keys are not to be used or read unless the
  owner states they have added one.
- item 9: the 2026-08-31 Corpus 3 raw files are lost. Owner must accept those rows
  as prose-only, with the replicated files standing in.

### D. Security wording pass on `main.tex`

See 2c.

### E. Diagnose the MultiHop null-query leaks

56 of 150 is the largest unsafe class and it is **not** the false-conflict problem
that Standing Decision 1 closes. It has never had a diagnostic pass. Must come
after item A, because tracing is how one sees why a null query clears sufficiency.

## 4. Coordination: how multiple sessions stay on the same page

Sessions do not share context. A new session starts cold. So chat-to-chat
messaging is the weak form of coordination; the strong form is a file every
session reads before working and writes after.

That protocol already exists in this repo:

| File | Holds |
|---|---|
| `docs/STATUS.md` | where the research stands |
| `numbers.md` | every number, single source of truth, with its source |
| `RAG_System_Observation_Log.md` | what was done, why, and what it cost |

Gap: those record findings, not assignments. Proposed addition, owned by the
coordinating session: `docs/WORK_QUEUE.md`, listing each item, its owner, what it
is blocked on, and what done looks like.

The protocol currently depends on whoever is in the chat remembering it. Section 5
makes it mechanical. That is why the Guardrail mod is first.

### Three sizes of help, and when each applies

- **Background command** - runs a sweep, writes a result file, no judgment needed.
  Cheapest. Most of item B is this.
- **Subagent** - reads many files, reports a pattern, produces no deliverable of
  its own, disappears. Read-only tools where it is diagnosing.
- **Session** - owns a deliverable that lands separately and may need steering.
  Expensive, because it starts cold.

Eight parallel sessions to run eight sweep points would be eight full instances
doing what one loop can do. Sessions are for work that needs a brain and produces
its own deliverable.

### Assignment

| Work | Who | When |
|---|---|---|
| Guardrail mod | with the owner, in the main chat | first |
| 78-query determinism check script | same | first |
| Trace sink and instrumentation (item A) | one session, sole owner of the pipeline core | after the check script |
| Safety curve sweeps (item B) | background commands | after the sweep script exists |
| Security wording, `main.tex` (item D) | own session | parallel, anytime |
| Pre-ingestion poisoning run (item C) | background command | parallel, anytime |
| Trace pane mod | own session | after the trace sink |
| MultiHop leak diagnosis (item E) | read-only subagents, fanned out | after traces exist |

Only one item is on the critical path. The rest genuinely parallelises.

### Rules

1. **One writer on the pipeline core, ever.** `validation.py`, `orchestrator.py`,
   `synthesis.py`, `retrieval_scoring.py` have exactly one owner at a time.
   Sessions share the working folder and nothing prevents a silent overwrite.
2. Anything touching code gets its own worktree, so it lands on its own branch and
   `jonan` stays clean until the owner asks for a merge.
3. No session or agent changes a threshold. Ever.
4. No session writes to `numbers.md` without the owner reading the diff.
5. No session opens the sealed test set, for any reason.
6. No session or agent decides to ship or reject a change. It reports; the owner
   rules.
7. The coordinator verifies the diff or the result file. A session's report is a
   claim, not evidence.

## 5. Mods (changes to Claude Code itself)

A mod is a TypeScript hooks module that can refuse a tool call, draw a pane beside
the chat, write the status line, show a band above the prompt, register slash
commands and subagent types, and run things on a timer.

The important property: a tool-call refusal is the only mechanism here that acts
on the agent rather than through it. Skills, slash commands and `CLAUDE.md` rules
all depend on the agent reading and complying. A refusal does not.

### Mod 1: Guardrail

**Scope reduced, 2026-11-08.** Only item 1 below, the sealed-data lock, is in
scope. The status line and the log band are deferred. Reason: the main session
objected that building a mod first puts the least load-bearing item ahead of the
work that answers the owner's actual question, and it was right.

**When the lock is needed.** Its trigger is not a position in the build order, it
is a condition: **it must exist before the first session runs unwatched.** While
the trace work happens in one session with the owner watching, the lock adds
nothing. The moment work fans out to background sweeps and parallel sessions, it
is the difference between a promise in a document and a closed door. So it lands
after the trace sink and before the parallel phase.

1. **Sealed-data lock.** A `tool.call` hook that refuses any Edit or Write to the
   sealed Corpus 3 test files, and to the threshold constants in `validation.py`,
   unless the owner sets an override. Today "sealed" is a promise in a document;
   this makes it a locked door. The sealed data is the only asset in the project
   that cannot be rebuilt once spoiled.
2. **Live config in the status line.** Every threshold is env-overridable and
   `numbers.md` keeps a table of switches. A permanent readout
   (`margin=5.5 focus=0.5 assertive=on dimensional=on`) removes the whole class of
   error where a number is reported under a misremembered switch state.
3. **Log enforcement, visible.** A band that turns red when a tracked file has
   changed and `RAG_System_Observation_Log.md` has not been appended to.

### Mod 2: Trace pane

Reads the JSONL trace from item A and draws the stage-by-stage funnel beside the
chat. Better than a separate web UI for single-query debugging; worse for sorting
hundreds of runs. Build the trace sink first, since both read the same file.

### Mod 3: Ledger light

Runs the existing `evaluation/check_ledger.py` after any edit to `main.tex` or
`numbers.md` and shows the result in the band.

### Notes

- Mods are TypeScript in a Python project. They live outside the repo, in the
  owner's Claude config folder, but are still a second language to maintain. Keep
  them small.
- Enabling requires the owner to answer a one-time prompt in the app. No
  permission setting can answer it for them.
- Risk to manage: mods are the most entertaining item here and the least
  load-bearing. Build one, then return to the measurements.

## 6. Build order

Revised 2026-11-08 after the main session's objection. The earlier order put the
Guardrail mod first; that was wrong for the reasons in section 5.

1. **Trace-compare mode on `evaluation/rerun_suite.py`.** Small, plain Python, in
   an existing file. This is the acceptance test for step 2, so it comes first.
2. **JSONL trace sink and instrumentation (item A).** The real work, and the thing
   that answers the owner's original question.
3. **Sealed-data lock** (Mod 1, item 1 only). Must land before step 4.
4. Safety curve sweeps in the background (item B), and the parallel phase begins.
5. MultiHop leak diagnosis (item E), read-only subagents.
6. Trace pane mod.
7. Skills, the Five-Line-Rule review command, the rest of the Guardrail
   (status line, log band), ledger light.

Items C and D can run in parallel at any point, as they touch no pipeline code.

The temptation is to start at the subagents because they are the exciting part. An
agent with nothing to read is an expensive way to generate confident guesses.

## 7. What not to automate

- Accept-or-reject decisions.
- Threshold tuning, by any agent, under any circumstances. There is no held-out
  data to catch an agent that tunes on a training set and reports a win.
- Writing to `numbers.md` unreviewed.
- Opening the sealed test set.

## 8. Evaluated and rejected

- **`DietrichGebert/ponytail`** (agent minimalism ruleset, MIT, installs as a
  Claude Code plugin; `/ponytail-review`, `/ponytail-audit`). Rejected. Its thesis
  is already in `CLAUDE.md` Development Principles, in a project-specific form. It
  risks fighting the deliberate stage separation in `validation.py`, which
  `CLAUDE.md` requires preserving, and would flag the `evaluation/` diagnostic
  scripts as clutter when they are records of falsified attempts. It also
  addresses code bloat, which is not this project's problem. Its headline 54%
  figure is self-reported on its own benchmark, a standard this project does not
  accept for its own claims. Better alternative: a project-specific review command
  that walks the Five-Line Rule, asks the Overfitting Test question in writing, and
  checks a diff against the Conflict-Detection Invariants.
- **Langfuse self-hosted.** Rejected on weight: Postgres, ClickHouse, Redis and
  MinIO under Docker. OpenTelemetry output keeps the option open if that changes.

## 9. Status

Build order in section 6 is the agreed one, settled 2026-11-08 between the main
session and the forked side session.

### Built (main session, branch `jonan`, nothing committed), verified here 2026-11-09

| Step | What | Evidence |
|---|---|---|
| 1 | `--trace-compare` mode on `evaluation/rerun_suite.py` | Observation 58; flag present at `rerun_suite.py:450` |
| 2 | `tracing.py` plus instrumentation in `orchestrator.py`, `validation.py`, `synthesis.py`, `retrieval_interface.py`, `evaluation/harness.py` | Observation 59. **Acceptance test PASS: 78/78 identical on both corpora**, comparing decision and cited conflict pair; 175 tests pass |
| 4 | `evaluation/safety_curve.py`, swept on Corpus 1 and 2 | Observation 60; refuses all three sealed sets by name |
| 3 | `tbt-guardrail` mod, the sealed-data lock | **WRITTEN BUT NOT WORKING.** Tested 2026-11-09 and it did not fire. See the test record below. Step 3 is **not** done and step 4 on Corpus 3 dev stays blocked. |

#### Step 3 test record, 2026-11-09: FAILED

The owner enabled mod hot-reloading and the engine reported the mod loaded. A
probe then wrote to `docs/PREREGISTRATION_GUARDRAIL_PROBE.md`, a path matching the
preregistration rule. **The write succeeded.** The guard did not refuse it. The
probe file was deleted immediately.

The probe was deliberately aimed at a harmless target rather than at real sealed
data, precisely so that a broken guard could not cause the damage it exists to
prevent. That choice is the only reason this is a test result and not an
incident. Keep it for every future guard: **never prove a lock by pointing it at
the thing you cannot replace.**

What was ruled out, by comparison against the installed `code-modernization`
plugin, which works:

- `hooks/hooks.json` wiring: identical, `{"modules": ["./register.ts"]}` with the
  module beside it.
- `userConfig` field shape: identical keys (`type`, `description`, `default`).
- Folder layout and manifest fields: the same.

What was not found: no engine error line naming the mod anywhere in the session
transcript, and the engine laid no `.claude-plugin/types/` folder beside the mod,
which it does for a mod it has loaded. Those two facts point at the module
failing rather than at a rule not matching, but they do not identify the cause.

**Bisection in progress.** `hooks/register.ts` has been reduced to a near-copy of
the `plugin-authoring` example: one rule, one tool, no loop, no `userConfig`, no
`session.start`, no Bash guard. The full version is parked at
`register.full.ts.bak`, which is not a loadable extension and is not imported.
If the minimal form fires, the pieces go back one at a time; if it does not, the
fault is in the loading path rather than in the guard logic.

**Lesson for the plan.** The earlier entry recorded step 3 as built on the
strength of having written it. Writing a guard and having a guard are different
things, and only the probe could tell them apart. No guard counts as built in
this project until a probe has been refused.

#### Bisection step 1, 2026-11-09: FIRED

The minimal module (one rule, one tool, the documented hook shape) refused the
probe:

```
tbt-guardrail: D:\Major Project\docs\PREREGISTRATION_GUARDRAIL_PROBE.md is sealed here.
```

So the hook shape and the wiring are correct, and the fault in the first version
is in one of the three pieces the minimal one dropped: the `for...of` loop that
registered the tools, `on('session.start', ...)` with its `$.ui.status` call, or
`userConfig` and the `options` parameter. Step 2 restores the rule set with those
three still absent; they go back one at a time, each with a probe, never together.

#### Cause found, 2026-11-09: a type error, proven with `tsc`

The owner approved a local TypeScript install. The engine had by then laid
`.claude-plugin/types/` beside the working minimal mod, so the parked failing
version could be type-checked against the real declarations (staged in the
scratchpad, so the live mod was never disturbed):

```
hooks/register.ts(128,21): error TS2345: Argument of type
  '{ tool: "Edit" | "NotebookEdit" | "Write" }' is not assignable ...
hooks/register.ts(142,15): error TS7006: Parameter '$' implicitly has an 'any' type.
```

**The `for...of` loop was the sole cause.** The tool matcher needs a single
literal name so the engine can narrow the event to that tool's arguments; a
union fails, and the `implicitly any` errors are the collapse after that overload
fails to resolve. Writing the hooks out explicitly fixes it.

Proven by elimination, not by narrative: with the loop removed the module
type-checks clean (exit 0), and it stays clean with every other piece restored,
including `session.start`, `userConfig`, the `options` parameter and the full
rule set. So none of the other suspects was ever at fault.

**The generalisable finding, which answers the main session's question: a
TypeScript type error in a hooks module is enough to stop it loading, with no
error line in the transcript and no `types/` folder laid.** The only outward
sign is that the mod silently does nothing. Therefore:

> **Type-check every hooks module before it goes live.** A mod that has not been
> type-checked and probed is not a guard, it is a decoration.
>
> `tsc -p <mod folder>` once the engine has laid the types; before that, stage a
> copy with a `tsconfig.json` extending `.claude-plugin/types/tsconfig.json`.

#### Review findings from the main session, 2026-11-09

All three accepted, with two factual corrections to the first.

1. **Threshold coverage was badly incomplete. Fixed.** The array listed 8
   constants. An audit of `grep -nE "os\.getenv" validation.py` gives **18**
   env-overridable constants plus `MIN_KNEE_KEEP`, so 10 were unguarded,
   including `MIN_CHUNK_SCORE_THRESHOLD` (a Stage 3 hard floor that drops chunks
   before Stage 4 or 5 sees them), `NLI_SIM_FLOOR`, and the pair-filter knobs
   `MAX_CONFLICT_EVIDENCE_RANK` and `RANK_TIE_EPSILON` that Standing Decision 1
   warns cost 2 to 5 true conflicts. All 19 are now named.
   *Corrections to the finding as filed:* the denominator is 18, not 15, and
   coverage was 8, not 6. `REQUIRE_ASSERTIVE_SPANS` and `DIMENSIONAL_VETO` are in
   `validation.py`, at lines 1009 and 1037. Neither changes the conclusion.
2. **The `safety_curve.py` rule was symmetric where the risk is not. Fixed.**
   Adding a dataset to the refusal list is protective and is now frictionless;
   only a removal is refused, detected by comparing key counts between
   `old_string` and `new_string`, with a whole-file `Write` refused only if the
   content drops a key. An override needed for routine safety-increasing edits
   would stop being deliberate, which is the only property the lock buys.
3. **`numbers.md` is unguarded while its mirror is locked. Documented.**
   `numbers.md` states its values are mirrored in `expected_baseline.json` and
   that the two change together, so the lock would permit the first edit and
   refuse the second, leaving the pair divergent exactly when a number moved.
   Guarding `numbers.md` outright would block legitimate frequent edits, so the
   refusal message now names the problem and tells the owner to make both edits
   together themselves.

#### Correction: the lock was never the right gate for step 4

Earlier revisions of this file, and three messages to the main session, said the
Corpus 3 dev sweep was blocked until the lock worked. **That was wrong, and the
main session was right to press it twice.**

A held-out set is spoiled by being *read* with the result allowed to steer a
decision. This lock refuses *writes*, and it allows reads on purpose so the
sealed test stays runnable. Two different threats were being treated as one:

| Threat | What actually stops it |
|---|---|
| A sealed file being clobbered or quietly edited | this lock |
| A sealed set being swept and the result steering selection | the `SEALED_HINT` refusal list inside `evaluation/safety_curve.py`, which exists, works, and the owner has ruled stays as written |

So the sweep gate already existed before the lock did. The lock remains worth
having, for unattended sessions and for accidental edits, but it must not be
recorded as a safety property it does not have.

#### Step 3 as built: `tbt-guardrail`

Three files, outside the repo: `.claude-plugin/plugin.json`, `hooks/hooks.json`,
`hooks/register.ts`. A `tool.call` hook on `Write`, `Edit` and `NotebookEdit`
returns `{ deny }` for a protected target; each guard is registered with
`.catch(($, e, next) => next.called ? next(e) : { deny })`, so a guard that
throws refuses rather than falls open.

What it refuses, each rule citing the document that seals it:

| Target | Sealed by |
|---|---|
| `data_corpus3/test-*` | Standing Decision 3; opened once 2026-08-31 |
| `corpus3_queries_combined.json` | carries the sealed test split |
| `evaluation/expected_{baseline,corpus3}.json` | its own comment: never edit it to make a run pass |
| `docs/PREREGISTRATION_*.md` | the protocol: written before the run, not edited after |
| `docs/RERUN_*MANIFEST*.md` | tamper evidence for gitignored results |
| threshold constant assignments in `validation.py` | detected in the edit text, by constant name, so ordinary work on the file is unaffected |
| the `SEALED_HINT` list in `evaluation/safety_curve.py` | keeps the sweep off the three sealed sets |
| the mod's own folder | so the guard cannot be removed by an agent |

Override: the `unlocked` boolean in the mod's `userConfig`, which the owner turns
on in `/config`. It is in the owner's own interface, not anything an agent sets.

**Honest limits.**
1. **Not a security boundary.** An agent can ask the owner to disable the mod and
   the owner can agree. What the mod guarantees is that any such attempt becomes
   visible and deliberate rather than silent.
2. **The Bash rule is best effort.** It refuses only a command that holds a sealed
   path *and* a write-ish fragment (`>`, `sed -i`, `tee`, `cp`, `mv`, `rm`,
   `truncate`, `dd`, `git checkout/restore`), so reads still work and the sealed
   test stays runnable. A shell can always be written to evade a pattern. The
   `Write`/`Edit`/`NotebookEdit` locks are the authoritative ones.
3. **Not machine-validated.** `claude plugin validate` and `tsc` could not be run
   here: the bundled CLI is not exposed as a binary and TypeScript is not
   installed. Every API surface used was checked against
   `plugin-authoring/types/claude-code.d.ts` by hand. The engine reports a module
   that fails to load, or a hook that is skipped, as a dim transcript line.
4. **One deviation from the agreed scope.** A single `$.ui.status` line reading
   "sealed data locked" was added, so the owner can see the guard is live. That is
   a small piece of the deferred status-line work; remove it if unwanted.

**Verification still owed:** once the owner enables the mod, attempt a write to a
protected path and confirm the refusal. Until that has been seen, the lock is
written but unproven.

Verified by reading the files and the log, not from the report. `git status` shows
`tracing.py` and `evaluation/safety_curve.py` untracked and six files modified,
nothing committed. Rule 1 was held: one writer on the pipeline core throughout.

### Observation 60's result, the answer to "never unsafe"

| | Corpus 1 | Corpus 2 |
|---|---|---|
| Gates off (c=0): answered / accuracy / unsafe | 53/78, 71, 7 | 59/78, 61, 14 |
| Shipped default (c=1.0) | 43/78, 75, **0** | 43/78, 70, **1** |
| First zero-unsafe point | **c=1.0**, 43/78, 75 | **c=1.5**, 21/78, 49 |
| Cost of reaching it from the default | none | **-22 answers, -21 accuracy** |

So zero unsafe is already free on Corpus 1 and costs 21 correct decisions on
Corpus 2, halving the answer rate from 55.1% to 26.9%. **The zero-unsafe point
does not transfer between the two corpora.** That is outcome three of the three
listed in item B, the calibration-transfer finding, and the most interesting of
them.

Internal validity: conflict recall and false-conflict counts were identical at all
seven points on both corpora, confirming the dial touches Stage 5 only.

**Honest limits on that table.** The Corpus 2 unsafe answer it eliminates is a
single query, so the 21-to-1 ratio rests on n=1 and the main session has already
withdrawn the confidence it first stated it with. At n=32 per corpus the
intervals are wide. Both corpora sit at 0 or 1 unsafe at the default, so they show
the cost side almost exclusively; the high-unsafe data that would show the benefit
side (MultiHop 56/150, Corpus 3) is sealed. Wilson intervals go into
`safety_curve.py` before any dev run.

### Settled: owner ruling, 2026-11-09

The question was whether Observation 60's Corpus 1 and 2 sweep reopens the owner
decision of 2026-10-11 (Observation 43).

**Owner's ruling: it does not. Those runs were re-verification.** The 2026-10-11
decision removed the *obligation* to re-verify Corpus 1 and 2; it did not forbid
running them. Observation 60 stands as recorded. Corpus 1 and 2 are **not** added
to the refusal list in `safety_curve.py`; the list stays as written, covering
`3-test`, `ramdocs` and `multihop` only.

**One distinction to carry forward.** Re-verification means running a known
configuration and checking the numbers reproduce. Observation 60 swept seven dial
points and read off the first zero-unsafe point, which is a sensitivity
measurement rather than a reproduction. That difference does not affect
permissions, because Corpus 1 and 2 are training data with no held-out claim to
protect. It affects how the result may be *used*: selecting the dial's operating
point from C1/C2 numbers is selection on training data, which is the proper use of
training data, but the point so chosen may not be called validated. Validation
comes from Corpus 3 dev, then the one-shot preregistered runs on the sealed sets
described above. Keep those two words apart in `main.tex`.

### Next

Step 3, the sealed-data lock, is now due: it must exist before step 4 runs on
Corpus 3 dev, which is the first work that may run unwatched.
