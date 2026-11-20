"""ASH results workbook for reading a run: one row per arm, one column per field.

Usage (from melanoma/):
  poetry run python3 scripts/ash_results_sheet.py --results data/ash_test_run/full_v1/results.json \\
      --registry data/ash_test_run/full_v1/registry.json \\
      --md data/postprocessed/ASH_Abstracts/ASH_2025_all.md \\
      --selection data/ash_test_run/full_v1/selection.csv \\
      --out ../.lavish/ash-integration/ash_full_v1_results.xlsx

Abstract values come first; a registry value fills a field the abstract left empty.
Each filled cell carries its quote as a comment. Red: the judge says the value is wrong.
Yellow: a code check flagged it, the quote is not in the source, or the judge is unsure.
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill

_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(Path(__file__).parent))

from ash_checks import AE_CLASS  # noqa: E402
from ash_fields import load_families  # noqa: E402
from ash_registry_run import registry_family  # noqa: E402
from ash_review_sheet import build_rows, load_selection  # noqa: E402
from ash_test_run import META, parse_md  # noqa: E402

RED = PatternFill("solid", fgColor="FFF8D7DA")
YELLOW = PatternFill("solid", fgColor="FFFFF3CD")
OTHER = "Other values (field: value, context)"
SETTING = "Setting (line of therapy)"


def _arm_id(label: str) -> str:
    return label.split(":", 1)[0]


def _tone(cell: dict[str, Any]) -> str:
    if cell.get("value_ok") == "no":
        return "red"
    if cell.get("flags") or cell.get("quote_found") is False:
        return "yellow"
    return "yellow" if cell.get("value_ok") == "unsure" else ""


def _shown(cell: dict[str, Any]) -> str:
    """The value, with the patients a rate is over when the abstract states them and
    the AE class when the field carries one."""
    tag = AE_CLASS.search(str(cell.get("detail") or "").strip())
    return (
        cell["value"]
        + (f" (n={cell['n']})" if cell.get("n") else "")
        + (f" {tag.group(1)}" if tag and tag.group(1) != "not stated" else "")
    )


def _note(cell: dict[str, Any]) -> str:
    parts = [f"quote: {cell['quote']}"]
    for key in ("detail", "flags", "error"):
        if cell.get(key):
            parts.append(f"{key}: {cell[key]}")
    if cell.get("source") == "registry":
        parts.append("source: ClinicalTrials.gov")
    return "\n".join(parts)[:1000]


def registry_cells(
    entry: dict[str, Any], names: dict[str, str]
) -> list[dict[str, Any]]:
    """One dict per filled registry value: arm ('trial' for trial-level), field, value..."""
    out: list[dict[str, Any]] = []
    extracted = entry.get("extracted") or {}
    scopes = [("trial", extracted.get("trial", {})), *extracted.get("arms", {}).items()]
    for arm_id, cells in scopes:
        for key, cell in cells.items():
            if key == "extra" or not cell["value"]:
                continue
            out.append(
                {
                    "arm": arm_id,
                    "field": names[key],
                    "value": cell["value"],
                    "quote": cell["quote"],
                    "detail": cell["detail"],
                    "flags": ", ".join(
                        entry.get("flags", {}).get(f"{arm_id}.{key}", [])
                    ),
                    "source": "registry",
                }
            )
    return out


def wide_rows(
    results: dict[str, Any],
    registry: dict[str, Any],
    rows: list[dict[str, Any]],
    registry_names: dict[str, str],
) -> dict[str, dict[str, dict[str, Any]]]:
    """abstract -> arm_id (or 'trial') -> field -> cell. Abstract first, registry fills gaps."""
    wide: dict[str, dict[str, dict[str, Any]]] = {n: {} for n in results}
    for r in rows:
        if r["kind"] != "field" or not r["value"]:
            continue
        wide[r["abstract"]].setdefault(_arm_id(r["arm"]), {})[r["field"]] = {
            **r,
            "source": "abstract",
        }
    for number, entry in registry.items():
        if number not in wide:
            continue
        for cell in registry_cells(entry, registry_names):
            wide[number].setdefault(cell["arm"], {}).setdefault(cell["field"], cell)
    return wide


def _write(ws: Any, headers: list[str], widths: dict[str, int]) -> None:
    ws.append(headers)
    for i, h in enumerate(headers, start=1):
        c = ws.cell(1, i)
        c.font = Font(bold=True)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.column_dimensions[c.column_letter].width = widths.get(h, 14)


def build(args: argparse.Namespace) -> None:
    csv_path = _root / "resources" / "ash" / "book1_sheet2.csv"
    families = load_families(csv_path)
    reg_family = registry_family(csv_path)
    registry_names = {f.key: f.name for f in reg_family.fields}
    selection = load_selection(args.selection)
    results = json.loads(args.results.read_text(encoding="utf-8"))
    results.pop(META, None)
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    registry.pop(META, None)
    texts = parse_md(args.md)
    rows = build_rows(results, texts, families, selection)
    wide = wide_rows(results, registry, rows, registry_names)

    with csv_path.open(newline="", encoding="utf-8") as f:
        order = [SETTING] + [r["field"] for r in csv.DictReader(f)]  # workbook order
    used = {f for arms in wide.values() for cells in arms.values() for f in cells}
    fields = list(dict.fromkeys(f for f in order if f in used))

    wb = openpyxl.Workbook()
    ov = wb.active
    ov.title = "Overview"
    ov_head = [
        "abstract", "doi", "indication", "group", "title", "arms", "values",
        "abstract_values", "registry_values", "red", "yellow", "pooled_values",
        "other_values", "errors",
    ]  # fmt: skip
    _write(ov, ov_head, {"title": 60, "errors": 40, "doi": 24, "indication": 18})
    arms_ws = wb.create_sheet("Arms")
    arm_head = [
        "abstract",
        "doi",
        "indication",
        "arm_id",
        "arm",
        "dose_level",
        "role",
        *fields,
        OTHER,
    ]
    _write(arms_ws, arm_head, {"arm": 32, OTHER: 60})
    pooled_ws = wb.create_sheet("Pooled (all arms together)")
    _write(
        pooled_ws, ["abstract", "indication", "pooled values"], {"pooled values": 90}
    )

    for number in [n for n in selection if n in results]:
        res, sel = results[number], selection[number]
        mine = [r for r in rows if r["abstract"] == number]
        trial = wide[number].get("trial", {})
        tones = {"red": 0, "yellow": 0}
        filled = {"abstract": 0, "registry": 0}
        for arm in res["arms"]:
            cells = {**trial, **wide[number].get(arm["arm_id"], {})}
            arms_ws.append(
                [number, sel["doi"], sel["indication"], arm["arm_id"], arm["arm_name"],
                 arm.get("dose_level") or None, arm["role"]]
                + [_shown(cells[f]) if f in cells else None for f in fields]
                + ["; ".join(
                    f"{r['field']}: {_shown(r)} ({r['context']})"
                    for r in mine
                    if r["kind"] == "extra" and _arm_id(r["arm"]) == arm["arm_id"]
                ) or None]
            )  # fmt: skip
            row = arms_ws.max_row
            for i, f in enumerate(fields, start=8):
                if f not in cells:
                    continue
                c = arms_ws.cell(row, i)
                c.comment = Comment(_note(cells[f]), "pipeline")
                tone = _tone(cells[f])
                if tone:
                    c.fill = RED if tone == "red" else YELLOW
            for cell in wide[number].get(arm["arm_id"], {}).values():
                filled[cell["source"]] += 1
                tone = _tone(cell)
                if tone:
                    tones[tone] += 1
        for cell in trial.values():
            filled[cell["source"]] += 1
            tone = _tone(cell)
            if tone:
                tones[tone] += 1
        pooled = [r for r in mine if r["kind"] == "pooled" and r["value"]]
        if pooled:
            pooled_ws.append(
                [number, sel["indication"], "; ".join(
                    f"{r['field']}: {_shown(r)}" + (f" ({r['context']})" if r["context"] else "")
                    for r in pooled
                )]
            )  # fmt: skip
        errors = list(res.get("errors") or []) + [
            f"{k}: {f['error']}" for k, f in res["families"].items() if f["error"]
        ]
        if registry.get(number, {}).get("error"):
            errors.append(f"registry: {registry[number]['error']}")
        title = re.search(r"#### Title:\n(.+)", texts[number])
        ov.append(
            [number, sel["doi"], sel["indication"], sel.get("group", ""),
             title.group(1).strip() if title else "", len(res["arms"]),
             filled["abstract"] + filled["registry"], filled["abstract"],
             filled["registry"], tones["red"], tones["yellow"], len(pooled),
             sum(r["kind"] == "extra" for r in mine), "; ".join(errors)[:500] or None]
        )  # fmt: skip

    for ws in (ov, arms_ws, pooled_ws):
        ws.freeze_panes = "G2" if ws is arms_ws else "A2"
        ws.auto_filter.ref = ws.dimensions
    args.out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(args.out)
    print(
        f"wrote {args.out}: {ov.max_row - 1} abstracts, {arms_ws.max_row - 1} arms, "
        f"{len(fields)} field columns"
    )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", type=Path, required=True)
    p.add_argument("--registry", type=Path, required=True)
    p.add_argument("--md", type=Path, required=True)
    p.add_argument("--selection", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    build(p.parse_args())


if __name__ == "__main__":
    main()
