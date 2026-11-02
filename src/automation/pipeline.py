"""End-to-end pipeline entry point.

    python -m src.automation.pipeline

Steps: data-quality report -> cleaning -> Part 1 metrics -> validation (invariants +
independent recalculation) -> save all tables to outputs/part1_analysis/.
Then Part 2: charts, budget scenario and the CMO memo (md + pdf).
"""
from src import config as C
from src.analytics.acquisition_metrics import acquisition_table, compute_acquisition
from src.analytics.customer_value import build_customer_table, compute_customer_value, customer_value_table
from src.analytics.ltv_cac import compute_ltv_cac, ltv_cac_table
from src.analytics.monthly_trends import compute_monthly_cac, monthly_table
from src.automation.validation import compare_with_pipeline, validate_invariants, write_sanity_check
from src.data_processing.clean_data import clean_all, save_cleaned
from src.data_processing.data_quality import run_and_save


def run_data_preparation():
    quality = run_and_save()                       # outputs/part1_analysis/data_quality_report.csv
    cleaned, exclusions, reconciliation = clean_all()
    save_cleaned(cleaned, exclusions, reconciliation)
    return quality, cleaned, exclusions, reconciliation


def run_analysis(cleaned):
    """Compute and save all Part 1 tables; returns the output tables."""
    customers = build_customer_table(cleaned)

    # Output (rounded) tables
    acq_t = acquisition_table(cleaned, customers)
    cv_t = customer_value_table(customers)
    ltv_t = ltv_cac_table(cleaned, customers)
    monthly_t, change_t = monthly_table(cleaned, customers)

    # Validation uses FULL-PRECISION values, not the rounded output tables.
    acq, cv = compute_acquisition(cleaned, customers), compute_customer_value(customers)
    ltv, monthly = compute_ltv_cac(cleaned, customers), compute_monthly_cac(cleaned, customers)
    passed = validate_invariants(cleaned, customers, acq, cv, ltv, monthly)
    comparison = compare_with_pipeline(cv, acq, ltv, monthly)
    assert comparison["match"].all(), "independent recalculation disagrees with pipeline"
    write_sanity_check(comparison, acq)

    C.PART1_DIR.mkdir(parents=True, exist_ok=True)
    acq_t.to_csv(C.PART1_DIR / "acquisition_metrics.csv", index=False)
    cv_t.to_csv(C.PART1_DIR / "customer_value_metrics.csv", index=False)
    ltv_t.to_csv(C.PART1_DIR / "ltv_cac_metrics.csv", index=False)
    monthly_t.to_csv(C.PART1_DIR / "monthly_cac_trends.csv", index=False)
    change_t.to_csv(C.PART1_DIR / "monthly_cac_change_summary.csv", index=False)
    return {"customers": customers, "acquisition": acq_t, "customer_value": cv_t, "ltv": ltv_t,
            "monthly": monthly_t, "change": change_t, "invariants_passed": passed, "comparison": comparison}


def run_recommendation():
    """Part 2: charts -> budget scenario (+ independent maths check) -> memo md/pdf. Needs Part 1 tables."""
    from src.visualizations.build_memo import build_all
    from src.visualizations.generate_charts import generate_all
    generate_all()
    return build_all()


def run():
    quality, cleaned, exclusions, reconciliation = run_data_preparation()
    res = run_analysis(cleaned)
    print("Memo words:", run_recommendation())
    from src.visualizations.build_architecture import build_all as build_design_note
    print("Design note words:", build_design_note())
    print("Quality checks:", len(quality), "| issues:", int((quality.status == "ISSUE").sum()))
    print(reconciliation.to_string(index=False))
    print(f"Invariant checks passed: {len(res['invariants_passed'])}")
    print(f"Independent recalculation: {int(res['comparison']['match'].sum())}/{len(res['comparison'])} metrics match")
    print(res["acquisition"].to_string(index=False))


if __name__ == "__main__":
    run()
