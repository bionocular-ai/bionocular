"""Build the ASH test-run review sheet (.xlsx) from results.json.

Usage (from melanoma/):
  poetry run python3 scripts/ash_review_sheet.py --results data/ash_test_run/results.json \
      --out ../.lavish/ash-integration/ash_test_review.xlsx

Rerunning keeps the check and check_note columns already typed into --out, so the
Summary tab can be rebuilt after the values are checked.
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(Path(__file__).parent))

from ash_fields import Family, SheetField, applies, load_families  # noqa: E402
from ash_test_run import parse_md, quote_found  # noqa: E402

COLUMNS = [
    "abstract",
    "doi",
    "indication",
    "arm",
    "family",
    "field",
    "value",
    "quote",
    "quote_found",
    "verdict",
    "note",
    "corrected_value",
    "other_values",
    "text_only",
    "check",
    "check_note",
]
SUMMARY_COLUMNS = [
    "family",
    "field",
    "applies",
    "filled",
    "quote_missing",
    "judge_pass",
    "judge_fail",
    "judge_uncertain",
    "wrong",
    "other_values_mentions",
]
Checks = dict[tuple[str, str, str], tuple[str, str]]


def load_selection(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return {r["abstract"]: r for r in csv.DictReader(f)}


def build_rows(
    results: dict[str, Any],
    texts: dict[str, str],
    families: tuple[Family, ...],
    selection: dict[str, dict[str, str]],
    checks: Checks | None = None,
) -> list[dict[str, Any]]:
    checks = checks or {}
    rows: list[dict[str, Any]] = []
    for number in [n for n in selection if n in results]:
        res, sel, text = results[number], selection[number], texts[number]
        names = {a["arm_id"]: a["arm_name"] for a in res["arms"]}
        for fam in families:
            got = res["families"].get(fam.key) or {}
            extracted = got.get("extracted")
            if not extracted:
                continue  # a failed family has no values; the run report lists it
            judge = {
                (i["arm_id"], i["key"]): i
                for i in (got.get("judge") or {}).get("items", [])
            }

            cells = [
                ("trial", "trial", f, extracted["trial"][f.key], "")
                for f in fam.fields
                if f.trial_level
            ] + [
                (
                    arm_id,
                    f"{arm_id}: {names.get(arm_id, '')}",
                    f,
                    v[f.key],
                    v["other_values"],
                )
                for arm_id, v in extracted["arms"].items()
                for f in fam.fields
                if not f.trial_level
            ]
            for arm_id, arm, f, cell, other in cells:
                j = judge.get((arm_id, f.key), {})
                check, note = checks.get((number, arm, f.name), ("", ""))
                rows.append(
                    {
                        "abstract": number,
                        "doi": sel["doi"],
                        "indication": sel["indication"],
                        "arm": arm,
                        "family": fam.title,
                        "field": f.name,
                        "value": cell["value"],
                        "quote": cell["quote"],
                        "quote_found": (
                            quote_found(cell["quote"], text) if cell["value"] else None
                        ),
                        "verdict": j.get("verdict", ""),
                        "note": j.get("note", ""),
                        "corrected_value": j.get("corrected_value", ""),
                        "other_values": other,
                        "text_only": f.text_only,
                        "check": check,
                        "check_note": note,
                    }
                )
    return rows


def _mentions(field: SheetField, text: str) -> int:
    alts = "|".join(
        re.escape(s) for s in sorted({field.name, field.key}, key=len, reverse=True)
    )
    return len(re.findall(rf"(?<![a-z0-9])(?:{alts})(?![a-z0-9])", text, re.I))


def summarize(
    rows: list[dict[str, Any]],
    families: tuple[Family, ...],
    selection: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    abstracts = sorted({r["abstract"] for r in rows})
    out = []
    for fam in families:
        for f in fam.fields:
            mine = [
                r for r in rows if r["field"] == f.name and r["family"] == fam.title
            ]
            filled = [r for r in mine if r["value"]]
            # other_values is per arm, repeated on each of that arm's rows: count once.
            arm_notes = {
                (r["abstract"], r["arm"]): r["other_values"]
                for r in rows
                if r["family"] == fam.title
            }
            out.append(
                {
                    "family": fam.title,
                    "field": f.name,
                    "applies": sum(
                        applies(f, selection[n]["indication"]) for n in abstracts
                    ),
                    "filled": len({r["abstract"] for r in filled}),
                    "quote_missing": sum(r["quote_found"] is False for r in filled),
                    "judge_pass": sum(r["verdict"] == "pass" for r in mine),
                    "judge_fail": sum(r["verdict"] == "fail" for r in mine),
                    "judge_uncertain": sum(r["verdict"] == "uncertain" for r in mine),
                    "wrong": sum(r["check"] == "wrong" for r in mine),
                    "other_values_mentions": sum(
                        _mentions(f, t) for t in arm_notes.values()
                    ),
                }
            )
    return out


def read_checks(path: Path) -> Checks:
    if not path.exists():
        return {}
    ws = openpyxl.load_workbook(path, read_only=True)["Values"]
    it = ws.iter_rows(values_only=True)
    header = list(next(it))
    ix = {
        c: header.index(c) for c in ("abstract", "arm", "field", "check", "check_note")
    }
    return {
        (str(r[ix["abstract"]]), str(r[ix["arm"]]), str(r[ix["field"]])): (
            r[ix["check"]] or "",
            r[ix["check_note"]] or "",
        )
        for r in it
        if r[ix["check"]]
    }


def _sheet(ws: Any, columns: list[str], rows: list[dict[str, Any]]) -> None:
    ws.append(columns)
    for r in rows:
        ws.append([r[c] for c in columns])
    font, wrap = Font(name="Arial", size=10), Alignment(wrap_text=True, vertical="top")
    for row in ws.iter_rows():
        for cell in row:
            cell.font, cell.alignment = font, wrap
    for cell in ws[1]:
        cell.font = Font(name="Arial", size=10, bold=True)
    for i, col in enumerate(columns, 1):
        longest = max([len(col)] + [len(str(r[col] or "")) for r in rows])
        ws.column_dimensions[get_column_letter(i)].width = min(longest + 2, 60)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions


def write_xlsx(
    path: Path, rows: list[dict[str, Any]], summary: list[dict[str, Any]]
) -> None:
    wb = openpyxl.Workbook()
    _sheet(wb.active, COLUMNS, rows)
    wb.active.title = "Values"
    _sheet(wb.create_sheet("Summary"), SUMMARY_COLUMNS, summary)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--results", type=Path, default=Path("data/ash_test_run/results.json")
    )
    p.add_argument(
        "--md", type=Path, default=Path("data/postprocessed/ASH_Abstracts/ASH_2025.md")
    )
    p.add_argument(
        "--selection", type=Path, default=_root / "resources/ash/test_run_selection.csv"
    )
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()

    families = load_families(_root / "resources" / "ash" / "book1_sheet2.csv")
    selection = load_selection(args.selection)
    results = json.loads(args.results.read_text())
    rows = build_rows(
        results, parse_md(args.md), families, selection, read_checks(args.out)
    )
    write_xlsx(args.out, rows, summarize(rows, families, selection))
    print(f"wrote {args.out}: {len(rows)} value rows from {len(results)} abstracts")


if __name__ == "__main__":
    main()
