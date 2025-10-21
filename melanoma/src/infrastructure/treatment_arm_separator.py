"""Treatment arm separator implementation.

This module implements the treatment arm separation logic using LLM
to identify and separate treatment arms from clinical trial abstracts.
"""

import logging
import re
from datetime import datetime
from typing import Any

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..domain.extraction_interfaces import LLMService
from ..domain.treatment_arm_models import (
    ArmType,
    LineOfTreatment,
    TreatmentArm,
    TreatmentArmSeparationResult,
)

logger = logging.getLogger(__name__)


class TreatmentArmSeparator:
    """LLM-based treatment arm separator.

    This service uses LLM to identify and separate treatment arms
    from clinical trial abstracts, providing structured output
    for downstream processing.
    """

    def __init__(self, llm_service: LLMService):
        """Initialize treatment arm separator.

        Args:
            llm_service: LLM service for text generation
        """
        self.llm_service = llm_service

        # Treatment arm separation prompt
        self.separation_prompt = self._create_separation_prompt()

        logger.info("Treatment arm separator initialized")

    async def separate_treatment_arms(
        self, abstract_text: str, abstract_id: str
    ) -> TreatmentArmSeparationResult:
        """Separate treatment arms from abstract text.

        Args:
            abstract_text: Full abstract text
            abstract_id: Abstract identifier

        Returns:
            Treatment arm separation result
        """
        start_time = datetime.now()

        try:
            logger.info(f"Starting treatment arm separation for abstract {abstract_id}")

            # Create separation prompt with abstract text
            prompt = self._format_separation_prompt(abstract_text)

            # Call LLM with retry logic
            response = await self._call_llm_with_retry(prompt)
            logger.debug(
                f"LLM separation raw response (first 500 chars): {(response or '')[:500]}"
            )

            # Parse LLM response
            treatment_arms = self._parse_arm_separation_response(response)

            # Validate separation results
            validation_result = self._validate_arm_separation(treatment_arms)

            # Calculate processing time
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

            # Create result
            result = TreatmentArmSeparationResult(
                abstract_id=abstract_id,
                treatment_arms=treatment_arms,
                separation_confidence=validation_result["confidence"],
                processing_time_ms=processing_time,
                errors=validation_result["errors"],
                warnings=validation_result["warnings"],
            )

            logger.info(
                f"Treatment arm separation completed: {len(treatment_arms)} arms identified"
            )
            return result

        except Exception as e:
            logger.error(f"Treatment arm separation failed: {e}")
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

            return TreatmentArmSeparationResult(
                abstract_id=abstract_id,
                treatment_arms=[],
                separation_confidence=0.0,
                processing_time_ms=processing_time,
                errors=[f"Separation failed: {str(e)}"],
            )

    def _create_separation_prompt(self) -> str:
        """Create the treatment arm separation prompt."""
        return """
TASK: Identify the main treatment arms from this clinical trial abstract.

CRITICAL REQUIREMENTS:
1. Focus on PRIMARY treatment arms only (typically 1-3 arms)
2. Each arm must have distinct treatment regimens
3. Different doses of the same drug are separate arms ONLY if explicitly compared
4. Combination therapies are single arms with "+" notation
5. Be conservative - avoid over-segmentation

TREATMENT ARM RULES:
- Single drug: "Drug Name" (e.g., "Nivolumab")
- Combination: "Drug A + Drug B" (e.g., "Nivolumab + Ipilimumab")
- Placebo/Control: Mark as control arm with generic_name="Placebo"
- Different doses: Only if explicitly mentioned as separate comparison groups

CONSERVATIVE APPROACH:
- Most clinical trials have 2-3 arms maximum
- If unsure, err on the side of fewer arms
- Focus on the main treatment comparison
- Avoid creating arms for adjuvant therapies, supportive care, or exploratory treatments

OUTPUT FORMAT (JSON):
{
  "treatment_arms": [
    {
      "arm_id": "arm_1",
      "arm_name": "Treatment Name",
      "generic_name": "Drug Name",
      "brand_name": "",
      "dose": "Dose if specified",
      "dosing_schedule": "Schedule if specified",
      "patient_count": 0,
      "line_of_treatment": "first_line",
      "arm_type": "monotherapy",
      "combination_drugs": [],
      "confidence_score": 0.95,
      "source_text": "Relevant text from abstract",
      "nct_number": ""
    }
  ]
}

ABSTRACT TEXT:
{abstract_text}

STRICT RESPONSE RULES:
- Return ONLY valid JSON
- Maximum 3 arms (most trials have 1-2)
- Focus on primary treatment comparisons
- Do NOT include explanations or markdown
- Each arm must have distinct treatment regimen
"""

    def _format_separation_prompt(self, abstract_text: str) -> str:
        """Format the separation prompt with abstract text.

        Avoid str.format to prevent accidental interpolation of JSON braces
        in the template by using a simple string replacement for the
        {abstract_text} placeholder only.
        """
        return self.separation_prompt.replace("{abstract_text}", abstract_text)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    )
    async def _call_llm_with_retry(self, prompt: str) -> str:
        """Call LLM with retry logic for handling temporary failures."""
        try:
            # Use the LLMService interface method
            return await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.1,
                max_tokens=2000,
                model_name="gpt-4o-mini",
            )
        except Exception as e:
            error_msg = str(e)
            logger.error(f"LLM call failed: {error_msg}")

            # Check for quota exceeded error
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
                logger.error(f"OpenAI quota exceeded: {e}")
                raise RuntimeError(f"OpenAI quota exceeded: {e}") from e
            else:
                logger.warning(f"LLM call failed, retrying: {e}")
                raise

    def _parse_arm_separation_response(self, response: str) -> list[TreatmentArm]:
        """Parse LLM response to extract treatment arms."""
        try:
            import json

            raw_response = (response or "").strip()
            logger.debug(
                f"Parsing LLM response (first 500 chars): {raw_response[:500]}"
            )

            # 1) Strip common markdown code fences, optional json tag
            code_fence_match = re.search(
                r"```(?:json)?\s*([\s\S]*?)```", raw_response, re.IGNORECASE
            )
            if code_fence_match:
                candidate = code_fence_match.group(1).strip()
            else:
                candidate = raw_response

            # 2) Extract the largest JSON object substring if extra text surrounds it
            obj_match = re.search(r"\{[\s\S]*\}", candidate)
            json_str = obj_match.group(0) if obj_match else candidate

            # 3) Try strict parse first
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                # 3a) Heuristic: try to extract the treatment_arms array and wrap
                arms_match = re.search(
                    r'"treatment_arms"\s*:\s*\[(?:[\s\S]*?)\]', json_str
                )
                if arms_match:
                    fixed = "{" + arms_match.group(0) + "}"
                    data = json.loads(fixed)
                else:
                    # 3b) Remove trailing commas before closing braces/brackets and retry
                    tmp = re.sub(r",\s*([}\]])", r"\1", json_str)
                    data = json.loads(tmp)

            # Normalize to find treatment_arms regardless of shape
            treatment_arms = []
            arms_data = []

            def find_arms(obj):
                if isinstance(obj, dict):
                    if "treatment_arms" in obj and isinstance(
                        obj["treatment_arms"], list
                    ):
                        return obj["treatment_arms"]
                    # search shallow children
                    for v in obj.values():
                        found = find_arms(v)
                        if found is not None:
                            return found
                elif isinstance(obj, list):
                    # Some models return a list of arms directly
                    if (
                        obj
                        and isinstance(obj[0], dict)
                        and ("arm_name" in obj[0] or "generic_name" in obj[0])
                    ):
                        return obj
                return None

            candidate_arms = find_arms(data)
            if isinstance(candidate_arms, list):
                arms_data = candidate_arms
            else:
                logger.warning(
                    "No 'treatment_arms' key found in LLM response after normalization"
                )
                arms_data = []

            # Normalization helpers
            lot_map = {
                "neoadjuvant": "first_line",
                "adjuvant": "first_line",
                "first line": "first_line",
                "second line": "second_line",
                "third line+": "third_line",
            }

            for i, arm_data in enumerate(arms_data):
                try:
                    # Normalize line_of_treatment before enum conversion
                    raw_lot = arm_data.get("line_of_treatment", "unknown")
                    if isinstance(raw_lot, str):
                        normalized_lot = lot_map.get(raw_lot.strip().lower(), raw_lot)
                    else:
                        normalized_lot = raw_lot

                    # Skip arms with empty generic names (except placebo/control arms)
                    generic_name = arm_data.get("generic_name", "").strip()
                    arm_type = arm_data.get("arm_type", "").strip().lower()

                    # Allow placebo and control arms even with empty generic names
                    if not generic_name and arm_type not in ["placebo", "control"]:
                        logger.warning(f"Skipping arm {i+1} due to empty generic name")
                        continue

                    # Set generic name for placebo/control arms if empty
                    if not generic_name and arm_type in ["placebo", "control"]:
                        generic_name = "Placebo" if arm_type == "placebo" else "Control"
                        logger.info(
                            f"Setting generic name to '{generic_name}' for {arm_type} arm"
                        )

                    # Create treatment arm
                    arm = TreatmentArm(
                        arm_id=arm_data.get("arm_id", f"arm_{i+1}"),
                        arm_name=arm_data.get("arm_name", ""),
                        generic_name=generic_name,
                        brand_name=arm_data.get("brand_name"),
                        dose=arm_data.get("dose"),
                        dosing_schedule=arm_data.get("dosing_schedule"),
                        patient_count=arm_data.get("patient_count"),
                        line_of_treatment=LineOfTreatment(normalized_lot),
                        arm_type=ArmType(arm_data.get("arm_type", "unknown")),
                        combination_drugs=arm_data.get("combination_drugs", []),
                        confidence_score=arm_data.get("confidence_score", 0.0),
                        source_text=arm_data.get("source_text"),
                        arm_metadata={
                            "nct_number": arm_data.get("nct_number"),
                            "generic_name": arm_data.get("generic_name", ""),
                            "raw_arm_data": arm_data,  # Store raw data for debugging
                        },
                    )
                    treatment_arms.append(arm)

                except Exception as e:
                    logger.warning(f"Failed to parse arm {i+1}: {e}")
                    continue

            return treatment_arms

        except Exception as e:
            logger.exception(f"Failed to parse arm separation response: {e}")
            return []

    def _validate_arm_separation(
        self, treatment_arms: list[TreatmentArm]
    ) -> dict[str, Any]:
        """Validate treatment arm separation results."""
        validation_result = {"confidence": 0.0, "errors": [], "warnings": []}

        if not treatment_arms:
            validation_result["errors"].append("No treatment arms identified")
            return validation_result

        # CRITICAL: Limit number of arms to prevent over-segmentation
        max_arms = 3
        if len(treatment_arms) > max_arms:
            validation_result["warnings"].append(
                f"Too many arms identified ({len(treatment_arms)}), limiting to {max_arms} "
                f"highest confidence arms"
            )
            # Sort by confidence score and keep only the top 3
            treatment_arms.sort(key=lambda x: x.confidence_score, reverse=True)
            treatment_arms = treatment_arms[:max_arms]

        # Calculate confidence based on various factors
        confidence_factors = []

        # Factor 1: Number of arms (expect 1-3 arms typically, max 3)
        arm_count = len(treatment_arms)
        if arm_count == 0:
            confidence_factors.append(0.0)
        elif 1 <= arm_count <= 2:
            confidence_factors.append(0.9)  # Most trials have 1-2 arms
        elif arm_count == 3:
            confidence_factors.append(0.8)  # 3 arms is acceptable but less common
        else:
            # More than 3 arms - likely over-segmentation
            confidence_factors.append(0.3)
            validation_result["warnings"].append(
                f"Too many arms identified ({arm_count}), likely over-segmentation. "
                f"Most clinical trials have 1-3 arms maximum."
            )

        # Factor 2: Arm completeness
        complete_arms = 0
        for arm in treatment_arms:
            if arm.generic_name and arm.arm_name:
                complete_arms += 1

        completeness_score = (
            complete_arms / len(treatment_arms) if treatment_arms else 0
        )
        confidence_factors.append(completeness_score)

        # Factor 3: Confidence scores from LLM
        if treatment_arms:
            avg_arm_confidence = sum(
                arm.confidence_score for arm in treatment_arms
            ) / len(treatment_arms)
            confidence_factors.append(avg_arm_confidence)

        # Factor 4: Check for duplicate arms
        arm_names = [arm.arm_name for arm in treatment_arms]
        if len(arm_names) != len(set(arm_names)):
            validation_result["warnings"].append("Duplicate arm names detected")
            confidence_factors.append(0.5)
        else:
            confidence_factors.append(0.9)

        # Calculate overall confidence
        validation_result["confidence"] = sum(confidence_factors) / len(
            confidence_factors
        )

        # Add specific validation errors
        for arm in treatment_arms:
            if not arm.generic_name:
                validation_result["errors"].append(
                    f"Arm {arm.arm_id} missing generic name"
                )
            if not arm.arm_name:
                validation_result["errors"].append(f"Arm {arm.arm_id} missing arm name")

        return validation_result

    async def validate_arm_separation_quality(
        self, separation_result: TreatmentArmSeparationResult
    ) -> dict[str, Any]:
        """Validate the quality of treatment arm separation.

        Args:
            separation_result: Treatment arm separation result

        Returns:
            Quality validation results
        """
        quality_assessment = {
            "is_valid": True,
            "quality_score": 0.0,
            "issues": [],
            "recommendations": [],
        }

        # Check basic validity
        if not separation_result.treatment_arms:
            quality_assessment["is_valid"] = False
            quality_assessment["issues"].append("No treatment arms identified")
            return quality_assessment

        # Calculate quality score
        quality_factors = []

        # Factor 1: Separation confidence
        quality_factors.append(separation_result.separation_confidence)

        # Factor 2: Arm completeness
        complete_arms = 0
        for arm in separation_result.treatment_arms:
            if arm.generic_name and arm.arm_name and arm.patient_count:
                complete_arms += 1

        completeness_score = complete_arms / len(separation_result.treatment_arms)
        quality_factors.append(completeness_score)

        # Factor 3: Arm diversity (avoid duplicates)
        arm_names = [arm.arm_name for arm in separation_result.treatment_arms]
        diversity_score = len(set(arm_names)) / len(arm_names) if arm_names else 0
        quality_factors.append(diversity_score)

        # Calculate overall quality score
        quality_assessment["quality_score"] = sum(quality_factors) / len(
            quality_factors
        )

        # Add quality issues
        if quality_assessment["quality_score"] < 0.6:
            quality_assessment["issues"].append("Low quality separation")

        if completeness_score < 0.8:
            quality_assessment["issues"].append("Incomplete arm information")

        if diversity_score < 0.9:
            quality_assessment["issues"].append("Potential duplicate arms")

        # Add recommendations
        if quality_assessment["quality_score"] < 0.7:
            quality_assessment["recommendations"].append("Consider manual review")

        if completeness_score < 0.8:
            quality_assessment["recommendations"].append(
                "Improve arm metadata extraction"
            )

        return quality_assessment
