"""Domain interfaces for the ingestion system."""

from abc import ABC, abstractmethod
from typing import Optional

from .models import (
    Chunk,
    ChunkingConfiguration,
    ConferenceType,
    Document,
    DocumentType,
    IngestionRequest,
    IngestionResponse,
    ParsedAbstract,
    PostprocessingConfiguration,
    PostprocessingResult,
)


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

    @abstractmethod
    def compute_hash(self, file_content: bytes) -> str:
        """Compute hash of file content."""
        pass

    @abstractmethod
    def get_storage_info(self) -> dict:
        """Get information about storage usage."""
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
    async def is_batch_pdf(self, file_content: bytes) -> bool:
        """Determine if a PDF contains multiple documents (for information only)."""
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


# Chunking Domain Interfaces


class ChunkingStrategyInterface(ABC):
    """Interface for text chunking strategies."""

    @abstractmethod
    async def chunk_content(
        self,
        content: str,
        configuration: ChunkingConfiguration,
        document_id: Optional[str] = None,
        filename: str = "",
    ) -> list[Chunk]:
        """Chunk content according to the strategy."""
        pass

    @abstractmethod
    def supports_configuration(self, configuration: ChunkingConfiguration) -> bool:
        """Check if this strategy supports the given configuration."""
        pass


# Postprocessing Interfaces


class PostprocessorInterface(ABC):
    """Interface for conference-specific postprocessors."""

    @abstractmethod
    def get_conference_type(self) -> ConferenceType:
        """Get the conference type this processor handles."""
        pass

    @abstractmethod
    async def parse_abstract(self, abstract_text: str) -> ParsedAbstract:
        """Parse a single abstract from raw text."""
        pass

    @abstractmethod
    async def format_to_markdown(
        self, parsed_abstract: ParsedAbstract, config: PostprocessingConfiguration
    ) -> str:
        """Format parsed abstract to structured markdown."""
        pass

    @abstractmethod
    async def validate_abstract(self, parsed_abstract: ParsedAbstract) -> list[str]:
        """Validate parsed abstract and return list of issues."""
        pass

    @abstractmethod
    def clean_text(self, text: str) -> str:
        """Clean and normalize text content."""
        pass

    @abstractmethod
    def clean_table_content(self, table_text: str) -> str:
        """Clean and format table content."""
        pass


class PostprocessingServiceInterface(ABC):
    """Interface for postprocessing orchestration service."""

    @abstractmethod
    async def process_file(
        self, input_path: str, output_path: str, config: PostprocessingConfiguration
    ) -> PostprocessingResult:
        """Process a single file containing conference abstracts."""
        pass

    @abstractmethod
    async def process_batch(
        self,
        input_paths: list[str],
        output_dir: str,
        config: PostprocessingConfiguration,
    ) -> list[PostprocessingResult]:
        """Process multiple files in batch."""
        pass

    @abstractmethod
    async def validate_file(self, file_path: str) -> dict[str, any]:
        """Validate a processed file and return validation summary."""
        pass
