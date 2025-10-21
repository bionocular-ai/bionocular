"""Batch attribute extractor for processing multiple treatment arms efficiently.

This module provides batch processing capabilities to extract attributes for multiple
treatment arms in a single LLM call, significantly reducing API costs and processing time.
"""

import asyncio
import json
import logging
from typing import Any

from ..domain.extraction_models import AttributeType, ExtractedAttribute
from ..domain.treatment_arm_models import TreatmentArm
from .cost_tracking_llm_service import CostTrackingLLMService
from .prompt_templates import ExtractionPromptTemplateProvider

logger = logging.getLogger(__name__)


class BatchAttributeExtractor:
    """Extracts attributes for multiple treatment arms in batch operations."""

    def __init__(
        self,
        llm_service: CostTrackingLLMService,
        prompt_provider: ExtractionPromptTemplateProvider,
    ):
        """Initialize batch attribute extractor.

        Args:
            llm_service: LLM service with cost tracking
            prompt_provider: Prompt template provider
        """
        self.llm_service = llm_service
        self.prompt_provider = prompt_provider
        logger.info("Batch attribute extractor initialized")

    async def extract_attributes_for_arms(
        self,
        arms: list[TreatmentArm],
        attributes: list[AttributeType],
        context: list[str],
        document_id: str,
    ) -> dict[AttributeType, dict[str, ExtractedAttribute]]:
        """Extract attributes for multiple arms - one attribute at a time for all arms.

        Args:
            arms: List of treatment arms
            attributes: List of attributes to extract
            context: Context chunks for extraction
            document_id: Document identifier

        Returns:
            Dictionary mapping attribute types to arm results
        """
        logger.info(
            f"Starting attribute-by-attribute extraction for {len(attributes)} attributes across {len(arms)} arms"
        )

        results = {}

        # Process ONE attribute at a time for ALL arms
        for attr_idx, attribute in enumerate(attributes):
            logger.info(
                f"Processing attribute {attr_idx + 1}/{len(attributes)}: {attribute.value}"
            )

            try:
                # Extract this single attribute for all arms
                attribute_results = await self._extract_single_attribute_for_all_arms(
                    arms, attribute, context, document_id
                )
                results[attribute] = attribute_results

                # Small delay between attributes to avoid rate limiting
                if attr_idx < len(attributes) - 1:
                    await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Failed to process attribute {attribute.value}: {e}")
                # Create "Not found" results for all arms for this attribute
                results[attribute] = self._create_not_found_results(
                    arms, attribute, context, document_id
                )
                continue

        logger.info(
            f"Attribute-by-attribute extraction completed: {len(results)} attribute types processed"
        )
        return results

    async def _extract_single_attribute_for_all_arms(
        self,
        arms: list[TreatmentArm],
        attribute: AttributeType,
        context: list[str],
        document_id: str,
    ) -> dict[str, ExtractedAttribute]:
        """Extract a single attribute for all arms in one LLM call.

        Args:
            arms: List of treatment arms
            attribute: Single attribute to extract
            context: Context chunks for extraction
            document_id: Document identifier

        Returns:
            Dictionary mapping arm IDs to extracted attribute results
        """
        # Create prompt for single attribute across all arms
        prompt = self._create_single_attribute_prompt(arms, attribute, context)

        # Call LLM once for this attribute across all arms
        response = await self._call_llm_with_retry(prompt)

        # Parse response to extract values for each arm
        return self._parse_single_attribute_response(
            response, arms, attribute, context, document_id
        )

    def _create_single_attribute_prompt(
        self,
        arms: list[TreatmentArm],
        attribute: AttributeType,
        context: list[str],
    ) -> str:
        """Create a prompt for extracting a single attribute across all arms.

        Args:
            arms: List of treatment arms
            attribute: Single attribute to extract
            context: Context chunks

        Returns:
            Formatted single attribute prompt
        """
        # Build arms information
        arms_info = []
        for i, arm in enumerate(arms):
            arm_info = f"Arm {i+1} ({arm.arm_id}): {arm.arm_name}"
            if arm.generic_name:
                arm_info += f" - Generic: {arm.generic_name}"
            if arm.dose:
                arm_info += f" - Dose: {arm.dose}"
            arms_info.append(arm_info)

        arms_text = "\n".join(arms_info)

        # Get the specific prompt for this attribute
        attr_name = attribute.value.replace("_", " ").title()
        base_prompt = self.prompt_provider.get_extraction_prompt(attribute, context)

        # Format context
        context_text = "\n\n".join(
            [f"Context {i+1}:\n{chunk}" for i, chunk in enumerate(context)]
        )

        # Create the single attribute prompt
        prompt = f"""TASK: Extract the {attr_name} for ALL treatment arms in this clinical trial.

TREATMENT ARMS:
{arms_text}

CRITICAL REQUIREMENTS:
1. Extract {attr_name} for EACH treatment arm separately
2. If {attr_name} is not found for a specific arm, use "Not found"
3. Return values in the exact JSON format specified below
4. Be precise and accurate - this is for clinical data analysis

{base_prompt}

CONTEXT:
{context_text}

OUTPUT FORMAT (JSON):
{{
  "arm_1": "value_for_arm_1",
  "arm_2": "value_for_arm_2",
  "arm_3": "value_for_arm_3"
}}

IMPORTANT: Return ONLY the JSON object, no additional text or explanation."""

        return prompt

    async def _call_llm_with_retry(self, prompt: str, max_retries: int = 3) -> str:
        """Call LLM with retry logic.

        Args:
            prompt: Prompt to send to LLM
            max_retries: Maximum number of retries

        Returns:
            LLM response
        """
        for attempt in range(max_retries):
            try:
                response = await self.llm_service.generate_response(prompt)
                return response.strip()
            except Exception as e:
                logger.warning(
                    f"LLM call failed (attempt {attempt + 1}/{max_retries}): {e}"
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)  # Exponential backoff
                else:
                    raise

        # This should never be reached, but satisfies type checker
        raise RuntimeError("LLM retry loop completed without returning or raising")

    def _parse_single_attribute_response(
        self,
        response: str,
        arms: list[TreatmentArm],
        attribute: AttributeType,
        context: list[str],
        document_id: str,
    ) -> dict[str, ExtractedAttribute]:
        """Parse single attribute LLM response to extract values for each arm.

        Args:
            response: LLM response
            arms: List of treatment arms
            attribute: Single attribute being extracted
            context: Context chunks
            document_id: Document identifier

        Returns:
            Dictionary mapping arm IDs to extracted attribute results
        """
        results = {}

        try:
            # Parse JSON response
            response_data = json.loads(response)

            # Extract values for each arm
            for i, arm in enumerate(arms):
                arm_key = f"arm_{i+1}"
                value = response_data.get(arm_key, "Not found")

                # Create ExtractedAttribute object
                extracted_attr = self._create_extracted_attribute(
                    attribute, value, context, document_id, arm
                )

                results[arm.arm_id] = extracted_attr

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response for {attribute.value}: {e}")
            logger.debug(f"Response was: {response}")

            # Fallback: create "Not found" results for all arms
            for arm in arms:
                extracted_attr = self._create_extracted_attribute(
                    attribute, "Not found", context, document_id, arm
                )
                results[arm.arm_id] = extracted_attr

        except Exception as e:
            logger.error(
                f"Failed to parse single attribute response for {attribute.value}: {e}"
            )

            # Fallback: create "Not found" results for all arms
            for arm in arms:
                extracted_attr = self._create_extracted_attribute(
                    attribute, "Not found", context, document_id, arm
                )
                results[arm.arm_id] = extracted_attr

        return results

    def _create_extracted_attribute(
        self,
        attribute_type: AttributeType,
        value: Any,
        context: list[str],
        document_id: str,
        arm: TreatmentArm,
    ) -> ExtractedAttribute:
        """Create an ExtractedAttribute object.

        Args:
            attribute_type: Type of attribute
            value: Extracted value
            context: Context chunks
            document_id: Document identifier
            arm: Treatment arm

        Returns:
            ExtractedAttribute object
        """
        # Clean up the value
        if value == "Not found" or value == "" or value is None:
            clean_value = "Not found"
            confidence = 0.0
        else:
            clean_value = str(value).strip()
            confidence = 0.8  # High confidence for batch extraction

        # Create source chunk IDs
        source_chunks = [f"chunk_{i}" for i in range(len(context))]

        # Create attribute data
        from datetime import datetime

        from src.domain.extraction_models import ValidationStatus

        return ExtractedAttribute(
            attribute_type=attribute_type,
            value=clean_value,
            confidence=confidence,
            source_chunks=source_chunks,
            validation_status=ValidationStatus.PENDING,
            validation_errors=[],
            extracted_at=datetime.now(),
        )

    def _create_not_found_results(
        self,
        arms: list[TreatmentArm],
        attribute: AttributeType,
        context: list[str],
        document_id: str,
    ) -> dict[str, ExtractedAttribute]:
        """Create "Not found" results for all arms for a failed attribute.

        Args:
            arms: List of treatment arms
            attribute: Attribute that failed to extract
            context: Context chunks
            document_id: Document identifier

        Returns:
            Dictionary mapping arm IDs to "Not found" results
        """
        results = {}
        for arm in arms:
            extracted_attr = self._create_extracted_attribute(
                attribute, "Not found", context, document_id, arm
            )
            results[arm.arm_id] = extracted_attr
        return results
