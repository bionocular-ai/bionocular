"""Unit tests for the deterministic trial-parameter validator.

Pure functions over an in-memory record dict; no LLM, no network, no files.
"""
from __future__ import annotations

from src.infrastructure.trial_deterministic_validator import (
    DROP,
    FLAG,
    DeterministicViolation,
    check_trial,
    is_droppable,
)

_SOURCE_CANCER_TYPES = ["Cutaneous Melanoma", "Uveal Melanoma"]


def _valid_trial() -> dict:
    """A fully-valid, clean record."""
    return {
        "nct_number": "NCT00000001",
        "cancer_type": ["Cutaneous Melanoma"],
        "treatment_name": "Pembrolizumab",
        "modality": ["Monoclonal Antibody"],
        "biomarker": ["BRAF (V600)"],
        "stage": ["Stage IV"],
        "line_of_therapy": ["1L"],
        "previous_treatment_criteria": ["IO Naive"],
        "extraction_status": "done",
        "error_message": None,
    }


def _rules(violations: list[DeterministicViolation]) -> set[str]:
    return {v.rule for v in violations}


def _by_field(
    violations: list[DeterministicViolation], field: str
) -> list[DeterministicViolation]:
    return [v for v in violations if v.field == field]


# ---- Clean record ------------------------------------------------------


def test_fully_valid_record_has_no_violations() -> None:
    assert check_trial(_valid_trial(), _SOURCE_CANCER_TYPES) == []


def test_valid_record_is_not_droppable() -> None:
    assert is_droppable(check_trial(_valid_trial(), _SOURCE_CANCER_TYPES)) is False


# ---- nct_format (DROP) -------------------------------------------------


def test_bad_nct_format_is_drop() -> None:
    trial = _valid_trial()
    trial["nct_number"] = "NCT123"
    violations = check_trial(trial, _SOURCE_CANCER_TYPES)
    nct = _by_field(violations, "nct_number")
    assert len(nct) == 1
    assert nct[0].rule == "nct_format"
    assert nct[0].severity == DROP
    assert is_droppable(violations) is True


def test_none_nct_is_drop() -> None:
    trial = _valid_trial()
    trial["nct_number"] = None
    violations = check_trial(trial, _SOURCE_CANCER_TYPES)
    assert any(v.rule == "nct_format" and v.severity == DROP for v in violations)


def test_nct_with_too_many_digits_is_drop() -> None:
    trial = _valid_trial()
    trial["nct_number"] = "NCT000000012"
    violations = check_trial(trial, _SOURCE_CANCER_TYPES)
    assert any(v.rule == "nct_format" for v in violations)


# ---- required_treatment_name (DROP) ------------------------------------


def test_none_treatment_name_on_done_is_drop() -> None:
    trial = _valid_trial()
    trial["treatment_name"] = None
    violations = check_trial(trial, _SOURCE_CANCER_TYPES)
    tn = _by_field(violations, "treatment_name")
    assert len(tn) == 1
    assert tn[0].rule == "required_treatment_name"
    assert tn[0].severity == DROP
    assert is_droppable(violations) is True


def test_empty_treatment_name_on_done_is_drop() -> None:
    trial = _valid_trial()
    trial["treatment_name"] = "   "
    violations = check_trial(trial, _SOURCE_CANCER_TYPES)
    assert any(
        v.rule == "required_treatment_name" and v.severity == DROP for v in violations
    )


def test_empty_treatment_name_on_partial_is_not_drop() -> None:
    trial = _valid_trial()
    trial["treatment_name"] = None
    trial["extraction_status"] = "partial"
    trial["error_message"] = "could not determine treatment"
    violations = check_trial(trial, _SOURCE_CANCER_TYPES)
    assert not any(v.rule == "required_treatment_name" for v in violations)
    assert is_droppable(violations) is False


# ---- vocab_membership (FLAG) -------------------------------------------


def test_out_of_vocab_modality_is_flag_naming_value() -> None:
    trial = _valid_trial()
    trial["modality"] = ["Monoclonal Antibody", "Laser Beam"]
    violations = check_trial(trial, _SOURCE_CANCER_TYPES)
    mod = _by_field(violations, "modality")
    assert len(mod) == 1
    assert mod[0].rule == "vocab_membership"
    assert mod[0].severity == FLAG
    assert "Laser Beam" in mod[0].detail


