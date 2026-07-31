"""Tests for the validation service's pure decision logic.

No LLM and no I/O: these cover the guards that decide whether a judge verdict is
trustworthy, and the routing table that turns verdicts into per-arm outcomes.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from src.app.results_validation_service import (
    ResultsValidationConfig,
    ResultsValidationService,
    RouteOutcome,
    effective_status,
    route_arm,
    value_supported_by_quote,
)
from src.domain.results_validation_models import (
    ArmFieldEvaluation,
    AttributeGroup,
    DerivationKind,
    GroupVerdict,
    MissedValue,
    ValidationDecision,
    ValidationFieldStatus,
)
from src.infrastructure.cost_calculator import CostCalculator
from src.infrastructure.document_source_loader import (
    DocumentSourceLoader,
    SourceDocument,
)
from src.infrastructure.results_deterministic_validator import (
    DROP,
    FLAG,
    DeterministicViolation,
)

_SOURCE = (
    "Median PFS was 14.7 months (95% CI 10.2-19.8) in the experimental arm.\n"
    "Grade 3 events occurred in 12.0%, grade 4 in 3.0% and grade 5 in 1.0%.\n"
    "12-month PFS rate was 56%."
)


def _evaluation(**overrides: object) -> ArmFieldEvaluation:
    payload: dict = {
        "arm_id": "arm_1",
        "field_name": "median_pfs",
        "extracted_value": "14.7",
        "status": ValidationFieldStatus.PASS,
        "source_evidence_quote": "Median PFS was 14.7 months",
        "derivation": DerivationKind.UNIT_STRIPPED,
        "arm_attribution_ok": True,
    }
    payload.update(overrides)
    return ArmFieldEvaluation(**payload)  # type: ignore[arg-type]


def _route(
    evaluations: list[ArmFieldEvaluation] | None = None,
    *,
    missed_values: list[MissedValue] | None = None,
    violations: list[DeterministicViolation] | None = None,
    apply_fixes: bool = False,
    validation_score: float = 0.9,
) -> RouteOutcome:
    return route_arm(
        evaluations=evaluations if evaluations is not None else [_evaluation()],
        missed_values=missed_values or [],
        violations=violations or [],
        source_text=_SOURCE,
        validation_score=validation_score,
        apply_fixes=apply_fixes,
        score_threshold=0.75,
    )


# ---------------------------------------------------------------------------
# value_supported_by_quote
# ---------------------------------------------------------------------------


def test_a_value_present_in_its_quote_is_supported() -> None:
    assert value_supported_by_quote("14.7", "Median PFS was 14.7 months")


def test_a_value_absent_from_its_quote_is_not_supported() -> None:
    assert not value_supported_by_quote("22.9", "Median PFS was 14.7 months")


def test_a_percentage_matches_its_quote_without_the_symbol() -> None:
    assert value_supported_by_quote("56", "12-month PFS rate was 56%")


def test_a_confidence_interval_matches_across_dash_styles() -> None:
    assert value_supported_by_quote("10.2-19.8", "95% CI 10.2–19.8")


def test_a_value_does_not_match_a_longer_number_containing_it() -> None:
    """'56' must not be satisfied by '561' or '5.6'."""
    assert not value_supported_by_quote("56", "the total was 561 patients")
    assert not value_supported_by_quote("56", "the rate was 5.6%")


def test_an_empty_quote_supports_nothing() -> None:
    assert not value_supported_by_quote("14.7", "")


def test_a_value_matches_a_lancet_style_middle_dot_decimal() -> None:
    """The Lancet and JCO print decimals as '11·0'. Without this, every correct
    numeric value in those journals is downgraded to UNCERTAIN."""
    assert value_supported_by_quote(
        "11.0", "median progression-free survival was 11·0 months"
    )
    assert value_supported_by_quote("0.67", "HR 0·67, 95% CI 0·53-0·84")
    assert value_supported_by_quote("0.53-0.84", "HR 0·67, 95% CI 0·53–0·84")


def test_a_middle_dot_outside_a_number_is_not_treated_as_a_decimal_point() -> None:
    """Markdown bullets must not be rewritten into digits."""
    assert not value_supported_by_quote("1.2", "· 1 patient · 2 patients")


def test_a_lancet_style_value_still_must_match_the_right_number() -> None:
    assert not value_supported_by_quote("11.0", "median survival was 25·1 months")


def test_a_confidence_interval_matches_a_quote_written_with_to() -> None:
    """Sources write CIs as '0.43 to 0.76'; the extractor normalises to a dash."""
    assert value_supported_by_quote("0.43-0.76", "95% CI, 0.43 to 0.76")


def test_a_non_numeric_value_is_supported_by_any_grounded_quote() -> None:
    """'NR' is written 'not reached' in prose - a numeric containment check
    cannot express the relationship, so it must not veto the value."""
    assert value_supported_by_quote("NR", "median duration of response was not reached")
    assert value_supported_by_quote("Significant", "the difference was significant")


def test_a_numeric_value_is_still_checked_when_mixed_with_text() -> None:
    assert not value_supported_by_quote("14.7", "median was not reached")


# ---------------------------------------------------------------------------
# effective_status - the anti-hallucination guards
# ---------------------------------------------------------------------------


def test_a_pass_with_a_grounded_quote_stays_a_pass() -> None:
    assert effective_status(_evaluation(), _SOURCE) is ValidationFieldStatus.PASS


def test_a_pass_whose_quote_is_not_in_the_source_becomes_uncertain() -> None:
    evaluation = _evaluation(source_evidence_quote="Median PFS was 99.9 months")

    assert effective_status(evaluation, _SOURCE) is ValidationFieldStatus.UNCERTAIN


def test_a_pass_without_any_quote_becomes_uncertain() -> None:
    assert (
        effective_status(_evaluation(source_evidence_quote=None), _SOURCE)
        is ValidationFieldStatus.UNCERTAIN
    )


def test_a_verbatim_pass_whose_value_is_absent_from_the_quote_becomes_uncertain() -> (
    None
):
    evaluation = _evaluation(
        extracted_value="22.9",
        derivation=DerivationKind.VERBATIM,
        source_evidence_quote="Median PFS was 14.7 months",
    )

    assert effective_status(evaluation, _SOURCE) is ValidationFieldStatus.UNCERTAIN


def test_a_summed_pass_is_not_required_to_show_its_value_in_the_quote() -> None:
    """Grade 3+ is 12.0 + 3.0 + 1.0; '16' appears nowhere in the source."""
    evaluation = _evaluation(
        field_name="grade_3_plus_ae",
        extracted_value="16.0",
        derivation=DerivationKind.SUMMED,
        derivation_justification="12.0 + 3.0 + 1.0",
        source_evidence_quote="grade 4 in 3.0% and grade 5 in 1.0%",
    )

    assert effective_status(evaluation, _SOURCE) is ValidationFieldStatus.PASS


def test_a_computed_pass_still_needs_a_grounded_quote() -> None:
    evaluation = _evaluation(
        derivation=DerivationKind.COMPUTED,
        source_evidence_quote="a phrase that is not in the document",
    )

    assert effective_status(evaluation, _SOURCE) is ValidationFieldStatus.UNCERTAIN


def test_a_pass_with_failed_arm_attribution_becomes_a_fail() -> None:
    evaluation = _evaluation(arm_attribution_ok=False)

    assert effective_status(evaluation, _SOURCE) is ValidationFieldStatus.FAIL


def test_a_declared_fail_stays_a_fail() -> None:
    evaluation = _evaluation(status=ValidationFieldStatus.FAIL)

    assert effective_status(evaluation, _SOURCE) is ValidationFieldStatus.FAIL


# ---------------------------------------------------------------------------
# route_arm - advisory mode (the shipping default)
# ---------------------------------------------------------------------------


def test_an_arm_whose_values_all_pass_is_kept() -> None:
    assert _route().decision is ValidationDecision.KEPT


def test_an_arm_with_no_extracted_values_is_kept() -> None:
    assert _route([]).decision is ValidationDecision.KEPT


def test_a_droppable_violation_drops_the_arm() -> None:
    violations = [
        DeterministicViolation("arm_name", "arm_identity", DROP, "unnamed arm")
    ]

    assert _route(violations=violations).decision is ValidationDecision.DROPPED


def test_a_droppable_violation_outranks_a_clean_judge_verdict() -> None:
    violations = [
        DeterministicViolation("patient_count", "patient_count", DROP, "count is 0")
    ]

    assert _route(violations=violations).decision is ValidationDecision.DROPPED


def test_an_advisory_violation_routes_to_review() -> None:
    violations = [
        DeterministicViolation("hr_pfs", "value_format", FLAG, "not a decimal")
    ]

    assert _route(violations=violations).decision is ValidationDecision.HITL


def test_a_failed_value_routes_to_review_in_advisory_mode() -> None:
    outcome = _route([_evaluation(status=ValidationFieldStatus.FAIL)])

    assert outcome.decision is ValidationDecision.HITL
    assert outcome.applied_corrections == []


def test_an_uncertain_value_routes_to_review() -> None:
    outcome = _route([_evaluation(status=ValidationFieldStatus.UNCERTAIN)])

    assert outcome.decision is ValidationDecision.HITL


def test_an_ungrounded_pass_routes_to_review() -> None:
    outcome = _route([_evaluation(source_evidence_quote="not in the document")])

    assert outcome.decision is ValidationDecision.HITL


def test_a_missed_value_routes_an_otherwise_clean_arm_to_review() -> None:
    missed = [
        MissedValue(
            arm_id="arm_1",
            field_name="pfs_rate_12m",
            suggested_value="56",
            source_evidence_quote="12-month PFS rate was 56%",
        )
    ]

    assert _route(missed_values=missed).decision is ValidationDecision.HITL


def test_advisory_mode_never_fixes_even_with_a_perfect_correction() -> None:
    evaluation = _evaluation(
        status=ValidationFieldStatus.FAIL,
        corrected_value="14.7",
        source_evidence_quote="Median PFS was 14.7 months",
    )

    outcome = _route([evaluation], validation_score=1.0)

    assert outcome.decision is ValidationDecision.HITL
    assert outcome.applied_corrections == []


# ---------------------------------------------------------------------------
# route_arm - gated auto-fix (off by default, enabled after calibration)
# ---------------------------------------------------------------------------


def test_a_grounded_correction_above_threshold_is_applied() -> None:
    evaluation = _evaluation(
        status=ValidationFieldStatus.FAIL,
        extracted_value="22.9",
        corrected_value="14.7",
        source_evidence_quote="Median PFS was 14.7 months",
    )

    outcome = _route([evaluation], apply_fixes=True, validation_score=0.9)

    assert outcome.decision is ValidationDecision.FIXED
    assert outcome.applied_corrections == [
        {
            "field": "median_pfs",
            "corrected": "14.7",
            "evidence_quote": "Median PFS was 14.7 months",
            "score": 0.9,
        }
    ]


def test_a_correction_below_the_score_threshold_is_not_applied() -> None:
    evaluation = _evaluation(
        status=ValidationFieldStatus.FAIL,
        corrected_value="14.7",
        source_evidence_quote="Median PFS was 14.7 months",
    )

    outcome = _route([evaluation], apply_fixes=True, validation_score=0.5)

    assert outcome.decision is ValidationDecision.HITL


def test_a_correction_whose_quote_is_not_in_the_source_is_not_applied() -> None:
    evaluation = _evaluation(
        status=ValidationFieldStatus.FAIL,
        corrected_value="14.7",
        source_evidence_quote="invented supporting text",
    )

    outcome = _route([evaluation], apply_fixes=True)

    assert outcome.decision is ValidationDecision.HITL


def test_a_failure_with_no_correction_goes_to_review_rather_than_dropping_the_arm() -> (
    None
):
    """One bad value among 165 must not discard an arm's good data."""
    evaluation = _evaluation(status=ValidationFieldStatus.FAIL, corrected_value=None)

    outcome = _route([evaluation], apply_fixes=True)

    assert outcome.decision is ValidationDecision.HITL


