"""
Apply the trials validation verdicts to a trial_landscape CSV export.

Reads both cohorts' validation.json and writes a patched copy of the CSV alongside a
per-cell change log and a per-column rollup. Nothing is written to Supabase.

Only the four controlled-vocabulary fields are patched. The two fields the judge also
graded are held back on purpose - see EXCLUDED_FIELDS.

Trials the judge decided to drop carry no verdict block, so they contribute no
corrections and are never patched here. Whether those rows leave the table is a separate
decision.

Usage:
    cd melanoma
    poetry run python3 scripts/apply_trials_validation.py
    poetry run python3 scripts/apply_trials_validation.py --out /tmp/patched.csv
"""

import argparse
import collections
import csv
import json
import pathlib
import sys

_here = pathlib.Path(__file__).parent
_root = _here.parent

DEFAULT_CSV = _root / "data/backups/trial_landscape_rows.csv"
OUT_DIR = _root / "data/validation/trials_adjudication"

COHORTS = {
    "industry": _root / "data/output/trials_extraction_industry/validation",
    "nonindustry": (
        _root / "data/output/trials_extraction_nonindustry/validation-rerun-2026-07-24"
    ),
}

# The judge grades six fields. These four are single-valued picks from a controlled
# vocabulary: the corrected value drops into the column as-is.
PATCHED_FIELDS = [
    "biomarker",
    "stage",
    "line_of_therapy",
    "previous_treatment_criteria",
]

# modality: these verdicts were produced 2026-07-24 against the pre-backfill vocabulary.
#   The 2026-07-28/30 backfill widened modality to 23 values and rewrote 678 rows, so
#   every modality verdict here grades a value the table no longer holds. Re-validate
#   against the current table instead of replaying these.
# treatment_name: the judge answers in a two-level grammar - ';' separates trial arms,
#   '+' combines agents within one arm. trial_landscape is one row per nct_id with a
#   single flat string, so a multi-arm answer has nowhere to go. Flattening back to '+'
#   would re-assert the very combination regimen the judge flagged as wrong. Needs a
#   schema decision, not a patch.
EXCLUDED_FIELDS = {"modality", "treatment_name"}


def load_verdicts(cohort_dirs: dict[str, pathlib.Path]) -> list[dict]:
    """Flatten every graded field of every trial into one correction candidate list."""
    candidates: list[dict] = []
    for cohort, directory in cohort_dirs.items():
        payload = json.load(open(directory / "validation.json"))
        for trial in payload["trials"]:
            verdict = trial.get("verdict") or {}
            for evaluation in verdict.get("field_evaluations") or []:
                candidates.append(
                    {
                        "cohort": cohort,
                        "nct_id": trial["nct_number"],
                        "decision": trial["decision"],
                        "field": evaluation["field_name"],
                        "status": evaluation["status"],
                        "corrected_value": evaluation.get("corrected_value"),
                        "issue": evaluation.get("issue_description") or "",
                    }
                )
    return candidates


class Patcher:
    def __init__(self, rows: list[dict]) -> None:
        self.by_nct = {row["nct_id"]: row for row in rows}
        self.changes: list[dict] = []
        self.skips: list[dict] = []

    def skip(self, candidate: dict, reason: str) -> None:
        self.skips.append(
            {
                "nct_id": candidate["nct_id"],
                "cohort": candidate["cohort"],
                "field": candidate["field"],
                "reason": reason,
            }
        )

    def apply(self, candidate: dict) -> None:
        field = candidate["field"]
        if field in EXCLUDED_FIELDS:
            self.skip(candidate, f"excluded field ({field})")
            return
        if field not in PATCHED_FIELDS:
            self.skip(candidate, f"field not patched by this pass ({field})")
            return
        if candidate["status"] == "PASS":
            return
        if candidate["corrected_value"] is None:
            self.skip(candidate, "FAIL with no corrected_value - stays HITL")
            return

        row = self.by_nct.get(candidate["nct_id"])
        if row is None:
            self.skip(candidate, "no matching trial_landscape row")
            return

        new = candidate["corrected_value"].strip()
        old = row[field]
        if old == new:
            self.skip(candidate, "cell already holds the corrected value")
            return

        row[field] = new
        self.changes.append(
            {
                "nct_id": candidate["nct_id"],
                "cohort": candidate["cohort"],
                "decision": candidate["decision"],
                "field": field,
                "old": old,
                "new": new,
                "issue": candidate["issue"][:300],
            }
        )


def write_reports(patcher: Patcher, out_csv: pathlib.Path) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    changes_path = OUT_DIR / "changes.csv"
    with open(changes_path, "w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "nct_id",
                "cohort",
                "decision",
                "field",
                "old",
                "new",
                "issue",
            ],
        )
        writer.writeheader()
        writer.writerows(patcher.changes)

    skips_path = OUT_DIR / "skipped.csv"
    with open(skips_path, "w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["nct_id", "cohort", "field", "reason"]
        )
        writer.writeheader()
        writer.writerows(patcher.skips)

    per_field: dict[str, collections.Counter] = collections.defaultdict(
        collections.Counter
    )
    for change in patcher.changes:
        per_field[change["field"]][change["cohort"]] += 1

    cohorts = sorted(COHORTS)
    lines = [
        "# Trials validation - patch report",
        "",
        f"Source CSV: `{DEFAULT_CSV.relative_to(_root)}`",
        f"Patched CSV: `{out_csv}`",
        f"Cells changed: {len(patcher.changes)}  |  rows touched: "
        f"{len({c['nct_id'] for c in patcher.changes})}",
        "",
        "## Changes per field",
        "",
        "| field | " + " | ".join(cohorts) + " | total |",
        "| --- |" + " --- |" * (len(cohorts) + 1),
    ]
    for field in sorted(per_field, key=lambda f: -sum(per_field[f].values())):
        counter = per_field[field]
        cells = " | ".join(str(counter.get(c, 0)) for c in cohorts)
        lines.append(f"| {field} | {cells} | {sum(counter.values())} |")

    skip_counts: collections.Counter = collections.Counter(
        skip["reason"] for skip in patcher.skips
    )
    lines += ["", "## Skipped", "", "| reason | count |", "| --- | --- |"]
    for reason, count in skip_counts.most_common():
        lines.append(f"| {reason} | {count} |")
    lines.append("")

    report_path = OUT_DIR / "patch_report.md"
    report_path.write_text("\n".join(lines))

    print(f"Wrote {changes_path}")
    print(f"Wrote {skips_path}")
    print(f"Wrote {report_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv", default=str(DEFAULT_CSV), help="Source trial_landscape CSV"
    )
    parser.add_argument(
        "--out",
        default=str(OUT_DIR / "trial_landscape_rows.patched.csv"),
        help="Where to write the patched CSV",
    )
    args = parser.parse_args()

    with open(args.csv, newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    if not fieldnames:
        print(f"No header in {args.csv}")
        sys.exit(1)

    missing = [field for field in PATCHED_FIELDS if field not in fieldnames]
    if missing:
        print(f"CSV is missing patched columns: {missing}")
        sys.exit(1)

    candidates = load_verdicts(COHORTS)
    print(f"Loaded {len(rows)} rows, {len(candidates)} graded fields")

    patcher = Patcher(rows)
    for candidate in candidates:
        patcher.apply(candidate)

    out_csv = pathlib.Path(args.out)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {out_csv} ({len(rows)} rows, {len(fieldnames)} columns)")

    write_reports(patcher, out_csv)
    print(f"{len(patcher.changes)} cells changed, {len(patcher.skips)} skipped")
    print("No Supabase write performed.")


if __name__ == "__main__":
    main()
