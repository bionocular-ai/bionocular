import pathlib
from datetime import date
from unittest.mock import patch

from src.infrastructure.news_scraper.biospace import BioSpaceScraper

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


class TestBioSpaceScraper:
    def test_parses_skin_cancer_articles(self):
        html = (FIXTURES / "biospace_cancer.html").read_text()
        scraper = BioSpaceScraper()
        with patch.object(scraper, "_fetch_page_html", return_value=html):
            articles = scraper.fetch_articles(since=date(2026, 2, 7))

        titles = [a.title for a in articles]
        assert any("Merkel Cell Carcinoma" in t for t in titles)
        assert any("squamous cell carcinoma" in t.lower() for t in titles)

    def test_excludes_non_skin_cancer(self):
        html = (FIXTURES / "biospace_cancer.html").read_text()
        scraper = BioSpaceScraper()
        with patch.object(scraper, "_fetch_page_html", return_value=html):
            articles = scraper.fetch_articles(since=date(2026, 2, 7))

        titles = [a.title for a in articles]
        assert not any("Diabetes" in t for t in titles)

    def test_filters_by_date(self):
        html = (FIXTURES / "biospace_cancer.html").read_text()
        scraper = BioSpaceScraper()
        with patch.object(scraper, "_fetch_page_html", return_value=html):
            articles = scraper.fetch_articles(since=date(2026, 2, 7))

        assert not any("Old Melanoma" in a.title for a in articles)

    def test_article_fields(self):
        html = (FIXTURES / "biospace_cancer.html").read_text()
        scraper = BioSpaceScraper()
        with patch.object(scraper, "_fetch_page_html", return_value=html):
            articles = scraper.fetch_articles(since=date(2026, 2, 7))

        mcc_article = next(a for a in articles if "Merkel" in a.title)
        assert mcc_article.source == "biospace"
        assert mcc_article.published_date == date(2026, 5, 8)
        assert mcc_article.url == "https://www.biospace.com/avelumab-merkel-cell-carcinoma-3year-os"
        assert "JAVELIN" in mcc_article.description

    def test_returns_empty_on_fetch_failure(self):
        scraper = BioSpaceScraper()
        with patch.object(scraper, "_fetch_page_html", side_effect=Exception("timeout")):
            articles = scraper.fetch_articles(since=date(2026, 2, 7))
        assert articles == []
