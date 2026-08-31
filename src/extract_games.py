"""
Extract Triple-A game logs, attendance and ballpark weather from the MLB Stats API.

Two passes:
  1. Season schedules  -> one request per season, gives the game list.
  2. Per-game detail    -> one request per game, gives attendance + weather.

Pass 2 is cached to disk, so the script is resumable. Interrupt it and re-run
and it picks up where it stopped.

Usage
-----
    python3 src/extract_games.py                     # every season in config
    python3 src/extract_games.py --seasons 2025 2026 # just those two
    python3 src/extract_games.py --limit 50          # smoke test
"""

from __future__ import annotations

import argparse
import json
import time
from typing import Any

import pandas as pd
import requests
from tqdm import tqdm

import config


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": config.USER_AGENT})


def get_json(url: str, params: dict | None = None) -> dict[str, Any]:
    """GET a URL and return parsed JSON, retrying with exponential backoff."""
    last_error: Exception | None = None

    for attempt in range(config.MAX_RETRIES):
        try:
            response = SESSION.get(url, params=params, timeout=config.REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # noqa: BLE001 - we want to retry on anything
            last_error = exc
            time.sleep(2 ** attempt)

    raise RuntimeError(f"Failed after {config.MAX_RETRIES} attempts: {url}") from last_error


# ---------------------------------------------------------------------------
# Pass 1: season schedules
# ---------------------------------------------------------------------------
def fetch_season_schedule(season: int, refresh: bool = False) -> dict[str, Any]:
    """Download one season's Triple-A schedule, caching the raw JSON."""
    cache_path = config.RAW_SCHEDULES / f"schedule_{season}.json"

    if cache_path.exists() and not refresh:
        return json.loads(cache_path.read_text())

    payload = get_json(
        f"{config.STATS_API}/v1/schedule",
        params={
            "sportId": config.SPORT_ID_TRIPLE_A,
            "season": season,
            "gameType": "R",           # regular season only
            "hydrate": "team,venue",   # needed for league id and venue name
        },
    )
    cache_path.write_text(json.dumps(payload))
    time.sleep(config.REQUEST_DELAY)
    return payload


def parse_schedule(payload: dict[str, Any], season: int) -> list[dict[str, Any]]:
    """Flatten a schedule payload into one row per game, keeping only AAA leagues."""
    rows: list[dict[str, Any]] = []

    for date_block in payload.get("dates", []):
        for game in date_block.get("games", []):
            home = game.get("teams", {}).get("home", {})
            away = game.get("teams", {}).get("away", {})
            home_team = home.get("team", {})
            away_team = away.get("team", {})
            league = home_team.get("league", {}) or {}

            # Drop the Mexican League and anything else unexpected.
            if league.get("id") not in config.KEEP_LEAGUE_IDS:
                continue

            home_record = home.get("leagueRecord", {}) or {}
            away_record = away.get("leagueRecord", {}) or {}

            rows.append({
                "game_pk": game.get("gamePk"),
                "season": season,
                "date": game.get("officialDate"),
                "game_type": game.get("gameType"),
                "status": (game.get("status") or {}).get("detailedState"),
                "day_night": game.get("dayNight"),
                "doubleheader": game.get("doubleHeader"),
                "game_number": game.get("gameNumber"),
                "series_game_number": game.get("seriesGameNumber"),
                "games_in_series": game.get("gamesInSeries"),
                "league_id": league.get("id"),
                "league_name": league.get("name"),
                "venue_id": (game.get("venue") or {}).get("id"),
                "venue_name": (game.get("venue") or {}).get("name"),
                "home_team_id": home_team.get("id"),
                "home_team": home_team.get("name"),
                "away_team_id": away_team.get("id"),
                "away_team": away_team.get("name"),
                "home_score": home.get("score"),
                "away_score": away.get("score"),
                "home_wins": home_record.get("wins"),
                "home_losses": home_record.get("losses"),
                "away_wins": away_record.get("wins"),
                "away_losses": away_record.get("losses"),
            })

    return rows


# ---------------------------------------------------------------------------
# Pass 2: per-game attendance and weather
# ---------------------------------------------------------------------------
DETAIL_FIELDS = (
    "gameData,datetime,officialDate,dayNight,"
    "weather,condition,temp,wind,"
    "gameInfo,attendance,firstPitch,gameDurationMinutes"
)


def fetch_game_detail(game_pk: int) -> dict[str, Any]:
    """Fetch attendance + weather for one game, caching the trimmed response."""
    cache_path = config.RAW_GAMES / f"{game_pk}.json"

    if cache_path.exists():
        return json.loads(cache_path.read_text())

    payload = get_json(
        f"{config.STATS_API}/v1.1/game/{game_pk}/feed/live",
        params={"fields": DETAIL_FIELDS},
    )

    game_data = payload.get("gameData", {}) or {}
    weather = game_data.get("weather", {}) or {}
    game_info = game_data.get("gameInfo", {}) or {}

    record = {
        "game_pk": game_pk,
        "attendance": game_info.get("attendance"),
        "first_pitch": game_info.get("firstPitch"),
        "game_duration_minutes": game_info.get("gameDurationMinutes"),
        "weather_condition": weather.get("condition"),
        "weather_temp_f": weather.get("temp"),
        "weather_wind": weather.get("wind"),
    }

    cache_path.write_text(json.dumps(record))
    time.sleep(config.REQUEST_DELAY)
    return record


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seasons", type=int, nargs="+", default=None,
                        help="Seasons to pull. Defaults to config.HISTORY_SEASONS.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Only fetch detail for the first N games (smoke test).")
    parser.add_argument("--refresh-schedules", action="store_true",
                        help="Re-download season schedules instead of using the cache.")
    args = parser.parse_args()

    config.ensure_dirs()

    seasons = args.seasons or config.HISTORY_SEASONS
    seasons = [s for s in seasons if s not in config.CANCELLED_SEASONS]

    # Pass 1 -----------------------------------------------------------------
    all_games: list[dict[str, Any]] = []
    for season in seasons:
        payload = fetch_season_schedule(season, refresh=args.refresh_schedules)
        rows = parse_schedule(payload, season)
        print(f"  {season}: {len(rows):>5} Triple-A games")
        all_games.extend(rows)

    schedule_df = pd.DataFrame(all_games)
    if schedule_df.empty:
        raise SystemExit("No games found. Check network access and season list.")

    schedule_path = config.DATA_INTERIM / "schedule.csv"
    schedule_df.to_csv(schedule_path, index=False)
    print(f"\nSchedule: {len(schedule_df):,} games -> {schedule_path.name}")

    # Pass 2 -----------------------------------------------------------------
    game_pks = schedule_df["game_pk"].dropna().astype(int).tolist()
    if args.limit:
        game_pks = game_pks[:args.limit]

    cached = sum(1 for pk in game_pks if (config.RAW_GAMES / f"{pk}.json").exists())
    print(f"Detail: {len(game_pks):,} games ({cached:,} already cached)\n")

    details = [fetch_game_detail(pk) for pk in tqdm(game_pks, desc="games", unit="game")]

    detail_df = pd.DataFrame(details)
    merged = schedule_df.merge(detail_df, on="game_pk", how="inner")

    out_path = config.DATA_INTERIM / "games_raw.csv"
    merged.to_csv(out_path, index=False)

    with_attendance = merged["attendance"].notna().sum()
    print(f"\nWrote {len(merged):,} rows -> {out_path}")
    print(f"Attendance present: {with_attendance:,} "
          f"({with_attendance / len(merged):.1%})")


if __name__ == "__main__":
    main()
