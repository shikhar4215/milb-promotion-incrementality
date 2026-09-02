# The SQL warehouse

The star schema Power BI reads is built by SQL, not pandas. `data/warehouse/milb.db`
is a SQLite database committed to the repo, so anyone who clones it can run every
query in this document without re-running the 45-minute extraction.

```bash
python3 src/load_warehouse.py       # build the database and export the star schema
python3 src/validate_warehouse.py   # check it against the pandas reference
```

## Why SQLite, and where the line sits

The model stays in Python. Fitting OLS with fixed effects, clustered standard errors
and a 400-draw placebo belongs in statsmodels; expressing it in SQL would be a stunt.
The warehouse holds the model's *output* — one predicted attendance and one residual
per club-date — and everything downstream of it is SQL.

That split is the honest one: SQL does the reshaping, joining and windowing it is good
at, and Python does the estimation it is good at.

## Schema

| Table | Grain | Notes |
|---|---|---|
| `game` | one played game | doubleheaders give two rows on one date |
| `schedule_slot` | one scheduled game, home and away | never analysed; it exists to define homestand boundaries |
| `giveaway` | one published giveaway item | a date can carry two |
| `model_residual` | one club-date | output of the Python baseline |
| `club_season_coverage` | one club-season | coverage is graded per season, not per club |
| `dim_date`, `model_result` | reference | loaded as-is |

Views build the star schema on top: `v_home_date` → `v_team_timeline` → `v_homestand`
→ `v_giveaway_offset` → `fct_home_date`, plus `dim_club`.

## The part worth reading: homestand reconstruction

A homestand is a run of home dates uninterrupted by a road game. Off-days inside it do
not break it — the club is still in town. A road trip does, which is what makes the
displacement test meaningful.

That is a **gaps-and-islands** problem. `LAG` finds every date whose previous
appearance was a road date; a running `SUM` over those flags numbers the runs:

```sql
LAG(is_home) OVER (PARTITION BY season, team_id ORDER BY date)  AS prev_is_home
...
SUM(is_stand_start) OVER (
    PARTITION BY season, team_id ORDER BY date
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
)                                                               AS stand_seq
```

`ROW_NUMBER()` then gives each date's position within its stand, and a second
`ROW_NUMBER()` in `v_giveaway_offset` picks the nearest giveaway to each date by pairing
every date with every treated date in its homestand and keeping the closest.

## Three bugs the validator caught

The warehouse was written to reproduce the pandas pipeline exactly, and it did not on
the first run. Each mismatch was a real defect, not a tolerance problem.

**A club can be listed both home and away on the same date** — 32 cases across the
panel. The pandas version deduplicated with home taking precedence; the first SQL
version used `UNION`, kept both rows, and the phantom road date split 545 dates into
the wrong homestands.

**`days_since_last_home_date` was computed over the wrong set.** The first version took
`LAG(date)` over the full timeline including road dates and cancelled games, so it
measured the gap to the club's last *appearance* rather than its last *played home
date*. 59 rows wrong.

**"First game of a doubleheader" was not well defined.** pandas takes the first row in
group order; SQL `MIN()` takes the smallest value, which for `day_night` means 'day'
beats 'night' regardless of which game came first. The fix was to load an explicit
`row_ord` column and rank on it — which also pins down behaviour that was previously
implicit in pandas' row ordering.

## One difference that remains, and why it is left

81 of roughly 6,200 win-percentage cells differ from the pandas copy in the third
decimal. SQLite rounds half away from zero; numpy rounds half to even. The columns are
display-only — the model was fitted on unrounded values — so the difference is reported
by the validator rather than hidden by a tolerance.

## Query library

`sql/03_analysis.sql` answers the project's questions directly against the warehouse.
Every query reproduces a number that appears in the write-up:

1. The headline: +9.53% on 577 treated dates, 535 extra fans on a 5,942 baseline
2. Stability across seasons: +10.49 / +10.29 / +7.89
3. Clean controls per treated date by night — Saturday at 0.56, every other night above 1.1
4. Displacement by position in the homestand: −1 sits at −0.21%, indistinguishable from zero
5. Clubs ranked by promotional intensity, with `RANK()`
6. Club-seasons that promoted *every* home Saturday — Nashville 2025, Sugar Land 2024,
   Jacksonville 2024, Scranton/Wilkes-Barre 2024. These are the clubs that leave no
   counterfactual behind, and they are why the Saturday estimate cannot be validated.

## Validation

`validate_warehouse.py` compares the SQL output against the pandas reference in
`data/processed/bi_reference/` column by column — 60 checks across both tables, plus a
recomputation of the headline entirely in SQL. It exits non-zero on any mismatch.

The export step also refuses to write a table that is missing a column the dashboard
expects, rather than emitting one that would break every visual on refresh.
