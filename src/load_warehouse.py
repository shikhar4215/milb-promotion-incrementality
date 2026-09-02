"""
Build the SQLite warehouse and rebuild the star schema in SQL.

The Python pipeline stays the source of the statistical model - OLS belongs in
statsmodels, not in SQL - but the star schema the dashboard reads is built here
by SQL views over the loaded tables. `validate_warehouse.py` then checks the SQL
output against the pandas output row by row; the SQL is only worth shipping if
the two agree.

Usage
-----
    python3 src/load_warehouse.py
"""

from __future__ import annotations

import sqlite3

import pandas as pd

import config

DB_PATH = config.PROJECT_ROOT / "data" / "warehouse" / "milb.db"
BI_OUT = config.DATA_PROCESSED / "bi"          # what Power BI reads - built by SQL
BI_REF = config.DATA_PROCESSED / "bi_reference"  # pandas copy, kept for validation
SQL_DIR = config.PROJECT_ROOT / "sql"
SEASONS = (2024, 2025, 2026)


def run_script(conn: sqlite3.Connection, name: str) -> None:
    conn.executescript((SQL_DIR / name).read_text())


def load(conn: sqlite3.Connection) -> None:
    games = pd.read_csv(config.DATA_INTERIM / "games_raw.csv")
    games["row_ord"] = range(len(games))
    games[[
        "row_ord", "game_pk", "season", "date", "status", "day_night",
        "home_team_id", "home_team", "away_team_id", "away_team",
        "league_name", "venue_name", "attendance",
        "home_wins", "home_losses", "away_wins", "away_losses",
        "weather_condition", "weather_temp_f", "weather_wind",
    ]].to_sql("game", conn, if_exists="append", index=False)

    sched = pd.read_csv(config.DATA_INTERIM / "schedule.csv")
    sched[["game_pk", "season", "date", "status",
           "home_team_id", "away_team_id"]].to_sql(
        "schedule_slot", conn, if_exists="append", index=False)

    frames = []
    for year in SEASONS:
        g = pd.read_csv(config.PROJECT_ROOT / f"data/reference/giveaways_{year}.csv")
        g["season"] = year
        frames.append(g[["season", "team_id", "club", "date",
                         "item", "coverage", "source_url"]])
    pd.concat(frames, ignore_index=True).to_sql(
        "giveaway", conn, if_exists="append", index=False)

    resid = pd.read_csv(config.DATA_PROCESSED / "games_with_residuals_eligible.csv")
    resid[["date_key", "team_id", "predicted_attendance", "residual"]].to_sql(
        "model_residual", conn, if_exists="append", index=False)

    pd.read_csv(config.DATA_PROCESSED / "bi" / "fct_model_result.csv").to_sql(
        "model_result", conn, if_exists="append", index=False)

    pd.read_csv(config.DATA_PROCESSED / "dim_date.csv").to_sql(
        "dim_date", conn, if_exists="append", index=False)

    # Coverage is graded per club-season upstream; the warehouse stores the
    # verdict rather than re-deriving the rules in SQL.
    src = pd.read_csv(config.DATA_PROCESSED / "games_analysis.csv")
    cs = (src.drop_duplicates(["team_id", "season"])
             [["team_id", "season", "club_coverage"]]
             .rename(columns={"club_coverage": "coverage"}))
    cs["analysis_eligible"] = (cs["coverage"] == "full_season_release").astype(int)
    cs.to_sql("club_season_coverage", conn, if_exists="append", index=False)


def export_bi(conn: sqlite3.Connection) -> None:
    """
    Write the star schema Power BI reads, straight out of the SQL views.

    Row order is team_id then date_key - deterministic, but not the same order
    the pandas reference happens to write. Row order in a CSV feeding a BI tool
    carries no meaning, and the validator sorts on keys before comparing.

    Column order is taken from the pandas reference copy when it exists.
    Power Query pins column names and positions at import, so emitting them in a
    different order would break every visual on refresh - the SQL being correct
    is not enough, it has to be correct in the same shape.
    """
    BI_OUT.mkdir(parents=True, exist_ok=True)
    for name, query in [
        ("fct_home_date",    "SELECT * FROM fct_home_date ORDER BY team_id, date_key"),
        ("dim_club",         "SELECT * FROM dim_club ORDER BY team_id"),
        ("dim_date",         "SELECT * FROM dim_date"),
        ("fct_model_result", "SELECT * FROM model_result"),
    ]:
        df = pd.read_sql(query, conn)
        ref = BI_REF / f"{name}.csv"
        if ref.exists():
            ref_df = pd.read_csv(ref)
            order = ref_df.columns.tolist()
            missing = [c for c in order if c not in df.columns]
            if missing:
                raise SystemExit(
                    f"{name}: SQL output is missing column(s) {missing} that the "
                    f"dashboard expects. Refusing to write a table that would "
                    f"break the report."
                )
            df = df[order + [c for c in df.columns if c not in order]]
            # SQLite hands back every number as a float, so a whole-number column
            # would serialise as "4995.0". Power Query types columns on import,
            # and a column that arrives decimal instead of whole changes how the
            # cards render. Match the reference dtypes exactly.
            for col in order:
                if col not in df.columns:
                    continue
                if pd.api.types.is_integer_dtype(ref_df[col]):
                    df[col] = df[col].astype("Int64")
                elif pd.api.types.is_float_dtype(ref_df[col]):
                    df[col] = df[col].astype(float)
        df.to_csv(BI_OUT / f"{name}.csv", index=False)
        print(f"   {name:<20} {len(df):>7,} rows  {len(df.columns):>3} cols -> bi/")


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    run_script(conn, "01_schema.sql")
    load(conn)
    run_script(conn, "02_views.sql")
    conn.commit()

    print(f"-> {DB_PATH.relative_to(config.PROJECT_ROOT)}")
    for table in ("game", "schedule_slot", "giveaway", "model_residual",
                  "model_result", "dim_date", "club_season_coverage"):
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"   {table:<22} {n:>7,} rows")
    for view in ("v_home_date", "v_homestand", "v_giveaway_offset",
                 "fct_home_date", "dim_club"):
        n = conn.execute(f"SELECT COUNT(*) FROM {view}").fetchone()[0]
        print(f"   {view:<22} {n:>7,} rows  (view)")

    print()
    export_bi(conn)
    conn.close()


if __name__ == "__main__":
    main()
