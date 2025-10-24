"""Database models for extraction system.

This module defines SQLAlchemy models for persisting extraction
results in a PostgreSQL database.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

from ..domain.extraction_models import (
    AttributeType,
    ExtractionConfidence,
    ValidationStatus,
)

Base = declarative_base()


class ExtractionResultModel(Base):
    """Database model for extraction results."""

    __tablename__ = "extraction_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(String(255), nullable=False, index=True)
    processing_time_ms = Column(Integer, nullable=False)
    total_chunks_processed = Column(Integer, nullable=False)
    extraction_confidence = Column(Float, nullable=False)
    success_rate = Column(Float, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    attributes = relationship(
        "ExtractedAttributeModel",
        back_populates="extraction_result",
        cascade="all, delete-orphan",
    )


class ExtractedAttributeModel(Base):
    """Database model for extracted attributes."""

    __tablename__ = "extracted_attributes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    extraction_result_id = Column(
        UUID(as_uuid=True),
        ForeignKey("extraction_results.id"),
        nullable=False,
        index=True,
    )
    attribute_type: AttributeType = Column(
        SQLEnum(AttributeType), nullable=False, index=True
    )
    value = Column(String(1000), nullable=True)
    confidence = Column(Float, nullable=False)
    source_chunks = Column(JSON, nullable=False, default=list)
    validation_status: ValidationStatus = Column(
        SQLEnum(ValidationStatus), nullable=False, default=ValidationStatus.PENDING
    )
    validation_errors = Column(JSON, nullable=False, default=list)
    confidence_level: ExtractionConfidence = Column(
        SQLEnum(ExtractionConfidence), nullable=False
    )
    extracted_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    extraction_result = relationship(
        "ExtractionResultModel", back_populates="attributes"
    )


class ValidationRuleModel(Base):
    """Database model for validation rules."""

    __tablename__ = "validation_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attribute_type: AttributeType = Column(
        SQLEnum(AttributeType), nullable=False, index=True
    )
    required = Column(Boolean, nullable=False, default=False)
    pattern = Column(String(500), nullable=True)
    min_value = Column(Float, nullable=True)
    max_value = Column(Float, nullable=True)
    allowed_values = Column(JSON, nullable=True)
    custom_validator = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class ExtractionMetricsModel(Base):
    """Database model for extraction metrics and analytics."""

    __tablename__ = "extraction_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(String(255), nullable=False, index=True)
    attribute_type: AttributeType = Column(
        SQLEnum(AttributeType), nullable=False, index=True
    )
    extraction_count = Column(Integer, nullable=False, default=1)
    success_count = Column(Integer, nullable=False, default=0)
    failure_count = Column(Integer, nullable=False, default=0)
    avg_confidence = Column(Float, nullable=False, default=0.0)
    last_extracted = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
