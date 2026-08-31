# Findings

Status as of the 2026 season, single treatment year.

## What the data supports

**Giveaway dates draw more than the same club's ordinary date — modestly.**

| Specification | Effect on giveaway date | 95% CI | p |
|---|---|---|---|
| League baseline, 17 complete-coverage clubs | +4.63% | [+0.49, +8.94] | — |
| League baseline, 28 clubs (incl. incomplete) | +6.08% | [+2.26, +10.04] | — |
| Within-homestand fixed effects | +8.31% | [−0.65, +18.08] | 0.070 |

Every specification points the same direction, and the placebo test is decisive:
400 fake giveaway sets, matched on club and weekday, produce a mean effect of
−1.20% (95% range −3.8% to +1.2%) against an observed +4.63%. Only 0.3% of
placebo draws were that extreme. **The pipeline is not manufacturing the effect.**

The honest statement is that giveaways add somewhere in the region of 5–8% to a
crowd — a few hundred fans on a typical Triple-A gate of ~6,000. That is far
below how promotions are usually described. Nobody's attendance doubles.

## What the data does not support

**We cannot establish whether giveaways displace demand.** This was the project's
motivating question, and one season cannot answer it.

The estimates are not robust across specification:

| Position | League baseline | Within-homestand |
|---|---|---|
| Day before (−1) | −6.63% [−11.16, −1.86] | +0.15% (p=0.973) |
| Giveaway (0) | +4.63% [+0.49, +8.94] | +8.31% (p=0.070) |
| Day after (+1) | +5.68% [−0.62, +12.38] | +9.01% (p=0.066) |

The league-baseline model shows a significant dip the day before. That dip
disappears completely under homestand fixed effects. When a result flips that
hard on a defensible change of specification, the result is the specification,
not the world.

### Why, precisely

Position within a homestand and day of week are close to the same variable.

```
offset -2: 41% Wednesday
offset -1: 41% Friday
offset  0: 40% Saturday      <- the giveaway
offset +1: 49% Sunday
offset +2: 52% Sunday
```

Clubs put giveaways on Saturdays. Homestands run Tuesday through Sunday. So
"the day before a giveaway" is largely a synonym for "Friday", and "the day
after" for "Sunday". Control for day of week and homestand together and almost
no independent variation remains to identify displacement from.

The league-baseline model appeared to find displacement because it compared
Friday-heavy dates against a baseline that models day of week additively and
imperfectly. The −6.63% is most likely a Friday artifact, not fans waiting for
a bobblehead.

## What would actually answer the question

**More treatment seasons.** Not more games — more *seasons of observed
promotions*. With three or four years, the same weekday appears at many
different homestand positions, which breaks the collinearity and gives the
displacement estimate something to work with.

Attendance history back to 2012 is already reachable through the same API. The
binding constraint is the promotional calendar, which currently exists only for
2026. Club press releases announcing prior seasons' schedules do persist —
2023 announcements are still live — so recovering 2024 and 2025 is the single
highest-value extension to this project, and it is what would turn the
displacement question from unanswerable into answerable.

## Secondary caveats

- Giveaway coverage is complete for only 17 of 30 clubs. Adding the
  partial-coverage clubs moved the lift estimate from +4.63% to +6.08%, well
  within noise, but those clubs have real giveaways coded as controls.
- Out-of-sample R² of the baseline is 0.617; median error 821 fans against a
  typical crowd of 5,139. Fine for detecting a systematic shift across 198
  giveaways, useless for predicting any single date.
- Announced attendance is tickets distributed, not turnstile count.
- 35 giveaways fall on September dates not yet played as of 2026-08-31.
