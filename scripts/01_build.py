"""
01_build.py  --  NHANES 2009-2010 分析数据集构建
目的：构建自报 IBD / 结肠镜确诊 IBD 两种定义、睡眠结局、协变量与调查设计变量。

数据来源（CDC NHANES 公共数据，2009-2010 周期）：
  DEMO_F   人口学、权重、设计变量
  ARQ_F    关节炎专项问卷（含 ARQ125C=UC, ARQ125D=CD, ARQ135C/D=诊断时结肠镜） <- IBD 条目唯一来源
  SLQ_F    睡眠（SLD010H 睡眠时长, SLQ050 睡眠困扰, SLQ060 睡眠障碍诊断）
  BMX_F    体格测量（BMI）
  SMQ_F    吸烟
  DPQ_F    抑郁（PHQ-9）
  DR1TOT_F 24h 膳食（第 1 天，DII 备用）

输出：data/analysis.csv
"""
import os
import urllib.request
import pandas as pd
import numpy as np

BASE = "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2009/DataFiles/"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
FILES = ["DEMO_F", "ARQ_F", "SLQ_F", "BMX_F", "SMQ_F", "DPQ_F", "DR1TOT_F"]


def fetch(name):
    path = os.path.join(DATA, f"{name}.xpt")
    if not os.path.exists(path) or os.path.getsize(path) < 10000:
        urllib.request.urlretrieve(BASE + name + ".XPT", path)
    return pd.read_sas(path, encoding="infer")


def main():
    demo = fetch("DEMO_F")[[
        "SEQN", "RIDAGEYR", "RIAGENDR", "RIDRETH1", "DMDEDUC2",
        "INDFMPIR", "WTMEC2YR", "SDMVPSU", "SDMVSTRA",
    ]]
    arq = fetch("ARQ_F")[["SEQN", "ARQ125C", "ARQ125D", "ARQ135C", "ARQ135D"]]
    slq = fetch("SLQ_F")[["SEQN", "SLD010H", "SLQ050", "SLQ060"]]
    bmx = fetch("BMX_F")[["SEQN", "BMXBMI"]]
    smq = fetch("SMQ_F")
    dpq = fetch("DPQ_F")
    dr = fetch("DR1TOT_F")[["SEQN", "DR1TKCAL", "DR1TPROT", "DR1TFIBE", "DR1TSFAT",
                            "DR1TMFAT", "DR1TPFAT", "DR1TCHOL", "WTDRD1"]]

    # 吸烟：SMQ020 是否吸过 100 支；SMQ040 现在是否吸
    sm = smq[["SEQN", "SMQ020", "SMQ040"]].copy()
    sm["smoke"] = np.select(
        [(sm.SMQ020 == 2), (sm.SMQ020 == 1) & (sm.SMQ040 == 3), (sm.SMQ020 == 1) & (sm.SMQ040.isin([1, 2]))],
        [0, 1, 2], default=np.nan)  # 0 从不, 1 既往, 2 现在

    # 抑郁：PHQ-9 总分（DPQ010-DPQ090，0-3 计分，7/9 视为缺失）
    phq_cols = [c for c in dpq.columns if c.startswith("DPQ0")][:9]
    phq = dpq[["SEQN"] + phq_cols].copy()
    for c in phq_cols:
        phq[c] = phq[c].replace({7: np.nan, 9: np.nan})
    phq["phq9"] = phq[phq_cols].sum(axis=1, min_count=7)

    d = demo.merge(arq, on="SEQN", how="inner") \
             .merge(slq, on="SEQN", how="left") \
             .merge(bmx, on="SEQN", how="left") \
             .merge(sm[["SEQN", "smoke"]], on="SEQN", how="left") \
             .merge(phq[["SEQN", "phq9"]], on="SEQN", how="left") \
             .merge(dr, on="SEQN", how="left")

    d = d[d.RIDAGEYR >= 20].copy()

    # ---- IBD 定义 ----
    # 缺失/拒答：ARQ125C/D 取值 7/9 -> NaN
    for c in ["ARQ125C", "ARQ125D", "ARQ135C", "ARQ135D"]:
        d[c] = d[c].where(d[c].isin([1, 2]))

    d["uc_self"] = (d.ARQ125C == 1).astype(float)
    d["cd_self"] = (d.ARQ125D == 1).astype(float)
    # 只要任一条目为"是"即判定为病例；两条目均为"否"判定为非病例；否则缺失
    d["ibd_self"] = np.where((d.ARQ125C == 1) | (d.ARQ125D == 1), 1.0,
                             np.where((d.ARQ125C == 2) & (d.ARQ125D == 2), 0.0, np.nan))

    # 确诊定义：自报且诊断当年做过结肠镜
    d["ibd_verif"] = (((d.ARQ125C == 1) & (d.ARQ135C == 1)) |
                      ((d.ARQ125D == 1) & (d.ARQ135D == 1))).astype(float)
    d.loc[d.ibd_self.isna(), "ibd_verif"] = np.nan

    # 严格定义：确诊 且 报告至少一项 IBD 肠外表现/相关病史（敏感性分析用，暂留接口）
    d["ibd_strict"] = d["ibd_verif"]

    # ---- 睡眠结局 ----
    d["sleep_hrs"] = d.SLD010H.where(d.SLD010H <= 14)
    d["short_sleep"] = (d.sleep_hrs < 7).astype(float)
    d.loc[d.sleep_hrs.isna(), "short_sleep"] = np.nan
    d["sleep_trouble"] = np.where(d.SLQ050 == 1, 1.0, np.where(d.SLQ050 == 2, 0.0, np.nan))
    d["sleep_disorder"] = np.where(d.SLQ060 == 1, 1.0, np.where(d.SLQ060 == 2, 0.0, np.nan))

    # ---- 协变量 ----
    d["age"] = d.RIDAGEYR
    d["female"] = (d.RIAGENDR == 2).astype(float)
    d["race"] = d.RIDRETH1
    d["edu"] = d.DMDEDUC2.where(d.DMDEDUC2 <= 5)
    d["pir"] = d.INDFMPIR
    d["bmi"] = d.BMXBMI
    d["depressed"] = (d.phq9 >= 10).astype(float)
    d.loc[d.phq9.isna(), "depressed"] = np.nan

    out = d[[
        "SEQN", "WTMEC2YR", "WTDRD1", "SDMVPSU", "SDMVSTRA",
        "age", "female", "race", "edu", "pir", "bmi", "smoke", "phq9", "depressed",
        "uc_self", "cd_self", "ibd_self", "ibd_verif",
        "ARQ135C", "ARQ135D",
        "sleep_hrs", "short_sleep", "sleep_trouble", "sleep_disorder",
        "DR1TKCAL", "DR1TFIBE", "DR1TPROT", "DR1TSFAT", "DR1TMFAT", "DR1TPFAT", "DR1TCHOL",
    ]].copy()

    out.to_csv(os.path.join(DATA, "analysis.csv"), index=False)
    print("N =", len(out))
    print("IBD self =", int(out.ibd_self.sum()), "| verified =", int(out.ibd_verif.sum()))
    print("Verified / self = %.1f%%" % (100 * out.ibd_verif.sum() / out.ibd_self.sum()))
    print("PSU:", out.SDMVPSU.nunique(), "Strata:", out.SDMVSTRA.nunique())
    return out


if __name__ == "__main__":
    main()
