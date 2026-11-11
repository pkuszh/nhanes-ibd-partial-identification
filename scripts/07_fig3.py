"""
07_fig3.py  --  Figure 3: Monte Carlo 分布 + 四种区间的嵌套比较

Panel A: 主结局（ibd_self × sleep_disorder）的偏倚调整 OR 分布（20,000 次抽样），
         叠加已发表的调整 OR 及其 95% CI。
Panel B: 同一估计量的五种区间，按假设从少到多排列（宽→窄）：
         识别区域 → 锚定区域 → Monte Carlo → 已发表 CI。
         信息：已发表的 CI 是最窄的，因为它假设得最多（Sp = 1）。

复用 scripts/03_bias.py 的 correct()/observed_cells()，并用与 03 完全相同的
随机种子与先验重跑 MC，断言与 bias_mc.csv 一致（可复现性检查）。

输出：results/mc_draws_primary.csv, results/fig3_mc.png
"""
import os
import importlib.util

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")

BLUE, RED, GRAY = "#185FA5", "#A32D2D", "#5F5E5A"

# ---- 复用 03 的函数 ----
spec = importlib.util.spec_from_file_location(
    "bias03", os.path.join(ROOT, "scripts", "03_bias.py"))
b03 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b03)

d = pd.read_csv(os.path.join(ROOT, "data", "analysis.csv"))
d = d[d.WTMEC2YR > 0]
cells = b03.observed_cells(d, "ibd_self", "sleep_disorder")

# ---- 重跑 MC（与 03_bias.py 完全一致的种子与先验）----
rng = np.random.default_rng(20261108)
nsim = 20000
se_s = rng.beta(8.0, 2.0, nsim)
p_true_s = rng.uniform(0.004, 0.013, nsim)
p_obs = float(cells[:2].sum() / cells.sum())      # 观测表观患病率
sp_s = 1 - (p_obs - se_s * p_true_s) / (1 - p_true_s)
ok = (sp_s > 0) & (sp_s < 1)
draws = []
for i in np.where(ok)[0]:
    orv, _, good = b03.correct(cells, se_s[i], sp_s[i])
    if good and np.isfinite(orv):
        draws.append(orv)
ors = np.array(draws)

mc = pd.read_csv(os.path.join(RES, "bias_mc.csv"))
row = mc[(mc.definition == "ibd_self") & (mc.outcome == "sleep_disorder")].iloc[0]
assert abs(np.median(ors) - row.median_OR) < 0.02, (np.median(ors), row.median_OR)
assert abs(np.percentile(ors, 2.5) - row["q2.5"]) < 0.02
assert abs(np.percentile(ors, 97.5) - row["q97.5"]) < 0.02
print(f"MC reproduced: n={len(ors)}, median={np.median(ors):.2f}, "
      f"95% [{np.percentile(ors, 2.5):.2f}, {np.percentile(ors, 97.5):.2f}]")

pd.DataFrame({"adjusted_OR": ors}).to_csv(
    os.path.join(RES, "mc_draws_primary.csv"), index=False)

PUB_PT, PUB_LO, PUB_HI = 2.94, 1.04, 8.29
med, lo, hi = np.median(ors), np.percentile(ors, 2.5), np.percentile(ors, 97.5)
out_ci = 100 * np.mean((ors < PUB_LO) | (ors > PUB_HI))
above_pt = 100 * np.mean(ors > PUB_PT)
above_diag = 100 * np.mean(ors > 11.64)   # 已诊断锚点区间上限
print(f"outside published CI: {out_ci:.1f}% | above published point: {above_pt:.1f}% "
      f"| above 11.64: {above_diag:.1f}%")

# ---- 区间清单（自上而下：假设最少 → 假设最多；区间由宽到窄）----
INTERVALS = [  # (label, low, high, point, color, assumption)
    ("Identification region\n(no priors)", 3.48, 273.66, None, BLUE,
     "only that Se, Sp reproduce the observed table"),
    ("Anchor-based region\n(all 4 anchors)", 3.81, 48.55, None, BLUE,
     "Sp implied by each published US prevalence"),
    ("Anchor-based region\ndiagnosed anchors only", 3.81, 11.64, None, BLUE,
     "as above, excluding treated-prevalence anchor"),
    ("Probabilistic bias analysis\n(20,000 draws)", lo, hi, med, BLUE,
     "priors: Se ~ Beta(8,2), prevalence ~ U(0.4%, 1.3%)"),
    ("Published adjusted model\n(assumes no measurement error)", PUB_LO, PUB_HI, PUB_PT, RED,
     "Sp = 1, implicitly"),
]

