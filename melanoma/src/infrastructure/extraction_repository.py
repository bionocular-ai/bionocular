"""Repository implementation for extraction system.

This module implements the extraction repository interface using
PostgreSQL and SQLAlchemy.
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from ..domain.extraction_interfaces import ExtractionRepository
from ..domain.extraction_models import (
    AttributeType,
    ExtractedAttribute,
    ExtractionResult,
    ValidationRule,
    ValidationStatus,
)
from .database_models import (
    ExtractedAttributeModel,
    ExtractionMetricsModel,
    ExtractionResultModel,
    ValidationRuleModel,
)

logger = logging.getLogger(__name__)


class ExtractionRepositoryImpl(ExtractionRepository):
    """PostgreSQL implementation of extraction repository.

    This implementation follows the Repository pattern and
    provides a clean abstraction over database operations.
    """

    def __init__(self, db_session: Session):
        """Initialize repository with database session.

        Args:
            db_session: SQLAlchemy database session
        """
        self.db_session = db_session
        logger.info("Extraction repository initialized")

    async def save_extraction_result(self, result: ExtractionResult) -> str:
        """Save extraction result to database.

        Args:
            result: Extraction result to save

        Returns:
            Unique identifier for saved result
        """
        try:
            # Create extraction result model
            result_model = ExtractionResultModel(
                document_id=result.document_id,
                processing_time_ms=result.processing_time_ms,
                total_chunks_processed=result.total_chunks_processed,
                extraction_confidence=result.extraction_confidence,
                success_rate=result.success_rate,
                created_at=result.created_at,
            )

            self.db_session.add(result_model)
            self.db_session.flush()  # Get the ID

            # Create attribute models
            for attr_type, attribute in result.extracted_attributes.items():
                attribute_model = ExtractedAttributeModel(
                    extraction_result_id=result_model.id,
                    attribute_type=attr_type,
                    value=str(attribute.value) if attribute.value is not None else None,
                    confidence=attribute.confidence,
                    source_chunks=attribute.source_chunks,
                    validation_status=attribute.validation_status,
                    validation_errors=attribute.validation_errors,
                    confidence_level=attribute.confidence_level,
                    extracted_at=attribute.extracted_at,
                )

                self.db_session.add(attribute_model)

            # Update metrics
            await self._update_extraction_metrics(result)

            # Commit transaction
            self.db_session.commit()

            logger.info(
                f"Saved extraction result {result_model.id} for document {result.document_id}"
            )
            return str(result_model.id)

        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Failed to save extraction result: {e}")
            raise

    async def get_extraction_result(self, result_id: str) -> Optional[ExtractionResult]:
        """Retrieve extraction result by ID.

        Args:
            result_id: Unique result identifier

        Returns:
            Extraction result or None if not found
        """
        try:
            result_model = (
                self.db_session.query(ExtractionResultModel)
                .filter(ExtractionResultModel.id == result_id)
                .first()
            )

            if not result_model:
                return None

            # Get attributes
            attribute_models = (
                self.db_session.query(ExtractedAttributeModel)
                .filter(ExtractedAttributeModel.extraction_result_id == result_id)
                .all()
            )

            # Convert to domain models
            extracted_attributes = {}
            for attr_model in attribute_models:
                attribute = self._convert_to_domain_attribute(attr_model)
                extracted_attributes[attr_model.attribute_type] = attribute

            # Create domain result
            result = ExtractionResult(
                document_id=str(result_model.document_id),
                extracted_attributes=extracted_attributes,  # type: ignore
                processing_time_ms=int(result_model.processing_time_ms),
                total_chunks_processed=int(result_model.total_chunks_processed),
                extraction_confidence=float(result_model.extraction_confidence),
                created_at=result_model.created_at,  # type: ignore
            )

            return result

        except Exception as e:
            logger.error(f"Failed to retrieve extraction result {result_id}: {e}")
            return None

    async def get_extraction_results_by_document(
        self, document_id: str
    ) -> list[ExtractionResult]:
        """Get all extraction results for a document.

        Args:
            document_id: Document identifier

        Returns:
            List of extraction results
        """
        try:
            result_models = (
                self.db_session.query(ExtractionResultModel)
                .filter(ExtractionResultModel.document_id == document_id)
                .order_by(desc(ExtractionResultModel.created_at))
                .all()
            )

            results = []
            for result_model in result_models:
                # Get attributes for this result
                attribute_models = (
                    self.db_session.query(ExtractedAttributeModel)
                    .filter(
                        ExtractedAttributeModel.extraction_result_id == result_model.id
                    )
                    .all()
                )

                # Convert to domain models
                extracted_attributes = {}
                for attr_model in attribute_models:
                    attribute = self._convert_to_domain_attribute(attr_model)
                    extracted_attributes[attr_model.attribute_type] = attribute

                # Create domain result
                result = ExtractionResult(
                    document_id=str(result_model.document_id),
                    extracted_attributes=extracted_attributes,  # type: ignore
                    processing_time_ms=int(result_model.processing_time_ms),
                    total_chunks_processed=int(result_model.total_chunks_processed),
                    extraction_confidence=float(result_model.extraction_confidence),
                    created_at=result_model.created_at,  # type: ignore
                )

                results.append(result)

            return results

        except Exception as e:
            logger.error(
                f"Failed to retrieve extraction results for document {document_id}: {e}"
            )
            return []

    async def get_validation_rules(
        self, attribute_type: AttributeType
    ) -> list[ValidationRule]:
        """Get validation rules for an attribute type.

        Args:
            attribute_type: Type of attribute

        Returns:
            List of validation rules
        """
        try:
            rule_models = (
                self.db_session.query(ValidationRuleModel)
                .filter(ValidationRuleModel.attribute_type == attribute_type)  # type: ignore
                .all()
            )

            rules = []
            for rule_model in rule_models:
                rule = ValidationRule(
                    attribute_type=rule_model.attribute_type,  # type: ignore
                    required=bool(rule_model.required),
                    pattern=rule_model.pattern,  # type: ignore
                    min_value=rule_model.min_value,  # type: ignore
                    max_value=rule_model.max_value,  # type: ignore
                    allowed_values=rule_model.allowed_values,  # type: ignore
                    custom_validator=rule_model.custom_validator,  # type: ignore
                )
                rules.append(rule)

            return rules

        except Exception as e:
            logger.error(
                f"Failed to retrieve validation rules for {attribute_type}: {e}"
            )
            return []

    def _convert_to_domain_attribute(
        self, attr_model: ExtractedAttributeModel
    ) -> ExtractedAttribute:
        """Convert database model to domain attribute.

        Args:
            attr_model: Database attribute model

        Returns:
            Domain attribute model
        """
        # Convert value back to appropriate type
        value = attr_model.value
        if value is not None:
            if attr_model.attribute_type in [
                AttributeType.OBJECTIVE_RESPONSE_RATE,
                AttributeType.GRADE_3_PLUS_AE,
            ]:
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    pass
            elif attr_model.attribute_type == AttributeType.P_VALUE_OS:
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    pass

        return ExtractedAttribute(
            attribute_type=attr_model.attribute_type,  # type: ignore
            value=value,  # type: ignore
            confidence=float(attr_model.confidence),
            source_chunks=attr_model.source_chunks or [],  # type: ignore
            validation_status=attr_model.validation_status,  # type: ignore
            validation_errors=attr_model.validation_errors or [],  # type: ignore
            extracted_at=attr_model.extracted_at,  # type: ignore
        )

    async def _update_extraction_metrics(self, result: ExtractionResult) -> None:
        """Update extraction metrics for analytics.

        Args:
            result: Extraction result to update metrics for
        """
        try:
            for attr_type, attribute in result.extracted_attributes.items():
                # Get or create metrics record
                metrics = (
                    self.db_session.query(ExtractionMetricsModel)
                    .filter(
                        and_(
                            ExtractionMetricsModel.document_id == result.document_id,
                            ExtractionMetricsModel.attribute_type == attr_type,  # type: ignore
                        )
                    )
                    .first()
                )

                if not metrics:
                    metrics = ExtractionMetricsModel(
                        document_id=result.document_id,
                        attribute_type=attr_type,
                        extraction_count=0,
                        success_count=0,
                        failure_count=0,
                        avg_confidence=0.0,
                    )
                    self.db_session.add(metrics)

                # Update metrics
                metrics.extraction_count += 1
                if attribute.validation_status == ValidationStatus.VALID:
                    metrics.success_count += 1
                else:
                    metrics.failure_count += 1

                # Update average confidence
                total_confidence = (
                    metrics.avg_confidence * (metrics.extraction_count - 1)
                    + attribute.confidence
                )
                metrics.avg_confidence = total_confidence / metrics.extraction_count
                metrics.last_extracted = datetime.utcnow()

        except Exception as e:
            logger.warning(f"Failed to update extraction metrics: {e}")
            # Don't raise - metrics update failure shouldn't break extraction
