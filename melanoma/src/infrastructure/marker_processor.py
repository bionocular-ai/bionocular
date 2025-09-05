"""Marker PDF processor implementation using the marker-pdf library."""

import logging
import time
from pathlib import Path
from typing import Any

from marker.config.parser import ConfigParser  # type: ignore
from marker.converters.pdf import PdfConverter  # type: ignore
from marker.models import create_model_dict  # type: ignore
from marker.output import text_from_rendered  # type: ignore

from ..domain.interfaces import PDFProcessorInterface

logger = logging.getLogger(__name__)


class MarkerPDFProcessor(PDFProcessorInterface):
    """Marker-based PDF processor implementation with superior accuracy."""

    def __init__(self, use_llm: bool = False, extract_images: bool = True) -> None:
        """Initialize the Marker PDF processor.

        Args:
            use_llm: Whether to use LLM for improved accuracy (slower but better)
            extract_images: Whether to extract images from PDFs
        """
        self.use_llm = use_llm
        self.extract_images = extract_images

        # Balanced configuration optimized for speed and accuracy
        self.config = {
            "output_format": "markdown",
            "extract_images": extract_images,
            "paginate_output": True,
            "keep_pageheader_in_output": True,
            "format_lines": False,
            "use_llm": use_llm,
            "redo_inline_math": False,
            "debug": False,
            "workers": 1,
        }

        # Processing statistics
        self.stats = {
            "successful": 0,
            "failed": 0,
            "total_time": 0,
            "start_time": None,
        }

    async def validate_pdf(self, file_content: bytes) -> bool:
        """Validate that the file is a valid PDF using Marker."""
        try:
            # Create a temporary file to test with Marker
            temp_path = Path(f"/tmp/temp_validation_{int(time.time())}.pdf")

            try:
                with open(temp_path, "wb") as f:
                    f.write(file_content)

                # Try to process with Marker
                config_parser = ConfigParser(self.config)
                converter = PdfConverter(
                    config=config_parser.generate_config_dict(),
                    artifact_dict=create_model_dict(),
                    processor_list=config_parser.get_processors(),
                    renderer=config_parser.get_renderer(),
                )

                # Try to build document structure
                doc = converter.build_document(str(temp_path))
                if doc and hasattr(doc, "pages") and len(doc.pages) > 0:
                    logger.info(f"PDF validation successful: {len(doc.pages)} pages")
                    return True
                else:
                    logger.warning("PDF validation failed: no pages found")
                    return False

            finally:
                # Clean up temp file
                if temp_path.exists():
                    temp_path.unlink()

        except Exception as e:
            logger.error(f"PDF validation failed: {str(e)}")
            return False

    async def is_batch_pdf(self, file_content: bytes) -> bool:
        """Determine if a PDF contains multiple documents using Marker."""
        try:
            # Create a temporary file to analyze
            temp_path = Path(f"/tmp/temp_batch_check_{int(time.time())}.pdf")

            try:
                with open(temp_path, "wb") as f:
                    f.write(file_content)

                config_parser = ConfigParser(self.config)
                converter = PdfConverter(
                    config=config_parser.generate_config_dict(),
                    artifact_dict=create_model_dict(),
                    processor_list=config_parser.get_processors(),
                    renderer=config_parser.get_renderer(),
                )

                # Build document to analyze structure
                doc = converter.build_document(str(temp_path))
                if not doc or not hasattr(doc, "pages"):
                    return False

                # Check if PDF has multiple pages
                if len(doc.pages) <= 1:
                    return False

                # Batch detection indicators for scientific documents
                batch_indicators = [
                    "Abstract ID",
                    "Abstract ID:",
                    "Abstract:",
                    "ABSTRACT:",
                    "Publication ID",
                    "Publication ID:",
                    "Title:",
                    "TITLE:",
                    "Authors:",
                    "AUTHORS:",
                    "Introduction",
                    "INTRODUCTION",
                    "Methods",
                    "METHODS",
                    "Results",
                    "RESULTS",
                    "Conclusion",
                    "CONCLUSION",
                ]

                for page_num in range(min(3, len(doc.pages))):
                    page = doc.pages[page_num]
                    if hasattr(page, "blocks") and page.blocks:
                        for block in page.blocks:
                            if hasattr(block, "text") and block.text:
                                for indicator in batch_indicators:
                                    if indicator in block.text:
                                        logger.info(
                                            f"Found batch indicator: {indicator}"
                                        )
                                        return True

                # Check if pages have very different content
                if len(doc.pages) > 2:
                    page1_text = self._extract_page_text(doc.pages[0])[:200]
                    page2_text = self._extract_page_text(doc.pages[1])[:200]

                    if self._is_different_content(page1_text, page2_text):
                        return True

                return False

            finally:
                # Clean up temp file
                if temp_path.exists():
                    temp_path.unlink()

        except Exception as e:
            logger.error(f"Error checking if PDF is batch: {str(e)}")
            return False

    async def extract_text(self, file_content: bytes) -> str:
        """Extract text content from PDF using Marker."""
        try:
            # Create a temporary file for processing
            temp_path = Path(f"/tmp/temp_extract_{int(time.time())}.pdf")

            try:
                with open(temp_path, "wb") as f:
                    f.write(file_content)

                # Process with Marker - match original script approach
                config_parser = ConfigParser(self.config)
                converter = PdfConverter(
                    config=config_parser.generate_config_dict(),
                    artifact_dict=create_model_dict(),
                    processor_list=config_parser.get_processors(),
                    renderer=config_parser.get_renderer(),
                )

                # 1. First build document structure (avoids immediate OCR)
                doc = converter.build_document(str(temp_path))
                if not doc or not hasattr(doc, "pages"):
                    raise Exception("Failed to build document structure")

                # 2. Then render to markdown (triggers OCR processing)
                rendered = converter(str(temp_path))
                main_text, _, _ = text_from_rendered(rendered)

                # Extract headers and combine with main text
                header_info = self._extract_headers_from_rendered(rendered)

                if header_info:
                    final_text = header_info + "\n\n" + main_text
                else:
                    final_text = main_text

                logger.info(
                    f"Successfully extracted text using Marker (length: {len(final_text)})"
                )
                return final_text

            finally:
                # Clean up temp file
                if temp_path.exists():
                    temp_path.unlink()

        except Exception as e:
            logger.error(f"Text extraction failed: {str(e)}")
            raise

    async def extract_metadata(self, file_content: bytes) -> dict[str, Any]:
        """Extract metadata from PDF using Marker."""
        try:
            # Create a temporary file for processing
            temp_path = Path(f"/tmp/temp_metadata_{int(time.time())}.pdf")

            try:
                with open(temp_path, "wb") as f:
                    f.write(file_content)

                # Process with Marker to get metadata
                json_config = self.config.copy()
                json_config["output_format"] = "json"

                config_parser = ConfigParser(json_config)
                converter = PdfConverter(
                    config=config_parser.generate_config_dict(),
                    artifact_dict=create_model_dict(),
                    processor_list=config_parser.get_processors(),
                    renderer=config_parser.get_renderer(),
                )

                # Convert to JSON to access metadata
                rendered = converter(str(temp_path))

                metadata = {}
                if hasattr(rendered, "metadata") and rendered.metadata:
                    metadata.update(rendered.metadata)

                # Add basic file info
                metadata.update(
                    {
                        "processor": "marker",
                        "use_llm": self.use_llm,
                        "extract_images": self.extract_images,
                        "processing_timestamp": time.time(),
                    }
                )

                logger.info("Successfully extracted metadata using Marker")
                return metadata

            finally:
                # Clean up temp file
                if temp_path.exists():
                    temp_path.unlink()

        except Exception as e:
            logger.error(f"Metadata extraction failed: {str(e)}")
            return {}

    def _extract_page_text(self, page) -> str:
        """Extract text from a page object."""
        text_parts = []

        if hasattr(page, "blocks") and page.blocks:
            for block in page.blocks:
                if hasattr(block, "text") and block.text:
                    text_parts.append(block.text.strip())
                elif hasattr(block, "html") and block.html:
                    # Clean HTML tags
                    import re

                    clean_text = re.sub(r"<[^>]+>", "", block.html).strip()
                    if clean_text:
                        text_parts.append(clean_text)

        return " ".join(text_parts)

    def _is_different_content(self, text1: str, text2: str) -> bool:
        """Check if two text samples are significantly different."""
        if not text1 or not text2:
            return True

        # Simple similarity check - can be improved
        words1 = set(text1.lower().split()[:50])  # First 50 words
        words2 = set(text2.lower().split()[:50])

        if not words1 or not words2:
            return True

        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))

        similarity = intersection / union if union > 0 else 0
        return similarity < 0.3  # Less than 30% similarity

    def _extract_headers_from_rendered(self, rendered) -> str:
        """Extract headers from the rendered output."""
        header_info = ""

        if hasattr(rendered, "children") and rendered.children:
            for i, page_data in enumerate(rendered.children, 1):
                page_headers = []

                # Extract headers from PageHeader blocks
                if hasattr(page_data, "children") and page_data.children:
                    for block in page_data.children:
                        if (
                            hasattr(block, "block_type")
                            and block.block_type == "PageHeader"
                        ):
                            if hasattr(block, "html") and block.html:
                                import re

                                clean_text = re.sub(r"<[^>]+>", "", block.html).strip()
                                if (
                                    clean_text
                                    and clean_text
                                    != "Text that appears at the top of a page, like a page title."
                                ):
                                    page_headers.append(clean_text)

                # Fallback: extract headers from page HTML patterns
                if not page_headers and hasattr(page_data, "html") and page_data.html:
                    import re

                    header_patterns = re.findall(r"<p>([^<]+)</p>", page_data.html)
                    for pattern in header_patterns:
                        clean_pattern = pattern.strip()
                        if (
                            clean_pattern
                            and len(clean_pattern) > 5
                            and clean_pattern.isupper()
                        ):
                            page_headers.append(clean_pattern)

                if page_headers:
                    header_info += (
                        f"\n--- Page {i} Header ---\n"
                        + "\n".join(page_headers)
                        + "\n---\n\n"
                    )

        return header_info

    def get_processing_stats(self) -> dict[str, Any]:
        """Get current processing statistics."""
        return self.stats.copy()

    def reset_stats(self) -> None:
        """Reset processing statistics."""
        self.stats = {
            "successful": 0,
            "failed": 0,
            "total_time": 0,
            "start_time": None,
        }
