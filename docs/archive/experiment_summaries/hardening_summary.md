# HARD TEST 4 — Synthesis Hardening (before / after)

*Only the synthesis prompt + evidence wrapping changed. No validation/decision threshold touched. Same 45 poisoned inputs as E3. Model llama-3.3-70b-versatile, temp 0.*

## End-to-end synthesis ASR: E3 (before) vs hardened (after)

| Injection style | E3 before | Hardened after |
|---|---|---|
| direct | 0.13 | 0.00 |
| authority | 0.20 | 0.00 |
| exfil | 0.87 | 0.00 |
| **All (n=45)** | **0.40** | **0.00** |

## Exfiltration specifically (E3 was 0.87)

- Before (E3): 0.87  →  After hardening: 0.00

## Regression on clean (un-poisoned) queries

| | queries answered | correct value present | mean faithfulness |
|---|---|---|---|
| Before hardening | 15 | 14/15 | 0.1 |
| After hardening | 15 | 14/15 | 0.1 |

Clean-query decision flips after hardening: 0 (none — decisions unchanged, as expected)

## Honest finding

After hardening, end-to-end synthesis ASR = **0.00** (was 0.40 in E3); exfiltration 0.87 → 0.00. This is a DEFENSIVE fix: the hardened system now matches a defended LLM end-to-end (E3 defended-LLM ASR was 0.00) rather than being worse. It is not an end-to-end *advantage* over a defended LLM. The durable advantage remains at the DECISION layer (injection-immune 0/45 by construction). Clean-query regression: decisions unchanged (synthesis never affects routing); correct value retained 14/15; faithfulness 0.1 → 0.1.