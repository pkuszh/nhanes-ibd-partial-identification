"""
09_coding_worksheet.py  --  生成人工编码工作单

作用：不替你判断，只把每篇全文里"可能要编码的那些句子"按维度捞出来，
      附在空白编码表旁边。明天拿到 PDF 后不用从头翻整篇，逐条勾即可。

输出：manuscript/06_coding_worksheet.md

用法：
  python scripts/09_coding_worksheet.py
"""

import os
import re

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
FT = os.path.join(ROOT, "data", "fulltext")
MS = os.path.join(ROOT, "manuscript")

# 五个编码维度对应的检索线索（只用于定位句子，不用于定码）
CUES = {
    "ack": [
        r"self[- ]report", r"questionnaire", r"cannot be (validated|verified)",
        r"no (clinical|medical) record", r"not (been )?validated", r"unvalidated",
        r"recall bias", r"misclassif", r"misreport", r"misdiagnos",
        r"subjective", r"not confirmed",
    ],
    "assert_valid": [
        r"consistent with (actual|physician)", r"high (rate|proportion) of colonoscopy",
        r"colonoscopy (rate|at diagnosis)", r"extraintestinal", r"extra-intestinal",
        r"valid(at|ity) of (the )?self", r"accurately (identified|captured)",
    ],
    "quant": [
        r"positive predictive value", r"\bPPV\b", r"correct(ed|ion) for (misclass|measurement)",
        r"quantitative bias", r"probabilistic bias", r"sensitivit(y|ies) and specificit",
        r"bounds?", r"partial identification",
    ],
    "altdef": [
        r"restrict(ed)? to (those|participants) (with|who)", r"sensitivit(y|ies) analys",
        r"alternative definition", r"more stringent definition", r"re-?ran",
        r"excluded? those",
    ],
    "report_verif": [
        r"validated", r"verification", r"medical record", r"chart review",
        r"physician[- ]diagnosed", r"confirmed by",
    ],
}

HEAD = {
    "ack": "是否把自报当成误差来源提及",
    "assert_valid": "是否反向主张该条目可靠",
    "quant": "是否做任何定量处理",
    "altdef": "是否换定义/换样本重跑主分析",
    "report_verif": "是否报告验证状态",
}


def sent_split(txt):
    """返回 [(句子, 起始字符位置)]，位置用于判断是否落在局限段之后。"""
    txt = re.sub(r"\s+", " ", txt)
    txt = txt.replace("\ufb01", "fi").replace("\ufb02", "fl")
    out, pos = [], 0
    for m in re.finditer(r"[^.!?]+[.!?]", txt):
        s = m.group(0).strip()
        if 45 <= len(s) <= 600 and not re.search(r"\b(Fig\.|Table\s*\d|doi:|et al\.,? \d{4})", s):
            out.append((s, m.start()))
    return out


def body_only(txt):
    """截掉参考文献表，否则书名/篇名里的 "self-report" 会被当成线索捞上来。"""
    cut = len(txt)
    for m in re.finditer(r"\bReferences\b|\bREFERENCES\b", txt):
        if m.start() > len(txt) * 0.5:
            cut = m.start()
            break
    return txt[:cut]


def lim_start(txt):
    """最后一段局限/优势讨论的起点；找不到就退回全文 60% 处。"""
    txt = re.sub(r"\s+", " ", txt)
    idx = [m.start() for m in re.finditer(r"limitation|several strengths|strengths and", txt, re.I)]
    return idx[-1] if idx else int(len(txt) * 0.6)


def pick(pairs, pats, lim_at, k=3):
    scored = []
    for s, pos in pairs:
        low = s.lower()
        hits = sum(1 for p in pats if re.search(p, low))
        if hits:
            # 落在局限段之后 +3，长度接近 180 字的略优先
            bonus = 3 if pos >= lim_at else 0
            scored.append((hits + bonus, -abs(len(s) - 180), s))
    scored.sort(reverse=True)
    seen, keep = set(), []
    for _, _, s in scored:
        key = s[:60].lower()
        if key in seen:
            continue
        seen.add(key)
        keep.append(s)
        if len(keep) >= k:
            break
    return keep


