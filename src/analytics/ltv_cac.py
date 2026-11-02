"""LTV and LTV:CAC.

Brief definition (used exactly, no lifetime extrapolation):
    LTV     = revenue per customer x contribution margin (30%)
    LTV:CAC = LTV / CAC

LIMITATION: revenue per customer only covers Jan-Jun 2026. Customers who signed up in
June have had days, not months, to buy again, so this "LTV" is a 0-6 month realised
value, not a true lifetime value. It is used for comparing channels, not as a forecast.
Organic has no marketing spend, so only its LTV is shown; no CAC / ratio is invented.
"""
import numpy as np
import pandas as pd

from src import config as C
from src.analytics.acquisition_metrics import compute_acquisition
from src.analytics.customer_value import compute_customer_value


def compute_ltv_cac(cleaned, customers) -> pd.DataFrame:
    cv = compute_customer_value(customers).set_index("channel")
    acq = compute_acquisition(cleaned, customers).set_index("channel")
    rows = []
    for ch in C.VALID_CHANNELS:                         # paid channels + Organic (Unknown excluded)
        rpc = cv.loc[ch, "revenue_per_customer"]
        ltv = rpc * C.CONTRIBUTION_MARGIN
        paid = ch in C.PAID_CHANNELS
        cac = acq.loc[ch, "cac"] if paid else np.nan
        rows.append({
            "channel": ch, "revenue_per_customer": rpc,
            "contribution_margin_pct": C.CONTRIBUTION_MARGIN * 100,
            "ltv": ltv, "cac": cac,
            "ltv_cac_ratio": ltv / cac if paid and cac > 0 else np.nan,
            "net_value_per_customer": ltv - cac if paid else np.nan,   # LTV minus CAC
            "repeat_purchase_rate_pct": cv.loc[ch, "repeat_purchase_rate_pct"],
        })
    t = pd.DataFrame(rows)
    # Rank paid channels by LTV:CAC (1 = best). Organic stays unranked.
    t["ltv_cac_rank"] = t["ltv_cac_ratio"].rank(ascending=False, method="min")
    return t


def ltv_cac_table(cleaned, customers) -> pd.DataFrame:
    """Output version. Money -> nearest rupee, percentages -> 1 decimal, ratio -> 2 decimals."""
    t = compute_ltv_cac(cleaned, customers)
    for c in ["revenue_per_customer", "ltv", "cac", "net_value_per_customer"]:
        t[c] = t[c].round(0)
    t["ltv_cac_ratio"] = t["ltv_cac_ratio"].round(2)
    t["repeat_purchase_rate_pct"] = t["repeat_purchase_rate_pct"].round(1)
    t["contribution_margin_pct"] = t["contribution_margin_pct"].round(1)
    t["ltv_cac_rank"] = t["ltv_cac_rank"].astype("Int64")
    t["note"] = np.where(
        t["channel"] == C.ORGANIC_CHANNEL,
        "No organic marketing spend supplied -> CAC and LTV:CAC not calculated",
        np.where(t["ltv_cac_ratio"] < 1, "LTV below CAC (not recovered by Jan-Jun margin)", "LTV above CAC"))
    return t
