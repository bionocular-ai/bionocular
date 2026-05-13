from unittest.mock import AsyncMock, patch

from src.infrastructure.news_scraper.gemini_extractor import (
    GeminiNewsExtractor,
    NewsExtractionResult,
)


def _make_extractor() -> GeminiNewsExtractor:
    return GeminiNewsExtractor(api_key="test-api-key")


def _mock_response(result: NewsExtractionResult) -> AsyncMock:
    return AsyncMock(return_value=result)


class TestGeminiNewsExtractor:
    def test_returns_nct_ids_and_per_type_efficacy(self):
        extractor = _make_extractor()
        mock_result = NewsExtractionResult(
            nct_ids=["NCT12345678"],
            efficacy_data={
                "Cutaneous Melanoma": {"orr": "68%", "median_pfs": "12.3 months"}
            },
            safety_data={},
        )
        with patch.object(
            extractor._service, "generate_structured", new=_mock_response(mock_result)
        ):
            result = extractor.extract(
                title="Phase 3 Pembrolizumab in Melanoma",
                full_text="NCT12345678 met primary endpoint. ORR 68%. Median PFS 12.3 months.",
                cancer_types=["Cutaneous Melanoma"],
            )

        assert result.nct_ids == ["NCT12345678"]
        assert result.has_efficacy is True
        assert result.efficacy_data["Cutaneous Melanoma"]["orr"] == "68%"
        assert result.has_safety is False

    def test_returns_empty_result_on_gemini_failure(self):
        extractor = _make_extractor()
        with patch.object(
            extractor._service,
            "generate_structured",
            side_effect=Exception("API error"),
        ):
            result = extractor.extract(
                title="Melanoma Trial Update",
                full_text="Some article text.",
                cancer_types=["Cutaneous Melanoma"],
            )

        assert result.nct_ids == []
        assert result.has_efficacy is False
        assert result.has_safety is False
        assert result.efficacy_data == {}
        assert result.safety_data == {}

    def test_extracts_per_type_safety_data(self):
        extractor = _make_extractor()
        mock_result = NewsExtractionResult(
            nct_ids=[],
            efficacy_data={},
            safety_data={
                "Cutaneous Melanoma": {
                    "grade_3_plus_ae_pct": "23%",
                    "serious_ae": "12%",
                }
            },
        )
        with patch.object(
            extractor._service, "generate_structured", new=_mock_response(mock_result)
        ):
            result = extractor.extract(
                title="Safety Profile of Pembrolizumab in Melanoma",
                full_text="Grade 3+ AEs occurred in 23% of patients.",
                cancer_types=["Cutaneous Melanoma"],
            )

        assert result.has_safety is True
        assert result.safety_data["Cutaneous Melanoma"]["grade_3_plus_ae_pct"] == "23%"
        assert result.has_efficacy is False

    def test_multi_cancer_type_extraction(self):
        extractor = _make_extractor()
        mock_result = NewsExtractionResult(
            nct_ids=[],
            efficacy_data={
                "Basal Cell Carcinoma": {"orr": "45%"},
                "Cutaneous Squamous Cell Carcinoma": {"orr": "68%"},
            },
            safety_data={},
        )
        with patch.object(
            extractor._service, "generate_structured", new=_mock_response(mock_result)
        ):
            result = extractor.extract(
                title="BCC and cSCC Treatment Advances",
                full_text="ORR 45% in BCC. ORR 68% in cSCC.",
                cancer_types=[
                    "Basal Cell Carcinoma",
                    "Cutaneous Squamous Cell Carcinoma",
                ],
            )

        assert result.has_efficacy is True
        assert "Basal Cell Carcinoma" in result.efficacy_data
        assert "Cutaneous Squamous Cell Carcinoma" in result.efficacy_data

    def test_prompt_contains_title_and_cancer_types(self):
        extractor = _make_extractor()
        captured: list[str] = []

        async def capture(prompt: str, **kwargs: object) -> NewsExtractionResult:
            captured.append(prompt)
            return NewsExtractionResult()

        with patch.object(extractor._service, "generate_structured", new=capture):
            extractor.extract(
                title="Unique Title For Testing",
                full_text="Article body.",
                cancer_types=["Uveal Melanoma", "Acral Melanoma"],
            )

        assert len(captured) == 1
        assert "Unique Title For Testing" in captured[0]
        assert "Uveal Melanoma" in captured[0]
        assert "Acral Melanoma" in captured[0]
