"""Central configuration: paths and business constants.

Everything that the brief fixes (channels, margin, analysis window) lives here so no
module hard-codes it.
"""
from pathlib import Path

# Project root = the folder that contains `src/` (works no matter where Python is launched from).
ROOT = Path(__file__).resolve().parents[1]

RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
PART1_DIR = ROOT / "outputs" / "part1_analysis"
PART2_DIR = ROOT / "outputs" / "part2_recommendation"
CHARTS_DIR = PART2_DIR / "charts"
PART3_DIR = ROOT / "outputs" / "part3_automation"
FINAL_DIR = ROOT / "outputs" / "final_submission"

RAW_FILES = {
    "users": RAW_DIR / "users.csv",
    "orders": RAW_DIR / "orders.csv",
    "spend": RAW_DIR / "marketing_spend.csv",
}

# ---- Business definitions fixed by Case_Study_Brief.pdf (do not change) ----
PAID_CHANNELS = ["Google Ads", "Meta Ads", "Affiliate", "Influencer"]
ORGANIC_CHANNEL = "Organic"
VALID_CHANNELS = PAID_CHANNELS + [ORGANIC_CHANNEL]
UNKNOWN_CHANNEL = "Unknown"          # blank channel is NOT silently mapped to Organic
SUCCESS_STATUS = "delivered"
VALID_STATUSES = ["delivered", "cancelled", "returned"]
CONTRIBUTION_MARGIN = 0.30          # brief: 30% for every channel

# Analysis window (Jan-Jun 2026)
PERIOD_START = "2026-01-01"
PERIOD_END = "2026-06-30"
MONTHS = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]

# Internal QA/test accounts use the company's own email domain.
INTERNAL_EMAIL_DOMAIN = "urbancart.in"
