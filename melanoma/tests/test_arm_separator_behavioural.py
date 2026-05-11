"""Behavioural fixture tests for treatment arm separator.

Each fixture is a known trap that historically caused over-segmentation.
These tests use the real Gemini API and are marked @pytest.mark.integration —
they're skipped in fast feedback loops.
"""
import os
from pathlib import Path

import pytest

from src.infrastructure.gemini_service import GeminiLLMService
from src.infrastructure.treatment_arm_separator import TreatmentArmSeparator

FIXTURES = Path(__file__).parent / "fixtures" / "arm_separator"

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture
def separator() -> TreatmentArmSeparator:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        pytest.skip("GOOGLE_API_KEY not set")
    llm = GeminiLLMService(api_key=api_key)
    return TreatmentArmSeparator(llm)


async def test_subgroup_analyses_are_not_separate_arms(
    separator: TreatmentArmSeparator,
) -> None:
    text = (FIXTURES / "subgroup_trap.md").read_text()
    result = await separator.separate_treatment_arms(text, "subgroup_trap")
    arm_count = len(result.treatment_arms)
    arm_names = [a.arm_name.lower() for a in result.treatment_arms]
    assert arm_count == 1, f"expected 1 arm, got {arm_count}: {arm_names}"
    # No biomarker labels in arm names
    for name in arm_names:
        assert "braf+" not in name and "braf-" not in name and "braf wild" not in name


async def test_dose_escalation_cohorts_are_not_separate_arms(
    separator: TreatmentArmSeparator,
) -> None:
    text = (FIXTURES / "dose_escalation_trap.md").read_text()
    result = await separator.separate_treatment_arms(text, "dose_escalation_trap")
    arm_count = len(result.treatment_arms)
    arm_names = [a.arm_name for a in result.treatment_arms]
    assert arm_count <= 2, f"expected at most 2 arms, got {arm_count}: {arm_names}"


async def test_geographic_cohorts_are_not_separate_arms(
    separator: TreatmentArmSeparator,
) -> None:
    text = (FIXTURES / "geographic_cohort_trap.md").read_text()
    result = await separator.separate_treatment_arms(text, "geographic_cohort_trap")
    arm_count = len(result.treatment_arms)
    arm_names = [a.arm_name for a in result.treatment_arms]
    assert arm_count == 1, f"expected 1 arm, got {arm_count}: {arm_names}"
