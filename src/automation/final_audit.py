"""Final submission audit.  Run:  python -m src.automation.final_audit

Checks (each prints PASS / FAIL, exit code 1 if anything fails):
  1. raw files unchanged (SHA-256 vs data/raw_checksums.sha256, and vs the original download folder if present)
  2. every deliverable file from the agreed structure exists and is non-empty
  3. word / line limits: memo <= 250, design note <= 400, reflection 200-250, AI note 3-5 lines
  4. memo + budget arithmetic: cuts sum to exactly 20% of the Q2 baseline
  5. key numbers quoted in README.md match the result tables
  6. notebook was executed without errors
  7. no temporary files / caches / links in the project folder
  8. charts exist and were generated after the result tables they plot
"""
import hashlib
import re
import sys

import nbformat
import pandas as pd

from src import config as C
from src.visualizations.build_architecture import TITLE as DESIGN_TITLE, word_count as design_words
from src.visualizations.build_memo import word_count as memo_words

RESULTS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  - {detail}" if detail else ""))


def sha(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


REQUIRED = [
    "README.md", "requirements.txt", "Case_Study_Brief.pdf", ".gitignore",
    "data/raw/users.csv", "data/raw/orders.csv", "data/raw/marketing_spend.csv",
    "data/processed/users_cleaned.csv", "data/processed/orders_cleaned.csv",
    "data/processed/marketing_spend_cleaned.csv", "data/processed/excluded_records.csv", "data/data_dictionary.md",
    "notebooks/Part1_Exploratory_Analysis.ipynb", "notebooks/Part1_Exploratory_Analysis.html",
    "src/__init__.py", "src/config.py",
    "src/data_processing/__init__.py", "src/data_processing/load_data.py",
    "src/data_processing/data_quality.py", "src/data_processing/clean_data.py",
    "src/analytics/__init__.py", "src/analytics/acquisition_metrics.py", "src/analytics/customer_value.py",
    "src/analytics/ltv_cac.py", "src/analytics/monthly_trends.py", "src/analytics/budget_scenario.py",
    "src/visualizations/__init__.py", "src/visualizations/generate_charts.py",
    "src/automation/__init__.py", "src/automation/pipeline.py", "src/automation/validation.py",
    "outputs/part1_analysis/data_quality_report.csv", "outputs/part1_analysis/acquisition_metrics.csv",
    "outputs/part1_analysis/customer_value_metrics.csv", "outputs/part1_analysis/ltv_cac_metrics.csv",
    "outputs/part1_analysis/monthly_cac_trends.csv", "outputs/part1_analysis/sanity_check.md",
    "outputs/part2_recommendation/CMO_Recommendation.md", "outputs/part2_recommendation/CMO_Recommendation.pdf",
    "outputs/part2_recommendation/charts/chart1_cac_by_channel.png",
    "outputs/part2_recommendation/charts/chart2_ltv_vs_cac_by_channel.png",
    "outputs/part2_recommendation/charts/chart3_monthly_cac_trend.png",
    "outputs/part3_automation/Architecture_Design.md", "outputs/part3_automation/Architecture_Design.pdf",
    "outputs/part3_automation/architecture_diagram.png",
    "outputs/final_submission/AI_Usage_Note.md", "outputs/final_submission/Reflection.md",
    "docs/project_approach.md", "docs/assumptions.md", "docs/technical_documentation.md",
]


def run() -> int:
    # 1. raw data preserved
    pairs = [l.split(" *") for l in (C.ROOT / "data" / "raw_checksums.sha256").read_text().splitlines() if l.strip()]
    bad = [name.strip() for h, name in pairs if sha(C.RAW_DIR / name.strip()) != h]
    check("Raw CSVs match recorded SHA-256 checksums", not bad, f"changed: {bad}" if bad else "3 files identical")
    orig = C.ROOT.parent / "Data_AI_Engineer_Case_Study" / "data"
    if orig.exists():
        diff = [p.name for p in C.RAW_DIR.glob("*.csv") if sha(p) != sha(orig / p.name)]
        check("Raw CSVs identical to the original download folder", not diff, f"differs: {diff}" if diff else "identical")

    # 2. deliverables exist
    # package markers (__init__.py) are intentionally empty; every other deliverable must have content
    missing = [r for r in REQUIRED if not (C.ROOT / r).exists()
               or ((C.ROOT / r).stat().st_size == 0 and not r.endswith("__init__.py"))]
    check(f"All {len(REQUIRED)} required deliverables exist (non-empty, except __init__.py markers)", not missing,
          f"missing: {missing}" if missing else "")

    # 3. limits
    memo = (C.PART2_DIR / "CMO_Recommendation.md").read_text(encoding="utf-8")
    design = (C.PART3_DIR / "Architecture_Design.md").read_text(encoding="utf-8")
    refl = (C.FINAL_DIR / "Reflection.md").read_text(encoding="utf-8")
    ai = (C.FINAL_DIR / "AI_Usage_Note.md").read_text(encoding="utf-8")
    n = memo_words(memo); check("CMO memo <= 250 words", n <= 250, f"{n} words")
    n = design_words(design); check("Design note <= 400 words (incl. title, list numbers)", n <= 400, f"{n} words")
    n = len(refl.split()); check("Reflection 200-250 words", 200 <= n <= 250, f"{n} words")
    n = len([l for l in ai.splitlines() if l.strip()]); check("AI-use note is 3-5 lines", 3 <= n <= 5, f"{n} lines")

    # 4. budget arithmetic (independent of the memo text)
    b = pd.read_csv(C.PART2_DIR / "budget_reallocation.csv").set_index("channel")
    paid = b.loc[C.PAID_CHANNELS]
    base, cut = int(paid["q2_baseline_spend"].sum()), int(paid["cut_inr"].sum())
    check("Cuts equal exactly 20% of the Q2 paid-spend baseline", cut * 100 == base * 20, f"{cut:,} vs 20% x {base:,}")
    check("New budget = baseline - cut", int(paid["new_budget"].sum()) == base - cut)
    raw_q2 = pd.read_csv(C.RAW_FILES["spend"]).query("month >= '2026-04'")["spend_inr"].sum()
    check("Baseline equals Q2 spend summed directly from the RAW spend file", base == raw_q2, f"{base:,}")

    # 5. README numbers vs tables
    readme = (C.ROOT / "README.md").read_text(encoding="utf-8").replace(",", "").replace("₹", "")
    acq = pd.read_csv(C.PART1_DIR / "acquisition_metrics.csv").set_index("channel")
    ltv = pd.read_csv(C.PART1_DIR / "ltv_cac_metrics.csv").set_index("channel")
    cv = pd.read_csv(C.PART1_DIR / "customer_value_metrics.csv").set_index("channel")
    chg = pd.read_csv(C.PART1_DIR / "monthly_cac_change_summary.csv").set_index("channel")
    want = []
    for ch in C.PAID_CHANNELS:
        want += [f"{int(acq.loc[ch, 'total_spend'])}", f"{int(acq.loc[ch, 'new_customers'])}", f"{int(acq.loc[ch, 'cac'])}",
                 f"{int(cv.loc[ch, 'revenue_per_customer'])}", f"{cv.loc[ch, 'repeat_purchase_rate_pct']:.1f}",
                 f"{ltv.loc[ch, 'ltv_cac_ratio']:.2f}"]
    want += [f"{chg.loc['Meta Ads', 'pct_change']:.1f}", f"{int(chg.loc['Meta Ads', 'jan_cac'])}", f"{int(chg.loc['Meta Ads', 'jun_cac'])}"]
    miss = [w for w in want if w not in readme]
    check("README key numbers all found in the result tables", not miss, f"not in README: {miss}" if miss else f"{len(want)} numbers matched")

    # 6. notebook executed cleanly
    nb = nbformat.read(C.ROOT / "notebooks" / "Part1_Exploratory_Analysis.ipynb", 4)
    code = [c for c in nb.cells if c.cell_type == "code"]
    errs = [o for c in code for o in c.outputs if o.output_type == "error"]
    check("Notebook: every code cell executed, no errors", all(c.execution_count for c in code) and not errs, f"{len(code)} cells")

    # 7. cleanliness
    junk = [p for p in C.ROOT.rglob("*") if p.name in {"__pycache__", ".ipynb_checkpoints", ".DS_Store", "Thumbs.db"}
            or p.suffix in {".tmp", ".bak", ".pyc"} or p.name.startswith("~$")]
    check("No caches / temp files in the project", not junk, f"{[str(j.relative_to(C.ROOT)) for j in junk[:5]]}" if junk else "")
    links = [p for p in C.ROOT.rglob("*") if p.is_symlink()]
    check("No symbolic links leaving the project", not links)

    # 8. charts newer than the tables they plot
    newest_table = max(p.stat().st_mtime for p in C.PART1_DIR.glob("*.csv"))
    stale = [p.name for p in C.CHARTS_DIR.glob("*.png") if p.stat().st_mtime < newest_table - 1]
    check("Charts were generated after the latest result tables", not stale, f"stale: {stale}" if stale else "")

    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run())
