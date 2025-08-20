"""Domain interfaces for the ingestion system."""

from abc import ABC, abstractmethod
from typing import Optional

from .models import Document, DocumentType, IngestionRequest, IngestionResponse


class StorageInterface(ABC):
    """Interface for document storage operations."""

    @abstractmethod
    async def store_document(
        self, file_content: bytes, filename: str, document_type: DocumentType
    ) -> str:
        """Store a document and return the storage path."""
        pass

    @abstractmethod
    async def document_exists(self, content_hash: str) -> bool:
        """Check if a document with the given hash already exists."""
        pass

    @abstractmethod
    async def get_document_path(self, content_hash: str) -> Optional[str]:
        """Get the storage path of an existing document."""
        pass


class DocumentRepositoryInterface(ABC):
    """Interface for document data persistence operations."""

    @abstractmethod
    async def save_document(self, document: Document) -> Document:
        """Save a document to the database."""
        pass

    @abstractmethod
    async def find_by_hash(self, content_hash: str) -> Optional[Document]:
        """Find a document by its content hash."""
        pass

    @abstractmethod
    async def find_by_id(self, document_id: str) -> Optional[Document]:
        """Find a document by its ID."""
        pass


class PDFProcessorInterface(ABC):
    """Interface for PDF processing operations."""

    @abstractmethod
    async def split_batch_pdf(
        self, file_content: bytes, filename: str
    ) -> list[tuple[bytes, str]]:
        """Split a batch PDF into individual documents.

        Returns:
            List of tuples containing (document_content, suggested_filename)
        """
        pass

    @abstractmethod
    async def is_batch_pdf(self, file_content: bytes) -> bool:
        """Determine if a PDF contains multiple documents."""
        pass

    @abstractmethod
    async def validate_pdf(self, file_content: bytes) -> bool:
        """Validate that the file is a valid PDF."""
        pass


class IngestionServiceInterface(ABC):
    """Interface for the main ingestion service."""

    @abstractmethod
    async def ingest_single_document(
        self, file_content: bytes, filename: str, request: IngestionRequest
    ) -> IngestionResponse:
        """Ingest a single document."""
        pass

    @abstractmethod
    async def ingest_batch_documents(
        self, file_content: bytes, filename: str, request: IngestionRequest
    ) -> list[IngestionResponse]:
        """Ingest multiple documents from a batch PDF."""
        pass
