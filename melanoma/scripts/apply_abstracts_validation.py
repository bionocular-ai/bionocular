"""
Apply the adjudicated abstracts validation verdicts to a trial_outcomes CSV export.

Reads the 48 agent verdict files plus the auto-repaired ci_hr ranges, and writes a
patched copy of the CSV alongside a per-cell change log and a per-column rollup.
Nothing is written to Supabase.

Two things separate this from the publications pass:

  vocabulary - the batches speak the extraction vocabulary ('trae') while the table
               speaks the storage vocabulary ('trae_pct'); 45 of the 89 columns a
               verdict can name differ. ATTRIBUTE_MAPPING bridges them.
  collisions - several source columns can MOVE onto one destination cell (69 of them).
               Every one carries the same value, so the first move-in wins and the rest
               are recorded as deduped.

Usage:
    cd melanoma
    poetry run python3 scripts/apply_abstracts_validation.py
    poetry run python3 scripts/apply_abstracts_validation.py --out /tmp/patched.csv
"""

import argparse
import collections
import csv
import datetime
import json
import pathlib
import sys

_here = pathlib.Path(__file__).parent
_root = _here.parent

sys.path.insert(0, str(_here))
from apply_publications_validation import (  # noqa: E402
    COL_VALIDATED_AT,
    COL_VALIDATION_STATUS,
    EXCLUDED_COLUMNS,
    NEW_COLUMNS,
    STATUS_VALIDATED,
    Patcher,
    load_attribute_mapping,
    normalize_key,
    parse_marker,
)

DEFAULT_CSV = _root / "data/backups/trial_outcomes_rows.csv"
ADJUDICATION_DIR = _root / "data/validation/abstracts_adjudication"
VERDICT_DIR = ADJUDICATION_DIR / "verdicts"
AUTO_CI_FIXES = ADJUDICATION_DIR / "auto_ci_fixes.json"
OUT_DIR = ADJUDICATION_DIR

SOURCE_TYPE = "abstract"

# Identity fields the extraction vocabulary names differently from the table.
IDENTITY_COLUMNS = {"nct_number": "nct_id"}

# Fields a verdict can name that this table has no cell for. The verdicts are still
# recorded in skipped.csv - they are real findings with nowhere to land.
UNMAPPED_COLUMNS = {
    "trial_name": "trial_outcomes has no trial-name column (exported to trial_names.csv)",
    "abstract_number": "abstract_id already carries the full document id",
}

# trial_name is the one homeless field carrying findings that would otherwise be lost:
# 54 of its verdicts are real trial names the extractor missed. They go to their own
# file, keyed by row id, so a later schema change can apply them without re-running.
TRIAL_NAME_FIELD = "trial_name"


def resolve_column(name: str, columns: set[str], by_normalized: dict[str, str]) -> str:
    """Extraction-vocabulary field name -> table column, or '' when it has none."""
    if name in UNMAPPED_COLUMNS:
        return ""
    if name in IDENTITY_COLUMNS:
        return IDENTITY_COLUMNS[name]
    if name in columns:
        return name
    return by_normalized.get(normalize_key(name), "")


def load_verdicts() -> list[dict]:
    verdicts: list[dict] = []
    for path in sorted(VERDICT_DIR.glob("*.json")):
        for verdict in json.load(open(path)):
            verdict["_batch"] = path.stem
            verdicts.append(verdict)
    return verdicts


def load_auto_ci_fixes() -> dict[tuple[str, str, str], str]:
    """(doc_id, arm_id, field) -> the recovered 'low-high' range.

    The triage pass repaired these offline and rewrote value_in_db in the batch, so
    agents saw a complete range and returned KEEP. The table still holds the bare
    lower bound, so a KEEP here has to write the range rather than do nothing.
    """
    if not AUTO_CI_FIXES.exists():
        return {}
    return {
        (fix["doc_id"], fix["arm_id"], fix["db_column"]): fix["corrected_value"]
        for fix in json.load(open(AUTO_CI_FIXES))
    }


