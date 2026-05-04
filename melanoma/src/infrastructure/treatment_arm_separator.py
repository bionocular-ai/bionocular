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
            confidence = validation_result["confidence"]
            errors = validation_result["errors"]
            warnings = validation_result["warnings"]

            result = TreatmentArmSeparationResult(
                abstract_id=abstract_id,
                treatment_arms=treatment_arms,
                separation_confidence=confidence
                if isinstance(confidence, float)
                else 0.0,
                processing_time_ms=processing_time,
                errors=errors if isinstance(errors, list) else [],
                warnings=warnings if isinstance(warnings, list) else [],
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

    @staticmethod
    def _create_separation_prompt() -> str:
        """Create the treatment arm separation prompt."""
        return """
TASK: Identify the primary treatment arms in this clinical trial document.

Treatment arms are usually defined in the Title and in Methods / Patients and Methods / Trial Design / Study Design. Look there first; confirm against Results tables.

RULES:
1. Extract PRIMARY treatment arms only. Most trials have 1-3; multi-cohort or platform trials may have up to 5.
2. Each arm = one distinct treatment regimen.
3. Combination = single arm with "+" notation (e.g., "Nivolumab + Ipilimumab").
4. Different doses of the same drug = separate arms ONLY if the trial explicitly compares them as randomized arms.
5. Non-pharmacological comparators ARE arms: surgery, observation (OBS), watchful waiting, radiotherapy, CLND, registry cohorts. Use arm_type="unknown" and set generic_name to the procedure name.
6. Placebo / control arms ARE arms. Use arm_type="placebo" or "control" with generic_name="Placebo" / "Control".
7. NOT arms - do NOT emit these as separate arms:
   - Subgroup analyses (BRAF+ vs BRAF-, PD-L1 high vs low, ECOG 0 vs 1, age <65 vs >=65)
   - Biomarker cohorts within a single treatment arm
   - Geographic / regional cohorts of the same regimen
   - Dose-escalation cohorts in Phase 1 unless explicitly compared as randomized arms in Phase 2
   - Adjuvant therapies, supportive care, exploratory expansion cohorts
8. If the abstract uses cohort labels (e.g., "Cohort A"), append the regimen: "Cohort A (Nivolumab)".
9. Prefer drug/treatment names over generic labels like "Arm 1", "Treatment arm", "Experimental arm".

FIELDS:
- arm_id: "arm_1", "arm_2", ... (sequential)
- arm_name: drug or treatment name(s) as referred to in the text
- generic_name: strict pharmacological/generic name without doses or "arm" suffix (e.g., "Nivolumab", "Dabrafenib + Trametinib", "Placebo")
- combination_drugs: list of individual drugs for combination arms; [] for monotherapy/placebo/non-drug
- arm_type: one of [monotherapy, combination, placebo, control, dose_variation, unknown]
- line_of_treatment: one of [first_line, second_line, third_line_plus, adjuvant, neoadjuvant, maintenance, unknown]. Infer from Methods (e.g., "previously untreated" -> first_line; "after failure of >=1 prior therapy" -> second_line).
- dose: dose with units if specified, else null
- dosing_schedule: schedule (e.g., "Q3W", "every 2 weeks") if specified, else null
- patient_count: integer N for this arm if explicitly stated, else 0
- nct_number: NCT identifier if found in the document, else ""
- source_text: the verbatim sentence from the document that defines this arm
- confidence_score: rubric:
    1.0 - arm explicitly named in the randomization scheme or trial design
    0.7 - arm clearly inferable from Methods + Results but not named in a randomization scheme
    0.4 - arm uncertain (e.g., dose-escalation cohort treated as arm, ambiguous text)

OUTPUT FORMAT (JSON ONLY - no markdown, no explanations):
{
  "treatment_arms": [
    {
      "arm_id": "arm_1",
      "arm_name": "Nivolumab + Ipilimumab",
      "generic_name": "Nivolumab + Ipilimumab",
      "combination_drugs": ["Nivolumab", "Ipilimumab"],
      "arm_type": "combination",
      "line_of_treatment": "first_line",
      "dose": "Nivo 1 mg/kg + Ipi 3 mg/kg",
      "dosing_schedule": "Q3W x 4 then Nivo Q2W",
      "patient_count": 314,
      "nct_number": "NCT01844505",
      "source_text": "Patients were randomly assigned to receive nivolumab plus ipilimumab...",
      "confidence_score": 1.0
    },
    {
      "arm_id": "arm_2",
      "arm_name": "Nivolumab",
      "generic_name": "Nivolumab",
      "combination_drugs": [],
      "arm_type": "monotherapy",
      "line_of_treatment": "first_line",
      "dose": "3 mg/kg",
      "dosing_schedule": "Q2W",
      "patient_count": 316,
      "nct_number": "NCT01844505",
      "source_text": "...nivolumab alone...",
      "confidence_score": 1.0
    },
    {
      "arm_id": "arm_3",
      "arm_name": "Ipilimumab",
      "generic_name": "Ipilimumab",
      "combination_drugs": [],
      "arm_type": "control",
      "line_of_treatment": "first_line",
      "dose": "3 mg/kg",
      "dosing_schedule": "Q3W x 4",
      "patient_count": 315,
      "nct_number": "NCT01844505",
      "source_text": "...or ipilimumab alone.",
      "confidence_score": 1.0
    }
  ]
}

DOCUMENT TEXT:
{abstract_text}
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
            import os

            return await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.1,
                max_tokens=2000,
                model_name=os.getenv("EXTRACTION_MODEL", "gpt-4o"),
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

            for i, arm_data in enumerate(arms_data):
                try:
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

                    # Safe enum construction — fall back to UNKNOWN instead of dropping the arm
                    try:
                        atype = ArmType(arm_data.get("arm_type", "unknown"))
                    except ValueError:
                        logger.warning(
                            f"Unknown arm_type '{arm_data.get('arm_type')}' for arm {i+1}, "
                            "defaulting to unknown"
                        )
                        atype = ArmType.UNKNOWN

                    try:
                        lot = LineOfTreatment(
                            arm_data.get("line_of_treatment", "unknown")
                        )
                    except ValueError:
                        lot = LineOfTreatment.UNKNOWN

                    # Create treatment arm
                    arm = TreatmentArm(
                        arm_id=arm_data.get("arm_id", f"arm_{i+1}"),
                        arm_name=arm_data.get("arm_name", ""),
                        generic_name=generic_name,
                        brand_name=arm_data.get("brand_name"),
                        dose=arm_data.get("dose"),
                        dosing_schedule=arm_data.get("dosing_schedule"),
                        patient_count=arm_data.get("patient_count"),
                        line_of_treatment=lot,
                        arm_type=atype,
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
    ) -> dict[str, float | list[str]]:
        """Validate treatment arm separation results."""
        validation_result: dict[str, float | list[str]] = {
            "confidence": 0.0,
            "errors": [],
            "warnings": [],
        }

        def add_error(msg: str) -> None:
            errors = validation_result["errors"]
            if isinstance(errors, list):
                errors.append(msg)

        def add_warning(msg: str) -> None:
            warnings = validation_result["warnings"]
            if isinstance(warnings, list):
                warnings.append(msg)

        if not treatment_arms:
            add_error("No treatment arms identified")
            return validation_result

        # Limit number of arms to prevent over-segmentation
        max_arms = 5
        if len(treatment_arms) > max_arms:
            add_warning(
                f"Too many arms identified ({len(treatment_arms)}), limiting to {max_arms} "
                f"highest confidence arms"
            )
            treatment_arms.sort(key=lambda x: x.confidence_score, reverse=True)
            del treatment_arms[max_arms:]

        # Calculate confidence based on various factors
        confidence_factors = []

        # Factor 1: Number of arms
        arm_count = len(treatment_arms)
        if arm_count == 0:
            confidence_factors.append(0.0)
        elif 1 <= arm_count <= 3:
            confidence_factors.append(0.9)  # Most trials have 1-3 arms
        elif arm_count <= 5:
            confidence_factors.append(0.8)  # Valid for multi-cohort/platform trials
        else:
            confidence_factors.append(0.3)
            add_warning(
                f"Too many arms identified ({arm_count}), likely over-segmentation. "
                f"Most clinical trials have 1-5 arms maximum."
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
            add_warning("Duplicate arm names detected")
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
                add_error(f"Arm {arm.arm_id} missing generic name")
            if not arm.arm_name:
                add_error(f"Arm {arm.arm_id} missing arm name")

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
        quality_assessment: dict[str, Any] = {
            "is_valid": True,
            "quality_score": 0.0,
            "issues": [],
            "recommendations": [],
        }

        def add_issue(msg: str) -> None:
            issues = quality_assessment["issues"]
            if isinstance(issues, list):
                issues.append(msg)

        def add_recommendation(msg: str) -> None:
            recommendations = quality_assessment["recommendations"]
            if isinstance(recommendations, list):
                recommendations.append(msg)

        # Check basic validity
        if not separation_result.treatment_arms:
            quality_assessment["is_valid"] = False
            add_issue("No treatment arms identified")
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
            add_issue("Low quality separation")

        if completeness_score < 0.8:
            add_issue("Incomplete arm information")

        if diversity_score < 0.9:
            add_issue("Potential duplicate arms")

        # Add recommendations
        if quality_assessment["quality_score"] < 0.7:
            add_recommendation("Consider manual review")

        if completeness_score < 0.8:
            add_recommendation("Improve arm metadata extraction")

        return quality_assessment
