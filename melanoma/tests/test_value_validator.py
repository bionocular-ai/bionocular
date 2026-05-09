"""Tests for deterministic value validators."""

import datetime as _dt

import pytest

from src.domain.extraction_models import AttributeType
from src.infrastructure.value_validator import (
    validate_ci,
    validate_for_attribute,
    validate_hr,
    validate_median_months,
    validate_nct,
    validate_p_value,
    validate_percentage,
)

# ---- HR ----------------------------------------------------------------


def test_validate_hr_passes_decimal():
    assert validate_hr("0.65") == (True, "0.65", "")


def test_validate_hr_rejects_text():
    assert validate_hr("low")[0] is False


def test_validate_hr_empty_is_valid():
    assert validate_hr("") == (True, "", "")


def test_validate_hr_rejects_nr():
    assert validate_hr("NR")[0] is False


def test_validate_hr_rejects_integer_only():
    # HR_RE requires "<digits>.<digits>"
    assert validate_hr("1")[0] is False


# ---- CI ----------------------------------------------------------------


def test_validate_ci_normalizes_to_dash():
    for raw in ["0.54-0.89", "0.54 to 0.89", "0.54, 0.89", "0.54–0.89"]:
        ok, n, _ = validate_ci(raw)
        assert ok and n == "0.54-0.89", raw


def test_validate_ci_strips_prefix():
    ok, n, _ = validate_ci("95% CI 0.42-0.64")
    assert ok and n == "0.42-0.64"


def test_validate_ci_strips_prefix_no_space():
    ok, n, _ = validate_ci("95%CI 0.42-0.64")
    assert ok and n == "0.42-0.64"


def test_validate_ci_empty_is_valid():
    assert validate_ci("") == (True, "", "")


def test_validate_ci_rejects_garbage():
    assert validate_ci("low to high")[0] is False


def test_validate_ci_strips_parens():
    ok, n, _ = validate_ci("(0.50-0.79)")
    assert ok and n == "0.50-0.79"


def test_validate_ci_with_prefix_and_to():
    ok, n, _ = validate_ci("95% CI: 0.50 to 0.79")
    assert ok and n == "0.50-0.79"


def test_validate_ci_rejects_single_decimal():
    ok, _, reason = validate_ci("0.66")
    assert not ok and "confidence interval" in reason


# ---- p-value -----------------------------------------------------------


def test_validate_p_value_decimal():
    assert validate_p_value("0.003") == (True, "0.003", "")


def test_validate_p_value_label():
    assert validate_p_value("Highly Significant")[0]


def test_validate_p_value_strips_prefix():
    ok, n, _ = validate_p_value("p=0.003")
    assert ok and n == "0.003"


def test_validate_p_value_strips_p_lt():
    ok, n, _ = validate_p_value("p<0.001")
    assert ok and n == "0.001"


def test_validate_p_value_out_of_range():
    assert validate_p_value("1.5")[0] is False


def test_validate_p_value_label_with_numeric_prefers_numeric():
    ok, n, _ = validate_p_value("Significant (p=0.003)")
    assert ok and n == "0.003"


def test_validate_p_value_empty():
    assert validate_p_value("") == (True, "", "")


def test_validate_p_value_rejects_nr():
    assert validate_p_value("NR")[0] is False


# ---- percentage --------------------------------------------------------


def test_validate_percentage_with_pct_sign():
    assert validate_percentage("45%") == (True, "45", "")


def test_validate_percentage_decimal():
    assert validate_percentage("45.7")[0]


def test_validate_percentage_over_100():
    assert validate_percentage("110")[0] is False


def test_validate_percentage_zero():
    assert validate_percentage("0")[0]


def test_validate_percentage_negative():
    assert validate_percentage("-1")[0] is False


def test_validate_percentage_empty():
    assert validate_percentage("") == (True, "", "")


def test_validate_percentage_rejects_nr():
    assert validate_percentage("NR")[0] is False


# ---- NCT ---------------------------------------------------------------


def test_validate_nct_passes():
    assert validate_nct("NCT01844505")[0]


def test_validate_nct_too_short():
    assert validate_nct("NCT123")[0] is False


def test_validate_nct_empty():
    assert validate_nct("") == (True, "", "")


def test_validate_nct_lowercase_rejected():
    assert validate_nct("nct01844505")[0] is False


# ---- median months -----------------------------------------------------


def test_validate_median_months_decimal():
    assert validate_median_months("36.9")[0]


def test_validate_median_months_integer():
    assert validate_median_months("36")[0]


def test_validate_median_months_nr():
    assert validate_median_months("NR") == (True, "NR", "")


def test_validate_median_months_nr_lowercase():
    assert validate_median_months("nr") == (True, "NR", "")


def test_validate_median_months_empty():
    assert validate_median_months("") == (True, "", "")


def test_validate_median_months_rejects_text():
    assert validate_median_months("not reached")[0] is False


# ---- dispatch ----------------------------------------------------------


def test_dispatch_hr_pfs():
    assert validate_for_attribute(AttributeType.HR_PFS, "0.65")[0]


def test_dispatch_hr_os_invalid():
    assert validate_for_attribute(AttributeType.HR_OS, "low")[0] is False


def test_dispatch_ci_normalizes():
    ok, n, _ = validate_for_attribute(AttributeType.CI_HR_PFS, "0.54 to 0.89")
    assert ok and n == "0.54-0.89"


def test_dispatch_p_value():
    ok, n, _ = validate_for_attribute(AttributeType.P_VALUE_OS, "p=0.003")
    assert ok and n == "0.003"


