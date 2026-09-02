-- ---------------------------------------------------------------------------
-- Star schema, rebuilt in SQL.
--
-- The interesting piece is homestand reconstruction. A homestand is a run of
-- home dates uninterrupted by a road game; off-days inside it do not break it.
-- That is a gaps-and-islands problem, solved here with LAG to detect where a
-- run starts and a running SUM to number the runs.
-- ---------------------------------------------------------------------------

DROP VIEW IF EXISTS v_home_date;
DROP VIEW IF EXISTS v_team_timeline;
DROP VIEW IF EXISTS v_homestand;
DROP VIEW IF EXISTS v_home_date_treated;
DROP VIEW IF EXISTS v_giveaway_offset;
DROP VIEW IF EXISTS fct_home_date;
DROP VIEW IF EXISTS dim_club;

-- 1. Collapse played games to one row per club home date.
--    Doubleheaders book the whole gate to one game of the pair, so attendance
--    is summed across the date rather than averaged.
CREATE VIEW v_home_date AS
WITH ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY home_team_id, season, date
                              ORDER BY row_ord) AS rn
    FROM game
    WHERE status IN ('Final','Completed Early')
)
SELECT
    g.home_team_id                        AS team_id,
    g.season,
    g.date,
    CAST(REPLACE(g.date,'-','') AS INTEGER) AS date_key,
    SUM(g.attendance)                     AS attendance,
    COUNT(*)                              AS games_that_date,
    MAX(CASE WHEN g.rn = 1 THEN g.home_team END)                      AS home_team,
    MAX(CASE WHEN g.rn = 1 THEN g.league_name END)                    AS league_name,
    MAX(CASE WHEN g.rn = 1 THEN g.venue_name END)                     AS venue_name,
    MAX(CASE WHEN g.rn = 1 THEN g.away_team_id END)                   AS away_team_id,
    MAX(CASE WHEN g.rn = 1 THEN g.day_night END)                      AS day_night,
    MAX(g.home_wins)                      AS home_wins,
    MAX(g.home_losses)                    AS home_losses,
    MAX(g.away_wins)                      AS away_wins,
    MAX(g.away_losses)                    AS away_losses,
    MAX(CASE WHEN g.rn = 1 THEN g.weather_condition END)              AS weather_condition,
    MAX(CASE WHEN g.rn = 1 THEN g.weather_wind END)                   AS weather_wind,
    MAX(CASE WHEN g.rn = 1 THEN g.weather_temp_f END) AS temp_f
FROM ranked g
GROUP BY g.home_team_id, g.season, g.date
HAVING SUM(g.attendance) > 0;

-- 2. Every date each club appeared, home or away. The away rows are never
--    analysed; they exist only to break homestands.
CREATE VIEW v_team_timeline AS
SELECT season, team_id, date, MAX(is_home) AS is_home
FROM (
    SELECT season, home_team_id AS team_id, date, 1 AS is_home FROM schedule_slot
    UNION ALL
    SELECT season, away_team_id AS team_id, date, 0 AS is_home FROM schedule_slot
)
GROUP BY season, team_id, date;

