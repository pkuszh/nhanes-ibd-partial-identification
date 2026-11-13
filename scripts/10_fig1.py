"""
10_fig1.py  --  Figure 1: study flow and data structure

Three columns, matching the style of fig2/fig3 (colors, dpi, fonts):
  A  Participant flow      10,537 -> 5,106 -> 5,096 -> 3,976
  B  Exposure definitions  D1 (62) = 43 verified + 19 unverified -> D2
  C  Literature audit      38 screened -> 20 included -> 19 full text

All numbers are the manuscript's own; sourced from scripts/01-02-03 and
results/t1_prevalence.csv. If any number changes, regenerate.

Output: results/fig1_flow.png
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")

BLUE, RED, GRAY = "#185FA5", "#A32D2D", "#5F5E5A"
LIGHT = "#E8F0F8"   # blue box fill
LRED = "#F6E9E9"    # red box fill
LGRAY = "#F0F0EE"   # neutral box fill

fig, ax = plt.subplots(figsize=(7.2, 4.4), dpi=200)
ax.set_xlim(0, 10)
ax.set_ylim(0, 10)
ax.axis("off")


def box(x, y, w, h, text, fc=LIGHT, ec=BLUE, fs=7.0, tc="black", bold=False):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.06,rounding_size=0.08",
        facecolor=fc, edgecolor=ec, lw=0.9))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fs, color=tc, fontweight="bold" if bold else "normal",
            linespacing=1.35)


def varrow(x, y1, y2, color=GRAY):
    ax.add_patch(FancyArrowPatch(
        (x, y1), (x, y2), arrowstyle="-|>", mutation_scale=8,
        color=color, lw=0.9, shrinkA=1, shrinkB=1))


def side_label(x, y, text, color=GRAY, ha="left"):
    ax.text(x, y, text, ha=ha, va="center", fontsize=6.0, color=color,
            linespacing=1.3)


# ================= column A: participant flow (x 0.15-2.95) =================
ax.text(0.15, 9.7, "A  Participant flow", fontsize=9,
        ha="left", va="center", fontweight="bold")

box(0.15, 8.85, 2.8, 0.6, "NHANES 2009–2010 cycle\n10,537 participants")
varrow(1.55, 8.79, 8.14)
side_label(1.67, 8.46, "arthritis questionnaire\n(ages 20–69) after MEC")
box(0.15, 7.45, 2.8, 0.6, "5,106 with an ARQ record")
varrow(1.55, 7.39, 6.74)
side_label(1.67, 7.06, "12 answered “don’t know” to\n≥1 item (10 not definable)")
box(0.15, 6.05, 2.8, 0.6,
    "5,096 (99.8%) definable status\nweighted analyses", bold=True, fs=6.6)
varrow(1.55, 5.99, 5.34)
side_label(1.67, 5.66, "missing covariates\n(1,120 excluded, 22%)")
box(0.15, 4.65, 2.8, 0.6,
    "3,976 complete cases\nregression models (51 exposed)")

# ================= column B: exposure definitions (x 4.2-7.1) =================
ax.text(4.2, 9.7, "B  Exposure definitions", fontsize=9,
        ha="left", va="center", fontweight="bold")

box(4.2, 8.85, 2.9, 0.6,
    "Self-reported IBD (D1)\n62 cases — prevalence 1.23%", bold=True)
varrow(4.95, 8.79, 8.26)
varrow(6.35, 8.79, 8.26, color=RED)
box(4.2, 7.25, 1.5, 0.95,
    "Verified (D2)\n43 (69.4%)\n0.96%", fs=6.3)
box(5.9, 7.2, 1.2, 1.05,
    "Unverified\n19 (30.6%)\nno reported\ncolonoscopy", fc=LRED, ec=RED, fs=5.9)
varrow(4.95, 7.14, 6.74)
varrow(6.5, 7.14, 6.74)
box(4.2, 6.05, 2.9, 0.6,
    "Both definitions: prevalence, sleep models,\nmisclassification correction",
    fc="white", ec=BLUE, fs=6.3)

# ================= column C: literature audit (x 7.7-9.95) =================
ax.text(7.7, 9.7, "C  Literature audit", fontsize=9,
        ha="left", va="center", fontweight="bold")

box(7.7, 8.85, 2.25, 0.6, "PubMed search\n38 records screened", fc=LGRAY, ec=GRAY, fs=6.5)
varrow(8.825, 8.79, 8.14)
box(7.7, 7.45, 2.25, 0.6, "20 secondary analyses\nincluded", fc=LGRAY, ec=GRAY, fs=6.5)
varrow(8.825, 7.39, 6.74)
box(7.7, 6.05, 2.25, 0.6, "19 coded at full text,\n1 at abstract only", fc=LGRAY, ec=GRAY, fs=6.5)
varrow(8.825, 5.99, 5.34)
box(7.7, 4.65, 2.25, 0.6, "5-item coding scheme\n(Table 4, S6)", fc=LGRAY, ec=GRAY, fs=6.5)

# ================= bottom banner =================
box(0.15, 3.55, 9.8, 0.6,
    "Weighted 2×2 table → identification region: OR > 3.45, unbounded above → anchored region "
    "3.81–48.55 → Monte Carlo, 19,935 admissible draws (Figs 2–3)",
    fc="white", ec=BLUE, fs=6.2)
varrow(1.55, 4.59, 4.21)
varrow(5.65, 5.99, 4.21)
varrow(8.825, 4.59, 4.21)

# footnote
ax.text(0.15, 3.15,
        "D1 = self-reported IBD (ARQ125C/D); D2 = D1 plus reported colonoscopy at diagnosis "
        "(ARQ135C/D). Weighted estimates use MEC examination weights with\nTaylor linearisation. "
        "Regression models are complete-case. Audit coverage, exclusions and coding: "
        "Supplementary Tables S4 and S6.",
        fontsize=5.8, color=GRAY, ha="left", va="top", linespacing=1.45)

fig.savefig(os.path.join(RES, "fig1_flow.png"), bbox_inches="tight")
print("saved:", os.path.join(RES, "fig1_flow.png"))
