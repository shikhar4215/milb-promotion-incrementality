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

## Weekday breakdown: attempted, and not supported

Since homestand position and weekday are near-collinear, the natural follow-up
was whether the giveaway effect differs by night. It does not resolve cleanly,
and the attempt is documented because the failure is informative.

| Night | n | Lift | 95% CI | Placebo pool |
|---|---|---|---|---|
| Tuesday | 11 | +15.8% | [−4.5, +40.3] | 43 |
| Wednesday | 24 | −3.7% | [−12.2, +5.6] | 45 |
| Thursday | 14 | −14.5% | [−21.2, −7.2] | 44 |
| Friday | 46 | +4.8% | [−5.0, +15.7] | 48 |
| Saturday | 79 | +9.9% | [+3.8, +16.4] | **50 — smaller than treated group** |
| Sunday | 23 | +1.0% | [−11.0, +14.7] | 48 |

Only Saturday and Thursday have intervals excluding zero. Thursday rests on 14
giveaways and is most plausibly selection — clubs scheduling promotions onto
Thursdays they already expected to be soft, which the model cannot observe.

**Saturday is the one that matters and the one we cannot validate.** 79 of 129
eligible Saturdays carried a giveaway. Nashville and Sugar Land ran one on
*every* home Saturday. There are 50 giveaway-free Saturdays league-wide, fewer
than the treated group, so no placebo can be constructed and the counterfactual
rests on a thin and possibly unrepresentative set of dates.

### A caution on the placebo p-values

Placebo p-values throughout this project run smaller than the analytic
confidence intervals justify — Friday reports p=0.000 alongside a CI spanning
[−5.0%, +15.7%]. The cause is pool size: draws of 46 from a pool of 48 overlap
almost entirely, so the placebo distribution understates true sampling
variability. **The confidence intervals are the honest inference. Placebo tests
are used here as a directional check that the pipeline is not manufacturing
effects, not as significance tests.**

An earlier version of the placebo matched draws on club as well as weekday,
which shrank the Saturday pool below the treated group and silently truncated
the draws. That was corrected to weekday-only matching, which is sufficient
because residuals are already club-adjusted by the model's fixed effects.

## Where this actually lands

One season supports a **pooled giveaway lift of roughly 5%**, with a confidence
interval that barely excludes zero, and little else. It does not support the
displacement analysis the project was built around, and it does not support a
reliable weekday breakdown.

The binding constraint is not model choice. It is that promotional scheduling
is highly structured — Saturdays, weekends, good opponents — so within a single
season the control group for the most common promotional slot barely exists.
Recovering 2024 and 2025 giveaway calendars is what would make both questions
answerable.

## Secondary caveats

- Giveaway coverage is complete for only 17 of 30 clubs. Adding the
  partial-coverage clubs moved the lift estimate from +4.63% to +6.08%, well
  within noise, but those clubs have real giveaways coded as controls.
- Out-of-sample R² of the baseline is 0.617; median error 821 fans against a
  typical crowd of 5,139. Fine for detecting a systematic shift across 198
  giveaways, useless for predicting any single date.
- Announced attendance is tickets distributed, not turnstile count.
- 35 giveaways fall on September dates not yet played as of 2026-08-31.
