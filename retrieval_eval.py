"""
Retrieval comparison harness for ChromaDB vs Qdrant hybrid.

Run with:
    python main.py --compare-retrievers
    python retrieval_eval.py
"""

from __future__ import annotations

from dataclasses import dataclass

from retrieval_interface import retrieve
from validation import validate
from utils import print_separator


@dataclass(frozen=True)
class EvalQuery:
    query: str
    expected_section: str | tuple[str, ...] | None
    should_abstain: bool = False
    expected_source: str | None = None


EVAL_QUERIES: tuple[EvalQuery, ...] = (
    EvalQuery("What is the leave policy?", "Leave Policy"),
    EvalQuery("How many annual leave days can employees take?", "Leave Policy"),
    EvalQuery("What are the remote work eligibility rules?", "Remote Work Policy"),
    EvalQuery("When are salary reviews conducted?", "Compensation and Salary Reviews"),
    EvalQuery("How much can an Exceptional employee receive as merit increase?", "Compensation and Salary Reviews"),
    EvalQuery("What safety training is mandatory for new employees?", "Safety and Compliance Training"),
    EvalQuery("What gifts need written approval?", "Code of Conduct"),
    EvalQuery("What are the rules for expense reimbursement?", "Expense Reimbursement"),
    EvalQuery("How quickly are formal grievances acknowledged?", "Grievance Procedure"),
    EvalQuery("Compare leave policy and remote work policy", None),
    EvalQuery(
        "What was Tata Group revenue in 2024-25?",
        ("Page 7", "Page 22"),
        expected_source="Tata-Sons-Annual-Report-FY25.pdf",
    ),
    EvalQuery(
        "How many employees does the Tata Group have?",
        "Page 7",
        expected_source="Tata-Sons-Annual-Report-FY25.pdf",
    ),
    EvalQuery(
        "What was Tata Sons net worth in FY25?",
        "Page 20",
        expected_source="Tata-Sons-Annual-Report-FY25.pdf",
    ),
    EvalQuery(
        "What was Tata Group aggregate market capitalization in FY25?",
        "Page 21",
        expected_source="Tata-Sons-Annual-Report-FY25.pdf",
    ),
    EvalQuery(
        "What is the Tata Group net zero aspiration year?",
        "Page 14",
        expected_source="Tata-Sons-Annual-Report-FY25.pdf",
    ),
    EvalQuery(
        "How many NeuPass members does Tata Digital have?",
        "Page 12",
        expected_source="Tata-Sons-Annual-Report-FY25.pdf",
    ),
    EvalQuery(
        "What capacity is Agratas establishing in India and the UK?",
        "Page 11",
        expected_source="Tata-Sons-Annual-Report-FY25.pdf",
    ),
    EvalQuery(
        "Who are the non-executive directors on the Tata Sons Board?",
        "Page 24",
        expected_source="Tata-Sons-Annual-Report-FY25.pdf",
    ),
    EvalQuery("What is tomorrow's weather in Mumbai?", None, should_abstain=True),
    EvalQuery("Who won the World Cup?", None, should_abstain=True),
)


def _section_matches(section: str, expected: str | tuple[str, ...] | None) -> bool:
    if expected is None:
        return True
    expected_sections = (expected,) if isinstance(expected, str) else expected
    return any(item.lower() in section.lower() for item in expected_sections)


def _source_matches(source: str, expected: str | None) -> bool:
    if expected is None:
        return True
    return source == expected


def _evaluate_backend(query: EvalQuery, backend: str, top_k: int) -> dict:
    chunks = retrieve(query.query, top_k=top_k, backend=backend)
    validation = validate(chunks, query=query.query)
    top = chunks[0] if chunks else {}
    top_source = str(top.get("source", "(none)"))
    top_section = str(top.get("section", "(none)"))
    top_match = _section_matches(top_section, query.expected_section)
    source_match = _source_matches(top_source, query.expected_source)

    abstained = validation["abstention_reason"] is not None
    abstain_ok = abstained if query.should_abstain else not abstained

    return {
        "backend": backend,
        "chunks": chunks,
        "validation": validation,
        "top_source": top_source,
        "top_section": top_section,
        "top_match": top_match,
        "source_match": source_match,
        "abstain_ok": abstain_ok,
        "top_score": float(top.get("score", 0.0)),
        "top_relevance": float(top.get("relevance_score", 0.0)),
        "top_dense": float(top.get("dense_score", 0.0)),
        "top_sparse": float(top.get("sparse_score", 0.0)),
        "top_hybrid": float(top.get("hybrid_score", 0.0)),
    }


def _backend_points(result: dict, query: EvalQuery) -> tuple[int, int]:
    points = 0
    possible = 3
    if result["top_match"]:
        points += 1
    if query.expected_source is not None:
        possible += 1
        if result["source_match"]:
            points += 1
    if result["abstain_ok"]:
        points += 1
    if result["validation"]["relevant_count"] > 0 and not query.should_abstain:
        points += 1
    if result["validation"]["relevant_count"] == 0 and query.should_abstain:
        points += 1
    return points, possible


def run_comparison(top_k: int = 5) -> dict:
    """Run the fixed retrieval benchmark and print compact diagnostics."""
    backends = ("chroma", "qdrant")
    totals = {backend: 0 for backend in backends}
    max_totals = {backend: 0 for backend in backends}
    rows: list[dict] = []

    print_separator("Retrieval Comparison: ChromaDB vs Qdrant Hybrid", width=88)
    print(f"  Queries : {len(EVAL_QUERIES)}")
    print(f"  top_k   : {top_k}")
    print()

    for idx, query in enumerate(EVAL_QUERIES, start=1):
        print(f"{idx:02d}. {query.query}")
        expected = query.expected_section or "(abstain/multi-topic)"
        expected_source = f" source={query.expected_source}" if query.expected_source else ""
        print(f"    expected={expected}{expected_source}")

        query_results: dict[str, dict] = {}
        for backend in backends:
            result = _evaluate_backend(query, backend, top_k)
            points, possible = _backend_points(result, query)
            totals[backend] += points
            max_totals[backend] += possible
            query_results[backend] = result

            validation = result["validation"]
            extra = ""
            if backend == "qdrant":
                extra = (
                    f" dense={result['top_dense']:.4f}"
                    f" sparse={result['top_sparse']:.4f}"
                    f" hybrid={result['top_hybrid']:.4f}"
                )

            print(
                f"    {backend:<7} src={result['top_source']:<34} "
                f"top={result['top_section']:<26} "
                f"score={result['top_score']:.4f} "
                f"rel={result['top_relevance']:.4f} "
                f"valid={validation['relevant_count']} "
                f"reason={validation['abstention_reason'] or 'none':<12} "
                f"match={str(result['top_match']):<5} "
                f"source_ok={str(result['source_match']):<5} "
                f"abstain_ok={str(result['abstain_ok']):<5}"
                f"{extra}"
            )

        rows.append({"query": query.query, "results": query_results})
        print()

    print_separator("Comparison Summary", width=88)
    for backend in backends:
        print(f"  {backend:<7}: {totals[backend]}/{max_totals[backend]} points")

    if totals["qdrant"] > totals["chroma"]:
        verdict = "Qdrant hybrid performed better on this test set."
    elif totals["qdrant"] < totals["chroma"]:
        verdict = "ChromaDB performed better on this test set."
    else:
        verdict = "Both retrievers tied on this test set."
    print(f"  Verdict : {verdict}")
    print_separator(width=88)

    return {"totals": totals, "rows": rows, "verdict": verdict}


if __name__ == "__main__":
    run_comparison()
