"""Domain models for the ingestion system."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


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
    upload_date: datetime = Field(default_factory=datetime.utcnow)
    hash: str = Field(
        ..., description="SHA-256 hash of the PDF content for duplicate detection"
    )
    status: DocumentStatus = Field(default=DocumentStatus.INGESTED)
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Extensible metadata"
    )

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


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
    created_at: datetime = Field(default_factory=datetime.utcnow)


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