def test_uncertainty_always_needs_a_human_even_with_fixes_enabled() -> None:
    outcome = _route(
        [_evaluation(status=ValidationFieldStatus.UNCERTAIN)], apply_fixes=True
    )

    assert outcome.decision is ValidationDecision.HITL


def test_a_missed_value_is_never_auto_added() -> None:
    missed = [
        MissedValue(
            arm_id="arm_1",
            field_name="pfs_rate_12m",
            suggested_value="56",
            source_evidence_quote="12-month PFS rate was 56%",
        )
    ]

    outcome = _route(missed_values=missed, apply_fixes=True)

    assert outcome.decision is ValidationDecision.HITL
    assert outcome.applied_corrections == []


@pytest.mark.parametrize("apply_fixes", [False, True])
def test_a_droppable_violation_drops_the_arm_in_either_mode(
    apply_fixes: bool,
) -> None:
    violations = [
        DeterministicViolation("arm_name", "arm_identity", DROP, "unnamed arm")
    ]

    outcome = _route(violations=violations, apply_fixes=apply_fixes)

    assert outcome.decision is ValidationDecision.DROPPED


# ---------------------------------------------------------------------------
# Run loop - checkpoint and derived outputs
# ---------------------------------------------------------------------------


class _StubLoader(DocumentSourceLoader):
    """Serves a fixed source text for every document."""

    def __init__(self, text: str) -> None:
        self._text = text

    def load(self, doc_id: str) -> SourceDocument:
        return SourceDocument(
            doc_id=doc_id, text=self._text, sha256="deadbeef", path=Path(f"{doc_id}.md")
        )

    def available_ids(self) -> set[str]:
        return {"pub_ok", "pub_boom"}


