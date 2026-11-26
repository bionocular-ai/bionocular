"""Tests for the ASH loader (resolved.json -> outcome_fields, trial_outcomes, outcome_values)."""

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import upload_ash_supabase  # noqa: E402
from upload_ash_supabase import (  # noqa: E402
    WIDE_COLUMNS,
    abstract_payload,
    drift,
    field_rows,
    parse_value,
)

FIX = Path(__file__).parent / "fixtures" / "ash_supabase"
RECORDS = json.loads((FIX / "resolved.json").read_text())
COLUMNS = dict(
    line.split(": ", 1)
    for line in (FIX / "trial_outcomes_columns.txt").read_text().splitlines()
)
VAL_KEYS = {
    "trial_outcome_id", "source_type", "source_id", "source_url", "nct_id", "cancer_type",
    "field_key", "context", "value_text", "value_num", "qualifier", "n", "detail",
    "derived", "origin", "caveat",
}  # fmt: skip
NUMERIC = {"percent", "months", "months_or_nr", "count", "number", "p_value"}


def _abstract(a: str) -> list[dict]:
    return [r for r in RECORDS if r["abstract"] == a]


def _payload(a: str) -> tuple[list[dict], list[dict]]:
    return abstract_payload(_abstract(a))


def _arm(arms: list[dict], arm_id: str) -> dict:
    [arm] = [x for x in arms if x["arm_id"] == arm_id]
    return arm


def test_parse_value():
    assert parse_value("NR", "months_or_nr") == (None, "NR")
    assert parse_value("<0.001", "p_value") == (0.001, "<")
    assert parse_value("0.86-3.28", "range") == (None, None)
    assert parse_value("81.1", "percent") == (81.1, None)
    assert parse_value("6 cycles", "text") == (None, None)


def test_parse_value_other_forms():
    assert parse_value("=0.002", "p_value") == (0.002, None)
    assert parse_value("<.0001", "p_value") == (0.0001, "<")
    assert parse_value(">0.99", "p_value") == (0.99, ">")
    assert parse_value("NE", "months_or_nr") == (None, None)
    assert parse_value("NR", "text") == (None, None)


def test_payload_ids():
    arms, vals = _payload("1")
    arm = _arm(arms, "arm_1")
    assert arm["id"] == "abstract_ASH_2025_1_arm_1"
    assert arm["abstract_id"] == "ASH_2025_1"
    assert arm["source_name"] == "extraction_results_ASH_2025"
    assert arm["source_url"] == "https://doi.org/10.1182/blood-2025-1"
    assert {v["source_id"] for v in vals} == {"ASH_2025_1"}
    arm_vals = [v for v in vals if v["trial_outcome_id"] == arm["id"]]
    assert arm_vals and all(v["source_type"] == "abstract" for v in arm_vals)


def test_payload_pooled_only():
    arms, vals = _payload("2")
    assert arms == []
    assert vals and all(v["trial_outcome_id"] is None for v in vals)


def test_vals_carry_source_url():
    _, vals = _payload("2")
    assert vals and {v["source_url"] for v in vals} == {
        "https://doi.org/10.1182/blood-2025-2"
    }


def test_payload_without_nct():
    arms, vals = _payload("3")
    assert arms and all(a["nct_id"] is None for a in arms)
    assert vals and all(v["nct_id"] is None for v in vals)


def test_primary_nct_first_cited():
    arms, vals = _payload("1")
    assert {a["nct_id"] for a in arms} == {"NCT00000001"}
    assert {v["nct_id"] for v in vals} == {"NCT00000001"}


def test_wide_columns_cancer_agnostic_only():
    assert not set(WIDE_COLUMNS.values()) & {"orr", "cr", "dcr", "cbr", "pcr", "cmr"}
    assert WIDE_COLUMNS["patients_enrolled"] == "num_patients"
    assert "patients_treated" not in WIDE_COLUMNS
    arm = _arm(_payload("1")[0], "arm_1")
    assert arm["num_patients"] == 120


def test_wide_copy_only_from_main_value():
    arms, _ = _payload("1")
    a1, a2 = _arm(arms, "arm_1"), _arm(arms, "arm_2")
    # arm_1's main median PFS is NR; its extra (36.0, with a context) never fills it
    assert a1["median_pfs"] is None and a1["is_nr"] == ["median_pfs"]
    assert a1["p_value_pfs"] == 0.001 and a1["is_lt"] == ["p_value_pfs"]
    assert a2["median_pfs"] == 24.5 and a2["is_nr"] is None and a2["is_lt"] is None


