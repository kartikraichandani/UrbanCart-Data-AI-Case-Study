# Technical Documentation

## 1. Part 3 architecture - extended detail

The 400-word design note (`outputs/part3_automation/Architecture_Design.md`) is the submission. This section holds the supporting detail it has no room for.
**It is a design only: no cloud resources were created and nothing was deployed.** Dataset and table names below are proposals.

### 1.1 Why each GCP service (and what was rejected)

| Need | Service | Why it is required | Considered and rejected |
|---|---|---|---|
| Land raw files unchanged | Cloud Storage | Cheap, immutable, replayable history; lets us rebuild any layer after a bug without re-calling APIs (which are rate-limited and sometimes only keep recent data) | Writing straight to the warehouse: no replay |
| Warehouse | BigQuery | Serverless, SQL, native GA4 export and Google Ads transfer, fine-grained IAM, no servers to run at this data size | Cloud SQL / self-managed Postgres: more admin, no native connectors |
| Pull from APIs | Cloud Run Jobs | Pay-per-run containers for Salesforce, MoEngage, Meta Ads (no native BigQuery connector assumed); ordinary Python | Cloud Functions: 9-60 min limits, harder for long incremental pulls |
| Transformations | Dataform | SQL-first, BigQuery-native, built-in assertions (data tests), no extra cost | dbt: equally valid; Dataform avoids another runtime |
| Orchestration | Cloud Scheduler + Cloud Workflows | Ordered steps with retries and failure branches for ~5 jobs, serverless | **Cloud Composer (Airflow): not justified**: always-on environment with a fixed monthly cost for a handful of daily jobs. Revisit if jobs grow to dozens with complex dependencies |
| Secrets | Secret Manager | Central, audited, rotatable; jobs read secrets at runtime via service accounts | Env vars / files in repo: leak risk |
| Observability | Cloud Logging + Monitoring | Already collects Cloud Run / Workflows logs; alert policies on failures and freshness | Extra monitoring tool: unnecessary |
| Dashboard | Looker Studio | Free, BigQuery-native, shareable with the CMO | Looker / Power BI: licence cost, not needed |
| Assistant host | Cloud Run service (+ Identity-Aware Proxy) | Stateless API for the chat front-end; only logged-in company users | Always-on VM |

Source connection details to confirm with each vendor before build (not verified here): Salesforce API access and incremental key (e.g. last-modified timestamp); MoEngage data/export API availability and rate limits; Meta Marketing API insights permissions and token refresh policy.

### 1.2 Data layers

| Layer | BigQuery dataset | Content | Rule |
|---|---|---|---|
| Raw | `raw` | Source data as received, loaded from Cloud Storage; plus load timestamp and file name | Never edited |
| Staging | `staging` | Typed columns, parsed dates, **de-duplicated** (`QUALIFY ROW_NUMBER() OVER (PARTITION BY order_id ...) = 1`), standard names | One row per business key |
| Clean | `clean` | Business rules: successful order = `delivered`; blank channel -> `Unknown` (never Organic); test accounts excluded by a maintained rule table | Every exclusion kept in an `excluded_records` table |
| Analytics | `analytics` | `mart_channel_monthly` (spend, new customers by signup month, CAC), `mart_channel_summary` (revenue per customer, repeat rate, LTV, LTV:CAC), `mart_budget` (baseline vs plan), `metric_catalog`, `pipeline_status` | The only dataset dashboard and assistant may read |

### 1.3 Part 1 data issues -> automated checks

| Part 1 finding | Automated control | Action on failure |
|---|---|---|
| 206 duplicate order rows | De-dupe in staging; assertion `unique(order_id)` after staging; alert if duplicates in a day exceed a threshold | Block publish if uniqueness fails after de-dupe |
| 35 QA/test accounts | Exclusion rule table (internal email domain); alert when a new internal-domain user appears | Alert; rule owner updates the table |
| 72 blank channels | `Unknown` label; alert if `Unknown` share > 2% of new users | Alert (warning) |
| Orders for non-existent users | Referential-integrity assertion orders -> users | Block publish |
| Invalid statuses / channels | Accepted-values assertions | Block publish |
| Spend completeness | Assertion: every paid channel has spend for every elapsed month; reconcile daily totals against the ad platform's own reported total | Block publish |
| Silent failure | Freshness (latest source timestamp < 36 h), row-count drop > 30% vs 7-day average | Alert; yesterday's analytics tables keep serving |

Failures write to `analytics.pipeline_status`, shown on the dashboard so the CMO can see data freshness.

### 1.4 Security

- One service account per job; each can read only its own secret and write only its own dataset.
- Assistant service account: **BigQuery Data Viewer on `analytics` only**, plus permission to run query jobs. No access to `raw`, `staging`, `clean` (where personal data such as emails lives).
- No keys in code or images; secrets fetched at runtime; rotation schedule per vendor token.
- Analytics tables contain aggregates only (no emails or user-level rows).

