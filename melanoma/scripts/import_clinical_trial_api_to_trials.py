#!/usr/bin/env python3
"""Copy api_discovery and clinical_trials_cache from clinical_trial_api.db into trials.db.

Use this when you have a populated clinical_trial_api database and want the main
dashboard to show trial cards from that data. The backend uses trials.db
(CLINICAL_TRIAL_DB_PATH); this script copies the required tables into it.

Usage:
  cd melanoma
  poetry run python scripts/import_clinical_trial_api_to_trials.py
  poetry run python scripts/import_clinical_trial_api_to_trials.py --source path/to/api.db --target path/to/trials.db
"""

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_SOURCE = (
    Path(__file__).parent.parent
    / "data"
    / "clinical_trial_api"
    / "clinical_trial_api.db"
)
DEFAULT_TARGET = Path(__file__).parent.parent / "data" / "trials_db" / "trials.db"


def ensure_tables(conn: sqlite3.Connection) -> None:
    """Ensure clinical_trials_cache and api_discovery exist in target DB."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS clinical_trials_cache (
            nct_number TEXT PRIMARY KEY,
            api_response_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_updated_at ON clinical_trials_cache(updated_at)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS api_discovery (
            nct_number TEXT NOT NULL,
            cancer_type_tag TEXT NOT NULL,
            current_status TEXT NOT NULL,
            discovery_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (nct_number, cancer_type_tag)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cancer_type_tag ON api_discovery(cancer_type_tag)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_api_discovery_nct_number ON api_discovery(nct_number)"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copy api_discovery and clinical_trials_cache from clinical_trial_api.db to trials.db"
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help=f"Source database (default: {DEFAULT_SOURCE})",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=DEFAULT_TARGET,
        help=f"Target database (default: {DEFAULT_TARGET})",
    )
    args = parser.parse_args()

    if not args.source.exists():
        logger.error("Source database not found: %s", args.source)
        return 1

    args.target.parent.mkdir(parents=True, exist_ok=True)

    source_abs = args.source.resolve()
    target_abs = args.target.resolve()

    logger.info("Source: %s", source_abs)
    logger.info("Target: %s", target_abs)

    try:
        src_conn = sqlite3.connect(str(source_abs))
        tgt_conn = sqlite3.connect(str(target_abs))

        src_cur = src_conn.cursor()
        src_cur.execute("SELECT COUNT(*) FROM clinical_trials_cache")
        cache_count = src_cur.fetchone()[0]
        src_cur.execute("SELECT COUNT(*) FROM api_discovery")
        discovery_count = src_cur.fetchone()[0]

        if cache_count == 0 and discovery_count == 0:
            logger.warning(
                "Source has no rows in clinical_trials_cache or api_discovery. Nothing to copy."
            )
            src_conn.close()
            tgt_conn.close()
            return 0

        ensure_tables(tgt_conn)
        tgt_cur = tgt_conn.cursor()

        src_cur.execute(
            "SELECT nct_number, api_response_json, created_at, updated_at, last_accessed_at FROM clinical_trials_cache"
        )
        rows = src_cur.fetchall()
        tgt_cur.executemany(
            """
            INSERT OR REPLACE INTO clinical_trials_cache
            (nct_number, api_response_json, created_at, updated_at, last_accessed_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )
        logger.info("Copied %s rows into clinical_trials_cache", len(rows))

        src_cur.execute(
            "SELECT nct_number, cancer_type_tag, current_status, discovery_date, is_active, updated_at FROM api_discovery"
        )
        rows = src_cur.fetchall()
        tgt_cur.executemany(
            """
            INSERT OR REPLACE INTO api_discovery
            (nct_number, cancer_type_tag, current_status, discovery_date, is_active, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        logger.info("Copied %s rows into api_discovery", len(rows))

        tgt_conn.commit()
        src_conn.close()
        tgt_conn.close()

        logger.info(
            "Done. Dashboard trials will use this data when backend points at %s",
            target_abs,
        )
        return 0

    except sqlite3.Error as e:
        logger.error("Database error: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
