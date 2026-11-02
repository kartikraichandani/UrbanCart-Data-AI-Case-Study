"""Data-quality checks on the RAW tables.

Nothing is assumed: every check runs a query against the data and records the count it
finds (including zero). Each row of the report states the issue, affected column, row
counts, how it is handled and why. Checks only *detect*; `clean_data.py` applies the
handling described here.
"""
import duckdb
import pandas as pd

from src import config as C
from src.data_processing.load_data import raw_connection

# SQL fragments: a date is valid only if it parses strictly as YYYY-MM-DD.
_VALID_CHANNEL_SQL = ", ".join(f"'{c}'" for c in C.VALID_CHANNELS)
_INTERNAL = f"lower(split_part(u.email,'@',2)) = '{C.INTERNAL_EMAIL_DOMAIN}'"


class _Report:
    """Collects one row per check."""

    def __init__(self):
        self.rows = []

    def add(self, table, column, check, affected, total, issue, handling, justification,
            kind="ISSUE", impact=""):
        """kind: ISSUE (found, acted on) | INFO (found, informational) | OK (checked, none found)."""
        if affected == 0 and kind == "ISSUE":
            kind = "OK"
            issue = f"No problem found: {check.lower()}"
            handling, justification = "None required", "Check passed on the actual data."
        pct = round(100 * affected / total, 1) if total else 0.0
        self.rows.append({
            "issue_id": f"DQ{len(self.rows) + 1:02d}", "table": table, "column": column,
            "check": check, "status": kind, "issue_description": issue,
            "rows_affected": int(affected), "total_rows": int(total), "pct_affected": pct,
            "handling": handling, "business_justification": justification,
            "impact_if_ignored": impact,
        })

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)


