"""Tests for FamilyExtractor."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel

from src.domain.extraction_models import (
    FAMILY_TO_ATTRIBUTES,
    AttributeFamily,
    AttributeType,
)
from src.domain.treatment_arm_models import ArmType, LineOfTreatment, TreatmentArm
from src.infrastructure.family_extractor import FamilyExtractor


def _arm(arm_id: str, name: str, n: int = 100) -> TreatmentArm:
    return TreatmentArm(
        arm_id=arm_id,
        arm_name=name,
        generic_name=name,
        combination_drugs=[],
        arm_type=ArmType.MONOTHERAPY,
        line_of_treatment=LineOfTreatment.FIRST_LINE,
        patient_count=n,
        source_text=name,
    )


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_max_tokens_budget_formula() -> None:
    fe = FamilyExtractor(gemini=AsyncMock())
    n = len(FAMILY_TO_ATTRIBUTES[AttributeFamily.AE_GRADE3_SPECIFIC])
    assert fe._max_tokens_for(AttributeFamily.AE_GRADE3_SPECIFIC, 5) == 200 + 5 * n * 60


def test_arms_block_rendering_lists_each_arm() -> None:
    fe = FamilyExtractor(gemini=AsyncMock())
    arms = [_arm("arm_1", "Nivolumab"), _arm("arm_2", "Ipilimumab")]
    block = fe._render_arms_block(arms)
    assert "arm_1" in block and "Nivolumab" in block
    assert "arm_2" in block and "Ipilimumab" in block


def test_dynamic_schema_includes_only_family_attrs() -> None:
    fe = FamilyExtractor(gemini=AsyncMock())
    schema = fe._build_response_schema(AttributeFamily.OS_FAMILY, ["arm_1", "arm_2"])
    arm_model = schema.model_fields["arms"].annotation.__args__[1]
    field_keys = set(arm_model.model_fields.keys())
    expected = {a.value for a in FAMILY_TO_ATTRIBUTES[AttributeFamily.OS_FAMILY]}
    assert field_keys == expected


def test_dynamic_schema_excludes_derived_attrs() -> None:
    """MODALITY/TARGET are not in any FAMILY_TO_ATTRIBUTES entry."""
    fe = FamilyExtractor(gemini=AsyncMock())
    for family in AttributeFamily:
        schema = fe._build_response_schema(family, ["arm_1"])
        arm_model = schema.model_fields["arms"].annotation.__args__[1]
        keys = set(arm_model.model_fields.keys())
        assert AttributeType.MODALITY.value not in keys
        assert AttributeType.TARGET.value not in keys


# ---------------------------------------------------------------------------
# extract() — happy path mapping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_calls_gemini_and_maps_response() -> None:
    family = AttributeFamily.OS_FAMILY
    arms = [_arm("arm_1", "Nivolumab"), _arm("arm_2", "Ipilimumab")]

    gemini = AsyncMock()

    async def fake_call(
        cache_id: str | None,
        doc_text: str,
        prompt: str,
        response_schema: type[BaseModel],
        temperature: float = 0.1,
        max_tokens: int = 4000,
    ) -> BaseModel:
        # Build a payload that matches the dynamic schema for OS_FAMILY.
        payload = {
            "arms": {
                "arm_1": {
                    "median_os": {
                        "value": "32.7",
                        "quote": "median OS was 32.7 months",
                    },
                    "hr_os": {"value": "", "quote": ""},
                },
                "arm_2": {
                    "median_os": {
                        "value": "20.0",
                        "quote": "median OS was 20.0 months",
                    },
                },
            }
        }
        return response_schema.model_validate(payload)

    gemini.cached_or_inline_generate = fake_call

    fe = FamilyExtractor(gemini=gemini)
    result = await fe.extract(None, "doc text", family, arms)

    assert set(result.keys()) == {"arm_1", "arm_2"}

    arm1 = result["arm_1"]
    assert AttributeType.MEDIAN_OS in arm1
    median_os = arm1[AttributeType.MEDIAN_OS]
    assert median_os.value == "32.7"
    assert median_os.source_quote == "median OS was 32.7 months"
    assert median_os.confidence == 0.9
    assert median_os.source == family.value

    # Empty cell → low confidence sentinel
    hr_os = arm1[AttributeType.HR_OS]
    assert hr_os.value == ""
    assert hr_os.confidence == 0.3

    assert result["arm_2"][AttributeType.MEDIAN_OS].value == "20.0"


@pytest.mark.asyncio
async def test_extract_skips_unknown_arm_id_from_llm() -> None:
    family = AttributeFamily.OS_FAMILY
    arms = [_arm("arm_1", "Nivolumab")]

    gemini = AsyncMock()

    async def fake_call(
        cache_id, doc_text, prompt, response_schema, temperature=0.1, max_tokens=4000
    ):
        payload = {
            "arms": {
                "arm_1": {"median_os": {"value": "10.0", "quote": "ten months"}},
                "arm_99_hallucinated": {"median_os": {"value": "X", "quote": "Y"}},
            }
        }
        return response_schema.model_validate(payload)

    gemini.cached_or_inline_generate = fake_call

    fe = FamilyExtractor(gemini=gemini)
    result = await fe.extract(None, "doc", family, arms)

    assert set(result.keys()) == {"arm_1"}
    assert result["arm_1"][AttributeType.MEDIAN_OS].value == "10.0"


@pytest.mark.asyncio
async def test_extract_returns_empty_dict_for_omitted_arm() -> None:
    family = AttributeFamily.OS_FAMILY
    arms = [_arm("arm_1", "Nivolumab"), _arm("arm_2", "Ipilimumab")]

    gemini = AsyncMock()

    async def fake_call(
        cache_id, doc_text, prompt, response_schema, temperature=0.1, max_tokens=4000
    ):
        payload = {
            "arms": {
                "arm_1": {"median_os": {"value": "10.0", "quote": "ten months"}},
            }
        }
        return response_schema.model_validate(payload)

    gemini.cached_or_inline_generate = fake_call

    fe = FamilyExtractor(gemini=gemini)
    result = await fe.extract(None, "doc", family, arms)

    assert result["arm_2"] == {}


# ---------------------------------------------------------------------------
# Concurrency cap
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_semaphore_caps_in_flight() -> None:
    family = AttributeFamily.OS_FAMILY
    arms = [_arm("arm_1", "Nivolumab")]

    state = {"in_flight": 0, "max_in_flight": 0}

    async def fake_call(
        cache_id, doc_text, prompt, response_schema, temperature=0.1, max_tokens=4000
    ):
        state["in_flight"] += 1
        state["max_in_flight"] = max(state["max_in_flight"], state["in_flight"])
        await asyncio.sleep(0.05)
        state["in_flight"] -= 1
        return response_schema.model_validate({"arms": {}})

    gemini = AsyncMock()
    gemini.cached_or_inline_generate = fake_call

    fe = FamilyExtractor(gemini=gemini, concurrency=2)

    await asyncio.gather(*(fe.extract(None, "doc", family, arms) for _ in range(8)))

    assert state["max_in_flight"] == 2


# ---------------------------------------------------------------------------
# Tenacity retry behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retries_on_transient_429() -> None:
    family = AttributeFamily.OS_FAMILY
    arms = [_arm("arm_1", "Nivolumab")]

    calls = {"n": 0}

    async def fake_call(
        cache_id, doc_text, prompt, response_schema, temperature=0.1, max_tokens=4000
    ):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("429 Too Many Requests: RATE_LIMIT_EXCEEDED")
        payload = {
            "arms": {
                "arm_1": {"median_os": {"value": "12.0", "quote": "twelve months"}}
            }
        }
        return response_schema.model_validate(payload)

    gemini = AsyncMock()
    gemini.cached_or_inline_generate = fake_call

    fe = FamilyExtractor(gemini=gemini)
    result = await fe.extract(None, "doc", family, arms)

    assert calls["n"] == 2
    assert result["arm_1"][AttributeType.MEDIAN_OS].value == "12.0"


@pytest.mark.asyncio
async def test_does_not_retry_on_non_transient_error() -> None:
    family = AttributeFamily.OS_FAMILY
    arms = [_arm("arm_1", "Nivolumab")]

    calls = {"n": 0}

    async def fake_call(*a, **kw):
        calls["n"] += 1
        raise ValueError("schema validation failed: not retryable")

    gemini = AsyncMock()
    gemini.cached_or_inline_generate = fake_call

    fe = FamilyExtractor(gemini=gemini)
    with pytest.raises(ValueError):
        await fe.extract(None, "doc", family, arms)

    assert calls["n"] == 1
