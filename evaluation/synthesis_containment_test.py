"""
synthesis_containment_test.py — Limitation 5: structural containment of the
synthesis layer.

The E3/E4 result was that synthesis could be hijacked (ASR 0.40, exfiltration
0.87) and that prompt hardening drove that to zero. Hardening is a soft defense:
it asks the model not to obey text it is shown, so its success is a measured
rate against the phrasings that were tried, not a property of the system.

This tests a different claim, at the input boundary rather than the output:

    with Stage-0 provenance verification, injected content never reaches the
    synthesis prompt at all.

An injection of this threat model works by getting attacker-authored text into
the retrieved evidence. That text is, by construction, not in the corpus
registry, so Stage 0 removes it before Stage 6 structures the evidence and
before any prompt is built. The model cannot obey an instruction it is never
shown, whatever the phrasing, so the property does not depend on the model.

Replays the exact 45 E3 cases (15 queries x 3 styles) and checks, for each:
  1. the poisoned chunk is rejected by Stage 0
  2. no poison text survives into the evidence that would be synthesized
  3. the routing decision is unchanged from the un-poisoned control

Zero LLM tokens.

    python evaluation/synthesis_containment_test.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import harness_bootstrap  # noqa: F401
import harness
import validation

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "experiments"))

MAX_CHUNKS = 12


def main() -> None:
    orchestrator = harness.setup("1")
    from baseline_experiment import retrieve_same_evidence
    from injection_test import (QUERIES, STYLES, build_poison_chunk,
                                context_block, POISON_SOURCE, route_decision)

    registry = validation._EVIDENCE_REGISTRY
    if registry is None:
        raise SystemExit("no provenance registry available for this store")

    rows = []
    for (qid, qtext, true_pat, wrong_value, wrong_pat) in QUERIES:
        chunks, _, _ = retrieve_same_evidence(qtext)
        clean_chunks = chunks[:MAX_CHUNKS]
        control = route_decision(validation.validate(clean_chunks, query=qtext))

        for style in STYLES:
            poison = build_poison_chunk(style, wrong_value)
            poisoned = [poison] + list(clean_chunks)

            validation.set_evidence_registry(None)      # provenance OFF
            before = validation.validate(poisoned, query=qtext)
            ctx_before = context_block(before["cleaned_chunks"])

            validation.set_evidence_registry(registry)  # provenance ON
            after = validation.validate(poisoned, query=qtext)
            ctx_after = context_block(after["cleaned_chunks"])

            rows.append({
                "key": f"{qid}|{style}", "qid": qid, "style": style,
                "control_decision": control,
                "poison_in_prompt_before": POISON_SOURCE in ctx_before,
                "poison_in_prompt_after": POISON_SOURCE in ctx_after,
                "poison_text_after": poison["text"][:40] in ctx_after,
                "rejected_by_stage0": after["unverified_count"],
                "decision_before": route_decision(before),
                "decision_after": route_decision(after),
                "routing_changed_by_attack": route_decision(after) != control,
            })

    n = len(rows)
    in_before = sum(r["poison_in_prompt_before"] for r in rows)
    in_after = sum(r["poison_in_prompt_after"] or r["poison_text_after"] for r in rows)
    rejected = sum(r["rejected_by_stage0"] == 1 for r in rows)
    routing_changed = sum(r["routing_changed_by_attack"] for r in rows)

    print(f"E3 injection cases replayed: {n}")
    print(f"  poison reached the synthesis prompt, provenance OFF : {in_before}/{n}")
    print(f"  poison reached the synthesis prompt, provenance ON  : {in_after}/{n}")
    print(f"  poison chunk rejected at Stage 0                    : {rejected}/{n}")
    print(f"  routing decision changed by the attack              : {routing_changed}/{n}")

    out = HERE / "results" / "synthesis_containment.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({
        "summary": {"n": n, "poison_in_prompt_before": in_before,
                    "poison_in_prompt_after": in_after,
                    "rejected_at_stage0": rejected,
                    "routing_changed": routing_changed},
        "results": rows,
    }, indent=2), encoding="utf-8")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
