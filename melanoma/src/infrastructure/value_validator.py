"""Deterministic value validators for extracted attribute strings.

Pure functions. No I/O. Each validator returns
``(is_valid, normalized_value, reason)``.

Conventions:
- Empty string ``""`` is ALWAYS valid (the LLM's "not stated for this arm" /
  null sentinel). It returns ``(True, "", "")``.
- ``"NR"`` (case-insensitive) is valid ONLY for median-survival/follow-up
  fields, where it normalizes to ``"NR"``. For HR / CI / p-value /
  percentage it is invalid.
"""

from __future__ import annotations

import datetime as _dt
import re

from ..domain.extraction_models import AttributeType

# ---- Regex constants ---------------------------------------------------

HR_RE = re.compile(r"^\d+\.\d+$")
CI_RE = re.compile(r"^\d+\.\d+\s*[-–]\s*\d+\.\d+$")
NCT_RE = re.compile(r"^NCT\d{8}$")
PCT_RE = re.compile(r"^\d+(\.\d+)?$")

# Strip leading "95% CI" / "95%CI" / "CI" (case-insensitive).
_CI_PREFIX_RE = re.compile(r"^\s*(?:95\s*%?\s*)?CI\s*[:=]?\s*", re.IGNORECASE)
# Strip leading "p=", "p<", "p >=" etc.
_P_PREFIX_RE = re.compile(r"^\s*p\s*[<>=]+\s*", re.IGNORECASE)
# Find a numeric token inside a label like "Significant (p=0.003)".
_P_NUMERIC_IN_TEXT_RE = re.compile(r"p\s*[<>=]+\s*(\d*\.?\d+)", re.IGNORECASE)

P_VALUE_LABELS: frozenset[str] = frozenset(
    {"Non-Significant", "Significant", "Highly Significant"}
)

# ---- Result type -------------------------------------------------------

Result = tuple[bool, str, str]


# ---- Atomic validators -------------------------------------------------


def validate_hr(v: str) -> Result:
    """Hazard ratio: a positive decimal like ``0.65``."""
    if v == "":
        return (True, "", "")
    s = v.strip()
    if HR_RE.match(s):
        return (True, s, "")
    return (False, v, "not a decimal hazard ratio")


def validate_ci(v: str) -> Result:
    """Confidence interval. Accepts hyphen, en-dash, ``to``, or comma
    separator. Strips an optional leading ``95% CI`` prefix. Normalizes
    to ``"low-high"`` with an ASCII hyphen."""
    if v == "":
        return (True, "", "")
    s = _CI_PREFIX_RE.sub("", v.strip())
    if s.startswith("(") and s.endswith(")"):
        s = s[1:-1].strip()
    # Normalize separators to a hyphen.
    s_norm = re.sub(r"\s*(?:to|,|–|-)\s*", "-", s, count=1)
    if CI_RE.match(s_norm):
        # Re-canonicalize: collapse whitespace around the dash and use ASCII '-'.
        m = re.match(r"^(\d+\.\d+)\s*[-–]\s*(\d+\.\d+)$", s_norm)
        if m:
            return (True, f"{m.group(1)}-{m.group(2)}", "")
    return (False, v, "not a confidence interval")


def validate_p_value(v: str) -> Result:
    """p-value: a decimal in [0, 1] OR one of the canonical labels.

    If both a label and a numeric appear (e.g. ``"Significant (p=0.003)"``),
    prefer the numeric.
    """
    if v == "":
        return (True, "", "")
    s = v.strip()

    # Prefer embedded numeric if present.
    m = _P_NUMERIC_IN_TEXT_RE.search(s)
    if m:
        candidate = m.group(1)
        try:
            f = float(candidate)
        except ValueError:
            f = -1.0
        if 0.0 <= f <= 1.0:
            return (True, candidate, "")
        return (False, v, "p-value out of [0,1]")

    # Try a bare label.
    if s in P_VALUE_LABELS:
        return (True, s, "")

    # Strip a leading "p=" / "p<" / "%" then re-check as decimal.
    stripped = _P_PREFIX_RE.sub("", s)
    stripped = stripped.rstrip("%").strip()
    try:
        f = float(stripped)
    except ValueError:
        return (False, v, "not a p-value")
    if 0.0 <= f <= 1.0:
        return (True, stripped, "")
    return (False, v, "p-value out of [0,1]")


