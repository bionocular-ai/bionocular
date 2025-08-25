"""Main ingestion service for processing and storing PDF documents."""

import logging
import os
from uuid import uuid4

from ..domain.interfaces import (
    DocumentRepositoryInterface,
    IngestionServiceInterface,
    PDFProcessorInterface,
    StorageInterface,
)
from ..domain.models import (
    Document,
    DocumentStatus,
    IngestionRequest,
    IngestionResponse,
)

logger = logging.getLogger(__name__)


class IngestionService(IngestionServiceInterface):
    """Main ingestion service implementation."""

    def __init__(
        self,
        storage: StorageInterface,
        repository: DocumentRepositoryInterface,
        pdf_processor: PDFProcessorInterface,
    ):
        """Initialize the ingestion service."""
        self.storage = storage
        self.repository = repository
        self.pdf_processor = pdf_processor

        # Configuration
        self.max_file_size = (
            int(os.getenv("MAX_FILE_SIZE_MB", "100")) * 1024 * 1024
        )  # 100MB default
        self.retry_attempts = int(os.getenv("RETRY_ATTEMPTS", "3"))

    async def ingest_single_document(
        self, file_content: bytes, filename: str, request: IngestionRequest
    ) -> IngestionResponse:
        """Ingest a single document."""
        try:
            # Validate file size
            if len(file_content) > self.max_file_size:
                raise ValueError(
                    f"File size {len(file_content)} bytes exceeds maximum {self.max_file_size} bytes"
                )

            # Validate PDF
            if not await self.pdf_processor.validate_pdf(file_content):
                raise ValueError("Invalid or corrupted PDF file")

            # Check if this is a batch PDF (for information only)
            if await self.pdf_processor.is_batch_pdf(file_content):
                logger.info(f"Detected batch PDF: {filename} - processing as single document")

            # Process as single document
            return await self._process_document(file_content, filename, request)

        except Exception as e:
            logger.error(f"Error ingesting single document {filename}: {str(e)}")
            return IngestionResponse(
                document_id=uuid4(),
                original_filename=filename,
                storage_path="",
                type=request.type,
                status=DocumentStatus.PROCESSING_FAILED,
                message=f"Processing failed: {str(e)}",
                is_duplicate=False,
            )

    async def ingest_batch_documents(
        self, file_content: bytes, filename: str, request: IngestionRequest
    ) -> list[IngestionResponse]:
        """Ingest multiple documents from a batch PDF."""
        try:
            # Validate file size
            if len(file_content) > self.max_file_size:
                raise ValueError(
                    f"File size {len(file_content)} bytes exceeds maximum {self.max_file_size} bytes"
                )

            # Validate PDF
            if not await self.pdf_processor.validate_pdf(file_content):
                raise ValueError("Invalid or corrupted PDF file")

            # Process batch PDF as single document (preserve context)
            logger.info(f"Processing batch PDF as single document: {filename}")
            response = await self._process_document(file_content, filename, request)
            return [response]

        except Exception as e:
            logger.error(f"Error ingesting batch documents from {filename}: {str(e)}")
            # Return error response for the entire batch
            return [
                IngestionResponse(
                    document_id=uuid4(),
                    original_filename=filename,
                    storage_path="",
                    type=request.type,
                    status=DocumentStatus.PROCESSING_FAILED,
                    message=f"Batch processing failed: {str(e)}",
                    is_duplicate=False,
                )
            ]

    async def _process_document(
        self, file_content: bytes, filename: str, request: IngestionRequest
    ) -> IngestionResponse:
        """Process a single document through the ingestion pipeline."""
        # Compute content hash for duplicate detection
        content_hash = self.storage.compute_hash(file_content)

        # Check for duplicates
        existing_doc = await self.repository.find_by_hash(content_hash)
        if existing_doc:
            logger.info(
                f"Duplicate document detected: {filename} (hash: {content_hash[:8]}...)"
            )
            return IngestionResponse(
                document_id=existing_doc.id,
                original_filename=existing_doc.original_filename,
                storage_path=existing_doc.storage_path,
                type=existing_doc.type,
                status=existing_doc.status,
                message="Document already exists",
                is_duplicate=True,
            )

        # Store document in filesystem
        storage_path = await self.storage.store_document(
            file_content, filename, request.type
        )

        # Create document entity
        document = Document(
            original_filename=filename,
            storage_path=storage_path,
            type=request.type,
            hash=content_hash,
            metadata=request.metadata or {},
        )

        # Save to database
        saved_document = await self.repository.save_document(document)

        logger.info(f"Successfully ingested document: {filename} -> {storage_path}")

        return IngestionResponse(
            document_id=saved_document.id,
            original_filename=saved_document.original_filename,
            storage_path=saved_document.storage_path,
            type=saved_document.type,
            status=saved_document.status,
            message="Document successfully ingested",
            is_duplicate=False,
        )

    async def get_ingestion_stats(self) -> dict:
        """Get statistics about the ingestion system."""
        try:
            storage_info = self.storage.get_storage_info()

            return {
                "storage": storage_info,
                "max_file_size_mb": self.max_file_size // (1024 * 1024),
                "retry_attempts": self.retry_attempts,
            }
        except Exception as e:
            logger.error(f"Error getting ingestion stats: {str(e)}")
            return {"error": str(e)}
