"""
check_ledger.py: check docs/NUMBERS_LEDGER.csv against the files it describes.

The ledger has one row per numeric claim, in every place the claim appears
(main.tex, the NLPIR PDF, README.md, docs/STATUS.md, docs/RAMDOCS_COMPARISON.md,
numbers.md). This script is read-only: it runs no pipeline, calls no LLM and
needs no API key. It runs five checks:

  (a) recompute: every row whose `source` is an expression (starts with "=" or
      "@i,j=") is evaluated and compared with the numbers in `value_as_written`
      at the printed precision. A RECOMPUTED row without an expression fails.
  (b) presence: each `value_as_written` string appears in its file, near its
      recorded line (MOVED is a warning, MISSING a failure). PDF rows give the
      page as "p7" and are matched on the page text (needs PyMuPDF).
  (c) coverage: every number in the body of main.tex lies inside a ledger row
      (citations, labels, layout sizes, equations, TikZ and the identifiers in
      NON_CLAIM_PATTERNS are not claims and are skipped).
  (d) rule: a number that is not about Corpus 1 or 2 (scope "other") must be
      REPRODUCED, RECOMPUTED, DERIVED or EXTERNAL. ACCEPTED_AS_IS or
      UNVERIFIABLE on such a row fails in main.tex and warns elsewhere.
  (e) stale: superseded strings (STALE_PATTERNS) are flagged unless they sit in
      a section marked historical, or the ledger row covering them says so
      (notes starting "HISTORICAL:" or containing "STALE_OK:").

Expressions (source column). Evaluated with no Python builtins; the names are:
  V(path, "a.b.0.c")   value at a dotted path in a JSON file (path from repo root;
                       integers index lists); V(path) is the whole document
  CODE(path, NAME)     the default of constant NAME in a source file
  GLOB(pattern)        number of files matching a glob
  FRAC("3/16")         (3, 16)
  count(seq, fn)       how many items fn(item) is true for
  pct(k, n)            100 * k / n
  wilson(k, n)         Wilson 95% interval, in percent, as (lo, hi)
  clopper(k, n)        exact (Clopper-Pearson) 95% interval, in percent
  mcnemar(b, c)        exact two-sided McNemar p from the discordant counts
  pairs(a, b, key)     two per-query lists aligned on key, as (a_item, b_item)
  mcnemar_pairs(p, fa, fb)  exact McNemar p over aligned pairs and two predicates
  binom_p(k, n, p0)    exact two-sided binomial p (sum of outcomes no likelier)
  fisher(a, b, c, d)   two-sided Fisher exact p for [[a, b], [c, d]]
  plus len, sum, min, max, abs, round, sorted, set, list, tuple, any, all, zip
A number is compared with the first number in the value (or the ones chosen by
"@i,j=", 1-based); a tuple with the first len(tuple) numbers; a bool is a
direct pass or fail. Tolerance is half a unit in the last printed digit.

    python evaluation/check_ledger.py            # all checks, summary
    python evaluation/check_ledger.py -v         # also list every finding
    python evaluation/check_ledger.py --checks a,b
    python evaluation/check_ledger.py --sync-lines   # after editing a file: store new lines

Exit status 1 if any check fails, 0 otherwise.
"""

from __future__ import annotations

import argparse
import csv
import glob as _glob
import json
import math
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "docs" / "NUMBERS_LEDGER.csv"
PAPER = "main.tex"

COLUMNS = ["id", "value_as_written", "meaning", "corpus_scope", "file", "line",
           "source", "status", "tested_after_merge", "date", "commit", "notes"]
STATUSES = ("REPRODUCED", "RECOMPUTED", "DERIVED", "EXTERNAL", "ACCEPTED_AS_IS",
            "UNVERIFIABLE")
SCOPES = ("C1", "C2", "both", "other")
TESTED = ("yes", "no", "n/a")
RULE_OK = {"REPRODUCED", "RECOMPUTED", "DERIVED", "EXTERNAL"}
MOVE_TOLERANCE = 40  # lines; other chats edit these files, so drift is a warning

