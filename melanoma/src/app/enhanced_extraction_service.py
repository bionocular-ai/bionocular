"""Enhanced extraction service with comprehensive attribute support.

This service integrates RAG-enhanced extraction with Clinical Trials API
data and backbone prompts for comprehensive clinical trial data extraction.
"""

import logging
from datetime import datetime
from typing import Any, Optional

from ..domain.extraction_interfaces import AttributeExtractor, LLMService
from ..domain.extraction_models import AttributeConfigurationFactory, AttributeType
from ..domain.treatment_arm_models import (
    ArmSpecificContext,
    TreatmentArm,
    TreatmentArmExtractionResult,
    TreatmentArmSeparationResult,
)
from ..infrastructure.arm_aware_rag_provider import ArmAwareRAGContextProvider
from ..infrastructure.backbone_prompt_provider import BackbonePromptProvider
from ..infrastructure.batch_attribute_extractor import BatchAttributeExtractor
from ..infrastructure.clinical_trials_api_service import ClinicalTrialsAPIService
from ..infrastructure.cost_calculator import CostCalculator
from ..infrastructure.cost_tracking_llm_service import CostTrackingLLMService
from ..infrastructure.file_path_extractor import FilePathExtractor
from ..infrastructure.prompt_templates import ExtractionPromptTemplateProvider
from ..infrastructure.treatment_arm_separator import TreatmentArmSeparator

logger = logging.getLogger(__name__)


