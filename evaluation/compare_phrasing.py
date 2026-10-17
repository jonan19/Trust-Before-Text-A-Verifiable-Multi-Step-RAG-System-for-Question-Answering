"""
compare_phrasing.py — Isolate query-phrasing sensitivity on Corpus 3.

Track A and the qform variant ask the SAME 17 propositions about the SAME
documents with the SAME gold labels; only the surface form differs (ContractNLI's
declarative hypothesis vs. a frozen interrogative rewrite). So a decision that
differs between them is caused by phrasing alone.

That makes this the controlled version of the Track A vs Track B contrast, where
phrasing, question content and gold mix all varied together and nothing could be
attributed cleanly.

CLAUDE.md failure pattern #1 predicts flips here ("the decision changes when the
query is reworded without changing its meaning"). This measures how many.

    python evaluation/compare_phrasing.py
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent / "results"


def load(tag: str) -> dict:
    path = OUT / f"{tag}_corpus3_test.json"
    if not path.exists():
        raise SystemExit(f"missing {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {r["id"]: r for r in payload["results"]}


def main() -> None:
    a = load("c3_hypothesis")
    q = load("c3_qform")

    shared = sorted(set(a) & set(q))
    if not shared:
        raise SystemExit("no shared query ids")

    flips = [i for i in shared if a[i]["observed"] != q[i]["observed"]]
    transitions = Counter((a[i]["observed"], q[i]["observed"]) for i in flips)

    a_correct = sum(a[i]["match"] for i in shared)
    q_correct = sum(q[i]["match"] for i in shared)

    # A flip is "safety-relevant" when exactly one side answered on a query whose
    # gold said abstain -- i.e. rewording alone created or removed an unsafe answer.
    unsafe_created = [
        i for i in flips
        if a[i]["expected"] in ("conflict", "insufficient")
        and a[i]["observed"] != "answer" and q[i]["observed"] == "answer"
    ]
    unsafe_removed = [
        i for i in flips
        if a[i]["expected"] in ("conflict", "insufficient")
        and a[i]["observed"] == "answer" and q[i]["observed"] != "answer"
    ]

    print(f"shared queries              : {len(shared)}")
    print(f"decisions that FLIPPED      : {len(flips)}  ({100*len(flips)/len(shared):.1f}%)")
    print(f"accuracy, hypothesis form   : {100*a_correct/len(shared):.1f}%")
    print(f"accuracy, question form     : {100*q_correct/len(shared):.1f}%")
    print()
    print("flip directions (hypothesis -> qform):")
    for (x, y), n in transitions.most_common():
        print(f"   {x:>12} -> {y:<12} {n}")
    print()
    print(f"rewording CREATED an unsafe answer : {len(unsafe_created)}")
    print(f"rewording REMOVED an unsafe answer : {len(unsafe_removed)}")
    print()
    print("A meaning-preserving rewrite must not change the decision at all;")
    print("every flip above is an invariance violation on held-out data.")

    (OUT / "c3_phrasing_comparison.json").write_text(json.dumps({
        "n_shared": len(shared),
        "n_flips": len(flips),
        "flip_rate": round(len(flips)/len(shared), 4),
        "accuracy_hypothesis_pct": round(100*a_correct/len(shared), 1),
        "accuracy_qform_pct": round(100*q_correct/len(shared), 1),
        "transitions": {f"{x}->{y}": n for (x, y), n in transitions.items()},
        "unsafe_created_by_rewording": unsafe_created,
        "unsafe_removed_by_rewording": unsafe_removed,
        "flipped_ids": flips,
    }, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT/'c3_phrasing_comparison.json'}")


if __name__ == "__main__":
    main()