# Files scanned for stale strings, and the strings (regex, why it is stale).
STALE_FILES = ("main.tex", "README.md", "docs/STATUS.md", "docs/RAMDOCS_COMPARISON.md")
STALE_PATTERNS = (
    (r"88\.4\s*\\?%", "88.4% is the label-leaky RAMDocs run (Observation 44)"),
    (r"82\.1\s*\\?%", "82.1% is Corpus 2 before the answerhood gate, not the current system"),
    (r"92\.3\s*\\?%", "92.3% is the frozen v6 Corpus 1 system, not the current one"),
    (r"Han et al\.", "the RAMDocs citation is Wang et al. (first author Han Wang)"),
    (r"10 of 25", "superseded count"),
)
# Markdown headings (or a top banner) that mark a section as historical.
HISTORICAL_HEADING = re.compile(r"histor|supersed|archive|frozen|\bv6\b|previous", re.I)
LATEX_HIST_BEGIN = re.compile(r"%\s*ledger:\s*historical-begin", re.I)
LATEX_HIST_END = re.compile(r"%\s*ledger:\s*historical-end", re.I)

# Numbers in main.tex that are identifiers or names, not claims.
NON_CLAIM_PATTERNS = (
    r"\bQ\d{3}\b",                                   # query ids
    r"\b(?:C[123]|E[1-5]|H[1-9])\b",                 # corpus, experiment, hypothesis tags
    r"Corpus(?:~|\s)?[123]\b", r"Corpora 1/2",
    r"Stages?(?:~|\s)?\d+(?:\s*(?:through|and|to|,)\s*\d+)*",
    r"Stage~?\d", r"Prong~?[ABC]",
    r"(?m)^\s*\d\s+&\s+[A-Z]",                       # stage numbers in the validation table
    r"\(\d\)~",                                      # enumerations in future work
    r"all-MiniLM-L6-v2", r"ms-marco-MiniLM-L-6-v2", r"MiniLM",
    r"deberta-v3-base", r"DeBERTa-v3", r"answerai-colbert-small-v1",
    r"[Ll]lama-3(?:\.3)?(?:-70[Bb])?(?:-versatile)?", r"Llama-3",
    r"Qwen2\.5-72B", r"GPT-4o-mini", r"gpt-oss-120b", r"\b70B\b", r"\b120B\b",
    r"Python(?:~|\s)3\.\d+", r"SHA-256", r"C2-Cite", r"384(?:-d| dimensions)",
    r"\\mathbbm\{1\}", r"Figs?\.~?\d", r"\\textsuperscript\{\w\}",
    r"\\multicolumn\{\d\}\{[^}]*\}", r"\\multirow\{\d\}\{[^}]*\}",
    r"\*\{\d\}\{", r"p\{0\.\d+\\columnwidth\}", r"\d*\.?\d+\\columnwidth",
    r"\\setlength\{[^}]*\}\{[^}]*\}", r"\\tabcolsep", r"\\\\\[[^\]]*\]",
    r"\\vspace\{[^}]*\}", r"\\hfill", r"Wilson 95\\%", r"95\\% interval",
    r"\\captionof\{table\}", r"F_\{?1\}?", r"\b[a-z]+(?:19|20)\d\d[a-z]*\b",  # cite keys split over lines
    r"SQuAD~?2\.0", r"BM25", r"3x3", r"n\s*\\geq\s*2", r"\bv6\b", r"Finding \d",
    r"stage3", r"\bF1\b",
)
_MASK_COMMANDS = re.compile(
    r"\\(?:cite|ref|label|url|eqref|includegraphics|IfFileExists|bibliography"
    r"|bibliographystyle|usepackage|begin|end)(?:\[[^\]]*\])?\{[^}]*\}")
_DIMENSION = re.compile(r"\d*\.?\d+\s*(?:pt|em|mm|cm|ex|in)\b")
_MASKED_ENVS = ("tikzpicture", "equation")

