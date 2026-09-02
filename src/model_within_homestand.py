"""
Within-homestand estimation: the specification the headline should rest on.

Why this replaces the league-baseline model
-------------------------------------------
The placebo test exposed a problem. Dates in homestands with no giveaway sit
about 1.2% BELOW the league baseline, which means clubs schedule giveaways into
homestands that were already going to draw well. Part of any measured lift is
therefore selection into good weekends, not the giveaway itself.

Homestand fixed effects remove it. Each giveaway is compared only against the
other dates in ITS OWN homestand - same club, same week, same opponent, same
weather window, same local demand. Anything constant within a homestand cancels,
including whatever made the club schedule a giveaway there.

What identifies the effect is then purely position within the homestand, which
is also exactly what the displacement question asks.

The offset dummies read directly:
    offset  0  -> lift on the giveaway date
    offset -1  -> demand held back the day before
    offset +1  -> spillover the day after
Reference category is every date three or more games from the giveaway.

Usage
-----
    python3 src/model_within_homestand.py
    python3 src/model_within_homestand.py --placebo
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

import config

MIN_DATES = 4          # homestands shorter than this cannot support the comparison
OFFSETS = [-2, -1, 0, 1, 2]


class _Tee:
    def __init__(self, *s): self.streams = s
    def write(self, t):
        for s in self.streams: s.write(t)
    def flush(self):
        for s in self.streams: s.flush()


def prepare(all_clubs: bool = False, drop_saturday: bool = False,
            midweek_only: bool = False) -> pd.DataFrame:
    df = pd.read_csv(config.DATA_PROCESSED / "games_analysis.csv")
    df = df[df["analysis_eligible"] == 1] if not all_clubs else df[df["club_coverage"] != "no_source_found"]
    df = df.copy()

    df["log_attendance"] = np.log(df["attendance"])
    df["temp_f"] = df["temp_f"].fillna(df["temp_f"].median())
    df["away_win_pct"] = df["away_win_pct"].fillna(0.5)
    df["offset"] = df["games_from_giveaway"]

    # Keep only homestands that actually contain a giveaway and are long enough
    # for a within-homestand comparison to mean anything.
    sizes = df.groupby("homestand_id").size()
    has_gv = df.groupby("homestand_id")["has_giveaway"].max()
    keep = sizes[(sizes >= MIN_DATES) & (has_gv.reindex(sizes.index) == 1)].index
    df = df[df["homestand_id"].isin(keep)].copy()

    if midweek_only:
        # The strongest break of the confound available. Keep only homestands
        # whose giveaway landed Tuesday, Wednesday or Thursday, so "the day
        # before the giveaway" is a Monday, Tuesday or Wednesday rather than
        # being a synonym for Friday. This is the subsample the extra seasons
        # were collected to make large enough to fit.
        mid = df[(df["has_giveaway"] == 1)
                 & (df["day_of_week"].isin(["Tuesday", "Wednesday", "Thursday"]))
                 ]["homestand_id"].unique()
        df = df[df["homestand_id"].isin(mid)].copy()

    if drop_saturday:
        # Saturday giveaways are what locks homestand position to weekday.
        # Dropping them leaves less data but real independent variation.
        sat = df[(df["has_giveaway"] == 1) & (df["day_of_week"] == "Saturday")]["homestand_id"].unique()
        df = df[~df["homestand_id"].isin(sat)].copy()

    for o in OFFSETS:
        df[f"off_{'m' if o < 0 else 'p'}{abs(o)}"] = (df["offset"] == o).astype(int)
    return df


def fit_and_report(df: pd.DataFrame, label: str) -> dict[int, tuple]:
    terms = " + ".join(f"off_{'m' if o < 0 else 'p'}{abs(o)}" for o in OFFSETS)
    formula = (f"log_attendance ~ C(homestand_id) + C(day_of_week) + C(day_night)"
               f" + temp_f + is_wet + away_win_pct + {terms}")
    model = smf.ols(formula, data=df).fit(cov_type="cluster",
                                          cov_kwds={"groups": df["homestand_id"]})

    print(f"\n=== {label} ===")
    print(f"  homestands {df['homestand_id'].nunique()}   dates {len(df):,}   "
          f"giveaways {int(df['has_giveaway'].sum())}   within-R2 {model.rsquared:.3f}")
    print(f"\n  offset      n     effect          95% CI            p")
    results = {}
    for o in OFFSETS:
        name = f"off_{'m' if o < 0 else 'p'}{abs(o)}"
        n = int(df[name].sum())
        coef, se, p = model.params[name], model.bse[name], model.pvalues[name]
        eff = (np.exp(coef) - 1) * 100
        lo = (np.exp(coef - 1.96 * se) - 1) * 100
        hi = (np.exp(coef + 1.96 * se) - 1) * 100
        star = " *" if p < 0.05 else ""
        tag = "  <-- giveaway" if o == 0 else ""
        print(f"   {o:+3d}     {n:>4}   {eff:+6.2f}%   [{lo:+6.2f}, {hi:+6.2f}]   {p:.3f}{star}{tag}")
        results[o] = (eff, lo, hi, p, n)
    return results


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--placebo", action="store_true",
                    help="Re-run with giveaway positions shuffled inside each homestand.")
    ap.add_argument("--all-clubs", action="store_true")
    ap.add_argument("--midweek", action="store_true",
                    help="Keep only homestands whose giveaway fell Tuesday-Thursday. "
                         "Breaks the weekday/position confound outright.")
    ap.add_argument("--no-saturday", action="store_true",
                    help="Drop homestands whose giveaway fell on a Saturday, breaking "
                         "the near-collinearity between homestand position and weekday.")
    args = ap.parse_args()

    config.ensure_dirs()
    name = "within_homestand"
    if args.placebo:
        name += "_placebo"
    if args.midweek:
        name += "_midweek"
    if args.no_saturday:
        name += "_nosaturday"
    out = config.REPORTS / f"{name}.txt"
    handle = open(out, "w")
    sys.stdout = _Tee(sys.__stdout__, handle)

    df = prepare(args.all_clubs, drop_saturday=args.no_saturday,
                 midweek_only=args.midweek)

    if not args.placebo:
        label = ("Within-homestand estimates, Saturday giveaways excluded"
                 if args.no_saturday else "Within-homestand estimates")
        res = fit_and_report(df, label)
        lift = res[0][0]
        before = res[-1][0]
        print("\n  reference category: dates 3+ games from the giveaway, same homestand")
        print("\n  reading:")
        print(f"    giveaway date runs {lift:+.1f}% against its own homestand")
        print(f"    the date before runs {before:+.1f}%")
        if res[-1][3] < 0.05 and before < 0:
            print("    -> demand is being held back, not created, on the day before")
        elif res[-1][3] >= 0.05:
            print("    -> no significant hold-back the day before")
    else:
        # Shuffle which date in each homestand is 'treated', preserving the
        # homestand structure. Should produce nothing.
        rng = np.random.default_rng(20260831)
        frames = []
        for hid, g in df.groupby("homestand_id"):
            g = g.sort_values("homestand_game_index").reset_index(drop=True)
            fake_pos = rng.integers(0, len(g))
            g["offset"] = g.index - fake_pos
            for o in OFFSETS:
                g[f"off_{'m' if o < 0 else 'p'}{abs(o)}"] = (g["offset"] == o).astype(int)
            frames.append(g)
        shuffled = pd.concat(frames, ignore_index=True)
        fit_and_report(shuffled, "PLACEBO - giveaway position randomised within homestand")
        print("\n  every effect here should be indistinguishable from zero.")

    sys.stdout = sys.__stdout__
    handle.close()
    print(f"\n-> {out.relative_to(config.PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
