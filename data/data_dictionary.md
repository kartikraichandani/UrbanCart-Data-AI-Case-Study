# Data Dictionary (cleaned datasets)

Generated from the actual files in `data/processed/` by `src/data_processing/clean_data.py`.

## `users_cleaned.csv`
One row per real user who signed up Jan-Jun 2026 (test accounts removed).
Rows: **5,100**

| Column | Type | Description |
|---|---|---|
| `user_id` | int64 | Unique user identifier (primary key). |
| `signup_date` | datetime64[us] | Date the user signed up (YYYY-MM-DD). |
| `city` | str | City of the user (8 cities, no cleaning needed). |
| `acquisition_channel` | str | Google Ads, Meta Ads, Affiliate, Influencer, Organic, or 'Unknown' (blank in source; never imputed). |
| `email` | str | User email (not used in metrics). |
| `channel_was_blank` | bool | True where the source channel was blank and was relabelled 'Unknown'. |
| `signup_month` | str | Signup month as YYYY-MM; used to group customers by cohort month for monthly CAC. |

## `orders_cleaned.csv`
One row per unique order (exact duplicates and test-account orders removed).
Rows: **5,193**

| Column | Type | Description |
|---|---|---|
| `order_id` | int64 | Unique order identifier (primary key). |
| `user_id` | int64 | Foreign key to users.user_id. |
| `order_date` | datetime64[us] | Date of the order (YYYY-MM-DD). |
| `order_value` | int64 | Order value in INR, whole rupees. |
| `status` | str | delivered, cancelled or returned. |
| `order_month` | str | Order month as YYYY-MM. |
| `is_successful` | bool | True only when status = 'delivered'. Only these orders count as revenue / customers. |

## `marketing_spend_cleaned.csv`
Monthly paid spend per channel, as supplied (no changes).
Rows: **24**

| Column | Type | Description |
|---|---|---|
| `month` | str | Month as YYYY-MM. |
| `channel` | str | Paid channel: Google Ads, Meta Ads, Affiliate, Influencer. |
| `spend_inr` | int64 | Marketing spend in INR for that month and channel. |

## Other generated files

- `data/processed/excluded_records.csv` - every record removed during cleaning, with reason and the raw row.
- `outputs/part1_analysis/data_quality_report.csv` - all checks, counts, handling and justification.

## Keys and rules

- `users.user_id` and `orders.order_id` are unique; every `orders.user_id` exists in `users`.
- Successful order = `status == 'delivered'` (`is_successful`).
- A *customer* = user with >= 1 successful order (derived in analytics, not stored).
- Spend covers 4 paid channels x 6 months = 24 rows. Organic has no spend.
