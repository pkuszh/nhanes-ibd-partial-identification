"""
08_ingest_fulltext.py  --  全文入库（PDF -> txt，自动认 PMID）

明天拿到 6 篇 C 组 PDF 后，把它们丢进 data/inbox/，跑这一个脚本即可：
  python scripts/08_ingest_fulltext.py

它会做三件事：
  1. pypdf 抽文本，存成 data/fulltext/<PMID>_pdf.txt（命名规则与已有的三篇一致）
  2. 认 PMID 的顺序：文件名 -> 首页 DOI -> 首页标题模糊匹配（对 lit_audit 的 20 条）
  3. 打印对照表；认不出的落到 data/fulltext/_unmatched/，人工改名后重跑

单独指定目录也可以：
  python scripts/08_ingest_fulltext.py "D:/some/where"
"""

import os
import re
import sys
import json
import glob
import difflib

import pandas as pd
from pypdf import PdfReader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
FT = os.path.join(ROOT, "data", "fulltext")
INBOX = os.path.join(ROOT, "data", "inbox")
UNMATCHED = os.path.join(FT, "_unmatched")


def load_doi_map():
    """从 refs_1_20.json / refs_21_29.json 里抠 DOI -> PMID。"""
    m = {}
    for fn in ("refs_1_20.json", "refs_21_29.json"):
        p = os.path.join(RES, fn)
        if not os.path.exists(p):
            continue
        for row in json.load(open(p, encoding="utf-8")):
            # 两个文件结构不同：[编号, PMID, 题录] 与 [PMID, 题录]
            pmid, cite = (str(row[1]), row[2]) if len(row) == 3 else (str(row[0]), row[1])
            for doi in re.findall(r"10\.\d{4,9}/[^\s;,)]+", cite):
                m[doi.lower().rstrip(".")] = pmid
    return m


def norm(s):
    s = s.lower()
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def read_pdf(path):
    r = PdfReader(path)
    pages = []
    for i, pg in enumerate(r.pages[:40]):
        try:
            pages.append(pg.extract_text() or "")
        except Exception:
            pages.append("")
    return "\n".join(pages), len(r.pages)


def match_pmid(path, text, doi_map, titles):
    stem = os.path.basename(path)

    # 1) 文件名里的 8 位 PMID
    for cand in re.findall(r"\b(\d{7,9})\b", stem):
        if cand in set(titles):
            return cand, "filename-pmid"

    # 2) DOI（文件名 + 前三页正文）
    hay = (stem + "\n" + text[:6000]).lower()
    for doi, pmid in doi_map.items():
        if doi in hay:
            return pmid, f"doi:{doi}"

    # 3) 标题模糊匹配
    head = norm(text[:4000])
    best, score = None, 0.0
    for pmid, t in titles.items():
        s = difflib.SequenceMatcher(None, norm(t)[:220], head[:400]).ratio()
        if s > score:
            best, score = pmid, s
    if score >= 0.60:
        return best, f"title:{score:.2f}"
    return None, f"unmatched(best {score:.2f})"


def main():
    dirs = sys.argv[1:] or [INBOX, FT]
    os.makedirs(UNMATCHED, exist_ok=True)

    base = pd.read_csv(os.path.join(RES, "lit_audit.csv"), dtype={"pmid": str})
    titles = dict(zip(base.pmid, base.title.fillna("")))
    doi_map = load_doi_map()

    pdfs = []
    for d in dirs:
        pdfs += sorted(glob.glob(os.path.join(d, "*.pdf")))
    if not pdfs:
        print(f"[空] 没找到 PDF。把明天的 6 篇放到：{INBOX}")
        print("      然后重跑本脚本。")
        return

    rows = []
    for p in pdfs:
        try:
            text, npages = read_pdf(p)
        except Exception as e:
            rows.append((os.path.basename(p), "-", f"读失败 {e}", 0))
            continue
        pmid, how = match_pmid(p, text, doi_map, titles)
        if pmid:
            out = os.path.join(FT, f"{pmid}_pdf.txt")
            open(out, "w", encoding="utf-8").write(text)
            rows.append((os.path.basename(p), pmid, how, len(text)))
        else:
            out = os.path.join(UNMATCHED, os.path.basename(p).replace(".pdf", ".txt"))
            open(out, "w", encoding="utf-8").write(text)
            rows.append((os.path.basename(p), "-", how, len(text)))

    w = [max(len(str(r[i])) for r in rows + [("文件", "PMID", "依据", "字符数")])
         for i in range(4)]
    print(f"{'文件'.ljust(w[0])}  {'PMID'.ljust(w[1])}  {'依据'.ljust(w[2])}  字符数")
    print("-" * (sum(w) + 12))
    for r in rows:
        print(f"{str(r[0]).ljust(w[0])}  {str(r[1]).ljust(w[1])}  {str(r[2]).ljust(w[2])}  {r[3]}")

    ok = [r for r in rows if r[1] != "-"]
    bad = [r for r in rows if r[1] == "-"]
    print(f"\n入库 {len(ok)} 篇；未识别 {len(bad)} 篇"
          + (f"（见 {UNMATCHED}，改名成 <PMID>.pdf 后重跑）" if bad else ""))
    print("下一步：python scripts/09_coding_worksheet.py")


if __name__ == "__main__":
    main()