def float_residue(value: str) -> str | None:
    """The clean form of a value carrying binary-float noise ('64.80000000000001').

    Normalizes to 12 significant digits, not to a fixed number of decimal places: a
    p-value of 0.0000033 is exact at two significant digits and must survive, while
    rounding it to 6 decimal places would corrupt it to 3e-06.

    Only genuine residue counts. '140' must not come back as '140.0' - that is the
    trailing-.0 difference the triage pass deliberately suppresses, not a defect.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    cleaned = float(f"{number:.12g}")
    return repr(cleaned) if cleaned != number else None


def write_trial_names(verdicts: list[dict], path: pathlib.Path) -> int:
    """Export the trial_name verdicts, which have no column to be applied to.

    Keyed by row id so this stays applyable if trial_outcomes ever gains the column.
    """
    fieldnames = [
        "row_id",
        "doc_id",
        "arm_id",
        "verdict",
        "value_in_db",
        "corrected_value",
        "confidence",
        "source_evidence",
        "reason",
        "batch",
    ]
    rows = [
        {
            "row_id": f"{SOURCE_TYPE}_{v['doc_id']}_{v['arm_id']}",
            "doc_id": v["doc_id"],
            "arm_id": v["arm_id"],
            "verdict": v["verdict"],
            "value_in_db": v["value_in_db"],
            "corrected_value": v.get("corrected_value") or "",
            "confidence": v.get("confidence", ""),
            "source_evidence": (v.get("source_evidence") or "")[:300],
            "reason": v.get("reason", ""),
            "batch": v.get("_batch", ""),
        }
        for v in verdicts
        if v["db_column"] == TRIAL_NAME_FIELD
    ]
    rows.sort(key=lambda r: (r["doc_id"], r["arm_id"]))
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def apply_verdicts(
    patcher: Patcher,
    verdicts: list[dict],
    columns: set[str],
    by_normalized: dict[str, str],
    auto_ci: dict[tuple[str, str, str], str],
) -> None:
    """Apply MOVE, then FIX, then NULL. KEEP is last and usually a no-op.

    Order matters twice. A FIX onto a cell a MOVE just filled carries the more precise
    value, so it must land after the move. A NULL is a verdict about what the cell held
    *before* this pass - if a MOVE has since filled that cell deliberately, the NULL is
    stale and must not wipe it (ASCO_2020_10052: one verdict nulls a computed 70.0
    while another moves the correct 100.0 into the same cell).
    """
    order = {
        "JUDGE_RIGHT_MOVE": 0,
        "JUDGE_RIGHT_FIX": 1,
        "JUDGE_RIGHT_NULL": 2,
        "JUDGE_WRONG_KEEP": 3,
        "UNCLEAR": 4,
    }
    moved_in: set[tuple[str, str]] = set()

    for verdict in sorted(verdicts, key=lambda v: order[v["verdict"]]):
        doc_id, arm_id = verdict["doc_id"], verdict["arm_id"]
        field = verdict["db_column"]
        kind = verdict["verdict"]

        if field in UNMAPPED_COLUMNS:
            patcher.skip(doc_id, arm_id, field, f"{UNMAPPED_COLUMNS[field]} ({kind})")
            continue
        column = resolve_column(field, columns, by_normalized)
        if not column:
            patcher.skip(doc_id, arm_id, field, f"field has no table column ({kind})")
            continue
        if column in EXCLUDED_COLUMNS:
            patcher.skip(doc_id, arm_id, column, f"excluded column ({kind})")
            continue
        row = patcher.row_for(doc_id, arm_id)
        if row is None:
            patcher.skip(doc_id, arm_id, column, "no matching CSV row")
            continue

        if kind == "UNCLEAR":
            patcher.skip(doc_id, arm_id, column, "UNCLEAR - left for a human")
        elif kind == "JUDGE_WRONG_KEEP":
            repaired = auto_ci.get((doc_id, arm_id, field))
            current = row[column]
            if repaired is not None and current != repaired:
                patcher.set_cell(
                    row,
                    column,
                    repaired,
                    "keep-ci-repair",
                    verdict,
                    note=f"auto-repaired range; table held {current!r}",
                )
            elif clean := float_residue(current):
                patcher.set_cell(
                    row,
                    column,
                    clean,
                    "keep-rounded",
                    verdict,
                    note=f"float residue from a unit conversion; was {current!r}",
                )
            else:
                patcher.skip(doc_id, arm_id, column, "KEEP - value stands")
        elif kind == "JUDGE_RIGHT_NULL":
            if (row["id"], column) in moved_in:
                patcher.skip(
                    doc_id, arm_id, column, "NULL superseded by a move into this cell"
                )
            else:
                patcher.set_cell(row, column, None, "null", verdict)
        elif kind == "JUDGE_RIGHT_FIX":
            patcher.set_cell(row, column, verdict["corrected_value"], "fix", verdict)
        elif kind == "JUDGE_RIGHT_MOVE":
            target = resolve_column(
                verdict["target_column"] or "", columns, by_normalized
            )
            if not target:
                patcher.skip(
                    doc_id,
                    arm_id,
                    verdict["target_column"] or "",
                    "MOVE target has no table column",
                )
                continue
            if target in EXCLUDED_COLUMNS:
                patcher.skip(doc_id, arm_id, target, "MOVE into an excluded column")
                continue

            moved, _ = parse_marker(verdict["value_in_db"], target)
            existing = row[target]
            if (row["id"], target) in moved_in:
                patcher.skip(
                    doc_id,
                    arm_id,
                    target,
                    "MOVE collision - another source already moved into this cell",
                )
            elif existing in ("", None):
                patcher.set_cell(
                    row, target, verdict["value_in_db"], "move-in", verdict
                )
                moved_in.add((row["id"], target))
            elif existing != moved:
                patcher.set_cell(
                    row,
                    target,
                    verdict["value_in_db"],
                    "move-in-overwrite",
                    verdict,
                    note=f"target held {existing!r}; move value {moved!r} wins",
                )
                moved_in.add((row["id"], target))
            else:
                moved_in.add((row["id"], target))
                patcher.skip(
                    doc_id, arm_id, target, "target already holds the moved value"
                )
            patcher.set_cell(row, column, None, "move-out", verdict)


def stamp_provenance(rows: list[dict], timestamp: str) -> collections.Counter:
    """Mark every abstract row validated; leave the other source types untouched."""
    counts: collections.Counter = collections.Counter()
    for row in rows:
        if row["source_type"] != SOURCE_TYPE:
            counts[f"untouched ({row['source_type']})"] += 1
            continue
        row[COL_VALIDATION_STATUS] = STATUS_VALIDATED
        row[COL_VALIDATED_AT] = timestamp
        counts[STATUS_VALIDATED] += 1
    return counts


def write_reports(
    patcher: Patcher, counts: collections.Counter, out_csv: pathlib.Path
) -> None:
    changes_path = OUT_DIR / "changes.csv"
    fieldnames = [
        "row_id",
        "doc_id",
        "arm_id",
        "column",
        "old",
        "new",
        "marker",
        "action",
        "verdict",
        "confidence",
        "note",
    ]
    with open(changes_path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(patcher.changes)

    per_column: dict[str, collections.Counter] = collections.defaultdict(
        collections.Counter
    )
    for change in patcher.changes:
        per_column[change["column"]][change["action"]] += 1
    actions = [
        "null",
        "move-in",
        "move-in-overwrite",
        "move-out",
        "fix",
        "keep-ci-repair",
        "keep-rounded",
    ]

    lines = [
        "# Abstracts validation - patch report",
        "",
        f"Source CSV: `{DEFAULT_CSV.relative_to(_root)}`",
        f"Patched CSV: `{out_csv}`",
        f"Cells changed: {len(patcher.changes)}  |  rows touched: "
        f"{len({c['row_id'] for c in patcher.changes})}",
        "",
        "## Provenance stamp",
        "",
        "| status | rows |",
        "| --- | --- |",
    ]
    for key, count in counts.most_common():
        lines.append(f"| {key} | {count} |")

    lines += [
        "",
        "## Changes per column",
        "",
        "| column | " + " | ".join(actions) + " | total |",
        "| --- |" + " --- |" * (len(actions) + 1),
    ]
    for column in sorted(per_column, key=lambda c: (-sum(per_column[c].values()), c)):
        counter = per_column[column]
        cells = " | ".join(str(counter.get(a, 0)) for a in actions)
        lines.append(f"| {column} | {cells} | {sum(counter.values())} |")

    skip_counts: collections.Counter = collections.Counter(
        skip["reason"].split(" (")[0] for skip in patcher.skips
    )
    lines += ["", "## Skipped", "", "| reason | count |", "| --- | --- |"]
    for reason, count in skip_counts.most_common():
        lines.append(f"| {reason} | {count} |")
    lines.append("")

    report_path = OUT_DIR / "patch_report.md"
    report_path.write_text("\n".join(lines))

    skips_path = OUT_DIR / "skipped.csv"
    with open(skips_path, "w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["doc_id", "arm_id", "column", "reason"]
        )
        writer.writeheader()
        writer.writerows(patcher.skips)

    print(f"Wrote {changes_path}")
    print(f"Wrote {skips_path}")
    print(f"Wrote {report_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default=str(DEFAULT_CSV), help="Source CSV")
    parser.add_argument(
        "--out",
        default=str(OUT_DIR / "trial_outcomes_rows.patched.csv"),
        help="Where to write the patched CSV",
    )
    args = parser.parse_args()

    csv.field_size_limit(10_000_000)
    with open(args.csv, newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    if not fieldnames:
        print(f"No header in {args.csv}")
        sys.exit(1)

    for column in NEW_COLUMNS:
        if column not in fieldnames:
            fieldnames.append(column)
    for row in rows:
        for column in NEW_COLUMNS:
            row.setdefault(column, "")

    mapping = load_attribute_mapping()
    by_normalized = {normalize_key(k): v for k, v in mapping.items()}
    columns = set(fieldnames)
    verdicts = load_verdicts()
    auto_ci = load_auto_ci_fixes()
    print(
        f"Loaded {len(rows)} rows, {len(verdicts)} verdicts, "
        f"{len(auto_ci)} auto-repaired ci_hr ranges"
    )

    patcher = Patcher(rows, fieldnames, source_type=SOURCE_TYPE)
    apply_verdicts(patcher, verdicts, columns, by_normalized, auto_ci)
    patcher.write_markers_back()

    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds"
    )
    counts = stamp_provenance(rows, timestamp)

    out_csv = pathlib.Path(args.out)
    with open(out_csv, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {out_csv} ({len(rows)} rows, {len(fieldnames)} columns)")

    write_reports(patcher, counts, out_csv)
    trial_names_path = OUT_DIR / "trial_names.csv"
    exported = write_trial_names(verdicts, trial_names_path)
    print(f"Wrote {trial_names_path} ({exported} verdicts with no column to apply to)")
    print(f"{len(patcher.changes)} cells changed, {len(patcher.skips)} skipped")
    print("No Supabase write performed.")


if __name__ == "__main__":
    main()
