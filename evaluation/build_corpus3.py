"""
build_corpus3.py — Build Corpus 3 (ContractNLI) bundles and their Qdrant stores.

Corpus 3 is the project's first held-out data. See docs/PREREGISTRATION_CORPUS3.md
for the governance rules; the short version is that the `test` split is opened
exactly once and never used to select anything.

What this builds
----------------
ContractNLI annotates 17 fixed hypotheses per contract as Entailment /
Contradiction / NotMentioned. That is a hypothesis-vs-document relation, which is
NOT what this project's Stage 4 detects — Stage 4 finds document-vs-document
self-contradiction.

Bundling converts one into the other. Put K=4 real NDAs in a single store and ask
one hypothesis. If annotators marked document A `Entailment` and document B
`Contradiction`, those two documents genuinely disagree about that proposition,
and the disagreement was certified by people who never saw this system. Stage 4
skips same-source pairs (validation.py:1701), so cross-document is exactly the
shape it looks for.

    >=1 Entailment and >=1 Contradiction  ->  expected_decision = "conflict"
    all four NotMentioned                 ->  expected_decision = "insufficient"
    otherwise                             ->  expected_decision = "answer"

Layout produced
---------------
    data_corpus3/
      bundles.json
      {dev,test}-bNN/
        nda_<id>.txt   x4        verbatim doc['text']
        queries.json             17 hypothesis-verbatim queries (primary)
        queries_qform.json       17 frozen interrogative rewrites (variant B)
        gold_spans.json          query id -> {source: [[start, end], ...]}
        chunk_offsets.json       chunk fingerprint -> {source, start, end}
    qdrant_db_c3/{dev,test}-bNN/

Usage
-----
    python evaluation/build_corpus3.py --split dev
    python evaluation/build_corpus3.py --split dev --verify-only
    python evaluation/build_corpus3.py --split test --bundles test-b00,test-b01
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from pathlib import Path

import harness_bootstrap  # noqa: F401  (adds this dir to sys.path)

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA_ROOT = ROOT / "data_corpus3"
QDRANT_ROOT = ROOT / "qdrant_db_c3"

# Downloads/contract-nli/contract-nli, i.e. a sibling of the "Final Proj" folder.
DEFAULT_CONTRACTNLI = ROOT.parent.parent / "contract-nli" / "contract-nli"

# ── Frozen construction parameters ──────────────────────────────────────
# Committed in docs/PREREGISTRATION_CORPUS3.md. Changing any of these after the
# test split has been opened invalidates the held-out claim.
BUNDLE_SIZE = 4
SEED = 0

# Chunker settings must match ingestion._iter_document_chunks exactly, or the
# chunk_offsets sidecar will not resolve the chunks retrieval actually returns.
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


# ── Variant B: frozen interrogative rewrites ────────────────────────────
# Written once, from each hypothesis' `short_description` + `hypothesis` text
# alone, BEFORE any evaluation run. The SHA-256 of this table is recorded in
# each queries_qform.json and in the pre-registration.
#
# Polarity is not preserved and does not need to be: grading is over the
# decision (answer / conflict / insufficient), not over the answer's content.
# "Does the Agreement grant a licence?" and "Is a licence withheld?" must both
# reach `answer` on a contract that addresses licensing.
QFORM = {
    "nda-1":  "Must the Disclosing Party expressly identify all Confidential Information?",
    "nda-2":  "Is Confidential Information limited to technical information only?",
    "nda-3":  "Can Confidential Information include information that was conveyed verbally?",
    "nda-4":  "Is the Receiving Party restricted to using Confidential Information only for the purposes stated in the Agreement?",
    "nda-5":  "May the Receiving Party share Confidential Information with its own employees?",
    "nda-7":  "May the Receiving Party share Confidential Information with third parties such as consultants, agents or professional advisors?",
    "nda-8":  "Must the Receiving Party notify the Disclosing Party if it is required by law or judicial process to disclose Confidential Information?",
    "nda-10": "Is the Receiving Party prohibited from disclosing that the Agreement was agreed or negotiated?",
    "nda-11": "Is the Receiving Party prohibited from reverse engineering objects that embody Confidential Information?",
    "nda-12": "May the Receiving Party independently develop information similar to the Confidential Information?",
    "nda-13": "May the Receiving Party acquire information similar to the Confidential Information from a third party?",
    "nda-15": "Does the Agreement grant the Receiving Party any right or licence to the Confidential Information?",
    "nda-16": "Must the Receiving Party return or destroy Confidential Information when the Agreement terminates?",
    "nda-17": "May the Receiving Party make copies of Confidential Information?",
    "nda-18": "Is the Receiving Party prohibited from soliciting the Disclosing Party's representatives or employees?",
    "nda-19": "Do any obligations under the Agreement survive its termination?",
    "nda-20": "May the Receiving Party retain any Confidential Information after the required return or destruction?",
}


def qform_hash() -> str:
    """SHA-256 of the frozen rewrite table, recorded so drift is detectable."""
    payload = json.dumps(QFORM, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ── Bundle construction ─────────────────────────────────────────────────

def load_split(contractnli_dir: Path, split: str) -> dict:
    path = contractnli_dir / f"{split}.json"
    if not path.exists():
        raise SystemExit(f"ContractNLI {split}.json not found at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def make_bundles(payload: dict, split: str) -> list[dict]:
    """
    Partition a split's documents into disjoint bundles of BUNDLE_SIZE.

    Ordering is fully determined: sort by document id, then shuffle under SEED.
    Sorting first matters — dict/JSON order is not a stable basis for a seeded
    shuffle across runs or Python versions.
    """
    by_id = {doc["id"]: doc for doc in payload["documents"]}
    ids = sorted(by_id)
    rng = random.Random(SEED)
    rng.shuffle(ids)

    n_bundles = len(ids) // BUNDLE_SIZE
    dropped = ids[n_bundles * BUNDLE_SIZE:]

    bundles = []
    for b in range(n_bundles):
        member_ids = ids[b * BUNDLE_SIZE:(b + 1) * BUNDLE_SIZE]
        bundles.append({
            "name": f"{split}-b{b:02d}",
            "documents": [by_id[i] for i in member_ids],
        })
    return bundles, dropped


def doc_filename(doc: dict) -> str:
    """
    Deterministic on-disk name.

    ContractNLI `file_name` values carry .pdf/.htm suffixes on what is really
    plain text, and at least one contains spaces. The document id is stable
    across all three splits, so it is the safer key.
    """
    return f"nda_{doc['id']}.txt"


def derive_gold(bundle_docs: list[dict], hypothesis_key: str) -> dict:
    """Aggregate per-document annotator choices into one bundle-level gold label."""
    entail, contra, mentioned = [], [], []
    for doc in bundle_docs:
        ann = doc["annotation_sets"][0]["annotations"].get(hypothesis_key)
        if ann is None:
            continue
        choice = ann["choice"]
        if choice == "Entailment":
            entail.append(doc)
            mentioned.append(doc)
        elif choice == "Contradiction":
            contra.append(doc)
            mentioned.append(doc)

    if entail and contra:
        decision = "conflict"
        # The pair is the two documents that actually disagree. When several
        # documents sit on each side, the lowest-id representative of each side
        # is chosen so the gold pair is deterministic.
        a = min(entail, key=lambda d: d["id"])
        b = min(contra, key=lambda d: d["id"])
        pair = sorted([doc_filename(a), doc_filename(b)])
    elif not mentioned:
        decision = "insufficient"
        pair = None
    else:
        decision = "answer"
        pair = None

    return {
        "decision": decision,
        "pair": pair,
        "sources": sorted(doc_filename(d) for d in mentioned),
    }


def gold_spans_for(bundle_docs: list[dict], hypothesis_key: str) -> dict:
    """Gold evidence spans as character offsets, keyed by on-disk filename."""
    out = {}
    for doc in bundle_docs:
        ann = doc["annotation_sets"][0]["annotations"].get(hypothesis_key)
        if not ann or not ann.get("spans"):
            continue
        offsets = [list(doc["spans"][i]) for i in ann["spans"]]
        if offsets:
            out[doc_filename(doc)] = offsets
    return out


def build_query_records(bundle: dict, labels: dict, *, qform: bool) -> list[dict]:
    """17 queries in the existing data/queries.json schema."""
    records = []
    for key in sorted(labels, key=lambda k: int(k.split("-")[1])):
        gold = derive_gold(bundle["documents"], key)
        records.append({
            "id": f"{bundle['name']}-{key}",
            "category": f"contractnli/{labels[key]['short_description']}",
            "query": QFORM[key] if qform else labels[key]["hypothesis"],
            "expected_decision": gold["decision"],
            "expected_sources": gold["sources"],
            "expected_conflict_pair": gold["pair"],
            "expected_answer_or_key_facts": labels[key]["short_description"],
            "trace": key,
            "note": "",
        })
    return records


# ── Offset integrity and chunk sidecar ──────────────────────────────────

def write_documents(bundle: dict, bundle_dir: Path) -> None:
    """
    Write each document's text VERBATIM.

    newline="" suppresses Windows CRLF translation. Without it every character
    offset past the first newline shifts, and gold span grading silently
    degrades into noise rather than failing loudly.
    """
    for doc in bundle["documents"]:
        path = bundle_dir / doc_filename(doc)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(doc["text"])


def verify_offsets(bundle: dict, bundle_dir: Path) -> list[str]:
    """
    Assert the round trip: file content == doc['text'], and every gold span
    slices to the same substring on disk as it does in the source JSON.

    Returns a list of problems; empty means clean.
    """
    problems = []
    for doc in bundle["documents"]:
        path = bundle_dir / doc_filename(doc)
        with open(path, "r", encoding="utf-8", newline="") as fh:
            on_disk = fh.read()
        if on_disk != doc["text"]:
            problems.append(
                f"{path.name}: content differs from doc['text'] "
                f"({len(on_disk)} chars on disk vs {len(doc['text'])} in JSON)"
            )
            continue
        for idx, (start, end) in enumerate(doc["spans"]):
            if doc["text"][start:end] != on_disk[start:end]:
                problems.append(f"{path.name}: span {idx} slices differently on disk")
                break
    return problems


def build_chunk_offsets(bundle: dict, bundle_dir: Path) -> dict:
    """
    Map every chunk the ingest path will produce back to its character offsets.

    Replays the SAME chunker ingestion._iter_document_chunks uses, then locates
    each chunk in the source text. FixedChunker slices text[start:end] and only
    .strip()s the result, so chunks are verbatim substrings and str.find is
    exact. Keyed by qdrant_retrieval.chunk_fingerprint so a chunk coming back
    from retrieval can be resolved without touching the ingest path at all.
    """
    from document_preprocessing import DocumentChunker
    import qdrant_retrieval

    chunker = DocumentChunker(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    offsets = {}
    unresolved = 0

    for doc in bundle["documents"]:
        name = doc_filename(doc)
        text = doc["text"]
        # Search forward from the previous chunk's start so that a short chunk
        # appearing twice in a document resolves to the right occurrence.
        cursor = 0
        for chunk in chunker.chunk_document(text, source_document=name):
            start = text.find(chunk.text, cursor)
            if start < 0:
                start = text.find(chunk.text)
            if start < 0:
                unresolved += 1
                continue
            offsets[qdrant_retrieval.chunk_fingerprint(chunk.text)] = {
                "source": name,
                "start": start,
                "end": start + len(chunk.text),
            }
            cursor = start

    if unresolved:
        print(f"    WARNING: {unresolved} chunk(s) could not be located in source text")
    return offsets


# ── Per-bundle build ────────────────────────────────────────────────────

def write_bundle(bundle: dict, labels: dict) -> list[str]:
    """Write every artifact for one bundle. Returns offset-integrity problems."""
    bundle_dir = DATA_ROOT / bundle["name"]
    bundle_dir.mkdir(parents=True, exist_ok=True)

    write_documents(bundle, bundle_dir)
    problems = verify_offsets(bundle, bundle_dir)
    if problems:
        return problems

    (bundle_dir / "queries.json").write_text(
        json.dumps({"queries": build_query_records(bundle, labels, qform=False)},
                   indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (bundle_dir / "queries_qform.json").write_text(
        json.dumps({
            "_qform_sha256": qform_hash(),
            "_note": "Frozen interrogative rewrites. See build_corpus3.QFORM.",
            "queries": build_query_records(bundle, labels, qform=True),
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    spans = {
        f"{bundle['name']}-{key}": gold_spans_for(bundle["documents"], key)
        for key in labels
    }
    (bundle_dir / "gold_spans.json").write_text(
        json.dumps(spans, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    (bundle_dir / "chunk_offsets.json").write_text(
        json.dumps(build_chunk_offsets(bundle, bundle_dir), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return []


def ingest_bundle(name: str) -> int:
    """
    Build one bundle's Qdrant store.

    _close_client() first, every time: qdrant_retrieval._get_client caches a
    single module-global client and IGNORES the qdrant_dir argument once one is
    open (qdrant_retrieval.py:118). Without this reset, bundle 2..N would be
    written into bundle 1's store, silently and without error.
    """
    import qdrant_retrieval

    qdrant_retrieval._close_client()
    return qdrant_retrieval.ingest_documents(
        data_dir=DATA_ROOT / name,
        qdrant_dir=QDRANT_ROOT / name,
    )


def store_artifacts_ok(name: str) -> list[str]:
    """The four files harness.setup() publishes to Stage 0 must all exist."""
    store = QDRANT_ROOT / name
    required = ["manifest.json", "chunk_registry.json", "corpus_stats.json",
                "sparse_encoder.json"]
    return [f for f in required if not (store / f).exists()]


# ── Entry point ─────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test"], required=True)
    ap.add_argument("--contractnli", type=Path, default=DEFAULT_CONTRACTNLI)
    ap.add_argument("--bundles", help="comma-separated bundle names (default: all)")
    ap.add_argument("--verify-only", action="store_true",
                    help="write files and check offset integrity; do not ingest")
    ap.add_argument("--skip-existing", action="store_true",
                    help="skip bundles whose store already has all Stage 0 artifacts")
    args = ap.parse_args()

    if args.split == "test":
        print("\n  *** TEST SPLIT — held-out data. See docs/PREREGISTRATION_CORPUS3.md.")
        print("  *** Debug on --split dev. The test split is opened once.\n")

    payload = load_split(args.contractnli, args.split)
    labels = payload["labels"]
    bundles, dropped = make_bundles(payload, args.split)

    if args.bundles:
        wanted = {s.strip() for s in args.bundles.split(",")}
        bundles = [b for b in bundles if b["name"] in wanted]

    print(f"ContractNLI {args.split}: {len(payload['documents'])} documents "
          f"-> {len(bundles)} bundles of {BUNDLE_SIZE} ({len(dropped)} dropped)")

    # Class distribution, computed from labels alone — no system involved.
    counts = {"answer": 0, "conflict": 0, "insufficient": 0}
    for bundle in bundles:
        for key in labels:
            counts[derive_gold(bundle["documents"], key)["decision"]] += 1
    total = sum(counts.values())
    print(f"  gold: {counts}  (n={total})")
    if total:
        print(f"  always-answer floor: {100 * counts['answer'] / total:.1f}%")

    DATA_ROOT.mkdir(parents=True, exist_ok=True)

    all_problems = []
    for i, bundle in enumerate(bundles, 1):
        print(f"\n[{i}/{len(bundles)}] {bundle['name']}")
        problems = write_bundle(bundle, labels)
        if problems:
            all_problems.extend(problems)
            for p in problems:
                print(f"    OFFSET INTEGRITY FAILURE: {p}")
            continue
        print("    offsets verified, artifacts written")

        if args.verify_only:
            continue
        if args.skip_existing and not store_artifacts_ok(bundle["name"]):
            print("    store already complete, skipping ingest")
            continue

        t0 = time.time()
        count = ingest_bundle(bundle["name"])
        missing = store_artifacts_ok(bundle["name"])
        status = f"MISSING {missing}" if missing else "ok"
        print(f"    ingested {count} chunks in {time.time() - t0:.1f}s [{status}]")

    manifest_path = DATA_ROOT / "bundles.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest.setdefault("construction", {
        "bundle_size": BUNDLE_SIZE, "seed": SEED,
        "chunk_size": CHUNK_SIZE, "chunk_overlap": CHUNK_OVERLAP,
        "qform_sha256": qform_hash(),
    })
    manifest.setdefault("splits", {})[args.split] = {
        "n_documents": len(payload["documents"]),
        "dropped_ids": dropped,
        "gold_counts": counts,
        "bundles": {
            b["name"]: [{"id": d["id"], "file_name": d["file_name"],
                         "on_disk": doc_filename(d)} for d in b["documents"]]
            for b in bundles
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                             encoding="utf-8")
    print(f"\nWrote {manifest_path}")

    if all_problems:
        raise SystemExit(f"\n{len(all_problems)} offset-integrity failure(s). "
                         "Nothing downstream is meaningful until these are fixed.")


if __name__ == "__main__":
    main()
