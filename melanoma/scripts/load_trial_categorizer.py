#!/usr/bin/env python3
"""Load trial_categorizer.txt (NCT, Modality) into trial_categorization table.

The table lives in the same SQLite DB as clinical_trials_cache and api_discovery
(trials.db). Creates the table if missing.

Usage:
  cd melanoma
  poetry run python scripts/load_trial_categorizer.py
  poetry run python scripts/load_trial_categorizer.py --input data/output/trial_categorizer.txt --db data/trials_db/trials.db
  poetry run python scripts/load_trial_categorizer.py --export-seed   # write data/deployed/trial_categorization_seed.json for Docker build
"""

import argparse
import csv
import json
import logging
import sqlite3
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_INPUT = (
    Path(__file__).parent.parent / "data" / "output" / "trial_categorizer.txt"
)
DEFAULT_DB = Path(__file__).parent.parent / "data" / "trials_db" / "trials.db"
DEFAULT_SEED_OUT = (
    Path(__file__).parent.parent / "data" / "deployed" / "trial_categorization_seed.json"
)


def ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS trial_categorization (
            nct_number TEXT PRIMARY KEY,
            cancer_type TEXT,
            modality TEXT,
            treatment_name TEXT,
            biomarker TEXT,
            stage TEXT,
            line_of_therapy TEXT,
            previous_treatment_criteria TEXT,
            extraction_status TEXT,
            error_message TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    # Add cancer_type to existing DBs created before this column existed (before creating index on it)
    try:
        conn.execute("ALTER TABLE trial_categorization ADD COLUMN cancer_type TEXT")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e).lower():
            raise
    # Recreate table with cancer_type right after nct_number if it's currently at the end
    cur = conn.execute("PRAGMA table_info(trial_categorization)")
    cols = [row[1] for row in cur.fetchall()]
    if len(cols) >= 2 and cols[1] != "cancer_type":
        _recreate_trial_categorization_column_order(conn)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_trial_categorization_modality ON trial_categorization(modality)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_trial_categorization_cancer_type ON trial_categorization(cancer_type)"
    )


def _recreate_trial_categorization_column_order(conn: sqlite3.Connection) -> None:
    """Recreate trial_categorization so cancer_type is the second column (after nct_number)."""
    cur = conn.execute("PRAGMA table_info(trial_categorization)")
    existing_cols = {r[1] for r in cur.fetchall()}

    desired_cols = [
        "nct_number",
        "cancer_type",
        "modality",
        "treatment_name",
        "biomarker",
        "stage",
        "line_of_therapy",
        "previous_treatment_criteria",
        "extraction_status",
        "error_message",
        "updated_at",
    ]

    conn.execute(
        """
        CREATE TABLE trial_categorization_new (
            nct_number TEXT PRIMARY KEY,
            cancer_type TEXT,
            modality TEXT,
            treatment_name TEXT,
            biomarker TEXT,
            stage TEXT,
            line_of_therapy TEXT,
            previous_treatment_criteria TEXT,
            extraction_status TEXT,
            error_message TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    insert_cols = ",".join(desired_cols)
    select_exprs: list[str] = []
    for col in desired_cols:
        if col in existing_cols:
            select_exprs.append(col)
        else:
            select_exprs.append("NULL")

    conn.execute(
        f"""
        INSERT INTO trial_categorization_new ({insert_cols})
        SELECT {','.join(select_exprs)}
        FROM trial_categorization
        """
    )
    conn.execute("DROP TABLE trial_categorization")
    conn.execute("ALTER TABLE trial_categorization_new RENAME TO trial_categorization")


def _backfill_cancer_type_from_api_discovery(conn: sqlite3.Connection) -> None:
    """Set trial_categorization.cancer_type from api_discovery (all tags per NCT, comma-separated)."""
    conn.execute(
        """
        UPDATE trial_categorization
        SET cancer_type = (
            SELECT group_concat(ad.cancer_type_tag, ', ')
            FROM (
                SELECT cancer_type_tag
                FROM api_discovery ad
                WHERE ad.nct_number = trial_categorization.nct_number
                ORDER BY ad.cancer_type_tag
            ) ad
        )
        WHERE EXISTS (
            SELECT 1 FROM api_discovery ad
            WHERE ad.nct_number = trial_categorization.nct_number
        )
        """
    )


def _parse_categorizer_file(input_path: Path) -> list[tuple[str, str | None]]:
    rows: list[tuple[str, str | None]] = []
    with open(input_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, fieldnames=("NCT", "Modality", "Target", "Trial_Name"))
        for rec in reader:
            nct = (rec.get("NCT") or "").strip().strip('"')
            if not nct or nct.upper() == "NCT":
                continue
            modality = (rec.get("Modality") or "").strip().strip('"') or None
            rows.append((nct, modality))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Load trial_categorizer.txt into trial_categorization table"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Path to trial_categorizer.txt (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help=f"Path to trials SQLite DB (default: {DEFAULT_DB})",
    )
    parser.add_argument(
        "--export-seed",
        action="store_true",
        help="Write trial_categorization_seed.json to data/deployed/ for Docker build (optional: also load into DB)",
    )
    parser.add_argument(
        "--seed-out",
        type=Path,
        default=DEFAULT_SEED_OUT,
        help=f"Path for --export-seed output (default: {DEFAULT_SEED_OUT})",
    )
    args = parser.parse_args()

    if not args.input.exists():
        logger.error("Input file not found: %s", args.input)
        return 1

    try:
        rows = _parse_categorizer_file(args.input)
    except OSError as e:
        logger.error("Error reading input: %s", e)
        return 1

    if args.export_seed:
        args.seed_out.parent.mkdir(parents=True, exist_ok=True)
        seed_data = [
            {"nct_number": r[0], "modality": r[1]}
            for r in rows
        ]
        with open(args.seed_out, "w", encoding="utf-8") as f:
            json.dump(seed_data, f, indent=2)
        logger.info("Wrote %s rows to %s", len(seed_data), args.seed_out)
        return 0

    args.db.parent.mkdir(parents=True, exist_ok=True)

    try:
        conn = sqlite3.connect(str(args.db))
        ensure_table(conn)
        conn.execute("DELETE FROM trial_categorization")
        conn.executemany(
            """
            INSERT INTO trial_categorization (nct_number, modality)
            VALUES (?, ?)
            """,
            rows,
        )
        _backfill_cancer_type_from_api_discovery(conn)
        conn.commit()
        conn.close()

        logger.info("Loaded %s rows into trial_categorization at %s", len(rows), args.db)
        return 0

    except (sqlite3.Error, OSError) as e:
        logger.error("Error: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
