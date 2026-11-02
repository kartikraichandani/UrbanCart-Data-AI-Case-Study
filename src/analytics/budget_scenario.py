"""Budget-cut scenario for the CMO recommendation (20% cut of paid spend).

Transparent, rule-based allocation (no black box):
  1. BASELINE  = Q2 2026 (Apr-Jun) paid spend, the most recent quarter, i.e. the run-rate that
                 "next quarter" is compared against.
  2. TARGET    = 20% x baseline total, in whole rupees (must be exact).
  3. RULE A    = Meta Ads is cut back to its Q1 spend level. Evidence: from Q1 to Q2 its spend rose
                 by Rs 1.31 lakh (+63%) while its new customers rose by only 17 (+5%).
  4. RULE B    = The remainder of the target comes from the paid channel with the lowest LTV:CAC
                 other than Meta (Affiliate). Cut may not exceed 50% of that channel's baseline.
  5. Channels with LTV:CAC >= 0.85 and a stable CAC (Google Ads, Influencer) are not cut.
  6. CHECK     = sum of cuts == target exactly.

Impact estimate (illustrative, NOT a forecast): customers lost = cut / the channel's average Q2 CAC
(i.e. assumes the cut spend was as productive as average spend - a pessimistic assumption for
Meta, where marginal spend looks far less productive). Contribution lost = customers lost x LTV
(30% margin on Jan-Jun revenue per customer).
"""
import pandas as pd

from src import config as C

BASELINE_MONTHS = ["2026-04", "2026-05", "2026-06"]       # Q2
COMPARISON_MONTHS = ["2026-01", "2026-02", "2026-03"]     # Q1
CUT_TARGET_PCT = 20
MAX_SINGLE_CHANNEL_CUT_PCT = 50


def build_scenario(monthly: pd.DataFrame, ltv: pd.DataFrame) -> dict:
    """monthly: full-precision monthly table (channel, month, spend, new_customers).
    ltv: full-precision LTV table (channel, ltv, ltv_cac_ratio)."""
    q2 = monthly[monthly.month.isin(BASELINE_MONTHS)].groupby("channel")[["spend", "new_customers"]].sum()
    q1 = monthly[monthly.month.isin(COMPARISON_MONTHS)].groupby("channel")[["spend", "new_customers"]].sum()
    l = ltv.set_index("channel")

    baseline_total = int(q2["spend"].sum())
    target = baseline_total * CUT_TARGET_PCT // 100
    assert baseline_total * CUT_TARGET_PCT % 100 == 0, "target is not a whole rupee amount"

    # ---- Rule A: Meta back to Q1 level ----
    cuts = {ch: 0 for ch in C.PAID_CHANNELS}
    cuts["Meta Ads"] = int(q2.loc["Meta Ads", "spend"] - q1.loc["Meta Ads", "spend"])
    # ---- Rule B: remainder from the weakest remaining channel (lowest LTV:CAC excluding Meta) ----
    others = [c for c in C.PAID_CHANNELS if c != "Meta Ads"]
    second = min(others, key=lambda c: l.loc[c, "ltv_cac_ratio"])
    cuts[second] = target - cuts["Meta Ads"]
    assert cuts[second] >= 0, "Rule A alone already exceeds the target"
    assert cuts[second] <= q2.loc[second, "spend"] * MAX_SINGLE_CHANNEL_CUT_PCT / 100, "cap exceeded"
    assert sum(cuts.values()) == target, "cuts do not add up to the 20% target"

    rows = []
    for ch in C.PAID_CHANNELS:
        base, cut = int(q2.loc[ch, "spend"]), cuts[ch]
        q2_cust = int(q2.loc[ch, "new_customers"])
        q2_cac = base / q2_cust
        lost = cut / q2_cac
        rows.append({
            "channel": ch,
            "q1_spend": int(q1.loc[ch, "spend"]), "q2_baseline_spend": base,
            "q1_new_customers": int(q1.loc[ch, "new_customers"]), "q2_new_customers": q2_cust,
            "cut_inr": cut, "cut_pct_of_channel": 100 * cut / base,
            "new_budget": base - cut,
            "share_of_total_cut_pct": 100 * cut / target,
            "q2_avg_cac": q2_cac, "ltv": l.loc[ch, "ltv"], "ltv_cac_ratio": l.loc[ch, "ltv_cac_ratio"],
            "est_customers_lost": lost,
            "est_contribution_lost": lost * l.loc[ch, "ltv"],
            "est_net_gain": cut - lost * l.loc[ch, "ltv"],
        })
    t = pd.DataFrame(rows)

    # Meta observed marginal productivity Q1 -> Q2
    m_ds = q2.loc["Meta Ads", "spend"] - q1.loc["Meta Ads", "spend"]
    m_dc = q2.loc["Meta Ads", "new_customers"] - q1.loc["Meta Ads", "new_customers"]
    summary = {
        "baseline_total": baseline_total, "target": target, "new_total": baseline_total - target,
        "cut_total": int(t["cut_inr"].sum()), "second_channel": second,
        "meta_delta_spend": int(m_ds), "meta_delta_customers": int(m_dc),
        "meta_delta_spend_pct": 100 * m_ds / q1.loc["Meta Ads", "spend"],
        "meta_delta_customers_pct": 100 * m_dc / q1.loc["Meta Ads", "new_customers"],
        "meta_marginal_cac": m_ds / m_dc,
        "q2_new_customers_total": int(q2["new_customers"].sum()),
        "est_customers_lost_pessimistic": t["est_customers_lost"].sum(),
        "est_customers_lost_meta_marginal": m_dc + t.set_index("channel").loc[second, "est_customers_lost"],
        "est_contribution_lost": t["est_contribution_lost"].sum(),
        "est_net_gain": t["est_net_gain"].sum(),
        "q2_blended_cac": baseline_total / q2["new_customers"].sum(),
    }
    return {"table": t, "summary": summary}


