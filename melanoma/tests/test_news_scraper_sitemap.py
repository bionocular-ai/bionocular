import pathlib
from datetime import date
from unittest.mock import patch

import pytest

from src.infrastructure.news_scraper.sitemap_news import NewsSitemapScraper

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text()


def _onclive() -> NewsSitemapScraper:
    return NewsSitemapScraper("onclive", "https://www.onclive.com/sitemap-news.xml")


class TestNewsSitemapScraper:
    def test_parses_articles_from_sitemap(self):
        xml = _read("onclive_sitemap.xml")
        scraper = _onclive()
        with patch.object(scraper, "_fetch_sitemap_text", return_value=xml):
            articles = scraper.fetch_articles(since=date(2026, 4, 1))

        assert len(articles) == 2
        urls = [a.url for a in articles]
        assert (
            "https://www.onclive.com/view/nivolumab-ipilimumab-melanoma-os-update"
            in urls
        )
        nivo = next(a for a in articles if "nivolumab" in a.url)
        assert (
            nivo.title
            == "Nivolumab Plus Ipilimumab Demonstrates Durable OS in Advanced Melanoma"
        )
        assert nivo.published_date == date(2026, 5, 7)
        assert nivo.source == "onclive"

    def test_filters_by_since_date(self):
        xml = _read("onclive_sitemap.xml")
        scraper = _onclive()
        with patch.object(scraper, "_fetch_sitemap_text", return_value=xml):
            articles = scraper.fetch_articles(since=date(2026, 4, 1))

        dates = [a.published_date for a in articles]
        assert all(d >= date(2026, 4, 1) for d in dates)
        assert date(2026, 1, 1) not in dates

    def test_raises_on_fetch_failure(self):
        scraper = _onclive()
        with (
            patch.object(scraper, "_fetch_sitemap_text", side_effect=Exception("403")),
            pytest.raises(Exception, match="403"),
        ):
            scraper.fetch_articles(since=date(2026, 4, 1))

    def test_url_is_real_article_url(self):
        xml = _read("onclive_sitemap.xml")
        scraper = _onclive()
        with patch.object(scraper, "_fetch_sitemap_text", return_value=xml):
            articles = scraper.fetch_articles(since=date(2026, 4, 1))

        assert all(a.url.startswith("https://www.onclive.com/") for a in articles)
        assert all("news.google.com" not in a.url for a in articles)
