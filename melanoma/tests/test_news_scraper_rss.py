import pathlib
from datetime import date
from unittest.mock import patch

import pytest

from src.infrastructure.news_scraper.onclive import OncLiveScraper
from src.infrastructure.news_scraper.cancernetwork import CancerNetworkScraper

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text()


class TestOncLiveScraper:
    def test_parses_articles_since_cutoff(self):
        xml = _read("onclive_rss.xml")
        scraper = OncLiveScraper()
        with patch.object(scraper, "_fetch_feed_text", return_value=xml):
            articles = scraper.fetch_articles(since=date(2026, 2, 7))

        urls = [a.url for a in articles]
        assert "https://www.onclive.com/view/phase-3-pembro-melanoma" in urls
        assert "https://www.onclive.com/view/avelumab-mcc" in urls
        assert "https://www.onclive.com/view/lung-cancer-io" not in urls

    def test_article_fields(self):
        xml = _read("onclive_rss.xml")
        scraper = OncLiveScraper()
        with patch.object(scraper, "_fetch_feed_text", return_value=xml):
            articles = scraper.fetch_articles(since=date(2026, 2, 7))

        art = next(a for a in articles if "pembro" in a.url)
        assert art.source == "onclive"
        assert "Pembrolizumab" in art.title
        assert art.published_date == date(2026, 5, 11)
        assert "NCT12345678" in art.description
        assert art.full_text is None

    def test_empty_when_all_old(self):
        xml = _read("onclive_rss.xml")
        scraper = OncLiveScraper()
        with patch.object(scraper, "_fetch_feed_text", return_value=xml):
            articles = scraper.fetch_articles(since=date(2026, 6, 1))
        assert articles == []


class TestCancerNetworkScraper:
    def test_parses_articles(self):
        xml = _read("cancernetwork_rss.xml")
        scraper = CancerNetworkScraper()
        with patch.object(scraper, "_fetch_feed_text", return_value=xml):
            articles = scraper.fetch_articles(since=date(2026, 2, 7))

        assert len(articles) == 2
        assert articles[0].source == "cancernetwork"
        urls = [a.url for a in articles]
        assert "https://www.cancernetwork.com/view/til-therapy-metastatic-melanoma" in urls
