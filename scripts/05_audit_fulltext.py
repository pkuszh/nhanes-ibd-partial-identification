"""
05_audit_fulltext.py  --  文献审计（修订版）

上一版（04_audit.py）只对 38 篇检索命中的摘要做关键词编码，得到的 "0/20 讨论误分类"
是不可靠的：摘要里通常不写局限段。本版改为两层：

  层 1（20 篇全集）：摘要级编码 —— 是否报告验证状态 / 是否做偏倚分析。
  层 2（可获取全文的子集）：人工逐篇核对局限段与讨论段，编码 4 个维度，
        并保留原文证据片段（evidence），供稿件与方法学附录使用。

输出：results/lit_audit_fulltext.csv, results/lit_audit_summary.md
"""

import os
import re
import glob
import html

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
FT = os.path.join(ROOT, "data", "fulltext")

# ---- 层 2：可获取全文的 11 篇，人工核对后的编码（evidence 为原文片段）----
# ack: 在局限/讨论中把"自报"作为问题提及（含"不能验证"这类表述）
# assert_valid: 反向地主张该条目可靠/与真实诊断一致
# quant: 对误分类幅度做任何定量处理（校正、PPV、与外部患病率比较后调整）
# altdef: 换用更严格定义或另一数据源重跑主分析
FULLTEXT_CODING = {
    "37223580": dict(
        label="Weisman 2023, Prev Med Rep",
        ack=1, assert_valid=0, quant=0, altdef=0, report_verif_status=1,
        evidence=("no clinical records were available, so we cannot validate the "
                  "self-reported medically diagnosed IBD estimates. The extent of "
                  "possible misdiagnosis cannot be determined"),
    ),
    "36147868": dict(
        label="Mayo Clin Proc Innov 2022 (axial pain in IBD)",
        ack=1, assert_valid=1, quant=0, altdef=0, report_verif_status=1,
        evidence=("these self-reports are generally consistent with actual "
                  "physician-diagnosed IBD. Cases of IBD from NHANES 2009-2010 had high "
                  "colonoscopy rates at diagnosis, increased rates of characteristic IBD "
                  "gastrointestinal symptoms, and IBD-related extraintestinal manifestations"),
    ),
    "28395506": dict(
        label="Gut Liver 2017 (IBD and depressive symptoms)",
        ack=1, assert_valid=0, quant=0, altdef=0, report_verif_status=0,
        evidence=("the study was based on self-reported history of IBD and DS, which can be "
                  "subject to recall bias"),
    ),
    "36090851": dict(
        label="Front Neurol 2022 (sleep quality and IBD)",
        ack=1, assert_valid=0, quant=0, altdef=0, report_verif_status=0,
        evidence=("the assessments of bowel health and sleep quality were based on "
                  "self-reports, which might not be accurate but serves as the only "
                  "conventional way in large epidemiological investigations"),
    ),
    "40600201": dict(
        label="J Multidiscip Healthc 2025 (caffeine and IBD)",
        ack=1, assert_valid=0, quant=0, altdef=0, report_verif_status=0,
        evidence=("bowel habits were defined by participants' self-reports, and the "
                  "information collected may be influenced by participants' subjective awareness"),
    ),
    "40097943": dict(
        label="BMC Gastroenterol 2025 (vitamins C, D, K and IBD)",
        ack=1, assert_valid=0, quant=0, altdef=0, report_verif_status=0,
        evidence=("IBD status was determined based on one self-reported question from the "
                  "participants, which is subject to potential bias. Future studies may consider "
                  "using physician diagnosis or other more objective tools for IBD assessment"),
    ),
    "40342858": dict(
        label="Front Physiol 2025 (non-HDL/HDL ratio and bowel health)",
        ack=1, assert_valid=0, quant=0, altdef=0, report_verif_status=0,
        evidence=("The reliance on self-reported data could also lead to inaccuracies in "
                  "assessing gut health status"),
    ),
    "29666980": dict(
        label="J Ophthalmic Inflamm Infect 2018 (uveitis)",
        ack=1, assert_valid=0, quant=0, altdef=0, report_verif_status=1,
        evidence=("recall bias may influence the results and add more uncertainty to the "
                  "prevalence estimate ... There is no evidence in the literature of the validity "
                  "of self-reported uveitis for epidemiologic studies"),
        notetype="selective scepticism",
        note=("reasons about sensitivity/specificity and direction for its "
              "OUTCOME (self-reported uveitis), then reports OR 11.3 and 22.2 for self-reported "
              "UC/CD as predictors without applying the same reasoning to its exposure"),
    ),
    # ---- 2026-11 补入的三篇（PDF 由作者提供，pypdf 提取）----
    "39209366": dict(
        label="Asia Pac J Clin Nutr 2024 (EPA/DHA and IBD)",
        ack=1, assert_valid=0, quant=0, altdef=0, report_verif_status=0,
        evidence=("the NHANES determined the presence of IBD based on a questionnaire, and did not "
                  "confirm this diagnosis with an endoscopic procedure, thereby likely leading to "
                  "some misreported data. In the future, endoscopic pathology should be used as a "
                  "diagnostic method"),
        notetype="reporting precision",
        note=("the most explicit statement in the set, and still no correction: the paper names "
              "the missing endoscopy, then reports quartile odds ratios as if the exposure were "
              "measured without error. It also calls the outcome \"incidence\" in 12 places and "
              "\"prevalence\" in 7 in a cross-sectional design, and attaches a direction (\"may "
              "underestimate the prevalence\") to the dietary limitation rather than to the "
              "diagnostic one"),
    ),
    "39397029": dict(
        label="Sci Rep 2024 (visceral adiposity index and bowel habits)",
        ack=1, assert_valid=0, quant=0, altdef=0, report_verif_status=0,
        evidence=("the information collected may have been influenced by participants' subjective "
                  "awareness ... because of the small number of IBD patients in the NHANES database "
                  "and the relatively inadequate sample size included, caution should be exercised "
                  "in interpreting IBD results"),
        notetype="reporting precision",
        note=("states that the IBD question was fielded only in 2009–2010 and restricts the analysis "
              "to 4,535 participants — correctly — but the abstract reports the 10,391-participant "
              "cohort, so the exposure-specific sample is invisible to anyone reading only the "
              "abstract"),
    ),
    "42184804": dict(
        label="Acta Psychol 2026 (IBD and anxiety/depression)",
        ack=1, assert_valid=0, quant=0, altdef=0, report_verif_status=1,
        evidence=("IBD status was based on self-reported physician diagnosis and could not be "
                  "verified against medical records, and Crohn's disease and ulcerative colitis "
                  "could not be reliably differentiated"),
        notetype="item provenance",
        note=("the Methods name MCQ160N and MCQ160O as the Crohn's and ulcerative colitis items. "
              "In the 2009-2010 cycle IBD is carried by ARQ125C and ARQ125D; MCQ160N asks about gout "
              "and MCQ160O is not fielded at all (MCQ_F holds 81 variables, none IBD-related). The "
              "reported case count, 56 of 6,398 (0.9%), matches an ARQ-based definition rather than "
              "the 4.5% gout item, so the analysis itself is probably unaffected -- but a reader "
              "cannot reconstruct which variable produced the exposure, and the paper calls the "
              "item \"physician-diagnosed\" in the same sentence that concedes it was never verified"),
    ),
    # ---- 2026-11-09 补入的六篇（作者提供 PDF，pypdf 提取）----
    "26422462": dict(
        label="Weiss 2015, Drug Alcohol Depend (cannabis use)",
        ack=1, assert_valid=0, quant=0, altdef=0, report_verif_status=1,
        evidence=("NHANES does not validate the response with a review of the medical record or "
                  "perform diagnostic testing relevant to IBD"),
        note=("the earliest user of the item, and the only one that states outright in Methods that "
              "the response is never validated against records. It even reports the colonoscopy rates "
              "(UC 73.4%, CD 96.5%) as descriptive detail but never uses them to argue validity or "
              "adjust anything; the limitation paragraph is spent on causality, not measurement. The "
              "abstract writes weighted counts as \"2084,895 subjects with IBD\" and calls a "
              "cross-sectional prevalence \"incidence\""),
    ),
    "32939644": dict(
        label="Biol Trace Elem Res 2021 (copper/zinc and IBD)",
        ack=0, assert_valid=0, quant=0, altdef=0, report_verif_status=0,
        evidence=("Our analysis has potential limitations. The cross-sectional design of the study is "
                  "a major limitation"),
        note=("the entire limitation discussion is one sentence about cross-sectional design; 56 IBD "
              "cases, weighted prevalence 1.14%, and the measurement of the case definition is never "
              "raised"),
    ),
    "33409918": dict(
        label="Biol Trace Elem Res 2021 (iron and IBD)",
        ack=0, assert_valid=0, quant=0, altdef=0, report_verif_status=0,
        evidence=("Causal inference between iron intake and chronic diarrhea cannot be made because of "
                  "the cross-sectional design of NHANES ... residual confounding by other unmeasured "
                  "factors cannot be excluded"),
        note=("despite the 2007-2010 span in its title, the IBD analysis is correctly restricted to "
              "the 2009-2010 cycle (47 cases of 4,043) while chronic diarrheal symptoms use the full "
              "span -- the honest way to handle the item's availability. The limitation list covers "
              "design and confounding only"),
    ),
    "38643975": dict(
        label="Clin Exp Pharmacol Physiol 2024 (dietary inflammatory index)",
        ack=1, assert_valid=0, quant=0, altdef=0, report_verif_status=0,
        evidence=("The NHANES database diagnoses IBD based on individual reports of study participants"),
        note=("uses the self-report fact as an interpretive lever -- patients may have changed their "
              "diets after diagnosis -- rather than as a measurement problem to be assessed; one of "
              "the two reports besides ours to locate the IBD questions correctly, as \"a sub-analysis "
              "of the Arthritis Questionnaire\" (the other is de Silva 2017)"),
    ),
    "39313067": dict(
        label="Clin Res Hepatol Gastroenterol 2024 (phenols and UC)",
        ack=0, assert_valid=0, quant=0, altdef=0, report_verif_status=0,
        evidence=("This is likely attributed to the limited number of UC cases in our sample and the "
                  "inclusion of too many confounders"),
        note=("attributes attenuated associations to case numbers and confounder count but never "
              "questions the UC label itself; covariates are described as self-reported throughout, "
              "the outcome never is"),
    ),
    "39700661": dict(
        label="Nutrition 2025 (nutrient intake and IBD, dose-response)",
        ack=1, assert_valid=0, quant=0, altdef=0, report_verif_status=0,
        evidence=("Another minor limitation is that our confirmation of IBD relies solely on the NHANES "
                  "2009-2010 survey questionnaire ... Some cases may be misdiagnosed or underreported, "
                  "potentially affecting the accuracy of our assessment of IBD incidence"),
        notetype="selective scepticism",
        note=("devotes a full paragraph to remediating dietary recall -- participant training, food "
              "frequency questionnaires, biomarkers, mobile apps -- while the disease-status item is "
              "filed under \"another minor limitation\"; the same self-report vocabulary, inverted "
              "priorities. Also calls a cross-sectional count \"incidence\""),
    ),
    "38111604": dict(
        label="Front Nutr 2023 (ulcerative colitis and PSA)",
        ack=1, assert_valid=0, quant=0, altdef=0, report_verif_status=0,
        evidence=("it is probable that information bias such as information on the UC and AGE that "
                  "was assessed through a questionnaire, which could affect the association, was "
                  "observed"),
        notetype="credibility inflation",
        note=("adds a two-sample Mendelian randomisation and concludes that \"the observations are "
              "more credible and reliable\"; the MR addresses confounding, not the questionnaire "
              "exposure, so the credibility claim is attached to the wrong bias"),
    ),
    "28689150": dict(
        label="de Silva 2017, Environ Pollut (urinary phenols and IBD)",
        ack=1, assert_valid=1, quant=0, altdef=0, report_verif_status=1,
        evidence=("The study database utilized does not allow us to obtain confirmatory medical "
                  "records ... and we relied on self reported outcomes. ... The prevalence of IBD "
                  "was limited to those respondents who completed the supplemental questionnaire "
                  "on arthritis and was not a chronic disease that is directly queried in the main "
                  "survey leading to a likely underestimation of disease prevalence"),
        notetype="credibility inflation",
        note=("the same Discussion that admits reliance on self-reported outcomes then declares "
              "\"Strengths of our study included the use of a well validated survey tool\", without "
              "excluding the one item that was neither directly queried nor validated. Second "
              "report (after Zhu 2024) to locate the item in the arthritis supplemental "
              "questionnaire; claims the item likely underestimates prevalence without "
              "quantification. Source is a scanned PDF with no text layer; passages transcribed "
              "from page images (data/fulltext/28689150_pdf.txt)"),
    ),
}

