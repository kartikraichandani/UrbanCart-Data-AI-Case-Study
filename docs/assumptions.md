# Assumptions Log

Living document. Every assumption is added here as it is made, with the phase it belongs to.

## Phase 0 – Setup

| # | Assumption / decision | Reason |
|---|-----------------------|--------|
| A0.1 | Original files are **copied** (never moved or edited) into `data/raw/`. SHA-256 hashes of source and copy were compared and match. | Preserve source data. |
| A0.2 | Package marker files are named `__init__.py` (the brief wrote `init.py`). | Python only recognises folders as packages when the file is `__init__.py`; `init.py` would break `import src...`. |
| A0.3 | Empty output folders contain a `.gitkeep` so they survive a GitHub push. | Git does not track empty folders. |
| A0.4 | Python 3.13 with pandas 3.x is used. DuckDB is not yet installed and will be added via `requirements.txt` (needs approval at install time). | Environment inspection. |

## Business definitions (fixed by the brief – not changed)

- New customer = user with >= 1 order with status `delivered`, counted under their `acquisition_channel`.
- CAC = channel spend / new customers.
- Revenue per customer = delivered revenue / customers (Jan–Jun 2026).
- Repeat purchase rate = customers with >= 2 delivered orders / customers.
- LTV = revenue per customer x 30% contribution margin. LTV:CAC = LTV / CAC.

## Phase 1 - Data inspection and cleaning

| # | Assumption / decision | Reason | Status |
|---|-----------------------|--------|--------|
| A1.1 | The 35 users with email `qa.test<N>@urbancart.in` are internal QA/test accounts and are **excluded** with their orders. Detected by the company's own email domain, not by their buying behaviour. Supporting evidence: all 35 are tagged Affiliate, all in Delhi, all have only delivered orders (285 unique orders, Rs 779,790 = 13.6% of delivered revenue). | Test purchases are not marketing-driven acquisitions. Left in, Affiliate would show 540 customers instead of 505. | **Judgement call - to be confirmed by the user.** Logged in `excluded_records.csv`, raw untouched; easy to reverse. |
| A1.2 | 206 repeated order rows are exact duplicate exports (0 had conflicting content) and are removed, keeping the first. Distinct order_ids are never merged, even if user/date/value match (0 such cases found anyway). | Duplicate export, not a second purchase. | Final |
| A1.3 | 72 users with a blank channel are kept and labelled `Unknown` - not Organic, not imputed. 40 of them have delivered orders. They are excluded from per-channel metrics and shown separately. | Source of these customers is unknowable. | Final |
| A1.4 | Cancelled / returned orders (735 raw rows) stay in `orders_cleaned.csv` flagged `is_successful=False`; only `delivered` counts. | Brief definition. | Final |
| A1.5 | Users with no orders (2,097 raw) are kept; they are sign-ups, not customers. | Brief definition of new customer. | Final |
| A1.6 | 44 order-value outliers (IQR rule) are kept, no capping. | Plausible basket sizes; no evidence of error. | Final |
| A1.7 | Order of operations: de-duplicate first, then remove test-account orders, so no row is logged twice. Raw = cleaned + excluded reconciles for every table. | Auditability. | Final |

### Cleaning results (all verified)

