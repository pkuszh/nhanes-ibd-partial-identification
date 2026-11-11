"""
04_audit.py  --  文献报告率审计

PubMed 检索 NHANES × IBD，人工筛选出真正使用 NHANES 自报 IBD 条目的二次分析，
编码：是否讨论验证状态 / 是否做定义敏感性分析 / 是否做定量偏倚分析 / 是否给出病例数。

注：筛选为人工完成（见 INCLUDE 列表），关键词编码仅用于初筛，最终以人工判读为准。
"""
import os
import re
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")

# 人工筛选：真正以 NHANES 自报 IBD（ARQ125C/D）为暴露或结局的二次分析
INCLUDE = {
    "26422462": "Cannabis use in IBD",
    "28395506": "IBD and depressive symptoms",
    "28689150": "Urinary phenolics and IBD",
    "29666980": "Uveitis epidemiology",
    "32939644": "Copper/zinc intake and IBD",
    "33409918": "Iron intake and IBD",
    "36090851": "Sleep quality and IBD",
    "36147868": "Axial pain/arthritis in IBD",
    "37223580": "IBD prevalence (surveillance)",
    "38111604": "UC and PSA",
    "38643975": "DII and IBD",
    "39209366": "EPA/DHA and IBD",
    "39313067": "Environmental phenols and UC",
    "39397029": "Visceral adiposity index and IBD",
    "40097943": "Vitamin C/D/K and IBD",
    "39700661": "Nutrient intake and IBD",
    "40342858": "Non-HDL/HDL ratio and IBD",
    "40600201": "Caffeine and IBD",
    "42184804": "IBD and anxiety/depression",
    "42162818": "Cadmium and intestinal inflammation",
}

PATTERNS = {
    "reports_verification": r"colonoscop|endoscop|medical record|chart review|biops|histolog|validat",
    "discusses_misclass": r"misclassif|recall bias|inaccurat|self-report(ed)? (diagnosis|data) (may|is)",
    "sensitivity_by_definition": r"sensitivit(y|ies) analys|alternative definition|robustness check",
    "reports_n_cases": r"\b\d{2,4}\s+(patients|participants|cases)\b",
}


def main():
    raw = pd.read_csv(os.path.join(RES, "lit_audit_raw.csv"), dtype={"pmid": str})
    sub = raw[raw.pmid.isin(INCLUDE)].copy()
    sub["topic"] = sub.pmid.map(INCLUDE)

    for k, p in PATTERNS.items():
        sub[k] = sub.abstract.fillna("").str.lower().str.contains(p, regex=True).astype(int)

    sub = sub[["pmid", "year", "journal", "topic", "title",
               "reports_verification", "discusses_misclass",
               "sensitivity_by_definition"]]
    sub = sub.sort_values("year")
    sub.to_csv(os.path.join(RES, "lit_audit.csv"), index=False)

    n = len(sub)
    print(f"筛选后纳入二次分析: {n} 篇")
    print(f"距今跨度: {sub.year.min()}–{sub.year.max()}")
    for k in ["reports_verification", "discusses_misclass", "sensitivity_by_definition"]:
        print(f"  {k}: {int(sub[k].sum())}/{n} ({100*sub[k].mean():.0f}%)")
    print("\n按年份:")
    print(sub.year.value_counts().sort_index().to_string())
    print("\n涉及验证状态的文献:")
    print(sub[sub.reports_verification == 1][["year", "journal", "topic"]].to_string(index=False))


if __name__ == "__main__":
    main()
