-- ---------------------------------------------------------------------------
-- Analytical queries. These answer the project's questions directly against the
-- warehouse, and each one reproduces a number that appears in the write-up.
-- Run them with:  sqlite3 data/warehouse/milb.db < sql/03_analysis.sql
-- ---------------------------------------------------------------------------

.mode column
.headers on

-- 1. The headline. Log-space mean, because the model predicts log(attendance):
--    averaging raw percentage gaps would overstate the effect (+9.5% vs +11.3%).
SELECT
    COUNT(*)                                    AS treated_dates,
    ROUND((EXP(AVG(residual)) - 1) * 100, 2)    AS effect_pct,
    ROUND(AVG(attendance - predicted_attendance)) AS extra_fans,
    ROUND(AVG(predicted_attendance))            AS baseline_crowd
FROM fct_home_date
WHERE analysis_eligible = 1 AND has_giveaway = 1;

-- 2. Stability across seasons. If the pooled estimate were driven by one year,
--    it would show here.
SELECT season,
       COUNT(*)                                 AS treated_dates,
       ROUND((EXP(AVG(residual)) - 1) * 100, 2) AS effect_pct
FROM fct_home_date
WHERE analysis_eligible = 1 AND has_giveaway = 1
GROUP BY season
ORDER BY season;

-- 3. The control-pool problem, which is the project's structural finding.
--    A clean control is a date with no giveaway anywhere in its homestand.
--    Saturday is the only night with fewer controls than treated dates.
SELECT
    d.day_of_week,
    SUM(CASE WHEN f.control_status = 'Giveaway'      THEN 1 ELSE 0 END) AS treated,
    SUM(CASE WHEN f.control_status = 'Clean control' THEN 1 ELSE 0 END) AS clean_controls,
    ROUND(
        CAST(SUM(CASE WHEN f.control_status = 'Clean control' THEN 1 ELSE 0 END) AS REAL)
        / NULLIF(SUM(CASE WHEN f.control_status = 'Giveaway' THEN 1 ELSE 0 END), 0), 2
    ) AS controls_per_treated
FROM fct_home_date f
JOIN dim_date d ON d.date_key = f.date_key
WHERE f.analysis_eligible = 1
GROUP BY d.day_of_week, d.day_of_week_num
ORDER BY d.day_of_week_num;

-- 4. Displacement. Position in the homestand relative to the nearest giveaway.
--    If promotions moved demand rather than creating it, -1 would sit clearly
--    below zero. It does not.
SELECT
    games_from_giveaway                          AS offset_games,
    COUNT(*)                                     AS n,
    ROUND((EXP(AVG(residual)) - 1) * 100, 2)     AS effect_pct
FROM fct_home_date
WHERE analysis_eligible = 1
  AND games_from_giveaway BETWEEN -4 AND 4
GROUP BY games_from_giveaway
ORDER BY games_from_giveaway;

-- 5. Which clubs the analysis can use, and how concentrated their promotions
--    are. RANK() is here because "who promotes hardest" is the natural
--    follow-up question a stakeholder asks.
SELECT
    c.club,
    c.eligible_seasons,
    c.home_dates,
    c.giveaways,
    ROUND(c.giveaway_rate * 100, 1)                                  AS pct_of_dates,
    RANK() OVER (ORDER BY c.giveaway_rate DESC)                      AS promo_intensity_rank
FROM dim_club c
WHERE c.eligible_seasons > 0
ORDER BY promo_intensity_rank
LIMIT 10;

-- 6. Saturday concentration by club-season: the clubs that leave no
--    counterfactual behind. A club promoting every home Saturday cannot
--    contribute a single untreated Saturday to the comparison.
SELECT
    c.club,
    f.season,
    COUNT(*)                                          AS home_saturdays,
    SUM(f.has_giveaway)                               AS with_giveaway,
    ROUND(100.0 * SUM(f.has_giveaway) / COUNT(*), 0)  AS pct_promoted
FROM fct_home_date f
JOIN dim_date  d ON d.date_key = f.date_key
JOIN dim_club  c ON c.team_id  = f.team_id
WHERE f.analysis_eligible = 1 AND d.day_of_week = 'Saturday'
GROUP BY c.club, f.season
HAVING pct_promoted = 100
ORDER BY home_saturdays DESC, c.club;