def scenario_output_table(t: pd.DataFrame) -> pd.DataFrame:
    """Rounded output: money to nearest rupee, percentages to 1 decimal, customers to whole numbers."""
    o = t.copy()
    for c in ["q2_avg_cac", "ltv", "est_contribution_lost", "est_net_gain"]:
        o[c] = o[c].round(0).astype("int64")
    for c in ["cut_pct_of_channel", "share_of_total_cut_pct"]:
        o[c] = o[c].round(1)
    o["ltv_cac_ratio"] = o["ltv_cac_ratio"].round(2)
    o["est_customers_lost"] = o["est_customers_lost"].round(0).astype("int64")
    total = {"channel": "Total paid", "q1_spend": o.q1_spend.sum(), "q2_baseline_spend": o.q2_baseline_spend.sum(),
             "q1_new_customers": o.q1_new_customers.sum(), "q2_new_customers": o.q2_new_customers.sum(),
             "cut_inr": o.cut_inr.sum(), "new_budget": o.new_budget.sum(),
             "cut_pct_of_channel": round(100 * o.cut_inr.sum() / o.q2_baseline_spend.sum(), 1),
             "share_of_total_cut_pct": round(o.share_of_total_cut_pct.sum(), 1),
             "est_customers_lost": o.est_customers_lost.sum(), "est_contribution_lost": o.est_contribution_lost.sum(),
             "est_net_gain": o.est_net_gain.sum()}
    return pd.concat([o, pd.DataFrame([total])], ignore_index=True)