def validate_percentage(v: str) -> Result:
    """Percentage in ``[0, 100]``. Strips trailing ``%``."""
    if v == "":
        return (True, "", "")
    s = v.strip().rstrip("%").strip()
    if not PCT_RE.match(s):
        return (False, v, "not a percentage")
    try:
        f = float(s)
    except ValueError:
        return (False, v, "not a percentage")
    if 0.0 <= f <= 100.0:
        return (True, s, "")
    return (False, v, "percentage out of [0,100]")


def validate_nct(v: str) -> Result:
    """ClinicalTrials.gov NCT identifier: ``NCT`` + 8 digits."""
    if v == "":
        return (True, "", "")
    s = v.strip()
    if NCT_RE.match(s):
        return (True, s, "")
    return (False, v, "not an NCT identifier")


def validate_median_months(v: str) -> Result:
    """Median survival/follow-up in months: a non-negative number OR
    ``NR`` ("not reached", case-insensitive, normalized to upper)."""
    if v == "":
        return (True, "", "")
    s = v.strip()
    if s.upper() == "NR":
        return (True, "NR", "")
    if not PCT_RE.match(s):
        return (False, v, "not a numeric median in months")
    try:
        f = float(s)
    except ValueError:
        return (False, v, "not a numeric median in months")
    if f < 0:
        return (False, v, "negative median")
    return (True, s, "")


# ---- Attribute family dispatch ----------------------------------------

_HR_ATTRS: frozenset[AttributeType] = frozenset(
    {
        AttributeType.HR_PFS,
        AttributeType.HR_OS,
        AttributeType.HR_EFS,
        AttributeType.HR_RFS,
        AttributeType.HR_MFS,
        AttributeType.HR_TTP,
    }
)

_CI_ATTRS: frozenset[AttributeType] = frozenset(
    {
        AttributeType.CI_HR_PFS,
        AttributeType.CI_HR_OS,
        AttributeType.CI_HR_EFS,
        AttributeType.CI_HR_RFS,
        AttributeType.CI_HR_MFS,
        AttributeType.CI_HR_TTP,
    }
)

_P_VALUE_ATTRS: frozenset[AttributeType] = frozenset(
    {
        AttributeType.P_VALUE_PFS,
        AttributeType.P_VALUE_OS,
        AttributeType.P_VALUE_EFS,
        AttributeType.P_VALUE_RFS,
    }
)

_MEDIAN_MONTHS_ATTRS: frozenset[AttributeType] = frozenset(
    {
        AttributeType.MEDIAN_OS,
        AttributeType.MEDIAN_PFS,
        AttributeType.MEDIAN_DOR,
        AttributeType.MEDIAN_FOLLOWUP_PFS,
        AttributeType.MEDIAN_FOLLOWUP_OS,
    }
)


def _build_percentage_attrs() -> frozenset[AttributeType]:
    """All attributes whose value is reported as a 0-100 percentage."""
    explicit = {
        # Response rates
        AttributeType.OBJECTIVE_RESPONSE_RATE,
        AttributeType.COMPLETE_RESPONSE,
        AttributeType.PATHOLOGICAL_COMPLETE_RESPONSE,
        AttributeType.COMPLETE_METABOLIC_RESPONSE,
        AttributeType.DISEASE_CONTROL_RATE,
        AttributeType.CLINICAL_BENEFIT_RATE,
        AttributeType.DOR_RATE,
        # PFS / OS rates at timepoints
        AttributeType.PFS_RATE_6M,
        AttributeType.PFS_RATE_9M,
        AttributeType.PFS_RATE_12M,
        AttributeType.PFS_RATE_18M,
        AttributeType.PFS_RATE_24M,
        AttributeType.PFS_RATE_36M,
        AttributeType.PFS_RATE_48M,
        AttributeType.OS_RATE_6M,
        AttributeType.OS_RATE_9M,
        AttributeType.OS_RATE_12M,
        AttributeType.OS_RATE_18M,
        AttributeType.OS_RATE_24M,
        AttributeType.OS_RATE_36M,
        AttributeType.OS_RATE_48M,
        # Other survival endpoints reported as %
        AttributeType.EFS,
        AttributeType.RFS,
        AttributeType.MFS,
        # Time-to metrics reported as % at landmark
        AttributeType.TTR,
        AttributeType.TTP,
        AttributeType.TTNT,
        AttributeType.TTF,
    }
    # All AE / TEAE / TRAE rate fields are percentages. They are exactly the
    # AttributeType members whose name starts with one of these prefixes.
    ae_prefixes = (
        "AE",
        "GRADE_",
        "SERIOUS_",
        "TEAE",
        "TRAE",
        "CRS",
        "IRR",
        "WBC_",
        "IMMUNE_RELATED_AE",
    )
    for attr in AttributeType:
        if any(attr.name.startswith(p) for p in ae_prefixes):
            explicit.add(attr)
    return frozenset(explicit)


