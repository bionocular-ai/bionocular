"""Domain interfaces for the ingestion system."""

from abc import ABC, abstractmethod
from typing import Any, Optional

from .models import (
    Chunk,
    ChunkingConfiguration,
    ChunkWithEmbedding,
    ConferenceType,
    Document,
    DocumentType,
    EmbeddingConfiguration,
    IngestionRequest,
    IngestionResponse,
    ParsedAbstract,
    PostprocessingConfiguration,
    PostprocessingResult,
    RAGQuery,
    RAGResponse,
    SearchQuery,
    SearchResult,
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

    @abstractmethod
    async def extract_text(self, file_content: bytes) -> str:
        """Extract text content from PDF."""
        pass

    @abstractmethod
    async def extract_metadata(self, file_content: bytes) -> dict[str, Any]:
        """Extract metadata from PDF."""
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


# =============================================================================
# EMBEDDING AND VECTOR STORE INTERFACES
# =============================================================================


class EmbeddingServiceInterface(ABC):
    """Interface for embedding generation services."""

    @abstractmethod
    async def generate_embedding(
        self, text: str, config: EmbeddingConfiguration
    ) -> list[float]:
        """Generate embedding for a single text."""
        pass

    @abstractmethod
    async def generate_embeddings_batch(
        self, texts: list[str], config: EmbeddingConfiguration
    ) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        pass

    @abstractmethod
    async def get_embedding_dimension(self, config: EmbeddingConfiguration) -> int:
        """Get the dimension of embeddings for the given model."""
        pass

    @abstractmethod
    async def validate_model(self, model_name: str) -> bool:
        """Validate that the model is available and working."""
        pass

    @abstractmethod
    async def cleanup_models(self) -> None:
        """Clean up loaded models to free memory."""
        pass


class VectorStoreInterface(ABC):
    """Interface for vector storage and retrieval."""

    @abstractmethod
    async def store_chunks(self, chunks: list[ChunkWithEmbedding]) -> None:
        """Store chunks with their embeddings."""
        pass

    @abstractmethod
    async def search_similar(self, query: SearchQuery) -> list[SearchResult]:
        """Search for similar chunks."""
        pass

    @abstractmethod
    async def get_chunk_by_id(self, chunk_id: str) -> Optional[ChunkWithEmbedding]:
        """Get a specific chunk by ID."""
        pass

    @abstractmethod
    async def delete_chunks(self, chunk_ids: list[str]) -> None:
        """Delete chunks by their IDs."""
        pass

    @abstractmethod
    async def get_store_info(self) -> dict[str, Any]:
        """Get information about the vector store."""
        pass

    @abstractmethod
    async def clear_store(self) -> None:
        """Clear all data from the vector store."""
        pass


class RAGServiceInterface(ABC):
    """Interface for RAG (Retrieval-Augmented Generation) operations."""

    @abstractmethod
    async def process_query(self, query: RAGQuery) -> RAGResponse:
        """Process a RAG query and return a response."""
        pass

    @abstractmethod
    async def generate_context(self, question: str, chunks: list[SearchResult]) -> str:
        """Generate context from retrieved chunks."""
        pass

    @abstractmethod
    async def format_response(
        self, answer: str, sources: list[SearchResult]
    ) -> RAGResponse:
        """Format the final RAG response."""
        pass
