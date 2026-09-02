# Recovering the 2024 and 2025 giveaway calendars

The 2026 calendars came from club promotions pages, scraped live. Those pages only ever
show the current season, so the historical calendars had to come from somewhere else.

## What worked

**milb.com keeps club press releases permanently, under a predictable URL pattern.**

```
https://www.milb.com/{slug}/news/{club}-announce-{year}-promotions-schedule
https://www.milb.com/{slug}/news/{club}-announce-{year}-promotions
https://www.milb.com/{slug}/news/{club}-unveil-{year}-season-promotional-schedule
```

The pattern is not consistent enough to generate blindly — the verb varies by club and by
year — so each club-season was located by search and then read directly.

Local news outlets mirror many of these releases verbatim. Those are useful as a **second
source for verification**, and for two club-seasons they were the only source that carried
the date table at all.

## What did not work

- **The Wayback Machine** is blocked from the analysis environment by egress policy, so
  archived copies of the club promotions pages were never available. This is the reason
  Iowa 2024 could not be recovered: the release is indexed at
  `/iowa/news/2024-promo-calendar` but that URL now returns 404, and the archive is the
  obvious next stop.
- **OurSports Central** carries Isotopes and Round Rock releases and was used for those,
  but its Triple-A coverage is patchy by year.
- **Club promotions pages** show the current season only. No historical view exists.

## Rules applied during collection

1. A row is recorded only if the article states an **explicit calendar date**. Never infer
   a date from a homestand, a day of week, or a pattern.
2. **Giveaways only** — a physical item handed to fans. Fireworks, theme nights, heritage
   nights with no item, jersey auctions, ticket bundles and food specials are excluded.
3. An announced giveaway with an unnamed item is recorded with item `TBA`. The treatment
   date is what the model uses.
4. **Restricted-audience items are not giveaways.** Indianapolis's Knot Hole Kids Club
   handout goes to a few hundred registered members, and no such item appears in the 2026
   file. 25 rows across 2024–2025 were dropped so the treatment definition would not vary
   by season.
5. Every row carries the URL it was read from.

## Coverage grading

Graded **per club-season**, because a club that published a full calendar one year and
homestand previews the next is eligible in the first and not the second.

| Grade | Meaning |
|---|---|
| `full_season_release` | One release covering the whole season |
| `partial_assembled` | Half-season release, homestand previews, or a stated count materially above the number of dates itemised |
| `no_source_found` | No dated release located |

Two club-seasons were demoted from a full-season release on the third criterion:

| Club-season | Stated | Itemised | Reason |
|---|---|---|---|
| Buffalo 2025 | ~35 | 13 | Release says giveaways at "nearly half" of 75 home games |
| Nashville 2024 | 31 | 21 | Release claims 31 giveaway dates, names 21 |

An unobserved giveaway is coded as a control, which biases lift **downward**, so these are
excluded from the headline sample rather than trusted.

## Verification

Collection was fanned out across five parallel passes, so it needed an independent check
rather than self-reporting.

- Every extracted date was re-checked against the weekday printed in the source release.
- Four club-seasons were re-read from source afterwards and compared line by line:
  Gwinnett 2024 (17 rows, matching the article's own stated count of 17), Omaha 2025 (8 of
  8 dates and items identical), St. Paul 2025, and Round Rock, whose mirror-sourced counts
  reconcile exactly with the totals milb.com states (14 and 16).
- Every date was then joined to the actual played schedule. 21 of 452 did not match; those
  are itemised in `findings.md` and were dropped, not shifted.

## Result

Club counts are clubs with at least one dated giveaway; the 2026 file also lists two
clubs that published nothing dated.

| Season | Rows | Distinct club-dates | Clubs | Eligible club-seasons |
|---|---|---|---|---|
| 2024 | 232 | 229 | 16 | 13 |
| 2025 | 224 | 223 | 17 | 14 |
| 2026 | 314 | 310 | 28 | 17 |

The number the collection existed to move: **midweek (Tuesday–Thursday) giveaways went
from 49 to 128**, which is what made the displacement question estimable on a subsample
where homestand position is not a proxy for day of week.
