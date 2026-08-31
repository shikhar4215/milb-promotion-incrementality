"""
Validate the giveaway reference data against the extracted schedule.

Every giveaway must land on a date the club actually played at home. Anything
that doesn't is a defect in the treatment variable, and a treatment variable
with silent defects will quietly bias every lift estimate in the study.

Writes reports/giveaway_validation.csv and prints a summary.

Usage
-----
    python3 src/validate_giveaways.py
"""

from __future__ import annotations

import pandas as pd

import config

PLAYED = ("Final", "Completed Early")


def main() -> None:
    config.ensure_dirs()

    giveaways = pd.read_csv(config.PROJECT_ROOT / "data/reference/giveaways_2026.csv")
    giveaways = giveaways[giveaways["date"].notna()].copy()

    games = pd.read_csv(config.DATA_INTERIM / "games_raw.csv")
    games["home_team_id"] = games["home_team_id"].astype("Int64")

    # Every home date, with the status that date resolved to.
    home_dates = (
        games.groupby(["home_team_id", "date"])["status"]
        .apply(lambda s: "played" if s.isin(PLAYED).any() else s.iloc[0])
        .reset_index()
        .rename(columns={"home_team_id": "team_id", "status": "date_status"})
    )

    merged = giveaways.merge(home_dates, on=["team_id", "date"], how="left")
    merged["date_status"] = merged["date_status"].fillna("no_home_game")

    def classify(status: str) -> str:
        if status == "played":
            return "usable"
        if status == "Scheduled":
            return "not_yet_played"          # season still running
        if status in ("Cancelled", "Postponed", "Suspended"):
            return "game_did_not_happen"
        return "unmatched_date"              # defect: investigate

    merged["validation"] = merged["date_status"].apply(classify)

    out = config.REPORTS / "giveaway_validation.csv"
    merged.to_csv(out, index=False)

    print(f"giveaway rows checked: {len(merged):,}\n")
    for label, n in merged["validation"].value_counts().items():
        print(f"  {n:>4}  {label}")

    bad = merged[merged["validation"] == "unmatched_date"]
    if len(bad):
        print(f"\nUNMATCHED - excluded from the treated set ({len(bad)} rows):")
        for _, r in bad.iterrows():
            print(f"  {r['club']:<34} {r['date']}  {str(r['item'])[:46]}")
        print("\nThese are NOT date-shifted into place. Several look like off-by-one")
        print("errors on homestand openers, but inferring the correct date would be")
        print("inventing treatment assignment.")

    print(f"\nreport -> {out.relative_to(config.PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
