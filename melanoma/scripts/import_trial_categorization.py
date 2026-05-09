#!/usr/bin/env python3
"""Import trial extraction CSVs into trial_categorization table.

All CSV columns map directly to the table. Rows are upserted
(INSERT OR REPLACE) so re-running is safe.
"""

import csv
import sqlite3
import sys
from pathlib import Path

_DB = Path(__file__).parent.parent / "data" / "trials_db" / "trials.db"

_CSV_FILES = [
    "data/output/trials_extraction/1-300_trials.csv",
    "data/output/trials_extraction/301-600_trials.csv",
    "data/output/trials_extraction/601-900_trials.csv",
    "data/output/trials_extraction/901-1200_trials.csv",
    "data/output/trials_extraction/1201-1224_trials.csv",
    "data/output/trials_extraction/1225-1274_trials.csv",
    "data/output/trials_extraction/1275-1324_trials.csv",
    "data/output/trials_extraction/1325-1424_trials.csv",
]

_UPSERT = """
    INSERT OR REPLACE INTO trial_categorization (
        nct_number,
        cancer_type,
        treatment_name,
        modality,
        biomarker,
        stage,
        line_of_therapy,
        previous_treatment_criteria,
        extraction_status,
        error_message,
        updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
"""


def _cell(row: dict, key: str) -> str | None:
    v = (row.get(key) or "").strip()
    return v or None


def _load_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main() -> int:
    root = Path(__file__).parent.parent
    conn = sqlite3.connect(_DB)

    total_inserted = 0
    total_skipped = 0

    with conn:
        for rel in _CSV_FILES:
            path = root / rel
            if not path.exists():
                print(f"  MISSING  {rel}", file=sys.stderr)
                continue

            rows = _load_csv(path)
            inserted = 0
            skipped = 0
            for row in rows:
                nct = (row.get("nct_number") or "").strip()
                if not nct:
                    skipped += 1
                    continue
                conn.execute(
                    _UPSERT,
                    (
                        nct,
                        _cell(row, "cancer_type"),
                        _cell(row, "treatment_name"),
                        _cell(row, "modality"),
                        _cell(row, "biomarker"),
                        _cell(row, "stage"),
                        _cell(row, "line_of_therapy"),
                        _cell(row, "previous_treatment_criteria"),
                        _cell(row, "extraction_status"),
                        _cell(row, "error_message"),
                    ),
                )
                inserted += 1

            print(f"  {inserted:>4} inserted  {skipped:>3} skipped  ← {rel}")
            total_inserted += inserted
            total_skipped += skipped

    final = conn.execute("SELECT COUNT(*) FROM trial_categorization").fetchone()[0]
    conn.close()

    print(f"\nDone — {total_inserted} rows upserted, {total_skipped} skipped.")
    print(f"trial_categorization now has {final} rows.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
