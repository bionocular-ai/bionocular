"""Domain models for clinical trial parameter extraction.

These models represent the structured output of the parameter extraction
pipeline, independent of the LLM or storage backend used.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class ExtractionStatus(str, Enum):
    """Status of a trial's extraction attempt."""

    DONE = "done"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TrialText:
    """Raw trial text loaded from an export file.

    Holds the full text of a trial .txt file. The single-pass extractor
    passes the complete text to the LLM so it has full context for all
    fields, including officialTitle and briefSummary for treatment/modality
    and eligibility sections for stage, line of therapy, and biomarkers.
    """

    nct_number: str
    official_title: str
    brief_summary: str
    full_text: str


@dataclass
class TrialParameterResult:
    """Extracted parameter set for a single clinical trial."""

    nct_number: str
    cancer_type: list[str] = field(default_factory=list)

    # Linked to treatment (from officialTitle + briefSummary)
    treatment_name: Optional[str] = None
    modality: list[str] = field(default_factory=list)

    # Linked to trial (from full text)
    biomarker: list[str] = field(default_factory=list)
    stage: list[str] = field(default_factory=list)
    line_of_therapy: list[str] = field(default_factory=list)
    previous_treatment_criteria: list[str] = field(default_factory=list)

    extraction_status: ExtractionStatus = ExtractionStatus.DONE
    error_message: Optional[str] = None
    extracted_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Serialise to a plain dict suitable for JSON output."""
        return {
            "nct_number": self.nct_number,
            "cancer_type": self.cancer_type,
            "treatment_name": self.treatment_name,
            "modality": self.modality,
            "biomarker": self.biomarker,
            "stage": self.stage,
            "line_of_therapy": self.line_of_therapy,
            "previous_treatment_criteria": self.previous_treatment_criteria,
            "extraction_status": self.extraction_status.value,
            "error_message": self.error_message,
            "extracted_at": self.extracted_at.isoformat(),
        }


@dataclass
class ExtractionRunSummary:
    """High-level summary written to the results file metadata block."""

    model: str
    run_date: datetime
    total_trials: int = 0
    successful: int = 0
    partial: int = 0
    failed: int = 0
    skipped: int = 0
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    # Provenance of the source snapshot (snapshot mode only). Lets the validation
    # pipeline assert it grades against the exact source the extractor saw.
    snapshot_path: Optional[str] = None
    snapshot_sha256: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "run_date": self.run_date.isoformat(),
            "total_trials": self.total_trials,
            "successful": self.successful,
            "partial": self.partial,
            "failed": self.failed,
            "skipped": self.skipped,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "total_tokens": self.total_tokens,
            "snapshot_path": self.snapshot_path,
            "snapshot_sha256": self.snapshot_sha256,
        }
