"""API models and utilities for trials endpoints."""

import os
from typing import Any

from pydantic import BaseModel, Field


class ArmData(BaseModel):
    """Arm data for a trial."""

    arm_name: str = Field(default="", description="Arm name")
    generic_name: str = Field(default="", description="Generic drug name")


class TrialResponse(BaseModel):
    """Response model for a single trial in the list."""

    id: str = Field(..., description="Document UUID")
    nct_id: str = Field(..., description="NCT number")
    title: str = Field(..., description="Trial title")
    phase: str = Field(..., description="Clinical trial phase")
    sponsor: str = Field(..., description="Sponsor name")
    status: str = Field(..., description="Trial status")
    abstract_id: str = Field(default="", description="Abstract ID")
    publication_name: str = Field(default="", description="Publication name (e.g., 'J Clin Oncol 37:693-702. 2019')")
    cancer_type: str = Field(
        default="", description="Primary cancer type (for backward compatibility)"
    )
    cancer_types: list[str] = Field(
        default_factory=list,
        description="List of all normalized cancer types (for filtering)",
    )
    year: str | int = Field(default="", description="Year")
    type: str = Field(
        default="abstract", description="Type: 'abstract' or 'publication'"
    )
    generic_name: str = Field(default="", description="Generic drug name")
    arm_name: str = Field(default="", description="Arm name")
    arms: list[ArmData] = Field(
        default_factory=list, description="List of arms for this trial"
    )


class TrialsListResponse(BaseModel):
    """Response model for trials list endpoint."""

    trials: list[TrialResponse] = Field(..., description="List of trials")
    total: int = Field(..., description="Total number of trials")
    skip: int = Field(..., description="Number of records skipped")
    limit: int = Field(..., description="Maximum number of records returned")


def extract_trial_data(doc: Any, metadata: dict[str, Any]) -> dict[str, Any]:
    """Extract and format trial data from document and metadata.

    Args:
        doc: DocumentModel instance
        metadata: Document metadata dictionary

    Returns:
        Formatted trial data dictionary
    """
    return {
        "id": str(doc.id),
        "nct_id": metadata.get("nct_number") or metadata.get("trial_id") or "",
        "title": metadata.get("title") or doc.original_filename or "Untitled",
        "phase": metadata.get("phase") or metadata.get("clinical_trial_phase") or "",
        "sponsor": metadata.get("sponsor") or metadata.get("sponsors") or "",
        "status": metadata.get("status") or "Unknown",
        "abstract_id": metadata.get("abstract_id")
        or metadata.get("abstract_number")
        or "",
        "cancer_type": metadata.get("cancer_type") or "",
        "year": metadata.get("year") or "",
    }


def get_trials_data_source() -> str:
    """Get the data source for trials.

    Returns:
        "json" if JSON file should be used, "database" otherwise
    """
    return os.getenv("TRIALS_DATA_SOURCE", "json").lower()
