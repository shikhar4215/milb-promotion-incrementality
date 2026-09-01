"""
Render the project's figures.

Static PNGs for the README and as a visual reference for the Power BI build.
Colours come from a validated categorical palette (blue/orange pass the CVD and
normal-vision separation gates on this surface); text stays in ink tokens rather
than series colours, and estimates are drawn as point-with-interval rather than
bars, because a bar implies a magnitude from zero and these are effects with
uncertainty.

Usage
-----
    python3 src/make_figures.py
    python3 src/make_figures.py --bi-dir <path> --out-dir <path>
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# --- palette (validated: see docs) -----------------------------------------
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
S1 = "#2a78d6"   # blue
S2 = "#eb6834"   # orange

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

plt.rcParams.update({
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans"],
    "font.size": 10,
    "axes.edgecolor": BASELINE,
    "axes.labelcolor": INK2,
    "text.color": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.spines.top": False,
    "axes.spines.right": False,
})


def _style(ax, title, subtitle=None, xlabel=None, ylabel=None):
    ax.set_title(title, color=INK, fontsize=13, fontweight="600", loc="left", pad=30 if subtitle else 10)
    if subtitle:
        ax.text(0, 1.015, subtitle, transform=ax.transAxes, color=INK2, fontsize=9.5,
                va="bottom", wrap=True)
    if xlabel:
        ax.set_xlabel(xlabel, color=INK2, fontsize=9.5)
    if ylabel:
        ax.set_ylabel(ylabel, color=INK2, fontsize=9.5)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["left"].set_color(BASELINE)
    ax.spines["bottom"].set_color(BASELINE)


# ---------------------------------------------------------------------------
def fig_drivers(fct: pd.DataFrame, out: Path) -> None:
    """What moves attendance before any promotion is involved."""
    fig, axes = plt.subplots(2, 2, figsize=(13, 8.6))
    axes = axes.ravel()

    d = (fct.groupby("day_of_week")["attendance"].agg(["mean", "size"])
         .reindex([x for x in DAY_ORDER if x in fct["day_of_week"].unique()]).dropna())
    ax = axes[0]
    ax.bar(range(len(d)), d["mean"], color=S1, width=0.62)
    ax.set_xticks(range(len(d)))
    # Sample size on the axis: Triple-A barely plays Mondays, and a mean over a
    # handful of dates should not read like the others.
    ax.set_xticklabels([f"{x[:3]}\nn={int(n)}" for x, n in zip(d.index, d["size"])])
    for i, v in enumerate(d["mean"]):
        ax.text(i, v + 90, f"{v:,.0f}", ha="center", color=INK2, fontsize=9)
    _style(ax, "Attendance by night of the week",
           "Mean crowd, all Triple-A home dates, 2026", ylabel="Fans")
    ax.set_ylim(0, d["mean"].max() * 1.16)

    bands = ["Under 55F", "55-65F", "65-75F", "75-85F", "85F+"]
    t = (fct.groupby("temp_band")["attendance"].agg(["mean", "size"])
         .reindex(bands).dropna())
    ax = axes[1]
    ax.bar(range(len(t)), t["mean"], color=S1, width=0.62)
    ax.set_xticks(range(len(t)))
    ax.set_xticklabels([f'{b.replace("F", chr(176) + "F").replace("Under ", "<")}\nn={int(n)}'
                        for b, n in zip(t.index, t["size"])], fontsize=9)
    for i, v in enumerate(t["mean"]):
        ax.text(i, v + 90, f"{v:,.0f}", ha="center", color=INK2, fontsize=9)
    _style(ax, "Attendance peaks at 75-85\u00b0F",
           "Mean crowd by temperature at first pitch", ylabel="Fans")
    ax.set_ylim(0, t["mean"].max() * 1.16)

    w = (fct[fct["weather_group"] != "Unknown"]
         .groupby("weather_group")["attendance"].agg(["mean", "size"])
         .reindex(["Clear", "Cloudy", "Precipitation"]).dropna())
    ax = axes[2]
    ax.bar(range(len(w)), w["mean"], color=S1, width=0.5)
    ax.set_xticks(range(len(w)))
    ax.set_xticklabels([f"{i}\nn={int(n):,}" for i, n in zip(w.index, w["size"])])
    for i, v in enumerate(w["mean"]):
        ax.text(i, v + 90, f"{v:,.0f}", ha="center", color=INK2, fontsize=9)
    _style(ax, "Attendance by weather at first pitch",
           "Conditions recorded at the ballpark", ylabel="Fans")
    ax.set_ylim(0, w["mean"].max() * 1.16)

    months = ["March", "April", "May", "June", "July", "August", "September"]
    m = (fct.groupby("month_name")["attendance"].agg(["mean", "size"])
         .reindex(months).dropna())
    ax = axes[3]
    ax.plot(range(len(m)), m["mean"], color=S1, linewidth=2,
            marker="o", markersize=8, markeredgecolor=SURFACE, markeredgewidth=1.6)
    for i, v in enumerate(m["mean"]):
        ax.text(i, v + 150, f"{v:,.0f}", ha="center", color=INK2, fontsize=9)
    ax.set_xticks(range(len(m)))
    ax.set_xticklabels([f"{x[:3]}\nn={int(n)}" for x, n in zip(m.index, m["size"])], fontsize=9)
    _style(ax, "Attendance across the season",
           "Mean crowd by month", ylabel="Fans")
    ax.set_ylim(min(m["mean"]) * 0.82, m["mean"].max() * 1.12)

    fig.tight_layout(h_pad=3.4, w_pad=3.0)
    fig.savefig(out / "fig1_attendance_drivers.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def fig_lift_by_night(res: pd.DataFrame, out: Path) -> None:
    """Estimated giveaway effect per night, with intervals and a validity flag."""
    d = res[res["analysis"] == "Lift by night"].copy()
    d["order"] = d["category"].map({v: i for i, v in enumerate(DAY_ORDER)})
    d = d.sort_values("order")

    fig, ax = plt.subplots(figsize=(9, 4.8))
    y = np.arange(len(d))

    ax.axvline(0, color=BASELINE, linewidth=1.4, zorder=1)
    for i, (_, r) in enumerate(d.iterrows()):
        reliable = int(r["reliable"]) == 1
        col = S1 if reliable else MUTED
        ax.plot([r["ci_low"], r["ci_high"]], [i, i], color=col, linewidth=2, zorder=2,
                alpha=1.0 if reliable else 0.75)
        ax.plot(r["effect_pct"], i, "o", markersize=10, zorder=3,
                color=col if reliable else SURFACE,
                markeredgecolor=col, markeredgewidth=2)
        ax.text(r["ci_high"] + 1.6, i, f"n={int(r['n'])}", va="center",
                color=MUTED, fontsize=9)
        if not reliable:
            ax.text(r["effect_pct"], i - 0.34, "no valid control group",
                    ha="center", va="top", color=INK2, fontsize=8.5, style="italic")

    ax.set_yticks(y)
    ax.set_yticklabels(d["category"], color=INK2)
    ax.invert_yaxis()
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.grid(axis="y", visible=False)
    ax.set_axisbelow(True)
    _style(ax, "Giveaway effect by night, with 95% intervals",
           "Attendance above or below the model's expectation for that date.\n"
           "Hollow marker: no valid control group exists for that night.",
           xlabel="Difference from expected attendance (%)")
    ax.grid(axis="y", visible=False)
    ax.set_xlim(d["ci_low"].min() - 6, d["ci_high"].max() + 12)

    fig.tight_layout()
    fig.savefig(out / "fig2_lift_by_night.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def fig_specification(res: pd.DataFrame, out: Path) -> None:
    """The robustness chart: the same question, two defensible samples."""
    a = res[res["analysis"].str.startswith("Position in homestand (17")].copy()
    b = res[res["analysis"].str.startswith("Position in homestand (28")].copy()
    order = ["-4 games", "-3 games", "-2 games", "-1 games", "Giveaway",
             "+1 games", "+2 games", "+3 games", "+4 games"]
    lbl = {"-1 games": "Day before", "Giveaway": "Giveaway", "+1 games": "Day after"}

    def prep(df):
        df = df[df["category"].isin(order)].copy()
        df["o"] = df["category"].map({v: i for i, v in enumerate(order)})
        return df.sort_values("o")

    a, b = prep(a), prep(b)

    fig, ax = plt.subplots(figsize=(9.6, 4.8))
    ax.axhline(0, color=BASELINE, linewidth=1.4, zorder=1)

    for df, col, off, name in ((a, S1, -0.13, "17 complete-coverage clubs"),
                               (b, S2, +0.13, "28 clubs, incl. incomplete")):
        x = df["o"].to_numpy() + off
        ax.vlines(x, df["ci_low"], df["ci_high"], color=col, linewidth=2, zorder=2)
        ax.plot(x, df["effect_pct"], "o", markersize=8, color=col,
                markeredgecolor=SURFACE, markeredgewidth=1.6, zorder=3, label=name)

    ax.set_xticks(range(len(order)))
    ax.set_xticklabels([lbl.get(o, o.replace(" games", "")) for o in order], color=INK2)
    _style(ax, "The day-before dip clears zero in one sample and not the other",
           "Attendance vs expected, by position relative to the nearest giveaway in the same homestand.\nUnder homestand fixed effects it disappears in both.",
           ylabel="Difference from expected (%)")
    ax.grid(axis="x", visible=False)

    i = order.index("-1 games")
    ax.annotate("significant dip\nin the clean sample",
                xy=(i - 0.13, a.loc[a["category"] == "-1 games", "effect_pct"].iloc[0]),
                xytext=(i - 1.5, -17), color=INK2, fontsize=9,
                arrowprops=dict(arrowstyle="->", color=MUTED, linewidth=1.2))

    leg = ax.legend(frameon=False, loc="upper left", fontsize=9.5)
    for t in leg.get_texts():
        t.set_color(INK2)

    fig.tight_layout()
    fig.savefig(out / "fig3_specification_check.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def fig_concentration(fct: pd.DataFrame, out: Path) -> None:
    """Why the counterfactual is thin: giveaways are not spread across nights."""
    d = fct[fct["analysis_eligible"] == 1]
    t = d[d["has_giveaway"] == 1].groupby("day_of_week").size()
    # A valid control is a date in a homestand with NO giveaway at all. A date
    # merely lacking a giveaway may still sit next to one and be contaminated
    # by it, so has_giveaway == 0 overstates the usable comparison group.
    u = d[d["games_from_giveaway"].isna()].groupby("day_of_week").size()
    days = [x for x in DAY_ORDER if x in set(t.index) | set(u.index) and x != "Monday"]
    t = t.reindex(days).fillna(0)
    u = u.reindex(days).fillna(0)

    fig, ax = plt.subplots(figsize=(9, 4.6))
    x = np.arange(len(days))
    ax.bar(x - 0.19, t, width=0.36, color=S1, label="With a giveaway")
    ax.bar(x + 0.19, u, width=0.36, color=S2, label="Uncontaminated control dates")

    for i, (a_, b_) in enumerate(zip(t, u)):
        ax.text(i - 0.19, a_ + 1.5, f"{int(a_)}", ha="center", color=INK2, fontsize=9)
        ax.text(i + 0.19, b_ + 1.5, f"{int(b_)}", ha="center", color=INK2, fontsize=9)

    ax.set_xticks(x)
    ax.set_xticklabels([d_[:3] for d_ in days])
    _style(ax, "On Saturdays the control group is smaller than the treated group",
           "Home dates by night, 17 complete-coverage clubs. Controls are dates in homestands with\n"
           "no giveaway at all. Two clubs ran a giveaway on every home Saturday.",
           ylabel="Home dates")
    ax.set_ylim(0, max(t.max(), u.max()) * 1.2)
    leg = ax.legend(frameon=False, fontsize=9.5, loc="upper left")
    for tx in leg.get_texts():
        tx.set_color(INK2)

    fig.tight_layout()
    fig.savefig(out / "fig4_scheduling_concentration.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bi-dir", default=None)
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()

    if args.bi_dir:
        bi, out = Path(args.bi_dir), Path(args.out_dir)
    else:
        import config
        bi, out = config.DATA_PROCESSED / "bi", config.FIGURES
    out.mkdir(parents=True, exist_ok=True)

    fct = pd.read_csv(bi / "fct_home_date.csv")
    res = pd.read_csv(bi / "fct_model_result.csv")

    fig_drivers(fct, out)
    fig_lift_by_night(res, out)
    fig_specification(res, out)
    fig_concentration(fct, out)

    for p in sorted(out.glob("*.png")):
        print(f"  {p.name:<40} {p.stat().st_size/1024:>7,.0f} KB")


if __name__ == "__main__":
    main()
