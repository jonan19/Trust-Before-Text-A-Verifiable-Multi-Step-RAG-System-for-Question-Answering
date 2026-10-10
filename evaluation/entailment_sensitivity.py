"""
entailment_sensitivity.py — Can the faithfulness check separate legitimate
answer sentences from injected ones well enough to gate releases (Limitation 5)?

The release gate only works if genuine, evidence-grounded sentences pass it.
Replaying real recorded answers showed they do not: legitimate answers score
0.0-0.67. Before accepting or rejecting the gate, this measures whether the
weakness is in the premise construction rather than the idea, by scoring the
same sentences under four ways of presenting the evidence to the NLI model:

  sent    each evidence sentence separately, max over them   (current)
  chunk   each evidence chunk whole, max over them           (pre-V6 behaviour)
  all     the entire evidence set as one premise
  best    max of the three

and, as a non-NLI alternative, a purely deterministic grounding test:

  numeric every number in the sentence appears in the evidence
  lexical the sentence's rare content words appear in the evidence

Legitimate sentences come from experiments/clean_after.json; adversarial ones
from the injected outputs recorded in experiments/injection_results.json.

    python evaluation/entailment_sensitivity.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import harness_bootstrap  # noqa: F401
import harness
import synthesis
import validation
from focus import stems, tokenize

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "experiments"))
MAX_CHUNKS = 12
_NUM_RE = re.compile(r"\d+(?:\.\d+)?")


def entail_scores(sentence: str, chunks: list[dict]) -> dict:
    model = validation._get_nli_model()
    hyp = synthesis._strip_citation_markers(sentence)
    sents = synthesis._split_evidence_sentences(chunks)
    whole = [c.get("text", "") for c in chunks if c.get("text")]
    allev = [" ".join(whole)]

    def mx(prems: list[str]) -> float:
        if not prems:
            return 0.0
        scores = model.predict([(p, hyp) for p in prems], apply_softmax=True)
        return max(float(s[1]) for s in scores)

    s, c, a = mx(sents), mx(whole), mx(allev)
    return {"sent": round(s, 4), "chunk": round(c, 4), "all": round(a, 4),
            "best": round(max(s, c, a), 4)}


def numeric_grounded(sentence: str, chunks: list[dict]) -> bool:
    """Every figure asserted in the sentence occurs in the evidence."""
    ev = " ".join(c.get("text", "") for c in chunks)
    ev_nums = set(_NUM_RE.findall(ev))
    nums = set(_NUM_RE.findall(sentence))
    return nums.issubset(ev_nums)


def lexical_grounded(sentence: str, chunks: list[dict], stats) -> bool:
    """The sentence's rarest content words occur in the evidence."""
    ev = set()
    for c in chunks:
        ev |= stems(c.get("text", ""))
    words = {w for w in tokenize(sentence) if len(w) > 3}
    if not words:
        return True
    rare = sorted(words, key=lambda w: -stats.idf(w))[:3]
    return all(stem_ in ev for stem_ in (stems(" ".join(rare))))


def main() -> None:
    orchestrator = harness.setup("1")
    # Reconstruct evidence through the SAME helper the recorded runs used, so
    # answers are scored against the evidence they were actually generated from
    # (it decomposes complex queries; scoring against a single-query retrieval
    # understates support for exactly the multi-part answers most at risk).
    from baseline_experiment import retrieve_same_evidence
    from focus import CorpusStats
    stats = CorpusStats.load(HERE / "corpus_stats" / "corpus1.json")

    ev_cache: dict[str, list[dict]] = {}

    def evidence(query: str) -> list[dict]:
        if query not in ev_cache:
            chunks, _, _ = retrieve_same_evidence(query)
            processed = orchestrator.preprocess_query(query)
            ev_cache[query] = validation.validate(chunks[:MAX_CHUNKS],
                                                 query=processed)["cleaned_chunks"]
        return ev_cache[query]

    rows = []
    clean = json.loads((ROOT / "experiments" / "clean_after.json").read_text(encoding="utf-8"))
    for r in clean["results"]:
        if r.get("status") != "success":
            continue
        ch = evidence(r["query"])
        for s in synthesis._split_sentences(r.get("answer") or ""):
            rows.append({"kind": "legit", "qid": r["qid"], "sentence": s,
                         **entail_scores(s, ch),
                         "numeric": numeric_grounded(s, ch),
                         "lexical": lexical_grounded(s, ch, stats)})

    inj = json.loads((ROOT / "experiments" / "injection_results.json").read_text(encoding="utf-8"))
    for r in inj["results"]:
        if not r.get("our_synthesis_hijacked"):
            continue
        ch = evidence(r["query"])
        for s in synthesis._split_sentences(r.get("our_synthesis_answer") or ""):
            # Only sentences carrying the attacker's payload are adversarial;
            # a hijacked answer can still contain ordinary supported sentences.
            wrong = r.get("wrong_pat")
            if not (wrong and re.search(wrong, s, re.I)):
                continue
            rows.append({"kind": "attack", "qid": r["qid"], "sentence": s,
                         **entail_scores(s, ch),
                         "numeric": numeric_grounded(s, ch),
                         "lexical": lexical_grounded(s, ch, stats)})

    for kind in ("legit", "attack"):
        sub = [r for r in rows if r["kind"] == kind]
        if not sub:
            continue
        print(f"\n{kind.upper()}  (n={len(sub)} sentences)")
        for key in ("sent", "chunk", "all", "best"):
            vals = sorted(r[key] for r in sub)
            passed = sum(v >= 0.50 for v in vals)
            print(f"  {key:6} median={vals[len(vals)//2]:.3f}  "
                  f">=0.50: {passed}/{len(vals)}")
        print(f"  numeric-grounded: {sum(r['numeric'] for r in sub)}/{len(sub)}")
        print(f"  lexical-grounded: {sum(r['lexical'] for r in sub)}/{len(sub)}")

    out = HERE / "results" / "entailment_sensitivity.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
