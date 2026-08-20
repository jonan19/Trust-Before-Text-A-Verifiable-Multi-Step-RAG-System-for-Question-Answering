# Baseline Comparison — Trust Before Text vs. a Prompted-LLM Baseline

*Model:* `llama-3.3-70b-versatile` · *consistency runs:* 5 @ temp 0.7 · *canonical:* temp 0.0 · *context:* top-12 retrieved passages/call · *n =* 78 queries.

Every number below is recomputed from `baseline_results.json` (baseline) and `our_decisions.json` (current v6 system). Our-system decisions were regenerated from the live pipeline, not read from the stale `data/phase6_fullrun_results*.json` files (those are v4/v5).

## Summary table

| Axis | Trust Before Text (ours) | Prompted-LLM baseline |
|---|---|---|
| Decision accuracy | 72/78 = **92.3%** | 76/78 = **97.4%** |
| **Pillar 1 — decision flips** (temp 0.7, 5 runs) | **0/78 = 0.0%** (deterministic by construction) | 1/78 = 1.3% |
| **Pillar 2 — parametric leakage** (on 16 gap queries) | **0** (generation never invoked) | 0 at temp 0 / 0 in any hot run |
| **Pillar 3 — conflict attribution** (on 16 conflicts) | **3.00 / 3** (structural) | 2.88 / 3 |
| &nbsp;&nbsp;· flagged CONFLICT | 16/16 | 15/16 |
| &nbsp;&nbsp;· named both documents | 16/16 | 16/16 |
| &nbsp;&nbsp;· gave both values | 16/16 | 15/16 |

## Honest findings

1. **Accuracy is a near-tie, and on this corpus the baseline edges ahead** (97.4% vs 92.3%). This is expected and was predicted: a well-prompted strong LLM handles a friendly, well-authored benchmark well. Accuracy is **not** the paper's claim.
2. **All of our 6 errors are safe over-caution** — false conflicts on answerable queries (Q001, Q019, Q029, Q062, Q064, Q072). The system abstains and shows the two documents it believes disagree; it never emits wrong information.
3. **The baseline answered a genuine conflict** (Q035): it produced a direct answer on a query where two documents give conflicting values, rather than flagging CONFLICT. This is exactly the unsafe-shaped behavior our architectural gate makes structurally impossible.
4. **Measured determinism and leakage gaps are real but small on this benchmark** — the baseline flipped on 1/78 query (Q069) and leaked on 0/16 gaps. We do **not** inflate these. The contribution is that ours is **0 by construction** — a *guarantee* that holds under distribution shift, where a soft-prompted model's low-but-nonzero rates would grow — plus a per-stage auditable reason a prompted model cannot provide.

## Framing for §4.5

> Even where a strong prompted LLM matches or exceeds our decision accuracy on this benchmark, it does so **non-deterministically** (1/78 decision flips observed, and 0% is not guaranteed), it **can answer despite a genuine document conflict** (1 case here), and it produces **no auditable record** of which check failed and why. Trust Before Text provides all three — determinism, structural conflict abstention, and a per-stage reason — as a property of the architecture rather than a tendency of a prompt.

*Baseline errors:* Q035 (exp conflict, got answer), Q072 (exp answer, got insufficient).
