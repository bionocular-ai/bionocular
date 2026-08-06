"""
Check adjudication verdict files against the batches they answer.

Run after each dispatch wave, before trusting any verdict. Catches the failure
modes a subagent can produce without noticing: a dropped or duplicated cell, a
verdict for a cell that was never asked about, a quote that is not in the
abstract, a MOVE into a column that does not exist, and MOVE collisions where
several source columns land on one destination cell.

Exits non-zero if any structural problem is found.

Usage:
    cd melanoma
    poetry run python3 scripts/check_adjudication_verdicts.py
    poetry run python3 scripts/check_adjudication_verdicts.py --quiet
"""

import argparse
import ast
import collections
import csv
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from verify_validation_quotes import normalize, quote_found  # noqa: E402

_root = pathlib.Path(__file__).parent.parent

DEFAULT_DIR = _root / "data/validation/abstracts_adjudication"
COLUMNS_CSV = _root / "data/backups/trial_outcomes_rows.csv"
VERDICTS = {
    "JUDGE_RIGHT_MOVE",
    "JUDGE_RIGHT_NULL",
    "JUDGE_RIGHT_FIX",
    "JUDGE_WRONG_KEEP",
    "UNCLEAR",
}


UPLOAD_SCRIPT = _root / "scripts/upload_to_supabase.py"


def key(record: dict) -> tuple[str, str, str]:
    return (record["doc_id"], record["arm_id"], record["db_column"])


def normalize_column(name: str) -> str:
    return name.lower().replace("attributetype.", "").replace("_", "")


def load_valid_targets() -> set[str]:
    """Column names a verdict may name as a MOVE destination.

    Batches speak the validation vocabulary ('trae'), the table speaks the
    storage vocabulary ('trae_pct'). ATTRIBUTE_MAPPING bridges them, so accept
    either form and let the patcher translate once.
    """
    source = UPLOAD_SCRIPT.read_text()
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Assign)
            and getattr(node.targets[0], "id", None) == "ATTRIBUTE_MAPPING"
        ):
            mapping: dict[str, str] = ast.literal_eval(node.value)
            break
    else:
        raise RuntimeError("ATTRIBUTE_MAPPING not found in upload_to_supabase.py")

    columns = set(next(csv.reader(open(COLUMNS_CSV))))
    by_normalized = {normalize_column(k) for k in mapping}
    return columns | by_normalized | set(mapping.values())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default=str(DEFAULT_DIR))
    parser.add_argument("--quiet", action="store_true", help="only print problems")
    args = parser.parse_args()

    base = pathlib.Path(args.dir)
    valid_targets = load_valid_targets()
    problems: list[str] = []
    totals: collections.Counter = collections.Counter()
    collisions: list[str] = []

    for verdict_path in sorted((base / "verdicts").glob("*.json")):
        name = verdict_path.stem
        batch_path = base / "batches" / f"{name}.json"
        if not batch_path.exists():
            problems.append(f"{name}: no matching batch file")
            continue

        batch = json.load(open(batch_path))
        verdicts = json.load(open(verdict_path))
        asked = {key(cell) for document in batch for cell in document["cells"]}
        sources = {d["doc_id"]: normalize(d["source_text"]) for d in batch}

        answered = [key(v) for v in verdicts]
        duplicates = [k for k, c in collections.Counter(answered).items() if c > 1]
        if missing := asked - set(answered):
            problems.append(
                f"{name}: {len(missing)} cells unanswered, e.g. {sorted(missing)[:3]}"
            )
        if extra := set(answered) - asked:
            problems.append(
                f"{name}: {len(extra)} verdicts for cells never asked, e.g. {sorted(extra)[:3]}"
            )
        if duplicates:
            problems.append(
                f"{name}: {len(duplicates)} duplicated cells, e.g. {duplicates[:3]}"
            )

        targets: collections.Counter = collections.Counter()
        for verdict in verdicts:
            label = verdict.get("verdict")
            totals[label] += 1
            if label not in VERDICTS:
                problems.append(f"{name}: unknown verdict {label!r} on {key(verdict)}")
            quote = verdict.get("source_evidence") or ""
            if not quote:
                problems.append(f"{name}: no source_evidence on {key(verdict)}")
            elif verdict["doc_id"] in sources:
                if not quote_found(quote, sources[verdict["doc_id"]]):
                    problems.append(
                        f"{name}: evidence not in abstract for {key(verdict)}: {quote[:70]!r}"
                    )
            if label == "JUDGE_RIGHT_MOVE":
                target = verdict.get("target_column")
                if not target:
                    problems.append(
                        f"{name}: MOVE without target_column on {key(verdict)}"
                    )
                elif (
                    normalize_column(target) not in valid_targets
                    and target not in valid_targets
                ):
                    problems.append(
                        f"{name}: MOVE to nonexistent column {target!r} on {key(verdict)}"
                    )
                else:
                    targets[(verdict["doc_id"], verdict["arm_id"], target)] += 1
            if label == "JUDGE_RIGHT_FIX" and verdict.get("corrected_value") in (
                None,
                "",
            ):
                problems.append(
                    f"{name}: FIX without corrected_value on {key(verdict)}"
                )

        for cell, count in targets.items():
            if count > 1:
                collisions.append(
                    f"{name}: {count} sources -> {cell[0]} {cell[1]} {cell[2]}"
                )

        if not args.quiet:
            counts = collections.Counter(v.get("verdict") for v in verdicts)
            print(f"{name}: {len(verdicts)} cells  {dict(counts)}")

    print(f"\ntotals: {dict(totals)}  ({sum(totals.values())} cells)")
    if collisions:
        print(f"\nMOVE collisions ({len(collisions)}) - the patcher must dedupe these:")
        for line in collisions:
            print(f"  {line}")
    if problems:
        print(f"\nPROBLEMS ({len(problems)}):")
        for line in problems:
            print(f"  {line}")
        return 1
    print("\nno structural problems")
    return 0


if __name__ == "__main__":
    sys.exit(main())
