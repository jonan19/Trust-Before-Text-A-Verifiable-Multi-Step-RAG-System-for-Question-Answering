# Trust Before Text

A question-answering system over policy documents that **decides whether it is
safe to answer before it writes anything**, and makes that decision without an
LLM.

Ask it *"How many days a week can I work from home?"* and it does not simply
find text and summarise it. First it checks three things:

1. **Is this evidence real?** Did every retrieved passage actually come from the
   ingested documents, or was it injected?
2. **Do the documents contradict each other?** If the superseded policy says 2
   days and the current one says 3, you should be told there is a conflict, not
   handed one of the two numbers.
3. **Is there enough here to answer at all?** If the corpus does not cover your
   question, the honest answer is "I don't know".

Only if all three checks pass does an LLM get invoked to write the answer. The
LLM never makes the safety decision. That is the whole idea: **trust is
established before text is generated.**

---

## What this project actually claims

This distinction matters more than any single number here, so it comes first.

**Structural claims** hold by construction. They do not depend on a sample, and
they cannot be argued away by a cleverer attacker prompt, because the component
being attacked is not in the loop:

| Property | Result |
|---|---|
| Injected text reaching the LLM prompt | 0/45 |
| Routing decision changed by injection | 0/45 |
| Fabricated evidence accepted (control abstains 4/4) | 0/4 |
| Decisions changed by reordering or duplicating documents | 0/78, both corpora |
| Adversarial gap probes answered unsafely | 0/48 |

The reason injection cannot flip the decision is not that the model resists it.
It is that the decision is made by deterministic code, before any prompt exists.
A defended LLM baseline, explicitly told its passages were untrusted, answered
the attacker's fabricated policy on **12 of 12 probes in each of three separate
runs**.

**Statistical claims** are accuracy figures over a sample, and they deserve much
less trust. Read the next section before quoting any of them.

---

## The honest results

Corpus 1 and Corpus 2 were **written by this project** and have been used to
accept or reject changes dozens of times. Their accuracy is a *training* metric.

| | Corpus 1 (HR policies) | Corpus 2 (university policies) |
|---|---|---|
| Decision accuracy | 96.2% (75/78) | 89.7% (70/78) |
| Contradictions found | 16/16 | 14/16 |
| Conflict precision | 1.000 | 0.875 |
| Right pair cited | 1.000 | 0.875 |
| Answered when it should have refused | 0/32 | 1/32 |
| False conflicts | 0 | 2 |

On corpora this project **did not** write, a plain prompted LLM is safer or more
correct than this system:

| Benchmark | This system | Prompted LLM baseline |
|---|---|---|
| ContractNLI, sealed test (510 queries) | 26.7% accuracy, against a 77.6% always-answer floor | not run |
| RAMDocs, safe rate | 85.2% | **94.8%** |
| RAMDocs, exact match | **18.0%** | 7.6% |
| MultiHop-RAG, unanswerable questions answered | **56/150** | 2/150 |
| MultiHop-RAG, decisions correct | 41.7% | **62.7%** |

That is the measured result, it is reported in full in the paper, and it is not
a bug to be tuned away. **The contribution is the guarantee, not the accuracy.**
A system that is merely accurate can still be talked into asserting a planted
policy; this one cannot, and that property is what the numbers above are there
to support.

Every figure on this page is traceable to [numbers.md](numbers.md), which is the
single source of truth. If any document in this repo disagrees with it, that
document is wrong.

---

## Quick start

```bash
pip install -r requirements.txt
```

```bash
python api.py
```

Then open **http://localhost:8000**. The API serves the interface itself; there
is no separate build step and no second server.

First start takes about half a minute while the embedding, NLI and
cross-encoder models load. Retrieval and all seven validation stages run
locally with no network calls. Only the final answer-writing step calls an LLM,
and only when the decision layer has already allowed it, so a refusal costs
nothing. Put an API key in `.env` if you want written answers; the routing
decision works without one.

Command line, if you prefer it:

```bash
python main.py --query "How many days a week can I work from home?"
```

### The interface

A switch in the top right toggles two views of the same query:

- **Use** shows the corpus, the upload area, the question bar, the decision, and
  the evidence the decision rests on.
- **Inspect** adds the seven-stage pipeline trace. Click any stage to see what it
  actually did: survivor counts, focus terms, NLI scores, which gate fired, and
  the raw response.

Uploading a document asks whether to index it **permanently** or
**temporarily**. Both are indexed identically and are equally searchable. A
temporary document lives in `data_temp/`, never enters the corpus on disk, and
is discarded when the server restarts or when you press discard.

