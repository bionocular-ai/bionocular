#!/usr/bin/env python3
"""
Export `trial_categorization` rows from SQLite into `trial_categorization_seed.json`.

The goal is to make the JSON schema match the SQLite table schema so that
`melanoma/scripts/build_db.py` can recreate/fill the table on Render (during build).

This exports *all* columns that currently exist on `trial_categorization` in the DB.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


DEFAULT_DB = Path(__file__).parent.parent / "data" / "trials_db" / "trials.db"
DEFAULT_OUT = (
    Path(__file__).parent.parent / "data" / "deployed" / "trial_categorization_seed.json"
)


def export_seed(db_path: Path, out_path: Path) -> int:
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(trial_categorization)")
        table_cols = [r[1] for r in cur.fetchall()]
        if not table_cols:
            raise SystemExit("trial_categorization table has no columns")

        cols_sql = ", ".join(table_cols)
        cur.execute(
            f"""
            SELECT {cols_sql}
            FROM trial_categorization
            ORDER BY nct_number
            """
        )
        rows = cur.fetchall()
        payload = [
            {col: r[col] for col in table_cols}
            for r in rows
        ]
    finally:
        conn.close()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"Wrote {len(payload)} rows to {out_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export trial_categorization from trials.db into trial_categorization_seed.json"
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB,
        help=f"Path to trials SQLite DB (default: {DEFAULT_DB})",
    )
    parser.add_argument(
        "--out-path",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Path for output JSON seed (default: {DEFAULT_OUT})",
    )
    args = parser.parse_args()
    return export_seed(args.db_path, args.out_path)


if __name__ == "__main__":
    raise SystemExit(main())

