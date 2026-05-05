"""Family-grouped attribute extractor.

One LLM call per (document, attribute family). Uses Gemini structured output
with a Pydantic schema dynamically built from `FAMILY_TO_ATTRIBUTES[family]`
and the supplied treatment arms. Bounded concurrency via `asyncio.Semaphore`
so an orchestrator can launch all 12 family extractions with `asyncio.gather`
without blowing past the configured cap.

Replaces the per-attribute mega-loop in `batch_attribute_extractor.py`.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pydantic import BaseModel, Field, create_model
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from ..domain.extraction_models import (
    FAMILY_TO_ATTRIBUTES,
    AttributeFamily,
    AttributeType,
    ExtractedAttribute,
    ValidationStatus,
)
from ..domain.prompt_templates import (
    ARM_SPECIFIC_VERIFICATION_PREFIX,
    FAMILY_PROMPTS,
    SHARED_EXTRACTION_RULES,
)
from ..domain.treatment_arm_models import TreatmentArm
from .gemini_service import GeminiLLMService

logger = logging.getLogger(__name__)

# Token-budget tuning constants.
_TOKEN_BUDGET_BASE = 200
_TOKEN_BUDGET_PER_CELL = 60

# Confidence heuristics for ExtractedAttribute.
_CONFIDENCE_VALUE_AND_QUOTE = 0.9
_CONFIDENCE_EMPTY_VALUE = 0.3
_CONFIDENCE_VALUE_NO_QUOTE = 0.0


def _is_transient_error(exc: BaseException) -> bool:
    """Match 429 / RESOURCE_EXHAUSTED / 5xx errors worth retrying."""
    msg = str(exc).upper()
    if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "RATE_LIMIT" in msg:
        return True
    return any(code in msg for code in ("500", "502", "503", "504"))


class _ValueWithQuote(BaseModel):
    """One extracted cell: the value and the verbatim sentence it came from."""

    value: str = ""
    quote: str = ""


class FamilyExtractor:
    """Extract one attribute family across all arms in a single LLM call."""

    def __init__(self, gemini: GeminiLLMService, concurrency: int = 4) -> None:
        self._gemini = gemini
        self._sem = asyncio.Semaphore(concurrency)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    async def extract(
        self,
        cache_id: str | None,
        doc_text: str,
        family: AttributeFamily,
        arms: list[TreatmentArm],
    ) -> dict[str, dict[AttributeType, ExtractedAttribute]]:
        """Extract one attribute family for all `arms`.

        Returns `{arm_id: {attribute: ExtractedAttribute}}`. Arms the LLM omits
        come back as empty dicts; arm_ids the LLM hallucinated are skipped with
        a warning.
        """
        if not arms:
            return {}

        arm_ids = [arm.arm_id for arm in arms]
        attrs = FAMILY_TO_ATTRIBUTES[family]
        schema = self._build_response_schema(family, arm_ids)
        prompt = self._build_prompt(family, arms)
        max_tokens = self._max_tokens_for(family, len(arms))

        async with self._sem:
            response = await self._call_with_retry(
                cache_id=cache_id,
                doc_text=doc_text,
                prompt=prompt,
                schema=schema,
                max_tokens=max_tokens,
            )

        return self._map_response(response, family, arm_ids, attrs)

    # ------------------------------------------------------------------ #
    # Helpers (testable in isolation)
    # ------------------------------------------------------------------ #

    def _max_tokens_for(self, family: AttributeFamily, n_arms: int) -> int:
        """Pure budget formula. Tested directly."""
        return _TOKEN_BUDGET_BASE + n_arms * len(FAMILY_TO_ATTRIBUTES[family]) * _TOKEN_BUDGET_PER_CELL

    def _render_arms_block(self, arms: list[TreatmentArm]) -> str:
        """Compact `arm_id: name (type, n=N)` listing fed into the prompt."""
        lines: list[str] = ["Arms in this document:"]
        for arm in arms:
            n_str = f", n={arm.patient_count}" if arm.patient_count else ""
            lines.append(
                f"{arm.arm_id}: {arm.arm_name} ({arm.arm_type.value}{n_str})"
            )
        lines.append("")
        lines.append(
            "Return one JSON object whose top-level key is `arms`, mapping each "
            "arm_id above to that arm's attribute object. Use the exact arm_id "
            "strings as keys."
        )
        return "\n".join(lines)

    def _build_prompt(self, family: AttributeFamily, arms: list[TreatmentArm]) -> str:
        arms_block = self._render_arms_block(arms)
        # Use replace, not str.format — FAMILY_PROMPTS contain literal `{...}`
        # JSON examples that would break str.format's brace parsing.
        family_prompt = FAMILY_PROMPTS[family].replace("{arms_block}", arms_block)
        return (
            f"{SHARED_EXTRACTION_RULES}\n\n"
            f"{ARM_SPECIFIC_VERIFICATION_PREFIX}\n\n"
            f"{family_prompt}"
        )

    def _build_response_schema(
        self,
        family: AttributeFamily,
        arm_ids: list[str],  # noqa: ARG002 — kept for API symmetry / tests
    ) -> type[BaseModel]:
        """Build the per-call Pydantic response schema.

        The schema mirrors `FAMILY_TO_ATTRIBUTES[family]`: derived attributes
        (MODALITY, TARGET) live outside that map, so they are naturally absent.
        """
        attrs = FAMILY_TO_ATTRIBUTES[family]
        per_arm_fields: dict[str, Any] = {
            attr.value: (_ValueWithQuote, Field(default_factory=_ValueWithQuote))
            for attr in attrs
        }
        per_arm_model = create_model(
            f"PerArm_{family.value}",
            __base__=BaseModel,
            **per_arm_fields,
        )

        wrapper = create_model(
            f"FamilyExtractionResponse_{family.value}",
            __base__=BaseModel,
            arms=(dict[str, per_arm_model], Field(default_factory=dict)),
        )
        return wrapper

    # ------------------------------------------------------------------ #
    # LLM call + retry
    # ------------------------------------------------------------------ #

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        retry=retry_if_exception(_is_transient_error),
        reraise=True,
    )
    async def _call_with_retry(
        self,
        cache_id: str | None,
        doc_text: str,
        prompt: str,
        schema: type[BaseModel],
        max_tokens: int,
    ) -> BaseModel:
        return await self._gemini.cached_or_inline_generate(
            cache_id,
            doc_text,
            prompt,
            schema,
            temperature=0.1,
            max_tokens=max_tokens,
        )

    # ------------------------------------------------------------------ #
    # Response → domain mapping
    # ------------------------------------------------------------------ #

    def _map_response(
        self,
        response: BaseModel,
        family: AttributeFamily,
        arm_ids: list[str],
        attrs: tuple[AttributeType, ...],
    ) -> dict[str, dict[AttributeType, ExtractedAttribute]]:
        result: dict[str, dict[AttributeType, ExtractedAttribute]] = {
            arm_id: {} for arm_id in arm_ids
        }
        known = set(arm_ids)

        arms_obj: dict[str, BaseModel] = getattr(response, "arms", {}) or {}
        for arm_id, per_arm in arms_obj.items():
            if arm_id not in known:
                logger.warning(
                    "FamilyExtractor: LLM returned unknown arm_id=%s for family=%s — skipping",
                    arm_id,
                    family.value,
                )
                continue
            arm_result: dict[AttributeType, ExtractedAttribute] = {}
            for attr in attrs:
                cell = getattr(per_arm, attr.value, None)
                if cell is None:
                    continue
                value = (cell.value or "").strip()
                quote = (cell.quote or "").strip()
                arm_result[attr] = ExtractedAttribute(
                    attribute_type=attr,
                    value=value,
                    source_quote=quote,
                    confidence=self._confidence_for(value, quote),
                    source=family.value,
                    validation_status=ValidationStatus.PENDING,
                )
            result[arm_id] = arm_result

        return result

    @staticmethod
    def _confidence_for(value: str, quote: str) -> float:
        if not value:
            return _CONFIDENCE_EMPTY_VALUE
        if not quote:
            return _CONFIDENCE_VALUE_NO_QUOTE
        return _CONFIDENCE_VALUE_AND_QUOTE
