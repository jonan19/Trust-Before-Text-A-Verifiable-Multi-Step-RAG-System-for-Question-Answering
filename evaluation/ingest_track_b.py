"""
ingest_track_b.py — Convert the delivered Track B question set into per-bundle
harness files.

Input:  corpus3_queries_combined.json  (30 bundles x 8 questions)
Output: data_corpus3/<bundle>/queries_open.json       (harness query schema)
        data_corpus3/<bundle>/gold_spans_open.json    (author quotes -> offsets)

Track B authorship is LLM-generated, not the human blind protocol originally
frozen. See docs/PREREGISTRATION_CORPUS3.md, Amendment 1 (2026-08-28), recorded
before the test run. This script does not judge that; it only converts.

Gold spans come from the author's verbatim quotes, resolved to true character
offsets by the same source-anchored search span_attribution.py uses, so Track B
attribution is graded on exactly the same footing as Track A.

    python evaluation/ingest_track_b.py
    python evaluation/ingest_track_b.py --check   # validate only, write nothing
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import harness_bootstrap  # noqa: F401  (adds this dir to sys.path)
from span_attribution import load_documents, resolve_subspan

ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = ROOT / "data_corpus3"
SOURCE = ROOT / "corpus3_queries_combined.json"

VALID_DECISIONS = {"answer", "conflict", "insufficient"}


def conflict_pair(question: dict) -> list | None:
    """
    The two documents the author says disagree.

    Track A derives this from ContractNLI's Entailment/Contradiction split. Here
    the author names the sources directly; a conflict needs at least two, and the
    pair is the two lowest-sorted filenames so the gold value is deterministic
    and comparable with harness.conflict_pair()'s sorted output.
    """
    if question["decision"] != "conflict":
        return None
    sources = sorted(question.get("sources") or [])
    return sources[:2] if len(sources) >= 2 else None


def build(write: bool) -> None:
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    bundles = payload["bundles"]

    problems: list[str] = []
    counts = {"answer": 0, "conflict": 0, "insufficient": 0}
    n_queries = 0
    n_spans = 0

    for entry in bundles:
        name = entry["bundle"]
        bundle_dir = DATA_ROOT / name
        if not bundle_dir.is_dir():
            problems.append(f"{name}: no such bundle directory")
            continue

        documents = load_documents(name)
        cache: dict = {}
        records = []
        spans_out: dict = {}

        for i, question in enumerate(entry["questions"], 1):
            qid = f"{name}-open-{i:02d}"
            decision = question["decision"]
            if decision not in VALID_DECISIONS:
                problems.append(f"{qid}: bad decision {decision!r}")
                continue

            sources = sorted(question.get("sources") or [])
            for src in sources:
                if src not in documents:
                    problems.append(f"{qid}: source {src} not in bundle")

            # An `insufficient` question asserts the documents do NOT address it,
            # so naming supporting sources is contradictory. Flag rather than
            # silently accept -- it means the author mislabelled.
            if decision == "insufficient" and sources:
                problems.append(f"{qid}: insufficient but names sources {sources}")
            if decision in ("answer", "conflict") and not sources:
                problems.append(f"{qid}: {decision} but names no source")

            pair = conflict_pair(question)
            if decision == "conflict" and pair is None:
                problems.append(f"{qid}: conflict with fewer than 2 sources")

            records.append({
                "id": qid,
                "category": "track-b/open",
                "query": question["question"],
                "expected_decision": decision,
                "expected_sources": sources,
                "expected_conflict_pair": pair,
                "expected_answer_or_key_facts": (question.get("notes") or "").strip(),
                "trace": "track-b",
                "note": "LLM-authored; see PREREGISTRATION_CORPUS3.md Amendment 1",
            })
            n_queries += 1
            counts[decision] += 1

            # Resolve each verbatim quote to true character offsets.
            per_source: dict = {}
            for src, quote in (question.get("quotes") or {}).items():
                hit = resolve_subspan(src, quote, documents, cache)
                if hit is None:
                    problems.append(f"{qid}: quote does not resolve in {src}")
                    continue
                _, start, end = hit
                per_source.setdefault(src, []).append([start, end])
                n_spans += 1
            if per_source:
                spans_out[qid] = per_source

        if write:
            (bundle_dir / "queries_open.json").write_text(
                json.dumps({
                    "_track": "B",
                    "_authorship": "LLM-generated, no project context; see "
                                   "docs/PREREGISTRATION_CORPUS3.md Amendment 1",
                    "queries": records,
                }, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            (bundle_dir / "gold_spans_open.json").write_text(
                json.dumps(spans_out, indent=2, ensure_ascii=False), encoding="utf-8"
            )

    print(f"bundles processed : {len(bundles)}")
    print(f"queries           : {n_queries}")
    print(f"gold spans        : {n_spans}")
    print(f"gold distribution : {counts}")
    total = sum(counts.values())
    if total:
        print(f"always-answer floor: {100 * counts['answer'] / total:.1f}%")
    print(f"problems          : {len(problems)}")
    for p in problems[:25]:
        print(f"  - {p}")
    if write and not problems:
        print("\nWrote queries_open.json + gold_spans_open.json per bundle.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="validate only")
    args = ap.parse_args()
    build(write=not args.check)


if __name__ == "__main__":
    main()
