"""
Apply the adjudicated publications validation verdicts to a trial_outcomes CSV export.

Reads the two human-adjudicated verdict files (safety + efficacy), plus the judge's
missed_values report, and writes a patched copy of the CSV alongside a per-cell change
log and a per-column rollup. Nothing is written to Supabase.

Usage:
    cd melanoma
    poetry run python3 scripts/apply_publications_validation.py
    poetry run python3 scripts/apply_publications_validation.py --out /tmp/patched.csv
"""

import argparse
import ast
import collections
import csv
import datetime
import json
import pathlib
import sys

_here = pathlib.Path(__file__).parent
_root = _here.parent

DEFAULT_CSV = _root / "data/backups/trial_outcomes_rows.csv"
VERDICT_DIR = _root / "data/validation/publications_adjudication"
MISSED_VALUES = (
    _root / "data/output/Publications_May_2026/validation/missed_values.json"
)
OUT_DIR = _root / "data/validation/publications_adjudication"

# Columns added by this pass. is_lt mirrors the existing is_nr pattern: the number is
# stored so it plots, the marker carries the "<".
COL_IS_LT = "is_lt"
COL_VALIDATION_STATUS = "validation_status"
COL_VALIDATED_AT = "validated_at"
NEW_COLUMNS = [COL_IS_LT, COL_VALIDATION_STATUS, COL_VALIDATED_AT]

STATUS_VALIDATED = "validated"
STATUS_UNVALIDATED = "unvalidated"

# Batch-I_24 timed out during the judge run; its 3 arms were never validated and are
# marked, not patched.
UNVALIDATED_DOCS = {"Batch-I_24"}

# cancer_type is a trusted anchor and the one FIX against it was only medium confidence.
EXCLUDED_COLUMNS = {"line_of_treatment", "cancer_type"}

# Text columns; everything else in the mapping is numeric and gets float-parsed.
KNOWN_STRINGS = {
    "id",
    "source_type",
    "source_name",
    "abstract_id",
    "publication_id",
    "source_url",
    "nct_id",
    "arm_id",
    "arm_name",
    "cancer_type",
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
    "is_nr",
    "all_attributes",
    "created_at",
    "ci_hr_pfs",
    "ci_hr_os",
    "ci_hr_efs",
    "ci_hr_rfs",
    "ci_hr_mfs",
    "ci_hr_ttp",
}

NR_TOKENS = {"NR", "NOT REACHED", "NOTREACHED"}
EMPTY_VALUES = {None, "", "Not found", "N/A", "Not available", "Not reached"}


def load_attribute_mapping() -> dict[str, str]:
    """Read ATTRIBUTE_MAPPING out of upload_to_supabase.py without importing it.

    Importing that module builds a Supabase client at module scope, which needs live
    credentials; this script is offline.
    """
    source = (_here / "upload_to_supabase.py").read_text()
    for node in ast.parse(source).body:
        if (
            isinstance(node, ast.Assign)
            and getattr(node.targets[0], "id", None) == "ATTRIBUTE_MAPPING"
        ):
            mapping: dict[str, str] = ast.literal_eval(node.value)
            return mapping
    raise RuntimeError("ATTRIBUTE_MAPPING not found in upload_to_supabase.py")


def _relative(path: pathlib.Path) -> str:
    """Path relative to melanoma/ when it sits inside the package, else as given."""
    try:
        return str(path.resolve().relative_to(_root))
    except ValueError:
        return str(path)


def normalize_key(key: str) -> str:
    return key.lower().replace("attributetype.", "").replace("_", "")


def parse_marker(value: str | None, column: str) -> tuple[str, str | None]:
    """Return (cell_value, marker) for a raw value.

    marker is 'lt' for censored '<n' values, 'nr' for not-reached, None otherwise.
    A censored value stores the bound as the number so it still plots.
    """
    if value is None:
        return "", None
    raw = str(value).strip()
    if raw in EMPTY_VALUES:
        return "", None
    if raw.upper() in NR_TOKENS:
        return "", "nr"
    marker = "lt" if raw.startswith("<") else None
    if column in KNOWN_STRINGS:
        return raw, marker
    stripped = raw.lstrip("<>").rstrip("%").strip()
    try:
        return str(float(stripped)), marker
    except ValueError:
        return raw, marker


