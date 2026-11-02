"""Customer base and customer-value metrics (brief section: Customer value).

Definitions (from Case_Study_Brief.pdf - unchanged):
  * successful order      = status 'delivered'
  * customer / new customer = user with >= 1 successful order, counted under their acquisition channel
  * Revenue per customer  = delivered revenue / customers      (full Jan-Jun period)
  * Repeat purchase rate  = customers with >= 2 delivered orders / customers * 100
DENOMINATOR for both ratios = customers with at least one delivered order (NOT all signups).
"""
import duckdb
import pandas as pd

from src import config as C


def build_customer_table(cleaned: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """One row per customer (user with >= 1 delivered order).

    Columns: user_id, channel, signup_month, delivered_orders, delivered_revenue.
    Cancelled / returned orders are excluded here, so they can never count as revenue.
    """
    con = duckdb.connect()
    con.register("users", cleaned["users"])
    con.register("orders", cleaned["orders"])
    return con.execute("""
        SELECT u.user_id, u.acquisition_channel AS channel, u.signup_month,
               count(*)           AS delivered_orders,
               sum(o.order_value) AS delivered_revenue
        FROM users u
        JOIN orders o ON o.user_id = u.user_id AND o.is_successful
        GROUP BY u.user_id, u.acquisition_channel, u.signup_month
    """).df()


def compute_customer_value(customers: pd.DataFrame) -> pd.DataFrame:
    """Full-precision customer value per channel (Organic and Unknown included)."""
    g = customers.groupby("channel")
    out = pd.DataFrame({
        "customers": g.size(),
        "total_revenue": g["delivered_revenue"].sum(),
        "repeat_customers": g["delivered_orders"].apply(lambda s: int((s >= 2).sum())),
    })
    out["revenue_per_customer"] = out["total_revenue"] / out["customers"]
    out["repeat_purchase_rate_pct"] = 100 * out["repeat_customers"] / out["customers"]
    order = C.VALID_CHANNELS + [C.UNKNOWN_CHANNEL]
    return out.reindex([c for c in order if c in out.index]).rename_axis("channel").reset_index()


def customer_value_table(customers: pd.DataFrame) -> pd.DataFrame:
    """Output version: money to the nearest rupee, percentages to 1 decimal."""
    t = compute_customer_value(customers)
    t["total_revenue"] = t["total_revenue"].round(0).astype("int64")
    t["revenue_per_customer"] = t["revenue_per_customer"].round(0).astype("int64")
    t["repeat_purchase_rate_pct"] = t["repeat_purchase_rate_pct"].round(1)
    t["customer_denominator"] = "customers with >=1 delivered order"
    return t
