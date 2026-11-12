"""Tests for the ASH test-run review sheet builder."""

import sys
from pathlib import Path
from typing import Any

import openpyxl

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from ash_fields import Family, SheetField  # noqa: E402
from ash_review_sheet import (  # noqa: E402
    COLUMNS,
    build_rows,
    read_checks,
    summarize,
    write_xlsx,
)


def _f(key: str, name: str, applies_to: str = "All", scope: str = "arm") -> SheetField:
    return SheetField(
        key, name, "resp", scope, "abstract", "percent", (), "", "", applies_to, ""
    )


ORR = _f("orr", "ORR")
CR = _f("mrd_cr", "MRD-negative CR", "AML")
SUB = _f("disease_subtype", "Disease subtype", scope="trial")
FAMILIES = (Family("resp", "Responses", (ORR, CR, SUB)),)
SELECTION = {
    "1": {"abstract": "1", "doi": "d1", "indication": "AML", "group": "g"},
    "2": {"abstract": "2", "doi": "d2", "indication": "CML", "group": "g"},
    "3": {"abstract": "3", "doi": "d3", "indication": "CML", "group": "g"},  # not run
}
TEXTS = {
    "1": "ORR was 80% in arm A. In patients over 75, ORR was 60%.",
    "2": "ORR 50%.",
}


def _cell(value: str = "", quote: str = "", **kw: Any) -> dict[str, Any]:
    return {
        "value": value,
        "quote": quote,
        "detail": "",
        "basis": "arm",
        "derived": False,
        **kw,
    }


RESULTS: dict[str, Any] = {
    "1": {
        "arms": [{"arm_id": "arm_1", "arm_name": "A", "role": "single arm"}],
        "families": {
            "resp": {
                "extracted": {
                    "trial": {"disease_subtype": _cell("AML", "not in text")},
                    "arms": {
                        "arm_1": {
                            "orr": _cell("80", "ORR was 80%"),
                            "mrd_cr": _cell(),
                            "extra": [
                                {
                                    "field": "orr",
                                    "value": "60",
                                    "context": "over 75",
                                    "quote": "ORR was 60%",
                                }
                            ],
                        }
                    },
                },
                "flags": {"trial.disease_subtype": ["quote_not_in_abstract"]},
                "items": [
                    {
                        "id": 1,
                        "kind": "field",
                        "arm_id": "trial",
                        "key": "disease_subtype",
                    },
                    {"id": 2, "kind": "field", "arm_id": "arm_1", "key": "orr"},
                    {
                        "id": 3,
                        "kind": "extra",
                        "arm_id": "arm_1",
                        "key": "orr",
                        "context": "over 75",
                    },
                ],
                "judge": {
                    "items": [
                        {
                            "id": 1,
                            "value_ok": "no",
                            "quote_ok": "no",
                            "error": "not_stated",
                            "right_value": "",
                            "right_quote": "",
                        },
                        {
                            "id": 3,
                            "value_ok": "unsure",
                            "quote_ok": "yes",
                            "error": "",
                            "right_value": "",
                            "right_quote": "",
                        },
                    ]
                },
                "missed": {
                    "items": [
                        {
                            "arm_id": "arm_1",
                            "field": "mrd_cr",
                            "value": "40",
                            "quote": "q",
                        }
                    ]
                },
                "error": None,
            }
        },
    },
    "2": {
        "arms": [{"arm_id": "arm_1", "arm_name": "B", "role": "single arm"}],
        "families": {"resp": {"extracted": None, "error": "boom"}},
    },
}


def _rows(checks: Any = None) -> list[dict[str, Any]]:
    return build_rows(RESULTS, TEXTS, FAMILIES, SELECTION, checks)


def _one(rows: list[dict[str, Any]], **want: Any) -> dict[str, Any]:
    (row,) = (r for r in rows if all(r[k] == v for k, v in want.items()))
    return row


def test_rows_fields_extras_and_missed() -> None:
    rows = _rows()
    assert [r["kind"] for r in rows] == ["field", "field", "field", "extra", "missed"]
    assert all(set(r) == set(COLUMNS) for r in rows)
    sub = _one(rows, field="Disease subtype")
    assert sub["arm"] == "trial" and sub["quote_found"] is False
    assert sub["flags"] == "quote_not_in_abstract" and sub["error"] == "not_stated"
    orr = _one(rows, field="ORR", kind="field")
    assert orr["arm"] == "arm_1: A" and orr["quote_found"] is True
    assert orr["value_ok"] == ""  # the judge skipped id 2
    extra = _one(rows, kind="extra")
    assert extra["context"] == "over 75" and extra["value_ok"] == "unsure"
    assert _one(rows, field="MRD-negative CR", kind="field")["quote_found"] is None
    assert _one(rows, kind="missed")["value"] == "40"


def test_summary_counts() -> None:
    by_field = {s["field"]: s for s in summarize(_rows(), FAMILIES, SELECTION)}
    orr = by_field["ORR"]
    assert (orr["filled_cells"], orr["extra_values"], orr["judge_unsure"]) == (1, 1, 1)
    assert by_field["MRD-negative CR"]["applies"] == 1  # AML only, abstract 1
    assert by_field["MRD-negative CR"]["missed"] == 1
    sub = by_field["Disease subtype"]
    assert (sub["quote_missing"], sub["flagged"], sub["judge_no"]) == (1, 1, 1)


def test_checks_survive_a_rebuild(tmp_path: Path) -> None:
    out = tmp_path / "r.xlsx"
    rows = _rows()
    write_xlsx(out, rows, summarize(rows, FAMILIES, SELECTION))
    wb = openpyxl.load_workbook(out)
    ws = wb["Values"]
    head = [c.value for c in ws[1]]
    for r in ws.iter_rows(min_row=2):
        if r[head.index("kind")].value == "extra":
            r[head.index("check")].value = "wrong"
            r[head.index("check_note")].value = "subgroup is 62"
    wb.save(out)
    rows = _rows(read_checks(out))
    assert _one(rows, kind="extra")["check"] == "wrong"
    assert _one(rows, field="ORR", kind="field")["check"] == ""
    assert {s["field"]: s["wrong"] for s in summarize(rows, FAMILIES, SELECTION)}[
        "ORR"
    ] == 1
