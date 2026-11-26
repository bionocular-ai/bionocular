"""Tests for the ASH loader (resolved.json -> outcome_fields, trial_outcomes, outcome_values)."""

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

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
