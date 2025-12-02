"""Null PDF processor for environments where PDF processing is disabled.

This processor implements the PDFProcessorInterface but disables actual
PDF processing functionality. It's useful for deployment environments
where PDF processing is handled elsewhere (e.g., Google Colab) and the
API server only needs to serve pre-processed data.
"""

import logging
from typing import Any

from ..domain.interfaces import PDFProcessorInterface

logger = logging.getLogger(__name__)


class NullPDFProcessor(PDFProcessorInterface):
    """Null PDF processor that disables PDF processing on the server.

    This processor provides minimal validation but raises errors when
    attempting to extract text or metadata, making it clear that PDF
    processing is not available on this server instance.
    """

    async def validate_pdf(self, file_content: bytes) -> bool:
        """Validate that the file appears to be a PDF.

        This is a minimal validation that only checks the PDF header.
        For full validation, use a proper PDF processor.

        Args:
            file_content: PDF file content as bytes

        Returns:
            True if file starts with PDF header, False otherwise
        """
        if not file_content:
            return False

        # Basic PDF header check: PDF files start with %PDF
        is_pdf = file_content[:4] == b"%PDF"

        if not is_pdf:
            logger.warning("File does not appear to be a valid PDF (missing header)")

        return is_pdf

    async def is_batch_pdf(self, file_content: bytes) -> bool:
        """Determine if a PDF contains multiple documents.

        Since we can't process PDFs, we always return False.

        Args:
            file_content: PDF file content as bytes

        Returns:
            Always False (cannot determine without processing)
        """
        return False

    async def extract_text(self, file_content: bytes) -> str:
        """Extract text content from PDF.

        This method raises NotImplementedError to indicate that PDF
        processing is disabled on this server.

        Args:
            file_content: PDF file content as bytes

        Raises:
            NotImplementedError: Always, since PDF processing is disabled
        """
        raise NotImplementedError(
            "PDF text extraction is disabled on this server. "
            "PDF processing should be done externally (e.g., Google Colab) "
            "and results should be ingested via the JSON data source."
        )

    async def extract_metadata(self, file_content: bytes) -> dict[str, Any]:
        """Extract metadata from PDF.

        This method raises NotImplementedError to indicate that PDF
        processing is disabled on this server.

        Args:
            file_content: PDF file content as bytes

        Raises:
            NotImplementedError: Always, since PDF processing is disabled
        """
        raise NotImplementedError(
            "PDF metadata extraction is disabled on this server. "
            "PDF processing should be done externally (e.g., Google Colab) "
            "and results should be ingested via the JSON data source."
        )
