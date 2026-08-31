# Giveaway Data Quality

The treatment variable in this study is "did this club hand out a physical item at
this home date". Everything downstream depends on it, so its defects are documented
here rather than discovered later.

Source data: `data/reference/giveaways_2026.csv` — 312 giveaways, 28 of 30 Triple-A
clubs, every row carrying the URL it came from.

## Coverage is not uniform

Clubs publish promotions inconsistently. Some issue one season-wide press release;
others announce homestand by homestand; two never pair an item with a date at all.

| Coverage | Clubs | Giveaways | Trust |
|---|---|---|---|
| `full_season_release` | 17 | 237 | Club published a season-wide schedule with dates |
| `partial_assembled` | 11 | 75 | Stitched from homestand previews — **known incomplete** |
| `no_source_found` | 2 | 0 | Norfolk Tides, Salt Lake Bees |

Durham shows 1 giveaway, Tacoma 2, Louisville 2. These are not promotion-light clubs;
they are clubs we cannot observe properly.

**Why this is dangerous.** A giveaway we fail to observe is recorded as an ordinary
date. That places treated dates inside the control group, contaminating the
counterfactual and biasing measured lift *downward*. The `coverage` column exists so
this is testable instead of invisible.

**Handling.** Estimate the headline result on `full_season_release` clubs only. Re-run
including `partial_assembled` as a sensitivity check and report both. The two
`no_source_found` clubs are excluded from the treatment analysis but still contribute
to the attendance baseline.

## Date validation

`src/validate_giveaways.py` joins every giveaway to the schedule and classifies it.

| Result | Count | Meaning |
|---|---|---|
| `usable` | 264 | Lands on a date the club played at home |
| `not_yet_played` | 35 | September games; season runs to 2026-09-20 |
| `game_did_not_happen` | 4 | Cancelled or suspended — no gate to measure |
| `unmatched_date` | 9 | No home game on that date at all |

### The unmatched nine

Verified against the raw API payload: these clubs genuinely had no home game on the
listed date. The parser was ruled out first — all 2,343 games are `gameType=R` in
leagues 117 and 112 only, so nothing was being silently filtered.

Three are off-by-one errors on homestand openers, and the pattern is consistent:

| Club | Listed | Actual home opener | Item |
|---|---|---|---|
| Rochester Red Wings | 2026-03-31 | 2026-04-01 | Winter Hat, Magnet Schedule |
| Scranton/Wilkes-Barre | 2026-04-07 | 2026-04-08 | Magnet Schedule |
| Lehigh Valley IronPigs | 2026-07-28 | 2026-07-29 | Knit Cap |

The rest (Nashville 4/4, Memphis 4/4, Lehigh Valley 4/25, Jacksonville 7/29,
Charlotte 8/28) fall on off-days inside an otherwise continuous homestand, most
likely announcements made against a schedule that was later revised.

**These dates are excluded, not corrected.** Shifting them a day would fit the
observed pattern, but inferring a treatment date is inventing treatment assignment —
the same objection that ruled out OCR on the promo PDFs. 9 of 312 rows, 2.9%.

## Other caveats carried from collection

- **Unnamed items on real dates.** Lehigh Valley 6/28, 8/15, 9/11 and Charlotte 8/9,
  Las Vegas 8/29 are dated giveaways whose item is listed as TBA. Treated as
  giveaways; the item string is unresolved.
- **Two rows, one date.** Toledo 7/3 and 7/4 each carry a gate giveaway and a postgame
  giveaway. Collapse to a single treated date.
- **Possible duplicate.** Memphis lists a Southern College of Optometry hoodie on both
  4/4 and 4/17 in different releases. 4/4 is already excluded as unmatched.
- **Live pages, not releases.** Toledo and Syracuse rows come from current promotions
  pages, so they reflect today's schedule and may have been revised since announcement.
- **Paired dates.** Nashville lists several items against two dates ("April 4 &
  September 16"). Both were kept, which assumes the item ran twice.
- **Announced attendance is tickets distributed, not turnstile count.** Universal in
  baseball attendance work. Named here rather than hidden.
