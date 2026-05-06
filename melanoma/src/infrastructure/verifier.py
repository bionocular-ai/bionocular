"""Bounded verifier pass for low-confidence extracted values.

When a primary extraction yields a value that fails deterministic validation,
this module asks the LLM (against the cached document context when available)
for a corrected, arm-scoped value. It retries up to ``MAX_VERIFIER_ATTEMPTS``
times before giving up.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from ..domain.extraction_models import (
    AttributeType,
    ExtractedAttribute,
    ValidationStatus,
)
from ..domain.treatment_arm_models import TreatmentArm
from .gemini_service import GeminiLLMService
from .value_validator import validate_for_attribute

logger = logging.getLogger(__name__)

MAX_VERIFIER_ATTEMPTS = 2
_VERIFIER_SOURCE = "verifier"
_VERIFIED_CONFIDENCE = 0.6


class VerifierSchema(BaseModel):
    """Structured response shape returned by the verifier LLM call."""

    value: str = ""
    quote: str = ""


async def verify_low_confidence(
    gemini: GeminiLLMService,
    cache_id: str | None,
    doc_text: str,
    arm: TreatmentArm,
    attribute: AttributeType,
    current_value: str,
    failure_reason: str,
) -> ExtractedAttribute:
    """Re-extract ``attribute`` for ``arm`` after a primary-extraction failure.

    Returns an ``ExtractedAttribute`` with one of three terminal statuses:
    ``VERIFIED`` (validator accepted), ``EMPTY`` (LLM said the doc has no
    value for this arm), or ``FAILED`` (exhausted attempts without a valid
    value).
    """
    logger.debug(
        "Entering verifier | arm=%s attribute=%s current_value=%r reason=%s",
        arm.arm_name,
        attribute.value,
        current_value,
        failure_reason,
    )
    for attempt in range(MAX_VERIFIER_ATTEMPTS):
        prompt = (
            f"For arm '{arm.arm_name}' ({arm.generic_name}), the field "
            f"{attribute.value} was extracted as '{current_value}' but failed "
            f"validation: {failure_reason}. "
            "Search the document for the correct value for THIS arm. "
            'Return JSON: {"value": "...", "quote": "...verbatim sentence..."}. '
            'If the document does not state this for this arm, return value="", quote="".'
        )
        result = await gemini.cached_or_inline_generate(
            cache_id, doc_text, prompt, VerifierSchema
        )
        ok, normalized, _ = validate_for_attribute(attribute, result.value)
        if ok or result.value == "":
            return ExtractedAttribute(
                attribute_type=attribute,
                value=normalized,
                source_quote=result.quote,
                confidence=_VERIFIED_CONFIDENCE if ok and result.value != "" else 0.0,
                source=_VERIFIER_SOURCE,
                validation_status=(
                    ValidationStatus.VERIFIED
                    if ok and result.value != ""
                    else ValidationStatus.EMPTY
                ),
            )
        logger.debug(
            "Verifier attempt %d/%d failed validation | value=%r",
            attempt + 1,
            MAX_VERIFIER_ATTEMPTS,
            result.value,
        )
        current_value = result.value
        failure_reason = f"verifier attempt {attempt + 1} also failed validation"

    return ExtractedAttribute(
        attribute_type=attribute,
        value=current_value,
        source_quote="",
        confidence=0.0,
        source=_VERIFIER_SOURCE,
        validation_status=ValidationStatus.FAILED,
    )
