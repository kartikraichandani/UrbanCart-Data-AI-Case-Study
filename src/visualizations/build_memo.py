"""Build the CMO memo (Markdown + PDF) from the computed results - no hand-typed numbers.

Reads the saved Part 1 tables and re-runs the budget scenario, fills the memo template,
asserts the 250-word limit, and renders a PDF (memo page + the three charts).
"""
import re

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer
import matplotlib

from src import config as C
from src.analytics.budget_scenario import build_scenario, budget_calculation_markdown, scenario_output_table
from src.analytics.customer_value import build_customer_table
from src.analytics.ltv_cac import compute_ltv_cac
from src.analytics.monthly_trends import compute_monthly_cac
from src.data_processing.load_data import load_cleaned

MAX_WORDS = 250


def inr(x) -> str:
    """Indian digit grouping: 173600 -> ₹1,73,600."""
    s = f"{int(round(x)):d}"
    head, tail = s[:-3], s[-3:]
    if head:
        head = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", head)
        return f"₹{head},{tail}"
    return f"₹{tail}"


def memo_markdown(res: dict) -> str:
    t, s = res["table"].set_index("channel"), res["summary"]
    ltv = pd.read_csv(C.PART1_DIR / "ltv_cac_metrics.csv").set_index("channel")
    cv = pd.read_csv(C.PART1_DIR / "customer_value_metrics.csv").set_index("channel")
    chg = pd.read_csv(C.PART1_DIR / "monthly_cac_change_summary.csv").set_index("channel")
    acq = pd.read_csv(C.PART1_DIR / "acquisition_metrics.csv").set_index("channel")
    sec = s["second_channel"]
    lo_pct = 100 * s["est_customers_lost_meta_marginal"] / s["q2_new_customers_total"]
    hi_pct = 100 * s["est_customers_lost_pessimistic"] / s["q2_new_customers_total"]
    return f"""**To:** CMO  |  **From:** Growth Analytics  |  **Re:** Cutting paid spend by 20%

**Decision.** Cut {inr(s['target'])} (20%) from the {inr(s['baseline_total'])} Q2 paid-spend baseline: Meta Ads −{inr(t.loc['Meta Ads','cut_inr'])} (−{t.loc['Meta Ads','cut_pct_of_channel']:.1f}%) and {sec} −{inr(t.loc[sec,'cut_inr'])} (−{t.loc[sec,'cut_pct_of_channel']:.1f}%). Hold Google Ads and Influencer flat. Check: {inr(t.loc['Meta Ads','cut_inr'])} + {inr(t.loc[sec,'cut_inr'])} = {inr(s['target'])} = 20% × {inr(s['baseline_total'])}.

**Why.**
- **Meta Ads:** Q2 spend rose {s['meta_delta_spend_pct']:.1f}% over Q1 ({inr(t.loc['Meta Ads','q1_spend'])} to {inr(t.loc['Meta Ads','q2_baseline_spend'])}) for only {s['meta_delta_customers']} extra customers (+{s['meta_delta_customers_pct']:.1f}%). CAC climbed from {inr(chg.loc['Meta Ads','jan_cac'])} (Jan) to {inr(chg.loc['Meta Ads','jun_cac'])} (Jun); LTV:CAC is {ltv.loc['Meta Ads','ltv_cac_ratio']:.2f}. We cut back to Q1 spend.
- **{sec}:** worst return (LTV:CAC {ltv.loc[sec,'ltv_cac_ratio']:.2f}), only {cv.loc[sec,'repeat_purchase_rate_pct']:.1f}% repeat buyers, {inr(cv.loc[sec,'revenue_per_customer'])} revenue per customer.
- **Influencer:** highest CAC ({inr(acq.loc['Influencer','cac'])}) but best revenue per customer ({inr(cv.loc['Influencer','revenue_per_customer'])}) and {cv.loc['Influencer','repeat_purchase_rate_pct']:.1f}% repeat. Not cut: CAC alone misleads.

**Protect: Google Ads.** The only channel whose LTV exceeds CAC ({ltv.loc['Google Ads','ltv_cac_ratio']:.2f}), with stable CAC ({chg.loc['Google Ads','pct_change']:+.1f}%) and {cv.loc['Google Ads','repeat_purchase_rate_pct']:.1f}% repeat.

**Expected impact.** Roughly {s['est_customers_lost_meta_marginal']:.0f}–{s['est_customers_lost_pessimistic']:.0f} fewer paid customers a quarter ({lo_pct:.1f}–{hi_pct:.1f}%), yet each lost customer earned less than it cost; net margin gain {inr(s['est_net_gain'])} even in the pessimistic case.

**Biggest risk.** Meta's CAC rise coincides with higher spend: association, not proof of saturation. LTV covers six months only and samples are modest, so volume could fall further.

**Monitor weekly:** Meta CAC and new customers, Organic signups (halo effect), {sec} repeat rate, total new customers. If total paid customers fall over {hi_pct:.1f}% below Q2 pace, revisit the Meta cut.
"""


