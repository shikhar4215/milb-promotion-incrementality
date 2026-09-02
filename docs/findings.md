# Findings

Three seasons of Triple-A baseball, 2024–2026. 6,195 club home dates, of which 2,992 fall
in the 44 club-seasons with a complete published giveaway calendar. 577 of those carry a
giveaway.

This document supersedes the single-season version. Where a conclusion changed, the old
one and the reason it was wrong are kept rather than quietly replaced.

## What the data supports

**Giveaways add about 9.5% to a crowd.** On the eligible sample the giveaway date runs
+9.53% above its own model-predicted attendance, 95% CI [+6.9, +12.2], across 577 treated
dates. In fans: roughly +566 on a 5,942 baseline.

The estimate is stable across seasons, which is the first thing to check when pooling
years:

| Season | Treated dates | Effect |
|---|---|---|
| 2024 | 191 | +10.49% |
| 2025 | 188 | +10.29% |
| 2026 | 198 | +7.89% |

and across specifications:

| Specification | Effect | 95% CI | n |
|---|---|---|---|
| League baseline, eligible club-seasons | +9.5% | [+6.9, +12.2] | 577 |
| League baseline, all club-seasons with data | +10.8% | [+8.4, +13.2] | 692 |
| Within-homestand fixed effects | +9.0% | [+3.2, +15.0] | 530 |
| Within-homestand, midweek giveaways only | +14.7% | [+3.5, +27.3] | 245 |
| Within-homestand, Saturday giveaways dropped | +14.3% | [+6.0, +23.3] | 145 |

**The placebo test is decisive.** 400 fake giveaway sets, matched on weekday, drawn from
untreated dates and pushed through the identical pipeline, produce a mean effect of
−0.15% with a standard deviation of 0.66pp and a range of [−1.62%, +1.13%]. The observed
+9.53% is roughly fourteen standard deviations outside that distribution. Not one draw in
400 came close.

**The model predicts honestly out of sample.** Cross-validated R² of 0.631 on held-out
dates, median absolute error 790 fans against a typical crowd of 5,205. Untreated dates
sit at +0.39%, which is the check that matters — a baseline that drifted positive on
controls would make the treated estimate meaningless.

## What the data now supports that one season could not

**There is no displacement.** The date before a giveaway sits at or above its own baseline
in every specification:

| Specification | Day before | 95% CI |
|---|---|---|
| League baseline | −0.2% | [−3.0, +2.6] |
| Within-homestand | +1.2% | [−3.9, +6.6] |
| Midweek giveaways only | +3.9% | [−6.1, +14.9] |
| Saturday giveaways dropped | −3.0% | [−10.0, +4.6] |

None is distinguishable from zero and the signs disagree, which is what noise looks like.

State this as a bound, not a proof. The midweek interval rules out pull-forward worse than
about −6% on the day before; it does not rule out −2%. What it does rule out is the large
displacement the project's premise assumed, and that is a real answer.

## The result that did not survive, and why

The single-season version reported **−6.63% [−11.2, −1.9]** on the day before a giveaway —
apparent, significant displacement. Under homestand fixed effects the same coefficient
became **+0.15%, p = 0.973**.

The diagnosis: giveaways cluster on Saturdays and homestands run Tuesday to Sunday, so
"the day before a giveaway" was largely a synonym for "Friday." Offset −1 was 41% Friday;
offset 0 was 40% Saturday. Position in a homestand and day of week were close to the same
variable, and one season contained no leverage to separate them.

Three seasons resolve it, and the mechanism matters more than the row count. **More
observations would not have helped by themselves** — Saturday giveaways scale with the
panel. What helped is midweek giveaways, where the day before is a Monday, Tuesday or
Wednesday. Those went from 49 to 128, enough to fit the model on that subsample alone.
The midweek row is the one carrying the argument.

The −6.63% was a Friday artifact. It does not survive, and it should not have been
reported as decisive in the first place.

## What three seasons did not fix

**Saturday remains unvalidatable.** 246 eligible Saturdays carry a giveaway against 138
clean controls — dates with no giveaway anywhere in the homestand, the only ones a placebo
can safely draw from. That is 0.56 controls per treated date:

| Night | Treated | Clean controls | Ratio |
|---|---|---|---|
| Tuesday | 33 | 129 | 3.91x |
| Wednesday | 59 | 134 | 2.27x |
| Thursday | 36 | 131 | 3.64x |
| Friday | 121 | 138 | 1.14x |
| **Saturday** | **246** | **138** | **0.56x** |
| Sunday | 80 | 135 | 1.69x |

Adding seasons scales treated and control together, because clubs schedule Saturday
giveaways every year. This is a structural feature of how baseball promotions are
scheduled, not a sample-size problem, and no amount of history repairs it. It would take a
club that stopped running Saturday giveaways, or an experiment.

Saturday carries 43% of all treated dates, so this is not a footnote. The reassurance
available is that dropping Saturday entirely leaves +14.3% [+6.0, +23.3] — the headline
does not depend on the night that cannot be checked.

## Weekday breakdown

Per-night estimates, with the caveat that several pools are thin:

| Night | n | Effect | 95% CI | Placebo mean | Verdict |
|---|---|---|---|---|---|
| Tuesday | 33 | +21.9% | [+9.3, +36.0] | +0.3% | significant, small n |
| Wednesday | 59 | +0.3% | [−6.1, +7.2] | +2.4% | null |
| Thursday | 36 | +2.0% | [−4.9, +9.5] | −1.4% | null |
| Friday | 121 | +6.0% | [−0.1, +12.5] | −1.6% | pool thin |
| Saturday | 246 | +14.7% | [+10.9, +18.6] | — | **placebo invalid** |
| Sunday | 80 | +3.7% | [−2.8, +10.6] | +1.2% | pool thin |

Tuesday and Wednesday disagree sharply on samples of 33 and 59. Do not read a weeknight
pattern into this; the honest summary is that the effect is concentrated on weekends and
the midweek nights are individually underpowered.

## Where this lands

Giveaways create attendance. About 9.5%, roughly 570 fans, and the surrounding dates do
not pay for it. That is a real effect and it is far below how promotions are usually
described — a bobblehead night is not doubling the gate.

The project's motivating question was whether promotions move demand rather than create
it. On three seasons of Triple-A data, they create it. The interesting caveat is not about
the answer but about the design: the single most-promoted night of the week is the one
night that cannot be checked, and the reason is that clubs promote it almost every week.

## Secondary caveats

- **21 of 452 historical giveaway dates (4.6%) had no played home game** and were dropped
  rather than shifted. Six were cancelled or postponed. Several carry a rain-out signature
  — Jacksonville 2025-07-09 has home dates on 07-08 and two on 07-10, a washout made up as
  a doubleheader. Whether the giveaway travelled to the makeup date is unknowable.
- **Two club-seasons were demoted despite publishing a calendar.** Buffalo 2025 states
  giveaways at roughly 35 dates and itemises 13; Nashville 2024 claims 31 and names 21.
- **Indianapolis Knot Hole Kids Club items were excluded** — restricted to a few hundred
  club members, and absent from the 2026 file, so including them would have made the
  treatment definition vary by season.
- **Iowa 2024 could not be recovered.** The release is indexed but the URL 404s.
- **2026 is a partial season.** Its September giveaways have no game attached.
- **Announced attendance is tickets distributed, not turnstile count.**
- **No pricing or cost data**, so this measures attendance rather than profit. A 570-fan
  lift against the cost of 2,000 bobbleheads is a different question and this project does
  not answer it.