- users: 5,135 raw -> 5,100 cleaned (35 excluded)
- orders: 5,684 raw -> 5,193 cleaned (206 duplicates + 285 test-account orders excluded)
- spend: 24 -> 24 (no issues; total Rs 15,90,000, consistent with the brief's "about Rs 16 lakh")
- Cleaned delivered orders 4,514; delivered revenue Rs 49,61,884; customers with a delivered order 2,643. Recomputed through a separate DuckDB-on-raw route: identical.

## Phase 2 - Part 1 analysis

| # | Assumption / decision | Reason |
|---|-----------------------|--------|
| A2.1 | QA test-account exclusion confirmed by the user. | Phase 1 decision A1.1. |
| A2.2 | **Customer denominator** for revenue per customer and repeat rate = customers with >= 1 delivered order (not signups). | Brief definition. |
| A2.3 | Derived metrics (LTV, LTV:CAC, % change) are computed from **unrounded** values; rounding (Rs to nearest rupee, % to 1 decimal, LTV:CAC to 2 decimals) is applied only in the output tables. | Avoids rounding-error compounding. The brief does not specify decimals for the ratio; 2 was chosen. |
| A2.4 | LTV = revenue per customer x 30%, exactly as the brief. Revenue covers Jan-Jun only, so it is a 0-6-month realised value, not a lifetime forecast. No extrapolation. | Brief definition + stated limitation. |
| A2.5 | Organic: LTV shown; no CAC, no LTV:CAC (no organic spend supplied). `Unknown`-channel customers (40) shown separately in customer value, never in CAC (no spend to attribute). | No invented numbers. |
| A2.6 | Monthly CAC groups customers by **signup month**; the first delivered order may happen in any month up to June. Later cohorts have had less time to convert, so recent-month CAC may be slightly overstated. | Brief definition + known cohort-maturity limitation. |
| A2.7 | A month with zero new customers gives an undefined CAC (NaN, noted), never a division by zero. In this data no such month exists (0 of 24). | Edge-case handling. |
| A2.8 | "Increasing / decreasing" is judged on the January-to-June change (as the brief asks), with a 6-month linear slope shown as a noise check. | Endpoints alone can be noisy (~50-125 customers per channel-month). |
| A2.9 | Sanity check: independent recalculation from the RAW csv files with Python stdlib only. It shares the business definitions and the two cleaning decisions, which it cannot validate; this is stated in `sanity_check.md`. Confirmed it detects errors: deliberately counting cancelled orders as successful dropped matches from 60/60 to 8/60. | Honest scope of the verification. |

### Part 1 results (all verified: 12 invariant checks, 60/60 independent metrics)

| Channel | Spend | New customers | CAC | Rev/customer | Repeat % | LTV | LTV:CAC |
|---|---|---|---|---|---|---|---|
| Google Ads | 4,00,000 | 655 | 611 | 2,311 | 57.7 | 693 | 1.14 |
| Meta Ads | 5,47,000 | 675 | 810 | 1,667 | 44.7 | 500 | 0.62 |
| Affiliate | 3,46,000 | 505 | 685 | 957 | 8.1 | 287 | 0.42 |
| Influencer | 2,97,000 | 307 | 967 | 2,858 | 73.0 | 857 | 0.89 |
| Organic | - | 461 | - | 1,903 | 55.7 | 571 | - |

Jan->Jun CAC change: Meta 491 -> 1,115 (+127.2%), Google +3.2%, Influencer +2.0%, Affiliate -3.9%.

## Phase 3 - Part 2 recommendation

| # | Assumption / decision | Reason |
|---|-----------------------|--------|
| A3.1 | **Baseline = Q2 2026 (Apr-Jun) paid spend = Rs 8,68,000**; 20% target = Rs 1,73,600. | The brief says "cut 20% next quarter"; the latest quarter is the run-rate being compared against. **Judgement call - the brief does not define the baseline.** If finance prefers another baseline (e.g. Jan-Jun average), change `BASELINE_MONTHS` in `src/analytics/budget_scenario.py` and re-run. |
| A3.2 | Allocation rule A: Meta Ads is cut back to its Q1 spend (Rs 2,08,000) = -Rs 1,31,000. Rule B: the remainder (Rs 42,600) comes from the lowest-LTV:CAC channel other than Meta (Affiliate), capped at 50% of its baseline. Google Ads and Influencer are not cut. | Meta's Q1->Q2 spend rose Rs 1,31,000 (+63.0%) for 17 extra customers (+5.2%); its Jan->Jun CAC rose 127.2%. Affiliate has the worst LTV:CAC (0.42), 8.1% repeat. Influencer's high CAC is offset by the best revenue per customer and repeat rate. |
| A3.3 | Impact estimate assumes cut spend is as productive as the channel's average Q2 CAC (pessimistic for Meta, whose marginal spend looks far less productive). Presented as illustrative, not a forecast. | Avoids over-claiming. Range: 82 (Meta's observed marginal loss + Affiliate average) to 199 fewer paid customers per quarter. |
| A3.4 | Correlation vs causation: Meta's CAC rise coincides with its spend increase; cause not tested. Stated in memo and Budget_Calculation.md. | No experiment / holdout available. |
| A3.5 | Charts: one fixed colour per channel (palette validated with the dataviz checker; the two light colours fall below 3:1 contrast so every mark has a visible value label). Zero-based axes. Values read from saved tables. | Readability / no misleading scales. |
| A3.6 | Memo numbers are generated from computed tables (`build_memo.py`), word count asserted <= 250 (216), budget arithmetic re-derived independently from the raw spend CSV. | No hand-typed numbers. |

## Phase 4 - Part 3 automation and self-serve design

| # | Assumption / decision | Reason |
|---|-----------------------|--------|
| A4.1 | **Design only.** No cloud resources, accounts or paid services were created. Table/dataset names are proposals. | Brief: "No cloud account is needed"; working rule: no paid cloud without approval. |
| A4.2 | GCP chosen (no strong reason for AWS): native GA4 and Google Ads exports into BigQuery. | Fewer moving parts; two of five sources need no custom code. |
| A4.3 | Cloud Composer/Airflow **not** used; Cloud Scheduler + Cloud Workflows + Cloud Run Jobs instead. | ~5 daily jobs do not justify Composer's fixed running cost. Revisit if pipelines grow. |
| A4.4 | Source-connection details for Salesforce, MoEngage and Meta Ads (API access, incremental keys, rate limits, token refresh) are **not verified** and must be confirmed with each vendor before build. | I have not had access to those systems. |
| A4.5 | Both a dashboard (Looker Studio) and a conversational assistant are proposed, as the user preferred. | User preference; the dashboard covers standing views, the assistant covers follow-ups. |
| A4.6 | The LLM never writes free-form SQL: it only produces a structured intent; code maps it to approved SQL templates. Numbers in answers are checked against the query result. | Prevents invented numbers and unsafe queries. |
| A4.7 | The word limit (400) is checked in code on the note text including its title and list numbers (393 words); diagram text is separate. Extra detail lives in `docs/technical_documentation.md`, which is not part of the 400-word note. | Strict reading of the limit. |
| A4.8 | The SQL template was prototyped on the Part 1 table in DuckDB (Meta Ads, Jan = Rs 491). The regex SQL validator used there is a sketch only; production would use a SQL parser plus BigQuery dry run. | Honest scope of what was tested. |

## Phase 5 - Reflection and AI-use note

| # | Note |
|---|------|
| A5.1 | The reflection (228 words) is a **draft written without any personal background from the user**. It is anchored only in events from this assignment (the 35 test accounts, the independent recalculation) and states no past jobs, projects or feelings beyond them. The user should edit it so every sentence is true in their own words. |
| A5.2 | The AI-use note lists only errors that actually occurred. The ~Rs 8.5 lakh estimate counted duplicate rows (Rs 8,53,172); de-duplicated it is Rs 7,79,790 (13.6%). It was corrected before any deliverable was produced. Other genuine slips this session (notebook newline-escaping, overlapping chart labels) were also caught, but only one is listed because the brief asks for one. |
