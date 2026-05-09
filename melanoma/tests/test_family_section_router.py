"""Tests for family_section_router."""
from pathlib import Path

import pytest

from src.domain.extraction_models import AttributeFamily
from src.infrastructure.family_section_router import slice_for_family
from src.infrastructure.markdown_section_parser import (
    ParsedDoc,
    SectionCategory,
    parse_markdown,
)

PUBS = Path(__file__).parents[1] / "data" / "postprocessed" / "Publications"


@pytest.fixture
def parsed_combi_d():
    return parse_markdown((PUBS / "Batch-II_1.md").read_text())


def test_identification_includes_title_and_methods(parsed_combi_d) -> None:
    s = slice_for_family(AttributeFamily.IDENTIFICATION, parsed_combi_d, raw_md="")
    assert "Dabrafenib and trametinib" in s
    assert "NCT01584648" in s  # NCT lives in Methods
    assert "Discussion" not in s


def test_pfs_includes_results_efficacy_table(parsed_combi_d) -> None:
    s = slice_for_family(AttributeFamily.PFS_FAMILY, parsed_combi_d, raw_md="")
    assert "progression-free survival" in s.lower() or "PFS" in s
    assert "Table 2" in s or "11.0" in s


def test_efs_skipped_when_no_anchor(parsed_combi_d) -> None:
    # COMBI-d has no EFS/RFS/MFS — router returns None to signal skip.
    s = slice_for_family(AttributeFamily.EFS_RFS_MFS, parsed_combi_d, raw_md="")
    assert s is None


def test_time_to_metrics_skipped_when_no_anchor(parsed_combi_d) -> None:
    # COMBI-d reports PFS/OS but no TTR/TTP/TTNT/TTF — router skips.
    s = slice_for_family(AttributeFamily.TIME_TO_METRICS, parsed_combi_d, raw_md="")
    assert s is None


def test_safety_table_included_for_ae_general(parsed_combi_d) -> None:
    s = slice_for_family(AttributeFamily.AE_GENERAL, parsed_combi_d, raw_md="")
    assert "Treatment-related adverse events" in s or "treatment-related" in s.lower()
    assert "Table 3" in s


def test_trae_includes_methods_ae_classification(parsed_combi_d) -> None:
    s = slice_for_family(AttributeFamily.TRAE_GENERAL, parsed_combi_d, raw_md="")
    assert "treatment-related" in s.lower()
    assert "Common Terminology Criteria" in s or "Adverse events were graded" in s


# ---- Fallback paths ----
def test_methods_fallback_positional_when_missing() -> None:
    """Doc with no Methods-classified header: router must still return non-empty for IDENTIFICATION."""
    # Build a parsed doc with empty Methods.
    parsed = ParsedDoc()
    parsed.by_category[SectionCategory.TITLE].append("Title here")
    parsed.by_category[SectionCategory.ABSTRACT].append(
        "Abstract content. NCT99999999."
    )
    parsed.by_category[SectionCategory.RESULTS].append("Results content with PFS data.")
    raw_md = (
        "# Title here\n\n# Abstract\nAbstract content. NCT99999999.\n\n"
        "# Trial Methodology\nDetailed methodology including NCT00000001 and inclusion criteria.\n\n"
        "# Results\nResults content with PFS data.\n"
    )
    s = slice_for_family(AttributeFamily.IDENTIFICATION, parsed, raw_md=raw_md)
    assert s
    # Fallback should pull from positional middle of raw_md, surfacing the methodology paragraph.
    assert "methodology" in s.lower() or "inclusion criteria" in s.lower()


def test_results_fallback_picks_from_other_when_classified_empty() -> None:
    parsed = ParsedDoc()
    parsed.by_category[SectionCategory.TITLE].append("T")
    parsed.by_category[SectionCategory.ABSTRACT].append("A")
    parsed.by_category[SectionCategory.OTHER].append(
        "Clinical Activity: ORR was 45% (95% CI 33-58). Median PFS 9.2 months."
    )
    raw_md = "# T\n# A\nA\n# Clinical Activity\nORR was 45% (95% CI 33-58). Median PFS 9.2 months.\n"
    s = slice_for_family(AttributeFamily.PFS_FAMILY, parsed, raw_md=raw_md)
    assert "9.2 months" in s


def test_safety_fallback_grep_when_no_safety_section() -> None:
    parsed = ParsedDoc()
    parsed.by_category[SectionCategory.RESULTS].append(
        "Patients responded well. Grade 3 adverse events were reported in 22%."
    )
    raw_md = "# Results\nPatients responded well. Grade 3 adverse events were reported in 22%.\n"
    s = slice_for_family(AttributeFamily.AE_GENERAL, parsed, raw_md=raw_md)
    assert "adverse events" in s.lower()
    assert "22%" in s


def test_other_content_always_included_in_slices() -> None:
    """OTHER-bucketed content must appear in every family slice regardless of keyword match."""
    parsed = ParsedDoc()
    parsed.by_category[SectionCategory.TITLE].append("Some Trial")
    parsed.by_category[SectionCategory.ABSTRACT].append("Abstract text.")
    parsed.by_category[SectionCategory.RESULTS].append("ORR was 45%.")
    parsed.by_category[SectionCategory.OTHER].append(
        "Key Points\n\nFindings: Median OS was 24.3 months (95% CI 18.1–31.2)."
    )
    raw_md = ""

    for family in [
        AttributeFamily.IDENTIFICATION,
        AttributeFamily.RESPONSE_RATES,
        AttributeFamily.PFS_FAMILY,
        AttributeFamily.OS_FAMILY,
        AttributeFamily.AE_GENERAL,
        AttributeFamily.AE_GRADE3_SPECIFIC,
    ]:
        s = slice_for_family(family, parsed, raw_md=raw_md)
        assert s is not None, f"{family}: returned None unexpectedly"
        assert "24.3 months" in s, f"{family}: OTHER content not included in slice"

    # When RESULTS is classified (non-empty), OTHER must appear exactly once — no duplication.
    s = slice_for_family(AttributeFamily.PFS_FAMILY, parsed, raw_md=raw_md)
    assert s is not None
    assert s.count("24.3 months") == 1, "OTHER content duplicated in slice"
