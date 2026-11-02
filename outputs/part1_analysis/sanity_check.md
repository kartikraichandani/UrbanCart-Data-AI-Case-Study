# Sanity Check (Part 1, question 6)

## Number selected: Meta Ads CAC

- **Spend (read directly from raw `marketing_spend.csv`)**: 54,000 + 68,000 + 86,000 + 109,000 + 114,000 + 116,000 = **Rs 547,000**
- **New customers (independent method)**: **675** users tagged Meta Ads with >= 1 delivered order
- **CAC** = 547,000 / 675 = **Rs 810**
- **Main pipeline result**: Rs 810  ->  **agrees**

## How the second method differs from the first

| | Main pipeline | Independent check |
|---|---|---|
| Tools | pandas + DuckDB SQL | Python standard-library `csv`, plain dicts and sets |
| Input | Cleaned CSVs in `data/processed/` | **Raw** CSVs in `data/raw/` |
| Dedup + test-account removal | `clean_data.py` | Re-implemented separately (set of full rows; email domain) |
| Aggregation | SQL JOIN / GROUP BY | Loops over rows, per-user counters |
| Spend | Sum of cleaned spend table | Sum of the raw spend column |

**What this proves:** the arithmetic, joins and grouping in the pipeline are correct, and the cleaning code really produces what the report says.
**What it does NOT prove:** that the *decisions* are right. Both routes share the same business definitions (from the brief) and the same two cleaning decisions (drop exact duplicate orders; exclude the 35 `@urbancart.in` test accounts). Those are documented in `docs/assumptions.md`.

## Full comparison: 60 of 60 metrics match

Every channel's customers, revenue, revenue per customer, repeat rate, spend, CAC, LTV:CAC and all 24 monthly CAC values were recomputed independently (tolerance 1e-6, before rounding).

**Result: ALL MATCH.**

## Sensitivity to the test-account decision (for transparency)

If the 35 QA accounts were *kept*, Affiliate would show 540 customers and a CAC of Rs 641 instead of 505 customers and Rs 685. Excluding them is the more defensible choice because they are not real customers.

## Why the two results agree

Both start from the same raw rows, apply the same definition (delivered order, de-duplicated, real users) and divide the same spend by the same count of customers. Different code reaching the same number means that the counts are not artefacts of a join or grouping error.
