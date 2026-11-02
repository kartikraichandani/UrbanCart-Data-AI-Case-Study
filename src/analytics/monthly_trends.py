"""Monthly CAC trend per paid channel.

Monthly CAC = that month's channel spend /
              new customers who SIGNED UP in that month and placed >= 1 delivered order
              (the delivered order may fall in any month up to June).

Zero-customer months have an undefined CAC (NaN) - never a division by zero or a fake 0.
Caveat: later signup months have had less time to place their first delivered order, so
recent months can be slightly understated in customers (-> overstated CAC).
"""
import numpy as np
import pandas as pd

from src import config as C


def compute_monthly_cac(cleaned, customers) -> pd.DataFrame:
    spend = cleaned["spend"].set_index(["channel", "month"])["spend_inr"]
    cust = customers.groupby(["channel", "signup_month"]).size()
    rows = []
    for ch in C.PAID_CHANNELS:
        for m in C.MONTHS:
            s = float(spend.get((ch, m), np.nan))
            n = int(cust.get((ch, m), 0))
            rows.append({"channel": ch, "month": m, "spend": s, "new_customers": n,
                         "cac": s / n if n > 0 else np.nan})
    return pd.DataFrame(rows)


def compute_change_summary(monthly: pd.DataFrame) -> pd.DataFrame:
    """January -> June change, plus a 6-month slope as a noise check on the endpoints."""
    rows = []
    for ch in C.PAID_CHANNELS:
        d = monthly[monthly.channel == ch].set_index("month")
        jan, jun = d.loc[C.MONTHS[0], "cac"], d.loc[C.MONTHS[-1], "cac"]
        if np.isnan(jan) or np.isnan(jun):
            abs_ch = pct_ch = np.nan                      # undefined if an endpoint month has no customers
        else:
            abs_ch, pct_ch = jun - jan, 100 * (jun - jan) / jan
        ok = d["cac"].notna()
        x = np.arange(len(C.MONTHS))[ok.values]
        slope = np.polyfit(x, d.loc[ok, "cac"].values, 1)[0] if ok.sum() >= 3 else np.nan
        if np.isnan(abs_ch):
            direction = "undefined"
        else:
            direction = "increasing" if abs_ch > 0 else "decreasing" if abs_ch < 0 else "flat"
        rows.append({"channel": ch, "jan_cac": jan, "jun_cac": jun, "abs_change": abs_ch,
                     "pct_change": pct_ch, "slope_per_month": slope, "direction_jan_to_jun": direction,
                     "months_with_undefined_cac": int((~ok).sum())})
    return pd.DataFrame(rows)


def monthly_table(cleaned, customers):
    """Output versions (money -> rupee, % -> 1 decimal). Undefined CAC is written as blank + note."""
    m = compute_monthly_cac(cleaned, customers)
    m["spend"] = m["spend"].round(0).astype("int64")
    m["cac_note"] = np.where(m["cac"].isna(), "undefined (0 new customers)", "")
    m["cac"] = m["cac"].round(0)
    s = compute_change_summary(compute_monthly_cac(cleaned, customers))
    for c in ["jan_cac", "jun_cac", "abs_change", "slope_per_month"]:
        s[c] = s[c].round(0)
    s["pct_change"] = s["pct_change"].round(1)
    return m, s
