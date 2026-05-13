import pathlib
from datetime import date
from unittest.mock import patch

from src.infrastructure.news_scraper.cancernetwork import CancerNetworkScraper
from src.infrastructure.news_scraper.onclive import OncLiveScraper

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text()


class TestOncLiveSitemapScraper:
    def test_parses_articles_from_sitemap(self):
        xml = _read("onclive_sitemap.xml")
        scraper = OncLiveScraper()
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
        scraper = OncLiveScraper()
        with patch.object(scraper, "_fetch_sitemap_text", return_value=xml):
            articles = scraper.fetch_articles(since=date(2026, 4, 1))

        dates = [a.published_date for a in articles]
        assert all(d >= date(2026, 4, 1) for d in dates)
        assert date(2026, 1, 1) not in dates

    def test_returns_empty_on_fetch_failure(self):
        scraper = OncLiveScraper()
        with patch.object(scraper, "_fetch_sitemap_text", side_effect=Exception("403")):
            articles = scraper.fetch_articles(since=date(2026, 4, 1))
        assert articles == []

    def test_url_is_real_article_url(self):
        xml = _read("onclive_sitemap.xml")
        scraper = OncLiveScraper()
        with patch.object(scraper, "_fetch_sitemap_text", return_value=xml):
            articles = scraper.fetch_articles(since=date(2026, 4, 1))

        assert all(a.url.startswith("https://www.onclive.com/") for a in articles)
        assert all("news.google.com" not in a.url for a in articles)


class TestCancerNetworkScraper:
    def test_parses_articles(self):
        xml = _read("cancernetwork_rss.xml")
        scraper = CancerNetworkScraper()
        with patch.object(scraper, "_fetch_feed_text", return_value=xml):
            articles = scraper.fetch_articles(since=date(2026, 2, 7))

        assert len(articles) == 2
        assert articles[0].source == "cancernetwork"
        urls = [a.url for a in articles]
        assert (
            "https://www.cancernetwork.com/view/til-therapy-metastatic-melanoma" in urls
        )
