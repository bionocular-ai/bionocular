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
