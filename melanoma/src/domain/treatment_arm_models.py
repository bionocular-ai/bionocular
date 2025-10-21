"""Domain models for treatment arm separation and management.

This module contains the core business entities for treatment arm
identification, separation, and management in clinical trial extraction.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, validator


class ArmType(str, Enum):
    """Types of treatment arms."""

    MONOTHERAPY = "monotherapy"
    COMBINATION = "combination"
    DOSE_VARIATION = "dose_variation"
    PLACEBO = "placebo"
    CONTROL = "control"
    UNKNOWN = "unknown"


class LineOfTreatment(str, Enum):
    """Lines of treatment for clinical trials."""

    NEOADJUVANT = "neoadjuvant"
    FIRST_LINE = "first_line"
    SECOND_LINE = "second_line"
    THIRD_LINE_PLUS = "third_line_plus"
    UNKNOWN = "unknown"


class TreatmentArm(BaseModel):
    """Represents a single treatment arm in a clinical trial."""

    arm_id: str = Field(..., description="Unique identifier for the treatment arm")
    arm_name: str = Field(..., description="Descriptive name of the treatment arm")
    generic_name: str = Field(..., description="Generic drug name(s)")
    brand_name: Optional[str] = Field(None, description="Brand name if available")
    dose: Optional[str] = Field(None, description="Dose information")
    dosing_schedule: Optional[str] = Field(None, description="Dosing schedule")
    patient_count: Optional[int] = Field(
        None, description="Number of patients in this arm"
    )
    line_of_treatment: LineOfTreatment = Field(
        LineOfTreatment.UNKNOWN, description="Line of treatment"
    )
    arm_type: ArmType = Field(ArmType.UNKNOWN, description="Type of treatment arm")
    combination_drugs: list[str] = Field(
        default_factory=list, description="List of drugs in combination"
    )

    # Metadata
    confidence_score: float = Field(
        ge=0.0, le=1.0, default=0.0, description="Confidence in arm separation"
    )
    source_text: Optional[str] = Field(
        None, description="Source text used for arm identification"
    )
    arm_metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata for the treatment arm"
    )
    created_at: datetime = Field(default_factory=datetime.now)

    @validator("generic_name")
    def validate_generic_name(cls, v):
        if not v or not v.strip():
            raise ValueError("Generic name cannot be empty")
        return v.strip()

    @validator("patient_count")
    def validate_patient_count(cls, v):
        if v is not None and v < 0:
            raise ValueError("Patient count cannot be negative")
        return v

    @property
    def is_combination(self) -> bool:
        """Check if this is a combination therapy."""
        return self.arm_type == ArmType.COMBINATION or len(self.combination_drugs) > 1

    @property
    def is_dose_variation(self) -> bool:
        """Check if this is a dose variation of another arm."""
        return self.arm_type == ArmType.DOSE_VARIATION

    def get_display_name(self) -> str:
        """Get a human-readable display name for the arm."""
        if self.is_combination:
            return f"{self.generic_name} + {' + '.join(self.combination_drugs)}"
        elif self.dose:
            return f"{self.generic_name} {self.dose}"
        else:
            return self.generic_name


class TreatmentArmSeparationResult(BaseModel):
    """Result of treatment arm separation process."""

    abstract_id: str = Field(..., description="Abstract identifier")
    treatment_arms: list[TreatmentArm] = Field(
        default_factory=list, description="Identified treatment arms"
    )
    separation_confidence: float = Field(
        ge=0.0, le=1.0, default=0.0, description="Overall separation confidence"
    )
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    errors: list[str] = Field(default_factory=list, description="Processing errors")
    warnings: list[str] = Field(default_factory=list, description="Processing warnings")
    created_at: datetime = Field(default_factory=datetime.now)

    @property
    def arm_count(self) -> int:
        """Number of treatment arms identified."""
        return len(self.treatment_arms)

    @property
    def has_errors(self) -> bool:
        """Check if there are any processing errors."""
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        """Check if there are any processing warnings."""
        return len(self.warnings) > 0

    def get_arm_by_id(self, arm_id: str) -> Optional[TreatmentArm]:
        """Get treatment arm by ID."""
        for arm in self.treatment_arms:
            if arm.arm_id == arm_id:
                return arm
        return None

    def get_arms_by_type(self, arm_type: ArmType) -> list[TreatmentArm]:
        """Get treatment arms by type."""
        return [arm for arm in self.treatment_arms if arm.arm_type == arm_type]


class ArmSpecificContext(BaseModel):
    """Context information specific to a treatment arm."""

    arm_id: str = Field(..., description="Treatment arm identifier")
    abstract_id: str = Field(..., description="Abstract identifier")
    context_chunks: list[dict[str, Any]] = Field(
        default_factory=list, description="RAG context chunks"
    )
    arm_metadata: dict[str, Any] = Field(
        default_factory=dict, description="Arm-specific metadata"
    )
    context_quality_score: float = Field(
        ge=0.0, le=1.0, default=0.0, description="Context quality score"
    )
    created_at: datetime = Field(default_factory=datetime.now)

    @property
    def chunk_count(self) -> int:
        """Number of context chunks."""
        return len(self.context_chunks)

    @property
    def has_context(self) -> bool:
        """Check if context is available."""
        return len(self.context_chunks) > 0


class TreatmentArmExtractionRequest(BaseModel):
    """Request for treatment arm-specific attribute extraction."""

    abstract_id: str = Field(..., description="Abstract identifier")
    treatment_arms: list[TreatmentArm] = Field(
        ..., description="Treatment arms to process"
    )
    attributes: list[str] = Field(..., description="Attributes to extract per arm")
    context_chunks_per_arm: int = Field(
        default=5, ge=1, le=20, description="Context chunks per arm"
    )
    similarity_threshold: float = Field(
        default=0.1, ge=0.0, le=1.0, description="Similarity threshold"
    )
    metadata_filters: dict[str, Any] = Field(
        default_factory=dict, description="Metadata filters"
    )


class TreatmentArmExtractionResult(BaseModel):
    """Result of treatment arm-specific attribute extraction."""

    abstract_id: str = Field(..., description="Abstract identifier")
    arm_results: dict[str, dict[str, Any]] = Field(
        default_factory=dict, description="Results per arm"
    )
    overall_confidence: float = Field(
        ge=0.0, le=1.0, default=0.0, description="Overall extraction confidence"
    )
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    total_attributes_extracted: int = Field(
        default=0, description="Total attributes extracted"
    )
    errors: list[str] = Field(default_factory=list, description="Processing errors")
    warnings: list[str] = Field(default_factory=list, description="Processing warnings")
    created_at: datetime = Field(default_factory=datetime.now)

    @property
    def arm_count(self) -> int:
        """Number of treatment arms processed."""
        return len(self.arm_results)

    @property
    def success_rate(self) -> float:
        """Success rate of attribute extraction."""
        if not self.arm_results:
            return 0.0

        total_arms = len(self.arm_results)
        successful_arms = sum(
            1
            for arm_result in self.arm_results.values()
            if not arm_result.get("errors", [])
        )
        return successful_arms / total_arms

    def get_arm_result(self, arm_id: str) -> Optional[dict[str, Any]]:
        """Get extraction result for a specific arm."""
        return self.arm_results.get(arm_id)

    def get_attribute_values(self, attribute_name: str) -> dict[str, Any]:
        """Get values for a specific attribute across all arms."""
        attribute_values = {}
        for arm_id, arm_result in self.arm_results.items():
            if "attributes" in arm_result:
                attribute_values[arm_id] = arm_result["attributes"].get(attribute_name)
        return attribute_values


class TreatmentArmValidationRule(BaseModel):
    """Validation rule for treatment arm data."""

    field_name: str = Field(..., description="Field to validate")
    required: bool = Field(default=False, description="Whether field is required")
    pattern: Optional[str] = Field(None, description="Regex pattern for validation")
    min_value: Optional[float] = Field(None, description="Minimum value")
    max_value: Optional[float] = Field(None, description="Maximum value")
    allowed_values: Optional[list[str]] = Field(None, description="Allowed values")
    custom_validator: Optional[str] = Field(
        None, description="Custom validation function"
    )


class TreatmentArmQualityAssessment(BaseModel):
    """Quality assessment for treatment arm separation and extraction."""

    abstract_id: str = Field(..., description="Abstract identifier")
    separation_quality: float = Field(
        ge=0.0, le=1.0, description="Arm separation quality score"
    )
    extraction_quality: float = Field(
        ge=0.0, le=1.0, description="Attribute extraction quality score"
    )
    overall_quality: float = Field(ge=0.0, le=1.0, description="Overall quality score")
    quality_issues: list[str] = Field(
        default_factory=list, description="Quality issues identified"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Improvement recommendations"
    )
    assessed_at: datetime = Field(default_factory=datetime.now)

    @property
    def quality_level(self) -> str:
        """Get quality level based on overall score."""
        if self.overall_quality >= 0.8:
            return "high"
        elif self.overall_quality >= 0.6:
            return "medium"
        else:
            return "low"

    @property
    def needs_review(self) -> bool:
        """Check if results need manual review."""
        return self.overall_quality < 0.6 or len(self.quality_issues) > 0
