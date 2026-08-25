# Corpus 3, Track B — Question authoring protocol

**Give this document to the author. Give them nothing else.**

---

## For the person running the study (remove before handing over)

The author must not see: this system, any of its outputs, `claude.md`,
`docs/STATUS.md`, `docs/PREREGISTRATION_CORPUS3.md`, the ContractNLI
annotations, or the 17 ContractNLI hypotheses. Any of those leaks the thing being
measured.

What to hand over: this page, and one folder per bundle containing four `.txt`
files. Nothing else from the repository.

**Pilot first.** Commission 2 **dev** bundles (16 questions), check the returned
file parses and that quoted passages resolve, fix any wording here, and only then
commission the 30 test bundles. The pilot exists so protocol bugs are found on
data that is allowed to be looked at twice.

**Order of work.** This is the critical path — recruiting and authoring takes
longer than everything else in the plan combined. Start it before writing any
code.

**Claim wording.** With one author there is no inter-annotator agreement figure;
say so in the paper. The precise, defensible claim is *"authored by a third party
who never saw the system or its outputs."* Do not write "independently
annotated" unqualified. If a second labeller becomes available, have them
re-label a 20% sample and report Cohen's κ.

---

## What you are doing

You will read sets of four real non-disclosure agreements (NDAs) and write
questions about them, together with the answer you believe is correct.

Your questions will be used to test a question-answering system. **You will not
see that system or its answers**, and that is deliberate — if you could see them,
you might unconsciously write questions that flatter or trip it, and the test
would be worthless. Write the questions you would genuinely ask if you needed to
understand these contracts.

There are no trick questions and no wrong answers to worry about. If you find a
question hard to label, say so in the notes field; that is useful data, not a
failure.

## What you get

A folder per bundle, e.g. `test-b00/`, containing four `.txt` files. Each file is
one complete NDA. Treat the four as a set — like four contracts a company has
signed with different partners, which someone now has to review together.

## What to produce

For each bundle, **8 questions**. For each question record:

| Field | What goes in it |
|---|---|
| `question` | The question, in your own words, as you would naturally ask it. |
| `decision` | One of `answer`, `insufficient`, `conflict` — see below. |
| `sources` | The filename(s) your answer relies on. Empty for `insufficient`. |
| `quotes` | For each source, the **exact text** copied from the file that supports your answer. Copy-paste it; do not retype or tidy it. |
| `notes` | Anything that made this hard or ambiguous. Optional. |

### The three decisions

- **`answer`** — the documents answer this question. One document addressing it
  is enough. Also use this when several documents address it and **agree**.
- **`insufficient`** — the documents do not address this. The information simply
  is not there.
- **`conflict`** — two or more documents address it and **genuinely disagree**.
  Use this only for real disagreement about the same point, not for two documents
  covering different topics, and not for one being more detailed than another.

**On `conflict`, the important distinction:** these are four separate contracts
with different companies, so they will naturally differ in wording, parties,
dates and structure. That is not a conflict. A conflict is when they make
*incompatible claims about the same proposition* — for example, one says
confidential material must be returned within 30 days and another says it may be
retained indefinitely.

### The quota

To keep the question set balanced, aim per bundle for:

- **3** questions you expect to be answerable
- **2** questions you expect the documents do **not** cover
- **2** questions where you expect the documents to **disagree**
- **1** free choice

**The quota tells you what to go looking for. It does not tell you what to
label.** Go hunting for a disagreement; if the documents turn out to agree,
record `answer`. If a question you expected to be answerable turns out not to be
covered, record `insufficient`. Being wrong about your own expectation is normal
and we measure it — never adjust a label to hit the quota.

### Writing good questions

- Ask them the way a person would, not the way a contract is written. "Can we
  share this with our lawyers?" is better than "Is disclosure to professional
  advisors permitted?"
- Vary the phrasing across bundles. Do not settle into a template.
- Do not copy sentences out of the documents and turn them into questions.
- Keep each question about **one** thing.
- Never make the answer part of the question.

### Quotes matter

The quote is how we check the system cites the right passage, so it must be
**exactly** what the file says — same words, same punctuation, same spelling,
including anything that looks like a typo or a strange character. Copy and paste.
A quote that has been retyped or cleaned up cannot be matched and the question
has to be discarded.

## Format

One JSON file per bundle, named `queries_open_raw.json`, saved in that bundle's
folder:

```json
{
  "bundle": "test-b00",
  "author": "your name or initials",
  "questions": [
    {
      "question": "If we get a subpoena, do we have to tell the other side before handing anything over?",
      "decision": "answer",
      "sources": ["nda_27.txt"],
      "quotes": {
        "nda_27.txt": "shall provide prompt written notice to the Disclosing Party prior to such disclosure"
      },
      "notes": ""
    }
  ]
}
```

Plain text in a spreadsheet is fine too if JSON is awkward — one row per
question, same columns. Send it back however is easiest.

## Ground rules

1. Do not look at the system, its output, or any other document from this
   project.
2. Do not discuss the questions with anyone else working on the project until
   the set is delivered.
3. Once a bundle is delivered it is **final**. Do not revise it later — that is
   the whole point of the exercise.
4. If something in this protocol is unclear, ask before starting rather than
   guessing partway through.

Thank you — this is the part of the evaluation that cannot be automated, and the
whole result depends on it.
