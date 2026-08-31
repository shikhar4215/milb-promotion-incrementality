"""
Emit a star schema for Power BI.

Power BI runs under x64 emulation on Apple Silicon, where date-based visuals
are the documented failure mode. Every temporal attribute is therefore
pre-computed here and joined on an integer date_key, and the report should have
Options > Data Load > Auto date/time switched OFF. No DAX time intelligence is
needed anywhere.

Tables written to data/processed/bi/
    fct_home_date   one row per club home date - the fact table
    dim_club        club attributes, including promo coverage quality
    dim_date        calendar
    fct_model_result  estimated effects, so the dashboard never hardcodes numbers

Usage
-----
    python3 src/build_bi_tables.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import config

BI = config.DATA_PROCESSED / "bi"


def main() -> None:
    config.ensure_dirs()
    BI.mkdir(parents=True, exist_ok=True)

    src = pd.read_csv(config.DATA_PROCESSED / "games_analysis.csv")
    resid = pd.read_csv(config.DATA_PROCESSED / "games_with_residuals_eligible.csv")

    # ---- dim_club --------------------------------------------------------
    dim_club = (
        src.groupby(["team_id", "home_team", "league_name", "venue_name"])
        .agg(home_dates=("date", "size"),
             mean_attendance=("attendance", "mean"),
             max_attendance=("attendance", "max"),
             giveaways=("has_giveaway", "sum"))
        .reset_index()
        .rename(columns={"home_team": "club", "league_name": "league", "venue_name": "venue"})
    )
    cov = src.groupby("team_id")["club_coverage"].first()
    dim_club["promo_coverage"] = dim_club["team_id"].map(cov)
    dim_club["coverage_label"] = dim_club["promo_coverage"].map({
        "full_season_release": "Complete",
        "partial_assembled": "Partial - known incomplete",
        "no_source_found": "No promo data",
    })
    dim_club["analysis_eligible"] = (dim_club["promo_coverage"] == "full_season_release").astype(int)
    dim_club["giveaway_rate"] = dim_club["giveaways"] / dim_club["home_dates"]
    dim_club["mean_attendance"] = dim_club["mean_attendance"].round(0)
    dim_club.to_csv(BI / "dim_club.csv", index=False)

    # ---- fct_home_date ---------------------------------------------------
    keep = [
        "date_key", "team_id", "away_team_id", "attendance", "games_that_date",
        "day_night", "day_of_week", "day_of_week_num", "month_name", "month_num",
        "week_of_season", "is_weekend", "is_holiday", "holiday",
        "homestand_id", "homestand_game_index", "homestand_length",
        "days_since_last_home_date", "home_win_pct", "away_win_pct",
        "weather_group", "weather_condition", "temp_f", "wind_mph", "is_wet",
        "has_giveaway", "giveaway_count", "giveaway_item",
        "homestand_has_giveaway", "games_from_giveaway", "analysis_eligible",
    ]
    fct = src[keep].copy()

    # Bring in the model's expectation so the dashboard can show actual vs
    # predicted without recomputing anything.
    r = resid[["date_key", "team_id", "predicted_attendance", "residual"]].copy()
    fct = fct.merge(r, on=["date_key", "team_id"], how="left")
    fct["vs_expected"] = fct["attendance"] - fct["predicted_attendance"]
    fct["vs_expected_pct"] = np.where(
        fct["predicted_attendance"].notna(),
        (fct["attendance"] / fct["predicted_attendance"] - 1) * 100, np.nan)
    fct["giveaway_label"] = np.where(fct["has_giveaway"] == 1, "Giveaway", "No giveaway")
    fct["temp_band"] = pd.cut(fct["temp_f"], [-99, 55, 65, 75, 85, 999],
                              labels=["Under 55F", "55-65F", "65-75F", "75-85F", "85F+"])
    fct["offset_label"] = fct["games_from_giveaway"].map(
        lambda o: "Giveaway" if o == 0 else
        (f"{int(o):+d} games" if pd.notna(o) and abs(o) <= 2 else
         ("3+ away" if pd.notna(o) else "No giveaway in homestand")))
    fct = fct.round({"predicted_attendance": 0, "vs_expected": 0,
                     "vs_expected_pct": 2, "residual": 4,
                     "home_win_pct": 3, "away_win_pct": 3})
    fct.to_csv(BI / "fct_home_date.csv", index=False)

    # ---- dim_date --------------------------------------------------------
    pd.read_csv(config.DATA_PROCESSED / "dim_date.csv").to_csv(BI / "dim_date.csv", index=False)

    # ---- fct_model_result ------------------------------------------------
    rows = []
    wk = pd.read_csv(config.REPORTS / "lift_by_weekday.csv")
    for _, r in wk.iterrows():
        reliable = r.get("pool_ratio", np.nan)
        rows.append({
            "analysis": "Lift by night", "category": r["day_of_week"],
            "n": int(r["n"]), "effect_pct": round(r["lift_pct"], 2),
            "ci_low": round(r["ci_low"], 2), "ci_high": round(r["ci_high"], 2),
            "excludes_zero": int(r["ci_low"] > 0 or r["ci_high"] < 0),
            "reliable": int(pd.notna(reliable) and reliable >= 1),
            "note": ("Control pool smaller than treated group - not validated"
                     if pd.notna(reliable) and reliable < 1 else ""),
        })

    for tag, label in [("eligible", "17 complete-coverage clubs"),
                       ("all_clubs", "28 clubs incl. incomplete")]:
        off = pd.read_csv(config.REPORTS / f"lift_by_offset_{tag}.csv")
        for _, r in off.iterrows():
            rows.append({
                "analysis": f"Position in homestand ({label})",
                "category": ("Giveaway" if r["offset"] == 0 else f"{int(r['offset']):+d} games"),
                "n": int(r["n"]), "effect_pct": round(r["mean_lift_pct"], 2),
                "ci_low": round(r["ci_low_pct"], 2), "ci_high": round(r["ci_high_pct"], 2),
                "excludes_zero": int(r["ci_low_pct"] > 0 or r["ci_high_pct"] < 0),
                "reliable": 1, "note": "",
            })

    pd.DataFrame(rows).to_csv(BI / "fct_model_result.csv", index=False)

    print(f"fct_home_date     {len(fct):>6,} rows   {fct.shape[1]} cols")
    print(f"dim_club          {len(dim_club):>6,} rows")
    print(f"dim_date          {len(pd.read_csv(BI/'dim_date.csv')):>6,} rows")
    print(f"fct_model_result  {len(rows):>6,} rows")
    print(f"\n-> {BI.relative_to(config.PROJECT_ROOT)}/")
    print("\nIn Power BI: relate fct_home_date[date_key] -> dim_date[date_key]")
    print("             and fct_home_date[team_id] -> dim_club[team_id]")
    print("Turn OFF Options > Data Load > Auto date/time before loading.")


if __name__ == "__main__":
    main()
