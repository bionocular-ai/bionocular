"""Deterministic validator for one extracted treatment arm.

Pure, deterministic functions. No LLM, no I/O, no network. Given a single arm
record - the shape the abstract / publication pipelines write under
``arm_results`` - return every rule violation found. An empty list means the arm
is clean on this pass.

Two kinds of rule run here:

* **Atomic format** - delegated to :mod:`value_validator`, which already knows the
  expected shape of every attribute (hazard ratio, CI range, p-value, percentage,
  median in months, NCT identifier).
* **Cross-field consistency** - relationships no single-value validator can see:
  a complete response larger than the objective response rate, a grade 3+ rate
  exceeding its all-grade total, a confidence interval that excludes its own
  hazard ratio, a survival curve that rises with time.

Each violation carries a severity:

- ``DROP`` - the arm cannot be interpreted at all; it is discarded before any LLM
  call. Reserved for *identity* failures: an arm with no name, or an impossible
  patient count. A malformed value is never a drop - the document, not the NCT,
  keys this pipeline, and a human may still want to correct the number.
- ``FLAG`` - advisory; the arm continues to the judge and lands in the review
  queue.

Mirrors ``trial_deterministic_validator`` in shape and severity vocabulary.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from ..domain.constants import ResultsValidation
from ..domain.extraction_models import AttributeType
from .value_validator import validate_for_attribute

logger = logging.getLogger(__name__)

# ---- Severities --------------------------------------------------------

DROP = "drop"  # arm cannot be interpreted -> discard before the judge runs
FLAG = "flag"  # advisory violation -> report, route to review

# ---- Rule ids ----------------------------------------------------------

_RULE_VALUE_FORMAT = "value_format"
_RULE_ARM_IDENTITY = "arm_identity"
_RULE_PATIENT_COUNT = "patient_count"
_RULE_RESPONSE_ORDERING = "response_ordering"
_RULE_AE_SUBSET = "ae_subset"
_RULE_CI_BRACKETS_HR = "ci_brackets_hr"
_RULE_RATE_MONOTONICITY = "rate_monotonicity"
_RULE_PFS_OS_ORDERING = "pfs_os_ordering"

# ---- Cross-field rule wiring -------------------------------------------

# (subset, superset) - the first value can never exceed the second.
_SUBSET_PAIRS: tuple[tuple[AttributeType, AttributeType], ...] = (
    (AttributeType.COMPLETE_RESPONSE, AttributeType.OBJECTIVE_RESPONSE_RATE),
    (AttributeType.OBJECTIVE_RESPONSE_RATE, AttributeType.DISEASE_CONTROL_RATE),
)
_AE_SUBSET_PAIRS: tuple[tuple[AttributeType, AttributeType], ...] = (
    (AttributeType.GRADE_3_PLUS_AE, AttributeType.AE),
    (AttributeType.GRADE_3_PLUS_TEAE, AttributeType.TEAE),
    (AttributeType.GRADE_3_PLUS_TRAE, AttributeType.TRAE),
    (AttributeType.GRADE_3_TEAE, AttributeType.GRADE_3_PLUS_TEAE),
    (AttributeType.GRADE_4_TEAE, AttributeType.GRADE_3_PLUS_TEAE),
    (AttributeType.GRADE_5_TEAE, AttributeType.GRADE_3_PLUS_TEAE),
    (AttributeType.GRADE_3_TRAE, AttributeType.GRADE_3_PLUS_TRAE),
    (AttributeType.GRADE_4_TRAE, AttributeType.GRADE_3_PLUS_TRAE),
    (AttributeType.GRADE_5_TRAE, AttributeType.GRADE_3_PLUS_TRAE),
)
# Survival-rate curves, ordered by timepoint. A rate can only fall over time.
_RATE_CURVES: tuple[tuple[AttributeType, ...], ...] = (
    (
        AttributeType.PFS_RATE_6M,
        AttributeType.PFS_RATE_9M,
        AttributeType.PFS_RATE_12M,
        AttributeType.PFS_RATE_18M,
        AttributeType.PFS_RATE_24M,
        AttributeType.PFS_RATE_36M,
        AttributeType.PFS_RATE_48M,
    ),
    (
        AttributeType.OS_RATE_6M,
        AttributeType.OS_RATE_9M,
        AttributeType.OS_RATE_12M,
        AttributeType.OS_RATE_18M,
        AttributeType.OS_RATE_24M,
        AttributeType.OS_RATE_36M,
        AttributeType.OS_RATE_48M,
    ),
)
# (hazard ratio, its confidence interval)
_HR_CI_PAIRS: tuple[tuple[AttributeType, AttributeType], ...] = (
    (AttributeType.HR_PFS, AttributeType.CI_HR_PFS),
    (AttributeType.HR_OS, AttributeType.CI_HR_OS),
    (AttributeType.HR_EFS, AttributeType.CI_HR_EFS),
    (AttributeType.HR_RFS, AttributeType.CI_HR_RFS),
    (AttributeType.HR_MFS, AttributeType.CI_HR_MFS),
    (AttributeType.HR_TTP, AttributeType.CI_HR_TTP),
)

_CI_RANGE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*$")
# "not reached" - a real clinical result, not a number to compare against.
_NOT_REACHED = "NR"

_ATTRIBUTE_BY_NAME: dict[str, AttributeType] = {a.value: a for a in AttributeType}


@dataclass(frozen=True)
class DeterministicViolation:
    """One rule violation found on an extracted arm."""

    field: str
    rule: str
    severity: str
    detail: str


# ---- Value helpers -----------------------------------------------------


def render_value(raw: object) -> str:
    """Render a stored attribute value as the text the validators expect."""
    if raw is None:
        return ""
    return str(raw).strip()


def has_value(rendered: str) -> bool:
    """Whether a rendered value is a real value rather than an absence sentinel."""
    return rendered.lower() not in ResultsValidation.EMPTY_VALUE_TOKENS


def _numeric(values: dict[str, str], attribute: AttributeType) -> float | None:
    """Return an attribute's value as a float, or None when absent/non-numeric.

    ``NR`` is deliberately not numeric: "not reached" is longer than any measured
    value, so comparing it as a number would invert every ordering rule.
    """
    rendered = values.get(attribute.value, "")
    if not has_value(rendered) or rendered.upper() == _NOT_REACHED:
        return None
    try:
        return float(rendered.rstrip("%").strip())
    except ValueError:
        return None


def _extracted_values(arm: dict) -> dict[str, str]:
    """Flatten ``attributes`` to ``{field_name: rendered_value}``."""
    values: dict[str, str] = {}
    for name, payload in (arm.get("attributes") or {}).items():
        raw = payload.get("value") if isinstance(payload, dict) else payload
        values[name] = render_value(raw)
    return values


# ---- Rules -------------------------------------------------------------


def _check_identity(arm: dict) -> list[DeterministicViolation]:
    """An arm must be nameable and, if counted, counted plausibly."""
    violations: list[DeterministicViolation] = []
    name = render_value(arm.get("arm_name")) or render_value(arm.get("generic_name"))
    if not has_value(name):
        violations.append(
            DeterministicViolation(
                field="arm_name",
                rule=_RULE_ARM_IDENTITY,
                severity=DROP,
                detail="arm has neither an arm_name nor a generic_name",
            )
        )

    patient_count = arm.get("patient_count")
    if patient_count is not None:
        try:
            count = int(patient_count)
        except (TypeError, ValueError):
            violations.append(
                DeterministicViolation(
                    field="patient_count",
                    rule=_RULE_PATIENT_COUNT,
                    severity=DROP,
                    detail=f"patient_count is not an integer: {patient_count!r}",
                )
            )
        else:
            if count <= 0:
                violations.append(
                    DeterministicViolation(
                        field="patient_count",
                        rule=_RULE_PATIENT_COUNT,
                        severity=DROP,
                        detail=f"patient_count must be positive, got {count}",
                    )
                )
    return violations


def _check_formats(values: dict[str, str]) -> list[DeterministicViolation]:
    """Atomic per-attribute format checks, delegated to ``value_validator``."""
    violations: list[DeterministicViolation] = []
    for name, rendered in values.items():
        if not has_value(rendered):
            continue
        attribute = _ATTRIBUTE_BY_NAME.get(name)
        if attribute is None:
            continue
        is_valid, _normalized, reason = validate_for_attribute(attribute, rendered)
        if not is_valid:
            violations.append(
                DeterministicViolation(
                    field=name,
                    rule=_RULE_VALUE_FORMAT,
                    severity=FLAG,
                    detail=f"{reason}: {rendered!r}",
                )
            )
    return violations


def _check_ordering(
    values: dict[str, str],
    pairs: tuple[tuple[AttributeType, AttributeType], ...],
    rule: str,
) -> list[DeterministicViolation]:
    """Flag every pair where the subset value exceeds its superset value."""
    violations: list[DeterministicViolation] = []
    for subset, superset in pairs:
        low = _numeric(values, subset)
        high = _numeric(values, superset)
        if low is None or high is None or low <= high:
            continue
        violations.append(
            DeterministicViolation(
                field=subset.value,
                rule=rule,
                severity=FLAG,
                detail=(
                    f"{subset.value} ({low}) exceeds {superset.value} ({high}); "
                    "the first is a subset of the second"
                ),
            )
        )
    return violations


def _check_rate_curves(values: dict[str, str]) -> list[DeterministicViolation]:
    """A survival rate at a later timepoint cannot exceed an earlier one."""
    violations: list[DeterministicViolation] = []
    for curve in _RATE_CURVES:
        previous: tuple[AttributeType, float] | None = None
        for attribute in curve:
            rate = _numeric(values, attribute)
            if rate is None:
                continue
            if previous is not None and rate > previous[1]:
                violations.append(
                    DeterministicViolation(
                        field=attribute.value,
                        rule=_RULE_RATE_MONOTONICITY,
                        severity=FLAG,
                        detail=(
                            f"{attribute.value} ({rate}) exceeds the earlier "
                            f"{previous[0].value} ({previous[1]}); a survival rate "
                            "cannot rise over time"
                        ),
                    )
                )
            previous = (attribute, rate)
    return violations


def _check_ci_brackets_hr(values: dict[str, str]) -> list[DeterministicViolation]:
    """A hazard ratio must lie inside its own confidence interval."""
    violations: list[DeterministicViolation] = []
    for hr_attribute, ci_attribute in _HR_CI_PAIRS:
        hazard_ratio = _numeric(values, hr_attribute)
        match = _CI_RANGE_RE.match(values.get(ci_attribute.value, ""))
        if hazard_ratio is None or match is None:
            continue
        low, high = float(match.group(1)), float(match.group(2))
        if low <= hazard_ratio <= high:
            continue
        violations.append(
            DeterministicViolation(
                field=ci_attribute.value,
                rule=_RULE_CI_BRACKETS_HR,
                severity=FLAG,
                detail=(
                    f"{ci_attribute.value} ({low}-{high}) does not contain "
                    f"{hr_attribute.value} ({hazard_ratio})"
                ),
            )
        )
    return violations


def _check_pfs_os_ordering(values: dict[str, str]) -> list[DeterministicViolation]:
    """Progression is an event on the way to death, so median PFS <= median OS."""
    median_pfs = _numeric(values, AttributeType.MEDIAN_PFS)
    median_os = _numeric(values, AttributeType.MEDIAN_OS)
    if median_pfs is None or median_os is None or median_pfs <= median_os:
        return []
    return [
        DeterministicViolation(
            field=AttributeType.MEDIAN_PFS.value,
            rule=_RULE_PFS_OS_ORDERING,
            severity=FLAG,
            detail=(
                f"median_pfs ({median_pfs}) exceeds median_os ({median_os}); "
                "progression precedes death"
            ),
        )
    ]


# ---- Entry points ------------------------------------------------------


def check_arm(arm: dict) -> list[DeterministicViolation]:
    """Return every deterministic violation on one extracted arm record."""
    values = _extracted_values(arm)
    violations = _check_identity(arm)
    violations.extend(_check_formats(values))
    violations.extend(_check_ordering(values, _SUBSET_PAIRS, _RULE_RESPONSE_ORDERING))
    violations.extend(_check_ordering(values, _AE_SUBSET_PAIRS, _RULE_AE_SUBSET))
    violations.extend(_check_ci_brackets_hr(values))
    violations.extend(_check_rate_curves(values))
    violations.extend(_check_pfs_os_ordering(values))
    return violations


def is_droppable(violations: list[DeterministicViolation]) -> bool:
    """Whether the arm must be discarded before the judge is asked about it."""
    return any(v.severity == DROP for v in violations)


def violation_dict(violation: DeterministicViolation) -> dict:
    """Serialise a violation for the JSON output files."""
    return {
        "field": violation.field,
        "rule": violation.rule,
        "severity": violation.severity,
        "detail": violation.detail,
    }