def test_out_of_vocab_biomarker_is_flag() -> None:
    trial = _valid_trial()
    trial["biomarker"] = ["ALK"]
    violations = check_trial(trial, _SOURCE_CANCER_TYPES)
    bio = _by_field(violations, "biomarker")
    assert len(bio) == 1
    assert bio[0].rule == "vocab_membership"
    assert "ALK" in bio[0].detail


def test_out_of_vocab_stage_is_flag() -> None:
    trial = _valid_trial()
    trial["stage"] = ["Stage V"]
    violations = check_trial(trial, _SOURCE_CANCER_TYPES)
    stg = _by_field(violations, "stage")
    assert len(stg) == 1
    assert stg[0].rule == "vocab_membership"
    assert "Stage V" in stg[0].detail


def test_out_of_vocab_line_of_therapy_is_flag() -> None:
    trial = _valid_trial()
    trial["line_of_therapy"] = ["4L"]
    violations = check_trial(trial, _SOURCE_CANCER_TYPES)
    lot = _by_field(violations, "line_of_therapy")
    assert len(lot) == 1
    assert lot[0].rule == "vocab_membership"
    assert "4L" in lot[0].detail


def test_out_of_vocab_previous_treatment_is_flag() -> None:
    trial = _valid_trial()
    trial["previous_treatment_criteria"] = ["Prior Chemo"]
    violations = check_trial(trial, _SOURCE_CANCER_TYPES)
    prev = _by_field(violations, "previous_treatment_criteria")
    assert len(prev) == 1
    assert prev[0].rule == "vocab_membership"
    assert "Prior Chemo" in prev[0].detail


def test_vocab_flags_never_droppable() -> None:
    trial = _valid_trial()
    trial["modality"] = ["Nonsense"]
    violations = check_trial(trial, _SOURCE_CANCER_TYPES)
    assert is_droppable(violations) is False


# ---- cancer_type_subset (FLAG) -----------------------------------------


def test_cancer_type_not_subset_is_flag() -> None:
    trial = _valid_trial()
    trial["cancer_type"] = ["Cutaneous Melanoma", "Basal Cell Carcinoma"]
    violations = check_trial(trial, _SOURCE_CANCER_TYPES)
    ct = _by_field(violations, "cancer_type")
    assert len(ct) == 1
    assert ct[0].rule == "cancer_type_subset"
    assert ct[0].severity == FLAG
    assert "Basal Cell Carcinoma" in ct[0].detail


def test_cancer_type_match_is_case_sensitive() -> None:
    trial = _valid_trial()
    trial["cancer_type"] = ["cutaneous melanoma"]
    violations = check_trial(trial, _SOURCE_CANCER_TYPES)
    assert any(v.rule == "cancer_type_subset" for v in violations)


def test_cancer_type_non_list_skips_subset_and_flags_shape() -> None:
    trial = _valid_trial()
    trial["cancer_type"] = "Cutaneous Melanoma"
    violations = check_trial(trial, _SOURCE_CANCER_TYPES)
    # Subset rule cannot run on a non-list; list_shape catches it instead.
    assert not any(v.rule == "cancer_type_subset" for v in violations)
    assert any(v.rule == "list_shape" and v.field == "cancer_type" for v in violations)


def test_cancer_type_rule_skipped_when_source_empty() -> None:
    trial = _valid_trial()
    trial["cancer_type"] = ["Anything At All"]
    violations = check_trial(trial, [])
    assert not any(v.rule == "cancer_type_subset" for v in violations)


# ---- list_shape (FLAG) -------------------------------------------------


def test_duplicate_values_is_list_shape_flag() -> None:
    trial = _valid_trial()
    trial["modality"] = ["Monoclonal Antibody", "Monoclonal Antibody"]
    violations = check_trial(trial, _SOURCE_CANCER_TYPES)
    shape = [v for v in _by_field(violations, "modality") if v.rule == "list_shape"]
    assert len(shape) == 1
    assert shape[0].severity == FLAG
    assert "duplicate" in shape[0].detail.lower()


