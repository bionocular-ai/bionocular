"""PDF processing implementation using PyPDF2."""

import io
import logging

from PyPDF2 import PdfReader, PdfWriter

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

    async def split_batch_pdf(
        self, file_content: bytes, filename: str
    ) -> list[tuple[bytes, str]]:
        """Split a batch PDF into individual documents."""
        try:
            pdf_stream = io.BytesIO(file_content)
            reader = PdfReader(pdf_stream)

            if len(reader.pages) <= 1:
                # Single page, return as is
                return [(file_content, filename)]

            documents = []
            current_doc_pages: list = []
            current_doc_start = 0

            for page_num, page in enumerate(reader.pages):
                page_text = page.extract_text()

                # Check if this page starts a new document
                if self._is_new_document_start(page_text, page_num):
                    # Save previous document if we have one
                    if current_doc_pages:
                        doc_content = self._create_pdf_from_pages(current_doc_pages)
                        doc_filename = self._generate_document_filename(
                            filename, current_doc_start, page_num - 1
                        )
                        documents.append((doc_content, doc_filename))

                    # Start new document
                    current_doc_pages = [page]
                    current_doc_start = page_num
                else:
                    # Add page to current document
                    current_doc_pages.append(page)

            # Don't forget the last document
            if current_doc_pages:
                doc_content = self._create_pdf_from_pages(current_doc_pages)
                doc_filename = self._generate_document_filename(
                    filename, current_doc_start, len(reader.pages) - 1
                )
                documents.append((doc_content, doc_filename))

            # If no splitting occurred, return original
            if len(documents) == 0:
                return [(file_content, filename)]

            logger.info(f"Split PDF into {len(documents)} documents")
            return documents

        except Exception as e:
            logger.error(f"Error splitting batch PDF: {str(e)}")
            # Return original file if splitting fails
            return [(file_content, filename)]

    def _is_new_document_start(self, page_text: str, page_num: int) -> bool:
        """Determine if a page starts a new document."""
        if page_num == 0:
            return False  # First page is never a new document start

        # Check for batch indicators
        for indicator in self.batch_indicators:
            if indicator in page_text:
                return True

        # Check if page starts with common scientific document patterns
        lines = page_text.split("\n")
        if len(lines) > 0:
            first_line = lines[0].strip()
            # Check for title-like patterns
            if (
                len(first_line) > 20
                and len(first_line) < 200
                and first_line.isupper()
                or first_line[0].isupper()
            ):
                return True

        return False

    def _is_different_content(self, text1: str, text2: str) -> bool:
        """Check if two text blocks represent different content."""
        # Simple heuristic: if less than 30% similarity, likely different documents
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if len(words1) == 0 or len(words2) == 0:
            return True

        intersection = words1.intersection(words2)
        similarity = len(intersection) / max(len(words1), len(words2))

        return similarity < 0.3

    def _create_pdf_from_pages(self, pages: list) -> bytes:
        """Create a new PDF from a list of pages."""
        writer = PdfWriter()

        for page in pages:
            writer.add_page(page)

        output_stream = io.BytesIO()
        writer.write(output_stream)
        output_stream.seek(0)

        return output_stream.getvalue()

    def _generate_document_filename(
        self, original_filename: str, start_page: int, end_page: int
    ) -> str:
        """Generate a filename for a split document."""
        base_name = original_filename.rsplit(".", 1)[0]
        extension = (
            original_filename.rsplit(".", 1)[1] if "." in original_filename else "pdf"
        )

        if start_page == end_page:
            return f"{base_name}_page_{start_page + 1}.{extension}"
        else:
            return f"{base_name}_pages_{start_page + 1}-{end_page + 1}.{extension}"
