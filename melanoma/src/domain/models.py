"""Domain models for the ingestion system."""

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .constants import EmbeddingDefaults, EmbeddingModel


class DocumentType(str, Enum):
    """Document type enumeration."""

    ABSTRACT = "abstract"
    PUBLICATION = "publication"


class DocumentStatus(str, Enum):
    """Document processing status enumeration."""

    INGESTED = "ingested"
    PROCESSING_FAILED = "processing_failed"


class Document(BaseModel):
    """Document entity representing a PDF document."""

    id: UUID = Field(default_factory=uuid4)
    original_filename: str = Field(
        ..., description="Original filename of the uploaded PDF"
    )
    storage_path: str = Field(..., description="Path where the PDF is stored locally")
    type: DocumentType = Field(
        ..., description="Type of document (abstract or publication)"
    )
    upload_date: datetime = Field(default_factory=lambda: datetime.now(UTC))
    hash: str = Field(
        ..., description="SHA-256 hash of the PDF content for duplicate detection"
    )
    status: DocumentStatus = Field(default=DocumentStatus.INGESTED)
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Extensible metadata"
    )

    model_config = ConfigDict(use_enum_values=True)


class IngestionRequest(BaseModel):
    """Request model for document ingestion."""

    type: DocumentType = Field(..., description="Type of document being ingested")
    metadata: Optional[dict[str, Any]] = Field(default_factory=dict)


class IngestionResponse(BaseModel):
    """Response model for document ingestion."""

    document_id: UUID
    original_filename: str
    storage_path: str
    type: DocumentType
    status: DocumentStatus
    message: str
    is_duplicate: bool = False


class BatchIngestionResponse(BaseModel):
    """Response model for batch document ingestion."""

    total_processed: int
    successful: int
    failed: int
    duplicates: int
    documents: list[IngestionResponse]
    errors: list[str] = Field(default_factory=list)


# Chunking Domain Models


class ChunkType(str, Enum):
    """Type of content chunk."""

    ABSTRACT_HEADER = "abstract_header"
    BACKGROUND = "background"
    METHODS = "methods"
    RESULTS = "results"
    CONCLUSIONS = "conclusions"
    TABLE = "table"
    TRIAL_DESIGN = "trial_design"
    CLINICAL_TRIAL = "clinical_trial"
    SPONSOR = "sponsor"
    FUNDING = "funding"
    LEGAL_ENTITY = "legal_entity"
    DOI = "doi"
    FULL_TEXT_REFERENCE = "full_text_reference"
    FULL_ABSTRACT = "full_abstract"


# Postprocessing Domain Models


class ConferenceType(str, Enum):
    """Type of medical conference."""

    ASCO = "asco"
    ESMO = "esmo"


class PostprocessingConfiguration(BaseModel):
    """Configuration for postprocessing operations."""

    conference_type: ConferenceType = Field(
        ..., description="Type of conference abstracts"
    )
    exclude_authors: bool = Field(
        default=True, description="Whether to exclude author information"
    )
    preserve_tables: bool = Field(
        default=True, description="Whether to preserve table formatting"
    )
    expand_abbreviations: bool = Field(
        default=True, description="Whether to expand medical abbreviations"
    )
    standardize_terminology: bool = Field(
        default=True, description="Whether to standardize medical terminology"
    )


class ParsedAbstract(BaseModel):
    """Parsed abstract data structure."""

    id: str = Field(..., description="Abstract identifier")
    title: str = Field(..., description="Abstract title")
    authors_and_affiliations: str = Field(default="", description="Author information")
    background: str = Field(default="", description="Background section")
    methods: str = Field(default="", description="Methods section")
    trial_design: str = Field(default="", description="Trial design section (ESMO)")
    results: str = Field(default="", description="Results section")
    conclusions: str = Field(default="", description="Conclusions section")
    clinical_trial_info: str = Field(
        default="", description="Clinical trial information"
    )
    sponsor: str = Field(default="", description="Research sponsor/funding")
    legal_entity: str = Field(default="", description="Legal entity responsible (ESMO)")
    funding: str = Field(default="", description="Funding information (ESMO)")
    doi: str = Field(default="", description="DOI link (ESMO)")
    full_text_reference: str = Field(default="", description="Full text reference")
    additional_content: str = Field(
        default="", description="Additional content (tables, etc.)"
    )