_PERCENTAGE_ATTRS: frozenset[AttributeType] = _build_percentage_attrs()

_CANCER_TYPES: frozenset[str] = frozenset(
    {
        "melanoma",
        "uveal melanoma",
        "cutaneous melanoma",
        "mucosal melanoma",
        "merkel cell carcinoma",
        "cutaneous squamous cell carcinoma",
        "basal cell carcinoma",
    }
)

_LINES_OF_TREATMENT: frozenset[str] = frozenset(
    {
        # Prompt canonical values (IDENTIFICATION prompt instructs LLM to output these)
        "first_line",
        "second_line",
        "third_line_plus",
        "adjuvant",
        "neoadjuvant",
        "maintenance",
        "unknown",
        # Short-form aliases the LLM may also produce
        "1L",
        "2L",
        "3L",
        "4L",
        "1L+",
        "2L+",
        "3L+",
        "4L+",
        "first-line",
        "second-line",
        "third-line",
        "fourth-line",
        "perioperative",
    }
)

# Normalization patterns: map verbose/messy LLM output to a canonical value.
# Ordered most-specific first (neoadjuvant before adjuvant, third before second/first).
_LINE_NORMALIZE: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bneo[- ]?adjuvant\b", re.I), "neoadjuvant"),
    (re.compile(r"\badjuvant\b", re.I), "adjuvant"),
    (re.compile(r"\bmaintenance\b", re.I), "maintenance"),
    (
        re.compile(r"\b(?:third|3rd)[- ]?line\b|\b[34]L\+?\b", re.I),
        "third_line_plus",
    ),
    (
        re.compile(
            r"\b(?:second|2nd)[- ]?line\b|\b2L\+?\b|\br/?r\b|relapsed.{0,5}refractory",
            re.I,
        ),
        "second_line",
    ),
    (
        re.compile(r"\b(?:first|1st|1)[- ]?line\b|\b1L\b", re.I),
        "first_line",
    ),
    (re.compile(r"\bunknown\b", re.I), "unknown"),
]


def validate_year(v: str) -> Result:
    if v == "":
        return (True, "", "")
    s = v.strip()
    if not re.fullmatch(r"\d{4}", s):
        return (False, v, "year is not a 4-digit integer")
    y = int(s)
    cur = _dt.date.today().year
    if 1990 <= y <= cur + 1:
        return (True, s, "")
    return (False, v, f"year {y} outside [1990, {cur + 1}]")


def validate_cancer_type(v: str) -> Result:
    if v == "":
        return (True, "", "")
    s = v.strip()
    if s.lower() in _CANCER_TYPES:
        return (True, s, "")
    return (False, v, "cancer_type not in controlled vocabulary")


def validate_line_of_treatment(v: str) -> Result:
    if v == "":
        return (True, "", "")
    s = v.strip()
    if s in _LINES_OF_TREATMENT:
        return (True, s, "")
    # LLMs often emit verbose strings like "1Line (1L) / First-Line Modalities"
    # or "1st line / first of care". Try normalization patterns before rejecting.
    for pat, canonical in _LINE_NORMALIZE:
        if pat.search(s):
            return (True, canonical, "")
    return (False, v, "line_of_treatment not in controlled vocabulary")


def validate_for_attribute(attr: AttributeType, v: str) -> Result:
    """Dispatch to the correct validator based on attribute family.

    Identification / free-text attrs (trial name, drug name, etc.) have no
    enforceable format and pass through unchanged.
    """
    if v == "":
        return (True, "", "")
    if attr in _HR_ATTRS:
        return validate_hr(v)
    if attr in _CI_ATTRS:
        return validate_ci(v)
    if attr in _P_VALUE_ATTRS:
        return validate_p_value(v)
    if attr is AttributeType.NCT_NUMBER:
        return validate_nct(v)
    if attr in (AttributeType.PUBLICATION_YEAR, AttributeType.PUBLISHED_YEAR):
        return validate_year(v)
    if attr is AttributeType.CANCER_TYPE:
        return validate_cancer_type(v)
    if attr is AttributeType.LINE_OF_TREATMENT:
        return validate_line_of_treatment(v)
    if attr in _MEDIAN_MONTHS_ATTRS:
        return validate_median_months(v)
    if attr in _PERCENTAGE_ATTRS:
        return validate_percentage(v)
    return (True, v, "passthrough")
