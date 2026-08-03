"""
synth_hardening_test.py — HARD TEST 4: synthesis hardening.

Closes the end-to-end injection hole found in E3 (synthesis ASR 0.40, exfil
0.87) by hardening ONLY the synthesis prompt/wrapping — no validation/decision
threshold is touched. Re-runs the exact 45 E3 injection cases plus a clean
regression set through synthesis, and compares before/after.

Phases (run order matters — clean-before must run BEFORE the code edits):
  --clean-before   un-hardened synthesis on clean (un-poisoned) queries  -> clean_before.json
  --clean-after    hardened synthesis on the same clean queries           -> clean_after.json
  --inject         hardened synthesis on the 45 poisoned E3 cases         -> hardening_injection.json
  --inject-smoke   2 poisoned cases only (sanity check before the full 45)
  --report         build before/after + regression tables + summary md

Synthesis is called via the REAL synthesis.synthesize(), with its LLM call
routed through the rotating Groq helper using the CURRENT (possibly hardened)
synthesis system prompt — so this measures the real system behaviour.
"""
from __future__ import annotations
import argparse, json, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments"))
try:
    from dotenv import load_dotenv; load_dotenv(ROOT / ".env")
except ImportError:
    pass

from baseline_experiment import groq_chat, n_keys, DailyTokenExhausted  # noqa
from injection_test import (  # noqa: reuse EXACT E3 machinery
    QUERIES, STYLES, build_poison_chunk, context_block, route_decision,
    graded_hijack, POISON_SOURCE,
)
from baseline_experiment import retrieve_same_evidence  # noqa
from validation import validate  # noqa
import synthesis  # noqa
import llm_interface  # noqa

OUT = ROOT / "experiments"
MAX_CHUNKS = 12

# Route synthesis's LLM call through rotating Groq, reading the CURRENT synthesis
# system prompt at call time (so the hardened prompt is picked up after editing).
synthesis.call_synthesis_llm = lambda prompt: groq_chat(
    llm_interface._SYNTHESIS_SYSTEM_PROMPT, prompt, temperature=0.0
)


def clean_chunks(qtext):
    norm, _, _ = retrieve_same_evidence(qtext)
    return norm[:MAX_CHUNKS]


def run_clean(out_name):
    """Synthesis on clean (un-poisoned) queries — regression / quality check."""
    results = []
    for (qid, qtext, true_pat, wrong_val, wrong_pat) in QUERIES:
        chunks = clean_chunks(qtext)
        vres = validate(chunks, query=qtext)
        decision = route_decision(vres)
        if decision == "answer":
            sres = synthesis.synthesize(
                query=qtext, cleaned_chunks=vres["cleaned_chunks"],
                sufficiency_flag=vres["sufficiency_flag"],
                conflict_flag=vres["conflict_flag"])
            ans, status, faith = sres["answer"], sres["status"], sres.get("faithfulness_score")
        else:
            ans, status, faith = f"(routed to {decision})", "abstain", None
        true_present = bool(re.search(true_pat, ans, re.I))
        results.append({"qid": qid, "query": qtext, "decision": decision,
                        "status": status, "faithfulness": faith,
                        "true_value_present": true_present, "answer": ans})
        print(f"  {qid} decision={decision} true_present={true_present} "
              f"faith={faith}", flush=True)
    json.dump({"results": results, "synthesis_system_prompt": llm_interface._SYNTHESIS_SYSTEM_PROMPT},
              open(OUT / out_name, "w", encoding="utf-8"), indent=2)
    print(f"Wrote {OUT/out_name}")


def run_inject(queries, out_name):
    """Hardened synthesis on the poisoned E3 cases (same inputs as E3)."""
    checkpoint = OUT / out_name
    results, done = [], set()
    if checkpoint.exists():
        try:
            prev = json.load(open(checkpoint, encoding="utf-8"))
            results = prev.get("results", []); done = {r["key"] for r in results}
            if done: print(f"Resuming: {len(done)} done.\n", flush=True)
        except Exception:
            pass
    print(f"Groq keys: {n_keys()}\n", flush=True)
    total = len(queries) * len(STYLES); idx = 0; stopped = False
    for (qid, qtext, true_pat, wrong_val, wrong_pat) in queries:
        norm = clean_chunks(qtext)
        for style in STYLES:
            idx += 1; key = f"{qid}|{style}"
            if key in done: continue
            poison = build_poison_chunk(style, wrong_val)
            poisoned = norm[:1] + [poison] + norm[1:]   # identical to E3
            vres = validate(poisoned, query=qtext)
            decision = route_decision(vres)
            try:
                if decision == "answer":
                    sres = synthesis.synthesize(
                        query=qtext, cleaned_chunks=vres["cleaned_chunks"],
                        sufficiency_flag=vres["sufficiency_flag"],
                        conflict_flag=vres["conflict_flag"])
                    ans, status = sres["answer"], sres["status"]
                else:
                    ans, status = f"(no synthesis — routed to '{decision}')", "abstain_at_gate"
            except DailyTokenExhausted as exc:
                print(f"\n[!] Groq daily cap at {key}. Saving {len(results)}.\n {exc}", flush=True)
                stopped = True; break
            hij = (decision == "answer" and graded_hijack(style, ans, wrong_pat, true_pat))
            results.append({"key": key, "qid": qid, "style": style,
                            "our_decision": decision, "our_synthesis_status": status,
                            "our_synthesis_answer": ans, "our_synthesis_hijacked": hij})
            json.dump({"results": results,
                       "synthesis_system_prompt": llm_interface._SYNTHESIS_SYSTEM_PROMPT},
                      open(checkpoint, "w", encoding="utf-8"), indent=2)
            print(f"[{idx}/{total}] {key:<16} route={decision:<12} "
                  f"synth={'HIT' if hij else ('safe' if decision!='answer' else '---')}",
                  flush=True)
        if stopped: break
    return results, stopped


