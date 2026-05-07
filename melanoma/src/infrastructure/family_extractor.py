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
    TRIAL_LEVEL_ATTRIBUTES,
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
# Values come back from Gemini as plain strings (see _build_response_schema).
# Source quotes are populated only for verifier-corrected cells (verifier.py).
_CONFIDENCE_VALUE_PRESENT = 0.9
_CONFIDENCE_EMPTY_VALUE = 0.3


def _is_transient_error(exc: BaseException) -> bool:
    """Match 429 / RESOURCE_EXHAUSTED / 5xx errors worth retrying."""
    msg = str(exc).upper()
    if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "RATE_LIMIT" in msg:
        return True
    return any(code in msg for code in ("500", "502", "503", "504"))


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

        `doc_text` is now the family-specific slice produced by
        `family_section_router.slice_for_family` for publications. The Gemini cache
        still carries the full doc + system instruction; this slice is appended
        inline only when `cache_id` is `None` (see
        `gemini_service.cached_or_inline_generate`). For abstracts the orchestrator
        passes the full text (no slicing).

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
        return (
            _TOKEN_BUDGET_BASE
            + n_arms * len(FAMILY_TO_ATTRIBUTES[family]) * _TOKEN_BUDGET_PER_CELL
        )

    def _render_arms_block(self, arms: list[TreatmentArm]) -> str:
        """Compact `arm_id: name (type, n=N)` listing fed into the prompt."""
        lines: list[str] = ["Arms in this document:"]
        for arm in arms:
            n_str = f", n={arm.patient_count}" if arm.patient_count else ""
            lines.append(f"{arm.arm_id}: {arm.arm_name} ({arm.arm_type.value}{n_str})")
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
        arm_ids: list[str],
    ) -> type[BaseModel]:
        """Build the per-call Pydantic response schema.

        Trial-level attrs (NCT, trial_name, cancer_type, publication_*) are
        lifted into a single `trial` block so the LLM emits them once per
        document instead of once per arm. `_map_response` broadcasts the
        `trial` values back to every arm.

        Gemini's ``types.Schema`` does not support open-ended maps
        (``additionalProperties``), so we materialize one explicit field per
        ``arm_id`` rather than ``dict[str, PerArm]``.
        """
        attrs = FAMILY_TO_ATTRIBUTES[family]
        trial_attrs = tuple(a for a in attrs if a in TRIAL_LEVEL_ATTRIBUTES)
        per_arm_attrs = tuple(a for a in attrs if a not in TRIAL_LEVEL_ATTRIBUTES)

        per_arm_fields: dict[str, Any] = {
            attr.value: (str, Field(default="")) for attr in per_arm_attrs
        }
        per_arm_model = create_model(
            f"PerArm_{family.value}",
            __base__=BaseModel,
            **per_arm_fields,
        )

        arms_fields: dict[str, Any] = {
            arm_id: (per_arm_model, Field(default_factory=per_arm_model))
            for arm_id in arm_ids
        }
        arms_model = create_model(
            f"Arms_{family.value}",
            __base__=BaseModel,
            **arms_fields,
        )

        wrapper_fields: dict[str, Any] = {
            "arms": (arms_model, Field(default_factory=arms_model)),
        }
        if trial_attrs:
            trial_fields: dict[str, Any] = {
                attr.value: (str, Field(default="")) for attr in trial_attrs
            }
            trial_model = create_model(
                f"Trial_{family.value}",
                __base__=BaseModel,
                **trial_fields,
            )
            wrapper_fields["trial"] = (
                trial_model,
                Field(default_factory=trial_model),
            )

        return create_model(
            f"FamilyExtractionResponse_{family.value}",
            __base__=BaseModel,
            **wrapper_fields,
        )

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

        arms_model = getattr(response, "arms", None)
        if arms_model is None:
            return result

        trial_model = getattr(response, "trial", None)
        # Walk declared fields so unset arms surface as the default empty PerArm.
        arms_obj: dict[str, BaseModel] = {
            field_name: getattr(arms_model, field_name)
            for field_name in arms_model.__class__.model_fields
        }
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
                if attr in TRIAL_LEVEL_ATTRIBUTES:
                    raw = getattr(trial_model, attr.value, "") if trial_model else ""
                else:
                    raw = getattr(per_arm, attr.value, "")
                value = (raw or "").strip()
                arm_result[attr] = ExtractedAttribute(
                    attribute_type=attr,
                    value=value,
                    source_quote="",
                    confidence=self._confidence_for(value),
                    source=family.value,
                    validation_status=ValidationStatus.PENDING,
                )
            result[arm_id] = arm_result

        return result

    @staticmethod
    def _confidence_for(value: str) -> float:
        return _CONFIDENCE_EMPTY_VALUE if not value else _CONFIDENCE_VALUE_PRESENT
