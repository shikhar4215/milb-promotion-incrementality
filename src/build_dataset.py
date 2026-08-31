"""
Build the analysis-ready dataset.

Collapses games to home dates, reconstructs homestand structure, joins the
verified giveaway calendar, and engineers every temporal feature in pandas so
Power BI reads finished columns rather than computing dates itself.

Outputs
-------
    data/processed/games_analysis.csv   one row per club home date
    data/processed/dim_date.csv         date dimension, integer date_key

Usage
-----
    python3 src/build_dataset.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import config

PLAYED = ("Final", "Completed Early")

# 2026 US dates that plausibly move ballpark demand.
HOLIDAYS_2026 = {
    "2026-05-10": "Mother's Day",
    "2026-05-25": "Memorial Day",
    "2026-06-21": "Father's Day",
    "2026-07-04": "Independence Day",
    "2026-09-07": "Labor Day",
}


# ---------------------------------------------------------------------------
# Homestand reconstruction
# ---------------------------------------------------------------------------
def build_homestands(schedule: pd.DataFrame) -> pd.DataFrame:
    """
    Assign a homestand id to every home date.

    A homestand is a run of home dates uninterrupted by a road game. Off-days
    inside a stand do not break it - the club is still in town, and the fans
    deciding between Friday and Saturday are the same fans. A road trip does
    break it, which is what makes the displacement test meaningful.
    """
    frames = []
    for team_id, club_games in schedule.groupby("home_team_id"):
        # Every date this club appeared, home or away.
        home = club_games[["date"]].assign(is_home=True)
        away = schedule.loc[schedule["away_team_id"] == team_id, ["date"]].assign(is_home=False)

        timeline = (
            pd.concat([home, away])
            .drop_duplicates(subset="date")
            .sort_values("date")
            .reset_index(drop=True)
        )

        # A new homestand starts whenever a home date follows a road date.
        prev_away = (~timeline["is_home"]).shift(fill_value=True)
        timeline["homestand_seq"] = (timeline["is_home"] & prev_away).cumsum()

        stand = timeline[timeline["is_home"]].copy()
        stand["team_id"] = team_id
        stand["homestand_id"] = (
            stand["team_id"].astype(str) + "-" + stand["homestand_seq"].astype(str)
        )
        stand["homestand_game_index"] = stand.groupby("homestand_id").cumcount() + 1
        stand["homestand_length"] = stand.groupby("homestand_id")["homestand_id"].transform("size")
        frames.append(stand[["team_id", "date", "homestand_id",
                             "homestand_game_index", "homestand_length"]])

    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Weather parsing
# ---------------------------------------------------------------------------
def parse_weather(df: pd.DataFrame) -> pd.DataFrame:
    df["temp_f"] = pd.to_numeric(df["weather_temp_f"], errors="coerce")

    wind = df["weather_wind"].fillna("").str.extract(r"^(\d+)\s*mph,?\s*(.*)$")
    df["wind_mph"] = pd.to_numeric(wind[0], errors="coerce")
    df["wind_direction"] = wind[1].replace("", np.nan)

    condition = df["weather_condition"].fillna("Unknown")
    df["weather_group"] = np.select(
        [
            condition.isin(["Sunny", "Clear"]),
            condition.isin(["Partly Cloudy", "Cloudy", "Overcast"]),
            condition.isin(["Rain", "Drizzle", "Snow"]),
        ],
        ["Clear", "Cloudy", "Precipitation"],
        default="Unknown",
    )
    df["is_wet"] = (df["weather_group"] == "Precipitation").astype(int)
    return df


# ---------------------------------------------------------------------------
def main() -> None:
    config.ensure_dirs()

    games = pd.read_csv(config.DATA_INTERIM / "games_raw.csv")
    schedule = pd.read_csv(config.DATA_INTERIM / "schedule.csv")
    giveaways = pd.read_csv(config.PROJECT_ROOT / "data/reference/giveaways_2026.csv")

    played = games[games["status"].isin(PLAYED)].copy()

    # --- collapse to one row per club home date ----------------------------
    # Doubleheaders book the whole gate to one game of the pair, so summing
    # across the date is the only honest attendance figure.
    agg = (
        played.groupby(["home_team_id", "date"])
        .agg(
            attendance=("attendance", "sum"),
            games_that_date=("game_pk", "size"),
            home_team=("home_team", "first"),
            league_name=("league_name", "first"),
            venue_name=("venue_name", "first"),
            away_team=("away_team", "first"),
            away_team_id=("away_team_id", "first"),
            day_night=("day_night", "first"),
            home_wins=("home_wins", "max"),
            home_losses=("home_losses", "max"),
            away_wins=("away_wins", "max"),
            away_losses=("away_losses", "max"),
            weather_condition=("weather_condition", "first"),
            weather_temp_f=("weather_temp_f", "first"),
            weather_wind=("weather_wind", "first"),
        )
        .reset_index()
        .rename(columns={"home_team_id": "team_id"})
    )
    agg = agg[agg["attendance"] > 0].copy()

    # --- temporal features (all computed here, none left to Power BI) ------
    d = pd.to_datetime(agg["date"])
    agg["date_key"] = d.dt.strftime("%Y%m%d").astype(int)
    agg["day_of_week"] = d.dt.day_name()
    agg["day_of_week_num"] = d.dt.dayofweek           # Monday = 0
    agg["month_num"] = d.dt.month
    agg["month_name"] = d.dt.month_name()
    agg["week_of_season"] = ((d - d.min()).dt.days // 7) + 1
    agg["is_weekend"] = agg["day_of_week_num"].isin([4, 5, 6]).astype(int)  # Fri-Sun
    agg["holiday"] = agg["date"].map(HOLIDAYS_2026)
    agg["is_holiday"] = agg["holiday"].notna().astype(int)

    # --- homestand structure ----------------------------------------------
    agg = agg.merge(build_homestands(schedule), on=["team_id", "date"], how="left")
    agg = agg.sort_values(["team_id", "date"])
    agg["days_since_last_home_date"] = (
        agg.groupby("team_id")["date"].apply(
            lambda s: pd.to_datetime(s).diff().dt.days
        ).reset_index(level=0, drop=True)
    )

    # --- team strength -----------------------------------------------------
    agg["home_win_pct"] = agg["home_wins"] / (agg["home_wins"] + agg["home_losses"]).replace(0, np.nan)
    agg["away_win_pct"] = agg["away_wins"] / (agg["away_wins"] + agg["away_losses"]).replace(0, np.nan)

    agg = parse_weather(agg)

    # --- treatment ---------------------------------------------------------
    give = giveaways[giveaways["date"].notna()].copy()

    club_coverage = give.groupby("team_id")["coverage"].first()
    all_coverage = giveaways.groupby("team_id")["coverage"].first()

    per_date = (
        give.groupby(["team_id", "date"])
        .agg(giveaway_item=("item", lambda s: " | ".join(s)),
             giveaway_count=("item", "size"))
        .reset_index()
    )

    agg = agg.merge(per_date, on=["team_id", "date"], how="left")
    agg["has_giveaway"] = agg["giveaway_item"].notna().astype(int)
    agg["giveaway_count"] = agg["giveaway_count"].fillna(0).astype(int)
    agg["club_coverage"] = agg["team_id"].map(all_coverage).fillna("no_source_found")
    agg["analysis_eligible"] = (agg["club_coverage"] == "full_season_release").astype(int)

    # Position relative to the nearest giveaway inside the same homestand -
    # this is the column the displacement test is built on.
    agg["homestand_has_giveaway"] = agg.groupby("homestand_id")["has_giveaway"].transform("max")

    def offset_from_giveaway(group: pd.DataFrame) -> pd.Series:
        treated = group.loc[group["has_giveaway"] == 1, "homestand_game_index"]
        if treated.empty:
            return pd.Series(np.nan, index=group.index)
        idx = group["homestand_game_index"].to_numpy()[:, None]
        return pd.Series(
            (idx - treated.to_numpy()[None, :]).astype(float)
            [np.arange(len(group)), np.abs(idx - treated.to_numpy()[None, :]).argmin(axis=1)],
            index=group.index,
        )

    agg["games_from_giveaway"] = (
        agg.groupby("homestand_id", group_keys=False).apply(offset_from_giveaway)
    )

    # --- write -------------------------------------------------------------
    cols = [
        "date_key", "date", "team_id", "home_team", "league_name", "venue_name",
        "away_team", "away_team_id", "attendance", "games_that_date", "day_night",
        "day_of_week", "day_of_week_num", "month_num", "month_name",
        "week_of_season", "is_weekend", "holiday", "is_holiday",
        "homestand_id", "homestand_game_index", "homestand_length",
        "days_since_last_home_date", "home_win_pct", "away_win_pct",
        "weather_condition", "weather_group", "temp_f", "wind_mph",
        "wind_direction", "is_wet",
        "has_giveaway", "giveaway_count", "giveaway_item",
        "homestand_has_giveaway", "games_from_giveaway",
        "club_coverage", "analysis_eligible",
    ]
    out = agg[cols].sort_values(["home_team", "date"])
    out_path = config.DATA_PROCESSED / "games_analysis.csv"
    out.to_csv(out_path, index=False)

    # --- date dimension ----------------------------------------------------
    span = pd.date_range(out["date"].min(), out["date"].max(), freq="D")
    dim = pd.DataFrame({"date": span.strftime("%Y-%m-%d")})
    dim["date_key"] = span.strftime("%Y%m%d").astype(int)
    dim["year"] = span.year
    dim["month_num"] = span.month
    dim["month_name"] = span.month_name()
    dim["day_of_month"] = span.day
    dim["day_of_week"] = span.day_name()
    dim["day_of_week_num"] = span.dayofweek
    dim["is_weekend"] = dim["day_of_week_num"].isin([4, 5, 6]).astype(int)
    dim["holiday"] = dim["date"].map(HOLIDAYS_2026)
    dim = dim[["date_key", "date", "year", "month_num", "month_name", "day_of_month",
               "day_of_week", "day_of_week_num", "is_weekend", "holiday"]]
    dim.to_csv(config.DATA_PROCESSED / "dim_date.csv", index=False)

    # --- summary -----------------------------------------------------------
    elig = out[out["analysis_eligible"] == 1]
    print(f"home dates:            {len(out):,}")
    print(f"  with a giveaway:     {int(out['has_giveaway'].sum()):,}")
    print(f"  clubs:               {out['team_id'].nunique()}")
    print(f"  homestands:          {out['homestand_id'].nunique():,}")
    print(f"  median homestand:    {out.groupby('homestand_id').size().median():.0f} dates")
    print()
    print(f"analysis-eligible (full_season_release clubs only):")
    print(f"  home dates:          {len(elig):,}")
    print(f"  with a giveaway:     {int(elig['has_giveaway'].sum()):,}"
          f"  ({elig['has_giveaway'].mean():.1%})")
    print(f"  clubs:               {elig['team_id'].nunique()}")
    print()
    print(f"-> {out_path.relative_to(config.PROJECT_ROOT)}")
    print(f"-> {(config.DATA_PROCESSED / 'dim_date.csv').relative_to(config.PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
