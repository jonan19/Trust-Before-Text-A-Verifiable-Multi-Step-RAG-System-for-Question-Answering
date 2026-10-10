"""
rank_gate_sweep.py — Re-calibrate MAX_CONFLICT_EVIDENCE_RANK after WS1.

The rank gate's cutoff of 4 was fitted against the pre-WS1 chunking. Sentence-
aligned overlap changes how many chunks a document contributes and therefore
where a given piece of evidence lands in the query's ranking: Corpus-1 Q076's
true conflict now sits at ranks 3 and 5, straddling the cliff.

Sweeps the gate over both corpora in one process (models load once) and reports
the safety-critical columns. Selection rule follows the project's existing
practice for QUERY_SPAN_RELEVANCE: take a value inside BOTH corpora's safe
windows rather than the best value for either.
"""
from __future__ import annotations

import json
from pathlib import Path

import harness_bootstrap  # noqa: F401
import validation
from harness import CORPORA, load_queries, metrics, run_queries, setup

VALUES = [3, 4, 5, 6, 8, 0]   # 0 = gate disabled
OUT = Path(__file__).resolve().parent / "results" / "rank_gate_sweep.json"


def main() -> None:
    rows: list[dict] = []
    for corpus in sorted(CORPORA):
        orch = setup(corpus)
        queries = load_queries(corpus)
        for val in VALUES:
            validation.MAX_CONFLICT_EVIDENCE_RANK = val
            m = metrics(run_queries(orch, queries, progress=False))
            rows.append({"corpus": corpus, "rank_gate": val, **m})
            print(f"  C{corpus} gate={val or 'off':>3}  "
                  f"acc={m['accuracy_pct']:5}  "
                  f"P={m['conflict_precision']:.4f} R={m['conflict_recall']:.4f} "
                  f"F1={m['conflict_f1']:.4f}  "
                  f"leaks={m['gap_leak_count']}  unsafe={m['unsafe_answers']}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
