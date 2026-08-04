"""Domain models for LLM-as-a-Judge validation of extracted results attributes.

Sibling of ``trial_validation_models`` for the abstract / publication cohorts. The
unit of judgement differs: a trial is one record with eight controlled-vocabulary
fields, whereas an abstract or publication carries several *treatment arms*, each
with 120-165 numeric attributes of which only a handful are populated. So the
judge grades per arm, and routing decisions are per arm too.

Two kinds of model live here, same split as the trials validator:

* ``GroupVerdict`` and its parts are the *LLM contract* - the typed structured
  output the judge returns for one (document, attribute-group) pair.
* ``ArmValidationResult`` / ``DocValidationResult`` / ``ResultsValidationRunSummary``
  are the *pipeline records* written to disk.

``ValidationFieldStatus`` and ``ValidationDecision`` are imported from
``trial_validation_models`` rather than redefined - the per-field verdict and the
routing outcomes are identical concepts across both validators.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from .trial_validation_models import ValidationDecision, ValidationFieldStatus

__all__ = [
    "ArmFieldEvaluation",
    "ArmValidationResult",
    "AttributeGroup",
    "DerivationKind",
    "DocValidationResult",
    "GroupVerdict",
    "MissedValue",
    "ResultsValidationRunSummary",
    "ValidationDecision",
    "ValidationFieldStatus",
]


class AttributeGroup(str, Enum):
    """One judge call per group, per document.

    Groups partition ``extraction_models.FAMILY_TO_ATTRIBUTES`` so every attribute
    the extractor can emit is audited exactly once.
    """

    IDENTIFICATION = "identification"
    EFFICACY = "efficacy"
    SAFETY = "safety"


class DerivationKind(str, Enum):
    """How an extracted value relates to the text it was drawn from.

    Extraction normalises as it reads (strips ``%`` and units, reads ``N (X%)`` as
    ``X``, sums G3+G4+G5 for ``grade_3_plus_*``, may compute ORR from CR+PR), so an
    extracted value is often absent from its own supporting quote. The judge labels
    which transform it believes was applied; the service uses the label to decide
    whether "the value must appear in the quote" is a check it can enforce.
    """

    VERBATIM = "VERBATIM"
    UNIT_STRIPPED = "UNIT_STRIPPED"
    PERCENT_OF_COUNT = "PERCENT_OF_COUNT"
    SUMMED = "SUMMED"
    COMPUTED = "COMPUTED"


#: Derivations where the extracted number is expected to survive into the quote,
#: so a literal value-in-quote check is meaningful.
LITERAL_DERIVATIONS: frozenset[DerivationKind] = frozenset(
    {DerivationKind.VERBATIM, DerivationKind.UNIT_STRIPPED}
)


# ---------------------------------------------------------------------------
# LLM contract (Pydantic) - the judge's structured output
# ---------------------------------------------------------------------------


class ArmFieldEvaluation(BaseModel):
    """The judge's verdict on one extracted attribute of one treatment arm."""

    arm_id: str = Field(description="The arm the value was filed under, e.g. 'arm_1'.")
    field_name: str = Field(description="Canonical attribute name, e.g. 'median_pfs'.")
    extracted_value: str = Field(description="The value under review, as text.")
    status: ValidationFieldStatus
    source_evidence_quote: str | None = Field(
        default=None,
        description="Verbatim phrase from the source that justifies the value. "
        "Required to PASS; must be a literal substring of the source text.",
    )
    derivation: DerivationKind | None = Field(
        default=None,
        description="Which transform maps the quoted text to the extracted value.",
    )
    derivation_justification: str | None = Field(
        default=None,
        description="For SUMMED / PERCENT_OF_COUNT / COMPUTED, the arithmetic: "
        "which numbers from the quote combine to the extracted value.",
    )
    arm_attribution_ok: bool = Field(
        default=True,
        description="False when the quoted value belongs to a different arm or to "
        "the study total rather than to this arm.",
    )
    corrected_value: str | None = Field(
        default=None,
        description="On FAIL, the value the source actually supports for this arm. "
        "Null when no correction can be justified.",
    )
    issue_description: str | None = Field(default=None)