fig, (ax1, ax2) = plt.subplots(
    1, 2, figsize=(7.2, 3.9), dpi=200,
    gridspec_kw={"width_ratios": [1.12, 1.0], "wspace": 0.55})

# ================= Panel A =================
lx = np.log10(ors)
ax1.hist(lx, bins=70, color=BLUE, alpha=0.25, edgecolor="none", density=True)
ax1.axvspan(np.log10(lo), np.log10(hi), color=BLUE, alpha=0.12, lw=0,
            label=f"MC 95% simulation interval [{lo:.2f}, {hi:.2f}]")
ax1.axvline(np.log10(med), color=BLUE, lw=1.6,
            label=f"MC median {med:.2f}")
ax1.axvline(np.log10(PUB_PT), color=RED, lw=1.6,
            label=f"published adjusted OR {PUB_PT:.2f}")
ax1.axvline(np.log10(PUB_LO), color=RED, lw=1.0, ls="--")
ax1.axvline(np.log10(PUB_HI), color=RED, lw=1.0, ls="--",
            label=f"published 95% CI ({PUB_LO:.2f}, {PUB_HI:.2f})")

ax1.set_xlim(np.log10(0.9), np.log10(70))
ax1.set_xticks(np.log10([1, 2, 3, 5, 10, 20, 50]))
ax1.set_xticklabels(["1", "2", "3", "5", "10", "20", "50"], fontsize=7.5)
ax1.tick_params(axis="y", labelsize=7.5)
ax1.set_ylim(0, 1.0)
ax1.set_yticklabels([])                       # 密度轴无数值含义，隐藏刻度值
ax1.set_xlabel("Bias-adjusted odds ratio (IBD and sleep disorder)", fontsize=8.5)
ax1.set_ylabel("Density of Monte Carlo draws", fontsize=8.5)
ax1.set_title("A  The distribution of the bias-adjusted estimate",
              fontsize=9, loc="left")
ax1.legend(fontsize=6.6, frameon=False, loc="upper right",
           bbox_to_anchor=(1.0, 1.02), handlelength=1.6,
           labelspacing=0.35, borderaxespad=0.2)
ax1.text(0.02, 0.60,
         f"{out_ci:.0f}% of draws fall outside the\npublished 95% CI;\n"
         f"{above_pt:.0f}% exceed the published\npoint estimate",
         transform=ax1.transAxes, fontsize=7.0, color=GRAY, va="top",
         bbox=dict(facecolor="white", edgecolor="none", alpha=0.75, pad=1.5))

# ================= Panel B =================
ys = np.arange(len(INTERVALS))[::-1]
for y, (lab, l, h, pt, c, assum) in zip(ys, INTERVALS):
    ax2.plot([l, h], [y, y], color=c, lw=2.4 if pt is not None else 4.2,
             solid_capstyle="butt", alpha=0.95 if pt is not None else 0.55)
    if pt is not None:
        ax2.plot(pt, y, "o", color=c, ms=4.5, zorder=5)
    ax2.text(1.06, y, assum, fontsize=6.2, color=GRAY, va="center", ha="left",
             transform=ax2.get_yaxis_transform())

ax2.set_yticks(ys)
ax2.set_yticklabels([i[0] for i in INTERVALS], fontsize=7.2)
ax2.set_xscale("log")
ax2.set_xlim(0.9, 480)
ax2.set_xticks([1, 2, 5, 10, 50, 100, 300])
ax2.set_xticklabels(["1", "2", "5", "10", "50", "100", "300"], fontsize=7.5)
ax2.set_ylim(-0.7, len(INTERVALS) - 0.3)
ax2.set_xlabel("Odds ratio (log scale)", fontsize=8.5)
ax2.set_title("B  What each interval assumes", fontsize=9, loc="left")

for ax in (ax1, ax2):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(alpha=0.15, lw=0.5)
    ax.set_axisbelow(True)
    ax.tick_params(length=2.5)
ax2.tick_params(axis="y", length=0)

fig.savefig(os.path.join(RES, "fig3_mc.png"), bbox_inches="tight")
print("saved:", os.path.join(RES, "fig3_mc.png"))
