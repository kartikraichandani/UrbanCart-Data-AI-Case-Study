"""Part 3 deliverables: architecture diagram (PNG) and the design note PDF.

The note text itself lives in outputs/part3_automation/Architecture_Design.md (hand-written);
this script draws the diagram, enforces the 400-word limit and renders the PDF.
"""
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer

from src import config as C

TITLE = "Architecture Design: Weekly Analytics, Automated and Self-Serve"
MAX_WORDS = 400
INK, INK2, EDGE, SURFACE = "#0b0b0b", "#52514e", "#8d8c86", "#fcfcfb"
SRC, ING, BQ, CONS, OPS = "#eceae4", "#dbe8f8", "#e3eefb", "#e0f3ea", "#f3efe6"
LAYER = ["#c9dcf5", "#b3cdf0", "#9bbfea", "#7fb0e4"]      # one hue, light -> dark (raw -> analytics)


def _box(ax, x, y, w, h, text, fc, fs=8, bold=False, ec=EDGE, lw=1.0, ls="-", align="center"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.0,rounding_size=0.8", fc=fc, ec=ec, lw=lw, ls=ls))
    if text:
        ax.text(x + (w / 2 if align == "center" else 1.0), y + h / 2, text, ha=align, va="center", fontsize=fs,
                color=INK, fontweight="bold" if bold else "normal", linespacing=1.35)


def _arrow(ax, p1, p2, color=INK2, lw=1.2, style="-|>"):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle=style, mutation_scale=9, color=color, lw=lw, shrinkA=0, shrinkB=0))


def draw_diagram(path):
    fig, ax = plt.subplots(figsize=(13, 7.6))
    fig.patch.set_facecolor(SURFACE)
    ax.set_xlim(0, 100); ax.set_ylim(0, 64); ax.axis("off")
    ax.text(1, 62.3, "UrbanCart analytics platform on GCP", fontsize=14, fontweight="bold", color=INK, va="center")
    ax.text(1, 59.6, "Daily batch pipeline  →  BigQuery layers  →  dashboard + controlled conversational assistant",
            fontsize=9, color=INK2, va="center")

    # column headers
    for x, t in [(8, "1  SOURCES"), (30.5, "2  INGEST"), (56, "3  WAREHOUSE (BigQuery)"), (86, "4  SELF-SERVE (CMO)")]:
        ax.text(x, 56.8, t, fontsize=8.5, color=INK2, ha="center", fontweight="bold")

    # --- sources
    src = [("GA4", "website activity", 47), ("Google Ads", "marketing spend", 38.5),
           ("Salesforce", "customers & orders", 30), ("MoEngage", "campaign engagement", 21.5),
           ("Meta Ads", "marketing spend", 13)]
    for name, sub, y in src:
        _box(ax, 1, y, 14, 7, f"{name}\n{sub}", SRC, fs=8)

    # --- ingest
    _box(ax, 20, 38.5, 21, 15.5, "Native exports\nBigQuery export (GA4)\nData Transfer Service\n(Google Ads)", ING, fs=7.6)
    _box(ax, 20, 25, 21, 11.5, "Cloud Run Jobs (Python)\nSalesforce · MoEngage\nMeta Ads · incremental API pulls", ING, fs=7.6)
    _box(ax, 20, 13, 21, 9.5, "Cloud Storage\nraw files, unchanged,\ndate-partitioned", ING, fs=7.6)
    _arrow(ax, (15, 50.5), (20, 49.5)); _arrow(ax, (15, 42), (20, 43.5))
    for y in (33.5, 25, 16.5):
        _arrow(ax, (15, y), (20, 31 if y > 20 else 27.5))
    _arrow(ax, (30.5, 25), (30.5, 22.5))

    # --- BigQuery container + layers (data flows top -> bottom)
    _box(ax, 45, 9.5, 25, 46, "", BQ, ec="#6a9bd8", lw=1.4)
    ax.text(46, 53.8, "BigQuery  (Dataform runs the SQL)", fontsize=8, color=INK2, va="center", fontweight="bold")
    layers = [("raw", "as received", 44.5), ("staging", "typed · de-duplicated", 34.9),
              ("clean", "business rules · test accounts out", 25.3), ("analytics", "CAC · LTV · repeat rate · catalogue", 15.7)]
    for i, (n, d, y) in enumerate(layers):
        _box(ax, 47, y, 21, 7, f"{n}\n{d}", LAYER[i], fs=7.4)
        if i < 3:
            _arrow(ax, (57.5, y), (57.5, y - 2.6))
    _box(ax, 47, 10.3, 21, 4.2, "Data-quality tests gate every step:\nblock publishing and raise alerts", "#fde9e6", ec="#d9534f", lw=1.2, ls="--", fs=6.8)
    # raw data enters BigQuery raw: native exports directly, Cloud Storage files via a load
    _arrow(ax, (41, 46.5), (47, 48.5)); _arrow(ax, (41, 17.5), (43, 17.5), style="-")
    _arrow(ax, (43, 17.5), (43, 47.5), style="-"); _arrow(ax, (43, 47.5), (47, 47.5))

    # --- consumption
    _box(ax, 74, 45.5, 25, 8.5, "Looker Studio dashboard\nspend · new customers · CAC · LTV:CAC\nrepeat rate · revenue/customer · trends", CONS, fs=7.2)
    _box(ax, 74, 17, 25, 25.5, "", CONS)
    ax.text(75.2, 40.2, "Conversational assistant (Cloud Run)", fontsize=7.8, fontweight="bold", color=INK, va="center")
    steps = ["1  LLM turns question into structured intent", "2  Code validates metric / channel / period",
             "3  Approved parameterised SQL template", "4  SQL validator: SELECT-only, allow-list",
             "5  BigQuery, read-only service account", "6  LLM explains returned numbers only,", "     with definition · period · freshness"]
    for i, s_ in enumerate(steps):
        ax.text(75.2, 37.4 - i * 2.95, s_, fontsize=7.0, color=INK, va="center")
    _box(ax, 74, 9.5, 25, 5.5, "Audit log (BigQuery)\nquestion · SQL · result · answer", "#d3ebe0", fs=7)
    _arrow(ax, (68, 21), (74, 49.5)); _arrow(ax, (68, 21), (74, 29))
    _arrow(ax, (86.5, 17), (86.5, 15))

    # --- operations band
    ax.text(1, 7.4, "OPERATIONS", fontsize=8, color=INK2, fontweight="bold", va="center")
    _box(ax, 1, 1, 32, 5, "Cloud Scheduler (daily) → Cloud Workflows\nextract → transform → test → publish, with retries", OPS, fs=7.4)
    _box(ax, 34.5, 1, 31, 5, "Secret Manager: API keys\nleast-privilege service accounts, no keys in code", OPS, fs=7.4)
    _box(ax, 67, 1, 32, 5, "Cloud Logging + Monitoring\nfailed job · stale data · failed test → Slack / email", OPS, fs=7.4)
    fig.savefig(path, dpi=170, facecolor=SURFACE, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)