class _StubJudge:
    """Returns a clean verdict, or raises for a document under test."""

    def __init__(self, failing_source: str | None = None) -> None:
        self._failing_source = failing_source
        self.calls = 0

    async def generate_structured(self, prompt: str, **kwargs: object) -> GroupVerdict:
        self.calls += 1
        if self._failing_source and self._failing_source in prompt:
            raise TimeoutError("Read timed out.")
        return GroupVerdict(is_valid=True, validation_score=1.0)


def _write_results(tmp_path: Path, doc_ids: list[str]) -> Path:
    path = tmp_path / "extraction_results_Publications_test.json"
    path.write_text(
        json.dumps(
            {
                "source": "publications",
                "publications": [
                    {
                        "pub_id": doc_id,
                        "total_arms": 1,
                        "arm_results": {
                            "arm_1": {
                                "arm_id": "arm_1",
                                "arm_name": "Pembrolizumab",
                                "patient_count": 100,
                                "attributes": {
                                    "median_pfs": {"value": "14.7", "confidence": 0.8}
                                },
                            }
                        },
                    }
                    for doc_id in doc_ids
                ],
            }
        )
    )
    return path


def _run(
    tmp_path: Path, doc_ids: list[str], judge: _StubJudge
) -> ResultsValidationService:
    config = ResultsValidationConfig(
        results_paths=[_write_results(tmp_path, doc_ids)],
        doc_type="publication",
        output_dir=tmp_path / "validation",
        model="stub",
        concurrency=2,
    )
    service = ResultsValidationService.from_config(
        config,
        judge,  # type: ignore[arg-type]
        _StubLoader(_SOURCE),
        CostCalculator(),
    )
    asyncio.run(service.run())
    return service


