# Power BI Setup

Power BI Desktop has no ARM64 build, so on Apple Silicon it runs under x64
emulation inside Parallels. Parallels documents an "Error fetching data for
this visual" failure on ARM, and community reports concentrate it in
**date-based visuals**. Everything below is arranged so the report never asks
Power BI to compute a date.

## 1. Install

In the Windows VM, download `PBIDesktopSetup_x64.exe` from Microsoft and
install. If visuals error out, reinstall with the 32-bit `PBIDesktopSetup.exe` —
Parallels recommends this specifically as the ARM workaround.

You do **not** need to sign in. A Microsoft account is required only to publish
to the Power BI service, which needs a work or school email and is not part of
this project. Building and saving a `.pbix` works signed out.

## 2. Before loading anything

**File > Options and settings > Options > Data Load > untick "Auto date/time".**

Do this first. That setting generates a hidden date hierarchy table for every
date column in the model, which is what appears to trigger the emulation bug,
and it bloats the file. The model has a proper date dimension instead.

## 3. Connect to the data

Parallels shares the Mac home directory into Windows, so no copying is needed:

```
\\Mac\Home\Projects\milb-promotion-incrementality\data\processed\bi\
```

Get Data > Text/CSV, and load all four:

| Table | Grain |
|---|---|
| `fct_home_date` | one row per club home date — the fact table |
| `dim_club` | one row per club |
| `dim_date` | one row per calendar day |
| `fct_model_result` | estimated effects with confidence intervals |

Re-running the pipeline on the Mac and hitting Refresh in Power BI picks up new
data. No re-import.

## 4. Model relationships

In Model view, create:

- `fct_home_date[date_key]` → `dim_date[date_key]` (many-to-one, single)
- `fct_home_date[team_id]` → `dim_club[team_id]` (many-to-one, single)

`fct_model_result` stays unrelated — it is a standalone results table.

Set `dim_date` as the date table if prompted, marking `date_key` as the key.
Do **not** create a relationship on the text `date` column.

## 5. Measures

Only four are needed, and none use time intelligence.

```DAX
Total Attendance   = SUM(fct_home_date[attendance])
Avg Attendance     = AVERAGE(fct_home_date[attendance])
Home Dates         = COUNTROWS(fct_home_date)
Avg vs Expected %  = AVERAGE(fct_home_date[vs_expected_pct])
```

Avoid `DATEADD`, `SAMEPERIODLASTYEAR`, `TOTALYTD` and similar — any
period-over-period comparison is already a column in the fact table.

## 6. The four pages

**Page 1 — What drives attendance.** Bar of `Avg Attendance` by
`dim_date[day_of_week]` (sort by `day_of_week_num`, not alphabetically). Bar by
`weather_group` and by `temp_band`. Line by `month_name`. This is the baseline
the whole study rests on, and it is the page that shows the model is sensible.

**Page 2 — The giveaway effect.** `Avg vs Expected %` by `giveaway_label`.
Column chart from `fct_model_result` filtered to "Lift by night", with `n` on
tooltip. Card showing the pooled +4.6%.

**Page 3 — Robustness.** Where this project separates itself. Plot
`fct_model_result` for "Position in homestand", both scopes side by side, so the
day-before effect visibly appears in one and vanishes in the other. Use the
`reliable` and `note` fields to flag Saturday as unvalidated. Most portfolio
dashboards show only what worked; this page shows what was tested and discarded.

**Page 4 — Club view.** Table from `dim_club`: club, home dates, mean
attendance, giveaways, giveaway rate, `coverage_label`. Slicer on
`analysis_eligible`. Makes the data-quality limitation visible rather than
buried in a footnote.

## 7. Saving

Save as `powerbi/milb_promotions.pbix` inside the repo, on the Mac side through
the Parallels share, so it is version-controlled with everything else. Export
each page as PNG into `reports/figures/` for the README.
