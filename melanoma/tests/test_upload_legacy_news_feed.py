import sys
import pathlib
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from scripts.upload_legacy_news_feed import parse_date, parse_nct_ids, build_rows, _classify_efficacy_safety


class TestParseDate:
    def test_standard_format(self):
        assert parse_date("February 2, 2026") == "2026-02-02"

    def test_single_digit_day(self):
        assert parse_date("January 9, 2026") == "2026-01-09"

    def test_double_digit_day(self):
        assert parse_date("November 12, 2025") == "2025-11-12"


class TestParseNctIds:
    def test_null_returns_empty(self):
        assert parse_nct_ids(None) == []

    def test_single_id(self):
        assert parse_nct_ids("NCT03655756") == ["NCT03655756"]

    def test_comma_separated(self):
        assert parse_nct_ids("NCT04949113, NCT03698019") == ["NCT04949113", "NCT03698019"]

    def test_strips_whitespace(self):
        assert parse_nct_ids("NCT001,  NCT002") == ["NCT001", "NCT002"]


class TestClassifyEfficacySafety:
    def test_efficacy_only(self):
        has_eff, has_saf = _classify_efficacy_safety("ORR; Median PFS; Median OS")
        assert has_eff is True
        assert has_saf is False

    def test_safety_only(self):
        has_eff, has_saf = _classify_efficacy_safety("Adverse Events")
        assert has_eff is False
        assert has_saf is True

    def test_both(self):
        has_eff, has_saf = _classify_efficacy_safety("Safety (DLTs); Efficacy (PFS2)")
        assert has_eff is True
        assert has_saf is True

    def test_ae_abbreviation_is_safety(self):
        has_eff, has_saf = _classify_efficacy_safety("ORR; AE-related Permanent Discontinuation")
        assert has_eff is True
        assert has_saf is True

    def test_unknown_defaults_to_efficacy(self):
        has_eff, has_saf = _classify_efficacy_safety("Some unrecognised metric")
        assert has_eff is True
        assert has_saf is False


class TestBuildRows:
    def _minimal_data(self):
        return {
            "cutaneous-melanoma": {
                "articles": [
                    {
                        "title": "Article A",
                        "date": "February 2, 2026",
                        "url": "https://example.com/a",
                        "nct_id": "NCT001",
                    }
                ],
                "results": [],
            }
        }

    def test_single_article_no_result(self):
        rows = build_rows(self._minimal_data())
        assert len(rows) == 1
        row = rows[0]
        assert row["url"] == "https://example.com/a"
        assert row["title"] == "Article A"
        assert row["date"] == "2026-02-02"
        assert row["cancer_type"] == ["Cutaneous Melanoma"]
        assert row["nct_ids"] == ["NCT001"]
        assert row["has_efficacy"] is False
        assert row["efficacy_data"] == {}
        assert row["has_safety"] is False
        assert row["safety_data"] == {}
        assert row["extracted_at"] is None

    def test_same_url_across_two_cancer_types_merged(self):
        data = {
            "cutaneous-melanoma": {
                "articles": [
                    {"title": "Article B", "date": "March 1, 2026",
                     "url": "https://example.com/b", "nct_id": None}
                ],
                "results": [],
            },
            "uveal-melanoma": {
                "articles": [
                    {"title": "Article B", "date": "March 1, 2026",
                     "url": "https://example.com/b", "nct_id": None}
                ],
                "results": [],
            },
        }
        rows = build_rows(data)
        assert len(rows) == 1
        assert set(rows[0]["cancer_type"]) == {"Cutaneous Melanoma", "Uveal Melanoma"}

    def test_result_adds_efficacy_data(self):
        data = {
            "cutaneous-melanoma": {
                "articles": [
                    {"title": "Article C", "date": "April 1, 2026",
                     "url": "https://example.com/c", "nct_id": None}
                ],
                "results": [
                    {"title": "Article C", "date": "April 1, 2026",
                     "url": "https://example.com/c", "nct_id": None,
                     "efficacy_or_safety_data": {"metric": "ORR", "value": "68%"}}
                ],
            }
        }
        rows = build_rows(data)
        assert len(rows) == 1
        assert rows[0]["has_efficacy"] is True
        assert rows[0]["efficacy_data"] == {"metric": "ORR", "value": "68%"}
        assert rows[0]["extracted_at"] is not None

    def test_result_only_url_not_in_articles(self):
        data = {
            "cutaneous-melanoma": {
                "articles": [],
                "results": [
                    {"title": "Result Only", "date": "May 1, 2026",
                     "url": "https://example.com/result-only", "nct_id": "NCT999",
                     "efficacy_or_safety_data": {"metric": "PFS", "value": "12.3 months"}}
                ],
            }
        }
        rows = build_rows(data)
        assert len(rows) == 1
        row = rows[0]
        assert row["url"] == "https://example.com/result-only"
        assert row["cancer_type"] == ["Cutaneous Melanoma"]
        assert row["nct_ids"] == ["NCT999"]
        assert row["has_efficacy"] is True

    def test_safety_only_result(self):
        data = {
            "cutaneous-melanoma": {
                "articles": [],
                "results": [
                    {"title": "Safety Article", "date": "May 1, 2026",
                     "url": "https://example.com/safety", "nct_id": None,
                     "efficacy_or_safety_data": {"metric": "Adverse Events", "value": "Grade 1-2 only"}}
                ],
            }
        }
        rows = build_rows(data)
        assert len(rows) == 1
        row = rows[0]
        assert row["has_safety"] is True
        assert row["safety_data"] == {"metric": "Adverse Events", "value": "Grade 1-2 only"}
        assert row["has_efficacy"] is False
        assert row["efficacy_data"] == {}
