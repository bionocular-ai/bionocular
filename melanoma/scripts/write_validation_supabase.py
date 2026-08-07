"""
Write an adjudicated validation patch to Supabase.

Update-only: one UPDATE per row carrying just the columns that changed. Nothing is
deleted, nothing is inserted, and rows outside the selected cohort are never touched.
The patch is derived by diffing the baseline export against the patched CSV produced by
the matching apply_*_validation.py, so this script cannot invent a change of its own.

Refuses to run if the live table has drifted from the baseline export since it was taken.

Two tables are served. trial_outcomes is keyed by `id` and split into cohorts by
`source_type`; trial_landscape is keyed by `nct_id` and has no cohort column, so its
whole patched export is one unit.

Usage:
    cd melanoma
    poetry run python3 scripts/write_validation_supabase.py --source-type abstract
    poetry run python3 scripts/write_validation_supabase.py --source-type abstract --execute
    poetry run python3 scripts/write_validation_supabase.py --table trial_landscape
    poetry run python3 scripts/write_validation_supabase.py --table trial_landscape --execute
"""

import argparse
import csv
import dataclasses
import datetime
import json
import os
import pathlib
import sys
from typing import cast

from dotenv import load_dotenv

_here = pathlib.Path(__file__).parent
_root = _here.parent

load_dotenv(_root / ".env")

from supabase import Client, create_client  # noqa: E402

BACKUP_DIR = _root / "data/backups"

