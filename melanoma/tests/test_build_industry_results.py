"""Tests for the industry CSV -> results.json reshape (validation input rebuild)."""

import importlib.util
from pathlib import Path

_SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "scripts"
    / "build_industry_results_from_csv.py"
)
_spec = importlib.util.spec_from_file_location("build_industry_results", _SCRIPT)
assert _spec and _spec.loader
build_industry_results = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_industry_results)

reshape_row = build_industry_results.reshape_row
load_rows = build_industry_results.load_rows


def _csv_row(**overrides: str) -> dict:
    base = {
        "nct_number": "NCT00002767",
        "cancer_type": "Cutaneous melanoma",
        "treatment_name": "Melacine + Interferon alfa-2b",
        "modality": "Vaccine; Immunostimulant/Cytokine",
        "biomarker": "",
        "stage": "Stage IV",
        "line_of_therapy": "1L",
        "previous_treatment_criteria": "IO Naive",
        "extraction_status": "done",
        "error_message": "",
    }
    base.update(overrides)
    return base


def test_multivalue_field_splits_on_semicolon() -> None:
    record = reshape_row(_csv_row())
    assert record["modality"] == ["Vaccine", "Immunostimulant/Cytokine"]


def test_empty_cell_becomes_empty_list() -> None:
    record = reshape_row(_csv_row(biomarker=""))
    assert record["biomarker"] == []


def test_single_value_becomes_one_element_list() -> None:
    record = reshape_row(_csv_row())
    assert record["cancer_type"] == ["Cutaneous melanoma"]
    assert record["stage"] == ["Stage IV"]


def test_scalar_fields_stay_strings() -> None:
    record = reshape_row(_csv_row())
    assert record["nct_number"] == "NCT00002767"
    assert record["treatment_name"] == "Melacine + Interferon alfa-2b"
    assert record["extraction_status"] == "done"
    assert record["error_message"] == ""


def test_treatment_name_with_plus_is_not_split() -> None:
    # '+' is not the delimiter; only '; ' separates multi-values.
    record = reshape_row(_csv_row())
    assert "+" in record["treatment_name"]


def test_load_rows_concatenates_and_sorts(tmp_path: Path) -> None:
    header = (
        "nct_number,cancer_type,treatment_name,modality,biomarker,stage,"
        "line_of_therapy,previous_treatment_criteria,extraction_status,error_message\n"
    )
    (tmp_path / "b_trials.csv").write_text(
        header + "NCT00000002,X,Drug B,Other,,Stage I,1L,None,done,\n"
    )
    (tmp_path / "a_trials.csv").write_text(
        header + "NCT00000001,X,Drug A,Other,,Stage I,1L,None,done,\n"
    )
    rows = load_rows(tmp_path)
    assert [r["nct_number"] for r in rows] == ["NCT00000001", "NCT00000002"]
