# Project Approach (plain-language walkthrough)

## The 2-minute version

1. **Check the data before trusting it.** 43 automated checks found three real problems: 35 internal test accounts (all tagged Affiliate, ~14% of delivered revenue), 206 duplicate order rows, and 72 users with no acquisition channel. Each was handled, logged and justified; nothing was silently deleted.
2. **Calculate with the brief's exact definitions.** Customer = at least one *delivered* order; CAC = spend ÷ customers; LTV = revenue per customer × 30%.
3. **Verify the numbers a second way.** I rebuilt every headline metric from the raw files using plain Python (no pandas/DuckDB). All 60 matched, and I confirmed that the check really fails when I deliberately break the logic.
4. **Recommend with the maths on show.** Cut Meta Ads ₹1,31,000 and Affiliate ₹42,600 = ₹1,73,600 = exactly 20% of Q2 spend. Protect Google Ads. Do not cut Influencer just because its CAC is highest.
5. **Design the automation as a plain, controlled system.** Daily pipeline on GCP, a dashboard, and an assistant that can only quote numbers returned by approved queries.

## Why each decision was made

| Decision | Why | What would change it |
|---|---|---|
| Exclude the 35 `@urbancart.in` accounts | Test purchases are not marketing-driven customers; left in, Affiliate shows 540 customers instead of 505 and revenue is overstated by ₹7,79,790. Detected by company email domain, not by behaviour | If the business confirms they are real customers |
| Remove only *exact* duplicate order rows | Same order_id with identical content is a duplicate export. Different order_ids are different orders, even with the same value/date | If duplicates had *conflicting* content (none did) – then manual review |
| Blank channel → `Unknown` | Guessing "Organic" would move customers between channels and distort CAC | If the source system can supply the true channel |
| Customer denominator = users with ≥1 delivered order | It is the brief's definition; signups alone are not customers | – |
| Derived metrics from unrounded values, rounded only for display | Avoids small rounding errors compounding (e.g. LTV:CAC) | – |
| Q2 as the "next quarter" baseline | The latest quarter is the run-rate being compared against. The brief does not define the baseline | If finance defines it differently, change `BASELINE_MONTHS` in `budget_scenario.py` |
| Cut Meta back to its Q1 spend | Q1→Q2: spend +63.0% (₹1,31,000) bought only 17 more customers (+5.2%) – the clearest sign of diminishing returns | An experiment (holdout) showing Meta spend really drives growth |
| Cut Affiliate for the remainder | Worst LTV:CAC (0.42), 8.1% repeat, lowest revenue per customer | – |
| Do not cut Influencer | Highest CAC but best revenue per customer (₹2,858) and repeat rate (73.0%); LTV:CAC 0.89 is above Meta and Affiliate | – |
| No Composer/Airflow in the design | Five daily jobs do not justify its fixed cost; Cloud Workflows is enough | Many more pipelines with complex dependencies |
| LLM never writes free-form SQL | Controlled intent → approved template → validated query → read-only run removes the main hallucination and safety risks | – |

## What I would say about limitations (honestly)

- Six months of data: LTV here is a 0–6 month figure and June signups have had little time to repurchase.
- 150–350 new customers per channel per quarter: small monthly moves are noisy; Meta's rise is much larger than that noise.
- Meta's CAC rising while spend rises is **association, not proof** of saturation.
- The cut impact (82–199 fewer customers per quarter) is an illustration under stated assumptions, not a forecast.
- The Part 3 design is **not built or tested**. Only the SQL-template idea was prototyped on the Part 1 table. Salesforce, MoEngage and Meta connection details are unverified.

## How AI was used

Claude Code wrote and ran the code, drafted documents and charts, and was checked by independent recalculation, invariant checks, and viewing every rendered chart and PDF. Genuine slips that were caught: a revenue estimate that included duplicate rows (₹8.5 lakh vs the correct ₹7,79,790), newline-escaping errors in generated files, and overlapping chart labels.

## Likely interview questions – short answers

- **Why is Influencer protected despite the highest CAC?** CAC is only half of the picture: its customers spend about 3× Affiliate's and 73% buy again. Its LTV:CAC (0.89) is better than Meta's (0.62) and Affiliate's (0.42).
- **Why is the total exactly 20%?** Rule A (Meta back to Q1 spend) fixes ₹1,31,000; rule B takes the remainder (₹1,73,600 − ₹1,31,000 = ₹42,600) from the weakest other channel. An assertion in code and an independent check from the raw file confirm the sum.
- **How do you know the numbers are right?** Two separate routes (pandas/DuckDB vs plain Python on raw files) agree on 60/60 metrics; the check fails when I plant an error.
- **What if the CMO asks something the data cannot answer?** The assistant replies "not available" – no estimate is invented.
- **What would you do next?** Run a Meta spend holdout test; extend LTV with more months of data; verify the vendor APIs and build the pipeline in a staging project.
