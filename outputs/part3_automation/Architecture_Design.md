## A. Automated daily pipeline (GCP)

- **Ingest.** GA4 and Google Ads reach BigQuery through their native export and Data Transfer Service. Salesforce, MoEngage and Meta Ads are pulled incrementally by small Python **Cloud Run Jobs** via API. Each pull is first saved unchanged in **Cloud Storage** (raw, date-partitioned).
- **Warehouse: BigQuery**, four layers: *raw*, *staging* (typed, de-duplicated), *clean* (business rules), *analytics* (CAC, LTV, repeat rate, trends). **Dataform** runs the SQL.
- **Schedule.** Cloud Scheduler triggers **Cloud Workflows** each morning: extract, transform, test, publish. Composer/Airflow is overkill for five jobs.
- **Automated quality checks (the Part 1 issues).** Tests block publishing: duplicate order_id (de-duplicated in staging), test accounts (exclusion rule), blank channel (alert above 2%), orphan orders, invalid values, spend reconciled with ad-platform totals, freshness, row-count drops. Yesterday's good tables keep serving.
- **Secrets and monitoring.** API keys sit in **Secret Manager**, read by least-privilege service accounts, never in code. Logging/Monitoring alerts (job failure, stale data, failed test) go to Slack and email.

## B. Self-serve tool: dashboard plus conversational assistant

- **Dashboard (Looker Studio):** spend, new customers, CAC, revenue per customer, repeat rate, LTV:CAC, monthly trends, budget versus actual.
- **Assistant** for follow-ups. Both read only *analytics* tables and a *metric catalogue*.
- **Question to answer:**
  1. An LLM converts the question into structured intent (metric, channel, period).
  2. Code validates it against the catalogue and resolves "last month" itself.
  3. An approved parameterised SQL template is selected; the LLM never writes free-form SQL.
  4. A validator enforces SELECT-only, allow-listed tables and columns, row and cost limits.
  5. BigQuery runs it under a read-only account.
  6. The LLM phrases the answer from returned rows only, adding metric definition, period and freshness.
- **No invented numbers.** A check confirms every number in the answer appears in the query result; otherwise the table is shown. Missing data returns "not available". "What if" questions use a deterministic budget function, labelled as an estimate. Everything is audit-logged.

## C. Testing before the CMO uses it

- Dataform assertions on the data.
- SQL templates checked against Part 1 results (e.g. Meta January CAC ₹491).
- Metric unit tests: zero customers gives undefined, missing months.
- 50-question evaluation set, including unanswerable questions.
- Security tests: write attempts, forbidden tables, prompt injection.
- Staging end-to-end run with injected duplicates and a deliberate failure, proving alerts fire.
- One week in parallel with the data team's numbers.