def test_none_element_is_list_shape_flag() -> None:
    trial = _valid_trial()
    trial["biomarker"] = [None]
    violations = check_trial(trial, _SOURCE_CANCER_TYPES)
    shape = [v for v in _by_field(violations, "biomarker") if v.rule == "list_shape"]
    assert len(shape) == 1
    assert shape[0].severity == FLAG
    # A None element must not also be reported as a vocab violation.
    assert not any(
        v.rule == "vocab_membership" for v in _by_field(violations, "biomarker")
    )


def test_non_list_value_is_list_shape_flag() -> None:
    trial = _valid_trial()
    trial["stage"] = "Stage IV"
    violations = check_trial(trial, _SOURCE_CANCER_TYPES)
    shape = [v for v in _by_field(violations, "stage") if v.rule == "list_shape"]
    assert len(shape) == 1
    assert shape[0].severity == FLAG
    # A non-list must not crash the vocab check nor be reported by it.
    assert not any(v.rule == "vocab_membership" for v in _by_field(violations, "stage"))


def test_none_value_is_list_shape_flag_not_crash() -> None:
    trial = _valid_trial()
    trial["line_of_therapy"] = None
    violations = check_trial(trial, _SOURCE_CANCER_TYPES)
    assert any(
        v.rule == "list_shape" and v.field == "line_of_therapy" for v in violations
    )


def test_list_shape_flags_never_droppable() -> None:
    trial = _valid_trial()
    trial["modality"] = ["Monoclonal Antibody", "Monoclonal Antibody"]
    violations = check_trial(trial, _SOURCE_CANCER_TYPES)
    assert is_droppable(violations) is False


# ---- status_consistency (FLAG) -----------------------------------------


def test_partial_without_error_message_is_flag() -> None:
    trial = _valid_trial()
    trial["extraction_status"] = "partial"
    trial["error_message"] = None
    violations = check_trial(trial, _SOURCE_CANCER_TYPES)
    status = _by_field(violations, "extraction_status")
    assert len(status) == 1
    assert status[0].rule == "status_consistency"
    assert status[0].severity == FLAG


def test_failed_with_empty_error_message_is_flag() -> None:
    trial = _valid_trial()
    trial["extraction_status"] = "failed"
    trial["treatment_name"] = None
    trial["error_message"] = "   "
    violations = check_trial(trial, _SOURCE_CANCER_TYPES)
    assert any(v.rule == "status_consistency" for v in violations)


def test_done_with_error_message_is_flag() -> None:
    trial = _valid_trial()
    trial["error_message"] = "something odd happened"
    violations = check_trial(trial, _SOURCE_CANCER_TYPES)
    status = _by_field(violations, "extraction_status")
    assert len(status) == 1
    assert status[0].rule == "status_consistency"
    assert status[0].severity == FLAG


def test_partial_with_error_message_is_clean() -> None:
    trial = _valid_trial()
    trial["extraction_status"] = "partial"
    trial["error_message"] = "only some fields extracted"
    violations = check_trial(trial, _SOURCE_CANCER_TYPES)
    assert not any(v.rule == "status_consistency" for v in violations)


def test_status_flag_is_not_droppable() -> None:
    trial = _valid_trial()
    trial["extraction_status"] = "partial"
    trial["error_message"] = None
    violations = check_trial(trial, _SOURCE_CANCER_TYPES)
    assert is_droppable(violations) is False


# ---- is_droppable ------------------------------------------------------


def test_is_droppable_true_only_when_drop_present() -> None:
    drop_only = [DeterministicViolation("nct_number", "nct_format", DROP, "bad")]
    flag_only = [DeterministicViolation("modality", "vocab_membership", FLAG, "bad")]
    mixed = drop_only + flag_only
    assert is_droppable(drop_only) is True
    assert is_droppable(flag_only) is False
    assert is_droppable(mixed) is True
    assert is_droppable([]) is False


def test_multiple_violations_accumulate() -> None:
    trial = _valid_trial()
    trial["nct_number"] = "bad"
    trial["modality"] = ["Nope"]
    trial["cancer_type"] = ["Basal Cell Carcinoma"]
    violations = check_trial(trial, _SOURCE_CANCER_TYPES)
    assert {"nct_format", "vocab_membership", "cancer_type_subset"} <= _rules(
        violations
    )
    assert is_droppable(violations) is True
