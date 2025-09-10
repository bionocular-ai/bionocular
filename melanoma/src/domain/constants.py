"""Centralized constants and patterns for the melanoma project.

This module follows the DRY principle by centralizing all repeated strings,
magic numbers, and configuration values used throughout the codebase.
"""

from enum import Enum
from typing import Final

# =============================================================================
# CONFERENCE AND DOCUMENT PATTERNS
# =============================================================================


class ConferenceType(Enum):
    """Medical conference types."""

    ASCO = "asco"
    ESMO = "esmo"


class AbstractPatterns:
    """Regex patterns and strings for abstract parsing."""

    # Abstract ID patterns
    ABSTRACT_ID_HEADER: Final[str] = "### Abstract ID: "
    ASCO_ABSTRACT_ID: Final[str] = r"### Abstract ID: (\d+)"
    ESMO_ABSTRACT_ID: Final[str] = r"### Abstract ID: ([0-9]+[A-Z]*)"
    GENERIC_ABSTRACT_ID: Final[str] = r"Abstract ID: ([0-9]+[A-Z]*)"

    # Year extraction patterns
    ASCO_YEAR: Final[str] = r"ASCO_(\d{4})"
    ESMO_YEAR: Final[str] = r"ESMO_(\d{4})"
    GENERIC_YEAR: Final[str] = r"(\d{4})"

    # Clinical trial patterns
    NCT_PATTERN: Final[str] = r"NCT\d+"

    # Sponsor patterns
    ASCO_SPONSOR: Final[str] = r"\*\*Research Sponsor:\*\* (.+)"
    ESMO_LEGAL_ENTITY: Final[
        str
    ] = r"\*\*Legal entity responsible for the study:\*\* (.+)"
    ESMO_FUNDING: Final[str] = r"\*\*Funding:\*\* (.+)"
    GENERIC_SPONSOR: Final[str] = r"\*\*Sponsor:\*\* (.+)"

    # Title patterns
    TITLE_PATTERN: Final[str] = r"\*\*Title:\*\* (.+)"

    # Table detection
    TABLE_ROW_SEPARATOR: Final[str] = "|"
    TABLE_HEADER_SEPARATOR: Final[str] = "---"


# =============================================================================
# CHUNKING DEFAULTS
# =============================================================================


class ChunkingDefaults:
    """Default values for chunking operations."""

    DEFAULT_CHUNK_SIZE: Final[int] = 800
    DEFAULT_CHUNK_OVERLAP: Final[int] = 150
    DEFAULT_MAX_ABSTRACTS: Final[int] = None
    DEFAULT_STRATEGY: Final[str] = "hybrid"
    DEFAULT_PRESERVE_TABLES: Final[bool] = True
    DEFAULT_INCLUDE_HEADERS: Final[bool] = True


# =============================================================================
# EMBEDDING CONFIGURATION
# =============================================================================


class EmbeddingModel(Enum):
    """Available embedding models for bio-clinical text."""

    BIO_BERT_SNLI = "pritamdeka/S-BioBERT-snli-multinli-stsb"
    SCI_BERT = "allenai/scibert_scivocab_uncased"
    BIO_LINK_BERT = "michiyasunaga/BioLinkBERT-large"


class EmbeddingDefaults:
    """Default values for embedding operations."""

    DEFAULT_MODEL: Final[EmbeddingModel] = EmbeddingModel.BIO_BERT_SNLI
    DEFAULT_BATCH_SIZE: Final[int] = 32
    DEFAULT_NORMALIZE_EMBEDDINGS: Final[bool] = True
    DEFAULT_MAX_SEQUENCE_LENGTH: Final[int] = 512
    DEFAULT_SIMILARITY_THRESHOLD: Final[float] = 0.7


# =============================================================================
# VECTOR STORE CONFIGURATION
# =============================================================================


class VectorStoreDefaults:
    """Default values for vector store operations."""

    DEFAULT_COLLECTION_NAME: Final[str] = "melanoma_chunks"
    DEFAULT_PERSIST_DIRECTORY: Final[str] = "./chroma_db"
    DEFAULT_TOP_K: Final[int] = 10
    DEFAULT_SIMILARITY_THRESHOLD: Final[float] = 0.0


# =============================================================================
# API DEFAULTS
# =============================================================================


class APIDefaults:
    """Default values for API operations."""

    DEFAULT_QUERY_LIMIT: Final[int] = 100
    DEFAULT_QUERY_OFFSET: Final[int] = 0
    DEFAULT_MAX_FILE_SIZE_MB: Final[int] = 100
    DEFAULT_RETRY_ATTEMPTS: Final[int] = 3
    DEFAULT_CONTEXT_CHUNKS: Final[int] = 5


# =============================================================================
# FILE EXTENSIONS AND PATHS
# =============================================================================


class FileExtensions:
    """File extension constants."""

    PDF: Final[str] = ".pdf"
    MARKDOWN: Final[str] = ".md"
    JSON: Final[str] = ".json"


class DirectoryPaths:
    """Standard directory paths."""

    DATA_PROCESSED: Final[str] = "data/processed"
    DATA_ABSTRACTS: Final[str] = "data/abstracts"
    DATA_PUBLICATIONS: Final[str] = "data/publications"
    STORAGE_BASE: Final[str] = "./storage"
    CHROMA_DB: Final[str] = "./chroma_db"


# =============================================================================
# ERROR MESSAGES
# =============================================================================


class ErrorMessages:
    """Centralized error messages."""

    FILE_NOT_FOUND: Final[str] = "Data file not found: {file_path}"
    MODEL_LOAD_FAILED: Final[str] = "Failed to load model: {model_name}"
    EMBEDDING_GENERATION_FAILED: Final[str] = "Failed to generate embedding: {error}"
    VECTOR_STORE_ERROR: Final[str] = "Vector store operation failed: {error}"
    INVALID_QUERY: Final[str] = "Invalid query parameters: {error}"


# =============================================================================
# LOGGING MESSAGES
# =============================================================================


class LogMessages:
    """Centralized log messages."""

    MODEL_LOADING: Final[str] = "Loading embedding model: {model_name}"
    MODEL_LOADED: Final[str] = "✅ Model loaded successfully: {model_name}"
    MODEL_CLEANUP: Final[str] = "Cleaning up model: {model_name}"
    MODEL_CLEANUP_COMPLETE: Final[str] = "✅ Model cleanup completed"
    CHUNKS_STORED: Final[str] = "✅ Stored {count} chunks in vector store"
    CHUNKS_DELETED: Final[str] = "✅ Deleted {count} chunks from vector store"
    STORE_CLEARED: Final[str] = "✅ Cleared all data from vector store"
    RAG_QUERY_PROCESSED: Final[str] = "✅ RAG query processed successfully"
