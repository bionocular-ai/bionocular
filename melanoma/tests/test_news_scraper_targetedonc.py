import pathlib
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.news_scraper.targetedonc import TargetedOncScraper

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


class TestTargetedOncScraper:
    def test_parses_articles_from_gnews(self):
        xml = (FIXTURES / "targetedonc_gnews.xml").read_text()
        scraper = TargetedOncScraper()

        def mock_resolve(url: str) -> str:
            mapping = {
                "https://news.google.com/rss/articles/CBMiogFBVV95cUxQ": "https://www.targetedonc.com/view/doc1021-fast-track-melanoma",
                "https://news.google.com/rss/articles/CBMiogFBVV95cUxR": "https://www.targetedonc.com/view/tebentafusp-uveal-melanoma",
            }
            return mapping.get(url, url)

        with (
            patch.object(scraper, "_fetch_gnews_text", return_value=xml),
            patch.object(scraper, "_resolve_redirect", side_effect=mock_resolve),
        ):
            articles = scraper.fetch_articles(since=date(2026, 2, 7))

        assert len(articles) == 2
        urls = [a.url for a in articles]
        assert "https://www.targetedonc.com/view/doc1021-fast-track-melanoma" in urls
        assert "https://www.targetedonc.com/view/tebentafusp-uveal-melanoma" in urls

    def test_article_source_is_targetedonc(self):
        xml = (FIXTURES / "targetedonc_gnews.xml").read_text()
        scraper = TargetedOncScraper()
        with (
            patch.object(scraper, "_fetch_gnews_text", return_value=xml),
            patch.object(scraper, "_resolve_redirect", side_effect=lambda url: url),
        ):
            articles = scraper.fetch_articles(since=date(2026, 2, 7))
        assert all(a.source == "targetedonc" for a in articles)

    def test_filters_by_date(self):
        xml = (FIXTURES / "targetedonc_gnews.xml").read_text()
        scraper = TargetedOncScraper()
        with (
            patch.object(scraper, "_fetch_gnews_text", return_value=xml),
            patch.object(scraper, "_resolve_redirect", side_effect=lambda url: url),
        ):
            articles = scraper.fetch_articles(since=date(2026, 5, 1))

        assert len(articles) == 1
        assert "DOC1021" in articles[0].title

    def test_deduplicates_by_url(self):
        xml = (FIXTURES / "targetedonc_gnews.xml").read_text()
        scraper = TargetedOncScraper()
        with (
            patch.object(scraper, "_fetch_gnews_text", return_value=xml),
            patch.object(scraper, "_resolve_redirect", side_effect=lambda url: url),
        ):
            articles = scraper.fetch_articles(since=date(2026, 2, 7))
        urls = [a.url for a in articles]
        assert len(urls) == len(set(urls))

    def test_falls_back_to_google_url_on_redirect_failure(self):
        xml = (FIXTURES / "targetedonc_gnews.xml").read_text()
        scraper = TargetedOncScraper()

        def raise_on_resolve(url: str) -> str:
            raise Exception("timeout")

        with (
            patch.object(scraper, "_fetch_gnews_text", return_value=xml),
            patch.object(scraper, "_resolve_redirect", side_effect=raise_on_resolve),
        ):
            articles = scraper.fetch_articles(since=date(2026, 2, 7))

        assert any(a.url.startswith("https://news.google.com") for a in articles)
