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
from .attribute_extractor import clean_numeric_value
from .cost_tracking_llm_service import CostTrackingLLMService
from .prompt_templates import ExtractionPromptTemplateProvider

logger = logging.getLogger(__name__)


class BatchAttributeExtractor:
    """Extracts attributes for multiple treatment arms in batch operations."""

    def __init__(
        self,
        llm_service: CostTrackingLLMService,
        prompt_provider: ExtractionPromptTemplateProvider,
        preferred_model: str = "gpt-4o",
    ):
        """Initialize batch attribute extractor.

        Args:
            llm_service: LLM service with cost tracking
            prompt_provider: Prompt template provider
            preferred_model: Preferred LLM model ("gpt-4o" or "gpt-4o-mini")
        """
        self.llm_service = llm_service
        self.prompt_provider = prompt_provider
        self.preferred_model = preferred_model

        # Rate limiting state
        self.request_count = 0
        self.last_request_time = 0
        self.rate_limit_window = 60  # 1 minute window

        # Model-specific rate limits (requests per minute)
        self.rate_limits = {
            "gpt-4o": 15,  # Conservative for GPT-4o (10-15 RPM)
            "gpt-4o-mini": 500,  # Much higher for GPT-4o-mini (500+ RPM)
        }
        self.current_model = preferred_model  # Track which model we're using
        logger.info(
            f"Batch attribute extractor initialized with preferred model: {preferred_model}"
        )

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
            progress = (attr_idx + 1) / len(attributes) * 100
            logger.info(
                f"Processing attribute {attr_idx + 1}/{len(attributes)} ({progress:.1f}%): {attribute.value}"
            )

            # Smart rate limiting - check if we need to wait
            await self._handle_rate_limiting()

            try:
                # Extract this single attribute for all arms
                attribute_results = await self._extract_single_attribute_for_all_arms(
                    arms, attribute, context, document_id
                )
                results[attribute] = attribute_results

                # Small delay between attributes to avoid rate limiting (only for GPT-4o)
                if attr_idx < len(attributes) - 1 and self.current_model == "gpt-4o":
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

        # Get the base prompt (attribute-specific instruction) without context
        # We'll add context separately in the wrapper
        if attribute in self.prompt_provider.extraction_prompts:
            base_instruction = self.prompt_provider.extraction_prompts[attribute]
        else:
            base_instruction = self.prompt_provider._get_dynamic_prompt(attribute)

        # Add arm-specific verification if needed
        if self.prompt_provider._needs_arm_specific_verification(attribute):
            base_instruction = (
                self.prompt_provider.arm_specific_verification_prefix + base_instruction
            )

        # Format context
        context_text = self.prompt_provider._format_context(context)

        # Get attribute name for display
        attr_name = attribute.value.replace("_", " ").upper()

        # Detect if this might be a single-arm study (only one arm or arms have same treatment)
        is_likely_single_arm = len(arms) == 1 or (
            len(arms) > 1
            and all(
                arm.generic_name == arms[0].generic_name and arm.dose == arms[0].dose
                for arm in arms
            )
        )

        single_arm_note = ""
        if is_likely_single_arm and attribute == AttributeType.NUMBER_OF_PATIENTS:
            single_arm_note = "\nNOTE: This appears to be a single-arm study. If you find only one total patient count (e.g., 'n=60', '60 patients'), use that same value for all arms listed above.\n"

        # Create the simplified single attribute prompt
        prompt = f"""TASK: Extract the {attr_name} for ALL treatment arms in this clinical trial.

TREATMENT ARMS:
{arms_text}{single_arm_note}

INSTRUCTIONS:
1. For each arm, extract the {attr_name} from the context.
2. If an arm-specific value is not found, return 'Not found' for that arm.
3. Use keywords or association with arm names when searching context.
4. Return results in this JSON format:

{{
  "arm_1": "value_for_arm_1",
  "arm_2": "value_for_arm_2",
  "arm_3": "value_for_arm_3"
}}

Attribute-Specific Example: {attr_name}

{base_instruction}

CONTEXT:
{context_text}"""

        return prompt

    async def _call_llm_with_retry(self, prompt: str, max_retries: int = 5) -> str:
        """Call LLM with retry logic.

        Args:
            prompt: Prompt to send to LLM
            max_retries: Maximum number of retries

        Returns:
            LLM response
        """
        for attempt in range(max_retries):
            try:
                # Try preferred model first, fallback to alternative on rate limits
                if attempt < 2:
                    model_name = self.preferred_model
                else:
                    # Fallback to alternative model
                    model_name = (
                        "gpt-4o-mini" if self.preferred_model == "gpt-4o" else "gpt-4o"
                    )

                response = await self.llm_service.generate_response(
                    prompt, model_name=model_name
                )

                # Track successful model for rate limiting
                if self.current_model != model_name:
                    logger.info(f"Switched to {model_name} for subsequent requests")
                    self.current_model = model_name
                    # Reset rate limiting when switching models
                    self.request_count = 0
                    self.last_request_time = 0

                return response.strip()
            except Exception as e:
                error_str = str(e)
                logger.warning(
                    f"LLM call failed (attempt {attempt + 1}/{max_retries}): {e}"
                )

                # Check if it's a rate limit error
                if "rate_limit_exceeded" in error_str or "429" in error_str:
                    # Extract wait time from error message if available
                    wait_time = self._extract_wait_time_from_error(error_str)
                    if wait_time and wait_time > 0:
                        logger.info(f"Rate limit hit, waiting {wait_time} seconds...")
                        await asyncio.sleep(wait_time)
                    else:
                        # Smart backoff: longer delays for rate limits
                        wait_time = min(
                            60, (2**attempt) * 5
                        )  # 5, 10, 20, 40, 60 seconds
                        logger.info(f"Rate limit hit, waiting {wait_time} seconds...")
                        await asyncio.sleep(wait_time)

                    # If we've tried GPT-4o multiple times, switch to GPT-4o-mini
                    if attempt >= 2:
                        logger.info(
                            "Switching to GPT-4o-mini due to persistent rate limits"
                        )
                else:
                    # Regular exponential backoff for other errors
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2**attempt)
                    else:
                        raise

                if attempt == max_retries - 1:
                    raise

        # This should never be reached, but satisfies type checker
        raise RuntimeError("LLM retry loop completed without returning or raising")

    def _extract_json_from_response(self, response: str) -> str:
        """Extract JSON from LLM response that might contain extra text.

        Args:
            response: Raw LLM response

        Returns:
            Cleaned JSON string
        """
        import re

        # Remove leading/trailing whitespace
        response = response.strip()

        # Try to find JSON object in the response
        # Look for patterns like { ... } or ```json { ... } ```

        # First, try to find JSON wrapped in code blocks
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
        if json_match:
            return json_match.group(1).strip()

        # Try to find JSON object directly
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            return json_match.group(0).strip()

        # If no JSON found, return original response
        return response

    def _extract_wait_time_from_error(self, error_str: str) -> int:
        """Extract wait time from rate limit error message.

        Args:
            error_str: Error message string

        Returns:
            Wait time in seconds, or 0 if not found
        """
        import re

        # Look for patterns like "Please try again in 1.39s" or "try again in 668ms"
        time_match = re.search(r"try again in ([\d.]+)([sm])", error_str)
        if time_match:
            value = float(time_match.group(1))
            unit = time_match.group(2)
            if unit == "s":
                return int(value) + 1  # Add 1 second buffer
            elif unit == "m":
                return int(value * 60) + 1  # Convert to seconds + buffer

        return 0

    async def _handle_rate_limiting(self):
        """Handle rate limiting with model-specific limits."""
        import time

        current_time = time.time()

        # Get model-specific rate limit
        max_requests = self.rate_limits.get(self.current_model, 15)

        # Reset counter if we're in a new minute
        if current_time - self.last_request_time > self.rate_limit_window:
            self.request_count = 0
            self.last_request_time = current_time

        # If we're approaching the rate limit, wait
        if self.request_count >= max_requests:
            wait_time = self.rate_limit_window - (current_time - self.last_request_time)
            if wait_time > 0:
                logger.info(
                    f"Rate limit approaching for {self.current_model} ({max_requests} RPM), waiting {wait_time:.1f} seconds..."
                )
                await asyncio.sleep(wait_time)
                # Reset after waiting
                self.request_count = 0
                self.last_request_time = time.time()

        # Increment request count
        self.request_count += 1

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
        cleaned_response = response  # Initialize for error handling

        try:
            # Clean response - extract JSON from response if it contains extra text
            cleaned_response = self._extract_json_from_response(response)

            # Parse JSON response
            response_data = json.loads(cleaned_response)

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
            logger.error(f"Cleaned response was: {repr(cleaned_response)}")
            logger.error(f"Original response was: {repr(response)}")

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
            # Special handling for ABSTRACT_NUMBER - should be string or integer, not float
            if attribute_type == AttributeType.ABSTRACT_NUMBER:
                if isinstance(value, (int, float)):
                    # Convert to int first, then to string to avoid .0
                    clean_value = str(int(float(value)))
                else:
                    # Extract numeric part from string if present
                    import re
                    numeric_match = re.search(r'\d+', str(value))
                    if numeric_match:
                        clean_value = numeric_match.group(0)
                    else:
                        clean_value = str(value).strip()
                confidence = 0.8
            # Special handling for NCT_NUMBER - supports NCT, EudraCT, and other identifiers
            elif attribute_type == AttributeType.NCT_NUMBER:
                import re
                value_str = str(value).strip()
                
                # Trial identifier patterns (priority order)
                trial_id_patterns = [
                    (r"NCT\d{8}", "NCT"),  # NCT number (highest priority)
                    (r"EudraCT[:\s]*(\d{4}-\d{6}-\d{2,3})", "EudraCT"),  # EudraCT format
                    (r"EudraCT[:\s]*(\d+)", "EudraCT"),  # EudraCT simple format
                ]
                
                # Try each pattern in priority order
                found_match = False
                for pattern, prefix in trial_id_patterns:
                    match = re.search(pattern, value_str, re.IGNORECASE)
                    if match:
                        if prefix == "NCT":
                            clean_value = match.group(0)  # Full match for NCT
                            found_match = True
                            break
                        elif prefix == "EudraCT":
                            # Format EudraCT properly
                            eudract_value = match.group(1) if match.lastindex else match.group(0)
                            # Clean up the value - remove non-digit/non-dash characters
                            eudract_value = re.sub(r'[^\d-]', '', eudract_value)
                            clean_value = f"EudraCT: {eudract_value}"
                            found_match = True
                            break
                
                if not found_match:
                    # If it's already in correct format, use it
                    if re.match(r'^NCT\d{8}$', value_str):
                        clean_value = value_str
                    else:
                        # Try to extract NCT number from the value
                        nct_match = re.search(r'NCT\d{8}', value_str)
                        if nct_match:
                            clean_value = nct_match.group(0)
                        else:
                            # If it's just digits (like 3086174.0), convert to NCT format
                            # Extract just the digits
                            digits_match = re.search(r'\d+', value_str.replace('.', ''))
                            if digits_match:
                                digits = digits_match.group(0)
                                # Pad to 8 digits if needed
                                if len(digits) == 7:
                                    digits = '0' + digits
                                if len(digits) == 8:
                                    clean_value = f"NCT{digits}"
                                else:
                                    clean_value = value_str
                            else:
                                clean_value = value_str
                confidence = 0.8
            else:
                # Check if this is a string-based attribute that should not be cleaned as numeric
                # These are non-numeric attributes extracted from abstracts
                from ..domain.extraction_models import AttributeConfigurationFactory
                config = AttributeConfigurationFactory.get_configuration(attribute_type)
                string_based_attributes = [
                    AttributeType.ABSTRACT_NUMBER,
                    AttributeType.COMMENTS,
                    AttributeType.NCT_NUMBER,
                    AttributeType.CANCER_TYPE,
                    AttributeType.CANCER_STAGE,
                    AttributeType.SPONSORS,
                    AttributeType.BRAND_NAME,
                    AttributeType.GENERIC_NAME,
                    AttributeType.TYPE_OF_THERAPY,
                    AttributeType.MECHANISM_OF_ACTION,
                    AttributeType.TARGET_PROTEIN,
                    AttributeType.BIOSIMILAR,
                    AttributeType.SUB_THERAPY,
                    AttributeType.TRIAL_NAME,
                    AttributeType.PRIMARY_ENDPOINT,
                    AttributeType.SECONDARY_ENDPOINT,
                ]
                
                # If it's a string-based attribute, return as-is without numeric cleaning
                if attribute_type in string_based_attributes or (config and str(config.value_kind) == "STRING"):
                    clean_value = str(value).strip()
                    confidence = 0.8
                else:
                    # First, try to clean numeric values (removes %, months, years, etc.)
                    cleaned_numeric = clean_numeric_value(value, attribute_type)
                    if cleaned_numeric is not None:
                        # Successfully extracted a numeric value
                        clean_value = cleaned_numeric
                        confidence = 0.8  # High confidence for batch extraction
                    else:
                        # Not a numeric value, process as string
                        clean_value = str(value).strip()

                    # Normalize "not reached" variations to "NR" for median survival metrics
                    # These are valid values that should be extracted, not treated as "Not found"
                    if attribute_type in [
                        AttributeType.MEDIAN_PFS,
                        AttributeType.MEDIAN_OS,
                        AttributeType.MEDIAN_DOR,
                        AttributeType.EFS,
                        AttributeType.RFS,
                        AttributeType.MFS,
                        AttributeType.TTR,
                        AttributeType.TTP,
                        AttributeType.TTNT,
                        AttributeType.TTF,
                    ]:
                        # Normalize variations of "not reached" to "NR"
                        clean_value_lower = clean_value.lower()
                        if clean_value_lower in [
                            "not reached",
                            "not-reached",
                            "not_reached",
                            "nr",
                        ]:
                            clean_value = "NR"

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
