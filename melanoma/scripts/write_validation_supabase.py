"""
Write an adjudicated validation patch to Supabase.

Update-only: one UPDATE per row carrying just the columns that changed. Nothing is
deleted, nothing is inserted, and rows of any other source_type are never touched.
The patch is derived by diffing the baseline export against the patched CSV produced by
apply_<cohort>_validation.py, so this script cannot invent a change of its own.

Refuses to run if the live table has drifted from the baseline export since it was taken.

Usage:
    cd melanoma
    poetry run python3 scripts/write_validation_supabase.py --source-type abstract
    poetry run python3 scripts/write_validation_supabase.py --source-type abstract --execute
"""

import argparse
import csv
import datetime
import json
import os
import pathlib
import sys

from dotenv import load_dotenv

_here = pathlib.Path(__file__).parent
_root = _here.parent

load_dotenv(_root / ".env")

from supabase import Client, create_client  # noqa: E402

BASELINE_CSV = _root / "data/backups/trial_outcomes_rows.csv"
BACKUP_DIR = _root / "data/backups"


def patched_csv_for(source_type: str) -> pathlib.Path:
    directory = _root / f"data/validation/{source_type}s_adjudication"
    return directory / "trial_outcomes_rows.patched.csv"


ARRAY_COLUMNS = {"cancer_type", "is_nr", "is_lt"}
INT_COLUMNS = {"num_patients"}
TIMESTAMP_COLUMNS = {"created_at", "validated_at"}
JSON_COLUMNS = {"all_attributes"}
TEXT_COLUMNS = {
    "id",
    "source_type",
    "source_name",
    "abstract_id",
    "publication_id",
    "source_url",
    "nct_id",
    "arm_id",
    "arm_name",
    "sponsors",
    "line_of_treatment",
    "generic_name",
    "brand_name",
    "dosage",
    "type_of_dosing",
    "mechanism_of_action",
    "target_protein",
    "type_of_therapy",
    "sub_therapy",
    "modality",
    "validation_status",
    "ci_hr_pfs",
    "ci_hr_os",
    "ci_hr_efs",
    "ci_hr_rfs",
    "ci_hr_mfs",
    "ci_hr_ttp",
}
# Columns the export renders differently from the API; excluded from the drift check.
# all_attributes is the extractor's own audit blob: the API returns it as a Python object
# and the export as JSON text, so the two never compare equal. The patchers exclude the
# column, so it is never written and its rendering cannot mask a real drift.
DRIFT_EXEMPT = {"created_at", "all_attributes"}


def to_db(column: str, raw: str) -> object:
    """Convert a CSV cell to the value the column's Postgres type expects."""
    if raw in ("", None):
        return None
    if column in ARRAY_COLUMNS or column in JSON_COLUMNS:
        return json.loads(raw)
    if column in INT_COLUMNS:
        return int(float(raw))
    if column in TEXT_COLUMNS or column in TIMESTAMP_COLUMNS:
        return raw
    return float(raw)


