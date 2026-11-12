"""Tests for the ASH test-run review sheet."""

import sys
from pathlib import Path
from typing import Any

import openpyxl

_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "scripts"))

from ash_fields import Family, SheetField  # noqa: E402
from ash_review_sheet import (  # noqa: E402
    build_rows,
    read_checks,
    summarize,
    write_xlsx,
)


def _f(key: str, name: str, applies_to: str = "All", trial: bool = False) -> SheetField:
    return SheetField(key, name, "Text", applies_to, "", False, trial)


ORR = _f("orr", "ORR")
CR = _f("mrd_cr", "MRD-negative CR", "AML")
SUB = _f("disease_subtype", "Disease subtype", trial=True)
FAMILIES = (Family("resp", "Responses", (ORR, CR, SUB)),)

SELECTION = {
    "1": {"doi": "10.1182/blood-2025-1", "indication": "AML", "group": "AML/APL"},
    "2": {
        "doi": "10.1182/blood-2025-2",
        "indication": "Multiple myeloma",
        "group": "PC",
    },
}
TEXTS = {"1": "ORR was 80% in arm A.", "2": "ORR 50%."}


def _cell(value: str, quote: str) -> dict[str, str]:
    return {"value": value, "quote": quote}


def _result(
    n: str, arms: dict[str, Any], judge: list[dict[str, str]]
) -> dict[str, Any]:
    return {
        "abstract": n,
        "arms": [{"arm_id": a, "arm_name": a.upper()} for a in arms],
        "errors": [],
        "families": {
            "resp": {
                "extracted": {
                    "trial": {"disease_subtype": _cell("", "")},
                    "arms": arms,
                },
                "judge": {"items": judge},
                "error": None,
            }
        },
    }


RESULTS = {
    "1": _result(
        "1",
        {
            "arm_1": {
                "orr": _cell("80%", "ORR was 80%"),
                "mrd_cr": _cell("40%", "not in text"),
                "other_values": "ORR in evaluable 85%; orr at 12 months 70%",
            },
            "arm_2": {
                "orr": _cell("", ""),
                "mrd_cr": _cell("", ""),
                "other_values": "",
            },
        },
        [
            {
                "arm_id": "arm_1",
                "key": "orr",
                "verdict": "pass",
                "note": "",
                "corrected_value": "",
            },
            {
                "arm_id": "arm_1",
                "key": "mrd_cr",
                "verdict": "fail",
                "note": "no quote",
                "corrected_value": "",
            },
            {
                "arm_id": "arm_1",
                "key": "other_values",
                "verdict": "fail",
                "note": "off-family",
                "corrected_value": "",
            },
        ],
    ),
    "2": _result(
        "2",
        {
            "arm_1": {
                "orr": _cell("50%", "ORR  50%"),
                "mrd_cr": _cell("", ""),
                "other_values": "CRS rate 10%",
            }
        },
        [],
    ),
}


def test_rows_count_and_fields() -> None:
    rows = build_rows(RESULTS, TEXTS, FAMILIES, SELECTION)
    # abstract 1: 2 arms x 2 per-arm fields + 1 trial field; abstract 2: 1 x 2 + 1
    assert len(rows) == 5 + 3
    trial = [r for r in rows if r["arm"] == "trial"]
    assert [r["abstract"] for r in trial] == ["1", "2"]
    r = next(
        r
        for r in rows
        if r["abstract"] == "1" and r["field"] == "ORR" and r["arm"] == "arm_1: ARM_1"
    )
    assert r["doi"] == "10.1182/blood-2025-1" and r["indication"] == "AML"
    assert r["verdict"] == "pass" and r["value"] == "80%"
    assert "evaluable" in r["other_values"]
    assert (
        r["other_values_verdict"] == "fail" and r["other_values_note"] == "off-family"
    )
    assert trial[0]["other_values_verdict"] == ""


def test_quote_found() -> None:
    rows = build_rows(RESULTS, TEXTS, FAMILIES, SELECTION)
    by = {(r["abstract"], r["arm"], r["field"]): r for r in rows}
    assert by[("1", "arm_1: ARM_1", "ORR")]["quote_found"] is True
    assert by[("1", "arm_1: ARM_1", "MRD-negative CR")]["quote_found"] is False
    assert by[("2", "arm_1: ARM_1", "ORR")]["quote_found"] is True  # whitespace
    assert by[("1", "arm_2: ARM_2", "ORR")]["quote_found"] is None  # no value


def test_summary_counts() -> None:
    rows = build_rows(RESULTS, TEXTS, FAMILIES, SELECTION)
    s = {r["field"]: r for r in summarize(rows, FAMILIES, SELECTION)}
    assert s["MRD-negative CR"]["applies"] == 1  # AML abstract only
    assert s["ORR"]["applies"] == 2
    assert s["ORR"]["filled"] == 2 and s["MRD-negative CR"]["filled"] == 1
    assert s["ORR"]["filled_cells"] == 2 and s["MRD-negative CR"]["filled_cells"] == 1
    assert s["MRD-negative CR"]["quote_missing"] == 1
    assert s["ORR"]["judge_pass"] == 1 and s["MRD-negative CR"]["judge_fail"] == 1
    # Review Focus 1: a field named twice in other_values counts twice.
    assert s["ORR"]["other_values_mentions"] == 2
    assert s["MRD-negative CR"]["other_values_mentions"] == 0


def test_wrong_counted_from_sheet(tmp_path: Path) -> None:
    rows = build_rows(RESULTS, TEXTS, FAMILIES, SELECTION)
    out = tmp_path / "review.xlsx"
    write_xlsx(out, rows, summarize(rows, FAMILIES, SELECTION))
    wb = openpyxl.load_workbook(out)
    ws = wb["Values"]
    header = [c.value for c in ws[1]]
    for row in ws.iter_rows(min_row=2):
        if row[header.index("field")].value == "ORR" and row[0].value == "2":
            row[header.index("check")].value = "wrong"
    wb.save(out)

    rebuilt = build_rows(RESULTS, TEXTS, FAMILIES, SELECTION, read_checks(out))
    s = {r["field"]: r for r in summarize(rebuilt, FAMILIES, SELECTION)}
    assert s["ORR"]["wrong"] == 1 and s["MRD-negative CR"]["wrong"] == 0
    assert openpyxl.load_workbook(out).sheetnames == ["Values", "Summary"]
