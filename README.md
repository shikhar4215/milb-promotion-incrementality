# Do Minor League Giveaways Create Attendance, or Just Move It?

A causal analysis of promotional giveaways across all 30 Triple-A baseball clubs,
using game-level attendance, ballpark weather, and hand-verified promotional calendars.

**Status: analysis complete, dashboard in progress.**

**Headline:** giveaways add roughly **5%** to a Triple-A crowd — a few hundred fans on a
gate of about 6,000, far below how promotions are usually described.

**The question this project set out to answer could not be answered with one season,
and the write-up says so.** The displacement result appeared, survived one
specification, and collapsed under another. Section [What the data does not
support](#what-the-data-does-not-support) explains exactly why, and what would fix it.

---

## The question

A bobblehead night draws 8,000 fans instead of the usual 5,000. The promotion "worked" —
that is how it gets reported, and it is the number most analyses stop at.

But if the two games on either side of it run 1,000 short of their own baselines, the
club did not create 3,000 fans. It moved them. Same customers, same wallets, different
night, minus the cost of 3,000 bobbleheads.

This project set out to separate the two:

- **Lift** — how much larger is the crowd than that date should have drawn, given the
  opponent, day of week, weather, and time of season?
- **Displacement** — do the surrounding games in the same homestand come in *below*
  their own baselines?

**It measured the first and could not establish the second.** That is the honest
result, and the reason is specific rather than a shrug: giveaways are scheduled on
Saturdays, homestands run Tuesday to Sunday, so "the day before a giveaway" is largely
a synonym for "Friday". Position in a homestand and day of week are close to the same
variable, and one season contains no leverage to separate them.

## Data

| Source | What it provides | Coverage |
|---|---|---|
| [MLB Stats API](https://statsapi.mlb.com) | Game logs, attendance, ballpark weather at first pitch | 2,250 games, 2026 season |
| Club press releases (milb.com, OurSports Central) | Dated giveaway calendars | 312 giveaways, 28 of 30 clubs |

Attendance and weather arrive in the same API record, so weather is the reading taken
at the ballpark at first pitch rather than a nearby-station proxy. The API is free and
needs no key. Verified working back to 2012.

**2026 season, after cleaning:** 1,958 games played, 96.5% carrying attendance, 100%
carrying weather. Median crowd 5,189 (632–13,675).

## Results

### What the data supports

| Specification | Effect on the giveaway date | 95% CI |
|---|---|---|
| League baseline, 17 complete-coverage clubs | **+4.6%** | [+0.5, +8.9] |
| League baseline, 28 clubs incl. incomplete | +6.1% | [+2.3, +10.0] |
| Within-homestand fixed effects | +8.3% | [−0.7, +18.1] |

Consistent in direction across every specification, and the placebo test supports it:
400 fake giveaway sets matched on weekday produce a mean effect of −0.9%, against an
observed +4.6%.

In fans, that is roughly **280 extra people on a 6,073 baseline**. Real, and much
smaller than the folklore.

![Giveaway effect by night](reports/figures/fig2_lift_by_night.png)

### What the data does not support

Displacement. The estimates are not robust across specification:

| Position | League baseline | Within-homestand |
|---|---|---|
| Day before | −6.6% [−11.2, −1.9] | +0.2% (p=0.97) |
| Giveaway | +4.6% [+0.5, +8.9] | +8.3% (p=0.07) |
| Day after | +5.7% [−0.6, +12.4] | +9.0% (p=0.07) |

A significant dip the day before disappears entirely under homestand fixed effects.
When a result flips that hard on a defensible change of specification, the result is
the specification, not the world.

![Specification check](reports/figures/fig3_specification_check.png)

### The structural finding

The reason both questions are hard is the same, and it is worth more than either answer
would have been: **promotional scheduling is so concentrated that the counterfactual
barely exists.** 79 of 129 eligible Saturdays carried a giveaway. Nashville and Sugar
Land ran one on *every* home Saturday. There are fewer giveaway-free Saturdays in the
league-season than there are treated ones.

![Scheduling concentration](reports/figures/fig4_scheduling_concentration.png)

### What actually drives attendance

Before any promotion is involved: night of the week dominates, temperature matters and
peaks at 75-85°F, and conditions barely register once temperature is known.

![Attendance drivers](reports/figures/fig1_attendance_drivers.png)

## Design decisions

Each of these came out of something the data actually did.

**The unit of analysis is a home date, not a game.** 68 played games report attendance
of exactly zero, and every one is a doubleheader. Baseball books the entire gate to one
game of the pair. Since fans buy one ticket for a doubleheader and promotions are
advertised per date, the date is the honest unit. This yields **1,889 observations**.

**Postponed games are returned twice.** A game rained out and made up as part of a
doubleheader comes back under the same `gamePk` twice — once as `Postponed`, once as the
completed makeup. 90 such rows in 2026. Left alone they would have been double-counted.

**Giveaways only, not all promotions.** Giveaways are published as clean dated items,
have a real per-unit cost, and are where the displacement question actually bites.
Fireworks are mostly recurring Friday events and are confounded with day of week; theme
nights are buried in prose and extract unreliably.

**The counterfactual is estimated within 2026.** Attendance history back to 2012 is
available, but those seasons had promotions too — unobserved. A baseline trained on them
would absorb promotional attendance into "normal" and bias every lift estimate toward
zero.

**Nine giveaway dates were dropped, not repaired.** They land on dates with no home
game. Three are clearly off-by-one on homestand openers, and shifting them by a day
would fit — but inferring a treatment date is inventing treatment assignment.

## Known limitations

Stated plainly because they bound what the results can claim.

- **Coverage is uneven.** 17 clubs published season-wide giveaway calendars; 11 did not,
  and their data is stitched from individual homestand previews and is knowably
  incomplete. An unobserved giveaway gets coded as a control date, which contaminates the
  counterfactual and biases lift *downward*. Headline results run on the 17 complete
  clubs; the rest are a reported sensitivity check.
- **One season.** A 2026-specific effect cannot be separated from a stable one.
- **Season incomplete.** 35 giveaways fall on September dates not yet played.
- **No pricing or cost data.** This measures attendance, not profit.
- **Announced attendance is tickets distributed, not turnstile count.** Standard in
  baseball attendance work, and worth stating rather than burying.

See [`docs/data-sources.md`](docs/data-sources.md) for every source evaluated, including
the ones that failed, and [`docs/giveaway-data-quality.md`](docs/giveaway-data-quality.md)
for the full defect log.

## Repository

```
data/
  raw/          API responses and club pages (regenerated by scripts, not committed)
  reference/    giveaways_2026.csv - hand-verified, every row carries its source URL
  processed/    analysis-ready tables
src/
  config.py               paths, league filters, study constants
  extract_games.py        resumable two-pass extractor for game logs and attendance
  fetch_promo_pages.py    club promotions page downloader
  validate_giveaways.py   joins giveaways to the schedule, reports defects
docs/           source evaluation and data quality
notebooks/      exploratory analysis
powerbi/        dashboard
reports/        validation output and figures
```

## Reproducing

```bash
git clone https://github.com/Shikhar4215/milb-promotion-incrementality.git
cd milb-promotion-incrementality

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python3 src/extract_games.py --seasons 2026   # ~2,250 games, ~15 min, resumable
python3 src/validate_giveaways.py             # data quality report
```

`extract_games.py` caches every game to disk and skips what it already has, so an
interrupted run resumes where it stopped.

## Roadmap

- [x] Source evaluation and feasibility
- [x] Game log, attendance and weather extraction
- [x] Giveaway calendar collection and date validation
- [x] Feature engineering: homestand structure, date dimension
- [x] Baseline attendance model (the counterfactual)
- [x] Lift and displacement estimation, with placebo and specification checks
- [ ] Power BI dashboard
- [ ] Recover 2024 and 2025 giveaway calendars — the extension that would make
      displacement estimable
