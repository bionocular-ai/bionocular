"""Deterministic validator for one extracted clinical-trial parameter record.

Pure, deterministic functions. No LLM, no I/O, no network. Given a single
extracted record (a plain dict, the shape produced by
``TrialParameterResult.to_dict``) plus the cancer types the source declared for
that trial, return every deterministic rule violation. An empty list means the
record is clean.

Each violation carries a severity:

- ``DROP`` — an objective violation; the row must be removed.
- ``FLAG`` — an advisory violation; report it and let a later stage decide.

Follows the style of ``value_validator``: pure functions, full type
annotations, a module logger, and docstrings. The return shape differs: this
module reports structured :class:`DeterministicViolation` objects rather than
``(is_valid, normalized, reason)`` tuples.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from ..domain.trials_extraction_prompts import (
    BIOMARKER_VALUES,
    LINE_OF_THERAPY_VALUES,
    MODALITY_VALUES,
    PREVIOUS_TREATMENT_VALUES,
    STAGE_VALUES,
)

logger = logging.getLogger(__name__)

# ---- Severities --------------------------------------------------------

DROP = "drop"  # objective violation -> row must be removed
FLAG = "flag"  # advisory violation -> report, let a later stage decide

# ---- Rule ids ----------------------------------------------------------

_RULE_NCT_FORMAT = "nct_format"
_RULE_REQUIRED_TREATMENT_NAME = "required_treatment_name"
_RULE_VOCAB_MEMBERSHIP = "vocab_membership"
_RULE_CANCER_TYPE_SUBSET = "cancer_type_subset"
_RULE_LIST_SHAPE = "list_shape"
_RULE_STATUS_CONSISTENCY = "status_consistency"

# ---- Record field names ------------------------------------------------

_FIELD_NCT = "nct_number"
_FIELD_TREATMENT_NAME = "treatment_name"
_FIELD_CANCER_TYPE = "cancer_type"
_FIELD_MODALITY = "modality"
_FIELD_BIOMARKER = "biomarker"
_FIELD_STAGE = "stage"
_FIELD_LINE_OF_THERAPY = "line_of_therapy"
_FIELD_PREVIOUS_TREATMENT = "previous_treatment_criteria"
_FIELD_EXTRACTION_STATUS = "extraction_status"
_FIELD_ERROR_MESSAGE = "error_message"

# ---- extraction_status values ------------------------------------------

_STATUS_DONE = "done"
_STATUS_PARTIAL = "partial"
_STATUS_FAILED = "failed"

# ---- Patterns / vocab wiring -------------------------------------------

_NCT_RE = re.compile(r"^NCT\d{8}$")

# Each controlled-vocabulary field mapped to its allowed value list.
_VOCAB_FIELDS: dict[str, list[str]] = {
    _FIELD_MODALITY: MODALITY_VALUES,
    _FIELD_BIOMARKER: BIOMARKER_VALUES,
    _FIELD_STAGE: STAGE_VALUES,
    _FIELD_LINE_OF_THERAPY: LINE_OF_THERAPY_VALUES,
    _FIELD_PREVIOUS_TREATMENT: PREVIOUS_TREATMENT_VALUES,
}

# Every list-shaped field: the five vocab fields plus cancer_type.
_LIST_FIELDS: tuple[str, ...] = (
    _FIELD_CANCER_TYPE,
    _FIELD_MODALITY,
    _FIELD_BIOMARKER,
    _FIELD_STAGE,
    _FIELD_LINE_OF_THERAPY,
    _FIELD_PREVIOUS_TREATMENT,
)


@dataclass(frozen=True)
class DeterministicViolation:
    """A single deterministic rule violation for one extracted record."""

    field: str  # e.g. "nct_number", "modality", "cancer_type"
    rule: str  # short rule id, one of the module _RULE_* constants
    severity: str  # DROP or FLAG
    detail: str  # human-readable explanation


# ---- Individual rule checks --------------------------------------------


def _check_nct_format(trial: dict) -> list[DeterministicViolation]:
    """nct_number must match ``^NCT\\d{8}$`` (DROP)."""
    nct = trial.get(_FIELD_NCT)
    if isinstance(nct, str) and _NCT_RE.match(nct):
        return []
    return [
        DeterministicViolation(
            field=_FIELD_NCT,
            rule=_RULE_NCT_FORMAT,
            severity=DROP,
            detail=f"nct_number {nct!r} does not match ^NCT\\d{{8}}$",
        )
    ]


def _check_required_treatment_name(trial: dict) -> list[DeterministicViolation]:
    """treatment_name must be present and non-empty on a ``done`` row (DROP)."""
    if trial.get(_FIELD_EXTRACTION_STATUS) != _STATUS_DONE:
        return []
    name = trial.get(_FIELD_TREATMENT_NAME)
    if isinstance(name, str) and name.strip():
        return []
    return [
        DeterministicViolation(
            field=_FIELD_TREATMENT_NAME,
            rule=_RULE_REQUIRED_TREATMENT_NAME,
            severity=DROP,
            detail="treatment_name must be non-empty when extraction_status is 'done'",
        )
    ]


def _list_shape_problem(value: object) -> str | None:
    """Return a description of the first shape problem, or None if the value is
    a well-formed list (a list, no None elements, no duplicates)."""
    if not isinstance(value, list):
        return f"expected a list, got {type(value).__name__}"
    if any(item is None for item in value):
        return "list contains None element(s)"
    seen: list[object] = []
    duplicates: list[object] = []
    for item in value:
        if item in seen:
            if item not in duplicates:
                duplicates.append(item)
        else:
            seen.append(item)
    if duplicates:
        return f"list contains duplicate value(s): {duplicates}"
    return None


def _check_list_shape(trial: dict) -> list[DeterministicViolation]:
    """Each list field must be a list with no None elements and no duplicates
    (FLAG, one violation per offending field)."""
    violations: list[DeterministicViolation] = []
    for field_name in _LIST_FIELDS:
        problem = _list_shape_problem(trial.get(field_name))
        if problem is not None:
            violations.append(
                DeterministicViolation(
                    field=field_name,
                    rule=_RULE_LIST_SHAPE,
                    severity=FLAG,
                    detail=problem,
                )
            )
    return violations


def _check_vocab_membership(trial: dict) -> list[DeterministicViolation]:
    """Every value of each vocab field must be in that field's allowed list
    (FLAG, one violation per offending field). Non-list values are left to the
    list_shape rule; None elements are ignored here."""
    violations: list[DeterministicViolation] = []
    for field_name, allowed in _VOCAB_FIELDS.items():
        value = trial.get(field_name)
        if not isinstance(value, list):
            continue
        bad = [item for item in value if item is not None and item not in allowed]
        if bad:
            violations.append(
                DeterministicViolation(
                    field=field_name,
                    rule=_RULE_VOCAB_MEMBERSHIP,
                    severity=FLAG,
                    detail=f"value(s) not in controlled vocabulary: {bad}",
                )
            )
    return violations


def _check_cancer_type_subset(
    trial: dict, source_cancer_types: list[str]
) -> list[DeterministicViolation]:
    """Every cancer_type value must appear in ``source_cancer_types`` (exact,
    case-sensitive; FLAG). Skipped when the source list is empty."""
    if not source_cancer_types:
        return []
    value = trial.get(_FIELD_CANCER_TYPE)
    if not isinstance(value, list):
        return []
    allowed = set(source_cancer_types)
    bad = [item for item in value if item is not None and item not in allowed]
    if not bad:
        return []
    return [
        DeterministicViolation(
            field=_FIELD_CANCER_TYPE,
            rule=_RULE_CANCER_TYPE_SUBSET,
            severity=FLAG,
            detail=f"cancer_type value(s) not in source {source_cancer_types}: {bad}",
        )
    ]


def _check_status_consistency(trial: dict) -> list[DeterministicViolation]:
    """partial/failed must carry a non-empty error_message; done must not
    (FLAG)."""
    status = trial.get(_FIELD_EXTRACTION_STATUS)
    error = trial.get(_FIELD_ERROR_MESSAGE)
    has_error = isinstance(error, str) and error.strip() != ""

    if status in (_STATUS_PARTIAL, _STATUS_FAILED) and not has_error:
        return [
            DeterministicViolation(
                field=_FIELD_EXTRACTION_STATUS,
                rule=_RULE_STATUS_CONSISTENCY,
                severity=FLAG,
                detail=f"extraction_status {status!r} requires a non-empty error_message",
            )
        ]
    if status == _STATUS_DONE and has_error:
        return [
            DeterministicViolation(
                field=_FIELD_EXTRACTION_STATUS,
                rule=_RULE_STATUS_CONSISTENCY,
                severity=FLAG,
                detail="extraction_status 'done' must not carry an error_message",
            )
        ]
    return []


# ---- Public API --------------------------------------------------------


def check_trial(
    trial: dict, source_cancer_types: list[str]
) -> list[DeterministicViolation]:
    """Return all deterministic violations for one extracted record.

    Args:
        trial: One extracted record, shaped like ``TrialParameterResult.to_dict``.
        source_cancer_types: Cancer types the source declared for this trial;
            used by the cancer_type_subset rule (skipped when empty).

    Returns:
        Every violation found, in a stable rule order. Empty means clean.
    """
    violations: list[DeterministicViolation] = []
    violations.extend(_check_nct_format(trial))
    violations.extend(_check_required_treatment_name(trial))
    violations.extend(_check_list_shape(trial))
    violations.extend(_check_vocab_membership(trial))
    violations.extend(_check_cancer_type_subset(trial, source_cancer_types))
    violations.extend(_check_status_consistency(trial))
    return violations


def is_droppable(violations: list[DeterministicViolation]) -> bool:
    """True if any violation has severity DROP."""
    return any(v.severity == DROP for v in violations)
