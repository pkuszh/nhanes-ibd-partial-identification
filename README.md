# Replication package: "One item, twenty studies, no validation"

Code and derived data for:

**Gong J, Chen W.** *One item, twenty studies, no validation: the precision of
self-reported inflammatory bowel disease in NHANES is an artefact of an
unmeasured specificity.* (manuscript submitted to the Journal of Clinical
Epidemiology, 2026)

## What this study does

NHANES 2009–2010 is the only cycle that ever fielded a self-reported
inflammatory bowel disease (IBD) item (ARQ125C/D). At least 20 published
studies (2015–2026) have used this item for cross-sectional outcome
associations, yet no validation study of the item exists. This package
replicates a quantitative bias analysis showing that the reported precision of
these studies rests on an unmeasured specificity:

1. **Primary analysis** — survey-weighted prevalence and sleep-outcome
   associations (self-reported IBD, n = 62/3,976 complete cases; OR 2.94,
   95% CI 1.04–8.29).
2. **Identification region** — with no priors on (sensitivity, specificity),
   the observed data are compatible with true ORs anywhere in
   [3.48, 273.66]; the critical specificity is Sp* = 0.9895.
3. **Anchored bounds** — anchoring specificity to external US IBD prevalence
   estimates narrows the OR to [3.81, 48.55]; the three *diagnosed*-prevalence
   anchors alone give [3.81, 11.64].
4. **Monte Carlo probabilistic bias analysis** — median OR 6.44 (95% interval
   3.74–23.26; 19,935/20,000 draws feasible).
5. **Reporting audit** — of 20 studies using the item, 17/20 (incl. one
   probable) acknowledge the self-report limitation, 0/20 quantify it, and
   0/20 re-run with an alternative definition.

## Repository layout

```
scripts/
  01_build.py             Download NHANES 2009-2010 XPT files from CDC and
                          build the analysis dataset (data/analysis.csv)
  02_analysis.py          Survey-weighted estimates (Taylor linearization):
                          prevalence, sleep outcomes, ORs -> t1/t2/t3 CSVs
  03_bias.py              Misclassification bias analysis: identification
                          region, external anchoring, Monte Carlo
  04_audit.py             Bibliometric retrieval + abstract-level screening
                          of the 20 studies -> lit_audit.csv
  05_audit_fulltext.py    Full-text audit (revises 04) -> lit_audit_fulltext.csv
  06_retrieval_list.py    Generates the full-text retrieval worksheet
  07_fig3.py              Figure 3 (MC distribution + nested-interval
                          comparison) -> results/fig3_mc.png
  08_ingest_fulltext.py   Converts retrieved PDFs to text for coding
  09_coding_worksheet.py  Builds the full-text coding worksheet
  10_fig1.py              Figure 1 (study flow) -> results/fig1_flow.png
data/
  analysis.csv            Analysis dataset (n = 5,106; derived from public
                          NHANES 2009-2010 files; no original or sensitive data)
results/
  All output tables and figures referenced in the manuscript.
```

## Reproduction

```bash
python scripts/01_build.py      # downloads ~25 MB of public CDC data on first run
python scripts/02_analysis.py
python scripts/03_bias.py
python scripts/07_fig3.py
python scripts/10_fig1.py
```

The audit pipeline (`04`–`06`, `08`, `09`) additionally requires the full
texts of the audited studies; those PDFs are copyrighted and are **not**
redistributed here. `results/lit_audit_fulltext.csv` contains the final
audited classifications so all manuscript numbers are reproducible without
the PDFs.

**Requirements:** Python >= 3.10; `pandas`, `numpy`, `scipy`, `matplotlib`,
`pyreadstat`.

**Data source:** CDC NHANES public-use data
(https://wwwn.cdc.gov/nchs/nhanes/), 2009–2010 cycle. No human-subjects
approval was required (secondary analysis of de-identified public data).

## Notes on the analysis dataset

- The IBD item lives in the arthritis-specific questionnaire file (ARQ_F),
  fielded only in 2009–2010, so the sample is restricted to ages 20–69 with
  MEC exam data (n = 5,106; 5,096 with both definitions definable; 3,976
  complete cases).
- Weights: WTMEC2YR; design: 15 strata x 31 PSUs (16 degrees of freedom),
  Taylor linearization.
- "Colonoscopy-confirmed IBD" (definition 2) is an internal-consistency
  anchor, not a gold standard; see the manuscript's Methods and Discussion.

## License

Code: MIT License. Derived data (`data/analysis.csv`): CC-BY 4.0.

## Citation

If you reuse this package, please cite the manuscript and this repository
(DOI: 10.5281/zenodo.XXXXXXX — assigned by Zenodo upon release).

## Correspondence

Jijun Gong, Peking University Shenzhen Hospital, Shenzhen, Guangdong, China
(pkuszh@yeah.net)
