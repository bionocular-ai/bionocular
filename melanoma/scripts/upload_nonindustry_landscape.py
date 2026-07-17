"""
Upload non-industry trial parameter extractions into the Supabase trial_landscape table.

Source is the cleaned extraction output (rows with empty treatment_name already
dropped). The live table stores multi-values as '; '-joined text on every column
except cancer_type, which is text[].

Usage:
    cd melanoma
    poetry run python3 scripts/upload_nonindustry_landscape.py --dry-run
    poetry run python3 scripts/upload_nonindustry_landscape.py --limit 5
    poetry run python3 scripts/upload_nonindustry_landscape.py
"""

import argparse
import json
import os
import pathlib
import re
import sys

from dotenv import load_dotenv

load_dotenv()

_here = pathlib.Path(__file__).parent
_root = _here.parent

from supabase import Client, create_client  # noqa: E402

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
if not url or not key:
    print("SUPABASE_URL and SUPABASE_KEY must be set in .env")
    sys.exit(1)

supabase: Client = create_client(url, key)

DEFAULT_JSON = str(
    _root / "data/output/trials_extraction_nonindustry/results.cleaned.json"
)

EXPECTED_ROWS = 1679
NCT_RE = re.compile(r"^NCT\d{8}$")
BATCH_SIZE = 500

# Columns the live table stores as '; '-joined text. cancer_type is text[] and
# treatment_name is a plain string, so neither is listed here.
JOINED_COLUMNS = (
    "modality",
    "biomarker",
    "stage",
    "line_of_therapy",
    "previous_treatment_criteria",
)


def map_record(trial: dict) -> dict:
    """Map one extraction row onto the live trial_landscape schema.

    Extraction emits nct_number and a list for every parameter; the table keys on
    nct_id and stores every parameter but cancer_type as '; '-joined text. Fields
    with no live column (extraction_status, error_message, extracted_at) are
    dropped — PostgREST rejects unknown keys.
    """
    record = {
        "nct_id": trial["nct_number"],
        "cancer_type": trial["cancer_type"],
        "treatment_name": trial["treatment_name"],
    }
    for col in JOINED_COLUMNS:
        values = trial[col]
        record[col] = "; ".join(values) if values else None
    return record


def validate(records: list[dict]) -> None:
    """Fail loudly before any write if the payload violates the table's invariants."""
    for r in records:
        if not NCT_RE.match(r["nct_id"]):
            raise ValueError(f"Malformed nct_id: {r['nct_id']!r}")
        if not r["treatment_name"]:
            raise ValueError(f"{r['nct_id']}: empty treatment_name")
        if not isinstance(r["cancer_type"], list):
            raise ValueError(f"{r['nct_id']}: cancer_type is not a list")

    duplicates = len(records) - len({r["nct_id"] for r in records})
    if duplicates:
        raise ValueError(f"{duplicates} duplicate nct_id(s) in payload")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default=DEFAULT_JSON)
    parser.add_argument(
        "--dry-run", action="store_true", help="Map and validate, but write nothing"
    )
    parser.add_argument("--limit", type=int, help="Upload only the first N records")
    args = parser.parse_args()

    with open(args.file) as f:
        trials = json.load(f)["trials"]

    records = [map_record(t) for t in trials]
    validate(records)

    if len(records) != EXPECTED_ROWS and not args.limit:
        raise ValueError(f"Expected {EXPECTED_ROWS} rows, got {len(records)}")

    if args.limit:
        records = records[: args.limit]

    print(f"Mapped {len(records)} records from {args.file}")

    if args.dry_run:
        print("\nFirst mapped record:")
        print(json.dumps(records[0], indent=2))
        print("\n--dry-run: nothing written")
        return

    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i : i + BATCH_SIZE]
        supabase.table("trial_landscape").upsert(batch, on_conflict="nct_id").execute()
        print(f"  ✓ upserted {i + len(batch)} / {len(records)}")

    print(f"Done: {len(records)} records upserted into trial_landscape")


if __name__ == "__main__":
    main()
