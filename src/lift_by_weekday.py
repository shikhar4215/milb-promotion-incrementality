"""
Does a giveaway's effect depend on which night it runs?

The displacement question could not be answered with one season, because
homestand position and weekday are nearly the same variable. But that same
confound points at a question this data CAN answer, and one that is arguably
more useful to a club: giveaways are concentrated on nights that already sell.
Do they still add anything there?

Method reuses the validated pipeline. The baseline is fitted on clean control
dates only - no giveaway in the homestand, or three-plus games away - so it
never sees a treated date. Residuals for giveaway dates are then split by
weekday. Each weekday's lift is compared against placebo giveaways drawn from
untreated dates on that same weekday and the same clubs, so a weekday that is
simply hard to predict cannot masquerade as an effect.

Usage
-----
    python3 src/lift_by_weekday.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

import config
from model_baseline import FORMULA, SPILLOVER_WINDOW, load

N_PLACEBO = 500
SEED = 20260831
DAYS = ["Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class _Tee:
    def __init__(self, *s): self.streams = s
    def write(self, t):
        for s in self.streams: s.write(t)
    def flush(self):
        for s in self.streams: s.flush()


def main() -> None:
    config.ensure_dirs()
    out = config.REPORTS / "lift_by_weekday.txt"
    handle = open(out, "w")
    sys.stdout = _Tee(sys.__stdout__, handle)

    df = load(all_clubs=False)
    is_clean = df["offset"].isna() | (df["offset"].abs() >= SPILLOVER_WINDOW)
    model = smf.ols(FORMULA, data=df[is_clean]).fit()

    df = df.copy()
    df["predicted_log"] = model.predict(df)
    df["residual"] = df["log_attendance"] - df["predicted_log"]
    df["predicted_attendance"] = np.exp(df["predicted_log"])

    treated = df[df["offset"] == 0]
    pool = df[df["offset"].isna()]          # never treated, never adjacent
    rng = np.random.default_rng(SEED)

    print("\n=== giveaway lift by night of the week ===")
    print("  each weekday's lift, against placebo giveaways on the same weekday\n")
    print("  night        n    lift        95% CI           placebo  pool      p")

    rows = []
    for day in DAYS:
        t = treated[treated["day_of_week"] == day]
        if len(t) < 8:
            continue
        r = t["residual"]
        se = r.std(ddof=1) / np.sqrt(len(r))
        lift = (np.exp(r.mean()) - 1) * 100
        lo = (np.exp(r.mean() - 1.96 * se) - 1) * 100
        hi = (np.exp(r.mean() + 1.96 * se) - 1) * 100

        # Placebo: untreated dates on the SAME weekday. We deliberately do not
        # match on club - residuals are already club-adjusted by the model's
        # fixed effects, and club-matching shrinks the pool below the treated
        # group on Saturdays, which truncates draws and understates variance.
        cand = pool[pool["day_of_week"] == day]
        draws = []
        if len(cand) >= len(t):
            for _ in range(N_PLACEBO):
                pick = cand.sample(len(t), replace=False,
                                   random_state=int(rng.integers(1e9)))
                draws.append(np.exp(pick["residual"].mean()) - 1)
        pool_ratio = len(cand) / len(t) if len(t) else 0.0

        if draws:
            d = np.array(draws) * 100
            p = (np.abs(d - d.mean()) >= abs(lift - d.mean())).mean()
            pm = d.mean()
        else:
            p, pm = float("nan"), float("nan")

        star = " *" if p < 0.05 else ""
        warn = ""
        if pool_ratio < 1:
            warn = "   POOL TOO SMALL - placebo not valid"
        elif pool_ratio < 2:
            warn = "   pool thin, treat p with caution"
        print(f"  {day:<10} {len(t):>4}  {lift:+6.1f}%  [{lo:+6.1f}, {hi:+6.1f}]   "
              f"{pm:+6.1f}%   {len(cand):>4}   {p:.3f}{star}{warn}")
        rows.append({"day_of_week": day, "n": len(t), "lift_pct": lift,
                     "ci_low": lo, "ci_high": hi, "placebo_mean": pm, "p_value": p,
                     "placebo_pool": len(cand), "pool_ratio": pool_ratio,
                     "baseline_attendance": t["predicted_attendance"].mean(),
                     "fans_gained": t["predicted_attendance"].mean() * (np.exp(r.mean()) - 1)})

    res = pd.DataFrame(rows)
    res.to_csv(config.REPORTS / "lift_by_weekday.csv", index=False)

    print("\n=== in fans, not percentages ===")
    print("  night        giveaways   baseline crowd   fans added   total added")
    for _, r in res.iterrows():
        print(f"  {r.day_of_week:<10} {int(r.n):>7}   {r.baseline_attendance:>12,.0f}   "
              f"{r.fans_gained:>+10,.0f}   {r.fans_gained*r.n:>+11,.0f}")

    weeknight = res[res.day_of_week.isin(["Tuesday", "Wednesday", "Thursday"])]
    weekend = res[res.day_of_week.isin(["Friday", "Saturday"])]
    if len(weeknight) and len(weekend):
        print(f"\n  weeknight (Tue-Thu) mean lift: {weeknight.lift_pct.mean():+.1f}%  "
              f"across {int(weeknight.n.sum())} giveaways")
        print(f"  Fri/Sat mean lift:             {weekend.lift_pct.mean():+.1f}%  "
              f"across {int(weekend.n.sum())} giveaways")

    sys.stdout = sys.__stdout__
    handle.close()
    print(f"\n-> {out.relative_to(config.PROJECT_ROOT)} and lift_by_weekday.csv")


if __name__ == "__main__":
    main()
