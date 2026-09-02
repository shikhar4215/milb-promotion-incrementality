"""
Build the analysis-ready dataset.

Collapses games to home dates, reconstructs homestand structure, joins the
verified giveaway calendars, and engineers every temporal feature in pandas so
Power BI reads finished columns rather than computing dates itself.

Covers 2024-2026. Coverage of the giveaway calendars is graded per club-season,
not per club: a club that published a full calendar in one year and homestand
previews in another is eligible in the first and not the second.

Outputs
-------
    data/processed/games_analysis.csv   one row per club home date
    data/processed/dim_date.csv         date dimension, integer date_key

Usage
-----
    python3 src/build_dataset.py
"""

from __future__ import annotations

import calendar
import datetime as dt

import numpy as np
import pandas as pd

import config

PLAYED = ("Final", "Completed Early")
SEASONS = (2024, 2025, 2026)

# Club-seasons whose release states a giveaway count materially above the number
# of dates it actually itemises. The extra dates exist but are unobserved, and an
# unobserved giveaway coded as a control biases lift downward, so these are
# demoted out of the headline sample rather than trusted.
COVERAGE_OVERRIDES: dict[tuple[int, int], tuple[str, str]] = {
    (422, 2025): ("partial_assembled", "release claims giveaways at ~35 dates, itemises 13"),
    (556, 2024): ("partial_assembled", "release claims 31 giveaway dates, itemises 21"),
}


# ---------------------------------------------------------------------------
# Holidays
# ---------------------------------------------------------------------------
def _nth_weekday(year: int, month: int, weekday: int, n: int) -> dt.date:
    """The nth given weekday of a month. Monday = 0, Sunday = 6."""
    first = dt.date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + dt.timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> dt.date:
    last = dt.date(year, month, calendar.monthrange(year, month)[1])
    return last - dt.timedelta(days=(last.weekday() - weekday) % 7)


def us_holidays(years) -> dict[str, str]:
    """US dates that plausibly move ballpark demand, computed rather than typed."""
    out: dict[str, str] = {}
    for y in years:
        out[_nth_weekday(y, 5, 6, 2).isoformat()] = "Mother's Day"
        out[_last_weekday(y, 5, 0).isoformat()] = "Memorial Day"
        out[_nth_weekday(y, 6, 6, 3).isoformat()] = "Father's Day"
        out[f"{y}-07-04"] = "Independence Day"
        out[_nth_weekday(y, 9, 0, 1).isoformat()] = "Labor Day"
    return out


# ---------------------------------------------------------------------------
# Giveaway calendars
# ---------------------------------------------------------------------------
def _normalise_coverage(value: object) -> str:
    """
    Collapse the two source vocabularies onto one.

    The 2026 file was graded as full_season_release / partial_assembled /
    no_source_found. The historical files record how the calendar was recovered
    (complete, partial-first-half, partial-second-half, partial-homestand).
    Anything short of a whole-season release is partial.
    """
    v = str(value).strip().lower()
    if v in ("full_season_release", "complete"):
        return "full_season_release"
    if v.startswith("partial"):
        return "partial_assembled"
    return "no_source_found"


def load_giveaways(seasons=SEASONS) -> pd.DataFrame:
    frames = []
    for year in seasons:
        path = config.PROJECT_ROOT / f"data/reference/giveaways_{year}.csv"
        if not path.exists():
            print(f"  warning: {path.name} not found, season skipped")
            continue
        g = pd.read_csv(path)
        g["season"] = year
        frames.append(g)
    give = pd.concat(frames, ignore_index=True)
    give["coverage"] = give["coverage"].map(_normalise_coverage)
    return give