def test_dispatch_pfs_rate():
    assert validate_for_attribute(AttributeType.PFS_RATE_24M, "45")[0]


def test_dispatch_orr_percentage():
    assert validate_for_attribute(AttributeType.OBJECTIVE_RESPONSE_RATE, "45%")[0]


def test_dispatch_grade3_trae_percentage():
    assert validate_for_attribute(AttributeType.GRADE_3_PLUS_TRAE, "12.5%")[0]


def test_dispatch_nct():
    assert validate_for_attribute(AttributeType.NCT_NUMBER, "NCT01844505")[0]


def test_dispatch_median_pfs_nr():
    ok, n, _ = validate_for_attribute(AttributeType.MEDIAN_PFS, "nr")
    assert ok and n == "NR"


def test_dispatch_median_os_decimal():
    assert validate_for_attribute(AttributeType.MEDIAN_OS, "24.3")[0]


def test_dispatch_median_followup_pfs():
    assert validate_for_attribute(AttributeType.MEDIAN_FOLLOWUP_PFS, "12.5")[0]


def test_dispatch_unknown_passthrough():
    assert validate_for_attribute(AttributeType.TRIAL_NAME, "CheckMate-067") == (
        True,
        "CheckMate-067",
        "passthrough",
    )


def test_dispatch_empty_always_valid():
    # Empty must be valid regardless of attr family.
    for attr in (
        AttributeType.HR_PFS,
        AttributeType.CI_HR_OS,
        AttributeType.P_VALUE_PFS,
        AttributeType.OBJECTIVE_RESPONSE_RATE,
        AttributeType.NCT_NUMBER,
        AttributeType.MEDIAN_PFS,
        AttributeType.TRIAL_NAME,
    ):
        ok, n, _ = validate_for_attribute(attr, "")
        assert ok and n == "", attr


# ---- year / cancer_type / line_of_treatment ----------------------------


@pytest.mark.parametrize("v", ["1989", "2099", "20-25", "twenty twenty-four"])
def test_validate_year_rejects_out_of_range(v: str) -> None:
    ok, _, _ = validate_for_attribute(AttributeType.PUBLICATION_YEAR, v)
    assert ok is False


def test_validate_year_empty_passes_through() -> None:
    ok, normalized, _ = validate_for_attribute(AttributeType.PUBLICATION_YEAR, "")
    assert ok is True and normalized == ""


def test_validate_year_accepts_current_window() -> None:
    cur = _dt.date.today().year
    ok, normalized, _ = validate_for_attribute(AttributeType.PUBLICATION_YEAR, str(cur))
    assert ok is True and normalized == str(cur)


def test_validate_cancer_type_rejects_unknown() -> None:
    ok, _, _ = validate_for_attribute(AttributeType.CANCER_TYPE, "Hogwarts Tumor")
    assert ok is False


def test_validate_cancer_type_normalizes_melanoma() -> None:
    ok, normalized, _ = validate_for_attribute(AttributeType.CANCER_TYPE, "Melanoma")
    assert ok is True and normalized == "Cutaneous Melanoma"


def test_validate_line_of_treatment_rejects_freeform() -> None:
    ok, _, _ = validate_for_attribute(
        AttributeType.LINE_OF_TREATMENT, "second-ish line"
    )
    assert ok is False


def test_validate_line_of_treatment_accepts_canonical() -> None:
    ok, normalized, _ = validate_for_attribute(
        AttributeType.LINE_OF_TREATMENT, "1L (First Line)"
    )
    assert ok is True and normalized == "1L (First Line)"


@pytest.mark.parametrize(
    "verbose,expected_canonical",
    [
        # 1L (First Line) keywords
        ("treatment-naive patients", "1L (First Line)"),
        ("front-line setting", "1L (First Line)"),
        ("untreated advanced melanoma", "1L (First Line)"),
        ("de novo metastatic disease", "1L (First Line)"),
        ("1Line (1L) / First-Line Modalities", "1L (First Line)"),
        ("1st line / first of care", "1L (First Line)"),
        ("1 line (prior therapies, max, min) | 1 line", "1L (First Line)"),
        # 2L (Second Line) keywords
        ("second-line therapy", "2L (Second Line)"),
        ("2nd-line setting", "2L (Second Line)"),
        ("failed 1L treatment", "2L (Second Line)"),
        # 2L+ (Refractory) keywords
        ("relapsed or refractory patients", "2L+ (Refractory)"),
        ("2L+ prior therapy", "2L+ (Refractory)"),
        ("previously treated cohort", "2L+ (Refractory)"),
        ("pre-treated population", "2L+ (Refractory)"),
        ("multi-line refractory", "2L+ (Refractory)"),
        # 3L+ (Third Line+) keywords
        ("salvage chemotherapy", "3L+ (Third Line+)"),
        ("heavily pre-treated patients", "3L+ (Third Line+)"),
        ("third-line or later", "3L+ (Third Line+)"),
        ("at least two prior lines", "3L+ (Third Line+)"),
        # Adjuvant keywords
        ("adjuvant phase", "Adjuvant"),
        ("post-operative consolidation", "Adjuvant"),
        ("maintenance therapy post-resection", "Adjuvant"),
        # Neoadjuvant keywords
        ("neoadjuvant treatment", "Neoadjuvant"),
        ("pre-operative induction", "Neoadjuvant"),
        ("resectable stage III disease", "Neoadjuvant"),
    ],
)
def test_validate_line_of_treatment_normalizes_verbose(
    verbose: str, expected_canonical: str
) -> None:
    ok, normalized, _ = validate_for_attribute(AttributeType.LINE_OF_TREATMENT, verbose)
    assert ok is True and normalized == expected_canonical
