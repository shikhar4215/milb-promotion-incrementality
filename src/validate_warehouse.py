"""
Check the SQL star schema against the pandas one, column by column.

The warehouse is only worth shipping if it reproduces the tables the dashboard
already reads. Two independent implementations of the same transformation are a
real test: homestand assignment done with LAG and a running SUM in SQL should
land on exactly the same runs as the shift-and-cumsum in pandas, and if it does
not, one of them is wrong.

Usage
-----
    python3 src/validate_warehouse.py
"""

from __future__ import annotations

import sqlite3
import sys

import numpy as np
import pandas as pd

import config

DB_PATH = config.PROJECT_ROOT / "data" / "warehouse" / "milb.db"
BI = config.DATA_PROCESSED / "bi"
TOL = 0.51  # pandas rounds several columns to whole numbers before writing

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{('  ' + detail) if detail else ''}")
    if not ok:
        failures.append(label)


def compare(name: str, sql: pd.DataFrame, pdf: pd.DataFrame, keys: list[str]) -> None:
    print(f"\n=== {name} ===")
    check(f"{name}: row count", len(sql) == len(pdf), f"sql {len(sql):,} vs pandas {len(pdf):,}")

    sql = sql.sort_values(keys).reset_index(drop=True)
    pdf = pdf.sort_values(keys).reset_index(drop=True)

    for k in keys:
        check(f"{name}: key {k} aligns", sql[k].equals(pdf[k]))

    shared = [c for c in sql.columns if c in pdf.columns and c not in keys]
    for col in shared:
        a, b = sql[col], pdf[col]
        if pd.api.types.is_numeric_dtype(b) and pd.api.types.is_numeric_dtype(a):
            both_null = a.isna() & b.isna()
            diff = (a.astype(float) - b.astype(float)).abs()
            bad = ((diff > TOL) | (a.isna() ^ b.isna())) & ~both_null
            n = int(bad.sum())
            detail = ""
            if n:
                i = bad.idxmax()
                detail = f"{n} rows differ, e.g. row {i}: sql={a.iat[i]!r} pandas={b.iat[i]!r}"
            check(f"{name}.{col}", n == 0, detail)
        else:
            a2 = a.astype("string").fillna("<NA>")
            b2 = b.astype("string").fillna("<NA>")
            bad = a2 != b2
            n = int(bad.sum())
            detail = ""
            if n:
                i = bad.idxmax()
                detail = f"{n} rows differ, e.g. row {i}: sql={a2.iat[i]!r} pandas={b2.iat[i]!r}"
            check(f"{name}.{col}", n == 0, detail)


def main() -> None:
    if not DB_PATH.exists():
        sys.exit("warehouse not built - run: python3 src/load_warehouse.py")

    conn = sqlite3.connect(DB_PATH)

    compare(
        "fct_home_date",
        pd.read_sql("SELECT * FROM fct_home_date", conn),
        pd.read_csv(BI / "fct_home_date.csv"),
        ["team_id", "date_key"],
    )
    compare(
        "dim_club",
        pd.read_sql("SELECT * FROM dim_club", conn),
        pd.read_csv(BI / "dim_club.csv"),
        ["team_id"],
    )

    # The headline number, recomputed entirely in SQL.
    print("\n=== headline, recomputed in SQL ===")
    row = conn.execute("""
        SELECT COUNT(*)                          AS n,
               (EXP(AVG(residual)) - 1) * 100     AS effect_pct,
               AVG(attendance - predicted_attendance) AS extra_fans,
               AVG(predicted_attendance)          AS baseline
        FROM fct_home_date
        WHERE analysis_eligible = 1 AND has_giveaway = 1
    """).fetchone()
    n, eff, fans, base = row
    print(f"  n={n}  effect={eff:+.2f}%  extra fans={fans:.0f}  baseline={base:.0f}")
    check("headline matches published +9.53%", abs(eff - 9.53) < 0.01)
    check("treated date count is 577", n == 577)

    # Known, bounded difference rather than an unexplained one.
    print("\n=== known differences ===")
    a = pd.read_sql("SELECT team_id,date_key,home_win_pct,away_win_pct FROM fct_home_date", conn)
    b = pd.read_csv(BI / "fct_home_date.csv" if False else
                    config.DATA_PROCESSED / "bi_reference" / "fct_home_date.csv",
                    usecols=["team_id", "date_key", "home_win_pct", "away_win_pct"])
    a = a.sort_values(["team_id", "date_key"]).reset_index(drop=True)
    b = b.sort_values(["team_id", "date_key"]).reset_index(drop=True)
    worst = 0.0
    cells = 0
    for col in ("home_win_pct", "away_win_pct"):
        d = (a[col] - b[col]).abs().fillna(0)
        worst = max(worst, float(d.max()))
        cells += int((d > 0).sum())
    print(f"  win-percentage rounding: {cells} cells differ, max {worst:.4f}")
    print("  SQLite rounds half away from zero, numpy rounds half to even.")
    check("rounding difference stays within 0.001", worst <= 0.001 + 1e-9)

    conn.close()

    print()
    if failures:
        print(f"{len(failures)} check(s) failed")
        sys.exit(1)
    print("all checks passed - the SQL star schema reproduces the pandas one")


if __name__ == "__main__":
    main()
