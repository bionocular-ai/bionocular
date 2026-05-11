"""Tests for the EnhancedExtractionService routing + new family-grouped path."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.app.enhanced_extraction_service import (
    LEGACY_FLAG_ENABLED_VALUE,
    LEGACY_FLAG_ENV,
    PROMPT_VERSION,
    EnhancedExtractionService,
)
from src.domain.extraction_models import (
    FAMILY_TO_ATTRIBUTES,
    AttributeFamily,
    AttributeType,
    ExtractedAttribute,
    ValidationStatus,
)
from src.domain.models import DocumentType
from src.domain.treatment_arm_models import (
    TreatmentArm,
    TreatmentArmExtractionResult,
    TreatmentArmSeparationResult,
)

# ── Fixtures ────────────────────────────────────────────────────────────────


def _arm(arm_id: str = "arm-1", name: str = "Pembrolizumab") -> TreatmentArm:
    return TreatmentArm(
        arm_id=arm_id,
        arm_name=name,
        generic_name=name.lower(),
    )


def _make_service(
    family_extractor: AsyncMock | None = None,
    gemini: AsyncMock | None = None,
    arm_separator: AsyncMock | None = None,
) -> EnhancedExtractionService:
    """Build a service wired only with the new-path deps required by tests."""
    if arm_separator is None:
        arm_separator = AsyncMock()
        arm_separator.separate_treatment_arms = AsyncMock(
            return_value=TreatmentArmSeparationResult(
                abstract_id="doc-1",
                treatment_arms=[_arm()],
                separation_confidence=1.0,
                processing_time_ms=1,
            )
        )
    if gemini is None:
        gemini = AsyncMock()
        gemini.create_context_cache = AsyncMock(return_value="cache-xyz")
        gemini.delete_cache = AsyncMock(return_value=None)
    if family_extractor is None:
        family_extractor = AsyncMock()
        family_extractor.extract = AsyncMock(return_value={"arm-1": {}})

    return EnhancedExtractionService(
        treatment_arm_separator=arm_separator,
        family_extractor=family_extractor,
        gemini=gemini,
        enable_cost_tracking=False,
    )


# ── Routing ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_enhanced_extraction_service_routes_by_env_flag(monkeypatch) -> None:
    monkeypatch.setenv(LEGACY_FLAG_ENV, LEGACY_FLAG_ENABLED_VALUE)
    service = _make_service()
    legacy_sentinel = TreatmentArmExtractionResult(
        abstract_id="doc-1",
        arm_results={},
        overall_confidence=0.0,
        processing_time_ms=0,
    )
    with patch.object(
        service, "_legacy_rag_extract", new=AsyncMock(return_value=legacy_sentinel)
    ) as legacy_mock:
        result = await service.extract("text", "doc-1", DocumentType.ABSTRACT)
    legacy_mock.assert_awaited_once()
    assert result is legacy_sentinel


@pytest.mark.asyncio
async def test_enhanced_extraction_service_uses_new_path_by_default(
    monkeypatch,
) -> None:
    monkeypatch.delenv(LEGACY_FLAG_ENV, raising=False)
    service = _make_service()
    with patch(
        "src.app.enhanced_extraction_service.enrich_result",
        side_effect=lambda r: r,
    ):
        result = await service.extract("text", "doc-1", DocumentType.ABSTRACT)
    assert result.prompt_version == PROMPT_VERSION
    service.gemini.create_context_cache.assert_awaited_once()
    service.gemini.delete_cache.assert_awaited_once_with("cache-xyz")


@pytest.mark.asyncio
async def test_extract_raises_when_legacy_flag_set_without_legacy_deps(
    monkeypatch,
) -> None:
    monkeypatch.setenv(LEGACY_FLAG_ENV, LEGACY_FLAG_ENABLED_VALUE)
    service = _make_service()  # no legacy deps wired
    with pytest.raises(RuntimeError, match=LEGACY_FLAG_ENV):
        await service.extract("text", "doc-1", DocumentType.ABSTRACT)


# ── Family selection ────────────────────────────────────────────────────────


def test_families_for_doc_type_abstract_includes_all_families() -> None:
    service = _make_service()
    families = service._families_for_doc_type(DocumentType.ABSTRACT)
    assert set(families) == set(FAMILY_TO_ATTRIBUTES.keys())
    assert len(families) == 12


def test_families_for_doc_type_publication_includes_all_12() -> None:
    service = _make_service()
    families = service._families_for_doc_type(DocumentType.PUBLICATION)
    assert set(families) == set(FAMILY_TO_ATTRIBUTES.keys())
    assert len(families) == 12


# ── _assemble_result ────────────────────────────────────────────────────────


def test_assemble_result_sets_prompt_version() -> None:
    service = _make_service()
    arm = _arm()
    per_arm = {
        arm.arm_id: {
            AttributeType.HR_OS: ExtractedAttribute(
                attribute_type=AttributeType.HR_OS,
                value="0.65",
                confidence=0.9,
                source="os_family",
                validation_status=ValidationStatus.VALID,
            )
        }
    }
    result = service._assemble_result(
        doc_id="doc-1",
        arms=[arm],
        per_arm=per_arm,
        processing_time_ms=10,
        prompt_version=PROMPT_VERSION,
    )
    assert result.prompt_version == PROMPT_VERSION
    assert "arm-1" in result.arm_results
    assert (
        result.arm_results["arm-1"]["attributes"][AttributeType.HR_OS.value]["value"]
        == "0.65"
    )


# ── Validation → verifier flow ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_extract_runs_validation_then_verifier_for_invalid(
    monkeypatch,
) -> None:
    monkeypatch.delenv(LEGACY_FLAG_ENV, raising=False)

    family_extractor = AsyncMock()

    async def _extract(cache_id, doc_text, family, arms):
        # Only return a value for OS_FAMILY so a single invalid value flows
        # through the validator → verifier pipeline.
        if family == AttributeFamily.OS_FAMILY:
            return {
                "arm-1": {
                    AttributeType.HR_OS: ExtractedAttribute(
                        attribute_type=AttributeType.HR_OS,
                        value="totally-not-a-number",
                        confidence=0.4,
                        source="os_family",
                        validation_status=ValidationStatus.PENDING,
                    )
                }
            }
        return {"arm-1": {}}

    family_extractor.extract = AsyncMock(side_effect=_extract)

    service = _make_service(family_extractor=family_extractor)

    verified_attr = ExtractedAttribute(
        attribute_type=AttributeType.HR_OS,
        value="0.65",
        confidence=0.6,
        source="verifier",
        validation_status=ValidationStatus.VERIFIED,
    )

    with patch(
        "src.app.enhanced_extraction_service.verify_low_confidence",
        new=AsyncMock(return_value=verified_attr),
    ) as verify_mock, patch(
        "src.app.enhanced_extraction_service.enrich_result",
        side_effect=lambda r: r,
    ):
        await service.extract("text", "doc-1", DocumentType.PUBLICATION)

    verify_mock.assert_awaited_once()
    args, kwargs = verify_mock.call_args
    # 4th positional is the arm, 5th is the attribute type
    assert (
        kwargs.get("attribute", args[4] if len(args) > 4 else None)
        == AttributeType.HR_OS
    )


@pytest.mark.asyncio
async def test_extract_skips_verifier_when_value_valid(monkeypatch) -> None:
    monkeypatch.delenv(LEGACY_FLAG_ENV, raising=False)

    family_extractor = AsyncMock()

    async def _extract(cache_id, doc_text, family, arms):
        if family == AttributeFamily.OS_FAMILY:
            return {
                "arm-1": {
                    AttributeType.HR_OS: ExtractedAttribute(
                        attribute_type=AttributeType.HR_OS,
                        value="0.65",
                        confidence=0.9,
                        source="os_family",
                        validation_status=ValidationStatus.PENDING,
                    )
                }
            }
        return {"arm-1": {}}

    family_extractor.extract = AsyncMock(side_effect=_extract)
    service = _make_service(family_extractor=family_extractor)

    with patch(
        "src.app.enhanced_extraction_service.verify_low_confidence",
        new=AsyncMock(),
    ) as verify_mock, patch(
        "src.app.enhanced_extraction_service.enrich_result",
        side_effect=lambda r: r,
    ):
        await service.extract("text", "doc-1", DocumentType.PUBLICATION)

    verify_mock.assert_not_awaited()


# ── Enrich + cache cleanup ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_extract_calls_enrich_after_assembly(monkeypatch) -> None:
    monkeypatch.delenv(LEGACY_FLAG_ENV, raising=False)
    service = _make_service()

    enrich_mock = MagicMock(side_effect=lambda r: r)
    with patch("src.app.enhanced_extraction_service.enrich_result", new=enrich_mock):
        result = await service.extract("text", "doc-1", DocumentType.ABSTRACT)

    enrich_mock.assert_called_once()
    assert enrich_mock.call_args.args[0] is result


@pytest.mark.asyncio
async def test_extract_deletes_cache_in_finally(monkeypatch) -> None:
    monkeypatch.delenv(LEGACY_FLAG_ENV, raising=False)
    arm_separator = AsyncMock()
    arm_separator.separate_treatment_arms = AsyncMock(side_effect=RuntimeError("boom"))
    service = _make_service(arm_separator=arm_separator)

    with pytest.raises(RuntimeError, match="boom"):
        await service.extract("text", "doc-1", DocumentType.ABSTRACT)

    service.gemini.delete_cache.assert_awaited_once_with("cache-xyz")
