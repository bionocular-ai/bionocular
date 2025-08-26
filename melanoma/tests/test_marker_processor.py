"""Tests for the Marker PDF processor."""

from unittest.mock import Mock, patch

import pytest

from src.infrastructure.marker_processor import MarkerPDFProcessor


class TestMarkerPDFProcessor:
    """Test cases for MarkerPDFProcessor."""

    def test_initialization(self):
        """Test processor initialization with different configurations."""
        # Test default configuration
        processor = MarkerPDFProcessor()
        assert processor.use_llm is False
        assert processor.extract_images is True
        assert processor.config["output_format"] == "markdown"

        # Test custom configuration
        processor = MarkerPDFProcessor(use_llm=True, extract_images=False)
        assert processor.use_llm is True
        assert processor.extract_images is False

    def test_config_validation(self):
        """Test that configuration is properly set."""
        processor = MarkerPDFProcessor()

        expected_config = {
            "output_format": "markdown",
            "extract_images": True,
            "paginate_output": True,
            "keep_pageheader_in_output": True,
            "format_lines": False,
            "use_llm": False,
            "redo_inline_math": False,
            "debug": False,
            "workers": 1,
        }

        assert processor.config == expected_config

    @pytest.mark.asyncio
    async def test_validate_pdf_success(self):
        """Test successful PDF validation."""
        processor = MarkerPDFProcessor()

        # Mock PDF content
        pdf_content = b"%PDF-1.4\n%Test PDF content"

        with patch(
            "src.infrastructure.marker_processor.PdfConverter"
        ) as mock_converter:
            # Mock successful document building
            mock_doc = Mock()
            mock_doc.pages = [Mock(), Mock()]  # 2 pages

            mock_converter_instance = Mock()
            mock_converter_instance.build_document.return_value = mock_doc
            mock_converter.return_value = mock_converter_instance

            # Mock ConfigParser
            with patch(
                "src.infrastructure.marker_processor.ConfigParser"
            ) as mock_config_parser:
                mock_config_parser_instance = Mock()
                mock_config_parser_instance.generate_config_dict.return_value = {}
                mock_config_parser_instance.get_processors.return_value = []
                mock_config_parser_instance.get_renderer.return_value = Mock()
                mock_config_parser.return_value = mock_config_parser_instance

                result = await processor.validate_pdf(pdf_content)
                assert result is True

    @pytest.mark.asyncio
    async def test_validate_pdf_failure(self):
        """Test PDF validation failure."""
        processor = MarkerPDFProcessor()

        # Mock PDF content
        pdf_content = b"Invalid PDF content"

        with patch(
            "src.infrastructure.marker_processor.PdfConverter"
        ) as mock_converter:
            # Mock failed document building
            mock_converter_instance = Mock()
            mock_converter_instance.build_document.side_effect = Exception("PDF error")
            mock_converter.return_value = mock_converter_instance

            # Mock ConfigParser
            with patch(
                "src.infrastructure.marker_processor.ConfigParser"
            ) as mock_config_parser:
                mock_config_parser_instance = Mock()
                mock_config_parser_instance.generate_config_dict.return_value = {}
                mock_config_parser_instance.get_processors.return_value = []
                mock_config_parser_instance.get_renderer.return_value = Mock()
                mock_config_parser.return_value = mock_config_parser_instance

                result = await processor.validate_pdf(pdf_content)
                assert result is False

    def test_get_processing_stats(self):
        """Test getting processing statistics."""
        processor = MarkerPDFProcessor()

        stats = processor.get_processing_stats()
        expected_keys = ["successful", "failed", "total_time", "start_time"]

        for key in expected_keys:
            assert key in stats

        assert stats["successful"] == 0
        assert stats["failed"] == 0

    def test_reset_stats(self):
        """Test resetting processing statistics."""
        processor = MarkerPDFProcessor()

        # Modify stats
        processor.stats["successful"] = 5
        processor.stats["failed"] = 2

        # Reset
        processor.reset_stats()

        assert processor.stats["successful"] == 0
        assert processor.stats["failed"] == 0

    def test_extract_page_text(self):
        """Test text extraction from page objects."""
        processor = MarkerPDFProcessor()

        # Mock page with blocks
        mock_page = Mock()
        mock_block1 = Mock()
        mock_block1.text = "First block text"
        mock_block1.html = None

        mock_block2 = Mock()
        mock_block2.text = None
        mock_block2.html = "<p>Second block HTML</p>"

        mock_page.blocks = [mock_block1, mock_block2]

        result = processor._extract_page_text(mock_page)
        assert "First block text" in result
        assert "Second block HTML" in result

    def test_is_different_content(self):
        """Test content similarity detection."""
        processor = MarkerPDFProcessor()

        # Test similar content
        text1 = "This is a test document about melanoma research"
        text2 = "This is a test document about cancer research"
        assert processor._is_different_content(text1, text2) is False

        # Test different content
        text3 = "Completely different topic about engineering"
        assert processor._is_different_content(text1, text3) is True

        # Test edge cases
        assert processor._is_different_content("", "some text") is True
        assert processor._is_different_content("text", "") is True
        assert processor._is_different_content("", "") is True

    @pytest.mark.asyncio
    async def test_extract_text(self):
        """Test text extraction from PDF content."""
        processor = MarkerPDFProcessor()

        # Mock PDF content
        pdf_content = b"%PDF-1.4\n%Test PDF content"

        with patch(
            "src.infrastructure.marker_processor.PdfConverter"
        ) as mock_converter:
            # Mock successful conversion
            mock_converter_instance = Mock()
            mock_converter_instance.return_value = Mock()
            mock_converter.return_value = mock_converter_instance

            # Mock text_from_rendered
            with patch(
                "src.infrastructure.marker_processor.text_from_rendered"
            ) as mock_text:
                mock_text.return_value = ("Extracted text", None, None)

                # Mock ConfigParser
                with patch(
                    "src.infrastructure.marker_processor.ConfigParser"
                ) as mock_config_parser:
                    mock_config_parser_instance = Mock()
                    mock_config_parser_instance.generate_config_dict.return_value = {}
                    mock_config_parser_instance.get_processors.return_value = []
                    mock_config_parser_instance.get_renderer.return_value = Mock()
                    mock_config_parser.return_value = mock_config_parser_instance

                    # Mock the rendered object with proper children attribute
                    mock_rendered = Mock()
                    mock_rendered.children = []
                    mock_converter_instance.return_value = mock_rendered

                    result = await processor.extract_text(pdf_content)
                    assert "Extracted text" in result

    @pytest.mark.asyncio
    async def test_extract_metadata(self):
        """Test metadata extraction from PDF content."""
        processor = MarkerPDFProcessor()

        # Mock PDF content
        pdf_content = b"%PDF-1.4\n%Test PDF content"

        with patch(
            "src.infrastructure.marker_processor.PdfConverter"
        ) as mock_converter:
            # Mock successful conversion
            mock_converter_instance = Mock()
            mock_converter_instance.return_value = Mock()
            mock_converter.return_value = mock_converter_instance

            # Mock text_from_rendered
            with patch(
                "src.infrastructure.marker_processor.text_from_rendered"
            ) as mock_text:
                mock_text.return_value = ("JSON content", None, None)

                # Mock ConfigParser
                with patch(
                    "src.infrastructure.marker_processor.ConfigParser"
                ) as mock_config_parser:
                    mock_config_parser_instance = Mock()
                    mock_config_parser_instance.generate_config_dict.return_value = {}
                    mock_config_parser_instance.get_processors.return_value = []
                    mock_config_parser_instance.get_renderer.return_value = Mock()
                    mock_config_parser.return_value = mock_config_parser_instance

                    # Mock the rendered object with metadata
                    mock_rendered = Mock()
                    mock_rendered.metadata = {"test_key": "test_value"}
                    mock_converter_instance.return_value = mock_rendered

                    result = await processor.extract_metadata(pdf_content)
                    assert "processor" in result
                    assert result["processor"] == "marker"
                    assert "test_key" in result

    @pytest.mark.asyncio
    async def test_is_batch_pdf(self):
        """Test batch PDF detection."""
        processor = MarkerPDFProcessor()

        # Mock PDF content
        pdf_content = b"%PDF-1.4\n%Test PDF content"

        with patch(
            "src.infrastructure.marker_processor.PdfConverter"
        ) as mock_converter:
            # Mock document with multiple pages
            mock_doc = Mock()
            mock_page1 = Mock()
            mock_page1.blocks = []
            mock_page2 = Mock()
            mock_page2.blocks = []

            mock_doc.pages = [mock_page1, mock_page2]

            mock_converter_instance = Mock()
            mock_converter_instance.build_document.return_value = mock_doc
            mock_converter.return_value = mock_converter_instance

            # Mock ConfigParser
            with patch(
                "src.infrastructure.marker_processor.ConfigParser"
            ) as mock_config_parser:
                mock_config_parser_instance = Mock()
                mock_config_parser_instance.generate_config_dict.return_value = {}
                mock_config_parser_instance.get_processors.return_value = []
                mock_config_parser_instance.get_renderer.return_value = Mock()
                mock_config_parser.return_value = mock_config_parser_instance

                result = await processor.is_batch_pdf(pdf_content)
                # Should return False for 2 pages without batch indicators
                assert result is False
