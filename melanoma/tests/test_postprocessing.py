"""Tests for postprocessing system."""

import sys
from pathlib import Path

import pytest

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.postprocessing_service import PostprocessingService  # noqa: E402
from domain.models import (  # noqa: E402
    ConferenceType,
    ParsedAbstract,
    PostprocessingConfiguration,
)
from infrastructure.asco_postprocessor import ASCOPostprocessor  # noqa: E402
from infrastructure.esmo_postprocessor import ESMOPostprocessor  # noqa: E402


class TestASCOPostprocessor:
    """Tests for ASCO postprocessor."""

    @pytest.fixture
    def processor(self):
        return ASCOPostprocessor()

    @pytest.fixture
    def sample_asco_abstract(self):
        return """10000 Oral Abstract Session

# Pembrolizumab versus placebo after complete resection of high-risk stage III melanoma.

Alexander M. Eggermont, Christian U. Blank, Mario Mandala

Background: We conducted the phase 3 double-blind EORTC 1325/KEYNOTE-054 trial to evaluate pembrolizumab vs placebo in patients with resected high-risk stage III melanoma.

Methods: Eligible pts included those ≥18 yrs of age with complete resection of cutaneous melanoma metastatic to lymph node(s).

Results: Overall, 15%/46%/39% of pts had stage IIIA/IIIB/IIIC. At 3.05-yr median follow-up, pembrolizumab prolonged RFS.

Conclusions: Pembrolizumab provided a sustained improvement in RFS in resected high-risk stage III melanoma.

Clinical trial information: NCT02362594.

Research Sponsor: Merck."""

    def test_get_conference_type(self, processor):
        assert processor.get_conference_type() == ConferenceType.ASCO

    def test_clean_text(self, processor):
        text = "  This is   a test\\nwith   multiple   spaces  "
        result = processor.clean_text(text)
        assert result == "This is a test with multiple spaces"

    def test_clean_table_content(self, processor):
        table_text = "|mo|pts|yrs|HR|CI|\n|---|---|---|---|---|\n|6|100|2|0.5|0.3-0.7|"
        result = processor.clean_table_content(table_text)
        assert "months" in result
        assert "patients" in result
        assert "years" in result
        assert "Hazard Ratio" in result
        assert "Confidence Interval" in result

    @pytest.mark.asyncio
    async def test_parse_abstract(self, processor, sample_asco_abstract):
        result = await processor.parse_abstract(sample_asco_abstract)

        assert isinstance(result, ParsedAbstract)
        assert result.id == "10000"
        assert "pembrolizumab" in result.title.lower()
        assert result.background != ""
        assert result.methods != ""
        assert result.results != ""
        assert result.conclusions != ""
        assert result.clinical_trial_info == "NCT02362594"
        assert result.sponsor == "Merck"

    @pytest.mark.asyncio
    async def test_format_to_markdown(self, processor, sample_asco_abstract):
        config = PostprocessingConfiguration(
            conference_type=ConferenceType.ASCO, exclude_authors=True
        )

        parsed = await processor.parse_abstract(sample_asco_abstract)
        result = await processor.format_to_markdown(parsed, config)

        assert "### Abstract ID: 10000" in result
        assert "#### Background:" in result
        assert "#### Methods:" in result
        assert "#### Results:" in result
        assert "#### Conclusions:" in result
        assert "#### Clinical Trial Information:" in result
        assert "#### Research Sponsor:" in result

    @pytest.mark.asyncio
    async def test_validate_abstract(self, processor, sample_asco_abstract):
        parsed = await processor.parse_abstract(sample_asco_abstract)
        issues = await processor.validate_abstract(parsed)

        # Should have no issues for a well-formed abstract
        assert len(issues) == 0


