"""Tests for the deterministic checks on extracted ASH values."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from ash_checks import cell_flags, quote_found, same_on_arms  # noqa: E402
from ash_fields import Family, SheetField  # noqa: E402

TEXT = "Median PFS was 30.1 months (HR 0.55; 95% CI 0.41\u20130.74). CRS in 8 of 21 patients."


def _f(name: str, value_type: str, scope: str = "arm") -> SheetField:
    return SheetField(
        name.lower().replace(" ", "_"),
        name,
        "fam",
        scope,
        "abstract",
        value_type,
        (),
        "",
        "",
        "All",
        "",
    )


def _cell(value: str, quote: str, **kw: object) -> dict[str, object]:
    return {
        "value": value,
        "quote": quote,
        "detail": "",
        "basis": "arm",
        "derived": False,
        **kw,
    }


def test_quote_found_ignores_whitespace_and_dash_variants():
    assert quote_found("95%  CI 0.41-0.74", TEXT)
    assert not quote_found("95% CI 0.40-0.74", TEXT)
    assert not quote_found("", TEXT)


def test_clean_value_has_no_flags():
    assert (
        cell_flags(
            _f("Median PFS", "months_or_nr"),
            _cell("30.1", "Median PFS was 30.1 months"),
            TEXT,
        )
        == []
    )


def test_flags():
    pfs = _f("Median PFS", "months_or_nr")
    assert cell_flags(pfs, _cell("30.1", "PFS was thirty"), TEXT) == [
        "quote_not_in_abstract",
        "number_not_in_quote",
    ]
    assert "bad_type" in cell_flags(
        pfs, _cell("30.1 months", "Median PFS was 30.1 months"), TEXT
    )
    assert cell_flags(_f("HR PFS", "number"), _cell("0.55", "HR 0.55"), TEXT) == [
        "measure_not_in_quote"
    ]
    crs = _f("CRS any grade", "percent")
    assert cell_flags(crs, _cell("38.1", "CRS in 8 of 21 patients"), TEXT) == [
        "number_not_in_quote"
    ]
    assert (
        cell_flags(crs, _cell("38.1", "CRS in 8 of 21 patients", derived=True), TEXT)
        == []
    )
    assert "bad_type" in cell_flags(
        crs, _cell("138", "CRS in 8 of 21 patients", derived=True), TEXT
    )


def test_same_on_arms_unless_pooled():
    fam = Family(
        "fam",
        "Fam",
        (_f("CRS any grade", "percent"), _f("HR PFS", "number", "comparison")),
    )
    cell = _cell("33", "CRS in 33%")
    arms = {"arm_1": {"crs_any_grade": cell}, "arm_2": {"crs_any_grade": dict(cell)}}
    assert same_on_arms(fam, {"arms": arms}) == {
        ("arm_1", "crs_any_grade"),
        ("arm_2", "crs_any_grade"),
    }
    arms["arm_2"]["crs_any_grade"]["basis"] = "pooled"
    arms["arm_1"]["crs_any_grade"]["basis"] = "pooled"
    assert same_on_arms(fam, {"arms": arms}) == set()