def load_verdicts() -> list[dict]:
    verdicts: list[dict] = []
    for name in ("safety", "efficacy"):
        path = VERDICT_DIR / f"{name}_verdicts.json"
        for verdict in json.load(open(path)):
            verdict["_group"] = name
            verdicts.append(verdict)
    return verdicts


def load_missed_values(mapping: dict[str, str]) -> list[dict]:
    """Flatten missed_values.json and resolve each extraction field to a DB column."""
    by_normalized = {normalize_key(k): v for k, v in mapping.items()}
    report = json.load(open(MISSED_VALUES))
    items: list[dict] = []
    for entries in report["by_field"].values():
        for entry in entries:
            column = by_normalized.get(normalize_key(entry["field_name"]))
            entry["_column"] = column
            items.append(entry)
    return items


class Patcher:
    def __init__(self, rows: list[dict], fieldnames: list[str]) -> None:
        # Publication rows only. Abstract and webscrape rows must come through byte-identical.
        self.by_id = {
            row["id"]: row for row in rows if row["source_type"] == "publication"
        }
        self.fieldnames = fieldnames
        self.changes: list[dict] = []
        self.skips: list[dict] = []
        self.markers: dict[str, dict[str, set[str]]] = collections.defaultdict(
            lambda: {"nr": set(), "lt": set()}
        )
        self.touched: set[str] = set()
        for row in self.by_id.values():
            if row.get("is_nr"):
                self.markers[row["id"]]["nr"] = set(json.loads(row["is_nr"]))

    def row_for(self, doc_id: str, arm_id: str) -> dict | None:
        return self.by_id.get(f"publication_{doc_id}_{arm_id}")

    def skip(self, doc_id: str, arm_id: str, column: str, reason: str) -> None:
        self.skips.append(
            {"doc_id": doc_id, "arm_id": arm_id, "column": column, "reason": reason}
        )

    def set_cell(
        self,
        row: dict,
        column: str,
        raw_value: str | None,
        action: str,
        verdict: dict | None = None,
        note: str = "",
    ) -> None:
        value, marker = parse_marker(raw_value, column)
        old = row[column]
        row[column] = value
        self.touched.add(row["id"])
        markers = self.markers[row["id"]]
        for kind in ("nr", "lt"):
            markers[kind].discard(column)
        if marker:
            markers[marker].add(column)
        self.changes.append(
            {
                "row_id": row["id"],
                "doc_id": row["source_name"],
                "arm_id": row["arm_id"],
                "column": column,
                "old": old,
                "new": value,
                "marker": marker or "",
                "action": action,
                "verdict": (verdict or {}).get("verdict", ""),
                "confidence": (verdict or {}).get("confidence", ""),
                "note": note or (verdict or {}).get("reason", ""),
            }
        )

    def write_markers_back(self) -> None:
        """Reserialize is_nr / is_lt only on rows this pass actually changed."""
        for row_id in sorted(self.touched):
            markers = self.markers[row_id]
            row = self.by_id[row_id]
            row["is_nr"] = json.dumps(sorted(markers["nr"])) if markers["nr"] else ""
            row[COL_IS_LT] = json.dumps(sorted(markers["lt"])) if markers["lt"] else ""


