"""Validation: (1) independent recalculation from the RAW csv files, (2) output invariants.

The independent route deliberately avoids pandas and DuckDB: it reads the raw files with
Python's `csv` module and aggregates with plain dicts/sets. It shares only the two cleaning
*decisions* (drop exact duplicate orders, drop @urbancart.in test accounts) - re-implemented
here from scratch - and the brief's business definitions. It does NOT share any aggregation
code with the main pipeline, so a bug in the SQL/pandas logic would show up as a mismatch.
"""
import csv
from collections import defaultdict

import pandas as pd

from src import config as C


def independent_recalculation() -> dict:
    # ---- raw spend, summed directly from marketing_spend.csv ----
    spend, spend_m = defaultdict(float), {}
    with open(C.RAW_FILES["spend"], newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            spend[r["channel"]] += float(r["spend_inr"])
            spend_m[(r["channel"], r["month"])] = float(r["spend_inr"])

    # ---- users: channel + signup month; test accounts identified by own email domain ----
    chan, smonth, test = {}, {}, set()
    with open(C.RAW_FILES["users"], newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            uid = r["user_id"]
            chan[uid] = r["acquisition_channel"].strip() or C.UNKNOWN_CHANNEL
            smonth[uid] = r["signup_date"][:7]
            if r["email"].lower().endswith("@" + C.INTERNAL_EMAIL_DOMAIN):
                test.add(uid)

    # ---- orders: drop exact duplicate rows, keep delivered only ----
    seen, per_user = set(), defaultdict(lambda: [0, 0.0])      # user -> [n delivered orders, revenue]
    per_user_with_test = defaultdict(lambda: [0, 0.0])
    with open(C.RAW_FILES["orders"], newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            key = (r["order_id"], r["user_id"], r["order_date"], r["order_value"], r["status"])
            if key in seen:
                continue
            seen.add(key)
            if r["status"] != C.SUCCESS_STATUS:
                continue
            per_user_with_test[r["user_id"]][0] += 1
            per_user_with_test[r["user_id"]][1] += float(r["order_value"])
            if r["user_id"] in test:
                continue
            per_user[r["user_id"]][0] += 1
            per_user[r["user_id"]][1] += float(r["order_value"])

    out = {"channels": {}, "monthly": {}, "sensitivity_with_test_accounts": {}}
    for ch in C.VALID_CHANNELS + [C.UNKNOWN_CHANNEL]:
        us = [u for u in per_user if chan[u] == ch]
        n, rev = len(us), sum(per_user[u][1] for u in us)
        rep = sum(1 for u in us if per_user[u][0] >= 2)
        d = {"customers": n, "revenue": rev, "repeat_customers": rep,
             "rpc": rev / n, "repeat_rate": 100 * rep / n}
        if ch in C.PAID_CHANNELS:
            d["spend"] = spend[ch]
            d["cac"] = spend[ch] / n
            d["ltv"] = d["rpc"] * C.CONTRIBUTION_MARGIN
            d["ltv_cac"] = d["ltv"] / d["cac"]
        out["channels"][ch] = d
    for ch in C.PAID_CHANNELS:
        for m in C.MONTHS:
            n = sum(1 for u in per_user if chan[u] == ch and smonth[u] == m)
            out["monthly"][(ch, m)] = spend_m[(ch, m)] / n if n else None
    aff = [u for u in per_user_with_test if chan[u] == "Affiliate"]
    out["sensitivity_with_test_accounts"] = {"affiliate_customers": len(aff),
                                             "affiliate_cac": spend["Affiliate"] / len(aff)}
    return out


def compare_with_pipeline(cust_value, acq, ltv, monthly) -> pd.DataFrame:
    """Compare full-precision pipeline outputs with the independent recalculation."""
    ind = independent_recalculation()
    rows = []

    def add(metric, pipe, indep):
        match = (pipe is None and indep is None) or (
            pipe is not None and indep is not None and abs(pipe - indep) < 1e-6)
        rows.append({"metric": metric, "pipeline": pipe, "independent": indep, "match": bool(match)})

    cv = cust_value.set_index("channel")
    a, l = acq.set_index("channel"), ltv.set_index("channel")
    for ch, d in ind["channels"].items():
        add(f"{ch} | customers", float(cv.loc[ch, "customers"]), float(d["customers"]))
        add(f"{ch} | revenue", float(cv.loc[ch, "total_revenue"]), d["revenue"])
        add(f"{ch} | revenue per customer", float(cv.loc[ch, "revenue_per_customer"]), d["rpc"])
        add(f"{ch} | repeat rate %", float(cv.loc[ch, "repeat_purchase_rate_pct"]), d["repeat_rate"])
        if ch in C.PAID_CHANNELS:
            add(f"{ch} | spend", float(a.loc[ch, "total_spend"]), d["spend"])
            add(f"{ch} | CAC", float(a.loc[ch, "cac"]), d["cac"])
            add(f"{ch} | LTV:CAC", float(l.loc[ch, "ltv_cac_ratio"]), d["ltv_cac"])
    mm = monthly.set_index(["channel", "month"])["cac"]
    for (ch, m), v in ind["monthly"].items():
        p = mm.loc[(ch, m)]
        add(f"{ch} | CAC {m}", None if pd.isna(p) else float(p), v)
    return pd.DataFrame(rows)


def validate_invariants(cleaned, customers, acq, cust_value, ltv, monthly) -> list[str]:
    """Internal consistency checks; raises AssertionError on failure, returns list of passed checks."""
    ok = []

    def check(cond, msg):
        assert cond, f"VALIDATION FAILED: {msg}"
        ok.append(msg)

    raw_total = pd.read_csv(C.RAW_FILES["spend"])["spend_inr"].sum()
    check(acq["total_spend"].sum() == raw_total, f"channel spend sums to raw file total (Rs {raw_total:,.0f})")
    check(monthly["spend"].sum() == raw_total, "monthly spend sums to raw file total")
    check(cust_value["customers"].sum() == len(customers), "customers across channels = customer table rows")
    check(abs(cust_value["total_revenue"].sum() - customers["delivered_revenue"].sum()) < 1e-6, "channel revenue sums to delivered revenue")
    delivered = cleaned["orders"].query("is_successful")
    check(abs(delivered["order_value"].sum() - customers["delivered_revenue"].sum()) < 1e-6, "customer revenue = delivered order revenue (no cancelled/returned leakage)")
    check(set(customers["channel"]) <= set(C.VALID_CHANNELS + [C.UNKNOWN_CHANNEL]), "only valid channels (or Unknown) present")
    check(((customers["delivered_orders"] >= 1)).all(), "every customer has >= 1 delivered order")
    paid = ltv[ltv.channel.isin(C.PAID_CHANNELS)]
    check(((paid["ltv"] - paid["revenue_per_customer"] * C.CONTRIBUTION_MARGIN).abs() < 1e-9).all(), "LTV = revenue per customer x 30%")
    check(((paid["ltv_cac_ratio"] - paid["ltv"] / paid["cac"]).abs() < 1e-9).all(), "LTV:CAC = LTV / CAC")
    check(ltv.loc[ltv.channel == C.ORGANIC_CHANNEL, "cac"].isna().all(), "Organic has no invented CAC / LTV:CAC")
    check(monthly["new_customers"].groupby(monthly["channel"]).sum().reindex(C.PAID_CHANNELS).tolist()
          == acq.set_index("channel").loc[C.PAID_CHANNELS, "new_customers"].tolist(), "monthly new customers sum to period totals")
    check(len(monthly) == len(C.PAID_CHANNELS) * len(C.MONTHS), "monthly table has 4 channels x 6 months")
    return ok


def write_sanity_check(comparison: pd.DataFrame, acq, ind=None, path=None) -> None:
    path = path or C.PART1_DIR / "sanity_check.md"
    ind = ind or independent_recalculation()
    n_ok, n = int(comparison["match"].sum()), len(comparison)
    meta = ind["channels"]["Meta Ads"]
    # Show the Meta spend arithmetic straight from the raw spend file.
    spend_rows = pd.read_csv(C.RAW_FILES["spend"]).query("channel == 'Meta Ads'")
    spend_terms = " + ".join(f"{int(v):,}" for v in spend_rows["spend_inr"])
    sens = ind["sensitivity_with_test_accounts"]
    aff = ind["channels"]["Affiliate"]
    lines = [
        "# Sanity Check (Part 1, question 6)", "",
        "## Number selected: Meta Ads CAC", "",
        f"- **Spend (read directly from raw `marketing_spend.csv`)**: {spend_terms} = **Rs {meta['spend']:,.0f}**",
        f"- **New customers (independent method)**: **{meta['customers']}** users tagged Meta Ads with >= 1 delivered order",
        f"- **CAC** = {meta['spend']:,.0f} / {meta['customers']} = **Rs {meta['cac']:,.0f}**",
        f"- **Main pipeline result**: Rs {acq.set_index('channel').loc['Meta Ads', 'cac']:,.0f}  ->  **{'agrees' if abs(acq.set_index('channel').loc['Meta Ads', 'cac'] - meta['cac']) < 1e-6 else 'DOES NOT AGREE'}**", "",
        "## How the second method differs from the first", "",
        "| | Main pipeline | Independent check |",
        "|---|---|---|",
        "| Tools | pandas + DuckDB SQL | Python standard-library `csv`, plain dicts and sets |",
        "| Input | Cleaned CSVs in `data/processed/` | **Raw** CSVs in `data/raw/` |",
        "| Dedup + test-account removal | `clean_data.py` | Re-implemented separately (set of full rows; email domain) |",
        "| Aggregation | SQL JOIN / GROUP BY | Loops over rows, per-user counters |",
        "| Spend | Sum of cleaned spend table | Sum of the raw spend column |", "",
        "**What this proves:** the arithmetic, joins and grouping in the pipeline are correct, and the cleaning code really produces what the report says.",
        "**What it does NOT prove:** that the *decisions* are right. Both routes share the same business definitions (from the brief) and the same two cleaning decisions "
        "(drop exact duplicate orders; exclude the 35 `@urbancart.in` test accounts). Those are documented in `docs/assumptions.md`.", "",
        f"## Full comparison: {n_ok} of {n} metrics match", "",
        "Every channel's customers, revenue, revenue per customer, repeat rate, spend, CAC, LTV:CAC and all 24 monthly CAC values were recomputed independently "
        "(tolerance 1e-6, before rounding).", "",
        f"**Result: {'ALL MATCH' if n_ok == n else str(n - n_ok) + ' MISMATCH(ES) - see table'}.**", "",
    ]
    bad = comparison[~comparison["match"]]
    if len(bad):
        lines += ["### Mismatches", "", "```", bad.to_string(index=False), "```", ""]
    lines += [
        "## Sensitivity to the test-account decision (for transparency)", "",
        f"If the 35 QA accounts were *kept*, Affiliate would show {sens['affiliate_customers']} customers and a CAC of Rs {sens['affiliate_cac']:,.0f} "
        f"instead of {aff['customers']} customers and Rs {aff['cac']:,.0f}. Excluding them is the more defensible choice because they are not real customers.", "",
        "## Why the two results agree", "",
        "Both start from the same raw rows, apply the same definition (delivered order, de-duplicated, real users) and divide the same spend by the same count of "
        "customers. Different code reaching the same number means that the counts are not artefacts of a join or grouping error.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def validate_budget_math(scenario_table: pd.DataFrame) -> list[str]:
    """Re-derive the 20% budget cut straight from the RAW spend csv (stdlib only) and compare."""
    q1, q2 = defaultdict(int), defaultdict(int)
    with open(C.RAW_FILES["spend"], newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            (q1 if r["month"] <= "2026-03" else q2)[r["channel"]] += int(r["spend_inr"])
    base, target = sum(q2.values()), sum(q2.values()) * 20 // 100
    assert sum(q2.values()) * 20 % 100 == 0
    t = scenario_table.set_index("channel")
    expect = {"Meta Ads": q2["Meta Ads"] - q1["Meta Ads"], "Google Ads": 0, "Influencer": 0}
    expect["Affiliate"] = target - expect["Meta Ads"]
    ok = []
    for ch, v in expect.items():
        assert int(t.loc[ch, "cut_inr"]) == v, f"{ch}: cut {t.loc[ch, 'cut_inr']} != independent {v}"
    ok.append(f"per-channel cuts match independent derivation from raw spend: {expect}")
    assert sum(expect.values()) == target == int(t["cut_inr"].sum())
    ok.append(f"cuts sum to exactly 20% of baseline: {sum(expect.values()):,} = 20% x {base:,}")
    assert int(t["new_budget"].sum()) == base - target
    ok.append(f"new budget {base - target:,} = baseline - target")
    assert all(0 <= expect[c] <= q2[c] for c in expect), "a cut exceeds its channel's baseline"
    ok.append("no channel is cut by more than its baseline")
    return ok
