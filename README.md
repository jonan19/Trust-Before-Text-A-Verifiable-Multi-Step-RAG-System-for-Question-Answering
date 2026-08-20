# Trust Before Text

A question-answering system over policy documents that **decides whether it is
safe to answer before it writes anything** — and makes that decision without an
LLM.

Ask it *"How many days can I work from home?"* and it does not just find text and
summarise it. First it checks three things:

1. **Is this evidence real?** — did every retrieved passage actually come from
   the ingested documents, or did an attacker inject it?
2. **Do the documents contradict each other?** — if the handbook says 2 days and
   the remote-work policy says 3, you should be told there is a conflict, not
   handed one of the two numbers.
3. **Is there enough here to answer at all?** — if the corpus simply does not
   cover your question, the honest answer is "I don't know".

Only if all three checks pass does an LLM get invoked to write the answer. The
LLM never makes the safety decision. That is the whole idea: **trust is
established before text is generated.**

---

## Start here

**New to this project? Read the docs in this order.**

| # | Document | What it answers |
|---|---|---|
| 1 | **[docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md)** | What the system does, how each stage works, and what every file in the repo is for. Written for someone who has never seen the code. |
| 2 | **[docs/STATUS.md](docs/STATUS.md)** | What currently works, what is broken, and the one big unsolved problem. All current numbers live here. |
| 3 | **[docs/REPRODUCE.md](docs/REPRODUCE.md)** | Every command needed to regenerate every number in `STATUS.md`. |

Those three files are the **only** current documentation. Everything under
[docs/archive/](docs/archive/) is a historical record kept for the paper's audit
trail — it contains superseded numbers and should not be used as a reference.
See [docs/archive/README.md](docs/archive/README.md) for what each archived file was.

---

## Quick start

```bash
pip install -r requirements.txt

# 1. Ingest a corpus (builds the vector store + provenance registry)
python main.py --ingest --retriever qdrant

# 2. Ask a question
python main.py --query "How many days a week can I work from home?"

# 3. Or run the web UI
python api.py          # then open frontend/index.html
```

`.env` holds the LLM API key. Retrieval, all seven validation stages, and the
whole safety decision run locally with no network calls — only the final
answer-writing step calls an LLM, and only when the decision layer has already
allowed it.

---

## What makes this different from a normal RAG system

A normal RAG pipeline retrieves passages, pastes them into a prompt, and asks an
LLM to answer — including asking it to notice contradictions or to refuse when
evidence is missing. That means **the same model that writes the answer also
decides whether answering is safe**, and it can be talked out of that decision.

Measured here: a defended LLM baseline, explicitly told the passages are
untrusted data, answered an attacker's fabricated policy on **every single one
of 48 adversarial probes**. This system abstained on all 48, because the
abstention is a deterministic routing decision made before any prompt exists.

The trade is honest and documented: the decision layer is more cautious than an
LLM and over-abstains on some answerable questions. See
[docs/STATUS.md](docs/STATUS.md).

---

## Current state at a glance

| | Corpus 1 (HR policies) | Corpus 2 (university policies) |
|---|---|---|
| Decision accuracy | 92.3% | 82.1% |
| Contradictions found | 16/16 | 15/16 |
| Answered when it should have refused | 1/32 | 2/32 |
| Adversarial probes leaked | see [STATUS](docs/STATUS.md) | 0/24 |

**The one big unsolved problem** is false conflicts: the system sometimes reports
a contradiction that is real in the corpus but irrelevant to your question. Full
explanation in [docs/STATUS.md](docs/STATUS.md).

---

## Repository layout

A one-line map; the full annotated tree is in
[docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md).

```
*.py                  the system itself (validation.py is the heart of it)
data/                 Corpus 1 — HR policies + 78 test questions
data_corpus2/         Corpus 2 — university policies + 78 test questions
evaluation/           the test suite (start with run_eval.py)
experiments/          frozen results from the original paper experiments
docs/                 documentation (start with HOW_IT_WORKS.md)
docs/archive/         superseded documents, kept for the audit trail
frontend/             browser UI
paper_assets/         the LaTeX paper and its figures
```
