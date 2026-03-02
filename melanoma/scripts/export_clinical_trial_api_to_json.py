#!/usr/bin/env python3
"""Export clinical_trials_cache and api_discovery from clinical_trial_api.db to JSON.

Use this to produce a seed file that can be baked into the Docker image so
production has trial API data without calling the API at deploy or startup.

Usage:
  cd melanoma
  poetry run python scripts/export_clinical_trial_api_to_json.py
  poetry run python scripts/export_clinical_trial_api_to_json.py --source path/to/api.db --out data/deployed/clinical_trials_api_seed.json
  poetry run python scripts/export_clinical_trial_api_to_json.py --gzip   # write .json.gz (compact) for smaller commit
  poetry run python scripts/export_clinical_trial_api_to_json.py --compact  # write compact JSON (no indent)
"""

import argparse
import gzip
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

DEFAULT_SOURCE = (
    Path(__file__).parent.parent / "data" / "clinical_trial_api" / "clinical_trial_api.db"
)
DEFAULT_OUT = (
    Path(__file__).parent.parent / "data" / "deployed" / "clinical_trials_api_seed.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export clinical_trials_cache and api_discovery to JSON for deployment"
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help=f"Source database (default: {DEFAULT_SOURCE})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output JSON file (default: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Write compact JSON (no indentation) for smaller file size",
    )
    parser.add_argument(
        "--gzip",
        action="store_true",
        help="Write gzipped JSON (.json.gz). Implies --compact. Use for deployment seed under GitHub limit.",
    )
    args = parser.parse_args()

    if args.gzip:
        args.compact = True
    out_path = args.out
    if args.gzip and out_path.suffix != ".gz":
        out_path = Path(str(out_path) + ".gz")

    if not args.source.exists():
        logger.error("Source database not found: %s", args.source)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)

    try:
        conn = sqlite3.connect(str(args.source))
        cur = conn.cursor()

        cur.execute(
            "SELECT nct_number, api_response_json, created_at, updated_at, last_accessed_at "
            "FROM clinical_trials_cache"
        )
        cache_rows = cur.fetchall()
        clinical_trials_cache = [
            {
                "nct_number": r[0],
                "api_response_json": r[1],
                "created_at": r[2],
                "updated_at": r[3],
                "last_accessed_at": r[4],
            }
            for r in cache_rows
        ]

        cur.execute(
            "SELECT nct_number, cancer_type_tag, current_status, discovery_date, is_active, updated_at "
            "FROM api_discovery"
        )
        discovery_rows = cur.fetchall()
        api_discovery = [
            {
                "nct_number": r[0],
                "cancer_type_tag": r[1],
                "current_status": r[2],
                "discovery_date": r[3],
                "is_active": r[4],
                "updated_at": r[5],
            }
            for r in discovery_rows
        ]

        conn.close()

        out_data = {
            "clinical_trials_cache": clinical_trials_cache,
            "api_discovery": api_discovery,
        }
        indent = None if args.compact else 2
        if args.gzip:
            with gzip.open(out_path, "wt", encoding="utf-8") as f:
                json.dump(out_data, f, indent=indent, default=str)
        else:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(out_data, f, indent=indent, default=str)

        logger.info(
            "Exported %s cache rows and %s discovery rows to %s",
            len(clinical_trials_cache),
            len(api_discovery),
            out_path,
        )
        return 0

    except (sqlite3.Error, OSError) as e:
        logger.error("Error: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
