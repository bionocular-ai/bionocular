import sys
from datetime import date
from unittest.mock import MagicMock

import pytest

from scripts.scrape_news_supabase import (
    build_upsert_row,
    compute_since,
    fetch_full_text,
    main,
)
from src.infrastructure.news_scraper.base import NewsArticleRaw
from src.infrastructure.news_scraper.gemini_extractor import NewsExtractionResult


class TestComputeSince:
    def test_days_flag(self):
        from datetime import timedelta

        result = compute_since(days=3, since_str=None)
        assert result == date.today() - timedelta(days=3)

    def test_since_str_overrides_days(self):
        result = compute_since(days=7, since_str="2026-02-06")
        assert result == date(2026, 2, 6)

    def test_invalid_since_str_raises(self):
        with pytest.raises(SystemExit):
            compute_since(days=2, since_str="not-a-date")


class TestFetchFullText:
    def test_returns_text_on_success(self):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "<html><body><p>Article content here.</p></body></html>"
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        text = fetch_full_text("https://example.com/article", mock_session)
        assert text is not None
        assert "Article content here." in text

    def test_returns_none_on_failure(self):
        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("timeout")

        text = fetch_full_text("https://example.com/article", mock_session)
        assert text is None


class TestBuildUpsertRow:
    def test_builds_complete_row(self):
        article = NewsArticleRaw(
            source="onclive",
            title="Phase 3 Pembrolizumab in Melanoma",
            url="https://www.onclive.com/view/pembro-melanoma",
            published_date=date(2026, 5, 11),
            description="ORR 68% in cutaneous melanoma.",
            full_text="Full article text here.",
        )
        cancer_types = ["Cutaneous Melanoma"]
        extraction = NewsExtractionResult(
            nct_ids=["NCT12345678"],
            has_efficacy=True,
            efficacy_data={"Cutaneous Melanoma": {"orr": "68%"}},
            has_safety=False,
            safety_data={},
        )

        row = build_upsert_row(article, cancer_types, extraction)

        assert row["title"] == "Phase 3 Pembrolizumab in Melanoma"
        assert row["url"] == "https://www.onclive.com/view/pembro-melanoma"
        assert row["date"] == "2026-05-11"
        assert row["cancer_type"] == ["Cutaneous Melanoma"]
        assert row["nct_ids"] == ["NCT12345678"]
        assert row["has_efficacy"] is True
        assert row["efficacy_data"] == {"Cutaneous Melanoma": {"orr": "68%"}}
        assert row["has_safety"] is False
        assert row["safety_data"] == {}
        assert row["extracted_at"] is not None

    def test_builds_row_without_extraction(self):
        article = NewsArticleRaw(
            source="biospace",
            title="Melanoma Trial Update",
            url="https://www.biospace.com/melanoma-trial",
            published_date=date(2026, 4, 1),
            description="Trial update.",
            full_text=None,
        )
        cancer_types = ["Cutaneous Melanoma"]

        row = build_upsert_row(article, cancer_types, extraction=None)

        assert row["nct_ids"] == []
        assert row["has_efficacy"] is False
        assert row["extracted_at"] is None


class TestPipelineWithoutGoogleApiKey:
    def test_pipeline_runs_without_google_api_key(self, monkeypatch):
        """Pipeline should proceed without GOOGLE_API_KEY — skips extraction."""
        from unittest.mock import MagicMock, patch

        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.setenv("SUPABASE_URL", "https://fake.supabase.co")
        monkeypatch.setenv("SUPABASE_KEY", "fake-key")
        monkeypatch.setattr(sys, "argv", ["scrape_news_supabase.py", "--days", "1"])

        with (
            patch(
                "scripts.scrape_news_supabase.load_dotenv"
            ),  # prevent .env from overwriting delenv
            patch("scripts.scrape_news_supabase.OncLiveScraper") as mock_onclive,
            patch("scripts.scrape_news_supabase.CancerNetworkScraper") as mock_cn,
            patch("scripts.scrape_news_supabase.TargetedOncScraper") as mock_to,
            patch("scripts.scrape_news_supabase.BioSpaceScraper") as mock_bs,
            patch("scripts.scrape_news_supabase.create_client") as mock_create_client,
            patch("scripts.scrape_news_supabase.CostCalculator"),
        ):
            for m in [mock_onclive, mock_cn, mock_to, mock_bs]:
                m.return_value.fetch_articles.return_value = []
            mock_create_client.return_value = MagicMock()

            result = main()

        assert result != 2
