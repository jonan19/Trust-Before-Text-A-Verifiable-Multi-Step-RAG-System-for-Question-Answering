"""
Generate the data-driven figures for the Trust Before Text paper (main.tex).

Fig. 4 and Fig. 6 are read from result files in evaluation/results/, so they
change only when those files do:
  Fig. 4  baseline_corpus{1,2}.json (frozen) and rerun_corpus{1,2}.json (current)
  Fig. 6  nli_scores_corpus{1,2}.json (python evaluation/nli_scores.py --corpus N)
Fig. 5 (the frozen-system ablation) has no result file; its three values are
the v6 history in numbers.md section 6 (ledger MT-095 to MT-097).

    python paper_assets/make_figures.py

Outputs .pdf (for LaTeX) and .png (for preview) next to this script.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).parent
RES = OUT.parent / "evaluation" / "results"
LABELS = ["answer", "conflict", "insufficient"]
SHOWN = ["Answer", "Conflict", "Insuff."]

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 11,
    "axes.linewidth": 0.8,
    "savefig.bbox": "tight",
    "savefig.dpi": 200,
})


def load(name):
    return json.loads((RES / name).read_text(encoding="utf-8"))


def save(fig, name):
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"{name}.{ext}")
    plt.close(fig)
    print("wrote", name)


# ---------------------------------------------------------------- Fig 4: confusion matrices
def confusion(results):
    cm = np.zeros((3, 3), dtype=int)
    for r in results:
        cm[LABELS.index(r["expected"]), LABELS.index(r["observed"])] += 1
    return cm


panels = [("Corpus 1, frozen", "baseline_corpus1.json"),
          ("Corpus 1, current", "rerun_corpus1.json"),
          ("Corpus 2, frozen", "baseline_corpus2.json"),
          ("Corpus 2, current", "rerun_corpus2.json")]
fig, axes = plt.subplots(2, 2, figsize=(6.4, 6.0))
for ax, (title, name) in zip(axes.flat, panels):
    cm = confusion(load(name)["results"])
    acc = np.trace(cm)
    ax.imshow(cm, cmap="Blues", vmin=0, vmax=46)
    ax.set_xticks(range(3)); ax.set_xticklabels(SHOWN, fontsize=9)
    ax.set_yticks(range(3)); ax.set_yticklabels(SHOWN, fontsize=9)
    for i in range(3):
        for j in range(3):
            v = cm[i, j]
            ax.text(j, i, str(v), ha="center", va="center", fontsize=12,
                    fontweight="bold", color="white" if v > 23 else "black")
    ax.set_title(f"{title}: {acc}/78", fontsize=10)
for ax in axes[1]:
    ax.set_xlabel("System decision", fontsize=10)
for ax in axes[:, 0]:
    ax.set_ylabel("Gold label", fontsize=10)
fig.tight_layout()
save(fig, "fig4_confusion_matrix")

# ---------------------------------------------------------------- Fig 5: ablation bar chart
configs = ["Validation\nbaseline",
           "+ Sufficiency\nAND$\\rightarrow$OR",
           "+ NLI 0.94, no\ncomparison override"]
acc = [67.9, 83.3, 92.3]
frac = ["53/78", "65/78", "72/78"]
fig, ax = plt.subplots(figsize=(6.2, 4.0))
bars = ax.bar(range(3), acc, width=0.6,
              color=["#b0b7c6", "#6b8cc7", "#2f5597"], edgecolor="black", linewidth=0.6)
ax.set_ylim(0, 110)
ax.set_yticks(range(0, 101, 20))
ax.set_ylabel("Decision accuracy (%)")
ax.set_xticks(range(3)); ax.set_xticklabels(configs, fontsize=9)
ax.set_title("Frozen system, Corpus 1: cumulative effect of each change", fontsize=11)
for b, a, f in zip(bars, acc, frac):
    ax.text(b.get_x() + b.get_width() / 2, a + 1.5, f"{a:.1f}%\n({f})",
            ha="center", va="bottom", fontsize=9)
ax.grid(axis="y", linestyle=":", alpha=0.5)
save(fig, "fig5_ablation")

# ---------------------------------------------------------------- Fig 6: NLI score separation
fig, axes = plt.subplots(2, 1, figsize=(6.6, 4.8), sharex=True)
rng = np.random.default_rng(0)
for ax, c in zip(axes, ("1", "2")):
    d = load(f"nli_scores_corpus{c}.json")
    thr = d["meta"]["threshold"]
    rows = [r for r in d["results"] if r["max_nli"] is not None]
    gold_c = [r for r in rows if r["expected"] == "conflict"]
    other = [r for r in rows if r["expected"] != "conflict"]
    for y, group, marker, colour, name in (
            (1, gold_c, "o", "#2f5597", "gold conflict"),
            (0, other, "s", "#c0504d", "gold answer or gap")):
        if not group:
            continue
        xs = np.array([r["max_nli"] for r in group])
        flagged = np.array([r["observed"] == "conflict" for r in group])
        ys = y + rng.uniform(-0.12, 0.12, len(xs))
        if flagged.any():
            ax.scatter(xs[flagged], ys[flagged], s=48, marker=marker, color=colour,
                       edgecolor="black", linewidth=0.5, zorder=3,
                       label=f"{name}, flagged ({flagged.sum()})")
        if (~flagged).any():
            ax.scatter(xs[~flagged], ys[~flagged], s=48, marker=marker,
                       facecolor="white", edgecolor=colour, linewidth=1.0, zorder=3,
                       label=f"{name}, not flagged ({(~flagged).sum()})")
    ax.axvline(thr, color="black", linestyle="--", linewidth=1.1)
    ax.set_yticks([0, 1]); ax.set_yticklabels(["Answer / gap", "Conflict"])
    ax.set_ylim(-0.6, 1.6)
    ax.set_title(f"Corpus {c}, current system ({len(rows)} of 78 queries reach the NLI prong)",
                 fontsize=10)
    ax.legend(loc="center left", fontsize=7.5, framealpha=0.9)
    ax.grid(axis="x", linestyle=":", alpha=0.5)
    false_hi = sorted((r["max_nli"] for r in other if r["observed"] == "conflict"),
                      reverse=True)
    if false_hi:
        true_lo = min(r["max_nli"] for r in gold_c if r["observed"] == "conflict")
        ax.text(0.92, -0.42, f"false conflicts {', '.join(f'{s:.4f}' for s in false_hi)}; "
                f"lowest flagged true conflict {true_lo:.4f}",
                fontsize=7.5, ha="right", va="center")
axes[0].text(thr - 0.01, 1.45, f"threshold {thr}", fontsize=8, va="center", ha="right")
axes[1].set_xlabel("Highest NLI contradiction score among the query's candidate pairs")
axes[1].set_xlim(-0.02, 1.02)
fig.tight_layout()
save(fig, "fig6_nli_separation")

print("done")
