"""Domain models for clinical trial attribute extraction.

This module contains the core business entities and value objects
for the extraction system, following clean architecture principles.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field, validator


class AttributeType(str, Enum):
    """Enumeration of extractable clinical trial attributes."""

    NCT_NUMBER = "nct_number"
    GENERIC_NAME = "generic_name"
    P_VALUE_OS = "p_value_os"
    OBJECTIVE_RESPONSE_RATE = "objective_response_rate"
    GRADE_3_PLUS_AE = "grade_3_plus_ae"


class ValidationStatus(str, Enum):
    """Validation status for extracted attributes."""

    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"
    WARNING = "warning"


class ExtractionConfidence(str, Enum):
    """Confidence levels for extraction results."""

    HIGH = "high"  # > 0.8
    MEDIUM = "medium"  # 0.5 - 0.8
    LOW = "low"  # < 0.5


class PValueSignificance(str, Enum):
    """P-value significance levels."""

    NON_SIGNIFICANT = "Non-Significant"  # p > 0.05
    SIGNIFICANT = "Significant"  # p ≤ 0.05
    HIGHLY_SIGNIFICANT = "Highly Significant"  # p ≤ 0.001


class ExtractedAttribute(BaseModel):
    """Core entity representing an extracted attribute."""

    attribute_type: AttributeType
    value: Union[str, float, int, None]
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence score between 0 and 1"
    )
    source_chunks: list[str] = Field(
        default_factory=list, description="Chunk IDs that contributed to extraction"
    )
    validation_status: ValidationStatus = ValidationStatus.PENDING
    validation_errors: list[str] = Field(default_factory=list)
    extracted_at: datetime = Field(default_factory=datetime.now)

    @validator("confidence")
    def validate_confidence(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        return v

    @property
    def confidence_level(self) -> ExtractionConfidence:
        """Get confidence level based on confidence score."""
        if self.confidence >= 0.8:
            return ExtractionConfidence.HIGH
        elif self.confidence >= 0.5:
            return ExtractionConfidence.MEDIUM
        else:
            return ExtractionConfidence.LOW


class NCTNumber(ExtractedAttribute):
    """Specialized model for NCT number extraction."""

    attribute_type: Literal[AttributeType.NCT_NUMBER] = AttributeType.NCT_NUMBER

    @validator("value")
    def validate_nct_format(cls, v):
        if v is None:
            return v
        if not isinstance(v, str):
            raise ValueError("NCT number must be a string")
        if not v.startswith("NCT") or len(v) != 11:
            raise ValueError("NCT number must be in format NCT########")
        return v


class GenericName(ExtractedAttribute):
    """Specialized model for generic drug name extraction."""

    attribute_type: Literal[AttributeType.GENERIC_NAME] = AttributeType.GENERIC_NAME

    @validator("value")
    def validate_generic_name(cls, v):
        if v is None:
            return v
        if not isinstance(v, str):
            raise ValueError("Generic name must be a string")
        if len(v.strip()) == 0:
            raise ValueError("Generic name cannot be empty")
        return v


class PValueOS(ExtractedAttribute):
    """Specialized model for OS p-value extraction."""

    attribute_type: Literal[AttributeType.P_VALUE_OS] = AttributeType.P_VALUE_OS

    @validator("value")
    def validate_p_value(cls, v):
        if v is None:
            return v
        if isinstance(v, str):
            if v in ["Non-Significant", "Significant", "Highly Significant"]:
                return v
            try:
                float_val = float(v)
                if not 0 <= float_val <= 1:
                    raise ValueError("P-value must be between 0 and 1")
                return float_val
            except ValueError as e:
                raise ValueError(
                    "P-value must be numeric or valid significance level"
                ) from e
        elif isinstance(v, (int, float)):
            if not 0 <= v <= 1:
                raise ValueError("P-value must be between 0 and 1")
            return v
        else:
            raise ValueError("P-value must be numeric or string")


class ObjectiveResponseRate(ExtractedAttribute):
    """Specialized model for ORR extraction."""

    attribute_type: Literal[
        AttributeType.OBJECTIVE_RESPONSE_RATE
    ] = AttributeType.OBJECTIVE_RESPONSE_RATE

    @validator("value")
    def validate_orr(cls, v):
        if v is None:
            return v
        if isinstance(v, str):
            try:
                float_val = float(v)
                if not 0 <= float_val <= 100:
                    raise ValueError("ORR must be between 0 and 100")
                return float_val
            except ValueError as e:
                raise ValueError("ORR must be numeric") from e
        elif isinstance(v, (int, float)):
            if not 0 <= v <= 100:
                raise ValueError("ORR must be between 0 and 100")
            return v
        else:
            raise ValueError("ORR must be numeric")


class Grade3PlusAE(ExtractedAttribute):
    """Specialized model for Grade 3+ AE extraction."""

    attribute_type: Literal[
        AttributeType.GRADE_3_PLUS_AE
    ] = AttributeType.GRADE_3_PLUS_AE

    @validator("value")
    def validate_grade_3_plus_ae(cls, v):
        if v is None:
            return v
        if isinstance(v, str):
            try:
                float_val = float(v)
                if not 0 <= float_val <= 100:
                    raise ValueError("Grade 3+ AE must be between 0 and 100")
                return float_val
            except ValueError as e:
                raise ValueError("Grade 3+ AE must be numeric") from e
        elif isinstance(v, (int, float)):
            if not 0 <= v <= 100:
                raise ValueError("Grade 3+ AE must be between 0 and 100")
            return v
        else:
            raise ValueError("Grade 3+ AE must be numeric")


class ExtractionRequest(BaseModel):
    """Request model for attribute extraction."""

    document_id: str = Field(..., description="Unique identifier for the document")
    attributes: list[AttributeType] = Field(
        ..., description="List of attributes to extract"
    )
    context_chunks: int = Field(
        default=5, ge=1, le=20, description="Number of context chunks to retrieve"
    )
    similarity_threshold: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Minimum similarity threshold for context",
    )
    metadata_filters: dict[str, Any] = Field(
        default_factory=dict, description="Metadata filters for context retrieval"
    )


class ExtractionResult(BaseModel):
    """Result model for attribute extraction."""

    document_id: str
    extracted_attributes: dict[AttributeType, ExtractedAttribute]
    processing_time_ms: int
    total_chunks_processed: int
    extraction_confidence: float = Field(ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=datetime.now)

    @property
    def success_rate(self) -> float:
        """Calculate success rate of extraction."""
        if not self.extracted_attributes:
            return 0.0
        valid_count = sum(
            1
            for attr in self.extracted_attributes.values()
            if attr.validation_status == ValidationStatus.VALID
        )
        return valid_count / len(self.extracted_attributes)

    @property
    def high_confidence_attributes(self) -> list[AttributeType]:
        """Get attributes with high confidence extraction."""
        return [
            attr_type
            for attr_type, attr in self.extracted_attributes.items()
            if attr.confidence_level == ExtractionConfidence.HIGH
        ]


class ValidationRule(BaseModel):
    """Validation rule for attribute extraction."""

    attribute_type: AttributeType
    required: bool = False
    pattern: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    allowed_values: Optional[list[str]] = None
    custom_validator: Optional[str] = None  # Function name for custom validation
