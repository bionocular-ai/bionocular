from datetime import date

from src.infrastructure.news_scraper.base import NewsArticleRaw
from src.infrastructure.news_scraper.cancer_filter import assign_cancer_types


def _article(title: str, description: str = "") -> NewsArticleRaw:
    return NewsArticleRaw(
        source="test",
        title=title,
        url="https://example.com",
        published_date=date(2026, 1, 1),
        description=description,
        full_text=None,
    )


# Bug 1: uveal/acral/mucosal must NOT get Cutaneous Melanoma
def test_uveal_melanoma_not_tagged_as_cutaneous():
    result = assign_cancer_types(_article("Phase III trial in uveal melanoma"))
    assert "Uveal Melanoma" in result
    assert "Cutaneous Melanoma" not in result


def test_acral_melanoma_not_tagged_as_cutaneous():
    result = assign_cancer_types(_article("New treatment for acral melanoma"))
    assert "Acral Melanoma" in result
    assert "Cutaneous Melanoma" not in result


def test_mucosal_melanoma_not_tagged_as_cutaneous():
    result = assign_cancer_types(_article("Mucosal melanoma response rates in phase II"))
    assert "Mucosal Melanoma" in result
    assert "Cutaneous Melanoma" not in result


def test_article_mentioning_both_uveal_and_cutaneous():
    result = assign_cancer_types(_article("Comparing uveal melanoma vs cutaneous melanoma"))
    assert "Uveal Melanoma" in result
    assert "Cutaneous Melanoma" in result


def test_generic_melanoma_still_gets_cutaneous():
    result = assign_cancer_types(_article("Pembrolizumab improves PFS in advanced melanoma"))
    assert "Cutaneous Melanoma" in result


# Bug 2: "rare melanoma" → all three rare subtypes, not Cutaneous
def test_rare_melanoma_assigns_all_three_rare_subtypes():
    result = assign_cancer_types(
        _article("Rare Melanoma Trial Serves as Model for Advancing Cancer Immunotherapy")
    )
    assert "Uveal Melanoma" in result
    assert "Acral Melanoma" in result
    assert "Mucosal Melanoma" in result
    assert "Cutaneous Melanoma" not in result


# Bug 3: "brain-metastatic melanoma" → Brain/CNS tag
def test_brain_metastatic_melanoma_gets_brain_cns_tag():
    result = assign_cancer_types(
        _article("Considering Lifileucel Use in Patients With Brain-Metastatic Melanoma")
    )
    assert "Cutaneous Melanoma with Brain/CNS Metastasis" in result
    assert "Cutaneous Melanoma" in result


# Regression: standard brain/CNS keyword still works
def test_brain_cns_gets_both_tags():
    result = assign_cancer_types(_article("Melanoma brain metastasis trial results"))
    assert "Cutaneous Melanoma with Brain/CNS Metastasis" in result
    assert "Cutaneous Melanoma" in result
