"""Part 2 charts. Every value is read from the saved Part 1 result tables (no retyped numbers).

Design choices (validated with the dataviz palette checker):
  * One fixed colour per channel across all charts (categorical slots 1-4, never re-ordered).
  * Bar charts start at zero; line chart y-axis also starts at zero, so slopes are not exaggerated.
  * Every bar/line end carries a visible value label (needed because two of the four colours sit
    below 3:1 contrast on white); text is always dark ink, never the series colour.
  * No dual axes, no gridlines clutter, no 3-D.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src import config as C

CHANNEL_COLOR = {"Google Ads": "#2a78d6", "Meta Ads": "#eb6834", "Affiliate": "#1baf7a", "Influencer": "#eda100"}
INK, INK2, GRID, SURFACE, NEUTRAL = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb", "#9a9a95"
ORDER = C.PAID_CHANNELS            # Google Ads, Meta Ads, Affiliate, Influencer (fixed everywhere)


def _style(ax, ylabel, xlabel=None):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_ylabel(ylabel, color=INK2, fontsize=9)
    if xlabel:
        ax.set_xlabel(xlabel, color=INK2, fontsize=9)


def _finish(fig, ax, title, subtitle, path, source):
    fig.patch.set_facecolor(SURFACE)
    fig.text(0.07, 0.955, title, fontsize=12.5, fontweight="bold", color=INK, ha="left", va="top")
    fig.text(0.07, 0.895, subtitle, fontsize=9, color=INK2, ha="left", va="top")
    fig.text(0.07, 0.015, source, fontsize=7.5, color=INK2, ha="left", va="bottom")
    fig.subplots_adjust(top=0.79, bottom=0.17, left=0.11, right=0.97)
    fig.savefig(path, dpi=200, facecolor=SURFACE)
    plt.close(fig)


def chart_cac(acq: pd.DataFrame, path):
    a = acq.set_index("channel").loc[ORDER]
    avg = acq.set_index("channel").loc["All paid", "cac"]
    fig, ax = plt.subplots(figsize=(7.5, 4.4))
    ax.axhline(avg, color=INK2, linestyle="--", linewidth=1, zorder=1)
    ax.text(-0.42, avg + 16, f"All paid channels: ₹{avg:,.0f}", ha="left", color=INK2, fontsize=8.5)
    bars = ax.bar(ORDER, a["cac"], color=[CHANNEL_COLOR[c] for c in ORDER], width=0.55, zorder=2)
    for b, v in zip(bars, a["cac"]):
        ax.text(b.get_x() + b.get_width() / 2, v + 15, f"₹{v:,.0f}", ha="center", va="bottom", color=INK, fontsize=10,
                fontweight="bold", zorder=3, bbox=dict(facecolor=SURFACE, edgecolor="none", pad=1.5))
    ax.set_ylim(0, a["cac"].max() * 1.18)
    _style(ax, "CAC (₹ per new customer)", "Paid channel")
    _finish(fig, ax, "Influencer and Meta Ads cost the most to acquire a customer",
            "Customer acquisition cost = Jan–Jun 2026 channel spend ÷ customers with ≥1 delivered order",
            path, "Source: outputs/part1_analysis/acquisition_metrics.csv (cleaned data; QA test accounts and duplicate orders excluded)")


def chart_ltv(ltv: pd.DataFrame, path):
    l = ltv.set_index("channel").loc[ORDER]
    fig, ax = plt.subplots(figsize=(7.5, 4.4))
    w, xs = 0.34, range(len(ORDER))
    b1 = ax.bar([x - w / 2 - 0.01 for x in xs], l["ltv"], width=w, color=[CHANNEL_COLOR[c] for c in ORDER], label="LTV (30% × revenue per customer)")
    b2 = ax.bar([x + w / 2 + 0.01 for x in xs], l["cac"], width=w, color=NEUTRAL, label="CAC")
    for b, v in list(zip(b1, l["ltv"])) + list(zip(b2, l["cac"])):
        ax.text(b.get_x() + b.get_width() / 2, v + 12, f"₹{v:,.0f}", ha="center", va="bottom", color=INK, fontsize=9)
    for x, ratio in zip(xs, l["ltv_cac_ratio"]):
        ax.text(x, max(l["ltv"].max(), l["cac"].max()) * 1.2, f"LTV:CAC {ratio:.2f}", ha="center", color=INK, fontsize=9.5, fontweight="bold")
    ax.set_xticks(list(xs)); ax.set_xticklabels(ORDER)
    ax.set_ylim(0, max(l["ltv"].max(), l["cac"].max()) * 1.32)
    ax.legend([b1.patches[0], b2.patches[0]], ["LTV (channel colour)", "CAC (grey)"], frameon=False, fontsize=8.5,
              labelcolor=INK2, loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=2)
    _style(ax, "₹ per customer", "Paid channel")
    _finish(fig, ax, "Only Google Ads earns back its acquisition cost",
            "LTV = Jan–Jun revenue per customer × 30% margin (a 0–6 month value, not a lifetime forecast)",
            path, "Source: outputs/part1_analysis/ltv_cac_metrics.csv")


def chart_trend(monthly: pd.DataFrame, path):
    m = monthly.pivot(index="month", columns="channel", values="cac").loc[C.MONTHS, ORDER]
    labels = [pd.Timestamp(x + "-01").strftime("%b") for x in m.index]
    fig, ax = plt.subplots(figsize=(7.5, 4.4))
    xs = list(range(len(m)))
    for ch in ORDER:
        ax.plot(xs, m[ch], color=CHANNEL_COLOR[ch], linewidth=2.2 if ch == "Meta Ads" else 1.8, marker="o", markersize=6,
                markeredgecolor=SURFACE, markeredgewidth=1.2, label=ch)
    # Direct end labels (value in ink, small colour swatch via the legend)
    ends = m.iloc[-1].sort_values()
    placed = []
    for ch, v in ends.items():
        y = v
        while any(abs(y - p) < 70 for p in placed):
            y += 70
        placed.append(y)
        ax.text(len(m) - 1 + 0.12, y, f"{ch}  ₹{v:,.0f}", va="center", color=INK, fontsize=8.5)
    ax.set_xticks(xs); ax.set_xticklabels(labels)
    ax.set_xlim(-0.2, len(m) - 1 + 1.9)
    ax.set_ylim(0, 1300)
    ax.legend(frameon=False, fontsize=8.5, labelcolor=INK2, loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=4)
    _style(ax, "CAC (₹ per new customer)", "Signup month, 2026")
    _finish(fig, ax, "Meta Ads CAC more than doubled; the other channels stayed flat",
            "Monthly CAC = month's channel spend ÷ customers who signed up that month and have ≥1 delivered order",
            path, "Source: outputs/part1_analysis/monthly_cac_trends.csv. Y-axis starts at zero.")


def generate_all():
    C.CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    acq = pd.read_csv(C.PART1_DIR / "acquisition_metrics.csv")
    ltv = pd.read_csv(C.PART1_DIR / "ltv_cac_metrics.csv")
    monthly = pd.read_csv(C.PART1_DIR / "monthly_cac_trends.csv")
    paths = [C.CHARTS_DIR / "chart1_cac_by_channel.png", C.CHARTS_DIR / "chart2_ltv_vs_cac_by_channel.png",
             C.CHARTS_DIR / "chart3_monthly_cac_trend.png"]
    chart_cac(acq, paths[0]); chart_ltv(ltv, paths[1]); chart_trend(monthly, paths[2])
    return paths


if __name__ == "__main__":
    for p in generate_all():
        print(p)
