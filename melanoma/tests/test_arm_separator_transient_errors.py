"""A throttled separation call must not look like an abstract with no arms.

Returning an empty arm list for a 429 made 60 of 116 ASCO 2026 abstracts
indistinguishable from genuinely arm-less ones, so they were never retried.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.treatment_arm_separator import TreatmentArmSeparator


@pytest.fixture
def separator() -> TreatmentArmSeparator:
    return TreatmentArmSeparator(llm_service=MagicMock())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        Exception("429 RESOURCE_EXHAUSTED. {'error': {'code': 429}}"),
        Exception("504 DEADLINE_EXCEEDED"),
    ],
)
async def test_transient_errors_propagate(
    separator: TreatmentArmSeparator, error: Exception
) -> None:
    separator._call_llm_for_separation = AsyncMock(side_effect=error)  # type: ignore[method-assign]

    with pytest.raises(Exception) as excinfo:
        await separator.separate_treatment_arms("text", "abs_1")

    assert excinfo.value is error


@pytest.mark.asyncio
async def test_permanent_errors_still_return_an_empty_result(
    separator: TreatmentArmSeparator,
) -> None:
    """Non-transient failures keep the existing degrade-with-reason behaviour."""
    separator._call_llm_for_separation = AsyncMock(  # type: ignore[method-assign]
        side_effect=ValueError("schema did not validate")
    )

    result = await separator.separate_treatment_arms("text", "abs_1")

    assert result.treatment_arms == []
    assert result.errors == ["Separation failed: schema did not validate"]
