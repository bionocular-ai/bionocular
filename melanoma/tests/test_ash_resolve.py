"""Tests for the tracked ASH resolver (resolved.json)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from ash_resolve import resolve_run  # noqa: E402

RUN = Path(__file__).parent / "fixtures" / "ash_supabase" / "run"
KEYS = {
    "abstract", "doi", "indication", "nct_ids", "arm_id", "arm_name", "arm_role",
    "field_key", "context", "value_text", "n", "detail", "derived", "origin", "caveat",
}  # fmt: skip


@pytest.fixture(scope="module")
def records() -> list[dict]:
    return resolve_run(RUN)


def _main(records: list[dict], abstract: str, key: str, arm: str | None) -> list[dict]:
    return [
        r
        for r in records
        if (r["abstract"], r["field_key"], r["arm_id"], r["context"])
        == (abstract, key, arm, "")
    ]


def test_cleared_value_absent(records):
    assert _main(records, "101", "cr_rate", "arm_1") == []
    assert [r["value_text"] for r in _main(records, "101", "cr_rate", "arm_2")] == [
        "50"
    ]


def test_override_applied(records):
    [r] = _main(records, "102", "cr_rate", "arm_1")
    assert r["value_text"] == "42" and r["caveat"] is None
    assert r["nct_ids"] == [] and r["indication"] == "Multiple Myeloma"


def test_caveat_from_note(records):
    [r] = _main(records, "103", "cr_rate", "arm_1")
    assert r["value_text"] == "60"
    assert r["caveat"] == "possible source error, literal value kept: needs a person"


def test_no_quote_key(records):
    assert records and all(set(r) == KEYS for r in records)


def test_registry_origin(records):
    [r] = _main(records, "103", "route", "arm_1")
    assert r["origin"] == "registry" and r["value_text"] == "IV"  # full_v2 beats v1
    assert {r["origin"] for r in records if r["field_key"] != "route"} == {"abstract"}


def test_trial_scope_has_no_arm(records):
    [r] = [r for r in records if r["field_key"] == "response_criteria"]
    assert r["arm_id"] is None and r["arm_name"] is None and r["value_text"] == "iwCLL"
    assert r["indication"] == "Chronic Lymphocytic Leukemia" and r["doi"].endswith(
        "101"
    )


def test_pooled_and_extra(records):
    pooled = [r for r in records if r["abstract"] == "101" and r["arm_id"] is None]
    assert {(r["field_key"], r["context"], r["value_text"]) for r in pooled} == {
        ("response_criteria", "", "iwCLL"),
        ("cr_rate", "all patients", "30"),
    }
    [extra] = [r for r in records if r["context"] == "del17p"]
    assert (extra["arm_id"], extra["value_text"], extra["n"]) == ("arm_1", "90", 10)


def test_dose_levels_named_apart(records):
    names = {r["arm_id"]: r["arm_name"] for r in records if r["abstract"] == "104"}
    assert names == {"arm_1": "drug E [10 mg]", "arm_2": "drug E [20 mg]"}


def test_nct_ids_in_citation_order(records):
    # 104 cites NCT00000104 before the numerically lower NCT00000050; NCT00000070
    # is not in the text, so it goes last, in its existing order
    assert {tuple(r["nct_ids"]) for r in records if r["abstract"] == "104"} == {
        ("NCT00000104", "NCT00000050", "NCT00000070")
    }
