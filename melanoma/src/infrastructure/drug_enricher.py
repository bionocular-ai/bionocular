"""Drug enrichment: canonicalize drug names + derive MODALITY / TARGET per arm.

Walks a TreatmentArmExtractionResult, mutates each arm dict in-place to:
    - Replace arm_name / generic_name / combination_drugs with canonical forms.
    - Attach MODALITY and TARGET attributes (as ExtractedAttribute dicts) to the
      arm's `attributes` map, with source='drug_knowledge'.

Unknown drugs are logged so the KB can be expanded.
"""

import logging
from typing import Any

from ..domain.drug_knowledge import (
    canonicalize,
    get_drug_info,
    get_modality,
    get_target,
)
from ..domain.extraction_models import (
    AttributeType,
    ExtractedAttribute,
    ValidationStatus,
)
from ..domain.treatment_arm_models import TreatmentArmExtractionResult

logger = logging.getLogger(__name__)

_DRUG_KNOWLEDGE_SOURCE = "drug_knowledge"


def _attr_dict(attribute_type: AttributeType, value: str) -> dict[str, Any]:
    """Build an ExtractedAttribute as a serialized dict matching arm_results shape."""
    attr = ExtractedAttribute(
        attribute_type=attribute_type,
        value=value,
        confidence=1.0 if value else 0.0,
        source=_DRUG_KNOWLEDGE_SOURCE,
        validation_status=ValidationStatus.PENDING,
    )
    return {
        "value": attr.value,
        "confidence": attr.confidence,
        "validation_status": attr.validation_status.value,
        "source_chunks": list(attr.source_chunks),
        "source": attr.source,
    }


def _log_unknowns(name: str) -> None:
    """Log a warning for any sub-drug not in the KB."""
    if not name or not name.strip():
        return
    parts = [p.strip() for p in name.split("+") if p.strip()] or [name.strip()]
    for p in parts:
        if get_drug_info(p) is None:
            logger.warning("drug_enricher: unknown drug '%s' (KB miss)", p)


def enrich_result(
    result: TreatmentArmExtractionResult,
) -> TreatmentArmExtractionResult:
    """Canonicalize drug names + derive MODALITY/TARGET per arm.

    Walks `result.arm_results` (a `dict[arm_id, dict[str, Any]]`), replaces
    arm_name / generic_name / combination_drugs with canonical forms via
    drug_knowledge, then attaches MODALITY and TARGET as ExtractedAttribute
    entries with source='drug_knowledge'. Logs unknowns so the KB can grow.
    """
    if not result.arm_results:
        return result

    for arm_id, arm in result.arm_results.items():
        if not isinstance(arm, dict):
            logger.warning(
                "drug_enricher: arm %s is not a dict (got %s) — skipping",
                arm_id,
                type(arm).__name__,
            )
            continue

        # Pick the best name to derive canonical / modality / target from.
        # Prefer generic_name (cleaner), fall back to arm_name.
        generic_name = arm.get("generic_name") or ""
        arm_name = arm.get("arm_name") or ""
        combination_drugs = arm.get("combination_drugs") or []

        source_name = generic_name or arm_name

        # Canonicalize names.
        if generic_name:
            arm["generic_name"] = canonicalize(generic_name)
        if arm_name:
            arm["arm_name"] = canonicalize(arm_name)
        if combination_drugs:
            arm["combination_drugs"] = [canonicalize(d) for d in combination_drugs]

        # Log unknowns from the source we're about to derive from.
        _log_unknowns(source_name)
        for d in combination_drugs:
            _log_unknowns(d)

        # Derive modality/target.
        modality = get_modality(source_name)
        target = get_target(source_name)

        # Ensure attributes map exists.
        attributes = arm.setdefault("attributes", {})
        if not isinstance(attributes, dict):
            logger.warning(
                "drug_enricher: arm %s has non-dict 'attributes' — skipping enrichment",
                arm_id,
            )
            continue

        attributes[AttributeType.MODALITY.value] = _attr_dict(
            AttributeType.MODALITY, modality
        )
        attributes[AttributeType.TARGET.value] = _attr_dict(
            AttributeType.TARGET, target
        )

    return result
