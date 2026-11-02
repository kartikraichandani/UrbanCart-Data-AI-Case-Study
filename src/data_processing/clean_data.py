"""Apply the handling decisions documented in the data-quality report.

Rules followed:
  * Raw files are never modified; cleaned copies go to data/processed/.
  * No record is silently dropped: every exclusion is written to excluded_records.csv
    with a reason, and row counts are reconciled (raw = cleaned + excluded).
  * No imputation. A blank channel becomes 'Unknown' (never 'Organic').
  * Cancelled/returned orders are KEPT but flagged is_successful=False.
"""
import pandas as pd

from src import config as C
from src.data_processing.load_data import load_raw


def _record_string(row: pd.Series) -> str:
    return "|".join(f"{k}={v}" for k, v in row.items())


def _excluded(table: str, df: pd.DataFrame, key: str, reason: str) -> pd.DataFrame:
    return pd.DataFrame({
        "source_table": table,
        "record_id": df[key].values,
        "reason": reason,
        "raw_record": df.apply(_record_string, axis=1).values,
    })


def clean_all(raw: dict[str, pd.DataFrame] | None = None):
    """Return (cleaned dict, exclusion log DataFrame, reconciliation DataFrame)."""
    raw = raw or load_raw()
    users, orders, spend = (raw[k].copy() for k in ("users", "orders", "spend"))
    log = []

    # ---------------- users ----------------
    users["acquisition_channel"] = users["acquisition_channel"].str.strip()
    is_test = users["email"].str.lower().str.split("@").str[1] == C.INTERNAL_EMAIL_DOMAIN
    test_ids = set(users.loc[is_test, "user_id"])
    log.append(_excluded("users", users[is_test], "user_id", "internal_qa_test_account"))
    users_c = users[~is_test].copy()

    blank = users_c["acquisition_channel"] == ""
    users_c["channel_was_blank"] = blank
    users_c.loc[blank, "acquisition_channel"] = C.UNKNOWN_CHANNEL     # NOT Organic, NOT imputed
    users_c["signup_date"] = pd.to_datetime(users_c["signup_date"], format="%Y-%m-%d")
    users_c["signup_month"] = users_c["signup_date"].dt.strftime("%Y-%m")
    users_c["user_id"] = users_c["user_id"].astype("int64")

    # ---------------- orders ----------------
    # Step 1: exact duplicates (same order_id AND identical content) -> keep first occurrence.
    dup_mask = orders.duplicated(keep="first")
    log.append(_excluded("orders", orders[dup_mask], "order_id", "exact_duplicate_row"))
    orders_d = orders[~dup_mask]
    assert orders_d["order_id"].is_unique, "same order_id with conflicting content - needs manual review"
    # Step 2: orders belonging to internal test accounts (applied after step 1 so no row is logged twice).
    test_o = orders_d["user_id"].isin(test_ids)
    log.append(_excluded("orders", orders_d[test_o], "order_id", "internal_qa_test_account_order"))
    orders_c = orders_d[~test_o].copy()

    orders_c["order_date"] = pd.to_datetime(orders_c["order_date"], format="%Y-%m-%d")
    orders_c["order_month"] = orders_c["order_date"].dt.strftime("%Y-%m")
    orders_c["order_value"] = orders_c["order_value"].astype(float).round().astype("int64")
    orders_c["order_id"] = orders_c["order_id"].astype("int64")
    orders_c["user_id"] = orders_c["user_id"].astype("int64")
    # Successful = status delivered (brief). Cancelled/returned are retained but never counted as revenue.
    orders_c["is_successful"] = orders_c["status"] == C.SUCCESS_STATUS

    # ---------------- spend ----------------
    spend_c = spend.copy()
    spend_c["spend_inr"] = spend_c["spend_inr"].astype(float).round().astype("int64")

    cleaned = {"users": users_c.reset_index(drop=True),
               "orders": orders_c.reset_index(drop=True),
               "spend": spend_c.reset_index(drop=True)}
    exclusions = pd.concat(log, ignore_index=True)

    # ---------------- reconciliation: raw = cleaned + excluded ----------------
    rec = []
    for t in ("users", "orders", "spend"):
        n_raw, n_clean = len(raw[t]), len(cleaned[t])
        n_ex = int((exclusions["source_table"] == t).sum())
        assert n_raw == n_clean + n_ex, f"{t}: rows do not reconcile"
        rec.append({"table": t, "raw_rows": n_raw, "excluded_rows": n_ex, "cleaned_rows": n_clean})
    # referential integrity of the cleaned set
    assert orders_c["user_id"].isin(users_c["user_id"]).all(), "orphan orders after cleaning"
    return cleaned, exclusions, pd.DataFrame(rec)


