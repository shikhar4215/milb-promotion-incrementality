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
    # One row per club. Grouping by venue as well would split any club that
    # played away from its usual park - Iowa hosted a game at the Field of
    # Dreams site - and a duplicated key breaks the relationship to the fact
    # table. Venue is reduced to the club's primary park instead.
    # Clubs rebrand mid-panel - Oklahoma City went from "Baseball Club" to
    # "Comets" between 2024 and 2025 - so grouping by name as well as id would
    # emit two rows for one club and break the relationship to the fact table.
    # The club is keyed on team_id and labelled with its most recent name.
    latest = (src.sort_values("season")
                 .groupby("team_id")[["home_team", "league_name"]].last())

    dim_club = (
        src.groupby(["team_id"])
        .agg(home_dates=("date", "size"),
             mean_attendance=("attendance", "mean"),
             max_attendance=("attendance", "max"),
             giveaways=("has_giveaway", "sum"),
             primary_venue=("venue_name", lambda v: v.mode().iat[0]),
             venues_used=("venue_name", "nunique"))
        .reset_index()
        .join(latest, on="team_id")
        .rename(columns={"home_team": "club", "league_name": "league"})
    )
    assert dim_club["team_id"].is_unique, "dim_club[team_id] must be unique"

    # Coverage is graded per club-season, so a club can be eligible in one year
    # and not the next. The dimension is at club grain, so it carries the count
    # of eligible seasons rather than a single label that would silently pick
    # whichever season sorted first.
    seasons_total = src["season"].nunique()
    cs = src.drop_duplicates(["team_id", "season"])[["team_id", "season", "club_coverage"]]
    eligible_seasons = (
        cs.assign(ok=(cs["club_coverage"] == "full_season_release").astype(int))
          .groupby("team_id")["ok"].sum()
    )
    dim_club["eligible_seasons"] = dim_club["team_id"].map(eligible_seasons).fillna(0).astype(int)
    dim_club["seasons_observed"] = dim_club["team_id"].map(
        cs.groupby("team_id").size()).fillna(0).astype(int)
    dim_club["coverage_label"] = np.select(
        [dim_club["eligible_seasons"] == seasons_total,
         dim_club["eligible_seasons"] > 0],
        ["Complete, every season", "Complete in some seasons"],
        default="Never complete",
    )
    # A club counts as eligible for club-level display if any season qualifies;
    # the fact table still carries per-date eligibility, which is what the
    # models actually filter on.
    dim_club["analysis_eligible"] = (dim_club["eligible_seasons"] > 0).astype(int)
    dim_club["giveaway_rate"] = dim_club["giveaways"] / dim_club["home_dates"]
    dim_club["mean_attendance"] = dim_club["mean_attendance"].round(0)
    dim_club.to_csv(BI / "dim_club.csv", index=False)

    # ---- fct_home_date ---------------------------------------------------
    keep = [
        "date_key", "season", "team_id", "away_team_id", "attendance", "games_that_date",
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
    bands = ["Under 55F", "55-65F", "65-75F", "75-85F", "85F+"]
    fct["temp_band"] = pd.cut(fct["temp_f"], [-99, 55, 65, 75, 85, 999], labels=bands)
    # Power BI sorts text alphabetically, which would put "Under 55F" last.
    # Ship an explicit sort key so the axis reads cold to hot.
    fct["temp_band_num"] = fct["temp_band"].map({b: i for i, b in enumerate(bands)})
    # Three-way status for the control-group chart. A date merely lacking a
    # giveaway is not a clean control: if it sits beside one in the same
    # homestand it may be contaminated by it.
    fct["control_status"] = np.where(
        fct["has_giveaway"] == 1, "Giveaway",
        np.where(fct["games_from_giveaway"].isna(),
                 "Clean control", "Adjacent to a giveaway"))
    fct["control_status_order"] = fct["control_status"].map(
        {"Giveaway": 0, "Adjacent to a giveaway": 1, "Clean control": 2})

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
    # Power BI sorts text alphabetically, which would order the homestand
    # positions +1, +2, +3, +4, -1, -2, -3, -4, Giveaway. Ship an explicit
    # sort key, and a short scope label fit for a chart legend.
    # Offset the weekday keys so the two analyses can never interleave on a
    # shared axis: positions occupy 0-8, weekdays 100-106.
    DAY_ORDER = {d: 100 + i for i, d in enumerate(
        ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])}
    POS_ORDER = {c: i for i, c in enumerate(
        ["-4 games", "-3 games", "-2 games", "-1 games", "Giveaway",
         "+1 games", "+2 games", "+3 games", "+4 games"])}

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
            "category_order": DAY_ORDER.get(r["day_of_week"], 99),
            "scope": "By night",
        })

    for tag, label in [("eligible", "17 complete-coverage clubs"),
                       ("all_clubs", "28 clubs incl. incomplete")]:
        short = "17 clubs, complete data" if tag == "eligible" else "28 clubs, incl. incomplete"
        off = pd.read_csv(config.REPORTS / f"lift_by_offset_{tag}.csv")
        for _, r in off.iterrows():
            rows.append({
                "analysis": f"Position in homestand ({label})",
                "category": ("Giveaway" if r["offset"] == 0 else f"{int(r['offset']):+d} games"),
                "n": int(r["n"]), "effect_pct": round(r["mean_lift_pct"], 2),
                "ci_low": round(r["ci_low_pct"], 2), "ci_high": round(r["ci_high_pct"], 2),
                "excludes_zero": int(r["ci_low_pct"] > 0 or r["ci_high_pct"] < 0),
                "reliable": 1, "note": "",
                "category_order": POS_ORDER.get(
                    "Giveaway" if r["offset"] == 0 else f"{int(r['offset']):+d} games", 99),
                "scope": short,
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
