"""Application service for clinical trial attribute extraction.

This service orchestrates the extraction process by coordinating
between domain entities and infrastructure services.
"""

import logging
from datetime import datetime
from typing import Optional

from ..domain.extraction_interfaces import (
    AttributeExtractor,
    AttributeValidator,
    ExtractionRepository,
    LLMService,
    PromptTemplateProvider,
    RAGContextProvider,
)
from ..domain.extraction_models import (
    AttributeType,
    ExtractedAttribute,
    ExtractionRequest,
    ExtractionResult,
)

logger = logging.getLogger(__name__)


class ExtractionService:
    """Main service for clinical trial attribute extraction.

    This service follows the Single Responsibility Principle by
    focusing solely on orchestrating the extraction process.
    """

    def __init__(
        self,
        rag_context_provider: RAGContextProvider,
        attribute_extractor: AttributeExtractor,
        attribute_validator: AttributeValidator,
        extraction_repository: Optional[ExtractionRepository] = None,
        prompt_template_provider: Optional[PromptTemplateProvider] = None,
        llm_service: Optional[LLMService] = None,
    ):
        """Initialize extraction service with dependencies.

        Args:
            rag_context_provider: Service for retrieving context from RAG
            attribute_extractor: Service for extracting attributes
            attribute_validator: Service for validating extracted attributes
            extraction_repository: Repository for persisting results
            prompt_template_provider: Service for prompt templates
            llm_service: Service for LLM operations
        """
        self.rag_context_provider = rag_context_provider
        self.attribute_extractor = attribute_extractor
        self.attribute_validator = attribute_validator
        self.extraction_repository = extraction_repository
        self.prompt_template_provider = prompt_template_provider
        self.llm_service = llm_service

        logger.info("Extraction service initialized")

    async def extract_attributes(self, request: ExtractionRequest) -> ExtractionResult:
        """Extract specified attributes from a document.

        Args:
            request: Extraction request with document ID and attributes

        Returns:
            Extraction result with all extracted attributes

        Raises:
            ValueError: If request is invalid
            RuntimeError: If extraction fails
        """
        try:
            start_time = datetime.now()
            logger.info(f"Starting extraction for document {request.document_id}")

            # Validate request
            self._validate_request(request)

            # Extract each attribute
            extracted_attributes = {}
            total_chunks_processed = 0

            for attribute_type in request.attributes:
                logger.info(f"Extracting attribute: {attribute_type}")

                # Get context for this attribute
                context = await self.rag_context_provider.get_context_for_attribute(
                    document_id=request.document_id,
                    attribute_type=attribute_type,
                    context_chunks=request.context_chunks,
                    similarity_threshold=request.similarity_threshold,
                    metadata_filters=request.metadata_filters,
                )

                total_chunks_processed += len(context)

                # Extract attribute
                extracted_attribute = await self.attribute_extractor.extract_attribute(
                    attribute_type=attribute_type,
                    context=context,
                    document_id=request.document_id,
                )

                # Validate attribute
                validation_rules = []
                if self.extraction_repository:
                    validation_rules = (
                        await self.extraction_repository.get_validation_rules(
                            attribute_type
                        )
                    )
                validated_attribute = await self.attribute_validator.validate_attribute(
                    attribute=extracted_attribute, validation_rules=validation_rules
                )

                extracted_attributes[attribute_type] = validated_attribute
                logger.info(
                    f"Extracted {attribute_type}: {validated_attribute.value} "
                    f"(confidence: {validated_attribute.confidence:.3f})"
                )

            # Calculate processing time and confidence
            processing_time_ms = int(
                (datetime.now() - start_time).total_seconds() * 1000
            )
            extraction_confidence = self._calculate_overall_confidence(
                extracted_attributes
            )

            # Create result
            result = ExtractionResult(
                document_id=request.document_id,
                extracted_attributes=extracted_attributes,
                processing_time_ms=processing_time_ms,
                total_chunks_processed=total_chunks_processed,
                extraction_confidence=extraction_confidence,
            )

            # Save result (if repository is available)
            if self.extraction_repository:
                result_id = await self.extraction_repository.save_extraction_result(
                    result
                )
                logger.info(
                    f"Extraction completed in {processing_time_ms}ms, result ID: {result_id}"
                )
            else:
                logger.info(
                    f"Extraction completed in {processing_time_ms}ms (no database persistence)"
                )

            return result

        except Exception as e:
            logger.error(f"Extraction failed for document {request.document_id}: {e}")
            raise RuntimeError(f"Extraction failed: {e}") from e

    async def get_extraction_result(self, result_id: str) -> Optional[ExtractionResult]:
        """Retrieve extraction result by ID.

        Args:
            result_id: Unique result identifier

        Returns:
            Extraction result or None if not found
        """
        if not self.extraction_repository:
            raise RuntimeError("Repository not available for retrieval")
        return await self.extraction_repository.get_extraction_result(result_id)

    async def get_document_extractions(
        self, document_id: str
    ) -> list[ExtractionResult]:
        """Get all extraction results for a document.

        Args:
            document_id: Document identifier

        Returns:
            List of extraction results
        """
        if not self.extraction_repository:
            raise RuntimeError("Repository not available for retrieval")
        return await self.extraction_repository.get_extraction_results_by_document(
            document_id
        )

    def _validate_request(self, request: ExtractionRequest) -> None:
        """Validate extraction request.

        Args:
            request: Request to validate

        Raises:
            ValueError: If request is invalid
        """
        if not request.document_id:
            raise ValueError("Document ID is required")

        if not request.attributes:
            raise ValueError("At least one attribute must be specified")

        if len(request.attributes) > 10:
            raise ValueError("Maximum 10 attributes allowed per request")

        # Check for duplicate attributes
        if len(request.attributes) != len(set(request.attributes)):
            raise ValueError("Duplicate attributes not allowed")

    def _calculate_overall_confidence(
        self, attributes: dict[AttributeType, ExtractedAttribute]
    ) -> float:
        """Calculate overall confidence for extraction result.

        Args:
            attributes: Dictionary of extracted attributes

        Returns:
            Overall confidence score between 0 and 1
        """
        if not attributes:
            return 0.0

        # Weight by attribute importance (NCT number is most critical)
        weights = {
            AttributeType.NCT_NUMBER: 0.3,
            AttributeType.GENERIC_NAME: 0.25,
            AttributeType.OBJECTIVE_RESPONSE_RATE: 0.2,
            AttributeType.P_VALUE_OS: 0.15,
            AttributeType.GRADE_3_PLUS_AE: 0.1,
        }

        weighted_confidence = sum(
            weights.get(attr_type, 0.1) * attr.confidence
            for attr_type, attr in attributes.items()
        )

        total_weight = sum(
            weights.get(attr_type, 0.1) for attr_type in attributes.keys()
        )

        return round(weighted_confidence / total_weight, 3) if total_weight > 0 else 0.0
