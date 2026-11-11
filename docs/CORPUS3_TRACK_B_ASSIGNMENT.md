# Corpus 3, Track B: question authoring assignment

Provenance record for Corpus 3 (ContractNLI). It states who authored the
questions and gold labels for which document bundles, and under what
instructions.

This matters because it is the basis of the project's one external-validity
claim: per `claude.md` Standing Decision 3, the value of Corpus 3 is that the
**questions and gold labels were authored by someone other than this project,
without seeing the system's output.** That claim rests on this assignment, so it
is recorded here rather than implied by a directory layout.

## Assignment

Each author received 10 bundles of 4 NDAs each, 40 documents per author, 120
documents in total across 30 bundles.

| Author | Bundles | Documents |
|---|---|---|
| Anish | `test-b00` through `test-b09` | 40 |
| Kaustubh | `test-b10` through `test-b19` | 40 |
| Jonan | `test-b20` through `test-b29` | 40 |

The bundles themselves are in `data_corpus3/<bundle>/`, which is the canonical
location. The documents are from the ContractNLI corpus and were not authored by
this project.

## Instructions given

All three authors worked from the same document:
[CORPUS3_AUTHORING_PROTOCOL.md](CORPUS3_AUTHORING_PROTOCOL.md).

## What was delivered back

The authored questions and gold labels came back as
`corpus3_queries_combined.json` (repo root), which
`evaluation/ingest_track_b.py` converts into per-bundle
`data_corpus3/<bundle>/queries_open.json` and `gold_spans_open.json`.

## Note on the former `track_b_handoff/` directory

The handoff packets were originally staged in `track_b_handoff/<author>/`, one
copy of each assigned NDA plus one copy of the authoring protocol per author.
That directory was removed on 2026-11-11: it was the **outbound** packet and
held no authored output, and all 120 of its `.txt` files were verified
byte-identical to the copies already in `data_corpus3/`. The only information
unique to it was the assignment above, which this file now records. The original
directory remains in git history.
