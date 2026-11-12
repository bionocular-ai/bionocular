"""Tests for the ASH Crossref-to-markdown adapter."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from ash_crossref_to_md import (  # noqa: E402
    abstract_number,
    jats_to_sections,
    render_abstract,
)


def p(text):
    return f"<jats:p>{text}</jats:p>"


def test_paragraph_opener_becomes_heading():
    assert jats_to_sections(p("Introduction LINVO is...")) == [("Introduction", "LINVO is...")]


def test_heading_variants_and_typos():
    cases = {
        "Study design and methods": "Methods",
        "Patients and methods": "Methods",
        "Background and significance": "Background",
        "Resullts": "Results",
        "Backgroud": "Background",
        "Conclusions：": "Conclusions",
    }
    for opener, canon in cases.items():
        assert jats_to_sections(p(f"{opener} Some text here.")) == [(canon, "Some text here.")]


def test_efficacy_paragraph_stays_in_results():
    out = jats_to_sections(p("Results Enrolled 10 pts.") + p("Efficacy ORR was 80%"))
    assert out == [("Results", "Enrolled 10 pts."), (None, "Efficacy ORR was 80%")]


def test_unknown_opener_keeps_text():
    assert jats_to_sections(p("Funding This work...")) == [(None, "Funding This work...")]


def test_entities_tags_whitespace():
    out = jats_to_sections(
        p("P&lt; 0.001 in <jats:italic>TP53</jats:italic>\n      mutant   cells")
    )
    assert out == [(None, "P< 0.001 in TP53 mutant cells")]


def test_reference_list_stripped():
    refs = "Zhang Y, Yin Z, Li X. Ther Adv Hematol. 2025;16:"
    out = jats_to_sections(p("Methods We did x.") + p(refs))
    assert out == [("Methods", "We did x.")]
    out = jats_to_sections(p("Methods We did x.") + p("References 1. Foo"))
    assert out == [("Methods", "We did x.")]


def test_render_format():
    md = render_abstract("94", "A title", [("Methods", "We did x."), (None, "Plain.")])
    assert md.startswith("### Abstract ID: 94\n\n#### Title:\nA title\n")
    assert "#### Methods:\nWe did x." in md
    assert "Plain." in md


def test_abstract_number():
    assert abstract_number("10.1182/blood-2025-2254") == "2254"
    assert abstract_number("10.1182/blood.2025028935") is None