def test_wide_text_and_trial_scope():
    arms, _ = _payload("1")
    a1, a2 = _arm(arms, "arm_1"), _arm(arms, "arm_2")
    assert a1["ci_hr_pfs"] == "0.30-0.60"
    assert a1["dosage"] == "100 mg daily"
    assert a1["generic_name"] == "drug-a + drug-b"
    assert a1["crs_pct"] == 12
    # the trial-scope setting fills line_of_treatment on every arm
    assert a1["line_of_treatment"] == a2["line_of_treatment"] == "relapsed/refractory"
    assert a1["arm_name"] == "drug A plus drug B"


def test_pooled_values_never_fill_arms():
    [setting] = [r for r in _abstract("1") if r["field_key"] == "setting"]
    pooled_age = dict(
        setting, field_key="median_age", value_text="70", origin="abstract"
    )
    arms, vals = abstract_payload([*_abstract("1"), pooled_age])
    assert all(a["median_age"] is None for a in arms)
    assert any(
        v["field_key"] == "median_age" and v["trial_outcome_id"] is None for v in vals
    )


def test_all_arms_have_identical_key_sets():
    keys = [
        frozenset(a)
        for abstract in sorted({r["abstract"] for r in RECORDS})
        for a in _payload(abstract)[0]
    ]
    assert len(keys) == 3 and len(set(keys)) == 1
    assert {"is_nr", "is_lt", *WIDE_COLUMNS.values()} <= keys[0]


def test_val_keys_match_outcome_values_columns():
    for abstract in {r["abstract"] for r in RECORDS}:
        assert all(set(v) == VAL_KEYS for v in _payload(abstract)[1])


def test_wide_targets_exist_with_matching_type():
    types = {r["key"]: r["value_type"] for r in field_rows()}
    for key, col in WIDE_COLUMNS.items():
        assert col in COLUMNS, col
        numeric_col = COLUMNS[col] in ("numeric", "integer")
        assert numeric_col == (types[key] in NUMERIC), (key, col)


def test_arm_keys_are_trial_outcomes_columns():
    arms, _ = _payload("1")
    assert set(arms[0]) <= set(COLUMNS)
    assert not {"expert_review", "expert_reviewed_at"} & set(arms[0])


def test_every_field_key_is_seeded():
    rows = field_rows()
    keys = {r["key"] for r in rows}
    assert {r["field_key"] for r in RECORDS} <= keys
    assert "setting" in keys
    assert len(keys) == len(rows) == len({r["label"] for r in rows})
    assert {r["wide_column"] for r in rows} - {None} == set(WIDE_COLUMNS.values())
    assert set(rows[0]) == {
        "key", "label", "family", "scope", "value_type", "allowed_values",
        "definition", "wide_column", "sort_order",
    }  # fmt: skip


def test_no_quote_in_payload():
    for abstract in {r["abstract"] for r in RECORDS}:
        arms, vals = _payload(abstract)
        assert not any("quote" in row for row in arms + vals)


def test_cancer_type_full_name():
    arms, vals = _payload("1")
    assert {tuple(x["cancer_type"]) for x in arms + vals} == {
        ("Chronic Lymphocytic Leukemia",)
    }


def test_exact_duplicates_dropped():
    _, vals = _payload("1")
    gen = [v for v in vals if v["field_key"] == "generic_name_per_component"]
    assert len(gen) == 1 and gen[0]["origin"] == "registry"


def test_caveat_kept():
    _, vals = _payload("3")
    [cr] = [v for v in vals if v["field_key"] == "cr_rate"]
    assert cr["caveat"].startswith("possible source error")
    assert cr["value_num"] == 33.0


def test_drift_detects_mismatch():
    arms, vals = _payload("1")
    assert drift(arms, vals) == []
    bad = copy.deepcopy(arms)
    _arm(bad, "arm_2")["median_pfs"] = 99.0
    _arm(bad, "arm_1")["is_nr"] = None
    out = drift(bad, vals)
    assert len(out) == 2
    assert any("abstract_ASH_2025_1_arm_2" in m and "median_pfs" in m for m in out)


class FakeSupabase:
    """The client --write talks to: serves canned rows per table (filtered by in_,
    paged by range) and records every write instead of sending it."""

    def __init__(self, tables: dict[str, list[dict]]):
        self.tables, self.writes = tables, []

    def table(self, name):
        return _Query(self, name)

    def rpc(self, name, params):
        self.writes.append((name, params))
        return _Result(1 if name == "delete_ash_abstracts_except" else None)


class _Result:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return self


