"""Extraction prompt template provider — infrastructure layer.

Implements `PromptTemplateProvider` (domain interface) using prompt data
from `domain.prompt_templates`. This file owns nothing proprietary:
it only wires domain data to the interface contract and handles
context formatting for LLM calls.
"""

import logging
from typing import Any

from ..domain.extraction_interfaces import PromptTemplateProvider
from ..domain.extraction_models import AttributeType
from ..domain.prompt_templates import (
    ARM_SPECIFIC_VERIFICATION_PREFIX,
    ATTRIBUTE_PROMPTS,
    SHARED_EXTRACTION_RULES,
)

logger = logging.getLogger(__name__)


class ExtractionPromptTemplateProvider(PromptTemplateProvider):
    """Implements PromptTemplateProvider using domain prompt data."""

    def __init__(self) -> None:
        self.extraction_prompts = ATTRIBUTE_PROMPTS
        self.arm_specific_verification_prefix = ARM_SPECIFIC_VERIFICATION_PREFIX
        self.shared_extraction_rules = SHARED_EXTRACTION_RULES
        logger.info("Prompt template provider initialized")

    def get_extraction_prompt(
        self, attribute_type: AttributeType, context: list[str]
    ) -> str:
        """Build extraction prompt for an attribute type.

        Args:
            attribute_type: Type of attribute to extract
            context: Context texts retrieved from RAG

        Returns:
            Formatted extraction prompt ready for LLM
        """
        logger.debug(
            "get_extraction_prompt called with attribute_type: %s (type: %s)",
            attribute_type,
            type(attribute_type),
        )

        if attribute_type in self.extraction_prompts:
            logger.debug("Found explicit prompt for %s", attribute_type)
            base_prompt = self.extraction_prompts[attribute_type]
        else:
            logger.debug(
                "No explicit prompt for %s, using dynamic prompt", attribute_type
            )
            base_prompt = self._get_dynamic_prompt(attribute_type)

        if self._needs_arm_specific_verification(attribute_type):
            base_prompt = self.arm_specific_verification_prefix + base_prompt

        context_text = self._format_context(context)
        return f"{self.shared_extraction_rules}\n\n{base_prompt}\n\nCONTEXT:\n{context_text}"

    def _get_dynamic_prompt(self, attribute_type: AttributeType) -> str:
        attr_name = attribute_type.value.replace("_", " ").title()
        return f"""
Extract the {attr_name} from the provided context.

Look for:
- Direct mentions of {attr_name}
- Related terms and synonyms
- Numerical values if applicable
- Context clues that indicate the value

The value should be the extracted value, or "Not found" if not available.
"""

    def _needs_arm_specific_verification(self, attribute_type: AttributeType) -> bool:
        return attribute_type in {AttributeType.NUMBER_OF_PATIENTS}

    def _format_context(self, context: list[Any]) -> str:
        if not context:
            return "No context available."

        formatted_chunks = []
        for i, chunk in enumerate(context, 1):
            chunk_text = chunk.content if hasattr(chunk, "content") else str(chunk)
            formatted_chunks.append(f"[Context {i}]\n{chunk_text.strip()}\n")

        return "\n".join(formatted_chunks)
