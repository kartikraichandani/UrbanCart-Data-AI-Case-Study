"""Acquisition analysis for the four paid channels (spend, new customers, CAC).

CAC = total channel spend (Jan-Jun 2026) / new customers.
New customer = user with >= 1 delivered order, attributed to their acquisition channel.
Signups are shown only as context - they are NOT used as 'customers'.
"""
import pandas as pd

from src import config as C


def compute_acquisition(cleaned: dict[str, pd.DataFrame], customers: pd.DataFrame) -> pd.DataFrame:
    spend = cleaned["spend"].groupby("channel")["spend_inr"].sum()
    new_cust = customers.groupby("channel").size()
    signups = cleaned["users"].groupby("acquisition_channel").size()
    rows = []
    for ch in C.PAID_CHANNELS:
        n = int(new_cust.get(ch, 0))
        s = float(spend[ch])
        rows.append({
            "channel": ch,
            "total_spend": s,
            "signups": int(signups.get(ch, 0)),
            "new_customers": n,
            # Zero customers would make CAC undefined; handled as NaN, never a division error.
            "cac": s / n if n > 0 else float("nan"),
        })
    t = pd.DataFrame(rows)
    t["signup_to_customer_pct"] = 100 * t["new_customers"] / t["signups"]
    return t


def acquisition_table(cleaned, customers) -> pd.DataFrame:
    """Output version: money to nearest rupee, percentages to 1 decimal."""
    t = compute_acquisition(cleaned, customers)
    t["total_spend"] = t["total_spend"].round(0).astype("int64")
    t["cac"] = t["cac"].round(0)
    t["signup_to_customer_pct"] = t["signup_to_customer_pct"].round(1)
    total = {"channel": "All paid", "total_spend": int(t["total_spend"].sum()),
             "signups": int(t["signups"].sum()), "new_customers": int(t["new_customers"].sum())}
    total["cac"] = round(total["total_spend"] / total["new_customers"])
    total["signup_to_customer_pct"] = round(100 * total["new_customers"] / total["signups"], 1)
    return pd.concat([t, pd.DataFrame([total])], ignore_index=True)
