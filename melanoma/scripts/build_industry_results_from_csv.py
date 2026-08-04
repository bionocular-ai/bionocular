#!/usr/bin/env python3
"""Rebuild a validation-ready results.json from the March industry extraction CSVs.

The industry cohort was extracted in March in per-batch CSVs
(`data/output/trials_extraction/*_trials.csv`); its consolidated results.json was
overwritten down to the last 300-row batch, so it cannot feed the validation
pipeline as-is. This script concatenates all batch CSVs and reshapes each row into
the `TrialParameterResult.to_dict` layout the judge expects: the six multi-value
fields become lists (split on '; '), treatment_name / nct_number stay strings, and
extraction_status / error_message are preserved for the status-consistency rule.

The output carries no `snapshot_sha256` (the original snapshot is gone); the
validator only warns on that and proceeds, which is fine for an advisory audit.

Usage:
    cd melanoma
    poetry run python3 scripts/build_industry_results_from_csv.py
    poetry run python3 scripts/build_industry_results_from_csv.py --out /tmp/r.json
"""

import argparse
import csv
import glob
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

_MELANOMA_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CSV_DIR = _MELANOMA_ROOT / "data" / "output" / "trials_extraction"
_DEFAULT_OUT = (
    _MELANOMA_ROOT / "data" / "output" / "trials_extraction_industry" / "results.json"
)

# Multi-value fields the CSV stores as '; '-joined text; the judge and the
# deterministic validator (trial_deterministic_validator._LIST_FIELDS) require lists.
_LIST_FIELDS = (
    "cancer_type",
    "modality",
    "biomarker",
    "stage",
    "line_of_therapy",
    "previous_treatment_criteria",
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _split(value: str) -> list[str]:
    """Split a '; '-joined CSV cell back into a list; empty cell -> empty list."""
    return [part.strip() for part in value.split(";") if part.strip()]


def reshape_row(row: dict) -> dict:
    """Map one CSV row onto the TrialParameterResult.to_dict shape."""
    record: dict = {
        "nct_number": row["nct_number"],
        "treatment_name": row["treatment_name"],
        "extraction_status": row["extraction_status"],
        "error_message": row["error_message"],
    }
    for field in _LIST_FIELDS:
        record[field] = _split(row[field])
    return record


def load_rows(csv_dir: Path) -> list[dict]:
    """Concatenate every *_trials.csv batch under csv_dir, sorted by NCT number."""
    rows: list[dict] = []
    for path in sorted(glob.glob(str(csv_dir / "*_trials.csv"))):
        with open(path, newline="") as handle:
            rows.extend(reshape_row(r) for r in csv.DictReader(handle))
    rows.sort(key=lambda r: r["nct_number"])
    return rows


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="build_industry_results_from_csv",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--csv-dir", type=Path, default=_DEFAULT_CSV_DIR, metavar="DIR")
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT, metavar="PATH")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    rows = load_rows(args.csv_dir)
    duplicates = len(rows) - len({r["nct_number"] for r in rows})
    if duplicates:
        logger.warning("Found %d duplicate NCT numbers across batches", duplicates)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": {
            "source": "trials_extraction/*_trials.csv (March industry extraction)",
            "rebuilt_at": datetime.now(timezone.utc).isoformat(),
            "total_trials": len(rows),
        },
        "trials": rows,
    }
    args.out.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info("Wrote %d trials to %s", len(rows), args.out)


if __name__ == "__main__":
    main()