def coverage_by_club_season(give: pd.DataFrame) -> pd.Series:
    cov = give.groupby(["team_id", "season"])["coverage"].first()
    for key, (label, _reason) in COVERAGE_OVERRIDES.items():
        if key in cov.index:
            cov.loc[key] = label
    return cov


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

    Homestands are scoped to a season. Without that, the last stand of one
    season and the first of the next would merge across the winter, since no
    road game falls between them.
    """
    frames = []
    for (team_id, season), club_games in schedule.groupby(["home_team_id", "season"]):
        season_sched = schedule[schedule["season"] == season]

        home = club_games[["date"]].assign(is_home=True)
        away = season_sched.loc[
            season_sched["away_team_id"] == team_id, ["date"]
        ].assign(is_home=False)

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
        stand["season"] = season
        stand["homestand_id"] = (
            f"{season}-" + stand["team_id"].astype(str)
            + "-" + stand["homestand_seq"].astype(str)
        )
        stand["homestand_game_index"] = stand.groupby("homestand_id").cumcount() + 1
        stand["homestand_length"] = stand.groupby("homestand_id")["homestand_id"].transform("size")
        frames.append(stand[["team_id", "season", "date", "homestand_id",
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
    giveaways = load_giveaways()

    missing = set(SEASONS) - set(games["season"].unique())
    if missing:
        raise SystemExit(
            f"games_raw.csv is missing season(s) {sorted(missing)}. "
            f"Re-run: python3 src/extract_games.py --seasons {' '.join(map(str, SEASONS))}"
        )

    played = games[games["status"].isin(PLAYED)].copy()

    # --- collapse to one row per club home date ----------------------------
    # Doubleheaders book the whole gate to one game of the pair, so summing
    # across the date is the only honest attendance figure.
    agg = (
        played.groupby(["home_team_id", "date"])
        .agg(
            season=("season", "first"),
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
    agg["is_weekend"] = agg["day_of_week_num"].isin([4, 5, 6]).astype(int)  # Fri-Sun

    # Week 1 is the opening week of each season, not of the panel.
    agg["week_of_season"] = agg.groupby("season")["date"].transform(
        lambda s: ((pd.to_datetime(s) - pd.to_datetime(s).min()).dt.days // 7) + 1
    )

    holidays = us_holidays(SEASONS)
    agg["holiday"] = agg["date"].map(holidays)
    agg["is_holiday"] = agg["holiday"].notna().astype(int)

    # --- homestand structure ----------------------------------------------
    agg = agg.merge(build_homestands(schedule), on=["team_id", "season", "date"], how="left")
    agg = agg.sort_values(["team_id", "date"])
    # Reset the gap at each season boundary; the winter is not a road trip.
    agg["days_since_last_home_date"] = agg.groupby(["team_id", "season"])["date"].transform(
        lambda s: pd.to_datetime(s).diff().dt.days
    )

    # --- team strength -----------------------------------------------------
    agg["home_win_pct"] = agg["home_wins"] / (agg["home_wins"] + agg["home_losses"]).replace(0, np.nan)
    agg["away_win_pct"] = agg["away_wins"] / (agg["away_wins"] + agg["away_losses"]).replace(0, np.nan)

    agg = parse_weather(agg)

    # --- treatment ---------------------------------------------------------
    give = giveaways[giveaways["date"].notna()].copy()

    per_date = (
        give.groupby(["team_id", "date"])
        .agg(giveaway_item=("item", lambda s: " | ".join(s)),
             giveaway_count=("item", "size"))
        .reset_index()
    )

    agg = agg.merge(per_date, on=["team_id", "date"], how="left")
    agg["has_giveaway"] = agg["giveaway_item"].notna().astype(int)
    agg["giveaway_count"] = agg["giveaway_count"].fillna(0).astype(int)

    cov = coverage_by_club_season(giveaways)
    agg["club_coverage"] = pd.MultiIndex.from_arrays(
        [agg["team_id"], agg["season"]]
    ).map(cov)
    agg["club_coverage"] = agg["club_coverage"].fillna("no_source_found")
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
        "date_key", "date", "season", "team_id", "home_team", "league_name", "venue_name",
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
    dim["holiday"] = dim["date"].map(holidays)
    dim = dim[["date_key", "date", "year", "month_num", "month_name", "day_of_month",
               "day_of_week", "day_of_week_num", "is_weekend", "holiday"]]
    dim.to_csv(config.DATA_PROCESSED / "dim_date.csv", index=False)

    # --- summary -----------------------------------------------------------
    print(f"home dates:            {len(out):,}")
    print(f"  with a giveaway:     {int(out['has_giveaway'].sum()):,}")
    print(f"  clubs:               {out['team_id'].nunique()}")
    print(f"  homestands:          {out['homestand_id'].nunique():,}")
    print(f"  median homestand:    {out.groupby('homestand_id').size().median():.0f} dates")
    print()
    print("by season:")
    for season, block in out.groupby("season"):
        elig = block[block["analysis_eligible"] == 1]
        print(f"  {season}  dates {len(block):>5,}   giveaways {int(block['has_giveaway'].sum()):>4,}"
              f"   eligible clubs {elig['team_id'].nunique():>3}"
              f"   eligible giveaways {int(elig['has_giveaway'].sum()):>4,}")
    print()
    elig = out[out["analysis_eligible"] == 1]
    print("analysis-eligible (full-season release for that club-season):")
    print(f"  home dates:          {len(elig):,}")
    print(f"  with a giveaway:     {int(elig['has_giveaway'].sum()):,}"
          f"  ({elig['has_giveaway'].mean():.1%})")
    print(f"  club-seasons:        {elig.groupby(['team_id','season']).ngroups}")
    print()
    print("  midweek (Tue-Thu) giveaways, the displacement subsample:")
    mid = elig[elig["day_of_week"].isin(["Tuesday", "Wednesday", "Thursday"])]
    print(f"    treated {int(mid['has_giveaway'].sum()):,} of {len(mid):,} midweek dates")
    print()
    print(f"-> {out_path.relative_to(config.PROJECT_ROOT)}")
    print(f"-> {(config.DATA_PROCESSED / 'dim_date.csv').relative_to(config.PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