# One tokenizer for coverage and for comparison, so "@2=" indexes the same
# numbers the coverage check sees. "2{,}304" is one number; "4.2\times10^{-7}"
# and "10^{-8}" are one number each.
_MINUS = "\u2212"  # the minus sign PyMuPDF returns for PDF text
_NUM = re.compile(
    r"(?P<sci>(?P<mant>\d+(?:\.\d+)?)\s*(?:\\times|\u00d7)\s*10\s*(?:\^\{?)?\s*(?P<exp>[-\u2212]?\d+)\}?)"
    r"|(?P<pow>(?<![\d.])10\s*(?:\^\{|(?=\u2212))(?P<pexp>[-\u2212]?\d+)\}?)"
    r"|(?P<plain>\d+(?:\{,\}\d{3}|,\d{3}(?!\d))*(?:\.\d+)?(?:e[-+]?\d+)?)")
_NON_CLAIM_RE = [re.compile(p) for p in NON_CLAIM_PATTERNS]


@dataclass
class Num:
    start: int
    end: int
    value: float
    tol: float


def tokenize(text: str) -> list[Num]:
    out = []
    for m in _NUM.finditer(text):
        if m.group("sci"):
            mant = m.group("mant")
            exp = int(m.group("exp").replace(_MINUS, "-"))
            dec = len(mant.split(".")[1]) if "." in mant else 0
            out.append(Num(m.start(), m.end(), float(mant) * 10 ** exp,
                           0.5 * 10 ** (-dec) * 10 ** exp))
        elif m.group("pow"):
            exp = int(m.group("pexp").replace(_MINUS, "-"))
            out.append(Num(m.start(), m.end(), 10.0 ** exp, 0.5 * 10.0 ** exp))
        else:
            s = m.group("plain").replace("{,}", "").replace(",", "")
            mant, _, e = s.partition("e")
            dec = len(mant.split(".")[1]) if "." in mant else 0
            scale = 10 ** int(e) if e else 1
            out.append(Num(m.start(), m.end(), float(s), 0.5 * 10 ** (-dec) * scale + 1e-9 * scale))
    return out


def mask_claims(text: str) -> str:
    """Blank the identifiers in NON_CLAIM_PATTERNS, keeping every column in place."""
    for p in _NON_CLAIM_RE:
        text = p.sub(lambda m: " " * (m.end() - m.start()), text)
    return text


def claim_numbers(value: str) -> list[Num]:
    """The numbers a ledger value states, ignoring identifiers such as "Corpus 1"."""
    return tokenize(mask_claims(value))


# ── expression helpers ──────────────────────────────────────────────────────
_JSON_CACHE: dict[Path, object] = {}


def _resolve(path: str, root: Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else root / p


def make_namespace(root: Path) -> dict:
    def V(path: str, dotted: str | None = None):
        p = _resolve(path, root)
        if p not in _JSON_CACHE:
            if not p.exists():
                raise FileNotFoundError(path)
            _JSON_CACHE[p] = json.loads(p.read_text(encoding="utf-8"))
        cur = _JSON_CACHE[p]
        if dotted:
            for part in dotted.split("."):
                cur = cur[int(part)] if isinstance(cur, list) else cur[part]
        return cur

    def CODE(path: str, name: str) -> float:
        p = _resolve(path, root)
        if not p.exists():
            raise FileNotFoundError(path)
        lines = p.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if re.match(rf"^{re.escape(name)}\b[^=]*=", line):
                tail = " ".join(lines[i:i + 6]).split("=", 1)[1]
                m = re.search(r"(?<![\w.])(\d+(?:\.\d+)?)", tail)
                if m:
                    return float(m.group(1))
        raise KeyError(f"{name} not found in {path}")

    def GLOB(pattern: str) -> int:
        return len(_glob.glob(str(root / pattern)))

    def FRAC(s: str):
        a, b = str(s).split("/")
        return (int(a), int(b))

    return {
        "__builtins__": {}, "V": V, "CODE": CODE, "GLOB": GLOB, "FRAC": FRAC,
        "count": lambda seq, fn: sum(1 for x in seq if fn(x)),
        "pct": lambda k, n: 100.0 * k / n, "wilson": wilson, "clopper": clopper,
        "mcnemar": mcnemar, "mcnemar_pairs": mcnemar_pairs, "pairs": pairs,
        "binom_p": binom_p, "fisher": fisher,
        "len": len, "sum": sum, "min": min, "max": max, "abs": abs, "round": round,
        "sorted": sorted, "set": set, "list": list, "tuple": tuple, "any": any,
        "all": all, "zip": zip, "float": float, "int": int, "str": str, "bool": bool,
    }


def wilson(k: int, n: int, z: float = 1.959963984540054):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * max(0.0, c - h), 100 * min(1.0, c + h))