# ---- 仅摘要（2026-11-09 定稿）----
# 这几篇不参与层 2 分母；五个编码维度一律记 missing（None），**不得记 0**。
# obs 只记录"摘要里能确证的事"，不冒充全文编码。
# 注：Weiss 2015（26422462）原以为只有摘要，2026-11-09 作者拿到全文，已转入 FULLTEXT_CODING。
ABSTRACT_ONLY = {
    "42162818": dict(
        label="Xi 2026, Environ Pollut (cadmium burden)",
        obs=("abstract states the data span 2005-2010, but the IBD item exists only in 2009-2010, so "
             "the 63.6% excess in blood cadmium among participants with IBD is presented against a "
             "six-year frame that only two of those years can supply. No limitation statement, no "
             "validation of the exposure definition"),
    ),
}

# 层 1 关键词（只用于摘要，仅作粗筛；不作为结论依据）
ABS_PATTERNS = {
    "abs_mentions_validation": r"validat|medical record|chart review|confirm(ed)? diagnos",
    "abs_mentions_misclass": r"misclassif|misdiagnos|recall bias",
    "abs_mentions_sensitivity": r"sensitivit(y|ies) analys",
}


def main():
    base = pd.read_csv(os.path.join(RES, "lit_audit.csv"), dtype={"pmid": str})
    raw = pd.read_csv(os.path.join(RES, "lit_audit_raw.csv"), dtype={"pmid": str})
    base = base.merge(raw[["pmid", "abstract"]], on="pmid", how="left")
    for k, p in ABS_PATTERNS.items():
        base[k] = base.abstract.fillna("").str.contains(p, case=False, regex=True).astype(int)

    rows = []
    for _, r in base.iterrows():
        pmid = r.pmid
        if pmid in FULLTEXT_CODING:
            coverage = "full_text"
        elif pmid in ABSTRACT_ONLY:
            coverage = "abstract_only"
        else:
            coverage = "pending"
        rec = {
            "pmid": pmid, "year": r.year, "journal": r.journal,
            "topic": r.topic, "coverage": coverage,
            "fulltext_available": int(coverage == "full_text"),
            "abs_mentions_validation": r.abs_mentions_validation,
            "abs_mentions_misclass": r.abs_mentions_misclass,
            "abs_mentions_sensitivity": r.abs_mentions_sensitivity,
        }
        if pmid in FULLTEXT_CODING:
            rec.update(FULLTEXT_CODING[pmid])
            rec.setdefault("note", "")
            rec.setdefault("notetype", "")
            rec.setdefault("obs", "")
        else:
            rec.update({k: None for k in
                        ["ack", "assert_valid", "quant", "altdef", "report_verif_status",
                         "note", "notetype", "evidence"]})
            if pmid in ABSTRACT_ONLY:
                rec.update(ABSTRACT_ONLY[pmid])   # label + obs
            else:
                rec.update({"obs": ""})
        rows.append(rec)
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(RES, "lit_audit_fulltext.csv"), index=False)

    ft = df[df.fulltext_available == 1]
    ao = df[df.coverage == "abstract_only"]
    pend = df[df.coverage == "pending"]
    lines = []
    lines.append("# 文献审计（修订版）\n")
    lines.append(f"纳入分析：**{len(df)} 篇**（2015–2026，NHANES 自报 IBD 条目的二次分析）\n")
    lines.append(f"可获取全文：**{len(ft)} 篇**（Europe PMC 开放获取 + 作者提供）\n")
    lines.append(f"仅摘要：**{len(ao)} 篇**（订阅期刊，无 OA/PMC/作者稿，见下）；"
                 f"待补：**{len(pend)} 篇**\n")
    lines.append("## 层 1：全 20 篇（摘要级）\n")
    lines.append("| 指标 | 篇数 |\n|---|---|")
    lines.append(f"| 摘要提及验证/病历/确诊 | {int(df.abs_mentions_validation.sum())} |")
    lines.append(f"| 摘要提及误分类/回忆偏倚 | {int(df.abs_mentions_misclass.sum())} |")
    lines.append(f"| 摘要提及敏感性分析 | {int(df.abs_mentions_sensitivity.sum())} |")
    lines.append("\n> 摘要级检索只能作粗筛：摘要通常不含局限段，命中数低估真实讨论率。\n")
    lines.append(f"> 层 2 覆盖 {len(ft)}/{len(df)} 篇；"
                 f"{len(ao)} 篇仅摘要、{len(pend)} 篇待补，"
                 "见 manuscript/05_fulltext_retrieval_list.md。\n")
    lines.append(f"## 层 2：{len(ft)} 篇全文人工核对\n")
    lines.append("| 研究 | 提及自报问题 | 反向主张可靠 | 定量处理 | 换定义重跑 | 报告验证状态 |")
    lines.append("|---|---|---|---|---|---|")
    for _, r in ft.iterrows():
        lines.append(f"| {r.label} | {r.ack} | {r.assert_valid} | {r.quant} | {r.altdef} "
                     f"| {r.report_verif_status} |")
    if len(ao):
        lines.append(f"\n### 仅摘要的 {len(ao)} 篇（编码记 missing，不记 0）\n")
        lines.append("这五列一律作缺失处理：没有全文就不能判定「没提」，只能判定「不知道」。\n")
        lines.append("| 研究 | 摘要里能确证的事 |")
        lines.append("|---|---|")
        for _, r in ao.iterrows():
            lines.append(f"| {r.label} | {r.obs} |")
    lines.append("\n### 关键原文证据\n")
    for _, r in ft.iterrows():
        lines.append(f"- **{r.label}**（PMID {r.pmid}）：\"{r.evidence}\"")
    n_ack = int(ft.ack.fillna(0).sum())
    n_silent = int((ft.ack.fillna(0) == 0).sum())
    lines.append("\n## 结论（可写入稿件）\n")
    lines.append(f"- {n_ack}/{len(ft)} 篇全文在文字上承认自报条目有问题；"
                 f"**{n_silent} 篇连提都未提**（局限段只谈横断面设计与混杂）"
                 f"{'；' if n_silent else ''}"
                 f"**0/{len(ft)} 篇把该问题转化为任何定量处理**；**0/{len(ft)} 篇换用更严格定义重跑主分析**。")
    lines.append(f"- {int(ft.assert_valid.sum())}/{len(ft)} 篇反向主张该条目可靠，依据是结肠镜率与肠外表现"
                 "——正是本研究定量检验的那类论证。")
    if len(ao):
        n_ack = int(ft.ack.sum())
        lo, hi = int(ft.assert_valid.sum()), int(ft.assert_valid.sum()) + len(ao)
        lines.append(f"- **{len(ao)} 篇仅摘要的边界**：把它们的五个维度按最坏情况填满，"
                     f"提及率也不过从 {n_ack}/{len(ft)} 变成 {n_ack+len(ao)}/{len(df)}；"
                     f"反向主张可靠从 {lo} 篇升到 {hi} 篇——方向与量级都不变。"
                     "故「承认但未量化」这一结论不受全文缺失影响。")
    notes = [r for _, r in ft.iterrows() if str(r.get("note", ""))]
    if notes:
        kinds = len({r.get("notetype") for r in notes})
        lines.append(f"- {len(notes)} 篇有需要单独征引的细节，分 {kinds} 类：")
        for nt in ["selective scepticism", "credibility inflation", "reporting precision",
                   "item provenance"]:
            grp = [r for r in notes if r.get("notetype") == nt]
            if not grp:
                continue
            head = {
                "selective scepticism": "**选择性怀疑** —— 同一套词汇用在结局上，不用在自己的暴露上",
                "credibility inflation": "**可信度误挂** —— 用只处理混杂的方法，去担保测量误差",
                "reporting precision": "**报道口径** —— 摘要的样本量与真正支撑该估计的样本量不一致",
                "item provenance": "**条目溯源** —— 正文给出的变量名对不上该周期真实存在的条目",
            }[nt]
            lines.append(f"  - {head}")
            for r in grp:
                lines.append(f"    - **{r.label}**（PMID {r.pmid}）：{r.note}")
        grp0 = [r for r in notes if not r.get("notetype")]
        if grp0:
            lines.append("  - **其他** —— 细节值得征引，但不足以单独立类")
            for r in grp0:
                lines.append(f"    - **{r.label}**（PMID {r.pmid}）：{r.note}")
    lines.append(f"- 准确表述是：{n_ack}/{len(ft)} 篇「承认但未量化」（acknowledged but not analysed），"
                 f"{n_silent} 篇「只字未提」，**没有任何一篇做过定量处理**。"
                 "上一版 0/20 与 11/11 的说法均已废弃。")
    txt = "\n".join(lines) + "\n"
    open(os.path.join(RES, "lit_audit_summary.md"), "w", encoding="utf-8").write(txt)
    print(txt)
    print("saved:", os.path.join(RES, "lit_audit_fulltext.csv"))


if __name__ == "__main__":
    main()
