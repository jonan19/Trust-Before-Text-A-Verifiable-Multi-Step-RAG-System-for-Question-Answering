"""
main.py — Entry point for the Trust Before Text RAG prototype (V3).

Usage:
    python main.py                      # runs all built-in demo queries
    python main.py "Your question here" # runs a single query from CLI

Set OPENAI_API_KEY environment variable to use a real LLM.
Without it, the mock LLM is used automatically.
"""

from __future__ import annotations

import sys

from orchestrator import run
from utils import print_separator


# ---------------------------------------------------------------------------
# Demo queries — exercise all V3 pipeline branches
# ---------------------------------------------------------------------------
DEMO_QUERIES: list[dict] = [
    {
        "query"    : "What is the leave policy?",
        "expected" : "abstain -- conflict  (corpus has 20-day AND 15-day leave chunks -> contradiction detected)",
    },
    {
        "query"    : "Compare leave policy and remote work policy",
        "expected" : "abstain -- conflict  (leave conflict detected across both sub-topic chunks)",
    },
    {
        "query"    : "How many days of leave are employees entitled to?",
        "expected" : "abstain -- conflict  (20 days vs 15 days, same section, numeric contradiction)",
    },
    {
        "query"    : "What is the company stock price?",
        "expected" : "abstain -- insufficient  (no relevant evidence in corpus)",
    },
    {
        "query"    : "When are salary reviews conducted?",
        "expected" : "proceed  (Stage 3 keeps only the compensation chunk, no conflict)",
    },
]


def main() -> None:
    if len(sys.argv) > 1:
        # Single query from command-line argument
        user_query = " ".join(sys.argv[1:])
        run(user_query, verbose=True)
        return

    # Run all demo queries
    print_separator("Trust Before Text — V3 RAG Demo", width=70)

    for idx, entry in enumerate(DEMO_QUERIES, start=1):
        query    = entry["query"]
        expected = entry["expected"]

        print(f"\n{'=' * 70}")
        print(f"  Demo {idx}/{len(DEMO_QUERIES)}")
        print(f"  Expected : {expected}")
        print(f"{'=' * 70}\n")

        result = run(query, verbose=True)

        # V3 summary line
        v = result["validation"]
        print(
            f"\n  [V3 Summary] "
            f"relevant={v['relevant_count']}  "
            f"conflict={v['conflict_flag']}  "
            f"sufficient={v['sufficiency_flag']}  "
            f"reason={v['abstention_reason'] or 'none'}  "
            f"confidence={v['confidence_score']:.4f}"
        )
        print()


if __name__ == "__main__":
    main()