def clopper(k: int, n: int):
    """Exact (Clopper-Pearson) 95% interval, in percent, as (lo, hi)."""
    def cdf(kk: int, p: float) -> float:
        return sum(_binom_pmf(i, n, p) for i in range(kk + 1))

    def bisect(pred) -> float:
        a, b = 0.0, 1.0
        for _ in range(60):
            m = (a + b) / 2
            a, b = (a, m) if pred(m) else (m, b)
        return (a + b) / 2

    lo = 0.0 if k == 0 else bisect(lambda p: 1 - cdf(k - 1, p) >= 0.025)
    hi = 1.0 if k == n else bisect(lambda p: cdf(k, p) <= 0.025)
    return (100 * lo, 100 * hi)


def pairs(a: list, b: list, key: str = "id") -> list:
    """Items of two per-query lists aligned on key, as (a_item, b_item)."""
    bk = {x[key]: x for x in b}
    return [(x, bk[x[key]]) for x in a if x[key] in bk]


def mcnemar_pairs(p: list, fa, fb) -> float:
    """Exact McNemar p over aligned pairs for two per-item predicates."""
    b = sum(1 for x, y in p if fa(x) and not fb(y))
    c = sum(1 for x, y in p if not fa(x) and fb(y))
    return mcnemar(b, c)


def _binom_pmf(k: int, n: int, p: float) -> float:
    return math.comb(n, k) * p ** k * (1 - p) ** (n - k)


def binom_p(k: int, n: int, p0: float = 0.5) -> float:
    obs = _binom_pmf(k, n, p0)
    return min(1.0, sum(_binom_pmf(i, n, p0) for i in range(n + 1)
                        if _binom_pmf(i, n, p0) <= obs * (1 + 1e-7)))


def mcnemar(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(_binom_pmf(i, n, 0.5) for i in range(min(b, c) + 1)))


def fisher(a: int, b: int, c: int, d: int) -> float:
    r1, c1, n = a + b, a + c, a + b + c + d

    def hyper(x: int) -> float:
        return math.comb(c1, x) * math.comb(n - c1, r1 - x) / math.comb(n, r1)

    obs = hyper(a)
    lo, hi = max(0, r1 + c1 - n), min(r1, c1)
    return min(1.0, sum(hyper(x) for x in range(lo, hi + 1) if hyper(x) <= obs * (1 + 1e-7)))