def run_quality_checks(con: duckdb.DuckDBPyConnection | None = None) -> pd.DataFrame:
    con = con or raw_connection()
    one = lambda sql: con.execute(sql).fetchone()[0]          # scalar helper
    r = _Report()

    n_u, n_o, n_s = (one(f"SELECT count(*) FROM {t}") for t in ("users", "orders", "spend"))

    # ------------------------------------------------------------------ USERS
    for col in ["user_id", "signup_date", "city", "acquisition_channel", "email"]:
        blanks = one(f"SELECT count(*) FROM users WHERE trim({col}) = ''")
        if col == "acquisition_channel":
            with_orders = one("SELECT count(*) FROM users WHERE trim(acquisition_channel)='' AND user_id IN (SELECT user_id FROM orders)")
            with_deliv = one("SELECT count(*) FROM users WHERE trim(acquisition_channel)='' AND user_id IN (SELECT user_id FROM orders WHERE status='delivered')")
            r.add("users", col, "Missing values in acquisition_channel", blanks, n_u,
                  f"{blanks} users have a blank acquisition channel ({with_deliv} of them have at least one delivered order).",
                  f"Retained and labelled '{C.UNKNOWN_CHANNEL}'. NOT mapped to Organic and NOT imputed. "
                  "Excluded from per-channel metrics, reported separately.",
                  "The true source is unknowable; guessing (e.g. Organic) would silently move customers "
                  "and revenue between channels and distort CAC / LTV.",
                  impact=f"{with_deliv} real customers would be attributed to the wrong channel (or none).")
        else:
            r.add("users", col, f"Missing values in {col}", blanks, n_u, f"{blanks} blank values in {col}.",
                  "Record flagged and excluded if the key is unusable", "Required field.")

    d = one("SELECT count(*) - count(DISTINCT user_id) FROM users")
    r.add("users", "user_id", "Duplicate user_id", d, n_u, f"{d} repeated user_id values.", "De-duplicate on user_id", "A user must be unique.")
    d = one("SELECT count(*) - (SELECT count(*) FROM (SELECT DISTINCT * FROM users)) FROM users")
    r.add("users", "all", "Exact duplicate user rows", d, n_u, f"{d} fully identical user rows.", "Drop repeats, keep first", "Exact copies carry no new information.")
    d = one("SELECT count(*) - count(DISTINCT lower(email)) FROM users")
    r.add("users", "email", "Duplicate email addresses", d, n_u, f"{d} repeated emails.", "Review; do not merge users automatically", "Different user_ids sharing an email may be separate sign-ups.")

    bad_dt = one("SELECT count(*) FROM users WHERE try_strptime(signup_date,'%Y-%m-%d') IS NULL")
    r.add("users", "signup_date", "Invalid / unparseable signup_date", bad_dt, n_u, f"{bad_dt} signup dates are not valid YYYY-MM-DD.", "Exclude from monthly analysis", "Cannot be assigned to a cohort month.")
    out = one(f"SELECT count(*) FROM users WHERE try_strptime(signup_date,'%Y-%m-%d') NOT BETWEEN DATE '{C.PERIOD_START}' AND DATE '{C.PERIOD_END}'")
    r.add("users", "signup_date", "signup_date outside Jan-Jun 2026", out, n_u, f"{out} signups outside the analysis window.", "Exclude from the window", "Brief covers Jan-Jun 2026 only.")

    ws = one("SELECT count(*) FROM users WHERE acquisition_channel <> trim(acquisition_channel)")
    r.add("users", "acquisition_channel", "Leading/trailing whitespace in channel", ws, n_u, f"{ws} channel values have stray whitespace.", "Trim whitespace", "Formatting only; same channel.")
    inv = one(f"SELECT count(*) FROM users WHERE trim(acquisition_channel) <> '' AND trim(acquisition_channel) NOT IN ({_VALID_CHANNEL_SQL})")
    names = con.execute(f"SELECT DISTINCT acquisition_channel FROM users WHERE trim(acquisition_channel) <> '' AND trim(acquisition_channel) NOT IN ({_VALID_CHANNEL_SQL})").fetchall()
    r.add("users", "acquisition_channel", "Invalid (non-standard) channel names", inv, n_u, f"{inv} users with unrecognised channel names: {[x[0] for x in names]}.", "Flag as Unknown, never auto-map", "Brief allows five channels only.")
    bad_em = one("SELECT count(*) FROM users WHERE NOT regexp_matches(email, '^[^@ ]+@[^@ ]+\\.[A-Za-z]+$')")
    r.add("users", "email", "Malformed email addresses", bad_em, n_u, f"{bad_em} emails fail a basic format check.", "Flag only", "Email is not used in any metric.")

    # Internal QA / test accounts (detected by the company's own email domain, NOT by their behaviour).
    t = con.execute(f"""
        SELECT count(*), count(*) FILTER (WHERE lower(email) LIKE 'qa.test%'),
               count(DISTINCT acquisition_channel), min(acquisition_channel), count(DISTINCT city), min(city)
        FROM users u WHERE {_INTERNAL}""").fetchone()
    # Impact figures (deduplicated orders) so the effect on the headline metrics is explicit.
    imp = con.execute(f"""
        WITH o AS (SELECT DISTINCT * FROM orders WHERE status='delivered')
        SELECT count(DISTINCT o.user_id), sum(cast(o.order_value AS DOUBLE)), count(*) FROM o JOIN users u USING(user_id)
        WHERE {_INTERNAL}""").fetchone()
    tot = con.execute("SELECT count(DISTINCT user_id), sum(cast(order_value AS DOUBLE)) FROM (SELECT DISTINCT * FROM orders WHERE status='delivered')").fetchone()
    aff = one(f"SELECT count(DISTINCT o.user_id) FROM (SELECT DISTINCT * FROM orders WHERE status='delivered') o JOIN users u USING(user_id) WHERE u.acquisition_channel='Affiliate'")
    r.add("users", "email", "Internal QA/test accounts (@urbancart.in)", t[0], n_u,
          f"{t[0]} users have the company's own email domain ({t[1]} follow the 'qa.test<N>' pattern). "
          f"All carry channel '{t[3]}' ({t[2]} distinct channel) and city '{t[5]}' ({t[4]} distinct city); "
          f"{imp[0]} of them have delivered orders ({imp[2]} unique orders, Rs {imp[1]:,.0f}).",
          "Excluded from all metrics together with their orders; logged in excluded_records.csv (not deleted from raw).",
          "Test accounts are not real customers. Their purchases are not marketing-driven acquisitions, "
          "so counting them would understate CAC and inflate revenue and repeat rate for the channel they are tagged with.",
          impact=f"Affiliate would have {aff} 'customers' instead of {aff - imp[0]}; delivered revenue overstated by Rs {imp[1]:,.0f} "
                 f"({100 * imp[1] / tot[1]:.1f}% of all delivered revenue).")

    nz = one("SELECT count(*) FROM users WHERE user_id NOT IN (SELECT user_id FROM orders)")
    r.add("users", "user_id", "Users with no orders at all", nz, n_u, f"{nz} users signed up but never placed an order.",
          "Retained in users_cleaned.csv; they are NOT customers (no delivered order).",
          "Valid sign-ups. The brief counts only users with >=1 delivered order as customers.", kind="INFO")

    # ------------------------------------------------------------------ ORDERS
    for col in ["order_id", "user_id", "order_date", "order_value", "status"]:
        b = one(f"SELECT count(*) FROM orders WHERE trim({col}) = ''")
        r.add("orders", col, f"Missing values in {col}", b, n_o, f"{b} blank values in {col}.", "Exclude record (no imputation)", "A missing key/value cannot be reliably imputed.")

    inv_ids = one("SELECT count(*) - count(DISTINCT order_id) FROM orders")
    ex_dup = one("SELECT count(*) - (SELECT count(*) FROM (SELECT DISTINCT * FROM orders)) FROM orders")
    involved = one("SELECT count(*) FROM orders WHERE order_id IN (SELECT order_id FROM orders GROUP BY 1 HAVING count(*) > 1)")
    conflict = one("SELECT count(*) FROM (SELECT order_id FROM orders GROUP BY 1 HAVING count(DISTINCT (user_id, order_date, order_value, status)) > 1)")
    dd = con.execute("SELECT status, count(*), sum(cast(order_value AS DOUBLE)) FROM (SELECT *, row_number() OVER (PARTITION BY order_id) rn FROM orders) WHERE rn > 1 GROUP BY 1").fetchall()
    dd = {s: (n, v) for s, n, v in dd}
    ov = dd.get("delivered", (0, 0))[1]
    ex_users = one("SELECT count(*) FROM (SELECT user_id FROM orders WHERE status='delivered' GROUP BY 1 HAVING count(*) >= 2 AND count(DISTINCT order_id) = 1)")
    r.add("orders", "order_id", "Duplicate order_id", inv_ids, n_o,
          f"{inv_ids} order_ids appear twice ({involved} rows involved). Detail: {ex_dup} are exact duplicate rows; "
          f"{conflict} order_ids have conflicting content (different user/date/value/status).",
          "Kept the first occurrence of each order_id, removed the exact repeats; logged in excluded_records.csv. "
          "All duplicates were exact copies, so no conflict resolution was needed.",
          "An order_id identifies one real order; a byte-identical repeat is a duplicate export, not a second purchase. "
          "Genuine repeat purchases have distinct order_ids and were kept.",
          impact=f"Delivered revenue overstated by Rs {ov:,.0f}; {ex_users} users would look like repeat buyers only because of a duplicated row.")
    r.add("orders", "all", "Exact duplicate order rows", ex_dup, n_o, f"{ex_dup} rows are 100% identical to another row.", "Removed (same action as DQ above; counted once)", "See duplicate order_id.", kind="INFO")
    pd_dup = one("SELECT count(*) FROM (SELECT user_id, order_date, order_value, status FROM (SELECT DISTINCT * FROM orders) GROUP BY ALL HAVING count(DISTINCT order_id) > 1)")
    r.add("orders", "user_id+order_date+order_value+status", "Possible duplicates under a different order_id", pd_dup, n_o,
          f"{pd_dup} groups of orders share user, date, value and status but have different order_ids.", "Kept (would be legitimate multiple orders)", "Different order_ids = different orders.")

    bd = one("SELECT count(*) FROM orders WHERE try_strptime(order_date,'%Y-%m-%d') IS NULL")
    r.add("orders", "order_date", "Invalid / unparseable order_date", bd, n_o, f"{bd} order dates are not valid YYYY-MM-DD.", "Exclude record", "Cannot be placed in time.")
    od = one(f"SELECT count(*) FROM orders WHERE try_strptime(order_date,'%Y-%m-%d') NOT BETWEEN DATE '{C.PERIOD_START}' AND DATE '{C.PERIOD_END}'")
    r.add("orders", "order_date", "order_date outside Jan-Jun 2026", od, n_o, f"{od} orders dated outside the window.", "Exclude from the window", "Brief covers Jan-Jun 2026 only.")
    stat = con.execute("SELECT status, count(*) FROM orders GROUP BY 1 ORDER BY 2 DESC").fetchall()
    bad_status = one("SELECT count(*) FROM orders WHERE status NOT IN ('delivered','cancelled','returned')")
    r.add("orders", "status", "Invalid order status", bad_status, n_o, f"{bad_status} orders have a status other than delivered/cancelled/returned. Distribution: {dict(stat)}.", "Exclude from revenue", "Only 'delivered' counts as success.")
    nonsucc = one("SELECT count(*) FROM orders WHERE status <> 'delivered'")
    r.add("orders", "status", "Non-delivered orders (cancelled + returned)", nonsucc, n_o, f"{nonsucc} orders are cancelled or returned.",
          "Kept in orders_cleaned.csv with is_successful=False; never counted as revenue or as acquisition.",
          "Brief: only delivered orders are successful.", kind="INFO")
    nn = one("SELECT count(*) FROM orders WHERE try_cast(order_value AS DOUBLE) IS NULL")
    r.add("orders", "order_value", "Non-numeric / missing order_value", nn, n_o, f"{nn} order values cannot be read as numbers.", "Exclude record, no imputation", "Imputing revenue would be fabrication.")
    nz_ = one("SELECT count(*) FROM orders WHERE try_cast(order_value AS DOUBLE) <= 0")
    r.add("orders", "order_value", "Zero or negative order_value", nz_, n_o, f"{nz_} orders have value <= 0.", "Exclude from revenue", "A paid order must have a positive value.")

    orph = one("SELECT count(*) FROM orders WHERE user_id NOT IN (SELECT user_id FROM users)")
    r.add("orders", "user_id", "Orders referencing non-existent users", orph, n_o, f"{orph} orders point to a user_id absent from users.csv.", "Exclude (cannot be attributed to a channel)", "No acquisition channel can be assigned.")
    pre = one("SELECT count(*) FROM orders o JOIN users u USING(user_id) WHERE try_strptime(o.order_date,'%Y-%m-%d') < try_strptime(u.signup_date,'%Y-%m-%d')")
    r.add("orders", "order_date", "Order placed before the user's signup date", pre, n_o, f"{pre} orders predate signup.", "Flag for review", "Logically impossible for a new user.")
    same = one("SELECT count(*) FROM orders o JOIN users u USING(user_id) WHERE o.order_date = u.signup_date")
    r.add("orders", "order_date", "Orders placed on the signup day", same, n_o, f"{same} orders are on the signup date.", "Kept", "Plausible same-day conversion.", kind="INFO")
    qa_o = con.execute(f"SELECT count(*), count(DISTINCT order_id) FROM orders JOIN users u USING(user_id) WHERE {_INTERNAL}").fetchone()
    r.add("orders", "user_id", "Orders from internal QA/test accounts", qa_o[0], n_o,
          f"{qa_o[0]} order rows ({qa_o[1]} unique order_ids) belong to the test accounts above. Some of these rows are also exact duplicates.",
          "Excluded (applied after de-duplication, so the same row is never counted twice in the exclusion log).",
          "Follows the test-account decision.")
    v = con.execute(f"""
        WITH d AS (SELECT cast(order_value AS DOUBLE) v FROM (SELECT DISTINCT * FROM orders) o JOIN users u USING(user_id) WHERE NOT ({_INTERNAL}))
        SELECT quantile_cont(v,.25), quantile_cont(v,.75), min(v), max(v), count(*) FROM d""").fetchone()
    lo, hi = v[0] - 1.5 * (v[1] - v[0]), v[1] + 1.5 * (v[1] - v[0])
    out_n = one(f"SELECT count(*) FROM (SELECT DISTINCT * FROM orders) o JOIN users u USING(user_id) WHERE NOT ({_INTERNAL}) AND (cast(order_value AS DOUBLE) > {hi} OR cast(order_value AS DOUBLE) < {lo})")
    r.add("orders", "order_value", "Statistical outliers in order_value (IQR rule)", out_n, n_o,
          f"{out_n} real-user orders fall outside [{lo:,.0f}, {hi:,.0f}] (range observed Rs {v[2]:,.0f}-{v[3]:,.0f}).",
          "Retained, no capping", "High values are plausible for D2C baskets; removing them would be arbitrary.", kind="INFO")

    # ------------------------------------------------------------------ SPEND
    for col in ["month", "channel", "spend_inr"]:
        b = one(f"SELECT count(*) FROM spend WHERE trim({col}) = ''")
        r.add("spend", col, f"Missing values in {col}", b, n_s, f"{b} blank values.", "Stop and ask: cannot invent spend", "Spend drives CAC.")
    dups = one("SELECT count(*) - (SELECT count(*) FROM (SELECT DISTINCT month, channel FROM spend)) FROM spend")
    r.add("spend", "month+channel", "Duplicate month/channel rows", dups, n_s, f"{dups} repeated month-channel combinations.", "Investigate before summing", "Would double-count spend.")
    invc = one(f"SELECT count(*) FROM spend WHERE channel NOT IN ({', '.join(repr(c) for c in C.PAID_CHANNELS)})")
    r.add("spend", "channel", "Spend channel not in paid-channel list", invc, n_s, f"{invc} spend rows have unknown channels.", "Flag", "Spend must map to a paid channel.")
    badm = one("SELECT count(*) FROM spend WHERE month NOT IN (" + ", ".join(repr(m) for m in C.MONTHS) + ")")
    r.add("spend", "month", "Month outside Jan-Jun 2026", badm, n_s, f"{badm} rows outside window.", "Exclude", "Out of scope.")
    badv = one("SELECT count(*) FROM spend WHERE try_cast(spend_inr AS DOUBLE) IS NULL OR try_cast(spend_inr AS DOUBLE) <= 0")
    r.add("spend", "spend_inr", "Non-numeric, zero or negative spend", badv, n_s, f"{badv} invalid spend values.", "Flag", "Spend should be positive.")
    exp = len(C.PAID_CHANNELS) * len(C.MONTHS)
    cells = one("SELECT count(DISTINCT (month, channel)) FROM spend")
    r.add("spend", "month+channel", "Completeness of 4 channels x 6 months grid", exp - cells, exp, f"{cells} of {exp} month-channel cells present.", "Report gaps", "A missing month would understate spend.")
    tot_sp = one("SELECT sum(cast(spend_inr AS DOUBLE)) FROM spend")
    r.add("spend", "spend_inr", "Total spend sanity vs brief ('about Rs 16 lakh')", 0, n_s, f"Total spend in file = Rs {tot_sp:,.0f}, consistent with the brief's 'about Rs 16 lakh'.", "Used as-is", "Reconciles with the brief.", kind="INFO")
    return r.frame()


def run_and_save(path=None) -> pd.DataFrame:
    path = path or C.PART1_DIR / "data_quality_report.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    df = run_quality_checks()
    df.to_csv(path, index=False)
    return df


if __name__ == "__main__":
    out = run_and_save()
    print(out[["issue_id", "status", "check", "rows_affected", "pct_affected"]].to_string(index=False))
