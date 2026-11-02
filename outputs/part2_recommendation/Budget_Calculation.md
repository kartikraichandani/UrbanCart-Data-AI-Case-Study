# Budget Calculation (supporting appendix to the CMO memo)

All figures are produced by `src/analytics/budget_scenario.py` from the Part 1 results.

## Step 1 - Baseline
Baseline = Q2 2026 (Apr-Jun) paid spend, the latest quarter and therefore the run-rate "next quarter" is measured against.

| Channel | Q2 spend |
|---|---|
| Google Ads | Rs 205,000 |
| Meta Ads | Rs 339,000 |
| Affiliate | Rs 170,000 |
| Influencer | Rs 154,000 |
| **Total** | **Rs 868,000** |

## Step 2 - Target
20% x Rs 868,000 = **Rs 173,600** to cut. New quarterly paid budget = Rs 868,000 - Rs 173,600 = **Rs 694,400**.

## Step 3 - Allocate the cut (rule-based)
**Rule A - Meta Ads back to its Q1 spend.** Q1 -> Q2, Meta spend rose Rs 131,000 (+63.0%) while new customers rose only 17 (+5.2%).
That is Rs 7,706 of extra spend per extra customer, against an LTV of Rs 500.
Cut = Rs 339,000 - Rs 208,000 = **Rs 131,000** (38.6% of Meta's baseline).

**Rule B - the rest from the weakest remaining channel.** Affiliate has the lowest LTV:CAC (0.42) after Meta.
Cut = Rs 173,600 - Rs 131,000 = **Rs 42,600** (25.1% of its baseline; cap is 50%).

**Not cut:** Google Ads (best LTV:CAC, stable CAC) and Influencer (best revenue per customer and repeat rate; high CAC alone is not a reason to cut).

## Step 4 - Proof the total is exactly 20%
| Channel | Q2 baseline | Cut | New budget | Cut as % of channel |
|---|---|---|---|---|
| Google Ads | Rs 205,000 | Rs 0 | Rs 205,000 | 0.0% |
| Meta Ads | Rs 339,000 | Rs 131,000 | Rs 208,000 | 38.6% |
| Affiliate | Rs 170,000 | Rs 42,600 | Rs 127,400 | 25.1% |
| Influencer | Rs 154,000 | Rs 0 | Rs 154,000 | 0.0% |
| **Total** | **Rs 868,000** | **Rs 173,600** | **Rs 694,400** | **20.0%** |

Rs 131,000 + Rs 42,600 = Rs 173,600 = 20.0% x Rs 868,000. (Checked by an assertion in the code.)

## Step 5 - Estimated impact (illustrative, not a forecast)
Assumption: customers lost = cut / the channel's average Q2 CAC (the cut spend was as productive as average spend). Contribution lost = customers lost x LTV.

| Channel | Q2 avg CAC | LTV | Est. customers lost | Contribution lost | Spend saved | Net |
|---|---|---|---|---|---|---|
| Meta Ads | Rs 980 | Rs 500 | 134 | Rs 66,846 | Rs 131,000 | Rs 64,154 |
| Affiliate | Rs 656 | Rs 287 | 65 | Rs 18,637 | Rs 42,600 | Rs 23,963 |

- Pessimistic case: about **199** fewer paid new customers per quarter (18.2% of Q2's 1,094), contribution lost Rs 85,483, spend saved Rs 173,600, net Rs 88,117.
- Observed Meta marginal case: if Meta's cut loses only the 17 customers it added in Q2, total loss is about **82** customers (7.5%).
- So some volume loss is likely (roughly 7-18%), but each lost customer in these channels earns less contribution (LTV) than it cost (CAC), so the net effect on margin is positive under both views.

## Limitations (read before acting)
- **Correlation, not causation.** Meta's rising CAC coincides with its spend increase; saturation is the likely story but creative fatigue, seasonality, audience mix or tracking changes could contribute. This is not an experiment.
- **LTV is a 0-6 month figure** (revenue x 30%), not lifetime. Channels with slower repeat behaviour look worse than they may be; Affiliate's 8.1% repeat rate is the least ambiguous signal.
- **Small samples:** 150-350 new customers per channel per quarter.
- **Cohort maturity:** June signups had less time to place a first delivered order, which inflates Q2 CAC slightly for every channel.
- Past performance does not guarantee future performance; the estimates above assume the Q1-Q2 relationships continue.
- Baseline choice: Q2 run-rate. If finance defines the baseline differently (e.g. Jan-Jun average), re-run `budget_scenario.py` with those months.