class EnhancedExtractionService:
    """Enhanced extraction service with comprehensive attribute support.

    This service orchestrates the complete workflow of:
    1. Treatment arm separation
    2. RAG context retrieval per arm
    3. Clinical Trials API data integration
    4. Backbone prompt enhancement for complex attributes
    5. Targeted attribute extraction per arm
    6. Quality assessment and validation
    """

    def __init__(
        self,
        treatment_arm_separator: TreatmentArmSeparator,
        arm_aware_rag_provider: ArmAwareRAGContextProvider,
        attribute_extractor: AttributeExtractor,
        llm_service: LLMService,
        clinical_trials_api_service: Optional[ClinicalTrialsAPIService] = None,
        enable_cost_tracking: bool = True,
    ):
        """Initialize enhanced extraction service.

        Args:
            treatment_arm_separator: Service for separating treatment arms
            arm_aware_rag_provider: RAG provider for arm-aware context retrieval
            attribute_extractor: Service for extracting attributes
            llm_service: LLM service for text generation
            clinical_trials_api_service: Service for Clinical Trials API data
            enable_cost_tracking: Whether to enable cost tracking
        """
        self.treatment_arm_separator = treatment_arm_separator
        self.arm_aware_rag_provider = arm_aware_rag_provider
        self.attribute_extractor = attribute_extractor
        self.clinical_trials_api_service = clinical_trials_api_service

        # Set up cost tracking if enabled
        if enable_cost_tracking:
            self.cost_calculator = CostCalculator()
            self.llm_service = CostTrackingLLMService(llm_service, self.cost_calculator)
            self.cost_tracking_enabled = True
        else:
            self.llm_service = llm_service
            self.cost_calculator = None
            self.cost_tracking_enabled = False

        # Initialize providers
        self.prompt_provider = ExtractionPromptTemplateProvider()
        self.backbone_provider = BackbonePromptProvider()
        self.file_path_extractor = FilePathExtractor()
        self.batch_extractor = BatchAttributeExtractor(
            self.llm_service, self.prompt_provider
        )

        # Get attribute configurations
        self.attribute_configs = AttributeConfigurationFactory.get_all_configurations()
        self.api_sourced_attributes = (
            AttributeConfigurationFactory.get_api_sourced_attributes()
        )
        self.backbone_prompt_attributes = (
            AttributeConfigurationFactory.get_backbone_prompt_attributes()
        )

        logger.info("Enhanced extraction service initialized")

        if self.cost_tracking_enabled:
            logger.info("Cost tracking enabled")

    async def extract_attributes_from_abstract(
        self,
        abstract_text: str,
        abstract_id: str,
        attributes: list[AttributeType],
        context_chunks_per_arm: int = 5,
        similarity_threshold: float = 0.1,
        include_api_data: bool = True,
        file_path: Optional[str] = None,
    ) -> TreatmentArmExtractionResult:
        """Extract attributes from abstract using enhanced workflow.

        Args:
            abstract_text: Full abstract text
            abstract_id: Abstract identifier
            attributes: List of attributes to extract
            context_chunks_per_arm: Number of context chunks per arm
            similarity_threshold: Similarity threshold for RAG retrieval
            include_api_data: Whether to include Clinical Trials API data
            file_path: Optional file path for Conference/Year extraction

        Returns:
            Treatment arm extraction result
        """
        start_time = datetime.now()

        try:
            logger.info(f"Starting enhanced extraction for abstract {abstract_id}")

            # Store file path for use in arm extraction
            self._current_file_path = file_path

            # Step 1: Separate treatment arms
            logger.info("Step 1: Separating treatment arms")
            separation_result = (
                await self.treatment_arm_separator.separate_treatment_arms(
                    abstract_text, abstract_id
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
                        include_api_data=include_api_data,
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
                f"Enhanced extraction completed: {total_attributes_extracted} attributes extracted"
            )
            return result

        except Exception as e:
            logger.error(f"Enhanced extraction failed: {e}")
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

            return TreatmentArmExtractionResult(
                abstract_id=abstract_id,
                arm_results={},
                overall_confidence=0.0,
                processing_time_ms=processing_time,
                errors=[f"Extraction failed: {str(e)}"],
            )

    async def extract_attributes_from_abstract_batch(
        self,
        abstract_text: str,
        abstract_id: str,
        attributes: list[AttributeType],
        context_chunks_per_arm: int = 5,
        similarity_threshold: float = 0.1,
        include_api_data: bool = True,
        file_path: Optional[str] = None,
    ) -> TreatmentArmExtractionResult:
        """Extract attributes from abstract using batch processing for efficiency.

        This method processes all attributes for all arms in batches, significantly
        reducing LLM API calls and improving processing speed.

        Args:
            abstract_text: Full abstract text
            abstract_id: Abstract identifier
            attributes: List of attributes to extract
            context_chunks_per_arm: Number of context chunks per arm
            similarity_threshold: Similarity threshold for RAG retrieval
            include_api_data: Whether to include Clinical Trials API data
            file_path: Optional file path for Conference/Year extraction

        Returns:
            Treatment arm extraction result
        """
        start_time = datetime.now()

        try:
            logger.info(f"Starting batch extraction for abstract {abstract_id}")

            # Store file path for use in arm extraction
            self._current_file_path = file_path

            # Step 1: Separate treatment arms
            logger.info("Step 1: Separating treatment arms")
            separation_result = (
                await self.treatment_arm_separator.separate_treatment_arms(
                    abstract_text, abstract_id
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

            # Step 2: Prepare comprehensive context for all arms
            logger.info("Step 2: Preparing comprehensive context for batch processing")
            comprehensive_context = await self._prepare_comprehensive_context(
                separation_result.treatment_arms,
                abstract_id,
                context_chunks_per_arm,
                similarity_threshold,
            )

            # Step 3: Separate attributes by source
            file_path_attributes = []
            abstract_attributes = []
            api_attributes = []

            for attr_type in attributes:
                if self.file_path_extractor.can_extract_from_path(attr_type):
                    file_path_attributes.append(attr_type)
                else:
                    config = self.attribute_configs.get(attr_type)
                    if config and config.api_source:
                        api_attributes.append(attr_type)
                    else:
                        abstract_attributes.append(attr_type)

            # Step 4: Extract file path attributes (once for all arms)
            file_path_results = {}
            if file_path_attributes:
                logger.info(
                    f"Extracting file path attributes: {[attr.value for attr in file_path_attributes]}"
                )
                file_path_results = self._extract_file_path_attributes_batch(
                    file_path_attributes, file_path
                )

            # Step 5: Extract abstract attributes using batch processing
            abstract_results = {}
            if abstract_attributes:
                logger.info(
                    f"Extracting abstract attributes in batch: {[attr.value for attr in abstract_attributes]}"
                )
                abstract_results = (
                    await self.batch_extractor.extract_attributes_for_arms(
                        arms=separation_result.treatment_arms,
                        attributes=abstract_attributes,
                        context=comprehensive_context,
                        document_id=abstract_id,
                    )
                )

            # Step 6: Extract API attributes
            api_results = {}
            if api_attributes and include_api_data:
                logger.info(
                    f"Extracting API attributes: {[attr.value for attr in api_attributes]}"
                )
                api_results = await self._extract_api_attributes_batch(
                    separation_result.treatment_arms, api_attributes, abstract_id
                )

            # Step 7: Combine results for each arm
            logger.info("Step 7: Combining results for each treatment arm")
            arm_results = {}
            total_attributes_extracted = 0

            for arm in separation_result.treatment_arms:
                arm_result: dict[str, Any] = {
                    "arm_id": arm.arm_id,
                    "arm_name": arm.arm_name,
                    "attributes": {},
                    "errors": [],
                    "warnings": [],
                }

                # Combine all attribute sources for this arm
                for attr_type in attributes:
                    if attr_type in file_path_results:
                        arm_result["attributes"][attr_type] = file_path_results[
                            attr_type
                        ]
                    elif (
                        attr_type in abstract_results
                        and arm.arm_id in abstract_results[attr_type]
                    ):
                        arm_result["attributes"][attr_type] = abstract_results[
                            attr_type
                        ][arm.arm_id]
                    elif (
                        attr_type in api_results
                        and arm.arm_id in api_results[attr_type]
                    ):
                        arm_result["attributes"][attr_type] = api_results[attr_type][
                            arm.arm_id
                        ]

                arm_results[arm.arm_id] = arm_result
                total_attributes_extracted += len(arm_result["attributes"])

            # Step 8: Calculate overall confidence and quality
            overall_confidence = self._calculate_overall_confidence(
                arm_results, separation_result
            )

            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

            logger.info(
                f"Batch extraction completed for abstract {abstract_id}: "
                f"{total_attributes_extracted} attributes across {len(arm_results)} arms "
                f"in {processing_time}ms"
            )

            return TreatmentArmExtractionResult(
                abstract_id=abstract_id,
                arm_results=arm_results,
                overall_confidence=overall_confidence,
                processing_time_ms=processing_time,
                errors=[],
                warnings=[],
            )

        except Exception as e:
            logger.error(f"Batch extraction failed: {e}")
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

            return TreatmentArmExtractionResult(
                abstract_id=abstract_id,
                arm_results={},
                overall_confidence=0.0,
                processing_time_ms=processing_time,
                errors=[f"Batch extraction failed: {str(e)}"],
            )

    async def _extract_attributes_for_arm(
        self,
        arm: TreatmentArm,
        attributes: list[AttributeType],
        arm_context: ArmSpecificContext,
        abstract_id: str,
        include_api_data: bool = True,
    ) -> dict[str, Any]:
        """Extract attributes for a specific treatment arm.

        Args:
            arm: Treatment arm to extract attributes for
            attributes: List of attributes to extract
            arm_context: RAG context for the arm
            abstract_id: Abstract identifier
            include_api_data: Whether to include API data

        Returns:
            Dictionary containing extracted attributes and metadata
        """
        extracted_attributes: dict[AttributeType, Any] = {}
        errors = []
        warnings = []

        # Get NCT number for API lookups
        nct_number = None
        if arm.arm_metadata and "nct_number" in arm.arm_metadata:
            nct_number = arm.arm_metadata["nct_number"]

        # Separate attributes by source
        file_path_attributes = []
        abstract_attributes = []
        api_attributes = []

        for attr_type in attributes:
            if self.file_path_extractor.can_extract_from_path(attr_type):
                file_path_attributes.append(attr_type)
            else:
                config = self.attribute_configs.get(attr_type)
                if config and config.api_source:
                    api_attributes.append(attr_type)
                else:
                    abstract_attributes.append(attr_type)

        # Extract file path-based attributes (Conference, Published Year)
        for attr_type in file_path_attributes:
            try:
                attr_name = (
                    attr_type.value if hasattr(attr_type, "value") else str(attr_type)
                )
                logger.debug(f"Extracting file path attribute: {attr_name}")

                # Get file path from the service call context
                # For now, we'll pass it through the arm context or use a default
                file_path_value = None
                if hasattr(self, "_current_file_path") and self._current_file_path:
                    file_path_value = (
                        self.file_path_extractor.extract_attribute_from_path(
                            attr_type, self._current_file_path
                        )
                    )

                if file_path_value is not None:
                    extracted_attributes[attr_type] = {
                        "value": file_path_value,
                        "source": "file_path",
                        "confidence": 1.0,  # High confidence for file path extraction
                    }
                else:
                    warnings.append(f"Could not extract {attr_name} from file path")

            except Exception as e:
                attr_name = (
                    attr_type.value if hasattr(attr_type, "value") else str(attr_type)
                )
                logger.error(f"Failed to extract {attr_name} from file path: {e}")
                errors.append(f"Failed to extract {attr_name} from file path: {str(e)}")

        # Extract abstract-level attributes using RAG + LLM
        for attr_type in abstract_attributes:
            try:
                attr_name = (
                    attr_type.value if hasattr(attr_type, "value") else str(attr_type)
                )
                logger.debug(f"Extracting abstract attribute: {attr_name}")
                logger.debug(f"attr_type: {attr_type} (type: {type(attr_type)})")

                # Get context for this specific attribute
                attr_context = (
                    await self.arm_aware_rag_provider.get_context_for_arm_attribute(
                        arm=arm,
                        attribute_type=attr_type,
                        abstract_id=abstract_id,
                        context_chunks=5,
                        similarity_threshold=0.1,
                    )
                )

                # Get extraction prompt
                context_texts = [
                    chunk["content"] for chunk in attr_context.context_chunks
                ]

                # Debug: Check attr_type before calling get_extraction_prompt
                logger.debug(
                    f"About to call get_extraction_prompt with attr_type: {attr_type} (type: {type(attr_type)})"
                )

                # Extract attribute using LLM
                arm_info = {
                    "arm_id": arm.arm_id,
                    "arm_name": arm.arm_name,
                    "generic_name": arm.generic_name,
                    "dose": arm.dose,
                }
                extracted_value = await self.attribute_extractor.extract_attribute(
                    attribute_type=attr_type,
                    context=context_texts,
                    document_id=abstract_id,
                    arm_info=arm_info,
                )

                if extracted_value is not None:
                    # Extract clean value from Pydantic object
                    clean_value = (
                        extracted_value.value
                        if hasattr(extracted_value, "value")
                        else str(extracted_value)
                    )
                    extracted_attributes[attr_type] = {
                        "value": clean_value,
                        "source": "abstract_extraction",
                        "confidence": getattr(extracted_value, "confidence", 0.8),
                        "context_chunks": len(attr_context.context_chunks),
                    }
                else:
                    attr_name = (
                        attr_type.value
                        if hasattr(attr_type, "value")
                        else str(attr_type)
                    )
                    warnings.append(f"Could not extract {attr_name} from abstract")

            except Exception as e:
                # Debug: Check what attr_type is at this point
                logger.debug(
                    f"Exception occurred for attr_type: {attr_type} (type: {type(attr_type)})"
                )
                logger.debug(f"Exception: {e}")
                logger.debug(f"Exception type: {type(e)}")

                attr_name = (
                    attr_type.value if hasattr(attr_type, "value") else str(attr_type)
                )
                logger.error(f"Failed to extract {attr_name}: {e}")
                errors.append(f"Failed to extract {attr_name}: {str(e)}")

        # Extract API-sourced attributes
        if include_api_data and self.clinical_trials_api_service and nct_number:
            try:
                logger.debug(f"Fetching API data for NCT: {nct_number}")
                # Prepare arm info for API service (only include fields that exist in TreatmentArm model)
                arm_info = {
                    "arm_id": arm.arm_id,
                    "arm_name": arm.arm_name,
                    "generic_name": arm.generic_name,
                    "brand_name": arm.brand_name,
                    "dose": arm.dose,
                    "dosing_schedule": arm.dosing_schedule,
                }

                api_data = self.clinical_trials_api_service.get_multiple_attributes(
                    nct_number, api_attributes, arm_info
                )

                for attr_type, value in api_data.items():
                    if value is not None:
                        extracted_attributes[attr_type] = {
                            "value": value,
                            "source": "clinical_trials_api",
                            "confidence": 0.9,  # High confidence for API data
                            "nct_number": nct_number,
                        }
                    else:
                        attr_name = (
                            attr_type.value
                            if hasattr(attr_type, "value")
                            else str(attr_type)
                        )
                        warnings.append(f"API data not available for {attr_name}")

            except Exception as e:
                logger.error(f"Failed to fetch API data: {e}")
                errors.append(f"Failed to fetch API data: {str(e)}")

        # Handle special cases and optimizations
        extracted_attributes = self._handle_special_cases(
            extracted_attributes, arm, nct_number
        )

        return {
            "arm_id": arm.arm_id,
            "arm_name": arm.arm_name,
            "attributes": extracted_attributes,
            "errors": errors,
            "warnings": warnings,
            "total_attributes": len(extracted_attributes),
            "api_attributes": len(
                [
                    a
                    for a in extracted_attributes.values()
                    if a.get("source") == "clinical_trials_api"
                ]
            ),
            "abstract_attributes": len(
                [
                    a
                    for a in extracted_attributes.values()
                    if a.get("source") == "abstract_extraction"
                ]
            ),
        }

    def _handle_special_cases(
        self,
        extracted_attributes: dict[AttributeType, Any],
        arm: TreatmentArm,
        nct_number: Optional[str],
    ) -> dict[AttributeType, Any]:
        """Handle special cases and optimizations for attribute extraction.

        Args:
            extracted_attributes: Currently extracted attributes
            arm: Treatment arm
            nct_number: NCT number if available

        Returns:
            Updated extracted attributes
        """
        # Direct propagation of NCT number from arm separation
        if nct_number and AttributeType.NCT_NUMBER not in extracted_attributes:
            extracted_attributes[AttributeType.NCT_NUMBER] = {
                "value": nct_number,
                "source": "arm_separation",
                "confidence": 1.0,
            }

        # Direct propagation of generic name from arm separation
        if arm.arm_metadata and "generic_name" in arm.arm_metadata:
            generic_name = arm.arm_metadata["generic_name"]
            if generic_name and AttributeType.GENERIC_NAME not in extracted_attributes:
                extracted_attributes[AttributeType.GENERIC_NAME] = {
                    "value": generic_name,
                    "source": "arm_separation",
                    "confidence": 1.0,
                }

        return extracted_attributes

    def _calculate_overall_confidence(
        self,
        arm_results: dict[str, Any],
        separation_result: TreatmentArmSeparationResult,
    ) -> float:
        """Calculate overall confidence score for the extraction.

        Args:
            arm_results: Results for each treatment arm
            separation_result: Treatment arm separation result

        Returns:
            Overall confidence score (0.0-1.0)
        """
        if not arm_results:
            return 0.0

        total_confidence = 0.0
        total_attributes = 0

        for arm_result in arm_results.values():
            attributes = arm_result.get("attributes", {})
            for attr_data in attributes.values():
                if isinstance(attr_data, dict) and "confidence" in attr_data:
                    total_confidence += attr_data["confidence"]
                    total_attributes += 1

        if total_attributes == 0:
            return 0.0

        return total_confidence / total_attributes

    def get_extraction_summary(
        self, result: TreatmentArmExtractionResult
    ) -> dict[str, Any]:
        """Get a summary of the extraction results.

        Args:
            result: Treatment arm extraction result

        Returns:
            Summary dictionary
        """
        total_arms = len(result.arm_results)
        total_attributes = result.total_attributes_extracted
        overall_confidence = result.overall_confidence

        # Count attributes by source
        api_attributes = 0
        abstract_attributes = 0
        arm_separation_attributes = 0

        for arm_result in result.arm_results.values():
            attributes = arm_result.get("attributes", {})
            for attr_data in attributes.values():
                if isinstance(attr_data, dict):
                    source = attr_data.get("source", "unknown")
                    if source == "clinical_trials_api":
                        api_attributes += 1
                    elif source == "abstract_extraction":
                        abstract_attributes += 1
                    elif source == "arm_separation":
                        arm_separation_attributes += 1

        return {
            "abstract_id": result.abstract_id,
            "total_arms": total_arms,
            "total_attributes": total_attributes,
            "overall_confidence": overall_confidence,
            "processing_time_ms": result.processing_time_ms,
            "attribute_sources": {
                "api": api_attributes,
                "abstract": abstract_attributes,
                "arm_separation": arm_separation_attributes,
            },
            "errors": result.errors,
            "warnings": result.warnings,
        }

    def get_cost_summary(self):
        """Get current cost summary if cost tracking is enabled.

        Returns:
            CostSummary or None if cost tracking is disabled
        """
        if self.cost_tracking_enabled and self.cost_calculator:
            return self.cost_calculator.get_summary()
        return None

    def print_cost_summary(self):
        """Print formatted cost summary if cost tracking is enabled."""
        if self.cost_tracking_enabled and self.cost_calculator:
            self.cost_calculator.print_summary()
        else:
            logger.info("Cost tracking is not enabled")

    def save_cost_report(self, filepath: str):
        """Save detailed cost report if cost tracking is enabled.

        Args:
            filepath: Path to save the report
        """
        if self.cost_tracking_enabled and self.cost_calculator:
            self.cost_calculator.save_detailed_report(filepath)
        else:
            logger.info("Cost tracking is not enabled")

    def reset_cost_tracking(self):
        """Reset cost tracking if enabled."""
        if self.cost_tracking_enabled and self.cost_calculator:
            self.cost_calculator.reset()
            logger.info("Cost tracking reset")

    async def _prepare_comprehensive_context(
        self,
        arms: list[TreatmentArm],
        abstract_id: str,
        context_chunks_per_arm: int,
        similarity_threshold: float,
    ) -> list[str]:
        """Prepare comprehensive context for all arms.

        Args:
            arms: List of treatment arms
            abstract_id: Abstract identifier
            context_chunks_per_arm: Number of context chunks per arm
            similarity_threshold: Similarity threshold for RAG retrieval

        Returns:
            List of context chunks
        """
        all_context_chunks = set()

        # Get context for each arm and combine
        for arm in arms:
            try:
                arm_context = await self.arm_aware_rag_provider.get_context_for_arm_attribute(
                    arm=arm,
                    attribute_type=AttributeType.NCT_NUMBER,  # Use a common attribute for context
                    abstract_id=abstract_id,
                    context_chunks=context_chunks_per_arm,
                    similarity_threshold=similarity_threshold,
                )

                # Add chunks to the comprehensive context
                for chunk in arm_context.context_chunks:
                    all_context_chunks.add(chunk["content"])

            except Exception as e:
                logger.warning(f"Failed to get context for arm {arm.arm_id}: {e}")
                continue

        return list(all_context_chunks)

    def _extract_file_path_attributes_batch(
        self,
        attributes: list[AttributeType],
        file_path: Optional[str],
    ) -> dict[AttributeType, dict[str, Any]]:
        """Extract file path attributes in batch.

        Args:
            attributes: List of file path attributes
            file_path: File path to extract from

        Returns:
            Dictionary mapping attribute types to their values
        """
        results = {}

        if not file_path:
            logger.warning("No file path provided for file path attribute extraction")
            for attr_type in attributes:
                results[attr_type] = {
                    "value": "Not found",
                    "source": "file_path",
                    "confidence": 0.0,
                }
            return results

        for attr_type in attributes:
            try:
                value = self.file_path_extractor.extract_attribute_from_path(
                    attr_type, file_path
                )
                results[attr_type] = {
                    "value": value if value is not None else "Not found",
                    "source": "file_path",
                    "confidence": 1.0 if value is not None else 0.0,
                }
            except Exception as e:
                logger.error(f"Failed to extract {attr_type.value} from file path: {e}")
                results[attr_type] = {
                    "value": "Not found",
                    "source": "file_path",
                    "confidence": 0.0,
                }

        return results

    async def _extract_api_attributes_batch(
        self,
        arms: list[TreatmentArm],
        attributes: list[AttributeType],
        abstract_id: str,
    ) -> dict[AttributeType, dict[str, Any]]:
        """Extract API attributes in batch.

        Args:
            arms: List of treatment arms
            attributes: List of API attributes
            abstract_id: Abstract identifier

        Returns:
            Dictionary mapping attribute types to arm results
        """
        results: dict[AttributeType, dict[str, Any]] = {}

        if not self.clinical_trials_api_service:
            logger.warning("Clinical Trials API service not available")
            for attr_type in attributes:
                results[attr_type] = {}
                for arm in arms:
                    results[attr_type][arm.arm_id] = {
                        "value": "Not found",
                        "source": "clinical_trials_api",
                        "confidence": 0.0,
                    }
            return results

        # Get NCT number from first arm (they should all be the same)
        nct_number = None
        if arms and arms[0].arm_metadata and "nct_number" in arms[0].arm_metadata:
            nct_number = arms[0].arm_metadata["nct_number"]

        if not nct_number:
            logger.warning("No NCT number found for API attribute extraction")
            for attr_type in attributes:
                results[attr_type] = {}
                for arm in arms:
                    results[attr_type][arm.arm_id] = {
                        "value": "Not found",
                        "source": "clinical_trials_api",
                        "confidence": 0.0,
                    }
            return results

        # Extract API data for each arm
        for arm in arms:
            try:
                arm_info = {
                    "arm_id": arm.arm_id,
                    "arm_name": arm.arm_name,
                    "generic_name": arm.generic_name,
                    "brand_name": arm.brand_name,
                    "dose": arm.dose,
                    "dosing_schedule": arm.dosing_schedule,
                }

                api_data = self.clinical_trials_api_service.get_multiple_attributes(
                    nct_number, attributes, arm_info
                )

                # Store results for this arm
                for attr_type in attributes:
                    if attr_type not in results:
                        results[attr_type] = {}

                    value = api_data.get(attr_type)
                    results[attr_type][arm.arm_id] = {
                        "value": value if value is not None else "Not found",
                        "source": "clinical_trials_api",
                        "confidence": 0.9 if value is not None else 0.0,
                    }

            except Exception as e:
                logger.error(f"Failed to extract API data for arm {arm.arm_id}: {e}")
                for attr_type in attributes:
                    if attr_type not in results:
                        results[attr_type] = {}
                    results[attr_type][arm.arm_id] = {
                        "value": "Not found",
                        "source": "clinical_trials_api",
                        "confidence": 0.0,
                    }

        return results
