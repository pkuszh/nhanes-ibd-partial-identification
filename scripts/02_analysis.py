"""
02_analysis.py  --  基于调查设计的估计（Taylor 线性化）
产出：
  results/t1_prevalence.csv     三种定义下的加权患病率
  results/t2_sleep_by_ibd.csv   各定义下睡眠结局的加权比例
  results/t3_or.csv             各定义下的关联 OR（粗 / 年龄性别调整 / 全调整）

设计：NHANES 2009-2010，SDMVSTRA(15) × SDMVPSU(3)，WTMEC2YR 权重。
ARQ 为 MEC 现场问卷，故使用 MEC 权重；单周期无需合并权重。
"""
import os
import numpy as np
import pandas as pd
from scipy import stats

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
RES = os.path.join(ROOT, "results")

DEFS = ["ibd_self", "ibd_verif"]
OUTCOMES = ["sleep_disorder", "sleep_trouble", "short_sleep"]


# ---------------- 设计基础函数 ----------------
def _design(df):
    return df["SDMVSTRA"].astype(int).values, df["SDMVPSU"].astype(int).values


def svy_mean(y, w, strata, psu):
    """加权比例 + Taylor 线性化方差"""
    m = ~np.isnan(y)
    y, w, strata, psu = y[m], w[m], strata[m], psu[m]
    W = w.sum()
    p = (w * y).sum() / W
    z = w * (y - p) / W
    var = 0.0
    for h in np.unique(strata):
        sel = strata == h
        if sel.sum() < 2:
            continue
        zh = z[sel]
        ph = psu[sel]
        upsu = np.unique(ph)
        if len(upsu) < 2:
            continue
        zbar = zh.mean()
        var += (len(upsu) / (len(upsu) - 1)) * ((zh - zbar) ** 2).sum()
    return p, np.sqrt(var)


def svy_logit(y, X, w, strata, psu, maxit=60):
    """加权 logistic（拟似然）+ 分层整群三明治方差"""
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    w = np.asarray(w, float)
    beta = np.zeros(X.shape[1])
    for _ in range(maxit):
        eta = X @ beta
        mu = 1 / (1 + np.exp(-eta))
        Wd = w * mu * (1 - mu)
        H = X.T @ (X * Wd[:, None])
        g = X.T @ (w * (y - mu))
        step = np.linalg.solve(H + 1e-9 * np.eye(len(beta)), g)
        beta += step
        if np.max(np.abs(step)) < 1e-8:
            break
    eta = X @ beta
    mu = 1 / (1 + np.exp(-eta))
    Wd = w * mu * (1 - mu)
    A = X.T @ (X * Wd[:, None])
    Ainv = np.linalg.inv(A)
    z = (w * (y - mu))[:, None] * X
    meat = np.zeros((X.shape[1], X.shape[1]))
    for h in np.unique(strata):
        sel = strata == h
        if sel.sum() < 2:
            continue
        ups = np.unique(psu[sel])
        if len(ups) < 2:
            continue
        Z = np.vstack([z[sel & (psu == u)].sum(0) for u in ups])
        Zc = Z - Z.mean(0)
        meat += (len(ups) / (len(ups) - 1)) * Zc.T @ Zc
    V = Ainv @ meat @ Ainv
    return beta, np.sqrt(np.diag(V))


def dummy(series, levels, ref):
    return np.column_stack([(series == l).astype(float) for l in levels if l != ref])


# ---------------- 主流程 ----------------
def main():
    d = pd.read_csv(os.path.join(DATA, "analysis.csv"))
    d = d[d.WTMEC2YR > 0].copy()
    strata, psu = _design(d)
    w = d.WTMEC2YR.values

    # --- T1 患病率 ---
    rows = []
    for name, col in [("Self-reported IBD", "ibd_self"),
                      ("Colonoscopy-verified IBD", "ibd_verif"),
                      ("Ulcerative colitis (self-report)", "uc_self"),
                      ("Crohn's disease (self-report)", "cd_self")]:
        y = d[col].values
        p, se = svy_mean(y, w, strata, psu)
        n = int(np.nansum(y))
        rows.append({"definition": name, "n_cases": n,
                     "weighted_prev_pct": round(100 * p, 2),
                     "se_pct": round(100 * se, 2),
                     "ci_low": round(100 * (p - 1.96 * se), 2),
                     "ci_high": round(100 * (p + 1.96 * se), 2)})
    t1 = pd.DataFrame(rows)
    t1.to_csv(os.path.join(RES, "t1_prevalence.csv"), index=False)

    # --- T2 睡眠结局的加权比例 ---
    rows = []
    for dfn in DEFS:
        for oc in OUTCOMES:
            sub = d[[dfn, oc]].dropna()
            idx = d.index.isin(sub.index)
            for g, lab in [(1, "IBD"), (0, "non-IBD")]:
                m = (sub[dfn] == g).values
                y = sub[oc].values
                mm = m
                p, se = svy_mean(y[mm], w[idx][mm], strata[idx][mm], psu[idx][mm])
                rows.append({"definition": dfn, "outcome": oc, "group": lab,
                             "n": int(mm.sum()), "weighted_pct": round(100 * p, 1),
                             "se_pct": round(100 * se, 1)})
    t2 = pd.DataFrame(rows)
    t2.to_csv(os.path.join(RES, "t2_sleep_by_ibd.csv"), index=False)

    # --- T3 关联 OR ---
    rows = []
    for dfn in DEFS:
        for oc in OUTCOMES:
            cols = [dfn, oc, "age", "female", "race", "edu", "pir", "bmi", "smoke", "depressed", "WTMEC2YR"]
            sub = d[cols].dropna()
            idx = d.index.isin(sub.index)
            y = sub[oc].values
            x0 = sub[dfn].values
            X1 = np.column_stack([np.ones(len(sub)), x0])
            X2 = np.column_stack([X1, sub.age.values, sub.female.values])
            X3 = np.column_stack([X2,
                                  dummy(sub.race, [1, 2, 3, 4, 5], 3),
                                  sub.edu.values, sub.pir.values, sub.bmi.values,
                                  dummy(sub.smoke, [0, 1, 2], 0),
                                  sub.depressed.values])
            for mname, X in [("crude", X1), ("age+sex", X2), ("fully adjusted", X3)]:
                b, se = svy_logit(y, X, sub.WTMEC2YR.values,
                                  strata[idx], psu[idx])
                orv = np.exp(b[1])
                lo = np.exp(b[1] - 1.96 * se[1])
                hi = np.exp(b[1] + 1.96 * se[1])
                rows.append({"definition": dfn, "outcome": oc, "model": mname,
                             "n": len(sub), "n_exposed": int(x0.sum()),
                             "OR": round(orv, 2), "ci_low": round(lo, 2),
                             "ci_high": round(hi, 2),
                             "p": round(2 * (1 - stats.norm.cdf(abs(b[1] / se[1]))), 4)})
    t3 = pd.DataFrame(rows)
    t3.to_csv(os.path.join(RES, "t3_or.csv"), index=False)

    print(t1.to_string(index=False))
    print()
    print(t3.to_string(index=False))
    print()
    print(t2.to_string(index=False))


if __name__ == "__main__":
    main()