`data/` is read-only to the app. It holds Corpus 1, the evaluation corpus behind
the published numbers, and nothing in the interface can delete it.

---

## How it works

```
query
  -> preprocess          normalise punctuation, contractions, whitespace
  -> classify            rule-based; no LLM
  -> decompose           split multi-part questions
  -> retrieve            hybrid search, tuned for recall, not precision
  -> validate            seven stages, deterministic
  -> decide              answer | conflict | insufficient
  -> synthesise          LLM, only on "answer"
```

The seven validation stages are provenance, normalisation, deduplication,
relevance filtering, conflict detection, sufficiency, and structuring. Stage 0
(provenance) is why injected text cannot reach the prompt: a passage that cannot
be traced to an ingested document is not weak evidence, it is not evidence, and
no later stage can be persuaded otherwise.

Retrieval maximises recall. Validation decides what is trustworthy. The LLM only
writes prose from evidence that has already passed. Keeping those three jobs
apart is the architecture.

---

## Seeing inside a decision

Tracing is off by default and is a no-op unless enabled:

```bash
RAG_TRACE=1 python api.py
```

Every query then appends one JSON line to
`evaluation/results/traces/trace_<date>.jsonl` recording per-stage survivor
counts, the focus terms, every NLI contradiction score, the answerhood margins,
and which gate vetoed what.

Tracing observes; it never votes. That is enforced by a test, not by assertion:

```bash
python evaluation/rerun_suite.py --trace-compare --corpora 1,2
```

It runs the evaluation twice, with and without tracing, and requires identical
decisions **and** identical cited evidence pairs on all 78 queries of both
corpora.

---

## Documentation

Read in this order:

| # | Document | What it answers |
|---|---|---|
| 1 | [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md) | What the system does, how each stage works, what every file is for. Written for someone who has never seen the code. |
| 2 | [docs/STATUS.md](docs/STATUS.md) | What works, what does not, and the open problems. |
| 3 | [docs/REPRODUCE.md](docs/REPRODUCE.md) | Every command needed to regenerate every number. |
| 4 | [main.tex](main.tex) | The paper. Reports both the frozen snapshot and the current system, labelled. |

Two living files track the work as it happens:

| File | What it is |
|---|---|
| [numbers.md](numbers.md) | Every headline number, once, with its source. Update it first when a number changes. |
| [RAG_System_Observation_Log.md](RAG_System_Observation_Log.md) | Append-only log of every change: issue, cause, fix, measured effect. |

`docs/NUMBERS_LEDGER.csv` traces each number in the paper back to the file it
came from; `python evaluation/check_ledger.py` verifies it.

Everything under [docs/archive/](docs/archive/) is a historical record kept for
the audit trail. It contains superseded numbers and should not be used as a
reference.

---

## Known limits

- **No held-out data of our own.** Both self-authored corpora have been used for
  selection many times, so their accuracy cannot be read as generalisation. The
  highest-value open item is an external corpus with questions and gold labels
  authored by someone else.
- **Zero unsafe answers is an operating point, not a free property.** Measured:
  reaching it on Corpus 2 costs 22 answers and 21 accuracy points, halving the
  answer rate, and the setting that achieves it does not transfer between the two
  corpora. See `evaluation/safety_curve.py` and Observation 60.
- **Over-abstention is the standing cost.** The decision layer is more cautious
  than an LLM and refuses some answerable questions. On MultiHop-RAG it also
  under-abstains in the other direction, answering 56 of 150 unanswerable
  questions.
- **Poisoning a document before ingestion defeats it**, and defeats a defended
  LLM equally. Provenance verifies that a passage came from the ingested corpus,
  not that the corpus was honest when it was ingested. That is a data-provenance
  bound, and the only layer that moves it is trusted ingestion.
- **Sealed datasets.** Corpus 3 test, RAMDocs and MultiHop-RAG are sealed against
  tuning by their own preregistrations. Tooling in this repo refuses to sweep
  them by name.

---

## Repository layout

```
*.py                  the system (validation.py is the heart of it)
tracing.py            optional execution tracing, off unless RAG_TRACE=1
api.py                local server; serves the API and the interface
frontend/             the browser interface
data/                 Corpus 1, HR policies, plus 78 test questions
data_corpus2/         Corpus 2, university policies, plus 78 test questions
data_corpus3/         Corpus 3, ContractNLI; the test split is sealed
data_uploads/         permanent uploads made through the interface
data_temp/            session-only uploads, purged on restart
evaluation/           the test suite; start with run_eval.py
experiments/          frozen results from the original paper experiments
docs/                 documentation; start with HOW_IT_WORKS.md
main.tex              the paper
```