def budget_calculation_markdown(res: dict) -> str:
    t, s = res["table"].set_index("channel"), res["summary"]
    a = t.loc["Meta Ads"]
    b = t.loc[s["second_channel"]]
    f = lambda x: f"Rs {x:,.0f}"
    return f"""# Budget Calculation (supporting appendix to the CMO memo)

All figures are produced by `src/analytics/budget_scenario.py` from the Part 1 results.

## Step 1 - Baseline
Baseline = Q2 2026 (Apr-Jun) paid spend, the latest quarter and therefore the run-rate "next quarter" is measured against.

| Channel | Q2 spend |
|---|---|
""" + "\n".join(f"| {ch} | {f(t.loc[ch, 'q2_baseline_spend'])} |" for ch in C.PAID_CHANNELS) + f"""
| **Total** | **{f(s['baseline_total'])}** |

## Step 2 - Target
20% x {f(s['baseline_total'])} = **{f(s['target'])}** to cut. New quarterly paid budget = {f(s['baseline_total'])} - {f(s['target'])} = **{f(s['new_total'])}**.

## Step 3 - Allocate the cut (rule-based)
**Rule A - Meta Ads back to its Q1 spend.** Q1 -> Q2, Meta spend rose {f(s['meta_delta_spend'])} (+{s['meta_delta_spend_pct']:.1f}%) while new customers rose only {s['meta_delta_customers']} (+{s['meta_delta_customers_pct']:.1f}%).
That is {f(s['meta_marginal_cac'])} of extra spend per extra customer, against an LTV of {f(a['ltv'])}.
Cut = {f(a['q2_baseline_spend'])} - {f(a['q1_spend'])} = **{f(a['cut_inr'])}** ({a['cut_pct_of_channel']:.1f}% of Meta's baseline).

**Rule B - the rest from the weakest remaining channel.** {s['second_channel']} has the lowest LTV:CAC ({b['ltv_cac_ratio']:.2f}) after Meta.
Cut = {f(s['target'])} - {f(a['cut_inr'])} = **{f(b['cut_inr'])}** ({b['cut_pct_of_channel']:.1f}% of its baseline; cap is 50%).

**Not cut:** Google Ads (best LTV:CAC, stable CAC) and Influencer (best revenue per customer and repeat rate; high CAC alone is not a reason to cut).

## Step 4 - Proof the total is exactly 20%
| Channel | Q2 baseline | Cut | New budget | Cut as % of channel |
|---|---|---|---|---|
""" + "\n".join(f"| {ch} | {f(t.loc[ch, 'q2_baseline_spend'])} | {f(t.loc[ch, 'cut_inr'])} | {f(t.loc[ch, 'new_budget'])} | {t.loc[ch, 'cut_pct_of_channel']:.1f}% |" for ch in C.PAID_CHANNELS) + f"""
| **Total** | **{f(s['baseline_total'])}** | **{f(s['cut_total'])}** | **{f(s['new_total'])}** | **{100 * s['cut_total'] / s['baseline_total']:.1f}%** |

{f(a['cut_inr'])} + {f(b['cut_inr'])} = {f(s['cut_total'])} = 20.0% x {f(s['baseline_total'])}. (Checked by an assertion in the code.)

## Step 5 - Estimated impact (illustrative, not a forecast)
Assumption: customers lost = cut / the channel's average Q2 CAC (the cut spend was as productive as average spend). Contribution lost = customers lost x LTV.

| Channel | Q2 avg CAC | LTV | Est. customers lost | Contribution lost | Spend saved | Net |
|---|---|---|---|---|---|---|
""" + "\n".join(f"| {ch} | {f(t.loc[ch, 'q2_avg_cac'])} | {f(t.loc[ch, 'ltv'])} | {t.loc[ch, 'est_customers_lost']:.0f} | {f(t.loc[ch, 'est_contribution_lost'])} | {f(t.loc[ch, 'cut_inr'])} | {f(t.loc[ch, 'est_net_gain'])} |" for ch in [a.name, b.name]) + f"""

- Pessimistic case: about **{s['est_customers_lost_pessimistic']:.0f}** fewer paid new customers per quarter ({100 * s['est_customers_lost_pessimistic'] / s['q2_new_customers_total']:.1f}% of Q2's {s['q2_new_customers_total']:,}), contribution lost {f(s['est_contribution_lost'])}, spend saved {f(s['target'])}, net {f(s['est_net_gain'])}.
- Observed Meta marginal case: if Meta's cut loses only the {s['meta_delta_customers']} customers it added in Q2, total loss is about **{s['est_customers_lost_meta_marginal']:.0f}** customers ({100 * s['est_customers_lost_meta_marginal'] / s['q2_new_customers_total']:.1f}%).
- So some volume loss is likely (roughly {100 * s['est_customers_lost_meta_marginal'] / s['q2_new_customers_total']:.0f}-{100 * s['est_customers_lost_pessimistic'] / s['q2_new_customers_total']:.0f}%), but each lost customer in these channels earns less contribution (LTV) than it cost (CAC), so the net effect on margin is positive under both views.

## Limitations (read before acting)
- **Correlation, not causation.** Meta's rising CAC coincides with its spend increase; saturation is the likely story but creative fatigue, seasonality, audience mix or tracking changes could contribute. This is not an experiment.
- **LTV is a 0-6 month figure** (revenue x 30%), not lifetime. Channels with slower repeat behaviour look worse than they may be; Affiliate's 8.1% repeat rate is the least ambiguous signal.
- **Small samples:** 150-350 new customers per channel per quarter.
- **Cohort maturity:** June signups had less time to place a first delivered order, which inflates Q2 CAC slightly for every channel.
- Past performance does not guarantee future performance; the estimates above assume the Q1-Q2 relationships continue.
- Baseline choice: Q2 run-rate. If finance defines the baseline differently (e.g. Jan-Jun average), re-run `budget_scenario.py` with those months.
"""
