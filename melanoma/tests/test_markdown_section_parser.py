"""Tests for markdown_section_parser using real cleaned publications."""
from pathlib import Path

import pytest

from src.infrastructure.markdown_section_parser import (
    SectionCategory,
    classify_header,
    parse_markdown,
)

PUBS = Path(__file__).parents[1] / "data" / "postprocessed" / "Publications"


def _read(name: str) -> str:
    return (PUBS / name).read_text()


# ---- Classifier unit tests (drive the lexicons) ----
@pytest.mark.parametrize(
    "header,expected",
    [
        ("Methods", SectionCategory.METHODS),
        ("Patients and Methods", SectionCategory.METHODS),
        ("Study Design and Treatment", SectionCategory.METHODS),
        ("Statistical Analysis", SectionCategory.METHODS),
        (
            "Trial Methodology",
            SectionCategory.METHODS,
        ),  # novel synonym must still classify
        ("Results", SectionCategory.RESULTS),
        ("Findings", SectionCategory.RESULTS),
        ("Clinical Activity", SectionCategory.RESULTS),
        ("Efficacy", SectionCategory.RESULTS),
        ("Adverse Events", SectionCategory.SAFETY),
        ("Safety", SectionCategory.SAFETY),
        ("Tolerability", SectionCategory.SAFETY),
        ("Abstract", SectionCategory.ABSTRACT),
        ("Summary", SectionCategory.ABSTRACT),
        ("Discussion", SectionCategory.DISCUSSION),
        ("Interpretation", SectionCategory.DISCUSSION),
        ("Conclusions", SectionCategory.DISCUSSION),
        ("Research in context", SectionCategory.DROP),
        ("Evidence before this study", SectionCategory.DROP),
        ("Knowledge Generated", SectionCategory.DROP),
        ("Funding", SectionCategory.DROP),
        ("References", SectionCategory.DROP),
        ("Acknowledgements", SectionCategory.DROP),
        ("Introduction", SectionCategory.DROP),
        ("Background", SectionCategory.DROP),
        ("Random nonsense header", SectionCategory.OTHER),
        # METHODS additions
        ("Purpose", SectionCategory.METHODS),
        ("Participants", SectionCategory.METHODS),
        ("Objectives", SectionCategory.METHODS),
        ("Correlative Studies", SectionCategory.METHODS),
        ("Pharmacokinetics", SectionCategory.METHODS),
        ("Pharmacodynamics", SectionCategory.METHODS),
        ("End Points", SectionCategory.METHODS),
        ("Trial Registration", SectionCategory.METHODS),
        ("Clinical Trial Registration", SectionCategory.METHODS),
        # RESULTS additions
        ("Patient Characteristics", SectionCategory.RESULTS),
        ("Patient Disposition", SectionCategory.RESULTS),
        ("Health-Related Quality of Life (QoL)", SectionCategory.RESULTS),
        # SAFETY tie-break
        ("Efficacy and Safety Assessments", SectionCategory.SAFETY),
        ("Management of Toxic Effects", SectionCategory.SAFETY),
        # DROP additions
        ("Keywords", SectionCategory.DROP),
        ("Key Words", SectionCategory.DROP),
        ("Abbreviations", SectionCategory.DROP),
        ("Conflict of Interest", SectionCategory.DROP),
        ("Article Information", SectionCategory.DROP),
    ],
)
def test_classify_header(header: str, expected: SectionCategory) -> None:
    assert classify_header(header) is expected


# ---- Parser integration tests against real fixtures ----
@pytest.mark.parametrize(
    "fname",
    [
        "Batch-II_1.md",
        "Batch-I_22.md",
        "Batch-III_3.md",
        "Batch-III_30.md",
        "Batch-III_25.md",
    ],
)
def test_required_categories_detected(fname: str) -> None:
    parsed = parse_markdown(_read(fname))
    for required in (
        SectionCategory.TITLE,
        SectionCategory.ABSTRACT,
        SectionCategory.METHODS,
        SectionCategory.RESULTS,
    ):
        text = parsed.text_for(required)
        assert text and text.strip(), f"{fname}: missing/empty {required}"


def test_drop_categories_not_in_canonical_text() -> None:
    parsed = parse_markdown(_read("Batch-II_1.md"))
    canonical_blob = "\n".join(
        parsed.text_for(c)
        for c in (
            SectionCategory.TITLE,
            SectionCategory.ABSTRACT,
            SectionCategory.METHODS,
            SectionCategory.RESULTS,
            SectionCategory.SAFETY,
        )
    )
    assert "Evidence before this study" not in canonical_blob
    assert "Implications of all the available evidence" not in canonical_blob


def test_tables_captured_with_keywords() -> None:
    parsed = parse_markdown(_read("Batch-II_1.md"))
    assert any("baseline" in t.keywords for t in parsed.tables)
    assert any(
        "survival" in t.keywords or "outcomes" in t.keywords for t in parsed.tables
    )
    assert any(
        "treatment-related" in t.keywords or "adverse" in t.keywords
        for t in parsed.tables
    )


def test_other_buckets_preserved_for_fallback() -> None:
    """Headers that don't match any category land in `other` so the router's
    positional fallback can still pull from them when canonical buckets empty."""
    md = (
        "# Title\n\n"
        "# Mystery Heading\n\nSome content goes here.\n\n"
        "# Methods\n\nMethods body.\n\n"
        "# Results\n\nResults body.\n"
    )
    parsed = parse_markdown(md)
    other = parsed.text_for(SectionCategory.OTHER)
    assert "Some content goes here" in other


def test_handles_summary_synonym_for_abstract() -> None:
    parsed = parse_markdown(_read("Batch-II_1.md"))  # uses "Summary"
    assert parsed.text_for(SectionCategory.ABSTRACT).strip()


def test_unclassified_headers_logged_for_tuning() -> None:
    """Parser exposes the unclassified header list so we can grow lexicons from real misses."""
    parsed = parse_markdown(_read("Batch-III_11.md"))
    # Every header that landed in OTHER should be visible in parsed.unclassified
    assert isinstance(parsed.unclassified, list)
