"""evaluation/check_ledger.py: the five ledger checks, on small fixture files (no pipeline, no LLM)."""
import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evaluation"))

import check_ledger as cl  # noqa: E402

TEX = r"""\documentclass{article}
\usepackage{booktabs}
\begin{document}
Accuracy is 96.2\% (75/78) on Corpus~1~\cite{lewis2020rag}.
\begin{equation} x \geq 0.65 \end{equation}
The gate fired on 7 queries. % 99 in a comment is not a claim
\end{document}
"""


def write_ledger(path: Path, rows: list[dict]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cl.COLUMNS)
        w.writeheader()
        for i, r in enumerate(rows, start=1):
            base = {c: "" for c in cl.COLUMNS}
            base.update(id=f"T-{i:03d}", corpus_scope="C1", file="main.tex", line="4",
                        status="ACCEPTED_AS_IS", tested_after_merge="no")
            base.update(r)
            w.writerow(base)
    return path


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "main.tex").write_text(TEX, encoding="utf-8")
    (tmp_path / "res.json").write_text('{"metrics": {"acc": 96.2, "n": 78, "list": [1, 2, 3]}}', encoding="utf-8")
    (tmp_path / "code.py").write_text('A: float = 0.90   # x\nB: float = float(\n    os.getenv("RAG_B", "5.5")\n)\n', encoding="utf-8")
    return tmp_path


def run(repo, rows, checks="abcde"):
    ledger = write_ledger(repo / "ledger.csv", rows)
    rep, _ = cl.run(ledger, repo, checks)
    return rep


# ── tokenizer and comparison ────────────────────────────────────────────────
def test_tokenizer_reads_latex_and_pdf_number_forms():
    vals = lambda s: [n.value for n in cl.claim_numbers(s)]
    assert vals(r"96.2\% (75/78)") == [96.2, 75, 78]
    assert vals(r"2{,}304 configurations") == [2304]
    assert vals(r"$4.2\times10^{-7}$") == pytest.approx([4.2e-7])
    assert vals(r"$p<10^{-8}$") == pytest.approx([1e-8])
    assert vals("p<10−6; p=0.016") == pytest.approx([1e-6, 0.016])
    assert vals("p = 2.4e-9") == pytest.approx([2.4e-9])
    # identifiers are not claims
    assert vals(r"Corpus~1 (78 Queries)") == [78]
    assert vals("gpt-oss-120b on 24/24") == [24, 24]
    assert vals(r"Conflict $F_1$ & 0.84") == [0.84]


def test_compare_uses_printed_precision():
    assert cl.compare("0.727", 0.7273)[0]
    assert not cl.compare("0.023", 0.02246)[0]          # rounds to 0.022
    assert cl.compare(r"85.2\% [81.8, 88.0]", (85.2, 81.83, 87.97))[0]
    assert cl.compare("p = 2.4e-9", 2.36e-9)[0]
    assert not cl.compare("p = 2.4e-9", 2.6e-9)[0]


def test_compare_bool_selector_and_fraction_string():
    assert cl.compare("anything 5", True)[0]
    assert not cl.compare("anything 5", False)[0]
    assert cl.compare("0/32 and 1/32", "1/32", indexes=[3, 4])[0]
    assert not cl.compare("one 1", 1, indexes=[2])[0]   # selector out of range
    assert not cl.compare("one 1", (1, 2))[0]            # expression gave more numbers


def test_statistics_helpers_match_known_values():
    assert cl.wilson(0, 32) == pytest.approx((0.0, 10.72), abs=0.01)
    assert cl.wilson(1, 32) == pytest.approx((0.55, 15.74), abs=0.01)
    assert cl.mcnemar(11, 2) == pytest.approx(0.02246, abs=1e-5)
    assert cl.mcnemar(0, 0) == 1.0
    assert cl.binom_p(85, 157, 0.486) == pytest.approx(0.175, abs=0.002)
    assert cl.clopper(85, 157) == pytest.approx((46.0, 62.1), abs=0.05)
    assert cl.fisher(1, 9, 9, 1) == pytest.approx(0.0011, abs=1e-4)


def test_expressions_have_no_builtins(repo):
    ns = cl.make_namespace(repo)
    assert eval("V('res.json','metrics.list.1')", ns) == 2
    assert eval("CODE('code.py','A')", ns) == 0.90
    assert eval("CODE('code.py','B')", ns) == 5.5           # default inside os.getenv
    with pytest.raises(NameError):
        eval("open('res.json')", ns)


# ── (a) recompute ───────────────────────────────────────────────────────────
def test_recompute_match_diff_missing_file_and_missing_expression(repo):
    rep = run(repo, [
        {"value_as_written": r"96.2\%", "source": "=V('res.json','metrics.acc')", "status": "RECOMPUTED"},
        {"value_as_written": "(75/78)", "source": "=(75, V('res.json','metrics.n'))", "status": "RECOMPUTED"},
        {"value_as_written": r"96.2\%", "source": "=V('res.json','metrics.acc')-1", "status": "RECOMPUTED"},
        {"value_as_written": r"96.2\%", "source": "=V('gone.json','x')", "status": "RECOMPUTED"},
        {"value_as_written": r"96.2\%", "source": "NLPIR p5", "status": "RECOMPUTED"},
    ], checks="a")
    assert rep.passes["a"] == 2
    fails = dict(rep.fails["a"])
    assert fails["T-003"].startswith("DIFF") and "no expression" in fails["T-005"]
    assert dict(rep.warns["a"])["T-004"].startswith("NO FILE")


