# paper/

The live paper. `main.tex` and `references.bib` moved here from the repository
root on 2026-11-11 so the root stops mixing the paper in with the pipeline
modules. Nothing about the paper's content changed in that move.

| File | What it is |
|---|---|
| `main.tex` | The paper, IEEEtran conference class, targeting IEEE Access. 2,455 lines. |
| `references.bib` | The live bibliography, 99 cited keys. |

The superseded v6 draft and its 31-entry bibliography are in
`../paper_assets/archive/`. The old NLPIR paper was never submitted.

## Figures live outside this directory, on purpose

`main.tex` includes its three figures with paths relative to the **repository
root**, not to this directory:

```
\includegraphics[width=\columnwidth]{paper_assets/fig4_confusion_matrix.pdf}
```

They are left that way deliberately, because those paths are what the Overleaf
bundle needs (see below). The consequence: **there is no LaTeX engine in this
repo, and if you add one, compile from the repository root**, not from inside
`paper/`:

```
pdflatex paper/main.tex        # correct: paper_assets/ resolves from the root
cd paper && pdflatex main.tex  # wrong: figures will not be found
```

If you ever need to compile from inside this directory, add
`\graphicspath{{./}{../}}` after `\usepackage{graphicx}` rather than rewriting
the three include paths; that form works both here and in the bundle.

## The Overleaf bundle

Compilation happens on Overleaf, from a flat bundle. `overleaf_bundle.zip` at the
repository root is that bundle, and it is gitignored because it is regenerable.
Its layout puts the paper at the zip root with the figures beside it, which is
why the include paths above are correct there:

```
main.tex                                 <- paper/main.tex
references.bib                           <- paper/references.bib
paper_assets/fig4_confusion_matrix.pdf   <- paper_assets/fig4_confusion_matrix.pdf
paper_assets/fig5_ablation.pdf           <- paper_assets/fig5_ablation.pdf
paper_assets/fig6_nli_separation.pdf     <- paper_assets/fig6_nli_separation.pdf
```

Rebuild it by zipping exactly those five files at exactly those paths. The two
`paper/` files go to the **zip root**; the figures keep their `paper_assets/`
prefix. Overleaf compile order: `pdflatex`, `bibtex`, `pdflatex`, `pdflatex`.

## Every number in here is verified

`docs/NUMBERS_LEDGER.csv` has one row per numeric claim in `main.tex`, 450 of
them, and `evaluation/check_ledger.py` checks each one: it recomputes the value
from the result files, confirms the text is present, and confirms that **every**
number in the body is covered by a row.

Run it after any edit to `main.tex`, and pass `--sync-lines` when text has
moved:

```
python evaluation/check_ledger.py -v
python evaluation/check_ledger.py --sync-lines -v
```

If a number changes, `numbers.md` is updated first and everything else is made
to match it. That order is not optional; see `claude.md`.
