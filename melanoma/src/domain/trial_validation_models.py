"""Domain models for LLM-as-a-Judge validation of extracted trial parameters.

Two kinds of model live here:

* The Pydantic ``TrialValidationVerdict`` and its parts are the *LLM contract* -
  the typed structured output the judge returns (see ``generate_structured``).
  Values are represented as strings (multi-values ``"; "``-joined) to keep the
  Gemini response schema simple; the service parses them back when applying fixes.
* The dataclass ``TrialValidationResult`` / ``ValidationRunSummary`` are the
  *pipeline records* written to disk, mirroring the extraction pipeline's models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ValidationFieldStatus(str, Enum):
    """Per-field judgement from the validator."""

    PASS = "PASS"
    FAIL = "FAIL"
    UNCERTAIN = "UNCERTAIN"


class ValidationDecision(str, Enum):
    """Routing outcome for a whole trial after validation."""

    KEPT = "kept"
    FIXED = "fixed"
    DROPPED = "dropped"
    HITL = "hitl"
    ERROR = "error"


# ---------------------------------------------------------------------------
# LLM contract (Pydantic) - the judge's structured output
# ---------------------------------------------------------------------------


class FieldEvaluation(BaseModel):
    """The judge's verdict on a single extracted field."""

    field_name: str = Field(description="The extracted field being judged.")
    status: ValidationFieldStatus
    extracted_value: str = Field(
        description="The value under review, rendered as text; "
        'multi-values joined with "; ".'
    )
    source_evidence_quote: str | None = Field(
        default=None,
        description="Verbatim phrase from source_text that justifies the value. "
        "Required to PASS; must be a literal substring of the source.",
    )
    mapping_justification: str | None = Field(
        default=None,
        description="Why the quoted phrase maps to the value (values are inferred, "
        "not copied).",
    )
    corrected_value: str | None = Field(
        default=None,
        description="On FAIL, the proposed replacement value(s), rendered as text "
        'with "; " between multiple values. Null when no correction is offered.',
    )
    issue_description: str | None = Field(default=None)


class MissedValue(BaseModel):
    """A value the source supports but the extractor omitted."""

    field_name: str
    suggested_value: str = Field(
        description="A single value to add; for enum fields it must be in vocabulary."
    )
    source_evidence_quote: str = Field(
        description="Verbatim phrase from source_text supporting the addition."
    )


class TrialValidationVerdict(BaseModel):
    """Full judge verdict for one trial (the structured-output response schema)."""

    is_valid: bool = Field(description="True when no field evaluation is FAIL.")
    validation_score: float = Field(
        ge=0.0, le=1.0, description="Overall confidence, 0.0-1.0."
    )
    field_evaluations: list[FieldEvaluation] = Field(default_factory=list)
    missed_values: list[MissedValue] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Pipeline records (dataclasses) - written to disk
# ---------------------------------------------------------------------------


@dataclass
class TrialValidationResult:
    """Outcome of validating one extracted trial record."""

    nct_number: str
    decision: ValidationDecision
    is_valid: bool = True
    validation_score: float = 1.0
    # Deterministic violations as plain dicts (app layer serialises the infra
    # DeterministicViolation objects so the domain stays free of infra imports).
    deterministic_violations: list[dict] = field(default_factory=list)
    # The judge verdict, serialised; None when the judge did not run (e.g. a
    # deterministic drop, or dry run).
    verdict: dict | None = None
    # Corrections actually applied to the cleaned record (2c only).
    applied_corrections: list[dict] = field(default_factory=list)
    error_message: str | None = None
    validated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "nct_number": self.nct_number,
            "decision": self.decision.value,
            "is_valid": self.is_valid,
            "validation_score": round(self.validation_score, 4),
            "deterministic_violations": self.deterministic_violations,
            "verdict": self.verdict,
            "applied_corrections": self.applied_corrections,
            "error_message": self.error_message,
            "validated_at": self.validated_at.isoformat(),
        }


@dataclass
class ValidationRunSummary:
    """High-level summary written to the validation.json metadata block."""

    model: str
    run_date: datetime
    mode: str = "online"
    apply_fixes: bool = False
    source_snapshot_sha256: str | None = None
    total_trials: int = 0
    kept: int = 0
    fixed: int = 0
    dropped: int = 0
    hitl: int = 0
    errored: int = 0
    total_cost_usd: float = 0.0
    total_tokens: int = 0

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "run_date": self.run_date.isoformat(),
            "mode": self.mode,
            "apply_fixes": self.apply_fixes,
            "source_snapshot_sha256": self.source_snapshot_sha256,
            "total_trials": self.total_trials,
            "kept": self.kept,
            "fixed": self.fixed,
            "dropped": self.dropped,
            "hitl": self.hitl,
            "errored": self.errored,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "total_tokens": self.total_tokens,
        }
