"""
06_retrieval_list.py  --  生成待补全文清单（供馆际互借/手工下载使用）

输入：results/lit_audit_fulltext.csv（谁已有全文）、results/refs_1_20.json（题录）
输出：manuscript/05_fulltext_retrieval_list.md

清单按「获取难度」排序：先重试可自动抓取的 OA，再走出版社 OA，最后进馆际互借。
"""
import json
import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
MS = os.path.join(ROOT, "manuscript")

# 有 PMCID 但抓取失败（Europe PMC 限流），重试即可
PMCID = {
    "38111604": "PMC10725916",
    "39397029": "PMC11471843",
    "39209366": "PMC11389807",
}
# 完全开放获取的出版社（可直接从官网 PDF 取）
GOLD_OA = {"Scientific reports", "Frontiers in nutrition", "Frontiers in physiology",
           "BMC gastroenterology", "Frontiers in neurology"}

# 每篇要看的地方：作者把自报问题写在哪一节（经验：局限段 > 讨论末段 > 方法学定义处）
FOCUS = {
    "26422462": "Methods 的 IBD 定义句 + Limitations 段；该文是早期使用者，看它有没有**任何**效度说明",
    "28689150": "Methods 定义 + Discussion 局限段；注意它同时用了 chronic diarrheal symptoms 作为次级结局",
    "32939644": "Limitations；铜/锌摄入与 IBD 的分析里是否提到 n 很小",
    "33409918": "Limitations；注意该文用了 2007–2010（跨周期），核对 IBD 条目实际可用年份",
    "38111604": "Limitations；UC 与 PSA 的关联，看是否讨论 UC 自报的假阳性",
    "38643975": "Limitations；DII 与 IBD，看是否提到反向因果（确诊后改饮食）",
    "39313067": "Limitations；UC 作为结局，看是否做定义敏感性分析",
    "39397029": "Limitations；VAI 与 bowel habits，看是否区分 IBD 与慢性腹泻",
    "39209366": "Limitations；EPA/DHA 与 IBD，看是否提测量误差",
    "39700661": "Limitations；剂量反应分析，看样条的自由度与病例数是否被讨论",
    "42162818": "Limitations；镉与肠道炎症，注意它把 IBD 与结肠炎小鼠模型并列",
    "42184804": "Limitations；IBD 与焦虑抑郁，与 Gut Liver 2017 属同型设计，可直接对比表述",
}


def route(pmid, journal, pmcid):
    if pmcid:
        return f"Europe PMC 重试（{pmcid}）"
    if journal in GOLD_OA:
        return "出版社 OA，官网 PDF"
    return "馆际互借 / 作者索取"


