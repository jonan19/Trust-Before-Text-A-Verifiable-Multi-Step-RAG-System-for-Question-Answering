"""
merged_corpora_test.py: does the frozen system still behave when both corpora
share one index?

Builds ONE Qdrant store from the 11 Corpus 1 documents and the 11 Corpus 2
documents (22 documents), then runs each corpus's own 78 queries against it
under the unchanged configuration and compares with the single-corpus runs.
Cross-corpus interference is the point: the two organisations' policies overlap
in topic (for example password rules), so a genuine disagreement between them
can fire. Zero LLM tokens. Evaluation-only code: no pipeline file is touched,
and the existing stores are not modified (new folders data_merged/ and
qdrant_db_merged/, both regenerable and gitignored).

    python evaluation/merged_corpora_test.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import harness_bootstrap  # noqa: F401
import harness
from run_info import run_info

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
MERGED_DATA = ROOT / "data_merged"
MERGED_STORE = "qdrant_db_merged"
KS = (1, 3, 5, 10, 30)


def refuse_if_overridden() -> None:
    overrides = {k: v for k, v in os.environ.items() if k.startswith("RAG_")}
    if overrides:
        raise SystemExit(f"Refusing to run: RAG_* overrides are set {overrides}. "
                         "This test runs under the default configuration only.")


def build_merged_data() -> list[str]:
    MERGED_DATA.mkdir(exist_ok=True)
    names = []
    for src in (ROOT / "data", ROOT / "data_corpus2"):
        for f in sorted(src.glob("*.docx")):
            dst = MERGED_DATA / f.name
            if dst.exists() and dst.stat().st_size != f.stat().st_size:
                raise SystemExit(f"name collision with different content: {f.name}")
            shutil.copy2(f, dst)
            names.append(f.name)
    if len(names) != len(set(names)):
        raise SystemExit("duplicate document names across the two corpora")
    return names


def ingest() -> int:
    import qdrant_retrieval
    qdrant_retrieval._close_client()
    return qdrant_retrieval.ingest_documents(
        data_dir=MERGED_DATA, qdrant_dir=ROOT / MERGED_STORE, force=True)


def recall_rows(orchestrator, queries: list[dict]) -> list[dict]:
    from retrieval_interface import retrieve
    rows = []
    for q in queries:
        gold = set(q.get("expected_sources") or [])
        if not gold:
            continue
        ranked = [c.get("source") for c in retrieve(
            orchestrator.preprocess_query(q["query"]), top_k=orchestrator.RETRIEVAL_TOP_K)]
        rows.append({"id": q["id"], "all_gold": {k: gold <= set(ranked[:k]) for k in KS}})
    return rows


def main() -> None:
    refuse_if_overridden()
    names = build_merged_data()
    print(f"merged documents: {len(names)}")
    n_chunks = ingest()
    print(f"chunks in merged store: {n_chunks}")

    import qdrant_retrieval
    qdrant_retrieval._close_client()
    qdrant_retrieval._published_registry_dir = None
    harness.CORPORA["merged"] = {"data": ROOT / "data", "qdrant": MERGED_STORE}
    orchestrator = harness.setup("merged")

    out = {"meta": {"documents": len(names), "chunks": n_chunks, "store": MERGED_STORE},
           "run_info": run_info(), "corpora": {}}
    for corpus in ("1", "2"):
        queries = harness.load_queries(corpus)
        records = harness.run_queries(orchestrator, queries, progress=False)
        m = harness.metrics(records)
        base_path = HERE / "results" / f"rerun_corpus{corpus}.json"
        base = {r["id"]: r["observed"] for r in json.loads(
            base_path.read_text(encoding="utf-8"))["results"]} if base_path.exists() else {}
        changed = [{"id": r["id"], "expected": r["expected"], "single_corpus": base.get(r["id"]),
                    "merged": r["observed"]} for r in records
                   if base and base.get(r["id"]) != r["observed"]]
        rec = recall_rows(orchestrator, queries)
        out["corpora"][corpus] = {
            "metrics": {k: v for k, v in m.items() if not isinstance(v, list)},
            "misattributed": m["misattributed"], "false_conflicts": m["false_conflicts"],
            "changed_vs_single_corpus": changed,
            "recall_all_gold_at_k": {k: sum(r["all_gold"][k] for r in rec) for k in KS},
            "recall_n": len(rec),
        }
        print(f"\ncorpus {corpus} queries on the merged index: accuracy {m['accuracy']}/{m['n']} "
              f"({m['accuracy_pct']}%), conflict recall {m['conflict_tp']}/{m['conflict_true']}, "
              f"precision {m['conflict_precision']}, unsafe {m['unsafe_answers']}, gap leaks {m['gap_leak_count']}")
        print(f"  gold documents all in top-5: {out['corpora'][corpus]['recall_all_gold_at_k'][5]}/{len(rec)}")
        print(f"  decisions changed vs the single-corpus run: {len(changed)}")
        for c in changed:
            print(f"    {c['id']}: expected {c['expected']}, single {c['single_corpus']} -> merged {c['merged']}")

    path = HERE / "results" / "merged_corpora.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWrote {path}")


if __name__ == "__main__":
    main()
