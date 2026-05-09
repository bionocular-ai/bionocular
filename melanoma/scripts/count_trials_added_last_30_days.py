#!/usr/bin/env python3
"""Count clinical trials added/updated in the 30 days before our last pull.

All dates are taken from the ClinicalTrials.gov API response (statusModule):
- studyFirstPostDateStruct.date = when the study was first posted on the registry
- lastUpdatePostDateStruct.date = when the record was last updated on the registry

The 30-day window is: [last_pull_date - 30 days, last_pull_date], where
last_pull_date is when we last updated the cache (max(updated_at)).

Usage:
  cd melanoma
  poetry run python scripts/count_trials_added_last_30_days.py
"""

import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.infrastructure.config import CLINICAL_TRIAL_DB_PATH


def parse_iso_date(s: str | None) -> datetime | None:
    """Parse YYYY-MM-DD or YYYY-MM to date at start of day UTC."""
    if not s or not s.strip():
        return None
    s = s.strip()
    try:
        if len(s) >= 10:
            return datetime.strptime(s[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if len(s) >= 7:
            return datetime.strptime(s[:7], "%Y-%m").replace(tzinfo=timezone.utc, day=1)
    except ValueError:
        pass
    return None


def main() -> int:
    db_path = CLINICAL_TRIAL_DB_PATH
    if not Path(db_path).exists():
        print(f"Database not found: {db_path}")
        return 1

    first_posted_in_window = 0
    last_updated_in_window = 0
    total = 0
    no_first_posted = 0
    no_last_updated = 0
    last_cache_updated: datetime | None = None

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # When was our cache last updated? (end of 30-day window – all dates from API)
        cursor.execute("SELECT max(updated_at) as t FROM clinical_trials_cache")
        row = cursor.fetchone()
        if row and row["t"]:
            try:
                last_cache_updated = datetime.fromisoformat(
                    row["t"].replace("Z", "+00:00")
                )
                if last_cache_updated.tzinfo is None:
                    last_cache_updated = last_cache_updated.replace(tzinfo=timezone.utc)
            except ValueError:
                last_cache_updated = None

        if not last_cache_updated:
            print("Cannot determine last pull date (no cache updated_at).")
            return 1

        # 30-day window ending at last pull; trial dates are from ClinicalTrials.gov API
        window_end = last_cache_updated
        cutoff = window_end - timedelta(days=30)

        cursor.execute(
            "SELECT nct_number, api_response_json FROM clinical_trials_cache"
        )
        for row in cursor.fetchall():
            total += 1
            try:
                data = json.loads(row["api_response_json"])
            except (json.JSONDecodeError, TypeError):
                continue
            status = (data.get("protocolSection") or {}).get("statusModule") or {}

            first_posted_struct = status.get("studyFirstPostDateStruct") or {}
            first_posted_str = first_posted_struct.get("date")
            first_posted_dt = parse_iso_date(first_posted_str)
            if first_posted_dt is None:
                no_first_posted += 1
            elif cutoff <= first_posted_dt <= window_end:
                first_posted_in_window += 1

            last_updated_struct = status.get("lastUpdatePostDateStruct") or {}
            last_updated_str = last_updated_struct.get("date")
            last_updated_dt = parse_iso_date(last_updated_str)
            if last_updated_dt is None:
                no_last_updated += 1
            elif cutoff <= last_updated_dt <= window_end:
                last_updated_in_window += 1

    print("Clinical trials – last 30 days (dates from ClinicalTrials.gov API)")
    print("=" * 55)
    print(f"Database: {db_path}")
    print(f"Total trials in cache: {total}")
    print(f"Last pull (window end): {window_end.isoformat()}")
    print(f"Window start (API dates): {cutoff.date().isoformat()}")
    print()
    print("Trials first posted (studyFirstPostDateStruct) in that window:")
    print(f"  {first_posted_in_window}")
    if no_first_posted:
        print(f"  (Trials missing studyFirstPostDateStruct: {no_first_posted})")
    print()
    print("Trials last updated (lastUpdatePostDateStruct) in that window:")
    print(f"  {last_updated_in_window}")
    if no_last_updated:
        print(f"  (Trials missing lastUpdatePostDateStruct: {no_last_updated})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
