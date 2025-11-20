"""RAG-enhanced extraction service for clinical trial data.

This service orchestrates the complete RAG-enhanced extraction workflow,
combining treatment arm separation with targeted attribute extraction.
"""

import logging
import re
from datetime import datetime
from typing import Any, Optional

from ..domain.extraction_interfaces import AttributeExtractor, LLMService
from ..domain.extraction_models import AttributeType
from ..domain.treatment_arm_models import (
    ArmSpecificContext,
    TreatmentArm,
    TreatmentArmExtractionResult,
    TreatmentArmSeparationResult,
)
from ..infrastructure.arm_aware_rag_provider import ArmAwareRAGContextProvider
from ..infrastructure.prompt_templates import ExtractionPromptTemplateProvider
from ..infrastructure.treatment_arm_separator import TreatmentArmSeparator

logger = logging.getLogger(__name__)


class RAGEnhancedExtractionService:
    """RAG-enhanced extraction service for clinical trial data.

    This service orchestrates the complete workflow of:
    1. Treatment arm separation
    2. RAG context retrieval per arm
    3. Targeted attribute extraction per arm
    4. Quality assessment and validation
    """

    def __init__(
        self,
        treatment_arm_separator: TreatmentArmSeparator,
        arm_aware_rag_provider: ArmAwareRAGContextProvider,
        attribute_extractor: AttributeExtractor,
        llm_service: LLMService,
    ):
        """Initialize RAG-enhanced extraction service.

        Args:
            treatment_arm_separator: Service for separating treatment arms
            arm_aware_rag_provider: RAG provider for arm-aware context retrieval
            attribute_extractor: Service for extracting attributes
            llm_service: LLM service for text generation
        """
        self.treatment_arm_separator = treatment_arm_separator
        self.arm_aware_rag_provider = arm_aware_rag_provider
        self.attribute_extractor = attribute_extractor
        self.llm_service = llm_service

        # Initialize prompt provider
        self.prompt_provider = ExtractionPromptTemplateProvider()

        logger.info("RAG-enhanced extraction service initialized")

    def _is_publication(self, content: str, file_path: Optional[str] = None) -> bool:
        """Detect if content is a full publication (not an abstract).
        
        Args:
            content: Document content
            file_path: Optional file path for pattern matching
            
        Returns:
            True if this appears to be a publication
        """
        # Check filename pattern (Publications folder)
        if file_path and ("Publications" in file_path or "publication" in file_path.lower()):
            return True
            
        # Check for publication structure (main sections with #)
        has_main_sections = (
            re.search(r"^#\s+(Introduction|Methods|Results|Discussion|Conclusion)", content, re.MULTILINE | re.IGNORECASE) is not None
        )
        
        # Check for absence of abstract-specific markers
        has_abstract_id = "### Abstract ID:" in content or "Abstract ID:" in content
        
        # Check length (publications are typically much longer)
        is_long = len(content) > 5000
        
        # Publication if it has main sections, no abstract ID, and is long
        return has_main_sections and not has_abstract_id and is_long

    def _extract_results_section(self, content: str) -> Optional[str]:
        """Extract the Results section from publication content.
        
        For publications, treatment arms are typically described in the Results section,
        not in Background or Methods. This method extracts only the Results section
        for arm separation.
        
        Args:
            content: Full publication content
            
        Returns:
            Results section content, or None if not found
        """
        lines = content.split("\n")
        results_start = None
        results_end = None
        in_results = False
        
        # Keywords that indicate Results section
        results_keywords = [
            r"^#+\s*\*?\*?Results\*?\*?",
            r"^#+\s*\*?\*?Findings\*?\*?",
        ]
        
        # Keywords that indicate end of Results section
        end_keywords = [
            r"^#+\s*\*?\*?Discussion\*?\*?",
            r"^#+\s*\*?\*?Conclusion\*?\*?",
            r"^#+\s*\*?\*?References\*?\*?",
            r"^#+\s*\*?\*?Appendix\*?\*?",
        ]
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            
            # Check if we're starting Results section
            if not in_results:
                for pattern in results_keywords:
                    if re.match(pattern, line_stripped, re.IGNORECASE):
                        results_start = i
                        in_results = True
                        logger.debug(f"Found Results section start at line {i}: {line_stripped[:50]}")
                        break
            else:
                # Check if we're ending Results section
                for pattern in end_keywords:
                    if re.match(pattern, line_stripped, re.IGNORECASE):
                        results_end = i
                        logger.debug(f"Found Results section end at line {i}: {line_stripped[:50]}")
                        break
                
                if results_end is not None:
                    break
        
        # If we found start but no end, Results section goes to end of document
        if results_start is not None and results_end is None:
            results_end = len(lines)
        
        if results_start is not None:
            results_content = "\n".join(lines[results_start:results_end])
            logger.info(f"Extracted Results section: {results_end - results_start} lines")
            return results_content
        
        logger.warning("Results section not found in publication content")
        return None

    async def extract_attributes_from_abstract(
        self,
        abstract_text: str,
        abstract_id: str,
        attributes: list[AttributeType],
        context_chunks_per_arm: int = 5,
        similarity_threshold: float = 0.1,
        file_path: Optional[str] = None,
    ) -> TreatmentArmExtractionResult:
        """Extract attributes from abstract using RAG-enhanced workflow.

        Args:
            abstract_text: Full abstract text
            abstract_id: Abstract identifier
            attributes: List of attributes to extract
            context_chunks_per_arm: Number of context chunks per arm
            similarity_threshold: Similarity threshold for RAG retrieval
            file_path: Optional file path for publication detection

        Returns:
            Treatment arm extraction result
        """
        start_time = datetime.now()

        try:
            logger.info(f"Starting RAG-enhanced extraction for abstract {abstract_id}")

            # Step 1: Separate treatment arms
            # For publications, extract Results section first and separate arms from it only
            is_pub = self._is_publication(abstract_text, file_path)
            text_for_arm_separation = abstract_text
            
            if is_pub:
                logger.info("Detected publication - extracting Results section for arm separation")
                results_section = self._extract_results_section(abstract_text)
                if results_section:
                    text_for_arm_separation = results_section
                    logger.info(f"Using Results section for arm separation ({len(results_section)} chars)")
                else:
                    logger.warning("Results section not found, using full publication text for arm separation")
            
            logger.info("Step 1: Separating treatment arms")
            separation_result = (
                await self.treatment_arm_separator.separate_treatment_arms(
                    text_for_arm_separation, abstract_id
                )
            )

            if not separation_result.treatment_arms:
                logger.warning(
                    f"No treatment arms identified for abstract {abstract_id}"
                )
                return TreatmentArmExtractionResult(
                    abstract_id=abstract_id,
                    arm_results={},
                    overall_confidence=0.0,
                    processing_time_ms=int(
                        (datetime.now() - start_time).total_seconds() * 1000
                    ),
                    errors=["No treatment arms identified"],
                )

            logger.info(
                f"Identified {len(separation_result.treatment_arms)} treatment arms"
            )

            # Step 2: Extract attributes for each treatment arm
            logger.info("Step 2: Extracting attributes per treatment arm")
            arm_results = {}
            total_attributes_extracted = 0

            for arm in separation_result.treatment_arms:
                try:
                    logger.info(f"Processing arm: {arm.arm_name}")

                    # Get RAG context for this arm
                    arm_context = (
                        await self.arm_aware_rag_provider.get_context_for_arm_attribute(
                            arm=arm,
                            attribute_type=attributes[
                                0
                            ],  # Use first attribute for context retrieval
                            abstract_id=abstract_id,
                            context_chunks=context_chunks_per_arm,
                            similarity_threshold=similarity_threshold,
                        )
                    )

                    # Extract attributes for this arm
                    arm_extraction_result = await self._extract_attributes_for_arm(
                        arm=arm,
                        attributes=attributes,
                        arm_context=arm_context,
                        abstract_id=abstract_id,
                    )

                    arm_results[arm.arm_id] = arm_extraction_result
                    total_attributes_extracted += len(
                        arm_extraction_result.get("attributes", {})
                    )

                except Exception as e:
                    logger.error(
                        f"Failed to extract attributes for arm {arm.arm_id}: {e}"
                    )
                    arm_results[arm.arm_id] = {
                        "arm_id": arm.arm_id,
                        "arm_name": arm.arm_name,
                        "attributes": {},
                        "errors": [f"Extraction failed: {str(e)}"],
                        "warnings": [],
                    }

            # Step 3: Calculate overall confidence and quality
            overall_confidence = self._calculate_overall_confidence(
                arm_results, separation_result
            )

            # Calculate processing time
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

            # Create result
            result = TreatmentArmExtractionResult(
                abstract_id=abstract_id,
                arm_results=arm_results,
                overall_confidence=overall_confidence,
                processing_time_ms=processing_time,
                total_attributes_extracted=total_attributes_extracted,
            )

            logger.info(
                f"RAG-enhanced extraction completed: {total_attributes_extracted} attributes extracted"
            )
            return result

        except Exception as e:
            logger.error(f"RAG-enhanced extraction failed: {e}")
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

            return TreatmentArmExtractionResult(
                abstract_id=abstract_id,
                arm_results={},
                overall_confidence=0.0,
                processing_time_ms=processing_time,
                errors=[f"Extraction failed: {str(e)}"],
            )

    async def _extract_attributes_for_arm(
        self,
        arm: TreatmentArm,
        attributes: list[AttributeType],
        arm_context: ArmSpecificContext,
        abstract_id: str,
    ) -> dict[str, Any]:
        """Extract attributes for a specific treatment arm.

        Args:
            arm: Treatment arm to extract attributes for
            attributes: List of attributes to extract
            arm_context: Arm-specific context
            abstract_id: Abstract identifier

        Returns:
            Arm extraction result
        """
        try:
            arm_result = {
                "arm_id": arm.arm_id,
                "arm_name": arm.arm_name,
                "attributes": {},
                "errors": [],
                "warnings": [],
                "context_quality": arm_context.context_quality_score,
            }

            # Extract each attribute
            for attribute_type in attributes:
                try:
                    # Use more context for sparse attributes
                    per_attr_chunks = (
                        10
                        if attribute_type
                        in (
                            AttributeType.P_VALUE_OS,
                            AttributeType.OBJECTIVE_RESPONSE_RATE,
                            AttributeType.GRADE_3_PLUS_AE,
                        )
                        else 5
                    )

                    # Get specific context for this attribute
                    attribute_context = (
                        await self.arm_aware_rag_provider.get_context_for_arm_attribute(
                            arm=arm,
                            attribute_type=attribute_type,
                            abstract_id=abstract_id,
                            context_chunks=per_attr_chunks,
                            similarity_threshold=0.1,
                        )
                    )

                    # Convert context to string format for attribute extractor
                    context_strings = [
                        chunk["content"] for chunk in attribute_context.context_chunks
                    ]

                    # Fallback: if no context, use full abstract text from arm_context metadata if available
                    if not context_strings:
                        if (
                            hasattr(arm_context, "arm_metadata")
                            and "full_abstract" in arm_context.arm_metadata
                        ):
                            context_strings = [
                                arm_context.arm_metadata["full_abstract"]
                            ]

                    # Extract attribute
                    extracted_attribute = (
                        await self.attribute_extractor.extract_attribute(
                            attribute_type=attribute_type,
                            context=context_strings,
                            document_id=abstract_id,
                        )
                    )

                    # Store extracted attribute
                    arm_result["attributes"][attribute_type.value] = {
                        "value": extracted_attribute.value,
                        "confidence": extracted_attribute.confidence,
                        "validation_status": extracted_attribute.validation_status.value,
                        "source_chunks": extracted_attribute.source_chunks,
                    }

                    # Direct NCT propagation: if attribute is NCT_NUMBER and arm/source has nct_number, prefer that
                    if attribute_type == AttributeType.NCT_NUMBER:
                        nct_from_arm = arm_result.get("nct_number") or getattr(
                            arm, "nct_number", None
                        )
                        if nct_from_arm and not extracted_attribute.value:
                            arm_result["attributes"][attribute_type.value][
                                "value"
                            ] = nct_from_arm
                            arm_result["attributes"][attribute_type.value][
                                "confidence"
                            ] = 1.0

                except Exception as e:
                    logger.warning(
                        f"Failed to extract {attribute_type} for arm {arm.arm_id}: {e}"
                    )
                    arm_result["attributes"][attribute_type.value] = {
                        "value": None,
                        "confidence": 0.0,
                        "validation_status": "invalid",
                        "source_chunks": [],
                    }
                    arm_result["warnings"].append(
                        f"Failed to extract {attribute_type.value}: {str(e)}"
                    )

            return arm_result

        except Exception as e:
            logger.error(f"Attribute extraction failed for arm {arm.arm_id}: {e}")
            return {
                "arm_id": arm.arm_id,
                "arm_name": arm.arm_name,
                "attributes": {},
                "errors": [f"Attribute extraction failed: {str(e)}"],
                "warnings": [],
            }

    def _calculate_overall_confidence(
        self,
        arm_results: dict[str, dict[str, Any]],
        separation_result: TreatmentArmSeparationResult,
    ) -> float:
        """Calculate overall confidence score for extraction results.

        Args:
            arm_results: Results for each treatment arm
            separation_result: Treatment arm separation result

        Returns:
            Overall confidence score
        """
        if not arm_results:
            return 0.0

        # Factor 1: Treatment arm separation confidence
        separation_confidence = separation_result.separation_confidence

        # Factor 2: Attribute extraction confidence per arm
        arm_confidences = []
        for arm_result in arm_results.values():
            if "attributes" in arm_result and arm_result["attributes"]:
                attribute_confidences = [
                    attr.get("confidence", 0.0)
                    for attr in arm_result["attributes"].values()
                ]
                if attribute_confidences:
                    arm_confidences.append(
                        sum(attribute_confidences) / len(attribute_confidences)
                    )

        avg_arm_confidence = (
            sum(arm_confidences) / len(arm_confidences) if arm_confidences else 0.0
        )

        # Factor 3: Context quality
        context_qualities = [
            arm_result.get("context_quality", 0.0)
            for arm_result in arm_results.values()
        ]
        avg_context_quality = (
            sum(context_qualities) / len(context_qualities)
            if context_qualities
            else 0.0
        )

        # Factor 4: Success rate
        successful_arms = sum(
            1 for arm_result in arm_results.values() if not arm_result.get("errors", [])
        )
        success_rate = successful_arms / len(arm_results) if arm_results else 0.0

        # Calculate weighted overall confidence
        overall_confidence = (
            separation_confidence * 0.3
            + avg_arm_confidence * 0.4
            + avg_context_quality * 0.2
            + success_rate * 0.1
        )

        return min(overall_confidence, 1.0)

    async def validate_extraction_quality(
        self, extraction_result: TreatmentArmExtractionResult
    ) -> dict[str, Any]:
        """Validate the quality of extraction results.

        Args:
            extraction_result: Extraction result to validate

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
        if not extraction_result.arm_results:
            quality_assessment["is_valid"] = False
            quality_assessment["issues"].append("No treatment arms processed")
            return quality_assessment

        # Calculate quality score
        quality_factors = []

        # Factor 1: Overall confidence
        quality_factors.append(extraction_result.overall_confidence)

        # Factor 2: Success rate
        quality_factors.append(extraction_result.success_rate)

        # Factor 3: Attribute completeness
        total_attributes = 0
        extracted_attributes = 0

        for arm_result in extraction_result.arm_results.values():
            if "attributes" in arm_result:
                for attr_result in arm_result["attributes"].values():
                    total_attributes += 1
                    if attr_result.get("value") is not None:
                        extracted_attributes += 1

        completeness_score = (
            extracted_attributes / total_attributes if total_attributes > 0 else 0.0
        )
        quality_factors.append(completeness_score)

        # Factor 4: Context quality
        context_qualities = [
            arm_result.get("context_quality", 0.0)
            for arm_result in extraction_result.arm_results.values()
        ]
        avg_context_quality = (
            sum(context_qualities) / len(context_qualities)
            if context_qualities
            else 0.0
        )
        quality_factors.append(avg_context_quality)

        # Calculate overall quality score
        quality_assessment["quality_score"] = sum(quality_factors) / len(
            quality_factors
        )

        # Add quality issues
        if quality_assessment["quality_score"] < 0.6:
            quality_assessment["issues"].append("Low quality extraction")

        if completeness_score < 0.8:
            quality_assessment["issues"].append("Incomplete attribute extraction")

        if extraction_result.success_rate < 0.8:
            quality_assessment["issues"].append("Low success rate")

        # Add recommendations
        if quality_assessment["quality_score"] < 0.7:
            quality_assessment["recommendations"].append("Consider manual review")

        if completeness_score < 0.8:
            quality_assessment["recommendations"].append("Improve context retrieval")

        if extraction_result.success_rate < 0.8:
            quality_assessment["recommendations"].append(
                "Check LLM service configuration"
            )

        return quality_assessment

    def get_extraction_statistics(
        self, extraction_result: TreatmentArmExtractionResult
    ) -> dict[str, Any]:
        """Get statistics about the extraction results.

        Args:
            extraction_result: Extraction result to analyze

        Returns:
            Extraction statistics
        """
        stats = {
            "abstract_id": extraction_result.abstract_id,
            "arm_count": extraction_result.arm_count,
            "total_attributes_extracted": extraction_result.total_attributes_extracted,
            "overall_confidence": extraction_result.overall_confidence,
            "success_rate": extraction_result.success_rate,
            "processing_time_ms": extraction_result.processing_time_ms,
            "error_count": len(extraction_result.errors),
            "warning_count": len(extraction_result.warnings),
        }

        # Per-arm statistics
        arm_stats = {}
        for arm_id, arm_result in extraction_result.arm_results.items():
            arm_stats[arm_id] = {
                "arm_name": arm_result.get("arm_name", ""),
                "attribute_count": len(arm_result.get("attributes", {})),
                "context_quality": arm_result.get("context_quality", 0.0),
                "error_count": len(arm_result.get("errors", [])),
                "warning_count": len(arm_result.get("warnings", [])),
            }

        stats["arm_statistics"] = arm_stats

        return stats