class _Query:
    def __init__(self, sb, name):
        self.sb, self.name, self.rows = sb, name, list(sb.tables.get(name, []))

    def select(self, *_):
        return self

    def eq(self, *_):
        return self

    def like(self, *_):
        return self

    def order(self, *_):
        return self

    def in_(self, col, values):
        self.rows = [r for r in self.rows if r[col] in values]
        return self

    def range(self, start, end):
        self.rows = self.rows[start : end + 1]
        return self

    def upsert(self, rows):
        self.sb.writes.append((self.name, rows))
        return self

    def execute(self):
        return _Result(self.rows)


def _arm_row(abstract, arm="arm_1", name="old name", review=None):
    return {"id": f"abstract_ASH_2025_{abstract}_{arm}", "abstract_id": f"ASH_2025_{abstract}",
            "arm_name": name, "expert_review": review}  # fmt: skip


def _fake(arms=(), vals=(), ncts=("NCT00000001", "NCT00000003")) -> FakeSupabase:
    return FakeSupabase(
        {
            "trial_outcomes": list(arms),
            "outcome_values": [{"source_id": s} for s in vals],
            "clinical_trials": [{"nct_id": n} for n in ncts],
        }
    )


def _write(monkeypatch, sb, *flags, run=FIX) -> FakeSupabase:
    monkeypatch.setattr(upload_ash_supabase, "_client", lambda: sb)
    argv = ["upload_ash_supabase.py", "--run", str(run), "--write", *flags]
    monkeypatch.setattr(sys, "argv", argv)
    upload_ash_supabase.main()
    return sb


def _refused(monkeypatch, sb, *flags) -> str:
    """Runs a --write that must refuse; returns its message. Nothing is written."""
    with pytest.raises(SystemExit) as e:
        _write(monkeypatch, sb, *flags)
    assert e.value.code not in (0, None)
    assert sb.writes == []
    return str(e.value.code)


def _rpcs(sb):
    return [w[0] for w in sb.writes if w[0] != "outcome_fields"]


LOAD = ["replace_ash_abstract"] * 3


def test_write_refuses_to_prune_a_reviewed_abstract(monkeypatch, capsys):
    arms = [_arm_row(1), _arm_row(9, review="good")]
    assert "reviewed" in _refused(monkeypatch, _fake(arms))
    assert "ASH_2025_9" in capsys.readouterr().out
    sb = _write(monkeypatch, _fake(arms), "--prune")
    assert _rpcs(sb) == [*LOAD, "delete_ash_abstracts_except"]


def test_write_refuses_to_prune_more_than_five(monkeypatch):
    vals = ["ASH_2025_1", *(f"ASH_2025_{n}" for n in range(10, 16))]
    assert "6 abstracts" in _refused(monkeypatch, _fake(vals=vals))
    sb = _write(monkeypatch, _fake(vals=vals), "--prune")
    assert _rpcs(sb) == [*LOAD, "delete_ash_abstracts_except"]
    sb = _write(monkeypatch, _fake(vals=vals[:-1]))  # five is allowed
    assert _rpcs(sb) == [*LOAD, "delete_ash_abstracts_except"]


def test_write_reports_reviewed_arm_renamed(monkeypatch, capsys):
    arms = [_arm_row(1, review="good"), _arm_row(1, "arm_9", "gone", "bad")]
    _write(monkeypatch, _fake(arms))
    out = capsys.readouterr().out
    assert "abstract_ASH_2025_1_arm_1 (good): 'old name' -> 'drug A plus drug B'" in out
    assert "abstract_ASH_2025_1_arm_9 (bad): 'gone' -> removed" in out


def test_write_refuses_unknown_nct(monkeypatch):
    assert "NCT00000003" in _refused(monkeypatch, _fake(ncts=["NCT00000001"]))


def test_empty_run_exits_with_a_message(monkeypatch, tmp_path):
    (tmp_path / "resolved.json").write_text("[]")
    monkeypatch.setattr(sys, "argv", ["x", "--run", str(tmp_path)])
    with pytest.raises(SystemExit) as e:
        upload_ash_supabase.main()
    assert "no abstracts" in str(e.value.code)


def test_dry_run_counts_all_arms_rows_like_the_view(monkeypatch, capsys):
    # abstract 1 has only trial-scope arm-less values, 2 is pooled-only, 3 neither
    monkeypatch.setattr(sys, "argv", ["x", "--run", str(FIX)])
    upload_ash_supabase.main()
    assert "3 abstracts, 3 arms, 21 values, 2 All arms rows" in capsys.readouterr().out
