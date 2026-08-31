# Data Sources: What Works, What Doesn't

A record of every source evaluated for this project, including the ones that
failed. The failures shaped the design more than the successes did.

## Confirmed working

### MLB Stats API — game logs, attendance, ballpark weather

`https://statsapi.mlb.com` — free, no API key, no registration.
Triple-A is `sportId=11`.

| Endpoint | Returns |
|---|---|
| `/v1/schedule?sportId=11&season=YYYY&gameType=R` | Game list: teams, venue, date, day/night, doubleheader flag, series position, team records |
| `/v1.1/game/{gamePk}/feed/live` | `gameInfo.attendance`, `weather.condition`, `weather.temp`, `weather.wind`, first pitch time |

Weather is recorded at the ballpark at first pitch and ships in the same record
as attendance, so no separate weather join is needed. This is more accurate than
matching games to a nearby NOAA station would have been.

**2026 season results:** 2,250 unique games, 1,958 played, 96.5% carrying
attendance, 100% carrying weather. Verified working back to 2012.

**Gotcha 1 — repeated game IDs.** A game postponed and made up as part of a
doubleheader is returned twice under the same `gamePk`: once as `Postponed`,
once as the completed makeup. 90 such rows in 2026 alone. `dedupe_schedule()`
keeps the row that was actually played.

**Gotcha 2 — zero attendance is not zero.** 68 played games report attendance
of 0; every one is a doubleheader, 66 of them game one. Baseball books the
whole gate to a single game of the pair. This is why the unit of analysis is
the **home date**, not the individual game.

## Evaluated and rejected

### Historical promotional calendars — not recoverable

| Approach | Outcome |
|---|---|
| `hydrate=promotions` on the schedule endpoint | Silently ignored; no promo data in the API |
| MLB Stats API endpoint catalogue | No promotions, tickets or giveaway endpoint exists |
| Wayback Machine, Indianapolis promo page @ 2024 | Only a 2026 capture exists |
| Wayback Machine, Lehigh Valley promo page @ 2023 | `archived_snapshots: {}` — never captured |
| PromoNight (getpromonight.com) | Current season only, and MLB/NBA/NHL/NFL — no MiLB |

Clubs remove promotion pages at season's end and the Internet Archive did not
systematically capture them.

### Club promotions pages — heterogeneous, mostly empty

`https://www.milb.com/{slug}/tickets/promotions` — 20 of 30 slugs resolved on
the first pass; the other 10 were multi-word cities needing hyphens
(`lehigh-valley`, `scranton-wilkes-barre`, `st-paul`, and so on).

Retrieving them was not the problem. **Content was.** Keyword scanning the
downloaded HTML showed only Indianapolis carries a substantive inline promo
calendar (121 "fireworks", 60 "giveaway" mentions, embedded as escaped JSON in
a page-builder payload). Most clubs scored zero: Durham's page contains no
promo container at all, only navigation and a link to a printable PDF.

Clubs build these pages differently. Scraping them uniformly is not possible.

### Printable promotion PDFs — flat artwork, no text layer

15 of 20 retrieved pages link a season promo PDF on `img.mlbstatic.com`.
Text extraction on a sample returns *"This PDF is empty or contains no
machine-readable text"* — they are designed graphics exported without a text
layer.

OCR was considered and rejected. Thirty different visual calendar designs would
produce a variable and unmeasurable error rate, and those errors would land
directly in the treatment variable. A promotion missed by OCR is silently coded
as "no promotion", which biases every lift estimate downward. Not acceptable for
the central measurement in the study.

## Under evaluation

### Club press releases — the remaining candidate

`https://www.milb.com/news/...` articles announcing each season's promotional
schedule. Unlike ticket pages, news archives persist: 2023 announcements are
still live, which would unlock multiple treatment seasons rather than one.

Format is mixed. Giveaways tend to appear as clean bulleted date pairs
("March 28: Replica championship ring"), while theme nights and weekly specials
are embedded in prose ("Fantasy Football Punishment Night (April 2)").

The risk is partial extraction. A parser that catches bullets but misses prose
silently codes real promotions as absent — the same bias that disqualified OCR,
in a less obvious form. Any parser built here must be validated against a
hand-checked sample before its output is trusted, with the recall rate reported
rather than assumed.