def main():
    q = pd.read_csv(os.path.join(RES, "retrieval_queue.csv"), dtype=str)
    base = pd.read_csv(os.path.join(RES, "lit_audit.csv"), dtype={"pmid": str})
    title = dict(zip(base.pmid, base.title.fillna("")))

    # C 组 9 篇 + 任何已经落盘的 *_pdf.txt（方便随时试跑）
    pmids = list(dict.fromkeys(
        list(q["PMID"].astype(str)) +
        [f.split("_")[0] for f in os.listdir(FT) if f.endswith("_pdf.txt")]
    ))

    L = ["# 人工编码工作单（层 2 补录）\n",
         "由 `scripts/09_coding_worksheet.py` 生成。每篇下面的句子是**检索线索**，",
         "不是结论：需要你核对上下文后自己判定 0/1，并把原文证据抄进 `evidence`。\n",
         "编码定稿后，把结果贴进 `scripts/05_audit_fulltext.py` 的 `FULLTEXT_CODING` 字典，",
         "重跑 05 即可更新 `results/lit_audit_summary.md`。\n",
         "---\n"]

    have, miss, ao = [], [], []
    for pmid in pmids:
        p = os.path.join(FT, f"{pmid}_pdf.txt")
        row = q[q["PMID"] == pmid]
        label = (row.iloc[0]["题录"].split(". *")[0] if len(row) else title.get(pmid, pmid))
        focus = row.iloc[0]["重点看哪一节"] if len(row) else ""
        status = row.iloc[0]["状态"] if len(row) and "状态" in row.columns else ""
        if not os.path.exists(p):
            if status == "仅摘要":
                ao.append((pmid, label))
            else:
                miss.append((pmid, label))
            continue
        have.append(pmid)
        txt = body_only(open(p, encoding="utf-8").read())
        pairs = sent_split(txt)
        ls = lim_start(txt)
        L.append(f"## {label}\n")
        L.append(f"- PMID `{pmid}`｜正文 {len(txt):,} 字符 / {len(pairs):,} 句"
                 f"｜局限段起点 ≈ 第 {ls:,} 字符（占 {ls/len(txt):.0%}）")
        if focus:
            L.append(f"- 该篇重点：{focus}")
        L.append("")
        L.append("| 提及自报问题 | 反向主张可靠 | 定量处理 | 换定义重跑 | 报告验证状态 |")
        L.append("|---|---|---|---|---|")
        L.append("|  |  |  |  |  |\n")
        for k in ["ack", "assert_valid", "quant", "altdef", "report_verif"]:
            picks = pick(pairs, CUES[k], ls, k=3)
            if not picks:
                continue
            L.append(f"**{HEAD[k]}**（线索 {len(picks)} 条）")
            for s in picks:
                L.append(f"> {s}\n")
        L.append("**原文证据（抄一句）**：\n")
        L.append("---\n")

    if miss:
        L.append("## 全文仍未到（先空着，别记 0）\n")
        for pmid, label in miss:
            L.append(f"- `{pmid}` {label}")
        L.append("")
    if ao:
        L.append("## 已确认仅摘要：不做层 2 编码\n")
        L.append("五列一律记 missing。摘要里读到的东西单列进 `ABSTRACT_ONLY` 的 `obs`，不冒充全文编码。\n")
        for pmid, label in ao:
            L.append(f"- `{pmid}` {label}")
        L.append("")

    out = os.path.join(MS, "06_coding_worksheet.md")
    open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"有全文 {len(have)} 篇；缺 {len(miss)} 篇")
    print("saved:", out)


if __name__ == "__main__":
    main()
