# UrbanCart – Data & AI Engineer Case Study (Growth & Analytics)

Take-home case study: analyse paid-channel performance, recommend a 20% spend cut, and design an automated, self-serve analytics platform.
The assignment brief is in `Case_Study_Brief.pdf`. All business definitions come from it and were not changed.

## Project overview

UrbanCart spent ₹15,90,000 between January and June 2026 on four paid channels (Google Ads, Meta Ads, Affiliate, Influencer). The CMO must cut paid spend by 20% next quarter without hurting growth.

| Part | Question | Where |
|---|---|---|
| 1 – Analyse | Data quality, CAC, customer value, LTV:CAC, monthly CAC trend, sanity check | `outputs/part1_analysis/`, `notebooks/` |
| 2 – Recommend | CMO memo (≤250 words) with 3 charts | `outputs/part2_recommendation/` |
| 3 – Automate | Design note (≤400 words) with architecture diagram (GCP) | `outputs/part3_automation/` |
| Final | AI-use note and reflection | `outputs/final_submission/` |

## Key findings

Cleaned data: 5,100 users and 5,193 orders (35 internal QA test accounts and 206 duplicate order rows removed and logged; 72 users with a blank channel kept as `Unknown`, never as Organic). Customer = user with at least one `delivered` order.

| Channel | Spend (₹) | New customers | CAC (₹) | Revenue / customer (₹) | Repeat rate | LTV (₹) | LTV:CAC |
|---|---|---|---|---|---|---|---|
| Google Ads | 4,00,000 | 655 | 611 | 2,311 | 57.7% | 693 | **1.14** (best) |
| Meta Ads | 5,47,000 | 675 | 810 | 1,667 | 44.7% | 500 | 0.62 |
| Affiliate | 3,46,000 | 505 | 685 | 957 | 8.1% | 287 | **0.42** (worst) |
| Influencer | 2,97,000 | 307 | 967 | 2,858 | 73.0% | 857 | 0.89 |
| Organic | – | 461 | – | 1,903 | 55.7% | 571 | – (no spend supplied) |

- **Meta Ads is getting more expensive:** monthly CAC rose from ₹491 (Jan) to ₹1,115 (Jun), +₹624 (+127.2%). The other channels moved by less than ±4%.
- **Recommendation (Q2 baseline ₹8,68,000, cut ₹1,73,600 = exactly 20%):** Meta Ads −₹1,31,000 (back to its Q1 spend), Affiliate −₹42,600; protect Google Ads; hold Influencer, whose high CAC is offset by the best revenue per customer and repeat rate. Full arithmetic: `outputs/part2_recommendation/Budget_Calculation.md`.
- **Caveats:** association, not causation; LTV is a 0–6 month value (revenue × 30%), not a lifetime forecast; modest sample sizes; Q2 is my choice of baseline (see `docs/assumptions.md`).
- **Verified two ways:** all 60 headline metrics were recomputed from the raw CSVs with plain Python and match.

## Folder structure

```
UrbanCart-Data-AI-Case-Study/
├── README.md, requirements.txt, Case_Study_Brief.pdf, .gitignore
├── data/
│   ├── raw/                     original CSVs (never modified; checksums in raw_checksums.sha256)
│   ├── processed/               cleaned CSVs + excluded_records.csv (every removed row, with reason)
│   └── data_dictionary.md
├── notebooks/                   Part1_Exploratory_Analysis.ipynb (+ .html copy, executed)
├── src/
│   ├── config.py                paths and fixed business constants
│   ├── data_processing/         load_data, data_quality (43 checks), clean_data
│   ├── analytics/               acquisition_metrics, customer_value, ltv_cac, monthly_trends, budget_scenario
│   ├── visualizations/          generate_charts, build_memo, build_architecture
│   └── automation/              pipeline (run everything), validation, final_audit
├── outputs/
│   ├── part1_analysis/          quality report, metric tables, sanity_check.md
│   ├── part2_recommendation/    CMO_Recommendation (md, pdf), Budget_Calculation.md, charts/
│   ├── part3_automation/        Architecture_Design (md, pdf), architecture_diagram.png
│   └── final_submission/        AI_Usage_Note.md, Reflection.md
└── docs/                        project_approach.md, assumptions.md, technical_documentation.md
```

## Technologies

Python 3.13, pandas, NumPy, DuckDB (SQL on CSV), matplotlib, Jupyter/nbconvert, reportlab (PDF). Design note: GCP (BigQuery, Cloud Storage, Cloud Run Jobs, Cloud Scheduler/Workflows, Dataform, Secret Manager, Looker Studio) – design only, nothing deployed.

## Setup

Run all commands from the repository root (`UrbanCart-Data-AI-Case-Study/`).

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
```

## How to run

```bash
# 1. Whole pipeline: quality checks -> cleaning -> Part 1 tables -> validation -> charts -> memo -> design note
python -m src.automation.pipeline

# 2. Re-execute the notebook (reads the same src/ modules)
jupyter nbconvert --to notebook --execute --inplace notebooks/Part1_Exploratory_Analysis.ipynb

# 3. Final submission audit (word limits, raw data unchanged, README numbers, no temp files ...)
python -m src.automation.final_audit
```

The pipeline stops with an error if any invariant check fails or if the independent recalculation disagrees with the main calculation.

## Deliverables (mapped to the brief's checklist)

| Brief requirement | File |
|---|---|
| Part 1: answers in a table + all code | `notebooks/Part1_Exploratory_Analysis.ipynb` (and `.html`), `outputs/part1_analysis/*.csv`, `src/` |
| Part 1: data-quality issues, rows affected, handling | `outputs/part1_analysis/data_quality_report.csv`, `data/processed/excluded_records.csv` |
| Part 1: sanity check | `outputs/part1_analysis/sanity_check.md` |
| Part 2: memo and charts | `outputs/part2_recommendation/CMO_Recommendation.pdf` (`.md`), `charts/` |
| Part 3: design note and diagram | `outputs/part3_automation/Architecture_Design.pdf` (`.md`), `architecture_diagram.png` |
| AI-use note (3–5 lines) | `outputs/final_submission/AI_Usage_Note.md` |
| Reflection | `outputs/final_submission/Reflection.md` |
| Assumptions (required by the brief) | `docs/assumptions.md` |

## Assumptions to be aware of

The main judgement calls (all logged with reasons in `docs/assumptions.md`): QA test accounts excluded; exact duplicate orders removed; blank channel kept as `Unknown`; Q2 2026 used as the "next quarter" baseline; LTV used exactly as the brief defines it, without extrapolation.
