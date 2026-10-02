import pathlib
from datetime import date
from unittest.mock import patch

import pytest

from src.infrastructure.news_scraper.biospace import BioSpaceScraper

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


class TestBioSpaceScraper:
    def test_resolves_google_url_to_real_url(self):
        xml = (FIXTURES / "targetedonc_gnews.xml").read_text()  # reuse same RSS shape
        scraper = BioSpaceScraper()

        with (
            patch.object(scraper, "_fetch_gnews_text", return_value=xml),
            patch.object(
                scraper,
                "_resolve_url",
                return_value="https://www.biospace.com/some-article",
            ),
        ):
            articles = scraper.fetch_articles(since=date(2026, 4, 1))

        assert all(not a.url.startswith("https://news.google.com") for a in articles)

    def test_falls_back_to_google_url_on_decode_failure(self):
        xml = (FIXTURES / "targetedonc_gnews.xml").read_text()
        scraper = BioSpaceScraper()

        with (
            patch.object(scraper, "_fetch_gnews_text", return_value=xml),
            patch.object(
                scraper, "_resolve_url", side_effect=Exception("decode failed")
            ),
        ):
            articles = scraper.fetch_articles(since=date(2026, 4, 1))

        # fallback: keeps original google URL rather than crashing
        assert len(articles) > 0

    def test_deduplicates_across_keywords(self):
        xml = (FIXTURES / "targetedonc_gnews.xml").read_text()
        scraper = BioSpaceScraper()

        def fake_resolve(_url: str) -> str:
            return "https://www.biospace.com/same-article"  # always same URL

        with (
            patch.object(scraper, "_fetch_gnews_text", return_value=xml),
            patch.object(scraper, "_resolve_url", side_effect=fake_resolve),
        ):
            articles = scraper.fetch_articles(since=date(2026, 4, 1))

        urls = [a.url for a in articles]
        assert len(urls) == len(set(urls))

    def test_raises_when_every_fetch_fails(self):
        scraper = BioSpaceScraper()
        with (
            patch.object(
                scraper, "_fetch_gnews_text", side_effect=Exception("timeout")
            ),
            pytest.raises(RuntimeError),
        ):
            scraper.fetch_articles(since=date(2026, 4, 1))

    def test_tolerates_some_fetch_failures(self):
        xml = (FIXTURES / "targetedonc_gnews.xml").read_text()
        scraper = BioSpaceScraper()
        with (
            patch.object(
                scraper,
                "_fetch_gnews_text",
                side_effect=lambda kw: xml if kw == "melanoma" else 1 / 0,
            ),
            patch.object(scraper, "_resolve_url", side_effect=lambda url: url),
        ):
            articles = scraper.fetch_articles(since=date(2026, 4, 1))
        assert len(articles) > 0