def canonical(column: str, value: object) -> str:
    """Comparable form for a value, whichever side it came from."""
    if value in ("", None):
        return ""
    # Marker arrays are sets of column names; element order carries no meaning, so
    # a reordering must not read as a change worth writing.
    if isinstance(value, list):
        return json.dumps(sorted(value), separators=(",", ":"))
    if isinstance(value, str) and column in ARRAY_COLUMNS:
        return json.dumps(sorted(json.loads(value)), separators=(",", ":"))
    if column in TEXT_COLUMNS or column in TIMESTAMP_COLUMNS or column in JSON_COLUMNS:
        return str(value)
    try:
        return str(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return str(value)


def read_rows(path: pathlib.Path, source_type: str) -> dict[str, dict]:
    csv.field_size_limit(10_000_000)
    with open(path, newline="") as handle:
        return {
            row["id"]: row
            for row in csv.DictReader(handle)
            if row["source_type"] == source_type
        }


def fetch_live(client: Client, source_type: str) -> dict[str, dict]:
    rows: list[dict] = []
    page = 500
    start = 0
    while True:
        response = (
            client.table("trial_outcomes")
            .select("*")
            .eq("source_type", source_type)
            .range(start, start + page - 1)
            .execute()
        )
        rows += response.data
        if len(response.data) < page:
            break
        start += page
    return {row["id"]: row for row in rows}


def find_drift(
    live: dict[str, dict], baseline: dict[str, dict]
) -> list[tuple[str, str, str, str]]:
    drift: list[tuple[str, str, str, str]] = []
    for row_id, base_row in baseline.items():
        live_row = live.get(row_id)
        if live_row is None:
            drift.append((row_id, "<row>", "present", "missing"))
            continue
        for column, base_value in base_row.items():
            if column in DRIFT_EXEMPT or column not in live_row:
                continue
            live_canonical = canonical(column, live_row[column])
            base_canonical = canonical(column, base_value)
            if live_canonical != base_canonical:
                drift.append((row_id, column, base_canonical[:40], live_canonical[:40]))
    return drift


def build_patches(
    baseline: dict[str, dict], patched: dict[str, dict]
) -> dict[str, dict]:
    patches: dict[str, dict] = {}
    for row_id, patched_row in patched.items():
        base_row = baseline[row_id]
        payload = {
            column: to_db(column, value)
            for column, value in patched_row.items()
            if canonical(column, value) != canonical(column, base_row.get(column, ""))
        }
        if payload:
            patches[row_id] = payload
    return patches


def drop_unreferencable_nct_ids(
    client: Client, patches: dict[str, dict]
) -> list[tuple[str, str]]:
    """Remove nct_id corrections that point at a trial clinical_trials does not hold.

    trial_outcomes.nct_id carries a foreign key onto clinical_trials, which is scoped to
    skin-cancer trials. A basket trial registered for "advanced solid tumors" that then
    publishes a melanoma subgroup abstract has a real registry id with no row to
    reference. Postgres rejects the whole UPDATE, so one unwritable column takes that
    row's unrelated corrections down with it. Drop the column and keep the rest; the
    correction is reported rather than silently applied.
    """
    wanted = {
        row_id: payload["nct_id"]
        for row_id, payload in patches.items()
        if payload.get("nct_id")
    }
    if not wanted:
        return []
    known: set[str] = set()
    for start in range(0, 20000, 1000):
        response = (
            client.table("clinical_trials")
            .select("nct_id")
            .range(start, start + 999)
            .execute()
        )
        known |= {row["nct_id"] for row in response.data}
        if len(response.data) < 1000:
            break
    dropped = [
        (row_id, str(nct_id))
        for row_id, nct_id in wanted.items()
        if nct_id not in known
    ]
    for row_id, _ in dropped:
        del patches[row_id]["nct_id"]
        if not patches[row_id]:
            del patches[row_id]
    return dropped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute", action="store_true", help="Perform the writes (default: dry run)"
    )
    parser.add_argument(
        "--source-type",
        default="publication",
        choices=["publication", "abstract"],
        help="Which cohort's patch to write (default: publication)",
    )
    parser.add_argument("--patched", default=None)
    parser.add_argument("--baseline", default=str(BASELINE_CSV))
    parser.add_argument(
        "--only-id",
        default=None,
        help="Restrict to one row id, to retry a row an earlier run could not write",
    )
    args = parser.parse_args()

    source_type = args.source_type
    patched_path = pathlib.Path(args.patched or patched_csv_for(source_type))

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        print("SUPABASE_URL and SUPABASE_KEY must be set in melanoma/.env")
        sys.exit(1)
    client: Client = create_client(url, key)

    baseline = read_rows(pathlib.Path(args.baseline), source_type)
    patched = read_rows(patched_path, source_type)
    if set(baseline) != set(patched):
        print("Baseline and patched CSVs cover different rows; refusing to continue.")
        sys.exit(1)
    print(f"Baseline and patched agree on {len(baseline)} {source_type} rows")

    if args.only_id:
        if args.only_id not in baseline:
            print(f"{args.only_id} is not a {source_type} row in the CSVs.")
            sys.exit(1)
        baseline = {args.only_id: baseline[args.only_id]}
        patched = {args.only_id: patched[args.only_id]}
        print(f"Restricted to {args.only_id}")

    live = fetch_live(client, source_type)
    print(f"Live {source_type} rows: {len(live)}")

    drift = find_drift(live, baseline)
    if drift:
        print(
            f"ABORT: {len(drift)} cells drifted from the baseline export since it was taken."
        )
        for row in drift[:20]:
            print(f"  {row[0]} {row[1]}: export={row[2]!r} live={row[3]!r}")
        sys.exit(1)
    print("Drift check clean: live table matches the baseline export")

    patches = build_patches(baseline, patched)
    unreferencable = drop_unreferencable_nct_ids(client, patches)
    for row_id, nct_id in unreferencable:
        print(f"  ! {row_id}: {nct_id} has no clinical_trials row; nct_id left as-is")
    cells = sum(len(payload) for payload in patches.values())
    print(f"{len(patches)} rows to update, {cells} columns total")

    if not args.execute:
        print("\n[dry run] first 3 payloads:")
        for row_id, payload in list(patches.items())[:3]:
            print(f"\n  {row_id}  ({len(payload)} columns)")
            for column, value in sorted(payload.items()):
                before = baseline[row_id].get(column, "")
                print(f"    {column}: {before!r} -> {value!r}")
        print("\n[dry run] no writes performed. Re-run with --execute.")
        return

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = BACKUP_DIR / f"trial_outcomes_{source_type}s_{stamp}.json"
    backup_path.write_text(json.dumps(list(live.values()), indent=1, default=str))
    print(f"Backed up {len(live)} live rows to {backup_path}")

    failures: list[tuple[str, str]] = []
    for index, (row_id, payload) in enumerate(patches.items(), start=1):
        try:
            client.table("trial_outcomes").update(payload).eq("id", row_id).execute()
        except Exception as error:  # noqa: BLE001 - surface any row failure, keep going
            failures.append((row_id, str(error)))
            print(f"  x {row_id}: {error}")
        if index % 25 == 0:
            print(f"  {index}/{len(patches)} rows written")
    print(f"Wrote {len(patches) - len(failures)}/{len(patches)} rows")

    after = fetch_live(client, source_type)
    # A dropped nct_id is a known, reported divergence, not a failed write.
    left_alone = {row_id for row_id, _ in unreferencable}
    remaining = [
        (row_id, column)
        for row_id, row in patched.items()
        for column in row
        if column in after[row_id]
        and column not in DRIFT_EXEMPT
        and not (column == "nct_id" and row_id in left_alone)
        and canonical(column, after[row_id][column]) != canonical(column, row[column])
    ]
    if remaining:
        print(
            f"VERIFY FAILED: {len(remaining)} cells still differ from the patched CSV"
        )
        for row in remaining[:20]:
            print(f"  {row[0]} {row[1]}")
        sys.exit(1)
    print(
        f"Verified: live table matches the patched CSV on all "
        f"{len(patched)} {source_type} rows"
    )
    if failures:
        print(f"{len(failures)} row updates reported errors; see above")
        sys.exit(1)


if __name__ == "__main__":
    main()
