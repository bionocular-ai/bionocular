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

sys.path.insert(0, str(_root))

from supabase import Client, create_client  # noqa: E402

from src.domain.trial_landscape_guard import partition_by_study_type  # noqa: E402

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


def fetch_study_types(nct_ids: list[str]) -> dict[str, str]:
    """Read study_type for these trials from clinical_trials."""
    types: dict[str, str] = {}
    for i in range(0, len(nct_ids), 200):
        response = (
            supabase.table("clinical_trials")
            .select("nct_id,study_type")
            .in_("nct_id", nct_ids[i : i + 200])
            .execute()
        )
        for row in response.data:
            types[row["nct_id"]] = row["study_type"]
    return types


def guard_study_types(records: list[dict]) -> list[dict]:
    """Drop trials this table does not accept, and say which and why."""
    types = fetch_study_types([r["nct_id"] for r in records])
    kept, rejected = partition_by_study_type(records, types)
    if rejected:
        counts: dict[str, int] = {}
        for _, reason in rejected:
            counts[reason] = counts.get(reason, 0) + 1
        print(f"Study-type guard dropped {len(rejected)} record(s):")
        for reason, count in sorted(counts.items(), key=lambda kv: -kv[1]):
            print(f"  {reason}: {count}")
    return list(kept)  # type: ignore[arg-type]


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

    if len(records) != EXPECTED_ROWS and not args.limit:
        raise ValueError(f"Expected {EXPECTED_ROWS} rows, got {len(records)}")

    # Guard first, validate second: a row this table will never accept should not be
    # able to fail validation and block the rows that are fine.
    records = guard_study_types(records)
    validate(records)

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
