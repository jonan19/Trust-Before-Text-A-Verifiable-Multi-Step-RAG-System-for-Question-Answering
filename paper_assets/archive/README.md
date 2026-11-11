# paper_assets/archive/

Superseded paper sources. **Nothing here is current.** Kept as the audit trail
behind the NLPIR draft, which was **never submitted** and has been replaced by
`paper/main.tex`.

| File | Status |
|---|---|
| `trust_before_text.tex` | The frozen v6 draft, 1,556 lines. Quotes the v6 figures (92.3% accuracy, 66.7% on Corpus 2, unsafe 4/32) which the system no longer produces. |
| `references.bib` | 31 entries, superseded. `paper/main.tex` cites 99 keys. |

**Canonical sources, in `paper/`:**

- `paper/main.tex` (2,455 lines) is the live paper. Every number in it is traced in
  `docs/NUMBERS_LEDGER.csv` and verified by `evaluation/check_ledger.py`.
- `paper/references.bib` is the live bibliography.

The figures and generation script in the parent `paper_assets/` directory are
**still live**: `paper/main.tex` references them. Only this subdirectory is archived.

Current measurements are in `docs/STATUS.md`; the number-of-record is
`numbers.md`.
