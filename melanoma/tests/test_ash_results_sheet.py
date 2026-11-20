"""Tests for the ASH results workbook."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from ash_results_sheet import _shown, wide_rows  # noqa: E402


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
