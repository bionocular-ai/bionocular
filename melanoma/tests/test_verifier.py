"""Tests for the bounded low-confidence verifier."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.domain.extraction_models import AttributeType, ValidationStatus
from src.domain.treatment_arm_models import TreatmentArm
from src.infrastructure.verifier import (
    MAX_VERIFIER_ATTEMPTS,
    VerifierSchema,
    verify_low_confidence,
)


def _make_arm() -> TreatmentArm:
    return TreatmentArm(
        arm_id="arm-1",
        arm_name="Pembrolizumab Arm",
        generic_name="pembrolizumab",
    )


def _make_gemini(return_values: list[VerifierSchema]) -> AsyncMock:
    """Build a mock gemini service whose ``cached_or_inline_generate``
    returns the given schema instances in order."""
    gemini = AsyncMock()
    gemini.cached_or_inline_generate = AsyncMock(side_effect=return_values)
    return gemini


@pytest.mark.asyncio
async def test_verifier_passes_on_attempt_1() -> None:
    gemini = _make_gemini([VerifierSchema(value="0.65", quote="HR was 0.65.")])
    arm = _make_arm()

    result = await verify_low_confidence(
        gemini=gemini,
        cache_id="cache-1",
        doc_text="doc",
        arm=arm,
        attribute=AttributeType.HR_PFS,
        current_value="zero point sixty-five",
        failure_reason="not a decimal hazard ratio",
    )

    assert result.validation_status == ValidationStatus.VERIFIED
    assert result.confidence == 0.6
    assert result.value == "0.65"
    assert result.source == "verifier"
    assert result.source_quote == "HR was 0.65."
    assert gemini.cached_or_inline_generate.await_count == 1


@pytest.mark.asyncio
async def test_verifier_passes_on_attempt_2() -> None:
    gemini = _make_gemini(
        [
            VerifierSchema(value="not a number", quote="garbage"),
            VerifierSchema(value="0.72", quote="HR 0.72."),
        ]
    )
    arm = _make_arm()

    result = await verify_low_confidence(
        gemini=gemini,
        cache_id=None,
        doc_text="doc",
        arm=arm,
        attribute=AttributeType.HR_OS,
        current_value="bad",
        failure_reason="not a decimal hazard ratio",
    )

    assert result.validation_status == ValidationStatus.VERIFIED
    assert result.confidence == 0.6
    assert result.value == "0.72"
    assert gemini.cached_or_inline_generate.await_count == 2


@pytest.mark.asyncio
async def test_verifier_returns_empty_when_doc_lacks_value() -> None:
    gemini = _make_gemini([VerifierSchema(value="", quote="")])
    arm = _make_arm()

    result = await verify_low_confidence(
        gemini=gemini,
        cache_id="cache-1",
        doc_text="doc",
        arm=arm,
        attribute=AttributeType.HR_PFS,
        current_value="bogus",
        failure_reason="not a decimal hazard ratio",
    )

    assert result.validation_status == ValidationStatus.EMPTY
    assert result.confidence == 0.0
    assert result.value == ""
    assert gemini.cached_or_inline_generate.await_count == 1


@pytest.mark.asyncio
async def test_verifier_exhausts_attempts_and_marks_failed() -> None:
    gemini = _make_gemini(
        [
            VerifierSchema(value="bad-1", quote="q1"),
            VerifierSchema(value="bad-2", quote="q2"),
        ]
    )
    arm = _make_arm()

    result = await verify_low_confidence(
        gemini=gemini,
        cache_id=None,
        doc_text="doc",
        arm=arm,
        attribute=AttributeType.HR_PFS,
        current_value="initial-bad",
        failure_reason="not a decimal hazard ratio",
    )

    assert result.validation_status == ValidationStatus.FAILED
    assert result.confidence == 0.0
    assert result.source == "verifier"
    assert gemini.cached_or_inline_generate.await_count == MAX_VERIFIER_ATTEMPTS


@pytest.mark.asyncio
async def test_verifier_passes_arm_context_in_prompt() -> None:
    gemini = _make_gemini([VerifierSchema(value="0.55", quote="HR 0.55.")])
    arm = _make_arm()

    await verify_low_confidence(
        gemini=gemini,
        cache_id="cache-1",
        doc_text="doc",
        arm=arm,
        attribute=AttributeType.HR_PFS,
        current_value="prev-bad",
        failure_reason="not a decimal hazard ratio",
    )

    call_args = gemini.cached_or_inline_generate.await_args
    # Positional: (cache_id, doc_text, prompt, schema)
    prompt = call_args.args[2]
    assert arm.arm_name in prompt
    assert arm.generic_name in prompt
    assert AttributeType.HR_PFS.value in prompt
    assert "prev-bad" in prompt
    assert "not a decimal hazard ratio" in prompt