def word_count(md: str) -> int:
    text = re.sub(r"[*|]", " ", md)              # drop markdown markers
    text = re.sub(r"^\s*-\s+", " ", text, flags=re.M)
    return len(text.split())


def _register_fonts():
    base = matplotlib.get_data_path() + "/fonts/ttf/"
    pdfmetrics.registerFont(TTFont("DV", base + "DejaVuSans.ttf"))
    pdfmetrics.registerFont(TTFont("DV-B", base + "DejaVuSans-Bold.ttf"))
    pdfmetrics.registerFontFamily("DV", normal="DV", bold="DV-B", italic="DV", boldItalic="DV-B")


def _html(line: str) -> str:
    line = line.replace("&", "&amp;").replace("<", "&lt;")
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line)


def build_pdf(md: str, charts: list, path) -> None:
    _register_fonts()
    body = ParagraphStyle("b", fontName="DV", fontSize=9.6, leading=14, spaceAfter=7, textColor=colors.HexColor("#0b0b0b"))
    bullet = ParagraphStyle("bl", parent=body, leftIndent=14, bulletIndent=3, spaceAfter=4)
    title = ParagraphStyle("t", parent=body, fontName="DV-B", fontSize=15, leading=19, spaceAfter=4)
    sub = ParagraphStyle("s", parent=body, fontSize=8.5, textColor=colors.HexColor("#52514e"), spaceAfter=12)
    story = [Paragraph("UrbanCart – Recommendation to the CMO", title),
             Paragraph("Paid-marketing budget: cutting 20% next quarter", sub)]
    for line in md.strip().splitlines():
        if not line.strip():
            continue
        if line.startswith("- "):
            story.append(Paragraph(_html(line[2:]), bullet, bulletText="•"))
        else:
            story.append(Paragraph(_html(line), body))
    story.append(Paragraph(f"<i>Calculation detail: Budget_Calculation.md. Charts on the following pages.</i>", sub))
    story.append(PageBreak())
    w = A4[0] - 4 * cm
    for i, c in enumerate(charts):
        story.append(Image(str(c), width=w, height=w * 4.4 / 7.5))
        story.append(Spacer(1, 10))
        if i == 1:
            story.append(PageBreak())
    SimpleDocTemplate(str(path), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm,
                      bottomMargin=1.5 * cm, title="UrbanCart CMO Recommendation", author="Growth Analytics").build(story)


def build_all():
    cl = load_cleaned()
    cu = build_customer_table(cl)
    res = build_scenario(compute_monthly_cac(cl, cu), compute_ltv_cac(cl, cu))
    C.PART2_DIR.mkdir(parents=True, exist_ok=True)
    scenario_output_table(res["table"]).to_csv(C.PART2_DIR / "budget_reallocation.csv", index=False)
    (C.PART2_DIR / "Budget_Calculation.md").write_text(budget_calculation_markdown(res), encoding="utf-8")
    from src.automation.validation import validate_budget_math
    for line in validate_budget_math(res["table"]):
        print("  [budget check OK]", line)
    md = memo_markdown(res)
    n = word_count(md)
    assert n <= MAX_WORDS, f"memo is {n} words (limit {MAX_WORDS})"
    (C.PART2_DIR / "CMO_Recommendation.md").write_text(md, encoding="utf-8")
    charts = sorted(C.CHARTS_DIR.glob("chart*.png"))
    build_pdf(md, charts, C.PART2_DIR / "CMO_Recommendation.pdf")
    return n


if __name__ == "__main__":
    print("memo words:", build_all())