class PostprocessingResult(BaseModel):
    """Result of postprocessing operation."""

    success: bool = Field(..., description="Whether postprocessing succeeded")
    abstracts_processed: int = Field(
        default=0, description="Number of abstracts processed"
    )
    abstracts_with_warnings: int = Field(
        default=0, description="Number of abstracts with warnings"
    )
    structured_metadata_count: int = Field(
        default=0, description="Number of abstracts with structured metadata"
    )
    conference_specific_features: int = Field(
        default=0, description="Number of conference-specific features detected"
    )
    output_path: str = Field(..., description="Path to processed output file")
    validation_summary: dict[str, Any] = Field(
        default_factory=dict, description="Validation results"
    )
    errors: list[str] = Field(default_factory=list, description="Processing errors")


class ChunkingStrategy(str, Enum):
    """Available chunking strategies."""

    HEADER_BASED = "header_based"
    RECURSIVE = "recursive"
    HYBRID = "hybrid"


class Chunk(BaseModel):
    """A chunk of content from a document."""

    id: UUID = Field(default_factory=uuid4)
    document_id: UUID = Field(..., description="ID of the source document")
    content: str = Field(..., description="The actual chunk content")
    chunk_type: ChunkType = Field(..., description="Type of content in this chunk")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Chunk-specific metadata"
    )
    sequence_number: int = Field(
        ..., description="Order of this chunk within the document"
    )
    token_count: Optional[int] = Field(
        None, description="Number of tokens in this chunk"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ChunkingConfiguration(BaseModel):
    """Configuration for chunking strategy."""

    strategy: ChunkingStrategy = Field(default=ChunkingStrategy.HYBRID)
    max_chunk_size: int = Field(
        default=1000, description="Maximum chunk size in characters"
    )
    chunk_overlap: int = Field(default=200, description="Overlap between chunks")
    preserve_tables: bool = Field(
        default=True, description="Keep tables as separate chunks"
    )
    include_headers: bool = Field(
        default=True, description="Include section headers in chunks"
    )


# =============================================================================
# EMBEDDING AND VECTOR STORE MODELS
# =============================================================================


class EmbeddingConfiguration(BaseModel):
    """Configuration for embedding generation."""

    model_name: EmbeddingModel = Field(
        default=EmbeddingDefaults.DEFAULT_MODEL, description="Embedding model to use"
    )
    batch_size: int = Field(
        default=EmbeddingDefaults.DEFAULT_BATCH_SIZE,
        description="Batch size for embedding generation",
        ge=1,
        le=128,
    )
    normalize_embeddings: bool = Field(
        default=EmbeddingDefaults.DEFAULT_NORMALIZE_EMBEDDINGS,
        description="Whether to normalize embeddings",
    )
    max_sequence_length: int = Field(
        default=EmbeddingDefaults.DEFAULT_MAX_SEQUENCE_LENGTH,
        description="Maximum sequence length for the model",
        ge=128,
        le=1024,
    )

    @field_validator("batch_size")
    @classmethod
    def validate_batch_size(cls, v):
        """Validate batch size is reasonable."""
        if v < 1 or v > 128:
            raise ValueError("Batch size must be between 1 and 128")
        return v

    @field_validator("max_sequence_length")
    @classmethod
    def validate_sequence_length(cls, v):
        """Validate sequence length is reasonable."""
        if v < 128 or v > 1024:
            raise ValueError("Sequence length must be between 128 and 1024")
        return v


class ChunkWithEmbedding(Chunk):
    """Chunk with embedding vector."""

    embedding: Optional[list[float]] = Field(
        default=None, description="Vector embedding of the chunk content"
    )
    embedding_model: Optional[str] = Field(
        default=None, description="Model used to generate the embedding"
    )
    embedding_dimension: Optional[int] = Field(
        default=None, description="Dimension of the embedding vector", ge=1
    )
    embedding_generated_at: Optional[datetime] = Field(
        default=None, description="When the embedding was generated"
    )

    @model_validator(mode="after")
    def validate_embedding_dimension(self):
        """Validate embedding dimension matches the vector length."""
        if (
            self.embedding is not None
            and self.embedding_dimension is not None
            and len(self.embedding) != self.embedding_dimension
        ):
            raise ValueError(
                f"Embedding dimension mismatch: expected {self.embedding_dimension}, got {len(self.embedding)}"
            )
        return self


class SearchQuery(BaseModel):
    """Query for semantic search."""

    text: str = Field(..., description="Query text to search for", min_length=1)
    top_k: int = Field(
        default=10, description="Number of top results to return", ge=1, le=100
    )
    similarity_threshold: float = Field(
        default=0.0, description="Minimum similarity score threshold", ge=0.0, le=1.0
    )
    metadata_filters: dict[str, Any] = Field(
        default_factory=dict, description="Filters to apply to metadata"
    )
    chunk_types: Optional[list[ChunkType]] = Field(
        default=None, description="Filter by specific chunk types"
    )
    embedding: Optional[list[float]] = Field(
        default=None, description="Pre-computed query embedding"
    )

    @field_validator("text")
    @classmethod
    def validate_text_not_empty(cls, v):
        """Validate text is not empty."""
        if not v.strip():
            raise ValueError("Query text cannot be empty")
        return v.strip()

    @field_validator("top_k")
    @classmethod
    def validate_top_k(cls, v):
        """Validate top_k is reasonable."""
        if v < 1 or v > 100:
            raise ValueError("top_k must be between 1 and 100")
        return v


class SearchResult(BaseModel):
    """Result from semantic search."""

    chunk: ChunkWithEmbedding = Field(..., description="Matching chunk")
    similarity_score: float = Field(..., description="Similarity score", ge=0.0, le=1.0)
    rank: int = Field(..., description="Rank in search results", ge=1)

    @field_validator("similarity_score")
    @classmethod
    def validate_similarity_score(cls, v):
        """Validate similarity score is in valid range."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Similarity score must be between 0.0 and 1.0")
        return v


class RAGQuery(BaseModel):
    """Query for RAG (Retrieval-Augmented Generation)."""

    question: str = Field(..., description="Question to answer", min_length=1)
    context_chunks: int = Field(
        default=5, description="Number of context chunks to retrieve", ge=1, le=20
    )
    similarity_threshold: float = Field(
        default=EmbeddingDefaults.DEFAULT_SIMILARITY_THRESHOLD,
        description="Minimum similarity for context chunks",
        ge=0.0,
        le=1.0,
    )
    metadata_filters: dict[str, Any] = Field(
        default_factory=dict, description="Filters for context retrieval"
    )

    @field_validator("question")
    @classmethod
    def validate_question_not_empty(cls, v):
        """Validate question is not empty."""
        if not v.strip():
            raise ValueError("Question cannot be empty")
        return v.strip()

    @field_validator("context_chunks")
    @classmethod
    def validate_context_chunks(cls, v):
        """Validate context_chunks is reasonable."""
        if v < 1 or v > 20:
            raise ValueError("context_chunks must be between 1 and 20")
        return v


class RAGResponse(BaseModel):
    """Response from RAG query."""

    answer: str = Field(..., description="Generated answer")
    context_chunks: list[SearchResult] = Field(
        ..., description="Chunks used as context"
    )
    confidence_score: float = Field(
        ..., description="Overall confidence in the answer", ge=0.0, le=1.0
    )
    sources: list[dict[str, Any]] = Field(
        ..., description="Source information for citations"
    )
    processing_time_ms: Optional[int] = Field(
        default=None,
        description="Time taken to process the query in milliseconds",
        ge=0,
    )

    @field_validator("confidence_score")
    @classmethod
    def validate_confidence_score(cls, v):
        """Validate confidence score is in valid range."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Confidence score must be between 0.0 and 1.0")
        return v