def apply_verdicts(patcher: Patcher, verdicts: list[dict]) -> None:
    """Apply MOVE, then FIX, then NULL. KEEP is a no-op that is still counted.

    Order matters: one cell (Batch-II_26 anemia) is both a MOVE target and a FIX
    target, and the FIX carries the more precise value.
    """
    order = {
        "JUDGE_RIGHT_MOVE": 0,
        "JUDGE_RIGHT_FIX": 1,
        "JUDGE_RIGHT_NULL": 2,
        "JUDGE_WRONG_KEEP": 3,
    }
    for verdict in sorted(verdicts, key=lambda v: order[v["verdict"]]):
        doc_id, arm_id, column = (
            verdict["doc_id"],
            verdict["arm_id"],
            verdict["db_column"],
        )
        if column in EXCLUDED_COLUMNS:
            patcher.skip(
                doc_id, arm_id, column, f"excluded column ({verdict['verdict']})"
            )
            continue
        row = patcher.row_for(doc_id, arm_id)
        if row is None:
            patcher.skip(doc_id, arm_id, column, "no matching CSV row")
            continue

        kind = verdict["verdict"]
        if kind == "JUDGE_WRONG_KEEP":
            patcher.skip(doc_id, arm_id, column, "KEEP - judge was wrong, value stands")
        elif kind == "JUDGE_RIGHT_NULL":
            patcher.set_cell(row, column, None, "null", verdict)
        elif kind == "JUDGE_RIGHT_FIX":
            patcher.set_cell(row, column, verdict["corrected_value"], "fix", verdict)
        elif kind == "JUDGE_RIGHT_MOVE":
            target = verdict["target_column"]
            existing = row[target]
            moved, _ = parse_marker(verdict["value_in_db"], target)
            if existing in ("", None):
                patcher.set_cell(
                    row, target, verdict["value_in_db"], "move-in", verdict
                )
            elif existing != moved:
                patcher.set_cell(
                    row,
                    target,
                    verdict["value_in_db"],
                    "move-in-overwrite",
                    verdict,
                    note=f"target held {existing!r}; move value {moved!r} wins",
                )
            patcher.set_cell(row, column, None, "move-out", verdict)


def apply_missed_values(patcher: Patcher, items: list[dict]) -> None:
    """Fill empty cells only. A missed value never overwrites an existing number."""
    for item in items:
        doc_id, arm_id, column = item["doc_id"], item["arm_id"], item["_column"]
        if column is None:
            patcher.skip(doc_id, arm_id, item["field_name"], "field has no DB column")
            continue
        if column in EXCLUDED_COLUMNS:
            patcher.skip(doc_id, arm_id, column, "excluded column (missed value)")
            continue
        row = patcher.row_for(doc_id, arm_id)
        if row is None:
            patcher.skip(doc_id, arm_id, column, "no matching CSV row")
            continue
        if row[column] not in ("", None):
            patcher.skip(doc_id, arm_id, column, f"cell already holds {row[column]!r}")
            continue
        patcher.set_cell(
            row,
            column,
            item["suggested_value"],
            "missed-value",
            note=item["source_evidence_quote"][:300],
        )


def stamp_provenance(rows: list[dict], timestamp: str) -> collections.Counter:
    counts: collections.Counter = collections.Counter()
    for row in rows:
        if row["source_type"] != "publication":
            row[COL_VALIDATION_STATUS] = ""
            row[COL_VALIDATED_AT] = ""
            counts["untouched (not a publication)"] += 1
            continue
        if row["source_name"] in UNVALIDATED_DOCS:
            row[COL_VALIDATION_STATUS] = STATUS_UNVALIDATED
            row[COL_VALIDATED_AT] = ""
            counts[STATUS_UNVALIDATED] += 1
            continue
        row[COL_VALIDATION_STATUS] = STATUS_VALIDATED
        row[COL_VALIDATED_AT] = timestamp
        counts[STATUS_VALIDATED] += 1
    return counts


def write_reports(
    patcher: Patcher, counts: collections.Counter, out_csv: pathlib.Path
) -> None:
    changes_path = OUT_DIR / "changes.csv"
    with open(changes_path, "w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
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
            ],
        )
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
        "missed-value",
    ]

    lines = [
        "# Publications validation - patch report",
        "",
        f"Source CSV: `{DEFAULT_CSV.relative_to(_root)}`",
        f"Patched CSV: `{_relative(out_csv)}`",
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
        s["reason"].split(" (")[0].split(" -")[0] for s in patcher.skips
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
    parser.add_argument(
        "--csv", default=str(DEFAULT_CSV), help="Source trial_outcomes CSV"
    )
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
    verdicts = load_verdicts()
    missed = load_missed_values(mapping)
    print(
        f"Loaded {len(rows)} rows, {len(verdicts)} verdicts, {len(missed)} missed values"
    )

    patcher = Patcher(rows, fieldnames)
    apply_verdicts(patcher, verdicts)
    apply_missed_values(patcher, missed)
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
    print(f"{len(patcher.changes)} cells changed, {len(patcher.skips)} skipped")
    print("No Supabase write performed.")


if __name__ == "__main__":
    main()
