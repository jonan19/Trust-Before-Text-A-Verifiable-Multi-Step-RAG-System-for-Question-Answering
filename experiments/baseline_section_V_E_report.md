# §V.E Baseline Artifacts — Prompted-LLM Baseline (Experiment E1)

*Every number is computed directly from `experiments/baseline_results.json`
(full raw) / `experiments/baseline_per_query.json` (clean per-query). Nothing
estimated. Our-system column is the CURRENT v6 system, regenerated live in
`experiments/our_decisions.json` — NOT the stale `data/phase6_fullrun_results*.json`
files (those are v4 = 67.9% and v5 = 83.3%, not the current system; do not cite
them for either system).*

Raw per-query file for the section: **`experiments/baseline_per_query.json`**
(fields: id, category, query, expected, baseline_decision [canonical, temp 0],
baseline_hot_decisions [5 runs @ temp 0.7], baseline_inconsistent, our_decision,
baseline_correct, plus `leakage` on gap rows and `attribution`+`baseline_reply`
on conflict rows).

---

## 1. Setup

- **Model:** Groq **`llama-3.3-70b-versatile`** (single model; the only backend key present). No OpenAI/Gemini used.
- **Evidence given to the baseline:** the SAME retrieved chunks our pipeline produces (preprocess → classify → decompose → hybrid retrieve), capped at the **top-12** passages per query, each labelled with its source document.
- **Runs per query (N):** **6 total** — **1 canonical run at temperature 0.0** (used for accuracy, attribution, leakage) **+ 5 repeated runs at temperature 0.7** (used for the determinism/flip test).
- **Exact prompt (verbatim).**
  - *System:*
    ```
    You answer questions using ONLY the provided context passages. Follow these rules exactly:
    1. If the answer is not present in the context, reply with exactly the single word: INSUFFICIENT
    2. If two passages give conflicting values for the fact being asked, reply with the word CONFLICT followed by both values and which document each value came from.
    3. Otherwise, give the answer, citing the document it came from.
    Do not use any knowledge beyond the context passages.
    ```
  - *User:*
    ```
    Context passages:
    {chunks}

    Question: {query}

    Answer (remember: exactly INSUFFICIENT if not present; start with CONFLICT if two passages disagree on the asked fact):
    ```
- **Decision parsing:** reply beginning with `CONFLICT` → conflict; `INSUFFICIENT` → insufficient; otherwise → answer.

---

## 2. Accuracy + baseline confusion matrix

**Decision accuracy: 76 / 78 = 97.4%** (canonical temp-0 run).

Confusion matrix — rows = gold (expected), columns = what the baseline gave:

| gold ↓ / baseline gave → | Answer | Conflict | Insufficient | total |
|---|---|---|---|---|
| **Answer** | 45 | 0 | 1 | 46 |
| **Conflict** | 1 | 15 | 0 | 16 |
| **Insufficient** | 0 | 0 | 16 | 16 |

The baseline's **2 errors**:
- **Q072** (gold Answer → gave **Insufficient**): over-abstention on an answerable query (safe error).
- **Q035** (gold Conflict → gave **Answer**): answered despite a real cross-document conflict (**unsafe** — see item 6).

*(For reference, our v6 system: 72/78 = 92.3%; its 6 errors are all Answer→Conflict over-caution, 0 unsafe.)*

---

## 3. Pillar 1 — Determinism / flip-rate

Across the **5 repeated runs at temperature 0.7**, a query is "inconsistent" if its decision was not identical on all 5 runs.

- **Baseline flip count: 1 / 78 = 1.3%.**
- The single flipping query: **Q069** — decisions across the 5 runs were `[conflict, answer, answer, answer, answer]` (1 run diverged).
- **Our system: 0 / 78 = 0%** (deterministic by construction; verified by re-running identical output).

---

## 4. Pillar 2 — Parametric leakage (on the 16 gap/insufficient queries)

Leakage = the baseline produced a concrete answer instead of `INSUFFICIENT` on a query the corpus genuinely does not answer.

- **Canonical (temp 0): 0 / 16 leaked.**
- **Any of the 5 hot runs (temp 0.7): 0 / 16 leaked.**
- **Our system: 0 / 16** (generation is never invoked on an abstain).

Honest note: on these *natural* gap queries the well-prompted baseline abstained perfectly. (Adversarial leakage probes were not run — a candidate future experiment.)

---

## 5. Pillar 3 — Conflict-attribution quality (on the 16 conflict queries)

3-point rubric per conflict query: (a) flagged `CONFLICT`; (b) named **both** clashing documents; (c) gave **both** values.

| Rubric point | Baseline | Our system |
|---|---|---|
| (a) flagged CONFLICT | 15 / 16 | 16 / 16 |
| (b) named both documents | 16 / 16 | 16 / 16 |
| (c) gave both values | 15 / 16 | 16 / 16 |
| **full 3/3** | **14 / 16** | 16 / 16 |
| **mean score** | **2.875 / 3** | 3.00 / 3 (structural) |

The one conflict the baseline did not flag is **Q035** (it answered instead). Per-query rubric flags and the baseline's raw reply text are in `baseline_per_query.json` (`attribution` + `baseline_reply` on each conflict row).

---

## 6. Unsafe answers (the direct safety comparison)

Unsafe = the baseline gave a plain answer despite a conflict or a gap (16 conflict + 16 insufficient = 32 "should-not-answer" queries).

- **Baseline: 1 / 32 unsafe** — **Q035** (answered a real conflict, reporting one side's value).
- **Our system: 0 / 32 unsafe.**

---

## One-line framing for §V.E
*Even though the prompted baseline reaches higher decision accuracy (97.4% vs 92.3%), it does so non-deterministically (1/78 flip), and it produced 1 unsafe answer (answering despite a real conflict, Q035) where our gate produced 0/32; the baseline's abstention and attribution behaviours are strong but soft (learned/prompted), whereas ours are structural and deterministic.*
