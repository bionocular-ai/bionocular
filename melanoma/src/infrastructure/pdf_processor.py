"""PDF processing implementation using PyPDF2."""

import io
import logging
from typing import Any

from PyPDF2 import PdfReader

from ..domain.interfaces import PDFProcessorInterface

logger = logging.getLogger(__name__)


class PyPDF2Processor(PDFProcessorInterface):
    """PyPDF2-based PDF processor implementation."""

    def __init__(self) -> None:
        """Initialize the PDF processor."""
        self.batch_indicators = [
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

    async def validate_pdf(self, file_content: bytes) -> bool:
        """Validate that the file is a valid PDF."""
        try:
            # Try to read the PDF
            pdf_stream = io.BytesIO(file_content)
            reader = PdfReader(pdf_stream)

            # Check if we can read at least one page
            if len(reader.pages) == 0:
                logger.warning("PDF has no pages")
                return False

            # Try to extract text from first page to ensure it's readable
            first_page = reader.pages[0]
            text = first_page.extract_text()

            # Basic validation - PDF should have some text content
            if not text or len(text.strip()) < 10:
                logger.warning("PDF appears to be empty or unreadable")
                return False

            return True

        except Exception as e:
            logger.error(f"PDF validation failed: {str(e)}")
            return False

    async def is_batch_pdf(self, file_content: bytes) -> bool:
        """Determine if a PDF contains multiple documents."""
        try:
            pdf_stream = io.BytesIO(file_content)
            reader = PdfReader(pdf_stream)

            # Check if PDF has multiple pages
            if len(reader.pages) <= 1:
                return False

            # Look for batch indicators in the first few pages
            for page_num in range(min(3, len(reader.pages))):
                page = reader.pages[page_num]
                text = page.extract_text()

                # Check for batch indicators
                for indicator in self.batch_indicators:
                    if indicator in text:
                        logger.info(f"Found batch indicator: {indicator}")
                        return True

            # Check if there are clear page breaks with different content
            if len(reader.pages) > 2:
                # Compare content between pages to detect different documents
                page1_text = reader.pages[0].extract_text()[:200]  # First 200 chars
                page2_text = reader.pages[1].extract_text()[:200]

                # If pages have very different content, likely a batch
                if self._is_different_content(page1_text, page2_text):
                    return True

            return False

        except Exception as e:
            logger.error(f"Error checking if PDF is batch: {str(e)}")
            return False

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

    async def extract_text(self, file_content: bytes) -> str:
        """Extract text content from PDF file.

        Args:
            file_content: PDF file content as bytes

        Returns:
            Extracted text content
        """
        try:
            pdf_stream = io.BytesIO(file_content)
            reader = PdfReader(pdf_stream)

            text_content = []
            for page in reader.pages:
                text_content.append(page.extract_text())

            return "\n".join(text_content)

        except Exception as e:
            logger.error(f"Failed to extract text from PDF: {e}")
            raise RuntimeError(f"Text extraction failed: {e}") from e

    async def extract_metadata(self, file_content: bytes) -> dict[str, Any]:
        """Extract metadata from PDF file.

        Args:
            file_content: PDF file content as bytes

        Returns:
            Extracted metadata dictionary
        """
        try:
            pdf_stream = io.BytesIO(file_content)
            reader = PdfReader(pdf_stream)

            metadata = {}
            if reader.metadata:
                metadata.update({
                    "title": reader.metadata.get("/Title", ""),
                    "author": reader.metadata.get("/Author", ""),
                    "subject": reader.metadata.get("/Subject", ""),
                    "creator": reader.metadata.get("/Creator", ""),
                    "producer": reader.metadata.get("/Producer", ""),
                    "creation_date": str(reader.metadata.get("/CreationDate", "")),
                    "modification_date": str(reader.metadata.get("/ModDate", "")),
                })

            # Add basic file info
            metadata.update({
                "page_count": len(reader.pages),
                "is_batch": await self.is_batch_pdf(file_content),
            })

            return metadata

        except Exception as e:
            logger.error(f"Failed to extract metadata from PDF: {e}")
            raise RuntimeError(f"Metadata extraction failed: {e}") from e