class MissedValue(BaseModel):
    """An endpoint the source reports for an arm that the extractor left empty."""

    arm_id: str
    field_name: str
    suggested_value: str = Field(
        description="The value the source supports, in the extractor's output format."
    )
    source_evidence_quote: str = Field(
        description="Verbatim phrase from the source supporting the addition."
    )


class GroupVerdict(BaseModel):
    """Judge verdict for one (document, attribute-group) pair - the response schema."""

    is_valid: bool = Field(description="True when no field evaluation is FAIL.")
    validation_score: float = Field(
        ge=0.0, le=1.0, description="Overall confidence, 0.0-1.0."
    )
    field_evaluations: list[ArmFieldEvaluation] = Field(default_factory=list)
    missed_values: list[MissedValue] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Pipeline records (dataclasses) - written to disk
# ---------------------------------------------------------------------------


@dataclass
class ArmValidationResult:
    """Outcome of validating one treatment arm of one document."""

    doc_id: str
    arm_id: str
    decision: ValidationDecision
    arm_name: str | None = None
    is_valid: bool = True
    validation_score: float = 1.0
    # Serialised infra ``DeterministicViolation`` objects, so the domain stays
    # free of infrastructure imports.
    deterministic_violations: list[dict] = field(default_factory=list)
    # Every judge evaluation for this arm, serialised.
    field_evaluations: list[dict] = field(default_factory=list)
    # Values the judge says the source supports but the extractor omitted.
    missed_values: list[dict] = field(default_factory=list)
    # Corrections actually applied to the cleaned record (--apply-fixes only).
    applied_corrections: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "arm_id": self.arm_id,
            "arm_name": self.arm_name,
            "decision": self.decision.value,
            "is_valid": self.is_valid,
            "validation_score": round(self.validation_score, 4),
            "deterministic_violations": self.deterministic_violations,
            "field_evaluations": self.field_evaluations,
            "missed_values": self.missed_values,
            "applied_corrections": self.applied_corrections,
        }


@dataclass
class DocValidationResult:
    """Outcome of validating one abstract or publication and all of its arms."""

    doc_id: str
    doc_type: str
    arms: list[ArmValidationResult] = field(default_factory=list)
    # Recorded at validation time. Extraction did not pin a source hash, so this
    # establishes provenance going forward rather than verifying the past.
    source_sha256: str | None = None
    source_path: str | None = None
    # validation_score per AttributeGroup value, for spotting a group that the
    # judge systematically distrusts.
    group_scores: dict[str, float] = field(default_factory=dict)
    error_message: str | None = None
    validated_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def decision(self) -> ValidationDecision:
        """Worst arm decision, used for checkpoint and progress reporting."""
        if self.error_message is not None:
            return ValidationDecision.ERROR
        ranking = [
            ValidationDecision.ERROR,
            ValidationDecision.DROPPED,
            ValidationDecision.HITL,
            ValidationDecision.FIXED,
            ValidationDecision.KEPT,
        ]
        for decision in ranking:
            if any(arm.decision is decision for arm in self.arms):
                return decision
        return ValidationDecision.KEPT

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "doc_type": self.doc_type,
            "decision": self.decision.value,
            "source_sha256": self.source_sha256,
            "source_path": self.source_path,
            "group_scores": {k: round(v, 4) for k, v in self.group_scores.items()},
            "error_message": self.error_message,
            "validated_at": self.validated_at.isoformat(),
            "arms": [arm.to_dict() for arm in self.arms],
        }


@dataclass
class ResultsValidationRunSummary:
    """High-level summary written to the validation.json metadata block."""

    model: str
    run_date: datetime
    doc_type: str
    apply_fixes: bool = False
    total_documents: int = 0
    total_arms: int = 0
    kept: int = 0
    fixed: int = 0
    dropped: int = 0
    hitl: int = 0
    errored: int = 0
    total_missed_values: int = 0
    total_cost_usd: float = 0.0
    total_tokens: int = 0

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "run_date": self.run_date.isoformat(),
            "doc_type": self.doc_type,
            "apply_fixes": self.apply_fixes,
            "total_documents": self.total_documents,
            "total_arms": self.total_arms,
            "kept": self.kept,
            "fixed": self.fixed,
            "dropped": self.dropped,
            "hitl": self.hitl,
            "errored": self.errored,
            "total_missed_values": self.total_missed_values,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "total_tokens": self.total_tokens,
        }