class TestESMOPostprocessor:
    """Tests for ESMO postprocessor."""

    @pytest.fixture
    def processor(self):
        return ESMOPostprocessor()

    @pytest.fixture
    def sample_esmo_abstract(self):
        return """# 1076O Adjuvant nivolumab (NIVO) vs ipilimumab (IPI) in resected stage III/IV melanoma

J. Weber, M. Del Vecchio

Background: NIVO has shown improved recurrence-free survival (RFS) vs IPI in patients with resected stage III/IV melanoma.

Methods: Pts aged 15 y with completely resected stage IIIB/C or IV melanoma were stratified by stage.

Results: At 48 mo of follow-up, NIVO continued to demonstrate superior RFS vs IPI.

Conclusions: NIVO continued to demonstrate improved RFS and DMFS vs IPI at 48 mo.

Clinical trial identification: NCT02388906

Legal entity responsible for the study: Bristol-Myers Squibb Company.

Funding: Bristol-Myers Squibb Company.

https://doi.org/10.1016/j.annonc.2020.08.1200"""

    def test_get_conference_type(self, processor):
        assert processor.get_conference_type() == ConferenceType.ESMO

    @pytest.mark.asyncio
    async def test_parse_abstract(self, processor, sample_esmo_abstract):
        result = await processor.parse_abstract(sample_esmo_abstract)

        assert isinstance(result, ParsedAbstract)
        assert result.id == "1076O"
        assert "nivolumab" in result.title.lower()
        assert result.background != ""
        assert result.methods != ""
        assert result.results != ""
        assert result.conclusions != ""
        assert result.clinical_trial_info == "NCT02388906"
        assert result.legal_entity == "Bristol-Myers Squibb Company."
        assert result.funding == "Bristol-Myers Squibb Company."
        assert "doi.org" in result.doi

    @pytest.mark.asyncio
    async def test_format_to_markdown(self, processor, sample_esmo_abstract):
        config = PostprocessingConfiguration(
            conference_type=ConferenceType.ESMO, exclude_authors=True
        )

        parsed = await processor.parse_abstract(sample_esmo_abstract)
        result = await processor.format_to_markdown(parsed, config)

        assert "### Abstract ID: 1076O" in result
        assert "#### Background:" in result
        assert "#### Methods:" in result
        assert "#### Results:" in result
        assert "#### Conclusions:" in result
        assert "#### Clinical Trial Identification:" in result
        assert "#### Legal Entity Responsible for Study:" in result
        assert "#### Funding:" in result
        assert "#### DOI:" in result


class TestPostprocessingService:
    """Tests for postprocessing service."""

    @pytest.fixture
    def service(self):
        return PostprocessingService()

    def test_get_processor(self, service):
        asco_processor = service._get_processor(ConferenceType.ASCO)
        assert isinstance(asco_processor, ASCOPostprocessor)

        esmo_processor = service._get_processor(ConferenceType.ESMO)
        assert isinstance(esmo_processor, ESMOPostprocessor)

    def test_get_processor_invalid_type(self, service):
        with pytest.raises(ValueError, match="Unsupported conference type"):
            service._get_processor("invalid")

    def test_split_abstracts_asco(self, service):
        content = """{0}------------------------------------------------

Abstract 1 content

{1}------------------------------------------------

Abstract 2 content"""

        result = service._split_abstracts(content, ConferenceType.ASCO)
        assert len(result) == 2
        assert "Abstract 1 content" in result[0]
        assert "Abstract 2 content" in result[1]


class TestPostprocessingConfiguration:
    """Tests for postprocessing configuration."""

    def test_default_configuration(self):
        config = PostprocessingConfiguration(conference_type=ConferenceType.ASCO)

        assert config.conference_type == ConferenceType.ASCO
        assert config.exclude_authors is True
        assert config.preserve_tables is True
        assert config.expand_abbreviations is True
        assert config.standardize_terminology is True

    def test_custom_configuration(self):
        config = PostprocessingConfiguration(
            conference_type=ConferenceType.ESMO,
            exclude_authors=False,
            preserve_tables=False,
        )

        assert config.conference_type == ConferenceType.ESMO
        assert config.exclude_authors is False
        assert config.preserve_tables is False
        assert config.expand_abbreviations is True  # Default
        assert config.standardize_terminology is True  # Default


class TestParsedAbstract:
    """Tests for parsed abstract model."""

    def test_parsed_abstract_creation(self):
        abstract = ParsedAbstract(
            id="10000",
            title="Test Abstract",
            background="Test background",
            methods="Test methods",
            results="Test results",
            conclusions="Test conclusions",
        )

        assert abstract.id == "10000"
        assert abstract.title == "Test Abstract"
        assert abstract.background == "Test background"
        assert abstract.methods == "Test methods"
        assert abstract.results == "Test results"
        assert abstract.conclusions == "Test conclusions"

    def test_parsed_abstract_defaults(self):
        abstract = ParsedAbstract(id="10000", title="Test Abstract")

        assert abstract.id == "10000"
        assert abstract.title == "Test Abstract"
        assert abstract.authors_and_affiliations == ""
        assert abstract.background == ""
        assert abstract.methods == ""
        assert abstract.trial_design == ""
        assert abstract.results == ""
        assert abstract.conclusions == ""
        assert abstract.clinical_trial_info == ""
        assert abstract.sponsor == ""
        assert abstract.legal_entity == ""
        assert abstract.funding == ""
        assert abstract.doi == ""
        assert abstract.full_text_reference == ""
        assert abstract.additional_content == ""
