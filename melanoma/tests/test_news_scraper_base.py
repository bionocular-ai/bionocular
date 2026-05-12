from datetime import date

import pytest

from src.infrastructure.news_scraper.base import NewsArticleRaw
from src.infrastructure.news_scraper.cancer_filter import assign_cancer_types


def _article(title: str, description: str = "") -> NewsArticleRaw:
    return NewsArticleRaw(
        source="onclive",
        title=title,
        url="https://example.com/article",
        published_date=date(2026, 3, 1),
        description=description,
        full_text=None,
    )


def test_assigns_cutaneous_melanoma():
    article = _article("Phase 3 Pembrolizumab Results in Cutaneous Melanoma")
    types = assign_cancer_types(article)
    assert "Cutaneous Melanoma" in types


def test_assigns_uveal_melanoma():
    article = _article("Tebentafusp Doubles 5-Year Survival in Uveal Melanoma")
    types = assign_cancer_types(article)
    assert "Uveal Melanoma" in types


def test_assigns_acral_melanoma():
    article = _article("New Data for Acral Lentiginous Melanoma Treatment")
    types = assign_cancer_types(article)
    assert "Acral Melanoma" in types


def test_assigns_mucosal_melanoma():
    article = _article("Immunotherapy Results in Mucosal Melanoma Reported")
    types = assign_cancer_types(article)
    assert "Mucosal Melanoma" in types


def test_assigns_brain_cns_metastasis():
    article = _article("Melanoma Brain Metastasis Study Shows Improved Outcomes")
    types = assign_cancer_types(article)
    assert "Cutaneous Melanoma with Brain/CNS Metastasis" in types
    assert "Cutaneous Melanoma" in types  # also tagged as cutaneous


def test_assigns_cscc():
    article = _article("Anti-PD-1 in Cutaneous Squamous Cell Carcinoma Phase 2 Trial")
    types = assign_cancer_types(article)
    assert "Cutaneous Squamous Cell Carcinoma" in types


def test_assigns_cscc_by_acronym():
    article = _article("cemiplimab for cSCC Receives FDA Approval")
    types = assign_cancer_types(article)
    assert "Cutaneous Squamous Cell Carcinoma" in types


def test_assigns_bcc():
    article = _article("Vismodegib Data in Basal Cell Carcinoma")
    types = assign_cancer_types(article)
    assert "Basal Cell Carcinoma" in types


def test_assigns_mcc():
    article = _article("Avelumab Maintains OS Benefit in Merkel Cell Carcinoma")
    types = assign_cancer_types(article)
    assert "Merkel Cell Carcinoma" in types


def test_discards_unrelated():
    article = _article("Atezolizumab in NSCLC Shows PFS Benefit")
    types = assign_cancer_types(article)
    assert types == []


def test_multiple_types():
    article = _article(
        "Rare Skin Cancers: BCC and cSCC Treatment Advances"
    )
    types = assign_cancer_types(article)
    assert "Basal Cell Carcinoma" in types
    assert "Cutaneous Squamous Cell Carcinoma" in types


def test_description_fallback():
    article = _article(
        title="New Oncology Data Released",
        description="Phase 3 results in cutaneous melanoma patients show ORR of 68%.",
    )
    types = assign_cancer_types(article)
    assert "Cutaneous Melanoma" in types
