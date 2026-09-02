"""
Does the baseline model deserve to be trusted?

Two checks, because the headline number is only as good as the counterfactual
behind it.

1. CROSS-VALIDATED R-SQUARED. In-sample R-squared is optimistic, and residual
   means within the model's own dummy levels are exactly zero by construction -
   they prove nothing. K-fold CV on the clean controls gives an honest read on
   how well the baseline predicts a date it has never seen, which is exactly
   what it is asked to do for treated dates.

2. PLACEBO TEST. Pretend giveaways happened on dates where they did not, drawn
   from the same clubs and the same day-of-week mix as the real ones, and run
   the identical estimation. A trustworthy pipeline returns roughly zero lift.
   If placebos show lift, the machinery is manufacturing an effect and the real
   estimate means nothing.

Usage
-----
    python3 src/diagnose_model.py
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

import config
from model_baseline import FORMULA, SPILLOVER_WINDOW, load

N_PLACEBO = 400
SEED = 20260831


def cross_validated_r2(controls: pd.DataFrame, k: int = 5, seed: int = SEED) -> None:
    rng = np.random.default_rng(seed)
    fold = rng.integers(0, k, len(controls))
    actual, predicted = [], []

    for f in range(k):
        train = controls[fold != f]
        test = controls[fold == f]
        try:
            fit = smf.ols(FORMULA, data=train).fit()
            pred = fit.predict(test)
        except Exception:
            continue
        ok = pred.notna()
        actual.append(test.loc[ok, "log_attendance"].to_numpy())
        predicted.append(pred[ok].to_numpy())

    a = np.concatenate(actual)
    p = np.concatenate(predicted)
    ss_res = ((a - p) ** 2).sum()
    ss_tot = ((a - a.mean()) ** 2).sum()

    print(f"  cross-validated R-squared : {1 - ss_res/ss_tot:.3f}   (n = {len(a):,})")
    print(f"  median absolute error     : {np.median(np.abs(np.exp(a) - np.exp(p))):,.0f} fans")
    print(f"  typical crowd             : {np.exp(a).mean():,.0f} fans")


def placebo(df: pd.DataFrame, model, n_draws: int = N_PLACEBO, seed: int = SEED) -> None:
    """Fake giveaways on untreated dates, matched on day of week only."""
    rng = np.random.default_rng(seed)

    real = df[df["offset"] == 0]
    # Pool of dates that were never treated and never adjacent to a giveaway.
    pool = df[df["offset"].isna()]
    if pool.empty:
        print("  no untreated pool available")
        return

    # Match on weekday only. Club is already absorbed by the model's fixed
    # effects, and club-matching shrinks the Saturday pool below the treated
    # group, which truncates draws and understates placebo variance.
    target_mix = real.groupby("day_of_week").size()
    shortfalls = {d: len(pool[pool["day_of_week"] == d]) / c
                  for d, c in target_mix.items() if c}
    thin = {d: r for d, r in shortfalls.items() if r < 1}
    if thin:
        print(f"  WARNING - untreated pool smaller than treated group for: "
              f"{', '.join(f'{d} ({r:.1f}x)' for d, r in thin.items())}")
        print("  placebo inference for those weekdays is not reliable")

    effects = []
    for _ in range(n_draws):
        picks = []
        for dow, count in target_mix.items():
            cand = pool[pool["day_of_week"] == dow]
            if len(cand) == 0:
                continue
            picks.append(cand.sample(min(count, len(cand)), replace=False,
                                     random_state=int(rng.integers(1e9))))
        if not picks:
            continue
        fake = pd.concat(picks)
        effects.append(np.exp(fake["residual"].mean()) - 1)

    e = np.array(effects) * 100
    real_lift = (np.exp(real["residual"].mean()) - 1) * 100
    p_val = (np.abs(e) >= abs(real_lift)).mean()

    print(f"  placebo lift  mean {e.mean():+.2f}%   sd {e.std():.2f}pp")
    print(f"  placebo range [{np.percentile(e,2.5):+.2f}%, {np.percentile(e,97.5):+.2f}%]")
    print(f"  observed lift {real_lift:+.2f}%")
    print(f"  share of placebos at least as extreme: {p_val:.3f}")
    if p_val < 0.05:
        print("  -> the observed lift is outside what the pipeline produces by chance")
    else:
        print("  -> WARNING: the pipeline produces effects this large on fake dates")


class _Tee:
    """Write everything printed to both the terminal and the report file."""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, text):
        for s in self.streams:
            s.write(text)

    def flush(self):
        for s in self.streams:
            s.flush()


def main() -> None:
    config.ensure_dirs()
    report_path = config.REPORTS / "model_diagnostics.txt"
    handle = open(report_path, "w")
    sys.stdout = _Tee(sys.__stdout__, handle)

    df = load(all_clubs=False)

    is_clean = df["offset"].isna() | (df["offset"].abs() >= SPILLOVER_WINDOW)
    controls = df[is_clean]

    print("=== 1. out-of-sample predictive power ===")
    cross_validated_r2(controls)

    model = smf.ols(FORMULA, data=controls).fit()
    df = df.copy()
    df["residual"] = df["log_attendance"] - model.predict(df)

    print(f"\n=== 2. placebo test ({N_PLACEBO} draws, matched on weekday) ===")
    placebo(df, model)

    sys.stdout = sys.__stdout__
    handle.close()
    print(f"\n-> {report_path.relative_to(config.PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
