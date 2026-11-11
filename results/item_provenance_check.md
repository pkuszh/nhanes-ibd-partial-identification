# 条目溯源核验记录（Supplementary Table S5 的底稿）

核验日期：2026-11-09。方法：直接读取 NCHS 公共传输文件（XPT）内嵌变量标签（`pyreadstat`），
并抓取 NCHS 各周期问卷文件清单页（`datapage.aspx?Component=Questionnaire&Cycle=…`）核对文件是否存在。

## 1. 变量标签（NHANES 2009–2010，ARQ_F.XPT / MCQ_F.XPT）

| 变量 | 内嵌标签（原文） | 是否 IBD | 取值分布（n=5,106） |
|---|---|---|---|
| `ARQ125C` | EVER TOLD YOU HAD ULCERATIVE COLITIS | 是（UC） | 1=53，2=5,043，9=10 |
| `ARQ125D` | EVER TOLD YOU HAD CROHNS DISEASE | 是（CD） | 1=11，2=5,091，9=4 |
| `ARQ135C` | COLONOSCOPY FOR ULCERATIVE COLITIS | 诊断时是否结肠镜 | — |
| `ARQ135D` | COLONOSCOPY FOR CROHNS DISEASE | 诊断时是否结肠镜 | — |
| `MCQ160N` | Doctor ever told you that you had **gout**? | 否（痛风） | 277/6,218 = 4.5% |
| `MCQ160O` | 该周期不存在 | — | — |
| MCQ_F 全表 | 81 个变量，无任何 Crohn / colitis / bowel disease 条目 | 否 | — |

## 2.  Arthritis 问卷（ARQ）的周期可得性

抓取 NCHS 各周期 Questionnaire 组件文件清单，检查是否存在 `ARQ_*` 文件：

| 周期 | 是否存在 ARQ 文件 |
|---|---|
| 1999–2000、2001–2002、2003–2004、2005–2006、2007–2008 | 否 |
| **2009–2010** | **是（ARQ_F）** |
| 2011–2012、2013–2014、2015–2016、2017–2018 | 否 |

结论：IBD 条目（ARQ125C/D）在连续 NHANES 中**只存在于 2009–2010 一个周期**，
且只发给 **20–69 岁**参加者（ARQ_F 共 5,106 人，年龄 20–69）。

用途：
1. Methods 的条目定义与样本年龄范围可直接据此写死；
2. 审计中对 Mei 2026（PMID 42184804）的 `item provenance` 编码有可复核依据；
3. 对"六年框架、只有两年能供给病例"这一表述（Xi 2026、Zhang 2022、Sci Rep 2024）提供事实基础。

复现：

```python
import pyreadstat
_, meta = pyreadstat.read_xport("data/ARQ_F.XPT")
print(meta.column_names_to_labels["ARQ125C"])   # EVER TOLD YOU HAD ULCERATIVE COLITIS
```
