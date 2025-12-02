"""Attribute extractor implementation using LLM.

This module implements the attribute extraction logic using
the existing LLM service and prompt templates.
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import Any, Optional, Union

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..domain.extraction_interfaces import (
    AttributeExtractor,
    LLMService,
    PromptTemplateProvider,
)
from ..domain.extraction_models import (
    AttributeType,
    ExtractedAttribute,
)

logger = logging.getLogger(__name__)


def clean_numeric_value(value: Any, attribute_type: AttributeType) -> Any:
    """Clean numeric values by removing units, percentages, and other text.

    This function extracts pure numeric values from strings that may contain
    units like '%', 'months', 'years', etc.

    Args:
        value: The value to clean (can be string, int, float, or None)
        attribute_type: The type of attribute being cleaned

    Returns:
        Cleaned numeric value (float/int) or None if not numeric
    """
    if value is None or value == "" or value == "Not found":
        return None

    # Skip numeric cleaning for string-based attributes
    # These are non-numeric attributes extracted from abstracts
    string_attributes = [
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
        AttributeType.PUBLICATION_NAME,
        AttributeType.PUBLICATION_YEAR,
    ]
    if attribute_type in string_attributes:
        return None

    # If value is already a number, return it as-is (but convert to int if needed)
    if isinstance(value, (int, float)):
        if attribute_type == AttributeType.NUMBER_OF_PATIENTS:
            return int(value)
        return float(value)

    # Convert to string for processing
    value_str = str(value).strip()

    # Handle special cases first
    value_lower = value_str.lower()
    if value_lower in ["not reached", "not-reached", "not_reached", "nr"]:
        # For survival metrics, "NR" is a valid value
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
            return "NR"
        return None

    # Remove percentage signs
    value_str = value_str.replace("%", "").strip()

    # Check for time units that need conversion (for median survival metrics)
    # These attributes should always be in months
    survival_attributes = {
        AttributeType.MEDIAN_PFS,
        AttributeType.MEDIAN_OS,
        AttributeType.MEDIAN_DOR,
        AttributeType.MEDIAN_FOLLOWUP_PFS,
        AttributeType.MEDIAN_FOLLOWUP_OS,
        AttributeType.EFS,
        AttributeType.RFS,
        AttributeType.MFS,
        AttributeType.TTR,
        AttributeType.TTP,
        AttributeType.TTNT,
        AttributeType.TTF,
    }

    if attribute_type in survival_attributes:
        # Look for time units and convert to months
        value_str_lower = value_str.lower()

        # Weeks to months (divide by 4)
        if "week" in value_str_lower:
            time_units_pattern = r"\b(weeks?|wks?|w)\b"
            value_str = re.sub(
                time_units_pattern, "", value_str, flags=re.IGNORECASE
            ).strip()
            numeric_match = re.search(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", value_str)
            if numeric_match:
                try:
                    numeric_value = (
                        float(numeric_match.group(0)) / 4.0
                    )  # Convert weeks to months
                    return numeric_value
                except (ValueError, OverflowError):
                    pass

        # Days to months (divide by ~30.44, but let's use 30 for simplicity)
        elif "day" in value_str_lower:
            time_units_pattern = r"\b(days?|d)\b"
            value_str = re.sub(
                time_units_pattern, "", value_str, flags=re.IGNORECASE
            ).strip()
            numeric_match = re.search(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", value_str)
            if numeric_match:
                try:
                    numeric_value = (
                        float(numeric_match.group(0)) / 30.0
                    )  # Convert days to months
                    return numeric_value
                except (ValueError, OverflowError):
                    pass

        # Years to months (multiply by 12)
        elif "year" in value_str_lower:
            time_units_pattern = r"\b(years?|yrs?|y)\b"
            value_str = re.sub(
                time_units_pattern, "", value_str, flags=re.IGNORECASE
            ).strip()
            numeric_match = re.search(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", value_str)
            if numeric_match:
                try:
                    numeric_value = (
                        float(numeric_match.group(0)) * 12.0
                    )  # Convert years to months
                    return numeric_value
                except (ValueError, OverflowError):
                    pass

    # Remove common time units (months, years, days, weeks, hours) for non-survival attributes
    # Use word boundaries to avoid removing parts of words
    time_units_pattern = r"\b(months?|years?|days?|weeks?|hours?|mo|yr|d|w|h)\b"
    value_str = re.sub(time_units_pattern, "", value_str, flags=re.IGNORECASE).strip()

    # Remove other common units
    other_units_pattern = r"\b(mg|kg|ml|l|g|mg/kg|mg/m2|units?)\b"
    value_str = re.sub(other_units_pattern, "", value_str, flags=re.IGNORECASE).strip()

    # Remove common prefixes/suffixes
    value_str = re.sub(
        r"^[<>≤≥=]+", "", value_str
    ).strip()  # Remove comparison operators at start
    value_str = re.sub(
        r"[<>≤≥=]+$", "", value_str
    ).strip()  # Remove comparison operators at end

    # Extract numeric value (supports decimals, negative numbers, scientific notation)
    numeric_match = re.search(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", value_str)
    if numeric_match:
        try:
            numeric_value = float(numeric_match.group(0))
            # Convert to int if it's a whole number and attribute expects integer
            if attribute_type == AttributeType.NUMBER_OF_PATIENTS:
                return int(numeric_value)
            return numeric_value
        except (ValueError, OverflowError):
            pass

    # If no numeric value found, return None
    return None


class LLMAttributeExtractor(AttributeExtractor):
    """LLM-based attribute extractor implementation.

    This extractor uses the existing LLM service to extract attributes
    from context using specialized prompts.
    """

    def __init__(
        self, llm_service: LLMService, prompt_provider: "PromptTemplateProvider"
    ):
        """Initialize attribute extractor.

        Args:
            llm_service: LLM service for text generation
            prompt_provider: Provider for extraction prompts
        """
        self.llm_service = llm_service
        self.prompt_provider = prompt_provider

        # Regex patterns for validation and extraction
        self.patterns = {
            AttributeType.NCT_NUMBER: r"NCT\d{8}",
            AttributeType.OBJECTIVE_RESPONSE_RATE: r"(\d+(?:\.\d+)?)\s*%",
            AttributeType.GRADE_3_PLUS_AE: r"(\d+(?:\.\d+)?)\s*%",
            AttributeType.P_VALUE_OS: r"p\s*[=<>]\s*(\d+(?:\.\d+)?)",
        }

        # Clinical trial identifier patterns (priority order)
        self.trial_id_patterns = [
            (r"NCT\d{8}", "NCT"),  # NCT number (highest priority)
            (r"EudraCT[:\s]*(\d{4}-\d{6}-\d{2,3})", "EudraCT"),  # EudraCT format
            (r"EudraCT[:\s]*(\d+)", "EudraCT"),  # EudraCT simple format
        ]

        logger.info("LLM attribute extractor initialized")

    async def extract_attribute(
        self,
        attribute_type: AttributeType,
        context: list[str],
        document_id: str,
        arm_info: Optional[dict] = None,
    ) -> ExtractedAttribute:
        """Extract a specific attribute from context.

        Args:
            attribute_type: Type of attribute to extract
            context: List of context texts
            document_id: Document identifier
            arm_info: Optional arm information for context

        Returns:
            Extracted attribute with confidence score
        """
        try:
            logger.info(f"Starting extraction for {attribute_type}")

            # Get extraction prompt
            prompt = self.prompt_provider.get_extraction_prompt(attribute_type, context)

            # Add arm-specific context if available
            if arm_info:
                arm_context = "\n\nTREATMENT ARM CONTEXT:\n"
                arm_context += f"Arm ID: {arm_info.get('arm_id', 'Unknown')}\n"
                arm_context += f"Arm Name: {arm_info.get('arm_name', 'Unknown')}\n"
                arm_context += (
                    f"Generic Name: {arm_info.get('generic_name', 'Unknown')}\n"
                )
                if arm_info.get("dose"):
                    arm_context += f"Dose: {arm_info.get('dose')}\n"
                arm_context += f"\nIMPORTANT: Extract the {attribute_type.value} specifically for this treatment arm. "
                arm_context += f"Look for data related to {arm_info.get('generic_name', 'this arm')} and ignore data from other treatment arms.\n"
                prompt = prompt + arm_context

            # Add small delay to avoid rate limiting
            await asyncio.sleep(0.5)

            # Generate extraction using LLM (GPT-4o mini) with retry logic
            response = await self._call_llm_with_retry(prompt)

            # Parse and validate response
            extracted_value = self._parse_extraction_response(response, attribute_type)

            # For NCT_NUMBER, also try direct extraction from context if LLM failed
            if attribute_type == AttributeType.NCT_NUMBER and (
                not extracted_value
                or extracted_value == "Not found"
                or extracted_value == ""
            ):
                logger.debug(
                    "LLM extraction failed for NCT_NUMBER, trying direct extraction from context"
                )
                extracted_value = self._extract_trial_id_from_context(context)
                if extracted_value:
                    logger.info(
                        f"Successfully extracted trial ID directly from context: {extracted_value}"
                    )

            # Calculate confidence score
            confidence = self._calculate_extraction_confidence(
                extracted_value, context, attribute_type
            )

            # Create appropriate attribute model
            attribute = self._create_attribute_model(
                attribute_type, extracted_value, confidence, context, document_id
            )

            logger.info(
                f"Extracted {attribute_type}: {extracted_value} (confidence: {confidence:.3f})"
            )
            return attribute

        except Exception as e:
            logger.error(f"Failed to extract {attribute_type}: {e}")
            # Return empty attribute with low confidence
            return self._create_empty_attribute(attribute_type, context, document_id)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    )
    async def _call_llm_with_retry(self, prompt: str) -> str:
        """Call LLM with retry logic for handling temporary failures.

        Args:
            prompt: Input prompt for LLM

        Returns:
            LLM response text

        Raises:
            RuntimeError: If all retry attempts fail
        """
        try:
            # Use LLMService interface method
            return await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.1,
                max_tokens=500,
                model_name="gpt-4o",
            )
        except Exception as e:
            error_msg = str(e)
            logger.error(f"🔍 DEBUG: LLM call failed with error: {error_msg}")
            logger.error(f"🔍 DEBUG: Error type: {type(e).__name__}")

            # Check for quota exceeded error with more comprehensive detection
            quota_indicators = [
                "quota",
                "429",
                "exceeded",
                "billing",
                "payment",
                "rate limit",
            ]
            is_quota_error = any(
                indicator in error_msg.lower() for indicator in quota_indicators
            )

            if is_quota_error:
                logger.error(f"OpenAI quota exceeded, cannot retry: {e}")
                raise RuntimeError(f"OpenAI quota exceeded: {e}") from e
            else:
                logger.warning(f"LLM call failed, retrying: {e}")
                raise

    def _parse_extraction_response(
        self, response: str, attribute_type: AttributeType
    ) -> Any:
        """Parse LLM response to extract the attribute value.

        Args:
            response: LLM response text
            attribute_type: Type of attribute being extracted

        Returns:
            Parsed attribute value
        """
        try:
            # Clean response
            response = response.strip()

            # Handle different attribute types
            if attribute_type == AttributeType.ABSTRACT_NUMBER:
                return self._parse_abstract_number(response)
            elif attribute_type == AttributeType.NCT_NUMBER:
                return self._parse_nct_number(response)
            elif attribute_type == AttributeType.GENERIC_NAME:
                return self._parse_generic_name(response)
            elif attribute_type == AttributeType.P_VALUE_OS:
                return self._parse_p_value(response)
            elif attribute_type == AttributeType.OBJECTIVE_RESPONSE_RATE:
                return self._parse_percentage(response)
            elif attribute_type == AttributeType.GRADE_3_PLUS_AE:
                return self._parse_percentage(response)
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
                    AttributeType.PUBLICATION_NAME,
                    AttributeType.PUBLICATION_YEAR,
                ]

                # If it's a string-based attribute, return as-is without numeric cleaning
                if attribute_type in string_based_attributes or (
                    config and str(config.value_kind) == "STRING"
                ):
                    # Handle empty or invalid responses
                    if (
                        not response
                        or response.strip() == ""
                        or response.strip() == '""'
                        or response.strip() == "''"
                    ):
                        # For PUBLICATION_NAME and PUBLICATION_YEAR, return empty string when not found
                        if attribute_type in (
                            AttributeType.PUBLICATION_NAME,
                            AttributeType.PUBLICATION_YEAR,
                        ):
                            return ""
                        return "Not found"
                    # For PUBLICATION_NAME and PUBLICATION_YEAR, check if LLM explicitly said not found
                    response_lower = response.strip().lower()
                    if attribute_type in (
                        AttributeType.PUBLICATION_NAME,
                        AttributeType.PUBLICATION_YEAR,
                    ):
                        if any(
                            phrase in response_lower
                            for phrase in [
                                "not found",
                                "not available",
                                "not provided",
                                "not in the context",
                                "does not contain",
                                "cannot find",
                                "unable to find",
                                "no publication",
                            ]
                        ):
                            return ""
                    return response

                # For other numeric attributes, try to clean the value
                # Check if this is a numeric attribute by looking at common patterns
                cleaned_numeric = clean_numeric_value(response, attribute_type)
                if cleaned_numeric is not None:
                    return cleaned_numeric

                # Handle empty or invalid responses
                if (
                    not response
                    or response.strip() == ""
                    or response.strip() == '""'
                    or response.strip() == "''"
                ):
                    return "Not found"
                return response

        except Exception as e:
            logger.warning(f"Failed to parse response for {attribute_type}: {e}")
            return None

    def _parse_abstract_number(self, response: str) -> Optional[str]:
        """Parse abstract number from response.

        Returns the abstract number as a string (not float).
        """
        # Extract numeric value
        numeric_match = re.search(r"\d+", response)
        if numeric_match:
            # Return as string to avoid float conversion
            return numeric_match.group(0)

        # Check for empty string indication
        if (
            "not found" in response.lower()
            or "empty" in response.lower()
            or response.strip() == ""
        ):
            return "Not found"

        return None

    def _parse_nct_number(self, response: str) -> Optional[str]:
        """Parse clinical trial identifier from response.

        Priority: NCT number > EudraCT > Other identifiers
        """
        # Try each pattern in priority order
        for pattern, prefix in self.trial_id_patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                if prefix == "NCT":
                    return match.group(0)  # Full match for NCT
                elif prefix == "EudraCT":
                    # Format EudraCT properly
                    eudract_value = (
                        match.group(1) if match.lastindex else match.group(0)
                    )
                    # Clean up the value
                    eudract_value = re.sub(r"[^\d-]", "", eudract_value)
                    return f"EudraCT: {eudract_value}"

        # Fallback: Look for NCT pattern (original logic)
        nct_match = re.search(self.patterns[AttributeType.NCT_NUMBER], response)
        if nct_match:
            return nct_match.group(0)

        # Check if response is just digits (like "3086174" or "3086174.0")
        # Extract digits and format as NCT number
        # Handle decimal numbers by extracting integer part before decimal
        if "." in response:
            # Extract integer part before decimal (e.g., "3086174.0" -> "3086174")
            integer_part = response.split(".")[0]
            digits_match = re.search(r"\d+", integer_part)
        else:
            digits_match = re.search(r"\d+", response)

        if digits_match:
            digits = digits_match.group(0)
            # Pad to 8 digits if needed (e.g., "3086174" -> "03086174")
            if len(digits) == 7:
                digits = "0" + digits
            if len(digits) == 8:
                return f"NCT{digits}"

        # Check for empty string indication
        if (
            "not found" in response.lower()
            or "empty" in response.lower()
            or response.strip() == ""
        ):
            return "Not found"

        return None

    def _extract_trial_id_from_context(self, context: list[str]) -> Optional[str]:
        """Extract clinical trial identifier directly from context chunks.

        This is a fallback when LLM extraction fails. It searches through
        context chunks for trial identifiers in priority order.

        Args:
            context: List of context text chunks

        Returns:
            Trial identifier string or None
        """
        # Combine all context chunks
        combined_context = "\n".join(context)

        # Try each pattern in priority order
        for pattern, prefix in self.trial_id_patterns:
            match = re.search(pattern, combined_context, re.IGNORECASE)
            if match:
                if prefix == "NCT":
                    return match.group(0)  # Full match for NCT
                elif prefix == "EudraCT":
                    # Format EudraCT properly
                    eudract_value = (
                        match.group(1) if match.lastindex else match.group(0)
                    )
                    # Clean up the value - remove non-digit/non-dash characters
                    eudract_value = re.sub(r"[^\d-]", "", eudract_value)
                    return f"EudraCT: {eudract_value}"

        return None

    def _parse_generic_name(self, response: str) -> Optional[str]:
        """Parse generic drug name from response."""
        # Clean up response
        response = response.strip()

        # Check for empty string indication
        if (
            "not found" in response.lower()
            or "empty" in response.lower()
            or response.strip() == ""
        ):
            return "Not found"

        # Return the response as-is (should be drug name)
        return response if response else "Not found"

    def _parse_p_value(self, response: str) -> Optional[Union[float, str]]:
        """Parse p-value from response."""
        # Look for numeric p-value
        p_match = re.search(
            self.patterns[AttributeType.P_VALUE_OS], response, re.IGNORECASE
        )
        if p_match:
            try:
                p_value = float(p_match.group(1))
                if 0 <= p_value <= 1:
                    return p_value
            except ValueError:
                pass

        # Check for significance levels
        response_lower = response.lower()
        if "non-significant" in response_lower or "non significant" in response_lower:
            return "Non-Significant"
        elif "significant" in response_lower and "highly" in response_lower:
            return "Highly Significant"
        elif "significant" in response_lower:
            return "Significant"

        # Check for empty string indication
        if (
            "not found" in response_lower
            or "empty" in response_lower
            or response.strip() == ""
        ):
            return "Not found"

        return None

    def _parse_percentage(self, response: str) -> Optional[float]:
        """Parse percentage value from response."""
        # First try to clean the response using the utility function
        cleaned_value = clean_numeric_value(
            response, AttributeType.OBJECTIVE_RESPONSE_RATE
        )
        if cleaned_value is not None:
            if isinstance(cleaned_value, (int, float)) and 0 <= cleaned_value <= 100:
                return float(cleaned_value)

        # Fallback: Look for percentage pattern
        percent_match = re.search(r"(\d+(?:\.\d+)?)", response)
        if percent_match:
            try:
                value = float(percent_match.group(1))
                if 0 <= value <= 100:
                    return value
            except ValueError:
                pass

        # Check for empty string indication
        if (
            "not found" in response.lower()
            or "empty" in response.lower()
            or response.strip() == ""
        ):
            return None

        return None

    def _calculate_extraction_confidence(
        self, extracted_value: Any, context: list[str], attribute_type: AttributeType
    ) -> float:
        """Calculate confidence score for extraction.

        Args:
            extracted_value: Extracted attribute value
            context: Context chunks used for extraction
            attribute_type: Type of attribute

        Returns:
            Confidence score between 0 and 1
        """
        if extracted_value is None or extracted_value == "":
            return 0.0

        # Base confidence from context quality
        context_confidence = min(
            1.0, len(context) / 5.0
        )  # More context = higher confidence

        # Pattern matching confidence
        pattern_confidence = 0.0
        if attribute_type in self.patterns:
            pattern = self.patterns[attribute_type]
            # Handle both string and ChunkWithEmbedding objects
            context_texts = []
            for chunk in context:
                if hasattr(chunk, "content"):
                    context_texts.append(chunk.content)
                else:
                    context_texts.append(str(chunk))
            context_text = " ".join(context_texts)
            if re.search(pattern, context_text, re.IGNORECASE):
                pattern_confidence = 0.3

        # Value validation confidence
        validation_confidence = 0.0
        if self._validate_extracted_value(extracted_value, attribute_type):
            validation_confidence = 0.4

        # Combine confidences
        total_confidence = (
            context_confidence + pattern_confidence + validation_confidence
        )
        return min(1.0, total_confidence)

    def _validate_extracted_value(
        self, value: Any, attribute_type: AttributeType
    ) -> bool:
        """Validate extracted value based on attribute type.

        Args:
            value: Extracted value
            attribute_type: Type of attribute

        Returns:
            True if value is valid
        """
        if value is None or value == "":
            return True  # Empty is valid

        try:
            if attribute_type == AttributeType.NCT_NUMBER:
                return isinstance(value, str) and bool(re.match(r"NCT\d{8}", value))
            elif attribute_type == AttributeType.GENERIC_NAME:
                return isinstance(value, str) and len(value.strip()) > 0
            elif attribute_type == AttributeType.P_VALUE_OS:
                if isinstance(value, str):
                    return value in [
                        "Non-Significant",
                        "Significant",
                        "Highly Significant",
                    ]
                else:
                    return isinstance(value, (int, float)) and 0 <= value <= 1
            elif attribute_type in [
                AttributeType.OBJECTIVE_RESPONSE_RATE,
                AttributeType.GRADE_3_PLUS_AE,
            ]:
                return isinstance(value, (int, float)) and 0 <= value <= 100
            else:
                return True
        except Exception:
            return False

    def _create_attribute_model(
        self,
        attribute_type: AttributeType,
        value: Any,
        confidence: float,
        context: list[str],
        document_id: str,
    ) -> ExtractedAttribute:
        """Create appropriate attribute model based on type.

        Args:
            attribute_type: Type of attribute
            value: Extracted value
            confidence: Confidence score
            context: Context chunks
            document_id: Document identifier

        Returns:
            Appropriate attribute model
        """
        # Create source chunk IDs (simplified for now)
        source_chunks = [f"chunk_{i}" for i in range(len(context))]

        # Create base attribute data
        attribute_data = {
            "attribute_type": attribute_type,
            "value": value,
            "confidence": confidence,
            "source": "abstract_extraction",
            "source_chunks": source_chunks,
            "validation_status": "pending",
            "validation_errors": [],
            "extracted_at": datetime.now(),
        }

        # Return simple ExtractedAttribute model
        return ExtractedAttribute(**attribute_data)

    def _create_empty_attribute(
        self, attribute_type: AttributeType, context: list[str], document_id: str
    ) -> ExtractedAttribute:
        """Create empty attribute when extraction fails.

        Args:
            attribute_type: Type of attribute
            context: Context chunks
            document_id: Document identifier

        Returns:
            Empty attribute with low confidence
        """
        return self._create_attribute_model(
            attribute_type=attribute_type,
            value=None,
            confidence=0.0,
            context=context,
            document_id=document_id,
        )
