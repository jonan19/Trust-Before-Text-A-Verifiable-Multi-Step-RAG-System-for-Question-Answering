"""
Generate the data-driven figures for the Trust Before Text paper.
All numbers are hard-coded from PAPER_MASTER_BRIEF.md sec 4 / sec 8 (ground truth).
Outputs both .pdf (for LaTeX \\includegraphics) and .png (for quick preview).
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

OUT = Path(__file__).parent
plt.rcParams.update({
    "font.family": "serif",
    "font.size": 11,
    "axes.linewidth": 0.8,
    "savefig.bbox": "tight",
    "savefig.dpi": 200,
})

def save(fig, name):
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"{name}.{ext}")
    plt.close(fig)
    print("wrote", name)

# ---------------------------------------------------------------- Fig 4: confusion matrix
# rows = gold, cols = system decision. Brief sec 4.
cm = np.array([[40, 6, 0],
               [0, 16, 0],
               [0, 0, 16]])
labels = ["Answer", "Conflict", "Insufficient"]
fig, ax = plt.subplots(figsize=(5.0, 4.2))
im = ax.imshow(cm, cmap="Blues", vmin=0, vmax=cm.max())
ax.set_xticks(range(3)); ax.set_xticklabels(labels)
ax.set_yticks(range(3)); ax.set_yticklabels(labels)
ax.set_xlabel("System decision"); ax.set_ylabel("Gold label")
for i in range(3):
    for j in range(3):
        v = cm[i, j]
        ax.text(j, i, str(v), ha="center", va="center",
                color="white" if v > cm.max()*0.5 else "black",
                fontsize=14, fontweight="bold")
ax.set_title("Decision confusion matrix (78 queries)", fontsize=11)
fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="query count")
save(fig, "fig4_confusion_matrix")

# ---------------------------------------------------------------- Fig 5: ablation bar chart
configs = ["Baseline\n(validation on)",
           "+ Sufficiency\nAND→OR (Fix D)",
           "+ NLI 0.94 &\nno cmp. override (E,F)"]
acc = [67.9, 83.3, 92.3]
frac = ["53/78", "65/78", "72/78"]
fig, ax = plt.subplots(figsize=(6.2, 4.0))
bars = ax.bar(range(3), acc, width=0.6,
              color=["#b0b7c6", "#6b8cc7", "#2f5597"], edgecolor="black", linewidth=0.6)
ax.set_ylim(0, 100)
ax.set_ylabel("Decision accuracy (%)")
ax.set_xticks(range(3)); ax.set_xticklabels(configs, fontsize=9)
ax.set_title("Ablation: cumulative impact of architectural fixes", fontsize=11)
for i, (b, a, f) in enumerate(zip(bars, acc, frac)):
    ax.text(b.get_x()+b.get_width()/2, a+1.5, f"{a:.1f}%\n({f})",
            ha="center", va="bottom", fontsize=9)
ax.grid(axis="y", linestyle=":", alpha=0.5)
save(fig, "fig5_ablation")

# ---------------------------------------------------------------- Fig 6: NLI score separation
# Brief sec 8.
true_scores = [0.965, 0.995, 0.9955, 0.9958, 0.9958, 0.996,
               0.9981, 0.9981, 0.9981, 0.9981, 0.9998, 0.9999]
false_scores = [0.817, 0.834, 0.861, 0.867, 0.876, 0.919, 0.9996, 0.9998]
thr = 0.94
fig, ax = plt.subplots(figsize=(6.6, 3.6))
rng = np.random.default_rng(0)
def jitter(n): return rng.uniform(-0.08, 0.08, n)
ax.scatter(true_scores, np.full(len(true_scores), 1) + jitter(len(true_scores)),
           s=55, color="#2f5597", edgecolor="black", linewidth=0.5,
           label=f"True conflicts (n={len(true_scores)})", zorder=3)
ax.scatter(false_scores, np.full(len(false_scores), 0) + jitter(len(false_scores)),
           s=55, marker="s", color="#c0504d", edgecolor="black", linewidth=0.5,
           label=f"False conflicts (n={len(false_scores)})", zorder=3)
ax.axvline(thr, color="black", linestyle="--", linewidth=1.2)
ax.text(thr, 1.45, f" threshold = {thr}", fontsize=9, va="center")
ax.set_yticks([0, 1]); ax.set_yticklabels(["False", "True"])
ax.set_ylim(-0.5, 1.6)
ax.set_xlabel("NLI contradiction score")
ax.set_title("NLI score separation: true vs. false conflicts", fontsize=11)
ax.legend(loc="lower left", fontsize=8, framealpha=0.9)
ax.grid(axis="x", linestyle=":", alpha=0.5)
# annotate the two unremovable false positives above every true conflict
ax.annotate("2 false conflicts score above\nevery true conflict (unremovable)",
            xy=(0.9997, 0.08), xytext=(0.90, -0.35), fontsize=8,
            arrowprops=dict(arrowstyle="->", lw=0.7))
save(fig, "fig6_nli_separation")

print("done")
