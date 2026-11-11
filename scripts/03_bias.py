"""
03_bias.py  --  误分类偏倚分析（本研究核心）

三种互补分析：
  A. 识别界（identification region）：不设先验，穷举能产生观测数据的 (Se, Sp)，
     给出真实 OR 的可行区间，并求临界特异度 Sp*（低于此值无可行解）。
  B. 外部锚定部分识别：用独立的美国 IBD 患病率估计锚定 Sp，把 OR 收窄成区间。
  C. 概率偏倚分析（Monte Carlo）：对 (Se, 真实患病率) 设先验，反解 Sp，得 OR 分布。

输出：results/bias_grid.csv, results/bias_anchored.csv, results/bias_mc.csv
"""
import os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
RES = os.path.join(ROOT, "results")

ANCHORS = {
    "Claims, treated IBD 0.4%": 0.004,
    "Claims, composite 0.7%": 0.0072,
    "NHIS 1999 0.9%": 0.009,
    "NHIS 2015 1.3%": 0.013,
}


def observed_cells(d, expo, outc):
    s = d[[expo, outc, "WTMEC2YR"]].dropna()
    w = s.WTMEC2YR.values / s.WTMEC2YR.sum()
    e, o = s[expo].values, s[outc].values
    return np.array([w[(e == 1) & (o == 1)].sum(), w[(e == 1) & (o == 0)].sum(),
                     w[(e == 0) & (o == 1)].sum(), w[(e == 0) & (o == 0)].sum()])


def correct(cells, se, sp):
    """闭式反演：返回 (OR, 隐含真实暴露比例, 可行性)"""
    a, b, c, d = cells
    det = se * sp - (1 - sp) * (1 - se)
    if abs(det) < 1e-12:
        return np.nan, np.nan, False
    # 结局+ 层：真暴露 / 真非暴露
    t1e = (sp * a - (1 - sp) * c) / det
    t1u = (-(1 - se) * a + se * c) / det
    # 结局- 层
    t0e = (sp * b - (1 - sp) * d) / det
    t0u = (-(1 - se) * b + se * d) / det
    if min(t1e, t1u, t0e, t0u) <= 0:
        return np.nan, np.nan, False
    orv = (t1e * t0u) / (t1u * t0e)
    return orv, t1e + t0e, True


def critical_sp(cells, se):
    """给定 Se，求使解可行的最小 Sp（二分）"""
    lo, hi = 0.5, 0.999999
    if correct(cells, se, hi)[2] is False:
        return np.nan
    for _ in range(80):
        mid = (lo + hi) / 2
        if correct(cells, se, mid)[2]:
            hi = mid
        else:
            lo = mid
    return hi


def main():
    d = pd.read_csv(os.path.join(DATA, "analysis.csv"))
    d = d[d.WTMEC2YR > 0]

    grid_rows, anchor_rows, mc_rows, region_rows = [], [], [], []

    for expo in ["ibd_self", "ibd_verif"]:
        for outc in ["sleep_disorder", "sleep_trouble", "short_sleep"]:
            cells = observed_cells(d, expo, outc)
            obs_or = (cells[0] * cells[3]) / (cells[1] * cells[2])
            p_obs = cells[0] + cells[1]

            # ---- A. 识别界 ----
            ses = np.arange(0.50, 0.96, 0.01)
            sps = np.arange(0.95, 0.99999, 0.0001)
            lo_or, hi_or = np.inf, -np.inf
            crit = []
            for se in ses:
                crit.append(critical_sp(cells, se))
                for sp in sps:
                    orv, _, ok = correct(cells, se, sp)
                    if ok:
                        lo_or, hi_or = min(lo_or, orv), max(hi_or, orv)
            region_rows.append({
                "definition": expo, "outcome": outc,
                "observed_OR": round(obs_or, 2),
                "region_low": round(lo_or, 2), "region_high": round(hi_or, 2),
                "critical_Sp_range": f"{np.nanmin(crit):.4f}-{np.nanmax(crit):.4f}"})

            for se in [0.90, 0.80, 0.70, 0.60, 0.50]:
                for sp in [0.9999, 0.999, 0.995, 0.990, 0.980]:
                    orv, prev, ok = correct(cells, se, sp)
                    grid_rows.append({
                        "definition": expo, "outcome": outc,
                        "observed_OR": round(obs_or, 2), "Se": se, "Sp": sp,
                        "adjusted_OR": round(orv, 2) if ok else np.nan,
                        "implied_true_prev_pct": round(100 * prev, 3) if ok else np.nan,
                        "feasible": bool(ok)})

            # ---- B. 外部锚定 ----
            for name, p_true in ANCHORS.items():
                for se in [0.60, 0.75, 0.85, 0.95]:
                    sp = 1 - (p_obs - se * p_true) / (1 - p_true)
                    if not (0 < sp < 1):
                        continue
                    orv, prev, ok = correct(cells, se, sp)
                    anchor_rows.append({
                        "definition": expo, "outcome": outc, "anchor": name,
                        "anchor_prev_pct": round(100 * p_true, 2), "Se": se,
                        "implied_Sp": round(sp, 5),
                        "adjusted_OR": round(orv, 2) if ok else np.nan,
                        "feasible": bool(ok)})

            # ---- C. Monte Carlo ----
            rng = np.random.default_rng(20261108)
            nsim = 20000
            se_s = rng.beta(8.0, 2.0, nsim)          # 均值 0.80
            p_true_s = rng.uniform(0.004, 0.013, nsim)
            sp_s = 1 - (p_obs - se_s * p_true_s) / (1 - p_true_s)
            ok = (sp_s > 0) & (sp_s < 1)
            ors = []
            for i in np.where(ok)[0]:
                orv, _, good = correct(cells, se_s[i], sp_s[i])
                if good:
                    ors.append(orv)
            ors = np.array(ors)
            mc_rows.append({
                "definition": expo, "outcome": outc, "observed_OR": round(obs_or, 2),
                "pct_inadmissible": round(100 * (1 - len(ors) / nsim), 1),
                "median_OR": round(np.median(ors), 2) if len(ors) else np.nan,
                "q2.5": round(np.percentile(ors, 2.5), 2) if len(ors) else np.nan,
                "q97.5": round(np.percentile(ors, 97.5), 2) if len(ors) else np.nan})

    pd.DataFrame(grid_rows).to_csv(os.path.join(RES, "bias_grid.csv"), index=False)
    pd.DataFrame(anchor_rows).to_csv(os.path.join(RES, "bias_anchored.csv"), index=False)
    pd.DataFrame(mc_rows).to_csv(os.path.join(RES, "bias_mc.csv"), index=False)
    reg = pd.DataFrame(region_rows)
    reg.to_csv(os.path.join(RES, "bias_region.csv"), index=False)

    print("== 识别界 ==")
    print(reg.to_string(index=False))
    print("\n== Monte Carlo ==")
    print(pd.DataFrame(mc_rows).to_string(index=False))
    print("\n== 外部锚定（自报定义 / sleep_disorder）==")
    a = pd.DataFrame(anchor_rows)
    print(a[(a.definition == "ibd_self") & (a.outcome == "sleep_disorder")].to_string(index=False))


if __name__ == "__main__":
    main()