# ── (b) presence ────────────────────────────────────────────────────────────
def test_presence_missing_fails_and_moved_warns(repo):
    rep = run(repo, [
        {"value_as_written": r"96.2\% (75/78)", "line": "4"},
        {"value_as_written": "fired on 7 queries", "line": "200"},
        {"value_as_written": "not in the file", "line": "4"},
    ], checks="b")
    assert rep.passes["b"] == 1
    assert [rid for rid, _ in rep.warns["b"]] == ["T-002"]
    assert [rid for rid, _ in rep.fails["b"]] == ["T-003"]


def test_repeated_values_stay_on_their_own_lines_after_a_shift(repo):
    body = "\n".join(["filler"] * 3 + [r"& 0/78 & 0/78 \\"] * 3)
    (repo / "main.tex").write_text("\\begin{document}\n" + body + "\n\\end{document}\n", encoding="utf-8")
    # ledger recorded lines 2, 3, 4 before three filler lines pushed the table down
    rows = [{"value_as_written": "& 0/78 & 0/78", "line": str(n)} for n in (2, 3, 4)]
    rep = run(repo, rows, checks="bc")
    assert rep.fails["c"] == [] and rep.passes["c"] == 12
    ledger = repo / "ledger.csv"
    assert cl.sync_lines(ledger, repo) == 3
    assert [r["line"] for r in cl.load_ledger(ledger)] == ["5", "6", "7"]


# ── (c) coverage ────────────────────────────────────────────────────────────
def test_coverage_flags_only_uncovered_claims(repo):
    rep = run(repo, [{"value_as_written": r"96.2\% (75/78)", "line": "4"}], checks="c")
    uncovered = [msg for _, msg in rep.fails["c"]]
    # preamble, \cite, "Corpus~1", the equation and the comment are not claims; 7 is
    assert len(uncovered) == 1 and "'7'" in uncovered[0]


def test_coverage_selector_covers_only_the_chosen_numbers(repo):
    rep = run(repo, [
        {"value_as_written": r"96.2\% (75/78)", "line": "4", "source": "@1=96.2", "status": "RECOMPUTED"},
        {"value_as_written": "fired on 7 queries", "line": "6"},
    ], checks="c")
    assert sorted(msg.split("'")[1] for _, msg in rep.fails["c"]) == ["75", "78"]


# ── (d) rule ────────────────────────────────────────────────────────────────
def test_rule_non_c1c2_numbers_need_a_verified_status(repo):
    rep = run(repo, [
        {"value_as_written": "x", "corpus_scope": "other", "status": "UNVERIFIABLE"},
        {"value_as_written": "x", "corpus_scope": "other", "status": "ACCEPTED_AS_IS", "file": "README.md"},
        {"value_as_written": "x", "corpus_scope": "other", "status": "RECOMPUTED"},
        {"value_as_written": "x", "corpus_scope": "C2", "status": "ACCEPTED_AS_IS"},
    ], checks="d")
    assert [rid for rid, _ in rep.fails["d"]] == ["T-001"]
    assert [rid for rid, _ in rep.warns["d"]] == ["T-002"]
    assert rep.passes["d"] == 1


# ── (e) stale ───────────────────────────────────────────────────────────────
def test_stale_strings_flagged_unless_marked_historical(repo):
    (repo / "main.tex").write_text(TEX.replace("The gate", r"Frozen: 92.3\%. Also 88.4\%. The gate"), encoding="utf-8")
    (repo / "README.md").write_text("# Now\nHan et al. say 82.1%\n## History\n82.1% then\n", encoding="utf-8")
    rep = run(repo, [{"value_as_written": r"Frozen: 92.3\%", "line": "6", "notes": "HISTORICAL: frozen"}], checks="e")
    flagged = sorted(loc for loc, _ in rep.fails["e"])
    assert flagged == ["README.md:2", "README.md:2", "main.tex:6"]   # Han et al., 82.1%, 88.4%
    assert rep.passes["e"] == 2                                        # 92.3% (row), 82.1% (History)


def test_superseded_banner_marks_a_whole_markdown_file_historical(tmp_path):
    lines = ["# Title", "", "> **SUPERSEDED, 2026-10-14.** read this", "", "88.4% here"]
    assert cl.historical_lines(Path("x.md"), lines) == set(range(1, 6))


def test_schema_rejects_unknown_status_scope_and_duplicate_ids(repo):
    ledger = write_ledger(repo / "ledger.csv", [{"status": "MAYBE", "corpus_scope": "C9", "value_as_written": "x"}])
    rows = cl.load_ledger(ledger)
    rows.append(dict(rows[0]))
    rep = cl.Report()
    cl.check_schema(rows, rep)
    text = " ".join(rep.schema)
    assert "unknown status" in text and "unknown scope" in text and "duplicate id" in text


# ── the real ledger ─────────────────────────────────────────────────────────
REAL = ROOT / "docs" / "NUMBERS_LEDGER.csv"


@pytest.mark.skipif(not REAL.exists(), reason="ledger not built")
def test_real_ledger_schema_is_valid():
    rows = cl.load_ledger(REAL)
    rep = cl.Report()
    cl.check_schema(rows, rep)
    assert rep.schema == []
    assert all(cl.parse_source(r["source"]) for r in rows if r["status"] == "RECOMPUTED")
    assert all((ROOT / r["file"]).exists() for r in rows)


@pytest.mark.skipif(not (ROOT / "evaluation" / "results" / "rerun_corpus1.json").exists(),
                    reason="result files are gitignored; absent on a fresh clone")
def test_real_ledger_expressions_all_evaluate():
    """DIFFs are findings for the report; an ERROR means a broken ledger row."""
    rep, _ = cl.run(REAL, ROOT, "a")
    errors = [(rid, m) for rid, m in rep.fails["a"] if not m.startswith("DIFF")]
    assert errors == []
