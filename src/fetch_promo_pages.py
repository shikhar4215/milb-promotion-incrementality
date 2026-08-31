"""
Download each Triple-A club's promotions page so the parser can work offline.

Fetching and parsing are deliberately separate. The pages only exist for the
current season, so we grab the HTML once and then iterate on the parser as
many times as we like without hammering milb.com.

Usage
-----
    python3 src/fetch_promo_pages.py            # all 30 clubs
    python3 src/fetch_promo_pages.py --team 484 # just Indianapolis
"""

from __future__ import annotations

import argparse
import time

import requests

import config

# milb.com URL slug for each club, keyed by MLB Stats API team id.
# Slugs are best-effort; the script reports any that 404 so they can be fixed.
TEAM_SLUGS: dict[int, str] = {
    # International League
    422: "buffalo",
    494: "charlotte",
    445: "columbus",
    234: "durham",
    431: "gwinnett",
    484: "indianapolis",
    451: "iowa",
    564: "jacksonville",
    1410: "lehighvalley",
    416: "louisville",
    235: "memphis",
    556: "nashville",
    568: "norfolk",
    541: "omaha",
    534: "rochester",
    531: "swb",
    1960: "stpaul",
    552: "syracuse",
    512: "toledo",
    533: "worcester",
    # Pacific Coast League
    342: "albuquerque",
    4904: "elpaso",
    400: "lasvegas",
    238: "oklahomacity",
    2310: "reno",
    102: "roundrock",
    105: "sacramento",
    561: "saltlake",
    5434: "sugarland",
    529: "tacoma",
}

PROMO_URL = "https://www.milb.com/{slug}/tickets/promotions"


def fetch_one(team_id: int, slug: str, refresh: bool = False) -> tuple[str, int | str]:
    """Download one club's promo page. Returns (outcome, status or size)."""
    out_path = config.RAW_PROMOS / f"{team_id}_{slug}.html"

    if out_path.exists() and not refresh:
        return "cached", out_path.stat().st_size

    try:
        response = requests.get(
            PROMO_URL.format(slug=slug),
            headers={"User-Agent": config.USER_AGENT},
            timeout=config.REQUEST_TIMEOUT,
        )
    except Exception as exc:  # noqa: BLE001
        return "error", type(exc).__name__

    if response.status_code != 200:
        return "http", response.status_code

    out_path.write_text(response.text, encoding="utf-8")
    time.sleep(config.REQUEST_DELAY)
    return "ok", len(response.text)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team", type=int, default=None, help="Single team id.")
    parser.add_argument("--refresh", action="store_true", help="Re-download cached pages.")
    args = parser.parse_args()

    config.ensure_dirs()

    targets = ({args.team: TEAM_SLUGS[args.team]} if args.team else TEAM_SLUGS)

    failures: list[tuple[int, str, str, object]] = []
    for team_id, slug in targets.items():
        outcome, detail = fetch_one(team_id, slug, refresh=args.refresh)
        if outcome in ("ok", "cached"):
            print(f"  {outcome:<7} {slug:<14} {detail:>9,} bytes")
        else:
            print(f"  FAILED  {slug:<14} {outcome}: {detail}")
            failures.append((team_id, slug, outcome, detail))

    print(f"\n{len(targets) - len(failures)}/{len(targets)} pages retrieved")
    if failures:
        print("\nSlugs to correct:")
        for team_id, slug, outcome, detail in failures:
            print(f"  {team_id}  {slug}  ({outcome} {detail})")


if __name__ == "__main__":
    main()