-- 3. Gaps and islands. A new homestand starts at any home date whose previous
--    appearance was a road date (or which is the club's first date of the
--    season). Numbering the starts with a running SUM labels each run.
CREATE VIEW v_homestand AS
WITH flagged AS (
    SELECT
        season, team_id, date, is_home,
        LAG(is_home) OVER (PARTITION BY season, team_id ORDER BY date) AS prev_is_home
    FROM v_team_timeline
),
starts AS (
    SELECT *,
        CASE WHEN is_home = 1 AND (prev_is_home IS NULL OR prev_is_home = 0)
             THEN 1 ELSE 0 END AS is_stand_start
    FROM flagged
),
numbered AS (
    SELECT *,
        SUM(is_stand_start) OVER (
            PARTITION BY season, team_id ORDER BY date
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS stand_seq
    FROM starts
)
SELECT
    season, team_id, date,
    season || '-' || team_id || '-' || stand_seq AS homestand_id,
    ROW_NUMBER() OVER (PARTITION BY season, team_id, stand_seq ORDER BY date) AS homestand_game_index,
    COUNT(*)    OVER (PARTITION BY season, team_id, stand_seq)                AS homestand_length
FROM numbered
WHERE is_home = 1;

-- 4. Attach treatment. giveaway_count matters because a date can carry two
--    published items; has_giveaway is the treatment indicator.
CREATE VIEW v_home_date_treated AS
SELECT
    hd.*,
    hs.homestand_id,
    hs.homestand_game_index,
    hs.homestand_length,
    COALESCE(gv.giveaway_count, 0)                        AS giveaway_count,
    CASE WHEN gv.giveaway_count > 0 THEN 1 ELSE 0 END     AS has_giveaway,
    gv.giveaway_item,
    COALESCE(cs.analysis_eligible, 0)                     AS analysis_eligible,
    COALESCE(cs.coverage, 'no_source_found')              AS club_coverage
FROM v_home_date hd
LEFT JOIN v_homestand hs
       ON hs.team_id = hd.team_id AND hs.season = hd.season AND hs.date = hd.date
LEFT JOIN (
    SELECT team_id, date,
           COUNT(*)                       AS giveaway_count,
           GROUP_CONCAT(item, ' | ')      AS giveaway_item
    FROM giveaway
    WHERE date IS NOT NULL
    GROUP BY team_id, date
) gv ON gv.team_id = hd.team_id AND gv.date = hd.date
LEFT JOIN club_season_coverage cs
       ON cs.team_id = hd.team_id AND cs.season = hd.season;

-- 4b. Signed distance in home dates to the nearest giveaway in the same
--     homestand. Every date is paired with every treated date in its homestand,
--     then ROW_NUMBER picks the closest. Ties resolve to the earlier giveaway,
--     matching the Python implementation's argmin.
CREATE VIEW v_giveaway_offset AS
WITH treated AS (
    SELECT homestand_id, homestand_game_index
    FROM v_home_date_treated
    WHERE has_giveaway = 1
),
paired AS (
    SELECT
        d.team_id,
        d.date,
        d.homestand_game_index - t.homestand_game_index AS games_from_giveaway,
        ROW_NUMBER() OVER (
            PARTITION BY d.team_id, d.date
            ORDER BY ABS(d.homestand_game_index - t.homestand_game_index),
                     t.homestand_game_index
        ) AS rn
    FROM v_home_date_treated d
    JOIN treated t ON t.homestand_id = d.homestand_id
)
SELECT team_id, date, games_from_giveaway
FROM paired
WHERE rn = 1;

-- 5. The fact table. games_from_giveaway is the signed distance in home dates
--    to the nearest giveaway inside the same homestand - the column the
--    displacement test is built on. Ties resolve to the earlier giveaway,
--    matching the Python implementation.
CREATE VIEW fct_home_date AS
SELECT
    t.date_key,
    t.season,
    t.team_id,
    t.away_team_id,
    t.attendance,
    t.games_that_date,
    t.day_night,
    t.homestand_id,
    t.homestand_game_index,
    t.homestand_length,
    -- Gap to the club's previous PLAYED home date, so a cancelled game does
    -- not count as a date the club was in town.
    CAST(julianday(t.date) - julianday(
        LAG(t.date) OVER (PARTITION BY t.team_id, t.season ORDER BY t.date)
    ) AS INTEGER) AS days_since_last_home_date,
    -- SQLite rounds half away from zero; numpy rounds half to even. 81 of the
    -- ~6,200 win-percentage cells land on an exact half and differ in the third
    -- decimal from the pandas copy. Immaterial here: these columns are display
    -- only, and the model was fitted on unrounded values in Python.
    ROUND(CAST(t.home_wins AS REAL) / NULLIF(t.home_wins + t.home_losses, 0), 3) AS home_win_pct,
    ROUND(CAST(t.away_wins AS REAL) / NULLIF(t.away_wins + t.away_losses, 0), 3) AS away_win_pct,
    d.day_of_week,
    d.day_of_week_num,
    d.month_name,
    d.month_num,
    d.is_weekend,
    d.holiday,
    CASE WHEN d.holiday IS NOT NULL AND d.holiday <> '' THEN 1 ELSE 0 END AS is_holiday,
    -- Week 1 is the opening week of each season, not of the panel.
    CAST((julianday(t.date)
          - MIN(julianday(t.date)) OVER (PARTITION BY t.season)) / 7 AS INTEGER) + 1
        AS week_of_season,
    t.weather_condition,
    CASE
        WHEN t.weather_condition IN ('Sunny','Clear')                   THEN 'Clear'
        WHEN t.weather_condition IN ('Partly Cloudy','Cloudy','Overcast') THEN 'Cloudy'
        WHEN t.weather_condition IN ('Rain','Drizzle','Snow')           THEN 'Precipitation'
        ELSE 'Unknown'
    END AS weather_group,
    CASE WHEN t.weather_condition IN ('Rain','Drizzle','Snow') THEN 1 ELSE 0 END AS is_wet,
    t.temp_f,
    -- weather_wind arrives as e.g. "7 mph, L To R"; take the leading integer.
    CAST(NULLIF(SUBSTR(t.weather_wind, 1, INSTR(t.weather_wind || ' ', ' ') - 1), '') AS REAL)
        AS wind_mph,
    CASE
        WHEN t.temp_f IS NULL   THEN NULL
        WHEN t.temp_f <= 55     THEN 'Under 55F'
        WHEN t.temp_f <= 65     THEN '55-65F'
        WHEN t.temp_f <= 75     THEN '65-75F'
        WHEN t.temp_f <= 85     THEN '75-85F'
        ELSE '85F+'
    END AS temp_band,
    -- Power BI sorts text alphabetically, which would put "Under 55F" last.
    -- Ship an explicit sort key so the axis reads cold to hot.
    CASE
        WHEN t.temp_f IS NULL THEN NULL
        WHEN t.temp_f <= 55   THEN 0
        WHEN t.temp_f <= 65   THEN 1
        WHEN t.temp_f <= 75   THEN 2
        WHEN t.temp_f <= 85   THEN 3
        ELSE 4
    END AS temp_band_num,
    CASE WHEN t.has_giveaway = 1 THEN 'Giveaway' ELSE 'No giveaway' END AS giveaway_label,
    t.has_giveaway,
    t.giveaway_count,
    t.giveaway_item,
    t.analysis_eligible,
    MAX(t.has_giveaway) OVER (PARTITION BY t.homestand_id) AS homestand_has_giveaway,
    off.games_from_giveaway,
    ROUND(r.predicted_attendance) AS predicted_attendance,
    ROUND(r.residual, 4) AS residual,
    ROUND(t.attendance - r.predicted_attendance) AS vs_expected,
    CASE WHEN r.predicted_attendance IS NOT NULL
         THEN ROUND((CAST(t.attendance AS REAL) / r.predicted_attendance - 1) * 100, 2) END
        AS vs_expected_pct,
    -- Three-way status for the control-group chart. A date merely lacking a
    -- giveaway is not a clean control: if it sits beside one in the same
    -- homestand it may be contaminated by it.
    CASE WHEN t.has_giveaway = 1                    THEN 'Giveaway'
         WHEN off.games_from_giveaway IS NULL       THEN 'Clean control'
         ELSE 'Adjacent to a giveaway' END          AS control_status,
    CASE WHEN t.has_giveaway = 1                    THEN 0
         WHEN off.games_from_giveaway IS NULL       THEN 2
         ELSE 1 END                                 AS control_status_order,
    CASE WHEN off.games_from_giveaway IS NULL       THEN 'No giveaway in homestand'
         WHEN off.games_from_giveaway = 0           THEN 'Giveaway'
         WHEN ABS(off.games_from_giveaway) <= 2
              THEN (CASE WHEN off.games_from_giveaway > 0 THEN '+' ELSE '-' END)
                   || ABS(off.games_from_giveaway) || ' games'
         ELSE '3+ away' END                         AS offset_label
FROM v_home_date_treated t
LEFT JOIN v_giveaway_offset off
       ON off.team_id = t.team_id AND off.date = t.date
LEFT JOIN dim_date d
       ON d.date_key = t.date_key
LEFT JOIN model_residual r
       ON r.date_key = t.date_key AND r.team_id = t.team_id;

-- 6. Club dimension. One row per club, labelled with its most recent name -
--    Oklahoma City rebranded mid-panel, so grouping by name would emit two
--    rows for one club and break the relationship to the fact table.
CREATE VIEW dim_club AS
WITH latest AS (
    SELECT team_id, home_team, league_name,
           ROW_NUMBER() OVER (PARTITION BY team_id ORDER BY season DESC) AS rn
    FROM (SELECT DISTINCT team_id, season, home_team, league_name FROM v_home_date)
),
agg AS (
    SELECT
        team_id,
        COUNT(*)                       AS home_dates,
        ROUND(AVG(attendance))         AS mean_attendance,
        MAX(attendance)                AS max_attendance,
        COUNT(DISTINCT venue_name)     AS venues_used
    FROM v_home_date
    GROUP BY team_id
),
-- A club's primary park. Iowa hosted one game at the Field of Dreams site, so
-- the club must not be keyed on venue; the most-used park labels it instead.
-- Ties break alphabetically, matching pandas' mode().
venue AS (
    SELECT team_id, venue_name,
           ROW_NUMBER() OVER (PARTITION BY team_id
                              ORDER BY COUNT(*) DESC, venue_name) AS rn
    FROM v_home_date
    GROUP BY team_id, venue_name
),
gv AS (
    SELECT team_id, SUM(has_giveaway) AS giveaways
    FROM v_home_date_treated GROUP BY team_id
),
cov AS (
    SELECT team_id,
           SUM(analysis_eligible)                       AS eligible_seasons,
           COUNT(*)                                     AS seasons_observed
    FROM club_season_coverage GROUP BY team_id
)
SELECT
    a.team_id,
    l.home_team  AS club,
    l.league_name AS league,
    a.home_dates,
    a.mean_attendance,
    a.max_attendance,
    COALESCE(g.giveaways, 0) AS giveaways,
    v.venue_name             AS primary_venue,
    a.venues_used,
    CAST(COALESCE(g.giveaways, 0) AS REAL) / a.home_dates AS giveaway_rate,
    COALESCE(c.eligible_seasons, 0) AS eligible_seasons,
    COALESCE(c.seasons_observed, 0) AS seasons_observed,
    CASE
        WHEN COALESCE(c.eligible_seasons,0) = (SELECT COUNT(DISTINCT season) FROM game)
             THEN 'Complete, every season'
        WHEN COALESCE(c.eligible_seasons,0) > 0 THEN 'Complete in some seasons'
        ELSE 'Never complete'
    END AS coverage_label,
    CASE WHEN COALESCE(c.eligible_seasons,0) > 0 THEN 1 ELSE 0 END AS analysis_eligible
FROM agg a
JOIN latest l ON l.team_id = a.team_id AND l.rn = 1
JOIN venue  v ON v.team_id = a.team_id AND v.rn = 1
LEFT JOIN gv  g ON g.team_id = a.team_id
LEFT JOIN cov c ON c.team_id = a.team_id;
