"""Unit tests for the pure validation routing logic (no LLM).

Covers the quote guard, correction parsing, and the decision matrix in both
advisory (detect-only) and mature (apply_fixes) modes.
"""

from __future__ import annotations

from src.app.trials_validation_service import (
    parse_corrected_value,
    quote_grounded,
    route_trial,
)
from src.domain.trial_validation_models import (
    FieldEvaluation,
    TrialValidationVerdict,
    ValidationDecision,
    ValidationFieldStatus,
)

_SOURCE = (
    "officialTitle:\nStudy of Nivolumab in unresectable metastatic melanoma\n\n"
    "eligibilityCriteria:\nStage IV disease; BRAF V600E-positive required."
)


def _ev(name: str, status: str, **kw: object) -> FieldEvaluation:
    return FieldEvaluation(field_name=name, status=status, **kw)  # type: ignore[arg-type]


def _verdict(
    evals: list[FieldEvaluation], score: float = 0.9
) -> TrialValidationVerdict:
    is_valid = all(e.status != ValidationFieldStatus.FAIL for e in evals)
    return TrialValidationVerdict(
        is_valid=is_valid, validation_score=score, field_evaluations=evals
    )


# --- quote_grounded ---------------------------------------------------------


def test_quote_grounded_substring() -> None:
    assert quote_grounded("unresectable metastatic melanoma", _SOURCE)


def test_quote_grounded_whitespace_normalised() -> None:
    assert quote_grounded("Study of  Nivolumab", _SOURCE)


def test_quote_grounded_missing_or_absent() -> None:
    assert not quote_grounded(None, _SOURCE)
    assert not quote_grounded("", _SOURCE)
    assert not quote_grounded("pembrolizumab combination", _SOURCE)


# --- parse_corrected_value --------------------------------------------------


def test_parse_corrected_value_enum_filters_vocab() -> None:
    assert parse_corrected_value("stage", "Stage III; Bogus") == ["Stage III"]


def test_parse_corrected_value_treatment_name_is_string() -> None:
    assert parse_corrected_value("treatment_name", "  Nivolumab ") == "Nivolumab"


# --- route_trial: detect-only (advisory) ------------------------------------


def _pass_ev() -> FieldEvaluation:
    return _ev(
        "stage",
        "PASS",
        extracted_value="Stage IV",
        source_evidence_quote="unresectable metastatic melanoma",
    )


def test_detect_only_all_pass_kept() -> None:
    outcome = route_trial(
        _verdict([_pass_ev()]), _SOURCE, apply_fixes=False, score_threshold=0.75
    )
    assert outcome.decision == ValidationDecision.KEPT


def test_detect_only_fail_goes_hitl_not_dropped() -> None:
    fail = _ev("modality", "FAIL", extracted_value="Vaccine", issue_description="wrong")
    outcome = route_trial(
        _verdict([fail]), _SOURCE, apply_fixes=False, score_threshold=0.75
    )
    assert outcome.decision == ValidationDecision.HITL


def test_detect_only_empty_field_pass_needs_no_quote() -> None:
    # A legitimately-empty field PASSes without a quote and must not be downgraded.
    empty = _ev("biomarker", "PASS", extracted_value="")
    empty_list = _ev("line_of_therapy", "PASS", extracted_value="[]")
    outcome = route_trial(
        _verdict([_pass_ev(), empty, empty_list]),
        _SOURCE,
        apply_fixes=False,
        score_threshold=0.75,
    )
    assert outcome.decision == ValidationDecision.KEPT


def test_detect_only_ungrounded_pass_treated_uncertain() -> None:
    bad = _ev(
        "stage",
        "PASS",
        extracted_value="Stage IV",
        source_evidence_quote="not in source",
    )
    outcome = route_trial(
        _verdict([bad]), _SOURCE, apply_fixes=False, score_threshold=0.75
    )
    assert outcome.decision == ValidationDecision.HITL


# --- route_trial: mature (apply_fixes) --------------------------------------


def test_apply_fixes_gated_correction_applied() -> None:
    fail = _ev(
        "stage",
        "FAIL",
        extracted_value="Stage III",
        corrected_value="Stage IV",
        source_evidence_quote="unresectable metastatic melanoma",
    )
    outcome = route_trial(
        _verdict([fail], score=0.9), _SOURCE, apply_fixes=True, score_threshold=0.75
    )
    assert outcome.decision == ValidationDecision.FIXED
    assert outcome.applied_corrections[0]["field"] == "stage"
    assert outcome.applied_corrections[0]["corrected"] == ["Stage IV"]


def test_apply_fixes_out_of_vocab_correction_dropped() -> None:
    fail = _ev(
        "stage",
        "FAIL",
        extracted_value="Stage III",
        corrected_value="Stage 99",
        source_evidence_quote="unresectable metastatic melanoma",
    )
    outcome = route_trial(
        _verdict([fail], score=0.9), _SOURCE, apply_fixes=True, score_threshold=0.75
    )
    assert outcome.decision == ValidationDecision.DROPPED


def test_apply_fixes_ungrounded_quote_dropped() -> None:
    fail = _ev(
        "stage",
        "FAIL",
        extracted_value="Stage III",
        corrected_value="Stage IV",
        source_evidence_quote="fabricated phrase not present",
    )
    outcome = route_trial(
        _verdict([fail], score=0.9), _SOURCE, apply_fixes=True, score_threshold=0.75
    )
    assert outcome.decision == ValidationDecision.DROPPED


def test_apply_fixes_below_threshold_dropped() -> None:
    fail = _ev(
        "stage",
        "FAIL",
        extracted_value="Stage III",
        corrected_value="Stage IV",
        source_evidence_quote="unresectable metastatic melanoma",
    )
    outcome = route_trial(
        _verdict([fail], score=0.5), _SOURCE, apply_fixes=True, score_threshold=0.75
    )
    assert outcome.decision == ValidationDecision.DROPPED


def test_apply_fixes_uncertain_goes_hitl() -> None:
    unc = _ev("biomarker", "UNCERTAIN", extracted_value="PD-L1")
    outcome = route_trial(
        _verdict([unc]), _SOURCE, apply_fixes=True, score_threshold=0.75
    )
    assert outcome.decision == ValidationDecision.HITL