OUTCOMES_ARRAY_COLUMNS = {"cancer_type", "is_nr", "is_lt"}
OUTCOMES_INT_COLUMNS = {"num_patients"}
OUTCOMES_TIMESTAMP_COLUMNS = {"created_at", "validated_at"}
OUTCOMES_JSON_COLUMNS = {"all_attributes"}
OUTCOMES_TEXT_COLUMNS = {
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
OUTCOMES_DRIFT_EXEMPT = {"created_at", "all_attributes"}

LANDSCAPE_COLUMNS = {
    "nct_id",
    "treatment_name",
    "modality",
    "biomarker",
    "stage",
    "line_of_therapy",
    "previous_treatment_criteria",
}


@dataclasses.dataclass(frozen=True)
class TableSpec:
    """Everything that differs between the two tables this script can write."""

    table: str
    key: str
    baseline_csv: pathlib.Path
    patched_name: str
    # None when the table has no cohort column and the whole export is one unit.
    cohort_column: str | None
    array_columns: frozenset[str]
    int_columns: frozenset[str]
    timestamp_columns: frozenset[str]
    json_columns: frozenset[str]
    text_columns: frozenset[str]
    drift_exempt: frozenset[str]

    def patched_csv(self, cohort: str | None) -> pathlib.Path:
        directory = "trials" if cohort is None else f"{cohort}s"
        return _root / f"data/validation/{directory}_adjudication" / self.patched_name


SPECS = {
    "trial_outcomes": TableSpec(
        table="trial_outcomes",
        key="id",
        baseline_csv=_root / "data/backups/trial_outcomes_rows.csv",
        patched_name="trial_outcomes_rows.patched.csv",
        cohort_column="source_type",
        array_columns=frozenset(OUTCOMES_ARRAY_COLUMNS),
        int_columns=frozenset(OUTCOMES_INT_COLUMNS),
        timestamp_columns=frozenset(OUTCOMES_TIMESTAMP_COLUMNS),
        json_columns=frozenset(OUTCOMES_JSON_COLUMNS),
        text_columns=frozenset(OUTCOMES_TEXT_COLUMNS),
        drift_exempt=frozenset(OUTCOMES_DRIFT_EXEMPT),
    ),
    "trial_landscape": TableSpec(
        table="trial_landscape",
        key="nct_id",
        baseline_csv=_root / "data/backups/trial_landscape_rows.csv",
        patched_name="trial_landscape_rows.patched.csv",
        cohort_column=None,
        array_columns=frozenset({"cancer_type"}),
        int_columns=frozenset(),
        timestamp_columns=frozenset({"created_at"}),
        json_columns=frozenset(),
        text_columns=frozenset(LANDSCAPE_COLUMNS),
        drift_exempt=frozenset({"created_at"}),
    ),
}


def to_db(spec: TableSpec, column: str, raw: str) -> object:
    """Convert a CSV cell to the value the column's Postgres type expects."""
    if raw in ("", None):
        return None
    if column in spec.array_columns or column in spec.json_columns:
        return json.loads(raw)
    if column in spec.int_columns:
        return int(float(raw))
    if column in spec.text_columns or column in spec.timestamp_columns:
        return raw
    return float(raw)


def canonical(spec: TableSpec, column: str, value: object) -> str:
    """Comparable form for a value, whichever side it came from."""
    if value in ("", None):
        return ""
    # Marker arrays are sets of column names; element order carries no meaning, so
    # a reordering must not read as a change worth writing.
    if isinstance(value, list):
        return json.dumps(sorted(value), separators=(",", ":"))
    if isinstance(value, str) and column in spec.array_columns:
        return json.dumps(sorted(json.loads(value)), separators=(",", ":"))
    if (
        column in spec.text_columns
        or column in spec.timestamp_columns
        or column in spec.json_columns
    ):
        return str(value)
    try:
        return str(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return str(value)


def read_rows(
    path: pathlib.Path, spec: TableSpec, cohort: str | None
) -> dict[str, dict]:
    csv.field_size_limit(10_000_000)
    with open(path, newline="") as handle:
        return {
            row[spec.key]: row
            for row in csv.DictReader(handle)
            if spec.cohort_column is None or row[spec.cohort_column] == cohort
        }


def fetch_live(client: Client, spec: TableSpec, cohort: str | None) -> dict[str, dict]:
    rows: list[dict] = []
    page = 500
    start = 0
    while True:
        query = client.table(spec.table).select("*")
        if spec.cohort_column is not None:
            query = query.eq(spec.cohort_column, cohort)
        response = query.range(start, start + page - 1).execute()
        rows += cast(list[dict], response.data)
        if len(response.data) < page:
            break
        start += page
    return {row[spec.key]: row for row in rows}


def find_drift(
    spec: TableSpec, live: dict[str, dict], baseline: dict[str, dict]
) -> list[tuple[str, str, str, str]]:
    drift: list[tuple[str, str, str, str]] = []
    for row_id, base_row in baseline.items():
        live_row = live.get(row_id)
        if live_row is None:
            drift.append((row_id, "<row>", "present", "missing"))
            continue
        for column, base_value in base_row.items():
            if column in spec.drift_exempt or column not in live_row:
                continue
            live_canonical = canonical(spec, column, live_row[column])
            base_canonical = canonical(spec, column, base_value)
            if live_canonical != base_canonical:
                drift.append((row_id, column, base_canonical[:40], live_canonical[:40]))
    return drift


def build_patches(
    spec: TableSpec, baseline: dict[str, dict], patched: dict[str, dict]
) -> dict[str, dict]:
    patches: dict[str, dict] = {}
    for row_id, patched_row in patched.items():
        base_row = baseline[row_id]
        payload = {
            column: to_db(spec, column, value)
            for column, value in patched_row.items()
            if canonical(spec, column, value)
            != canonical(spec, column, base_row.get(column, ""))
        }
        if payload:
            patches[row_id] = payload
    return patches


def drop_unreferencable_nct_ids(
    client: Client, patches: dict[str, dict]
) -> list[tuple[str, str]]:
    """Remove nct_id corrections that point at a trial clinical_trials does not hold.

    Only trial_outcomes needs this. trial_landscape.nct_id is its own primary key, not a
    reference, and this pass never writes it.

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
        known |= {row["nct_id"] for row in cast(list[dict], response.data)}
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
        "--table",
        default="trial_outcomes",
        choices=sorted(SPECS),
        help="Which table to write (default: trial_outcomes)",
    )
    parser.add_argument(
        "--source-type",
        default="publication",
        choices=["publication", "abstract"],
        help="trial_outcomes only: which cohort's patch to write (default: publication)",
    )
    parser.add_argument("--patched", default=None)
    parser.add_argument("--baseline", default=None)
    parser.add_argument(
        "--only-id",
        default=None,
        help="Restrict to one row id, to retry a row an earlier run could not write",
    )
    args = parser.parse_args()

    spec = SPECS[args.table]
    cohort = args.source_type if spec.cohort_column else None
    label = cohort or spec.table
    patched_path = pathlib.Path(args.patched or spec.patched_csv(cohort))
    baseline_path = pathlib.Path(args.baseline or spec.baseline_csv)

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        print("SUPABASE_URL and SUPABASE_KEY must be set in melanoma/.env")
        sys.exit(1)
    client: Client = create_client(url, key)

    baseline = read_rows(baseline_path, spec, cohort)
    patched = read_rows(patched_path, spec, cohort)
    if set(baseline) != set(patched):
        print("Baseline and patched CSVs cover different rows; refusing to continue.")
        sys.exit(1)
    print(f"Baseline and patched agree on {len(baseline)} {label} rows")

    if args.only_id:
        if args.only_id not in baseline:
            print(f"{args.only_id} is not a {label} row in the CSVs.")
            sys.exit(1)
        baseline = {args.only_id: baseline[args.only_id]}
        patched = {args.only_id: patched[args.only_id]}
        print(f"Restricted to {args.only_id}")

    live = fetch_live(client, spec, cohort)
    print(f"Live {label} rows: {len(live)}")

    drift = find_drift(spec, live, baseline)
    if drift:
        print(
            f"ABORT: {len(drift)} cells drifted from the baseline export since it was taken."
        )
        for row in drift[:20]:
            print(f"  {row[0]} {row[1]}: export={row[2]!r} live={row[3]!r}")
        sys.exit(1)
    print("Drift check clean: live table matches the baseline export")

    patches = build_patches(spec, baseline, patched)
    unreferencable: list[tuple[str, str]] = []
    if spec.table == "trial_outcomes":
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
    suffix = f"_{cohort}s" if cohort else ""
    backup_path = BACKUP_DIR / f"{spec.table}{suffix}_{stamp}.json"
    backup_path.write_text(json.dumps(list(live.values()), indent=1, default=str))
    print(f"Backed up {len(live)} live rows to {backup_path}")

    failures: list[tuple[str, str]] = []
    for index, (row_id, payload) in enumerate(patches.items(), start=1):
        try:
            client.table(spec.table).update(payload).eq(spec.key, row_id).execute()
        except Exception as error:  # noqa: BLE001 - surface any row failure, keep going
            failures.append((row_id, str(error)))
            print(f"  x {row_id}: {error}")
        if index % 25 == 0:
            print(f"  {index}/{len(patches)} rows written")
    print(f"Wrote {len(patches) - len(failures)}/{len(patches)} rows")

    after = fetch_live(client, spec, cohort)
    # A dropped nct_id is a known, reported divergence, not a failed write.
    left_alone = {row_id for row_id, _ in unreferencable}
    remaining = [
        (row_id, column)
        for row_id, row in patched.items()
        for column in row
        if column in after[row_id]
        and column not in spec.drift_exempt
        and not (column == "nct_id" and row_id in left_alone)
        and canonical(spec, column, after[row_id][column])
        != canonical(spec, column, row[column])
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
        f"{len(patched)} {label} rows"
    )
    if failures:
        print(f"{len(failures)} row updates reported errors; see above")
        sys.exit(1)


if __name__ == "__main__":
    main()