def test_a_clean_run_keeps_its_arms_and_writes_the_cleaned_cohort(
    tmp_path: Path,
) -> None:
    _run(tmp_path, ["pub_ok"], _StubJudge())

    cleaned = json.loads((tmp_path / "validation" / "results.cleaned.json").read_text())

    assert cleaned["total_arms"] == 1
    assert cleaned["publications"][0]["pub_id"] == "pub_ok"
    assert "arm_1" in cleaned["publications"][0]["arm_results"]


def test_an_errored_document_is_not_checkpointed_so_resume_retries_it(
    tmp_path: Path,
) -> None:
    """A transient timeout must not silently exclude a document forever."""
    judge = _StubJudge(failing_source=_SOURCE)

    _run(tmp_path, ["pub_boom"], judge)
    checkpoint_path = tmp_path / "validation" / "validation_checkpoint.json"
    recorded = (
        json.loads(checkpoint_path.read_text()) if checkpoint_path.exists() else {}
    )
    calls_after_first_run = judge.calls

    _run(tmp_path, ["pub_boom"], judge)

    assert recorded == {}
    assert judge.calls > calls_after_first_run, "resume did not retry the failure"


def test_a_successful_document_is_checkpointed_and_skipped_on_resume(
    tmp_path: Path,
) -> None:
    judge = _StubJudge()

    _run(tmp_path, ["pub_ok"], judge)
    first_pass_calls = judge.calls
    _run(tmp_path, ["pub_ok"], judge)

    assert first_pass_calls == len(AttributeGroup)
    assert judge.calls == first_pass_calls


def test_the_recall_report_groups_missed_values_by_field(tmp_path: Path) -> None:
    _run(tmp_path, ["pub_ok"], _StubJudge())

    missed = json.loads((tmp_path / "validation" / "missed_values.json").read_text())

    assert missed == {"total": 0, "by_field": {}}
