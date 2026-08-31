"""
span_attribution.py — Grade Corpus 3 citations against ContractNLI's gold spans.

Why this exists
---------------
This project's claim is verifiability, not accuracy, and docs/STATUS.md already
records the failure it is most exposed to: "right decision, wrong evidence" — the
system abstains for `conflict` with a correct verdict while citing a pair
unrelated to the question. `harness.metrics()` catches that for Corpus 1/2 by
comparing against `expected_conflict_pair`, but those gold pairs were written by
this project.

ContractNLI ships gold evidence spans as character offsets, annotated by people
who never saw this system. This module grades citations against them, which makes
these the first externally validated evidence claims the project has.

How a chunk becomes character offsets
-------------------------------------
Retrieval returns chunk TEXT, not offsets. build_corpus3.py wrote a sidecar,
chunk_offsets.json, mapping qdrant_retrieval.chunk_fingerprint(text) ->
{source, start, end}, produced by replaying the same chunker the ingest path
uses. A chunk coming back from the pipeline is therefore resolved by fingerprint,
with no change to the ingest path and no fuzzy matching.

Metrics
-------
  evidence_recall     gold spans covered by at least one validated chunk
  evidence_precision  validated chunks overlapping at least one gold span
  external_attribution_precision   (primary)
                      of conflict reports, the fraction whose two cited chunks
                      each overlap a gold span AND land in the two documents
                      ContractNLI names as disagreeing

A chunk that cannot be resolved by fingerprint is counted in `unresolved` rather
than silently scored. A high unresolved rate means the offset sidecar diverged
from the ingest path — a build problem, not a retrieval result.

Usage
-----
    python evaluation/span_attribution.py --tag dev_smoke --split dev
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import harness_bootstrap  # noqa: F401  (adds this dir to sys.path)

ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = ROOT / "data_corpus3"
OUT_DIR = Path(__file__).resolve().parent / "results"


GOLD_SPANS = {
    "A": "gold_spans.json",       # ContractNLI annotator spans
    "B": "gold_spans_open.json",  # Track B author quotes, resolved to offsets
}


def load_sidecars(bundle: str, track: str = "A") -> tuple[dict, dict]:
    """
    (gold_spans, chunk_offsets) for one bundle, keyed as written by the builder.

    `track` selects which gold file to grade against. Track A uses ContractNLI's
    own annotator spans; Track B uses the question author's verbatim quotes,
    resolved to true offsets by evaluation/ingest_track_b.py. Both are graded by
    identical logic below, so the two tracks are directly comparable.
    """
    bundle_dir = DATA_ROOT / bundle.removeprefix("3-")
    gold = json.loads((bundle_dir / GOLD_SPANS[track]).read_text(encoding="utf-8"))
    offsets = json.loads((bundle_dir / "chunk_offsets.json").read_text(encoding="utf-8"))
    return gold, offsets


def resolve(text: str, offsets: dict):
    """Chunk text -> (source, start, end) via its fingerprint, or None."""
    import qdrant_retrieval
    text = (text or "").strip()
    if not text:
        return None
    hit = offsets.get(qdrant_retrieval.chunk_fingerprint(text))
    if hit is None:
        return None
    return hit["source"], hit["start"], hit["end"]


def load_documents(bundle: str) -> dict:
    """
    {filename: full text} for one bundle, read exactly as it was written.

    newline="" matters: the builder wrote these verbatim so ContractNLI's gold
    character offsets line up. Reading with newline translation on would shift
    every offset past the first line break.
    """
    bundle_dir = DATA_ROOT / bundle.removeprefix("3-")
    docs = {}
    for path in sorted(bundle_dir.glob("*.txt")):
        with open(path, "r", encoding="utf-8", newline="") as fh:
            docs[path.name] = fh.read()
    return docs


def _normalise_with_map(text: str):
    """
    Collapse runs of whitespace to a single space, keeping an index back to the
    original string so a match can be reported in TRUE character offsets.

    Returns (normalised_text, index_map) where index_map[i] is the position in
    `text` that normalised_text[i] came from.
    """
    out = []
    index_map = []
    prev_space = False
    for i, ch in enumerate(text):
        if ch.isspace():
            if prev_space:
                continue
            out.append(" ")
            index_map.append(i)
            prev_space = True
        else:
            out.append(ch)
            index_map.append(i)
            prev_space = False
    return "".join(out), index_map


def resolve_subspan(source: str, text: str, documents: dict, cache: dict):
    """
    Locate a conflict span inside its own source document.

    Conflict spans are query-relevant SUB-SPANS of a chunk, not whole chunks
    (validation.py:1803-1807), so chunk_fingerprint cannot match them. The span
    is copied out of the document, so an exact string search resolves it — but
    the extractor collapses newlines to spaces, so an exact search misses any
    span that crossed a line break in the source. Measured on the dev split:
    10 of 52 spans, all of them multi-line.

    So: exact search first, then a whitespace-normalised search whose result is
    mapped back to true offsets. Still no fuzzy matching — normalised equality
    is exact equality up to whitespace, which is the only thing that differs.
    """
    body = documents.get(source)
    if body is None:
        return None
    needle = (text or "").strip()
    if not needle:
        return None

    start = body.find(needle)
    if start >= 0:
        return source, start, start + len(needle)

    if source not in cache:
        cache[source] = _normalise_with_map(body)
    norm_body, index_map = cache[source]
    norm_needle = " ".join(needle.split())
    if not norm_needle:
        return None

    pos = norm_body.find(norm_needle)
    if pos < 0:
        return None
    true_start = index_map[pos]
    true_end = index_map[pos + len(norm_needle) - 1] + 1
    return source, true_start, true_end


def overlaps(start: int, end: int, spans: list) -> bool:
    """True when [start, end) intersects any gold span."""
    return any(start < s_end and s_start < end for s_start, s_end in spans)


def grade(records: list, track: str = "A") -> dict:
    """Grade every record that has gold evidence."""
    sidecars: dict = {}

    gold_total = gold_hit = 0
    chunks_total = chunks_hit = unresolved = 0
    conflict_reports = conflict_correct = 0
    graded = 0
    detail = []
    unresolved_spans = []

    for rec in records:
        bundle = rec.get("bundle")
        if not bundle:
            continue
        if bundle not in sidecars:
            sidecars[bundle] = (*load_sidecars(bundle, track), load_documents(bundle), {})
        gold_spans, offsets, documents, norm_cache = sidecars[bundle]

        gold_for_query = gold_spans.get(rec["id"]) or {}
        if not gold_for_query:
            continue  # NotMentioned everywhere: no evidence to attribute
        graded += 1

        resolved = []
        for chunk in rec.get("evidence") or []:
            chunks_total += 1
            hit = resolve(chunk.get("text"), offsets)
            if hit is None:
                unresolved += 1
                continue
            resolved.append(hit)

        # Evidence precision: cited chunks that land on gold evidence.
        for source, start, end in resolved:
            if overlaps(start, end, gold_for_query.get(source, [])):
                chunks_hit += 1

        # Evidence recall: gold spans that a cited chunk actually covers.
        for source, spans in gold_for_query.items():
            for s_start, s_end in spans:
                gold_total += 1
                if any(src == source and s_start < end and start < s_end
                       for src, start, end in resolved):
                    gold_hit += 1

        # External attribution: the reported conflict pair, graded against gold.
        if rec["observed"] == "conflict":
            conflict_reports += 1
            expected_pair = rec.get("expected_conflict_pair")
            cited = []
            for chunk in rec.get("conflict_chunks") or []:
                hit = resolve_subspan(chunk.get("source"), chunk.get("text"),
                                      documents, norm_cache)
                if hit:
                    cited.append(hit)
                else:
                    unresolved_spans.append(rec["id"])
            pair_ok = False
            if expected_pair and len(cited) == 2:
                sources_ok = sorted({c[0] for c in cited}) == sorted(expected_pair)
                spans_ok = all(
                    overlaps(start, end, gold_for_query.get(src, []))
                    for src, start, end in cited
                )
                pair_ok = sources_ok and spans_ok
            if pair_ok:
                conflict_correct += 1
            else:
                detail.append({
                    "id": rec["id"],
                    "expected_pair": expected_pair,
                    "cited_sources": [c[0] for c in cited],
                })

    def ratio(num, den):
        return round(num / den, 4) if den else None

    scored_chunks = chunks_total - unresolved
    return {
        "graded_queries": graded,
        "evidence_recall": ratio(gold_hit, gold_total),
        "evidence_recall_n": f"{gold_hit}/{gold_total}",
        "evidence_precision": ratio(chunks_hit, scored_chunks),
        "evidence_precision_n": f"{chunks_hit}/{scored_chunks}",
        "external_attribution_precision": ratio(conflict_correct, conflict_reports),
        "external_attribution_n": f"{conflict_correct}/{conflict_reports}",
        "unresolved_conflict_spans": len(unresolved_spans),
        "unresolved_chunks": unresolved,
        "unresolved_rate": ratio(unresolved, chunks_total),
        "misattributed_detail": detail[:40],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--split", choices=["dev", "test"], default="dev")
    ap.add_argument("--track", choices=["A", "B"], default="A",
                    help="A = ContractNLI gold spans; B = Track B author quotes")
    args = ap.parse_args()

    path = OUT_DIR / f"{args.tag}_corpus3_{args.split}.json"
    if not path.exists():
        raise SystemExit(f"No result file at {path}. Run run_eval_corpus3.py first.")

    payload = json.loads(path.read_text(encoding="utf-8"))
    result = grade(payload["results"], track=args.track)

    out = OUT_DIR / f"{args.tag}_corpus3_{args.split}_attribution.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"=== span attribution / {args.tag} / {args.split} / track {args.track} ===")
    for key, value in result.items():
        if key == "misattributed_detail":
            continue
        print(f"  {key:32} {value}")

    rate = result["unresolved_rate"]
    if rate is not None and rate > 0.05:
        print(f"\n  WARNING: {rate:.1%} of chunks unresolved. The offset sidecar has "
              "diverged from the ingest path; rebuild before trusting these numbers.")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