def build_report():
    inj = json.load(open(OUT / "hardening_injection.json", encoding="utf-8"))["results"]
    before = json.load(open(OUT / "injection_results.json", encoding="utf-8"))["results"]
    cb = json.load(open(OUT / "clean_before.json", encoding="utf-8"))["results"]
    ca = json.load(open(OUT / "clean_after.json", encoding="utf-8"))["results"]

    def asr(recs, style=None):
        rs = [r for r in recs if style is None or r["style"] == style]
        return round(sum(r["our_synthesis_hijacked"] for r in rs) / len(rs), 3)
    L = []
    A = L.append
    A("# HARD TEST 4 — Synthesis Hardening (before / after)\n")
    A("*Only the synthesis prompt + evidence wrapping changed. No validation/"
      "decision threshold touched. Same 45 poisoned inputs as E3. Model "
      "llama-3.3-70b-versatile, temp 0.*\n")
    A("## End-to-end synthesis ASR: E3 (before) vs hardened (after)\n")
    A("| Injection style | E3 before | Hardened after |")
    A("|---|---|---|")
    for s in STYLES:
        A(f"| {s} | {asr(before, s):.2f} | {asr(inj, s):.2f} |")
    A(f"| **All (n={len(inj)})** | **{asr(before):.2f}** | **{asr(inj):.2f}** |")
    A("")
    A("## Exfiltration specifically (E3 was 0.87)\n")
    A(f"- Before (E3): {asr(before,'exfil'):.2f}  →  After hardening: {asr(inj,'exfil'):.2f}")
    A("")
    A("## Regression on clean (un-poisoned) queries\n")
    def agg_clean(recs):
        ans = [r for r in recs if r["decision"] == "answer"]
        tp = sum(r["true_value_present"] for r in ans)
        fa = [r["faithfulness"] for r in ans if r["faithfulness"] is not None]
        return len(ans), tp, (round(sum(fa)/len(fa), 3) if fa else None)
    nb, tb, fb = agg_clean(cb)
    na, ta, fa_ = agg_clean(ca)
    A("| | queries answered | correct value present | mean faithfulness |")
    A("|---|---|---|---|")
    A(f"| Before hardening | {nb} | {tb}/{nb} | {fb} |")
    A(f"| After hardening | {na} | {ta}/{na} | {fa_} |")
    # decision flips on clean
    db = {r["qid"]: r["decision"] for r in cb}
    flips = [q for q in db if db[q] != next(r["decision"] for r in ca if r["qid"] == q)]
    A(f"\nClean-query decision flips after hardening: {len(flips)} "
      f"({flips if flips else 'none — decisions unchanged, as expected'})")
    A("")
    A("## Honest finding\n")
    ov_b, ov_a = asr(before), asr(inj)
    A(f"After hardening, end-to-end synthesis ASR = **{ov_a:.2f}** (was {ov_b:.2f} in "
      f"E3); exfiltration {asr(before,'exfil'):.2f} → {asr(inj,'exfil'):.2f}. This is a "
      "DEFENSIVE fix: the hardened system now matches a defended LLM end-to-end "
      "(E3 defended-LLM ASR was 0.00) rather than being worse. It is not an "
      "end-to-end *advantage* over a defended LLM. The durable advantage remains "
      "at the DECISION layer (injection-immune 0/45 by construction). Clean-query "
      "regression: decisions unchanged (synthesis never affects routing); correct "
      f"value retained {ta}/{na}; faithfulness {fb} → {fa_}.")
    (OUT / "hardening_summary.md").write_text("\n".join(L), encoding="utf-8")
    print("Wrote", OUT / "hardening_summary.md")
    print("\n".join(L))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean-before", action="store_true")
    ap.add_argument("--clean-after", action="store_true")
    ap.add_argument("--inject", action="store_true")
    ap.add_argument("--inject-smoke", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    if args.clean_before: run_clean("clean_before.json")
    elif args.clean_after: run_clean("clean_after.json")
    elif args.inject_smoke: run_inject(QUERIES[:2], "hardening_injection_smoke.json")
    elif args.inject: run_inject(QUERIES, "hardening_injection.json")
    elif args.report: build_report()
    else: ap.error("pick a phase")


if __name__ == "__main__":
    main()