## 2. Conversational assistant - controlled workflow

```
CMO question
 -> LLM: structured intent {metric, channel, period, comparison}   (JSON schema, no SQL)
 -> Code: validate against metric_catalog; resolve "last month" using today's date in code
 -> Select an approved parameterised SQL template for that intent
 -> Validator: SELECT-only, allow-listed tables/columns, row limit, bytes-billed cap, BigQuery dry run
 -> BigQuery (read-only service account)
 -> Rows returned as structured JSON
 -> LLM: write the answer from the rows only
 -> Check: every number in the answer appears in the rows; attach definition, period, data freshness
 -> Audit log
```

Key safeguards:

1. **No free-form SQL from the model.** The LLM picks an intent; code maps it to a reviewed template. Questions that fit no template get a polite "I can't answer that yet" and are logged so the data team can add a template.
2. **Time handled in code.** "Last month" is resolved by deterministic date logic, so the model never guesses a date range.
3. **Numbers come only from query results.** The answer-checking step rejects any number not present in the returned rows (after formatting) and falls back to showing the table.
4. **Unavailable data.** An empty result or a month outside the data range returns "not available for <period>", never an estimate.
5. **Definitions travel with the answer**: metric formula, reporting period, "data updated <timestamp>".
6. **What-if questions** ("reduce Influencer by 20%") call a deterministic budget function (same logic as `src/analytics/budget_scenario.py`) and are labelled as estimates with their assumptions.
7. **Prompt injection / abuse.** The model never sees raw credentials and cannot execute anything; SQL is chosen by code, validated, and run read-only. Free text in user questions is treated as data.
8. **Audit log**: user, question, parsed intent, SQL, rows returned, answer, validation outcome, latency, bytes billed.

Example template (verified against the Part 1 table in a DuckDB prototype: Meta Ads, 2026-01 returned spend 54,000, 110 new customers, CAC 491; a month outside the data returned no rows):

```sql
SELECT channel, month, spend, new_customers, cac
FROM analytics.mart_channel_monthly
WHERE channel = @channel AND month = @month
LIMIT 1
```

The regex validator used in that prototype was only a sketch. In production the validator should parse the SQL (e.g. with `sqlglot`), compare referenced tables/columns with an allow-list, and use a BigQuery dry run for cost and syntax.

## 3. Testing plan

| Test type | What is checked | Example |
|---|---|---|
| Data validation | Dataform assertions on every layer: not-null keys, unique keys, accepted values, referential integrity, freshness, row-count anomaly | `unique(order_id)` fails -> run stops |
| SQL correctness | Each template run on a fixed fixture and compared with a known result | Meta January CAC = 491 (Part 1) |
| Metric calculation | Unit tests of CAC, LTV, repeat rate, % change against hand-calculated values | CAC with 0 customers returns undefined, never a division error |
| Edge cases | Missing month, zero customers, a channel with no spend, a future month, ambiguous question | "Spend in July" -> "not available" |
| AI response accuracy | ~50 labelled questions (answerable, unanswerable, ambiguous); score numeric match, correct period, refusal behaviour, no number outside the result | Accuracy gate before launch, re-run after every prompt or model change |
| Permission and security | Assistant account cannot write or read `raw`; attempts like `DROP TABLE`, forbidden tables and prompt injection are blocked and logged | Attempt to read `raw.users` -> denied |
| End-to-end | Full run in a staging project on fixture data with injected duplicates, a blank channel, and a revoked secret | Alert reaches Slack/email within minutes |
| User acceptance | One week in parallel with the data team's own numbers | Differences investigated before go-live |

## 4. Part 1 / 2 code map

| Purpose | File |
|---|---|
| Paths and fixed business constants | `src/config.py` |
| Load raw CSVs read-only | `src/data_processing/load_data.py` |
| 43 data-quality checks | `src/data_processing/data_quality.py` |
| Cleaning, exclusion log, reconciliation, data dictionary | `src/data_processing/clean_data.py` |
| Customer table, revenue per customer, repeat rate | `src/analytics/customer_value.py` |
| Spend, new customers, CAC | `src/analytics/acquisition_metrics.py` |
| LTV and LTV:CAC | `src/analytics/ltv_cac.py` |
| Monthly CAC and Jan->Jun change | `src/analytics/monthly_trends.py` |
| 20% budget scenario | `src/analytics/budget_scenario.py` |
| Charts / CMO memo / architecture diagram | `src/visualizations/generate_charts.py`, `build_memo.py`, `build_architecture.py` |
| Invariants, independent recalculation, budget-maths check | `src/automation/validation.py` |
| Run everything | `src/automation/pipeline.py` (`python -m src.automation.pipeline`) |
| Final submission audit (limits, raw data, README numbers, cleanliness) | `src/automation/final_audit.py` |