def main():
    df = pd.read_csv(os.path.join(RES, "lit_audit_fulltext.csv"), dtype={"pmid": str})
    refs = {str(pm): ref for _, pm, ref in
            json.load(open(os.path.join(RES, "refs_1_20.json"), encoding="utf-8"))}
    missing = df[df.fulltext_available == 0].copy()

    rows = []
    for _, r in missing.iterrows():
        pm = r.pmid
        rows.append({
            "PMID": pm,
            "年份": r.year,
            "期刊": r.journal,
            "题录": refs.get(pm, r.topic),
            "获取路径": route(pm, r.journal, PMCID.get(pm)),
            "重点看哪一节": FOCUS.get(pm, "Limitations 段"),
            "已有全文": int(r.fulltext_available),
        })
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(RES, "retrieval_queue.csv"), index=False)

    L = []
    pending = out[out["已有全文"] == 0]
    done = int(df.fulltext_available.sum())
    L.append(f"# 待补全文清单（{len(pending)} 篇）\n")
    L.append(f"当前审计覆盖 **{done}/20** 篇全文。这份清单是把它推到 20/20 的工作单。\n")
    L.append("> 优先级：A 组机器可抓，先做；C 组走馆际互借或向作者索取。\n")

    a = pending[pending["获取路径"].str.startswith("Europe PMC")]
    if not a.empty:
        L.append("## A 组：有 PMCID，Europe PMC 限流导致抓取失败（重试即可）\n")
        for _, r in a.iterrows():
            L.append(f"- [ ] {r['题录']}")
            L.append(f"      PMID {r['PMID']}｜{r['获取路径']}｜重点：{r['重点看哪一节']}")
        L.append("\n抓取命令：\n")
        L.append("```bash")
        for pm in a["PMID"]:
            pmc = PMCID.get(pm)
            if pmc:
                L.append(f"curl -s -m 45 -o data/fulltext/{pm}.xml "
                         f"\"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmc}/fullTextXML\"")
        L.append("# 单次间隔 20–30 秒，否则返回 HTTP 500（会被限流挡下）")
        L.append("```\n")

    b = pending[pending["获取路径"] == "出版社 OA，官网 PDF"]
    if not b.empty:
        L.append("## B 组：出版社完全开放获取（官网直接下 PDF）\n")
        for _, r in b.iterrows():
            L.append(f"- [ ] {r['题录']}")
            L.append(f"      PMID {r['PMID']}｜重点：{r['重点看哪一节']}")
        L.append("")

    c = pending[pending["获取路径"].str.startswith("馆际互借")]
    L.append(f"## C 组：订阅期刊，需馆际互借或向作者索取（{len(c)} 篇）\n")
    c = out[out["获取路径"].str.startswith("馆际互借")]
    for _, r in c.iterrows():
        L.append(f"- [ ] {r['题录']}  \n      PMID {r['PMID']}｜重点：{r['重点看哪一节']}")
    L.append("")

    L.append("## 拿到全文后的编码表（填完直接进 scripts/05 的 FULLTEXT_CODING）\n")
    L.append("| PMID | 提及自报问题 | 反向主张可靠 | 定量处理 | 换定义重跑 | 报告验证状态 | 原文证据（一句） |")
    L.append("|---|---|---|---|---|---|---|")
    for _, r in out.iterrows():
        L.append(f"| {r['PMID']} |  |  |  |  |  |  |")
    L.append("")
    L.append("编码规则（与 `scripts/05_audit_fulltext.py` 一致）：\n")
    L.append("- **提及自报问题**：在局限/讨论中把自报视为误差来源，含「无法验证」「回忆偏倚」"
             "「可能不准确」等表述。**不是**指摘要里提一句。")
    L.append("- **反向主张可靠**：用结肠镜率、肠外表现、既往患病率一致性等论据，"
             "正面论证该条目可信。")
    L.append("- **定量处理**：给出校正后估计、PPV、识别界，或与外部患病率比较后调整结论。"
             "仅「结果需谨慎解读」不算。")
    L.append("- **换定义重跑**：以更严格定义（如加结肠镜条件）或另一数据源重做主分析。")
    L.append("- **报告验证状态**：明确说明「无病历可核」「未经验证」或报告可用的验证性信息。")
    L.append("")
    L.append("## 提醒\n")
    L.append("1. 补全文**不会**改变「0 篇定量处理」这个结论——定量处理会出现在摘要里，"
             "而 20 篇摘要已全部读毕。它改变的是「多少篇提到」这个次要与易受攻击的数字。")
    L.append("2. 补全文后需回头改三处：`results/lit_audit_summary.md`（重跑 05 自动更新）、"
             "Abstract 的「the eleven whose full text」、Discussion 的「11 of 20」与「All eleven」。"
             "都是同一个数字，05 重跑后手改。")
    txt = "\n".join(L) + "\n"
    open(os.path.join(MS, "05_fulltext_retrieval_list.md"), "w", encoding="utf-8").write(txt)
    print(txt[:1500])
    print("...\nsaved:", os.path.join(MS, "05_fulltext_retrieval_list.md"))


if __name__ == "__main__":
    main()
