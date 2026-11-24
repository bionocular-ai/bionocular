"""Tests for the ASH results workbook."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from ash_results_sheet import (  # noqa: E402
    _listed,
    _shown,
    _tone,
    apply_judge,
    apply_reviewed,
    wide_rows,
)


def _cell(value: str) -> dict:
    return {"value": value, "quote": "q", "detail": "", "derived": False}


def test_abstract_value_wins_and_registry_fills_gaps():
    rows = [
        {"abstract": "1", "arm": "arm_1: drug A", "kind": "field", "field": "Route", "value": "IV"},
        {"abstract": "1", "arm": "arm_1: drug A", "kind": "extra", "field": "Dose", "value": "5"},
    ]  # fmt: skip
    registry = {
        "1": {
            "extracted": {
                "trial": {"setting": _cell("newly diagnosed")},
                "arms": {"arm_1": {"route": _cell("SC"), "target": _cell("CD38")}},
            },
            "flags": {},
        }
    }
    names = {"setting": "Setting", "route": "Route", "target": "Target"}
    wide = wide_rows({"1": {}}, registry, rows, names)
    arm = wide["1"]["arm_1"]
    assert arm["Route"]["value"] == "IV" and arm["Route"]["source"] == "abstract"
    assert arm["Target"]["value"] == "CD38" and arm["Target"]["source"] == "registry"
    assert "Dose" not in arm  # extras go to the other-values column, not a field
    assert wide["1"]["trial"]["Setting"]["value"] == "newly diagnosed"


def test_rates_show_their_denominator():
    assert _shown({"value": "77.8", "n": "9"}) == "77.8 (n=9)"
    assert _shown({"value": "77.8", "n": ""}) == "77.8"
    assert _shown(_cell("CD38")) == "CD38"  # registry cells carry no n
    assert _shown({"value": "40", "n": "21", "detail": "lymphopenia; TEAE"}) == (
        "40 (n=21) TEAE"
    )
    assert _shown({"value": "40", "detail": "not stated"}) == "40"


def test_apply_judge_takes_right_values_quoted_from_the_abstract() -> None:
    text = "ORR was 62% (31 of 50). CR rate 20%."
    base = {"abstract": "1", "value": "80", "quote": "q", "n": "50", "flags": "x"}
    rows = [
        {**base, "value_ok": "no", "error": "wrong_number", "right_value": "62",
         "right_quote": "ORR was 62%"},
        {**base, "value_ok": "no", "right_value": "70", "right_quote": "ORR was 70%"},
        {**base, "value_ok": "no", "right_value": "", "right_quote": ""},
        {**base, "value_ok": "yes", "right_value": "62", "right_quote": "ORR was 62%"},
        {**base, "value_ok": "no", "right_value": "80", "right_quote": "ORR was 62%"},
    ]  # fmt: skip
    assert apply_judge(rows, {"1": text}) == 1
    assert rows[0]["value"] == "62" and rows[0]["n"] == "" and rows[0]["flags"] == ""
    assert rows[0]["patched"] == "80 (judge: wrong_number)"
    assert _tone(rows[0]) == "patched"
    assert [r["value"] for r in rows[1:]] == ["80"] * 4  # unquoted, none, ok, same
    assert _tone(rows[1]) == _tone(rows[2]) == "red"


def test_apply_reviewed_writes_fixes_matched_by_cell() -> None:
    cell = {"abstract": "1", "arm": "arm_1: X", "field": "Median age", "kind": "field",
            "context": "", "value": "51-69", "quote": "q", "n": "", "flags": "bad_type",
            "value_ok": "yes"}  # fmt: skip
    rows = [cell, {**cell, "arm": "arm_2: Y"}]
    reviewed = [
        {**{k: cell[k] for k in ("abstract", "arm", "field", "kind", "context", "value")},
         "verdict": "fix", "correct_value": "58.5", "quote": "median aged 58.5"},
        {**{k: cell[k] for k in ("abstract", "field", "kind", "context", "value")},
         "arm": "arm_2: Y", "verdict": "wrong", "correct_value": ""},
    ]  # fmt: skip
    assert apply_reviewed(rows, reviewed, "expert") == 1
    assert rows[0]["value"] == "58.5" and rows[0]["quote"] == "median aged 58.5"
    assert rows[0]["patched"] == "51-69 (expert)" and _tone(rows[0]) == "patched"
    assert rows[1]["value"] == "51-69"  # only fixes are written


def test_listed_names_the_old_value_of_a_patched_extra() -> None:
    r = {"field": "ORR rate", "value": "62", "n": "", "context": "R/R only"}
    assert _listed(r) == "ORR rate: 62 (R/R only)"
    assert _listed({**r, "context": "", "patched": "80 (expert)"}) == (
        "ORR rate: 62 [was 80 (expert)]"
    )