# ── ledger I/O ──────────────────────────────────────────────────────────────
def load_ledger(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return rows


_SELECTOR = re.compile(r"^@(?P<idx>\d+(?:,\d+)*)=")


def parse_source(source: str):
    """Return (indexes or None, expression) for an expression source, else None."""
    s = (source or "").strip()
    m = _SELECTOR.match(s)
    if m:
        return [int(i) for i in m.group("idx").split(",")], s[m.end():]
    if s.startswith("="):
        return None, s[1:]
    return None


@dataclass
class Report:
    fails: dict = field(default_factory=lambda: {k: [] for k in "abcde"})
    warns: dict = field(default_factory=lambda: {k: [] for k in "abcde"})
    passes: Counter = field(default_factory=Counter)
    schema: list = field(default_factory=list)

    def failed(self) -> bool:
        return bool(self.schema) or any(self.fails.values())


def check_schema(rows: list[dict], rep: Report) -> None:
    seen = set()
    for i, r in enumerate(rows, start=2):
        missing = [c for c in COLUMNS if c not in r]
        if missing:
            rep.schema.append(f"row {i}: missing columns {missing}")
            continue
        if r["id"] in seen:
            rep.schema.append(f"row {i}: duplicate id {r['id']}")
        seen.add(r["id"])
        if r["status"] not in STATUSES:
            rep.schema.append(f"{r['id']}: unknown status {r['status']!r}")
        if r["corpus_scope"] not in SCOPES:
            rep.schema.append(f"{r['id']}: unknown scope {r['corpus_scope']!r}")
        if r["tested_after_merge"] not in TESTED:
            rep.schema.append(f"{r['id']}: tested_after_merge must be one of {TESTED}")
        if not r["value_as_written"]:
            rep.schema.append(f"{r['id']}: empty value_as_written")


def _flat(x):
    if isinstance(x, (list, tuple)):
        for y in x:
            yield from _flat(y)
    else:
        yield x


def compare(value: str, result, indexes=None) -> tuple[bool, str]:
    if isinstance(result, bool):
        return result, f"condition is {result}"
    if isinstance(result, str) and "/" in result:
        a, b = result.split("/")
        result = (int(a), int(b))
    got = [float(x) for x in _flat(result)]
    nums = claim_numbers(value)
    if indexes:
        try:
            nums = [nums[i - 1] for i in indexes]
        except IndexError:
            return False, f"selector {indexes} out of range ({len(claim_numbers(value))} numbers)"
    if len(nums) < len(got):
        return False, f"value has {len(nums)} numbers, expression gave {len(got)}"
    bad = [(n.value, g) for n, g in zip(nums, got) if abs(n.value - g) > n.tol]
    shown = ", ".join(f"{g:.6g}" for g in got)
    if bad:
        return False, f"got {shown}; written {[n.value for n in nums[:len(got)]]}"
    return True, f"got {shown}"


def check_recompute(rows: list[dict], root: Path, rep: Report) -> None:
    ns = make_namespace(root)
    for r in rows:
        parsed = parse_source(r["source"])
        if parsed is None:
            if r["status"] == "RECOMPUTED":
                rep.fails["a"].append((r["id"], "RECOMPUTED row has no expression source"))
            continue
        indexes, expr = parsed
        try:
            result = eval(expr, ns)  # noqa: S307 - ledger is repo-authored, builtins removed
        except FileNotFoundError as e:
            rep.warns["a"].append((r["id"], f"NO FILE {e}"))
            continue
        except Exception as e:  # noqa: BLE001
            rep.fails["a"].append((r["id"], f"ERROR {type(e).__name__}: {e}"))
            continue
        ok, msg = compare(r["value_as_written"], result, indexes)
        if ok:
            rep.passes["a"] += 1
        else:
            rep.fails["a"].append((r["id"], f"DIFF {msg}"))


# ── file text, with PDF pages ───────────────────────────────────────────────
_TEXT_CACHE: dict[Path, list[str]] = {}


def _norm_ws(s: str) -> str:
    s = s.replace("\u2212", "-").replace("−", "-").replace("ﬀ", "ff").replace("ﬁ", "fi")
    return re.sub(r"\s+", " ", s).strip()


def pdf_pages(path: Path) -> list[str]:
    if path not in _TEXT_CACHE:
        import fitz  # PyMuPDF; optional, only for PDF rows

        with fitz.open(path) as doc:
            _TEXT_CACHE[path] = [_norm_ws(p.get_text()) for p in doc]
    return _TEXT_CACHE[path]


def file_lines(path: Path) -> list[str]:
    if path not in _TEXT_CACHE:
        _TEXT_CACHE[path] = path.read_text(encoding="utf-8").splitlines()
    return _TEXT_CACHE[path]


def find_occurrences(lines: list[str], value: str) -> list[tuple[int, int]]:
    """(1-based line, column) of every occurrence of value."""
    out = []
    for i, line in enumerate(lines, start=1):
        start = line.find(value)
        while start != -1:
            out.append((i, start))
            start = line.find(value, start + 1)
    return out


def nearest(occ: list[tuple[int, int]], line: int):
    return min(occ, key=lambda o: abs(o[0] - line)) if occ else None


def _line_no(s: str) -> int:
    try:
        return int(str(s).strip())
    except ValueError:
        return 0


def _assign(lines_wanted: list[int], occ: list[tuple[int, int]]) -> list:
    """Order-preserving match of rows (by recorded line) to occurrences, least total drift.

    Several rows can share one value string (for example "& 0/78 & 0/78" in a table);
    matching them in order keeps each row on its own line when the file shifts.
    """
    k, m = len(lines_wanted), len(occ)
    if k > m:  # more rows than occurrences: each takes its nearest
        return [nearest(occ, ln) for ln in lines_wanted]
    inf = float("inf")
    cost = [[inf] * (m + 1) for _ in range(k + 1)]
    for j in range(m + 1):
        cost[0][j] = 0.0
    for i in range(1, k + 1):
        for j in range(i, m + 1):
            take = cost[i - 1][j - 1] + abs(occ[j - 1][0] - lines_wanted[i - 1])
            cost[i][j] = min(cost[i][j - 1], take)
    out, j = [None] * k, m
    for i in range(k, 0, -1):
        while cost[i][j] == cost[i][j - 1] and j > i:
            j -= 1
        out[i - 1] = occ[j - 1]
        j -= 1
    return out


def locate(rows: list[dict], root: Path) -> dict:
    """Row id -> (line, column) of its value in its (text) file, or None if absent."""
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        path = _resolve(r["file"], root)
        if path.suffix.lower() == ".pdf" or not path.exists():
            continue
        groups.setdefault((str(path), r["value_as_written"]), []).append(r)
    found = {}
    for (path, value), rs in groups.items():
        occ = find_occurrences(file_lines(Path(path)), value)
        if not occ:
            found.update({r["id"]: None for r in rs})
            continue
        rs = sorted(rs, key=lambda r: _line_no(r["line"]))
        for r, o in zip(rs, _assign([_line_no(r["line"]) for r in rs], occ)):
            found[r["id"]] = o
    return found


def check_presence(rows: list[dict], root: Path, rep: Report) -> None:
    where = locate(rows, root)
    for r in rows:
        path = _resolve(r["file"], root)
        if not path.exists():
            rep.fails["b"].append((r["id"], f"file not found: {r['file']}"))
            continue
        if path.suffix.lower() == ".pdf":
            try:
                pages = pdf_pages(path)
            except ImportError:
                rep.warns["b"].append((r["id"], "PyMuPDF not installed; PDF row not checked"))
                continue
            want = _norm_ws(r["value_as_written"])
            page = int(str(r["line"]).lstrip("p") or 0)
            hits = [i + 1 for i, t in enumerate(pages) if want in t]
            if not hits:
                rep.fails["b"].append((r["id"], f"MISSING in {r['file']}: {want!r}"))
            elif page not in hits:
                rep.warns["b"].append((r["id"], f"MOVED to page {hits[0]} (ledger p{page})"))
            else:
                rep.passes["b"] += 1
            continue
        line = _line_no(r["line"])
        best = where.get(r["id"])
        if best is None:
            rep.fails["b"].append((r["id"], f"MISSING in {r['file']}: {r['value_as_written']!r}"))
        elif abs(best[0] - line) > MOVE_TOLERANCE:
            rep.warns["b"].append((r["id"], f"MOVED {r['file']}:{line} -> {best[0]}"))
        else:
            rep.passes["b"] += 1


# ── coverage of main.tex ────────────────────────────────────────────────────
def masked_body(lines: list[str]) -> list[str]:
    """main.tex lines with every non-claim region blanked (same length, same columns)."""
    out = []
    in_body = False
    env_depth = {e: 0 for e in _MASKED_ENVS}
    for line in lines:
        if not in_body:
            out.append(" " * len(line))
            if r"\begin{document}" in line:
                in_body = True
            continue
        s = line
        for e in _MASKED_ENVS:
            if rf"\begin{{{e}}}" in s:
                env_depth[e] += 1
        if any(env_depth.values()):
            for e in _MASKED_ENVS:
                if rf"\end{{{e}}}" in s:
                    env_depth[e] -= 1
            out.append(" " * len(line))
            continue
        m = re.search(r"(?<!\\)%", s)
        if m:
            s = s[:m.start()] + " " * (len(s) - m.start())

        def blank(mm):
            return " " * (mm.end() - mm.start())

        s = _MASK_COMMANDS.sub(blank, s)
        s = _DIMENSION.sub(blank, s)
        s = mask_claims(s)
        out.append(s)
    return out


def covered_spans(rows: list[dict], where: dict, paper: str) -> dict[int, list[tuple[int, int]]]:
    spans: dict[int, list[tuple[int, int]]] = {}
    for r in rows:
        if r["file"] != paper:
            continue
        value = r["value_as_written"]
        best = where.get(r["id"])
        if best is None:
            continue
        ln, col = best
        nums = claim_numbers(value)
        parsed = parse_source(r["source"])
        indexes = parsed[0] if parsed else None
        chosen = [nums[i - 1] for i in indexes if 0 < i <= len(nums)] if indexes else nums
        for n in chosen:
            spans.setdefault(ln, []).append((col + n.start, col + n.end))
    return spans


def check_coverage(rows: list[dict], root: Path, rep: Report, paper: str = PAPER) -> None:
    path = root / paper
    if not path.exists():
        rep.fails["c"].append(("-", f"{paper} not found"))
        return
    lines = file_lines(path)
    body = masked_body(lines)
    spans = covered_spans(rows, locate(rows, root), paper)
    for ln, text in enumerate(body, start=1):
        for n in tokenize(text):
            if any(a <= n.start and n.end <= b for a, b in spans.get(ln, [])):
                rep.passes["c"] += 1
            else:
                snippet = lines[ln - 1][max(0, n.start - 30):n.end + 30].strip()
                rep.fails["c"].append((f"{paper}:{ln}", f"uncovered {text[n.start:n.end]!r} in ...{snippet}..."))


# ── rule and staleness ──────────────────────────────────────────────────────
def check_rule(rows: list[dict], rep: Report, paper: str = PAPER) -> None:
    for r in rows:
        if r["corpus_scope"] != "other":
            continue
        if r["status"] in RULE_OK:
            rep.passes["d"] += 1
            continue
        msg = f"non-C1/C2 number with status {r['status']}: {r['value_as_written']!r} ({r['file']}:{r['line']})"
        (rep.fails if r["file"] == paper else rep.warns)["d"].append((r["id"], msg))


def historical_lines(path: Path, lines: list[str]) -> set[int]:
    hist: set[int] = set()
    if path.suffix == ".md":
        head = "\n".join(lines[:8])
        if re.search(r"^>\s*\**SUPERSEDED", head, re.M):
            return set(range(1, len(lines) + 1))
        level_hist = None
        for i, line in enumerate(lines, start=1):
            m = re.match(r"^(#+)\s+(.*)", line)
            if m:
                level = len(m.group(1))
                if level_hist is not None and level <= level_hist:
                    level_hist = None
                if level_hist is None and HISTORICAL_HEADING.search(m.group(2)):
                    level_hist = level
            if level_hist is not None:
                hist.add(i)
    else:
        on = False
        for i, line in enumerate(lines, start=1):
            if LATEX_HIST_BEGIN.search(line):
                on = True
            if on:
                hist.add(i)
            if LATEX_HIST_END.search(line):
                on = False
    return hist


def _stale_ok(note: str) -> bool:
    return note.strip().upper().startswith("HISTORICAL:") or "STALE_OK:" in note.upper()


def check_stale(rows: list[dict], root: Path, rep: Report, files=STALE_FILES) -> None:
    for rel in files:
        path = root / rel
        if not path.exists():
            continue
        lines = file_lines(path)
        hist = historical_lines(path, lines)
        mask = masked_body(lines) if rel.endswith(".tex") else lines
        ok_spans: dict[int, list[tuple[int, int]]] = {}
        where = locate([r for r in rows if r["file"] == rel], root)
        for r in rows:
            if r["file"] != rel or not _stale_ok(r["notes"]):
                continue
            best = where.get(r["id"])
            if best:
                ok_spans.setdefault(best[0], []).append((best[1], best[1] + len(r["value_as_written"])))
        for pat, why in STALE_PATTERNS:
            for ln, text in enumerate(mask, start=1):
                for m in re.finditer(pat, text):
                    if ln in hist:
                        rep.passes["e"] += 1
                    elif any(a <= m.start() and m.end() <= b for a, b in ok_spans.get(ln, [])):
                        rep.passes["e"] += 1
                    else:
                        rep.fails["e"].append((f"{rel}:{ln}", f"STALE {m.group(0)!r}: {why}"))


# ── main ────────────────────────────────────────────────────────────────────
CHECK_NAMES = {"a": "recompute", "b": "presence", "c": "coverage of main.tex",
               "d": "non-C1/C2 rule", "e": "stale strings"}


def run(ledger: Path = LEDGER, root: Path = ROOT, checks: str = "abcde") -> tuple[Report, list[dict]]:
    _JSON_CACHE.clear()
    _TEXT_CACHE.clear()
    rows = load_ledger(ledger)
    rep = Report()
    check_schema(rows, rep)
    if "a" in checks:
        check_recompute(rows, root, rep)
    if "b" in checks:
        check_presence(rows, root, rep)
    if "c" in checks:
        check_coverage(rows, root, rep)
    if "d" in checks:
        check_rule(rows, rep)
    if "e" in checks:
        check_stale(rows, root, rep)
    return rep, rows


def sync_lines(ledger: Path, root: Path = ROOT) -> int:
    """Rewrite the line column from where each value is found now; returns rows changed."""
    _TEXT_CACHE.clear()
    rows = load_ledger(ledger)
    where = locate(rows, root)
    changed = 0
    for r in rows:
        path = _resolve(r["file"], root)
        new = None
        if path.suffix.lower() == ".pdf" and path.exists():
            hits = [i + 1 for i, t in enumerate(pdf_pages(path)) if _norm_ws(r["value_as_written"]) in t]
            new = f"p{hits[0]}" if hits and r["line"] not in {f"p{h}" for h in hits} else None
        elif where.get(r["id"]):
            new = str(where[r["id"]][0])
        if new and new != r["line"]:
            r["line"] = new
            changed += 1
    with ledger.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows({c: r.get(c, "") for c in COLUMNS} for r in rows)
    _TEXT_CACHE.clear()
    return changed


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--ledger", type=Path, default=LEDGER)
    ap.add_argument("--checks", default="abcde", help="subset of a,b,c,d,e")
    ap.add_argument("-v", "--verbose", action="store_true", help="list every finding")
    ap.add_argument("--sync-lines", action="store_true",
                    help="write each row's current line (or PDF page) back to the ledger, then check")
    args = ap.parse_args(argv)
    checks = args.checks.replace(",", "")
    if args.sync_lines:
        print(f"synced {sync_lines(args.ledger, ROOT)} line number(s)")
    rep, rows = run(args.ledger, ROOT, checks)

    status = Counter(r.get("status", "?") for r in rows)
    print(f"Ledger {args.ledger.relative_to(ROOT) if args.ledger.is_relative_to(ROOT) else args.ledger}: {len(rows)} rows")
    print("  by status: " + ", ".join(f"{s} {status.get(s, 0)}" for s in STATUSES))
    scope = Counter(r.get("corpus_scope", "?") for r in rows)
    print("  by scope:  " + ", ".join(f"{s} {scope.get(s, 0)}" for s in SCOPES))
    if rep.schema:
        print(f"SCHEMA: {len(rep.schema)} problem(s)")
        for s in rep.schema:
            print("  " + s)
    for k in checks:
        f, w, p = rep.fails[k], rep.warns[k], rep.passes[k]
        print(f"({k}) {CHECK_NAMES[k]}: {p} ok, {len(f)} fail, {len(w)} warn")
        if args.verbose or k in "d":
            for rid, msg in f:
                print(f"    FAIL {rid}: {msg}")
            for rid, msg in w:
                print(f"    warn {rid}: {msg}")
        elif f:
            for rid, msg in f[:10]:
                print(f"    FAIL {rid}: {msg}")
            if len(f) > 10:
                print(f"    ... {len(f) - 10} more (use -v)")
    print("LEDGER CHECK " + ("FAILED" if rep.failed() else "PASSED"))
    return 1 if rep.failed() else 0


if __name__ == "__main__":
    sys.exit(main())
