"""Tests for the deterministic (no-LLM) pre-pass over an extracted arm.

Every rule gets a clean case and a violating case. The clean cases matter as much
as the violations: a validator that flags correct data floods the HITL queue and
gets ignored.
"""

from __future__ import annotations

from typing import Any

from src.infrastructure.results_deterministic_validator import (
    DROP,
    FLAG,
    check_arm,
    is_droppable,
)


def _arm(**attributes: Any) -> dict:
    """Build an arm record in the shape the extraction pipelines emit."""
    return {
        "arm_id": "arm_1",
        "arm_name": "Pembrolizumab",
        "generic_name": "Pembrolizumab",
        "patient_count": 100,
        "attributes": {
            name: {"value": value, "confidence": 0.8}
            for name, value in attributes.items()
        },
    }


def _rules(violations: list) -> set[str]:
    return {v.rule for v in violations}


def _fields(violations: list) -> set[str]:
    return {v.field for v in violations}


# ---------------------------------------------------------------------------
# Clean records
# ---------------------------------------------------------------------------


def test_a_clean_arm_has_no_violations() -> None:
    arm = _arm(
        nct_number="NCT03005782",
        objective_response_rate="61.2",
        complete_response="12.2",
        disease_control_rate="80.0",
        median_pfs="15.3",
        median_os="NR",
        hr_pfs="0.81",
        ci_hr_pfs="0.67-0.97",
        p_value_pfs="0.001",
        pfs_rate_12m="56",
        pfs_rate_24m="42",
        ae="95.0",
        grade_3_plus_ae="43.9",
    )

    assert check_arm(arm) == []


def test_empty_and_not_found_sentinels_are_not_violations() -> None:
    arm = _arm(
        median_pfs="Not found",
        hr_os="",
        ci_hr_os="N/A",
        objective_response_rate=None,
    )

    assert check_arm(arm) == []


def test_nr_is_a_value_for_medians_but_not_for_a_hazard_ratio() -> None:
    assert check_arm(_arm(median_os="NR")) == []

    assert "value_format" in _rules(check_arm(_arm(hr_os="NR")))


# ---------------------------------------------------------------------------
# Atomic format rules (delegated to value_validator)
# ---------------------------------------------------------------------------


def test_a_malformed_hazard_ratio_is_flagged() -> None:
    violations = check_arm(_arm(hr_pfs="zero point eight"))

    assert _rules(violations) == {"value_format"}
    assert _fields(violations) == {"hr_pfs"}
    assert violations[0].severity == FLAG


def test_a_percentage_above_one_hundred_is_flagged() -> None:
    violations = check_arm(_arm(objective_response_rate="150"))

    assert _rules(violations) == {"value_format"}


def test_a_malformed_nct_is_flagged_but_never_drops_the_arm() -> None:
    """The doc_id keys this pipeline, not the NCT - a bad NCT must not discard
    otherwise-good efficacy data."""
    violations = check_arm(_arm(nct_number="NCT123"))

    assert _rules(violations) == {"value_format"}
    assert not is_droppable(violations)


# ---------------------------------------------------------------------------
# Identity rules (the only droppable class)
# ---------------------------------------------------------------------------


def test_an_arm_with_no_name_at_all_is_droppable() -> None:
    arm = _arm()
    arm["arm_name"] = ""
    arm["generic_name"] = None

    violations = check_arm(arm)

    assert _rules(violations) == {"arm_identity"}
    assert violations[0].severity == DROP
    assert is_droppable(violations)


def test_a_generic_name_alone_identifies_the_arm() -> None:
    arm = _arm()
    arm["arm_name"] = ""

    assert check_arm(arm) == []


def test_a_non_positive_patient_count_is_droppable() -> None:
    arm = _arm()
    arm["patient_count"] = 0

    violations = check_arm(arm)

    assert _rules(violations) == {"patient_count"}
    assert is_droppable(violations)


def test_a_missing_patient_count_is_not_a_violation() -> None:
    arm = _arm()
    arm["patient_count"] = None

    assert check_arm(arm) == []


# ---------------------------------------------------------------------------
# Cross-field consistency rules
# ---------------------------------------------------------------------------


def test_complete_response_above_objective_response_rate_is_flagged() -> None:
    violations = check_arm(_arm(complete_response="40", objective_response_rate="30"))

    assert _rules(violations) == {"response_ordering"}
    assert not is_droppable(violations)


def test_objective_response_rate_above_disease_control_rate_is_flagged() -> None:
    violations = check_arm(
        _arm(objective_response_rate="70", disease_control_rate="60")
    )

    assert _rules(violations) == {"response_ordering"}


def test_grade_3_plus_above_its_all_grade_total_is_flagged() -> None:
    violations = check_arm(_arm(ae="40", grade_3_plus_ae="60"))

    assert _rules(violations) == {"ae_subset"}
    assert _fields(violations) == {"grade_3_plus_ae"}


def test_a_single_grade_above_its_grade_3_plus_total_is_flagged() -> None:
    violations = check_arm(_arm(grade_3_plus_trae="20", grade_4_trae="35"))

    assert _rules(violations) == {"ae_subset"}


def test_a_confidence_interval_that_excludes_its_hazard_ratio_is_flagged() -> None:
    violations = check_arm(_arm(hr_os="0.50", ci_hr_os="0.67-0.97"))

    assert _rules(violations) == {"ci_brackets_hr"}
    assert _fields(violations) == {"ci_hr_os"}


def test_a_confidence_interval_containing_its_hazard_ratio_is_clean() -> None:
    assert check_arm(_arm(hr_os="0.82", ci_hr_os="0.67-1.02")) == []


def test_a_rising_survival_rate_curve_is_flagged() -> None:
    """A survival rate cannot increase with time - later timepoints are subsets."""
    violations = check_arm(_arm(os_rate_12m="50", os_rate_24m="65"))

    assert _rules(violations) == {"rate_monotonicity"}
    assert _fields(violations) == {"os_rate_24m"}


def test_a_falling_survival_rate_curve_is_clean() -> None:
    arm = _arm(
        os_rate_6m="90",
        os_rate_12m="80",
        os_rate_24m="61.8",
        os_rate_36m="54.1",
        os_rate_48m="51.5",
    )

    assert check_arm(arm) == []


def test_a_rate_curve_with_gaps_compares_only_present_timepoints() -> None:
    assert check_arm(_arm(pfs_rate_6m="80", pfs_rate_48m="20")) == []
    assert "rate_monotonicity" in _rules(
        check_arm(_arm(pfs_rate_6m="20", pfs_rate_48m="80"))
    )


def test_median_pfs_longer_than_median_os_is_flagged() -> None:
    violations = check_arm(_arm(median_pfs="30", median_os="20"))

    assert _rules(violations) == {"pfs_os_ordering"}


def test_median_pfs_is_not_compared_against_an_unreached_median_os() -> None:
    assert check_arm(_arm(median_pfs="30", median_os="NR")) == []


# ---------------------------------------------------------------------------
# is_droppable
# ---------------------------------------------------------------------------


def test_is_droppable_is_false_for_an_empty_violation_list() -> None:
    assert not is_droppable([])


def test_is_droppable_is_true_only_when_a_drop_severity_is_present() -> None:
    arm = _arm(hr_pfs="bad")
    arm["patient_count"] = -5

    violations = check_arm(arm)

    assert {v.severity for v in violations} == {FLAG, DROP}
    assert is_droppable(violations)
