"""Build the ASH test-run review sheet (.xlsx) from results.json.

Usage (from melanoma/):
  poetry run python3 scripts/ash_review_sheet.py --results data/ash_test_run/results.json \\
      --out ../.lavish/ash-integration/ash_test_review_v2.xlsx

One row per asked field and arm, plus one row per extra value and per missed value.
Rerunning keeps the check and check_note columns already typed into --out.
"""

import argparse
import csv
import json
import sys
from functools import partial
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(Path(__file__).parent))

from ash_checks import quote_found  # noqa: E402
from ash_fields import Family, applies, load_families  # noqa: E402
from ash_test_run import META, parse_md  # noqa: E402

COLUMNS = [
    "abstract",
    "doi",
    "indication",
    "arm",
    "family",
    "field",
    "kind",
    "context",
    "value",
    "detail",
    "derived",
    "quote",
    "quote_found",
    "flags",
    "value_ok",
    "quote_ok",
    "error",
    "right_value",
    "right_quote",
    "check",
    "check_note",
]
SUMMARY_COLUMNS = [
    "family",
    "field",
    "applies",
    "filled",
    "filled_cells",
    "quote_missing",
    "flagged",
    "judge_no",
    "judge_unsure",
    "quote_not_ok",
    "extra_values",
    "pooled",
    "missed",
    "wrong",
]
Checks = dict[tuple[str, str, str, str], tuple[str, str]]
_NO_VERDICT = {
    "value_ok": "",
    "quote_ok": "",
    "error": "",
    "right_value": "",
    "right_quote": "",
}


def _row(
    family: str, arm: str, field: str, kind: str, cols: dict[str, Any]
) -> dict[str, Any]:
    blank = dict.fromkeys(
        ("context", "value", "detail", "derived", "quote", "flags"), ""
    )
    return {
        "arm": arm,
        "family": family,
        "field": field,
        "kind": kind,
        **blank,
        **_NO_VERDICT,
        **cols,
    }


def _add(
    out: list[dict[str, Any]],
    names: dict[str, str],
    fam: Family,
    arm_id: str,
    field: str,
    kind: str,
    **cols: Any,
) -> None:
    out.append(_row(fam.title, names.get(arm_id, arm_id), field, kind, cols))


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
        names = {a["arm_id"]: f"{a['arm_id']}: {a['arm_name']}" for a in res["arms"]}
        names["trial"] = "trial"
        names["pooled"] = "pooled (all arms)"

        mine: list[dict[str, Any]] = []

        add = partial(_add, mine, names)

        for fam in families:
            got = res["families"].get(fam.key) or {}
            extracted = got.get("extracted")
            if not extracted:
                continue  # not asked for this indication, or the family failed
            name_of = {f.key: f.name for f in fam.fields}
            verdicts = {i["id"]: i for i in (got.get("judge") or {}).get("items", [])}
            judged = {
                (i["kind"], i["arm_id"], i["key"], i.get("context", "")): {
                    k: verdicts.get(i["id"], _NO_VERDICT)[k] for k in _NO_VERDICT
                }
                for i in got.get("items", [])
            }
            for i, p in enumerate(extracted.get("pooled", [])):
                add(
                    fam,
                    "pooled",
                    name_of[p["field"]],
                    "pooled",
                    value=p["value"],
                    context=p["context"],
                    detail=p["detail"],
                    derived="yes" if p["derived"] else "",
                    quote=p["quote"],
                    flags=", ".join(got["flags"].get(f"pooled.{i}", [])),
                    **judged.get(("pooled", "pooled", p["field"], p["context"]), {}),
                )
            scopes = list(extracted.get("arms", {}).items())
            if "trial" in extracted:
                scopes.insert(0, ("trial", extracted["trial"]))
            for arm_id, cells in scopes:
                for key, cell in cells.items():
                    if key == "extra":
                        continue
                    add(
                        fam,
                        arm_id,
                        name_of[key],
                        "field",
                        value=cell["value"],
                        detail=cell["detail"],
                        derived="yes" if cell["derived"] else "",
                        quote=cell["quote"],
                        flags=", ".join(got["flags"].get(f"{arm_id}.{key}", [])),
                        **judged.get(("field", arm_id, key, ""), {}),
                    )
                for i, ex in enumerate(cells.get("extra", [])):
                    add(
                        fam,
                        arm_id,
                        name_of[ex["field"]],
                        "extra",
                        value=ex["value"],
                        context=ex["context"],
                        quote=ex["quote"],
                        flags=", ".join(got["flags"].get(f"{arm_id}.extra.{i}", [])),
                        **judged.get(("extra", arm_id, ex["field"], ex["context"]), {}),
                    )
            for m in (got.get("missed") or {}).get("items", []):
                add(
                    fam,
                    m["arm_id"],
                    name_of[m["field"]],
                    "missed",
                    value=m["value"],
                    quote=m["quote"],
                )
        for r in mine:
            key = (number, r["arm"], r["field"], r["context"])
            r["check"], r["check_note"] = checks.get(key, ("", ""))
            r["quote_found"] = quote_found(r["quote"], text) if r["value"] else None
            rows.append(
                {
                    "abstract": number,
                    "doi": sel["doi"],
                    "indication": sel["indication"],
                    **r,
                }
            )
    return rows


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
            main = [r for r in mine if r["kind"] == "field"]
            filled = [r for r in main if r["value"]]
            out.append(
                {
                    "family": fam.title,
                    "field": f.name,
                    "applies": sum(
                        applies(f, selection[n]["indication"]) for n in abstracts
                    ),
                    "filled": len({r["abstract"] for r in filled}),
                    "filled_cells": len(filled),
                    "quote_missing": sum(r["quote_found"] is False for r in filled),
                    "flagged": sum(bool(r["flags"]) for r in filled),
                    "judge_no": sum(r["value_ok"] == "no" for r in mine),
                    "judge_unsure": sum(r["value_ok"] == "unsure" for r in mine),
                    "quote_not_ok": sum(r["quote_ok"] == "no" for r in mine),
                    "extra_values": sum(r["kind"] == "extra" for r in mine),
                    "pooled": sum(r["kind"] == "pooled" for r in mine),
                    "missed": sum(r["kind"] == "missed" for r in mine),
                    "wrong": sum(
                        str(r["check"]).strip().lower() == "wrong" for r in mine
                    ),
                }
            )
    return out


def read_checks(path: Path) -> Checks:
    if not path.exists():
        return {}
    wb = openpyxl.load_workbook(path, read_only=True)
    it = wb["Values"].iter_rows(values_only=True)
    header = list(next(it))
    ix = {
        c: header.index(c)
        for c in ("abstract", "arm", "field", "context", "check", "check_note")
    }
    checks = {
        (
            str(r[ix["abstract"]]),
            str(r[ix["arm"]]),
            str(r[ix["field"]]),
            str(r[ix["context"]] or ""),
        ): (r[ix["check"]] or "", r[ix["check_note"]] or "")
        for r in it
        if r[ix["check"]]
    }
    wb.close()
    return checks


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
    results = json.loads(args.results.read_text(encoding="utf-8"))
    results.pop(META, None)
    rows = build_rows(
        results, parse_md(args.md), families, selection, read_checks(args.out)
    )
    write_xlsx(args.out, rows, summarize(rows, families, selection))
    print(f"wrote {args.out}: {len(rows)} value rows from {len(results)} abstracts")


if __name__ == "__main__":
    main()
