"""
Estimate the counterfactual, then measure lift and displacement.

The design in one paragraph
---------------------------
Fit an attendance model on CLEAN CONTROL dates only - dates far enough from any
giveaway that neither the promotion nor its spillover can influence them. That
model never sees a treated date, so it cannot absorb the effect we are trying to
measure. Predict every date from it, and the residual (actual minus predicted,
in logs) is the share of the crowd the ordinary drivers of attendance do not
explain. Average residuals by distance from the nearest giveaway and the whole
question answers itself:

    offset  0  -> lift          (how much bigger the giveaway crowd was)
    offset +-1 -> displacement  (did the neighbours come in under their own baseline)

Net incremental = lift + displacement, since displacement is negative if real.

Why logs: attendance is right-skewed and effects are proportional. A club drawing
10,000 and one drawing 3,000 do not both gain 800 fans from a bobblehead; they
gain a percentage. Coefficients read directly as percent changes.

Usage
-----
    python3 src/model_baseline.py
    python3 src/model_baseline.py --all-clubs   # sensitivity check
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

import config

# A date is a clean control if no giveaway happened in its homestand, or if it
# sits at least this many games away from the nearest one.
SPILLOVER_WINDOW = 3

FORMULA = (
    "log_attendance ~ C(team_id) + C(day_of_week) + C(month_num) + C(day_night)"
    " + temp_f + temp_f_sq + is_wet + is_holiday"
    " + home_win_pct + away_win_pct"
    " + homestand_game_index + days_since_last_home_date"
)


def load(all_clubs: bool) -> pd.DataFrame:
    df = pd.read_csv(config.DATA_PROCESSED / "games_analysis.csv")

    if not all_clubs:
        df = df[df["analysis_eligible"] == 1].copy()
        scope = "17 clubs with complete season promo releases"
    else:
        df = df[df["club_coverage"] != "no_source_found"].copy()
        scope = "all clubs with any promo data (includes known-incomplete clubs)"

    df["log_attendance"] = np.log(df["attendance"])
    df["temp_f"] = df["temp_f"].fillna(df["temp_f"].median())
    df["temp_f_sq"] = df["temp_f"] ** 2
    df["home_win_pct"] = df["home_win_pct"].fillna(0.5)
    df["away_win_pct"] = df["away_win_pct"].fillna(0.5)
    df["days_since_last_home_date"] = df["days_since_last_home_date"].fillna(1).clip(upper=14)
    df["offset"] = df["games_from_giveaway"]

    print(f"scope: {scope}")
    print(f"home dates: {len(df):,}   giveaways: {int(df['has_giveaway'].sum()):,}\n")
    return df


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--all-clubs", action="store_true",
                    help="Include clubs with known-incomplete promo data.")
    args = ap.parse_args()

    config.ensure_dirs()
    df = load(args.all_clubs)

    # --- clean controls ----------------------------------------------------
    is_clean = df["offset"].isna() | (df["offset"].abs() >= SPILLOVER_WINDOW)
    controls = df[is_clean]
    print(f"clean control dates used to fit the baseline: {len(controls):,} "
          f"({len(controls)/len(df):.0%} of sample)")
    print(f"  (excludes every date within {SPILLOVER_WINDOW-1} games of a giveaway)\n")

    model = smf.ols(FORMULA, data=controls).fit()
    print(f"baseline R-squared: {model.rsquared:.3f}   "
          f"adj: {model.rsquared_adj:.3f}   n = {int(model.nobs):,}")

    # --- residuals for every date -----------------------------------------
    df = df.copy()
    df["predicted_log"] = model.predict(df)
    df["residual"] = df["log_attendance"] - df["predicted_log"]
    df["predicted_attendance"] = np.exp(df["predicted_log"])

    # --- non-promotional drivers, for the dashboard narrative --------------
    print("\n=== what actually moves attendance (baseline coefficients) ===")
    print("  effects are percent change vs the reference level\n")
    for name in model.params.index:
        if name.startswith("C(day_of_week)") or name.startswith("C(day_night)"):
            pct = (np.exp(model.params[name]) - 1) * 100
            label = name.split("[T.")[-1].rstrip("]")
            print(f"  {label:<14} {pct:+6.1f}%   p={model.pvalues[name]:.3f}")
    for name in ["temp_f", "is_wet", "is_holiday", "home_win_pct", "homestand_game_index"]:
        if name in model.params:
            print(f"  {name:<24} coef={model.params[name]:+.4f}  p={model.pvalues[name]:.3f}")

    # --- lift and displacement --------------------------------------------
    print("\n=== residual by distance from nearest giveaway ===")
    print("  offset    n    mean lift        95% CI")
    rows = []
    for off in range(-4, 5):
        sub = df[df["offset"] == off]
        if len(sub) < 5:
            continue
        r = sub["residual"]
        se = r.std(ddof=1) / np.sqrt(len(r))
        pct = (np.exp(r.mean()) - 1) * 100
        lo = (np.exp(r.mean() - 1.96 * se) - 1) * 100
        hi = (np.exp(r.mean() + 1.96 * se) - 1) * 100
        star = "  <-- giveaway" if off == 0 else ""
        print(f"   {off:+3d}   {len(sub):>4}   {pct:+6.1f}%     "
              f"[{lo:+.1f}%, {hi:+.1f}%]{star}")
        rows.append({"offset": off, "n": len(sub), "mean_lift_pct": pct,
                     "ci_low_pct": lo, "ci_high_pct": hi})

    out = pd.DataFrame(rows)
    out.to_csv(config.REPORTS / "lift_by_offset.csv", index=False)

    # --- headline ----------------------------------------------------------
    treated = df[df["offset"] == 0]
    neighbours = df[df["offset"].isin([-1, 1])]

    lift_pct = (np.exp(treated["residual"].mean()) - 1) * 100
    disp_pct = (np.exp(neighbours["residual"].mean()) - 1) * 100

    mean_baseline = treated["predicted_attendance"].mean()
    lift_fans = treated["predicted_attendance"].mean() * (np.exp(treated["residual"].mean()) - 1)
    disp_fans = neighbours["predicted_attendance"].mean() * (np.exp(neighbours["residual"].mean()) - 1)

    print("\n=== headline ===")
    print(f"  giveaway date lift:        {lift_pct:+.1f}%  "
          f"(~{lift_fans:+,.0f} fans on a {mean_baseline:,.0f} baseline)")
    print(f"  adjacent dates (+-1):      {disp_pct:+.1f}%  "
          f"(~{disp_fans:+,.0f} fans each, {len(neighbours)} dates)")
    print(f"  net per giveaway:          ~{lift_fans + 2*disp_fans:+,.0f} fans")
    if disp_pct < 0:
        share = min(100, abs(2*disp_fans) / lift_fans * 100) if lift_fans > 0 else float("nan")
        print(f"\n  {share:.0f}% of the giveaway-day gain is offset by softer "
              f"neighbouring dates.")
    else:
        print("\n  No evidence of demand being pulled forward - adjacent dates "
              "are at or above their own baselines.")

    df.to_csv(config.DATA_PROCESSED / "games_with_residuals.csv", index=False)
    with open(config.REPORTS / "baseline_summary.txt", "w") as f:
        f.write(str(model.summary()))
    print(f"\n-> reports/lift_by_offset.csv, reports/baseline_summary.txt")
    print(f"-> data/processed/games_with_residuals.csv")


if __name__ == "__main__":
    main()