def word_count(md: str) -> int:
    r = re.sub(r"^\s*-\s+", " ", md, flags=re.M)         # bullet markers are not words
    r = re.sub(r"[*#|]", " ", r)
    return len((TITLE + " " + r).split())                 # includes the title and list numbers


def _register():
    base = matplotlib.get_data_path() + "/fonts/ttf/"
    pdfmetrics.registerFont(TTFont("DV", base + "DejaVuSans.ttf"))
    pdfmetrics.registerFont(TTFont("DV-B", base + "DejaVuSans-Bold.ttf"))
    pdfmetrics.registerFont(TTFont("DV-I", base + "DejaVuSans-Oblique.ttf"))
    pdfmetrics.registerFontFamily("DV", normal="DV", bold="DV-B", italic="DV-I", boldItalic="DV-B")


def _html(s: str) -> str:
    s = s.replace("&", "&amp;").replace("<", "&lt;")
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    return re.sub(r"\*(.+?)\*", r"<i>\1</i>", s)


def build_pdf(md: str, diagram, path):
    _register()
    body = ParagraphStyle("b", fontName="DV", fontSize=8.6, leading=11.8, spaceAfter=3, textColor=colors.HexColor("#0b0b0b"))
    bl = ParagraphStyle("bl", parent=body, leftIndent=12, bulletIndent=2)
    nl = ParagraphStyle("nl", parent=body, leftIndent=26, bulletIndent=14, spaceAfter=1.5)
    h2 = ParagraphStyle("h2", parent=body, fontName="DV-B", fontSize=10.5, leading=14, spaceBefore=7, spaceAfter=3)
    title = ParagraphStyle("t", parent=body, fontName="DV-B", fontSize=14, leading=18, spaceAfter=2)
    story = [Paragraph(TITLE, title)]
    for line in md.strip().splitlines():
        if not line.strip():
            continue
        m = re.match(r"^(\s+)(\d+)\.\s+(.*)", line)
        if line.startswith("## "):
            story.append(Paragraph(_html(line[3:]), h2))
        elif m:
            story.append(Paragraph(_html(m.group(3)), nl, bulletText=f"{m.group(2)}."))
        elif line.startswith("- "):
            story.append(Paragraph(_html(line[2:]), bl, bulletText="•"))
        else:
            story.append(Paragraph(_html(line), body))
    story.append(PageBreak())
    w = A4[0] - 3 * cm
    story += [Paragraph("Architecture diagram", h2), Spacer(1, 4), Image(str(diagram), width=w, height=w * 0.585)]
    SimpleDocTemplate(str(path), pagesize=A4, leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.4 * cm,
                      bottomMargin=1.2 * cm, title="UrbanCart Architecture Design", author="Growth Analytics").build(story)


def build_all():
    C.PART3_DIR.mkdir(parents=True, exist_ok=True)
    md = (C.PART3_DIR / "Architecture_Design.md").read_text(encoding="utf-8")
    n = word_count(md)
    assert n <= MAX_WORDS, f"design note is {n} words (limit {MAX_WORDS})"
    png = C.PART3_DIR / "architecture_diagram.png"
    draw_diagram(png)
    build_pdf(md, png, C.PART3_DIR / "Architecture_Design.pdf")
    return n


if __name__ == "__main__":
    print("design note words (incl. title, excl. diagram):", build_all())
