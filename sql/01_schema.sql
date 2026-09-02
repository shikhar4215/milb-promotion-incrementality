-- Warehouse schema for the MiLB promotion study.
--
-- Grain notes, because they are the whole design:
--   game          one row per played game. Doubleheaders give two rows on one date.
--   schedule_slot every scheduled game, home and away, played or not. Needed to
--                 reconstruct homestands: a road game is what ends one, so the
--                 rows we never analyse are the rows that define the boundaries.
--   giveaway      one row per published giveaway item. A date can carry two.
--   model_residual  output of the Python OLS baseline, joined back in by key.

DROP TABLE IF EXISTS game;
CREATE TABLE game (
    game_pk            INTEGER PRIMARY KEY,
    row_ord            INTEGER NOT NULL,  -- load order; pins which game of a doubleheader is "first"
    season             INTEGER NOT NULL,
    date               TEXT    NOT NULL,
    status             TEXT,
    day_night          TEXT,
    home_team_id       INTEGER NOT NULL,
    home_team          TEXT,
    away_team_id       INTEGER,
    away_team          TEXT,
    league_name        TEXT,
    venue_name         TEXT,
    attendance         INTEGER,
    home_wins          INTEGER,
    home_losses        INTEGER,
    away_wins          INTEGER,
    away_losses        INTEGER,
    weather_condition  TEXT,
    weather_temp_f     REAL,
    weather_wind       TEXT
);

DROP TABLE IF EXISTS schedule_slot;
CREATE TABLE schedule_slot (
    game_pk       INTEGER PRIMARY KEY,
    season        INTEGER NOT NULL,
    date          TEXT    NOT NULL,
    status        TEXT,
    home_team_id  INTEGER NOT NULL,
    away_team_id  INTEGER NOT NULL
);

DROP TABLE IF EXISTS giveaway;
CREATE TABLE giveaway (
    giveaway_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    season       INTEGER NOT NULL,
    team_id      INTEGER NOT NULL,
    club         TEXT,
    date         TEXT,
    item         TEXT,
    coverage     TEXT,
    source_url   TEXT
);

DROP TABLE IF EXISTS model_residual;
CREATE TABLE model_residual (
    date_key              INTEGER NOT NULL,
    team_id               INTEGER NOT NULL,
    predicted_attendance  REAL,
    residual              REAL,
    PRIMARY KEY (date_key, team_id)
);

DROP TABLE IF EXISTS model_result;
CREATE TABLE model_result (
    analysis        TEXT,
    category        TEXT,
    n               INTEGER,
    effect_pct      REAL,
    ci_low          REAL,
    ci_high         REAL,
    excludes_zero   INTEGER,
    reliable        INTEGER,
    note            TEXT,
    category_order  INTEGER,
    scope           TEXT
);

DROP TABLE IF EXISTS dim_date;
CREATE TABLE dim_date (
    date_key        INTEGER PRIMARY KEY,
    date            TEXT NOT NULL,
    year            INTEGER,
    month_num       INTEGER,
    month_name      TEXT,
    day_of_month    INTEGER,
    day_of_week     TEXT,
    day_of_week_num INTEGER,
    is_weekend      INTEGER,
    holiday         TEXT
);

-- Coverage is graded per club-season, so this is the key the eligibility
-- filter joins on. Storing it once stops each query re-deriving it.
DROP TABLE IF EXISTS club_season_coverage;
CREATE TABLE club_season_coverage (
    team_id           INTEGER NOT NULL,
    season            INTEGER NOT NULL,
    coverage          TEXT,
    analysis_eligible INTEGER,
    PRIMARY KEY (team_id, season)
);

CREATE INDEX idx_game_home      ON game (home_team_id, date);
CREATE INDEX idx_game_season    ON game (season);
CREATE INDEX idx_slot_home      ON schedule_slot (season, home_team_id, date);
CREATE INDEX idx_slot_away      ON schedule_slot (season, away_team_id, date);
CREATE INDEX idx_giveaway_key   ON giveaway (team_id, date);
