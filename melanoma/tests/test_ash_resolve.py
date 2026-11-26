"""Tests for the tracked ASH resolver (resolved.json)."""

import csv
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import ash_resolve  # noqa: E402
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


IMWG = {
    "protocolSection": {
        "outcomesModule": {"primaryOutcomes": [{"measure": "CR rate per IMWG"}]}
    }
}


def _cli(monkeypatch, tmp_path, *flags, studies=None) -> Path:
    """Runs the CLI on a copy of the fixture run, with the registry served from
    `studies` instead of ClinicalTrials.gov. Returns the copy."""
    run = tmp_path / "run"
    if not run.exists():
        shutil.copytree(RUN, run)
    monkeypatch.setattr(
        ash_resolve, "fetch", lambda nct, cache, client: (studies or {}).get(nct)
    )
    monkeypatch.setattr(sys, "argv", ["ash_resolve.py", "--run", str(run), *flags])
    ash_resolve.main()
    return run


def test_registry_criteria_filled_by_default(monkeypatch, tmp_path):
    run = _cli(monkeypatch, tmp_path, studies={"NCT00000103": IMWG})
    out = json.loads((run / "resolved.json").read_text())
    [crit] = [
        r
        for r in out
        if r["origin"] == "registry" and r["field_key"] == "response_criteria"
    ]
    assert (crit["abstract"], crit["value_text"]) == ("103", "IMWG")
    run = _cli(
        monkeypatch, tmp_path, "--no-registry-criteria", studies={"NCT00000103": IMWG}
    )
    out = json.loads((run / "resolved.json").read_text())
    assert not [
        r
        for r in out
        if r["field_key"] == "response_criteria" and r["origin"] == "registry"
    ]


def test_failed_check_leaves_resolved_json(monkeypatch, tmp_path):
    run = tmp_path / "run"
    shutil.copytree(RUN, run)
    (run / "resolved.json").write_text("previous")
    monkeypatch.setattr(
        ash_resolve, "check_xlsx", lambda records, path: (["bad"], Counter())
    )
    with pytest.raises(SystemExit) as e:
        _cli(monkeypatch, tmp_path, "--check-xlsx", "sheet.xlsx")
    assert e.value.code == 1
    assert (run / "resolved.json").read_text() == "previous"


def test_zero_registry_fills(monkeypatch, tmp_path, capsys):
    run = _cli(monkeypatch, tmp_path)
    assert json.loads((run / "resolved.json").read_text()) == resolve_run(RUN)
    with (run / "spot_check.csv").open() as f:
        assert list(csv.reader(f)) == [
            ["abstract", "nct", "set", "indication", "sentence", "ok", "why"]
        ]
    assert "registry criteria: 0 filled" in capsys.readouterr().out