# Column documentation used to generate data/data_dictionary.md from the REAL cleaned schemas.
_DESC = {
    "users": ("One row per real user who signed up Jan-Jun 2026 (test accounts removed).", {
        "user_id": "Unique user identifier (primary key).",
        "signup_date": "Date the user signed up (YYYY-MM-DD).",
        "city": "City of the user (8 cities, no cleaning needed).",
        "acquisition_channel": "Google Ads, Meta Ads, Affiliate, Influencer, Organic, or 'Unknown' (blank in source; never imputed).",
        "email": "User email (not used in metrics).",
        "channel_was_blank": "True where the source channel was blank and was relabelled 'Unknown'.",
        "signup_month": "Signup month as YYYY-MM; used to group customers by cohort month for monthly CAC."}),
    "orders": ("One row per unique order (exact duplicates and test-account orders removed).", {
        "order_id": "Unique order identifier (primary key).",
        "user_id": "Foreign key to users.user_id.",
        "order_date": "Date of the order (YYYY-MM-DD).",
        "order_value": "Order value in INR, whole rupees.",
        "status": "delivered, cancelled or returned.",
        "order_month": "Order month as YYYY-MM.",
        "is_successful": "True only when status = 'delivered'. Only these orders count as revenue / customers."}),
    "spend": ("Monthly paid spend per channel, as supplied (no changes).", {
        "month": "Month as YYYY-MM.",
        "channel": "Paid channel: Google Ads, Meta Ads, Affiliate, Influencer.",
        "spend_inr": "Marketing spend in INR for that month and channel."}),
}


def write_data_dictionary(cleaned: dict[str, pd.DataFrame], path=None) -> None:
    path = path or C.ROOT / "data" / "data_dictionary.md"
    lines = ["# Data Dictionary (cleaned datasets)", "",
             "Generated from the actual files in `data/processed/` by `src/data_processing/clean_data.py`.", ""]
    for t, fname in (("users", "users_cleaned.csv"), ("orders", "orders_cleaned.csv"), ("spend", "marketing_spend_cleaned.csv")):
        df = cleaned[t]
        desc, cols = _DESC[t]
        lines += [f"## `{fname}`", desc, f"Rows: **{len(df):,}**", "",
                  "| Column | Type | Description |", "|---|---|---|"]
        for c in df.columns:
            lines.append(f"| `{c}` | {df[c].dtype} | {cols[c]} |")
        lines.append("")
    lines += ["## Other generated files", "",
              "- `data/processed/excluded_records.csv` - every record removed during cleaning, with reason and the raw row.",
              "- `outputs/part1_analysis/data_quality_report.csv` - all checks, counts, handling and justification.", "",
              "## Keys and rules", "",
              "- `users.user_id` and `orders.order_id` are unique; every `orders.user_id` exists in `users`.",
              "- Successful order = `status == 'delivered'` (`is_successful`).",
              "- A *customer* = user with >= 1 successful order (derived in analytics, not stored).",
              "- Spend covers 4 paid channels x 6 months = 24 rows. Organic has no spend."]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def save_cleaned(cleaned, exclusions, reconciliation) -> None:
    C.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    cleaned["users"].to_csv(C.PROCESSED_DIR / "users_cleaned.csv", index=False)
    cleaned["orders"].to_csv(C.PROCESSED_DIR / "orders_cleaned.csv", index=False)
    cleaned["spend"].to_csv(C.PROCESSED_DIR / "marketing_spend_cleaned.csv", index=False)
    exclusions.to_csv(C.PROCESSED_DIR / "excluded_records.csv", index=False)
    reconciliation.to_csv(C.PART1_DIR / "cleaning_reconciliation.csv", index=False)
    write_data_dictionary(cleaned)


if __name__ == "__main__":
    c, e, rec = clean_all()
    save_cleaned(c, e, rec)
    print(rec.to_string(index=False))
    print(e.groupby(["source_table", "reason"]).size())
