"""Shared configuration for the MiLB promotional incrementality project."""

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths. Everything is resolved relative to the repo root so the scripts work
# no matter which directory you run them from.
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_INTERIM = PROJECT_ROOT / "data" / "interim"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
REPORTS = PROJECT_ROOT / "reports"
FIGURES = REPORTS / "figures"

RAW_SCHEDULES = DATA_RAW / "schedules"
RAW_GAMES = DATA_RAW / "games"
RAW_PROMOS = DATA_RAW / "promos"

# ---------------------------------------------------------------------------
# MLB Stats API
# ---------------------------------------------------------------------------
STATS_API = "https://statsapi.mlb.com/api"

# Triple-A. (Double-A is 12, High-A 13, Single-A 14 if we ever extend.)
SPORT_ID_TRIPLE_A = 11

# The Mexican League also carries sportId=11 in older seasons. It is a
# different market with different economics, so we exclude it.
LEAGUE_INTERNATIONAL = 117
LEAGUE_PACIFIC_COAST = 112
LEAGUE_MEXICAN = 125
KEEP_LEAGUE_IDS = {LEAGUE_INTERNATIONAL, LEAGUE_PACIFIC_COAST}

# ---------------------------------------------------------------------------
# Study design
# ---------------------------------------------------------------------------
# Layer A: long attendance history, used to estimate stable structural effects
# (day of week, month, weather, opponent).
HISTORY_SEASONS = list(range(2015, 2027))

# Layer B: the one season where we can observe promotions, so the treatment
# effect is estimated within it.
TREATMENT_SEASON = 2026

# 2020 was cancelled for the minor leagues (COVID-19).
CANCELLED_SEASONS = {2020}

# ---------------------------------------------------------------------------
# HTTP politeness
# ---------------------------------------------------------------------------
REQUEST_DELAY = 0.20      # seconds between calls
REQUEST_TIMEOUT = 30      # seconds
MAX_RETRIES = 4
USER_AGENT = "milb-attendance-research/1.0 (academic portfolio project)"


def ensure_dirs() -> None:
    """Create every data directory the pipeline writes to."""
    for path in (
        DATA_RAW, DATA_INTERIM, DATA_PROCESSED,
        RAW_SCHEDULES, RAW_GAMES, RAW_PROMOS,
        REPORTS, FIGURES,
    ):
        path.mkdir(parents=True, exist_ok=True)
