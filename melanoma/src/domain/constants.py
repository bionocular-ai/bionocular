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
    # Title pattern - new format has title as separate section
    TITLE_PATTERN: Final[str] = r"#### Title:\s*\n(.+?)(?:\n####|\n\n|$)"

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


# =============================================================================
# ATTRIBUTE OUTPUT ORDER
# =============================================================================


# Canonical output order for clinical trial attributes
# This ensures consistent ordering in exported data and reports
ATTRIBUTE_OUTPUT_ORDER: Final[tuple[str, ...]] = (
    # File-level metadata (Abstracts)
    "conference",
    "published_year",
    "abstract_number",
    # Publication-level metadata
    "publication_name",
    "publication_year",
    "pdf_number",
    # Trial identification
    "nct_number",
    "trial_name",
    "cancer_type",
    # Geographic presence
    "company_eu",
    "company_us",
    "company_china",
    "sponsors",
    # Trial design
    "clinical_trial_phase",
    # Patient population
    "chemotherapy_naive",
    "chemotherapy_failed",
    "ici_naive",
    "ici_failed",
    "ipilimumab_failure",
    "anti_pd1_failure",
    "mutation_status",
    "braf_mutation",
    "nras_mutation",
    "biosimilar",
    "line_of_treatment",
    # Study endpoints
    "primary_endpoint",
    "secondary_endpoint",
    # Biomarkers
    "biomarker_inclusion",
    "biomarkers_inclusion_criteria",
    "biomarkers_exclusion_criteria",
    # Trial timeline
    "study_start_date",
    "study_completion_date",
    "first_results",
    # Geographic execution
    "trial_run_in_europe",
    "trial_run_in_us",
    "trial_run_in_china",
    # Treatment details
    "generic_name",
    "brand_name",
    "dosage",
    "type_of_dosing",
    "mechanism_of_action",
    "target_protein",
    "type_of_therapy",
    # Demographics
    "median_age",
    "number_of_patients",
    # Progression-Free Survival (PFS)
    "median_pfs",
    "median_followup_pfs",
    "p_value_pfs",
    "hr_pfs",
    # Overall Survival (OS)
    "median_os",
    "median_followup_os",
    "p_value_os",
    "hr_os",
    # Response rates
    "objective_response_rate",
    "complete_response",
    "pathological_complete_response",
    "complete_metabolic_response",
    "disease_control_rate",
    "clinical_benefit_rate",
    # Duration of Response
    "median_dor",
    "dor_rate",
    # PFS rates over time
    "pfs_rate_6m",
    "pfs_rate_9m",
    "pfs_rate_12m",
    "pfs_rate_18m",
    "pfs_rate_24m",
    "pfs_rate_36m",
    "pfs_rate_48m",
    # OS rates over time
    "os_rate_6m",
    "os_rate_9m",
    "os_rate_12m",
    "os_rate_18m",
    "os_rate_24m",
    "os_rate_36m",
    "os_rate_48m",
    # Other survival metrics
    "efs",
    "p_value_efs",
    "hr_efs",
    "rfs",
    "p_value_rfs",
    "length_rfs",
    "hr_rfs",
    "mfs",
    "length_mfs",
    "hr_mfs",
    "ttr",
    "ttp",
    "ttnt",
    "ttf",
    # Adverse Events (AE)
    "ae",
    "grade_3_plus_ae",
    "ae_leading_to_discontinuation",
    "serious_ae",
    "immune_related_ae",
    "serious_immune_related_ae",
    "ae_leading_to_death",
    # Treatment-Emergent Adverse Events (TEAE)
    "teae",
    "grade_3_plus_teae",
    "grade_3_teae",
    "grade_4_teae",
    "grade_5_teae",
    "teae_leading_to_discontinuation",
    "teae_leading_to_death",
    "serious_teae",
    "teae_immune_related",
    # Treatment-Related Adverse Events (TRAE)
    "trae",
    "grade_3_plus_trae",
    "grade_3_trae",
    "grade_4_trae",
    "grade_5_trae",
    "trae_leading_to_discontinuation",
    "trae_leading_to_death",
    "trae_immune_related",
    "serious_trae",
    # Specific adverse events
    "crs",
    "wbc_decreased",
    # Grade 3+ AE Specific Adverse Events
    "grade_3_plus_ae_crs",
    "grade_3_plus_ae_thrombocytopenia",
    "grade_3_plus_ae_neutropenia",
    "grade_3_plus_ae_leukopenia",
    "grade_3_plus_ae_nausea",
    "grade_3_plus_ae_anemia",
    "grade_3_plus_ae_diarrhea",
    "grade_3_plus_ae_colitis",
    "grade_3_plus_ae_hyperglycemia",
    "grade_3_plus_ae_neutrophil_count_decreased",
    "grade_3_plus_ae_dyspnea",
    "grade_3_plus_ae_pyrexia",
    "grade_3_plus_ae_bleeding",
    "grade_3_plus_ae_pruritus",
    "grade_3_plus_ae_rash",
    "grade_3_plus_ae_pneumonia",
    "grade_3_plus_ae_thyroiditis",
    "grade_3_plus_ae_hypophysitis",
    "grade_3_plus_ae_hepatitis",
    "grade_3_plus_ae_pneumonitis",
    "grade_3_plus_ae_alanine_aminotransferase",
    "grade_3_plus_ae_wbc_decreased",
    "grade_3_plus_ae_immune_related",
    # Grade 3+ TRAE Specific Adverse Events
    "grade_3_plus_trae_immune_related",
    "grade_3_plus_trae_crs",
    "grade_3_plus_trae_thrombocytopenia",
    "grade_3_plus_trae_neutropenia",
    "grade_3_plus_trae_leukopenia",
    "grade_3_plus_trae_nausea",
    "grade_3_plus_trae_anemia",
    "grade_3_plus_trae_diarrhea",
    "grade_3_plus_trae_colitis",
    "grade_3_plus_trae_hyperglycemia",
    "grade_3_plus_trae_neutrophil_count_decreased",
    "grade_3_plus_trae_dyspnea",
    "grade_3_plus_trae_pyrexia",
    "grade_3_plus_trae_bleeding",
    "grade_3_plus_trae_pruritus",
    "grade_3_plus_trae_rash",
    "grade_3_plus_trae_pneumonia",
    "grade_3_plus_trae_thyroiditis",
    "grade_3_plus_trae_hypophysitis",
    "grade_3_plus_trae_hepatitis",
    "grade_3_plus_trae_pneumonitis",
    "grade_3_plus_trae_alanine_aminotransferase",
    "grade_3_plus_trae_wbc_decreased",
    # Grade 3+ TEAE Specific Adverse Events
    "grade_3_plus_teae_immune_related",
    "grade_3_plus_teae_crs",
    "grade_3_plus_teae_thrombocytopenia",
    "grade_3_plus_teae_neutropenia",
    "grade_3_plus_teae_leukopenia",
    "grade_3_plus_teae_nausea",
    "grade_3_plus_teae_anemia",
    "grade_3_plus_teae_diarrhea",
    "grade_3_plus_teae_colitis",
    "grade_3_plus_teae_hyperglycemia",
    "grade_3_plus_teae_neutrophil_count_decreased",
    "grade_3_plus_teae_dyspnea",
    "grade_3_plus_teae_pyrexia",
    "grade_3_plus_teae_bleeding",
    "grade_3_plus_teae_pruritus",
    "grade_3_plus_teae_rash",
    "grade_3_plus_teae_pneumonia",
    "grade_3_plus_teae_thyroiditis",
    "grade_3_plus_teae_hypophysitis",
    "grade_3_plus_teae_hepatitis",
    "grade_3_plus_teae_pneumonitis",
    "grade_3_plus_teae_alanine_aminotransferase",
    "grade_3_plus_teae_wbc_decreased",
)


def get_ordered_attributes(attributes_dict: dict) -> dict:
    """Order attributes according to ATTRIBUTE_OUTPUT_ORDER.

    Args:
        attributes_dict: Dictionary of attributes with any keys

    Returns:
        Ordered dictionary with attributes in canonical output order.
        Attributes not in ATTRIBUTE_OUTPUT_ORDER are appended at the end.
    """
    ordered = {}

    # First, add attributes in the canonical order
    for attr_name in ATTRIBUTE_OUTPUT_ORDER:
        # Try different key formats
        possible_keys = [
            attr_name,  # e.g., "nct_number"
            attr_name.upper(),  # e.g., "NCT_NUMBER"
            f"AttributeType.{attr_name.upper()}",  # e.g., "AttributeType.NCT_NUMBER"
        ]

        for key in possible_keys:
            if key in attributes_dict:
                ordered[key] = attributes_dict[key]
                break

    # Add any remaining attributes that weren't in the canonical order
    for key, value in attributes_dict.items():
        if key not in ordered:
            ordered[key] = value

    return ordered


def get_ordered_attribute_list(attribute_types: list) -> list:
    """Order a list of AttributeType enums according to ATTRIBUTE_OUTPUT_ORDER.

    Args:
        attribute_types: List of AttributeType enum values to order

    Returns:
        List of AttributeType enums in canonical output order.
        AttributeTypes not in ATTRIBUTE_OUTPUT_ORDER are appended at the end.
    """
    # Create mapping from snake_case name to AttributeType
    attr_map = {}
    for attr_type in attribute_types:
        # Convert enum value to snake_case (e.g., "nct_number")
        snake_case = attr_type.value.lower()
        attr_map[snake_case] = attr_type

    # Order according to canonical sequence
    ordered = []

    # Add attributes in canonical order
    for attr_name in ATTRIBUTE_OUTPUT_ORDER:
        if attr_name in attr_map:
            ordered.append(attr_map[attr_name])
            del attr_map[attr_name]  # Remove so we don't add twice

    # Add any remaining attributes not in canonical order
    ordered.extend(attr_map.values())

    return ordered


# =============================================================================
# PUBLICATION POSTPROCESSING PATTERNS
# =============================================================================


class PublicationPostprocessingPatterns:
    """Regex patterns for publication postprocessing."""

    # Headers and footers to remove
    DOWNLOADED_FROM: Final[str] = r"^Downloaded from.*"
    COPYRIGHT: Final[str] = r"^(\*)?Copyright ©.*\*?$"
    PROTECTED_BY_COPYRIGHT: Final[str] = r"^Protected by copyright.*"
    TECHNOLOGY_RELATED: Final[str] = r"^Technology related to text and data mining.*"
    NEJM_HEADER: Final[str] = r"^The NEW ENGLAND JOURNAL of MEDICINE"
    LANCET_HEADER: Final[str] = r"^www\.thelancet\.com.*"
    JCO_HEADER: Final[str] = r"^J Clin Oncol \d+.*"
    JITC_HEADER: Final[str] = r"^J Immunother Cancer: first published as.*"

    # Page numbers (standalone digits)
    PAGE_NUMBER: Final[str] = r"^\d{3,4}$"

    # Graph artifacts (number sequences)
    NUMBER_SEQUENCE: Final[str] = r"^\d+(\s+\d+)+$"

    # "No. at Risk" or "Number at risk" tables
    NUMBER_AT_RISK_START: Final[str] = r"^(No\.|Number)\s+at\s+risk"
    NUMBER_AT_RISK_LINE: Final[str] = r"^\d+(\s+\d+){2,}$"

    # Table continuation markers
    TABLE_CONTINUED: Final[str] = r"\(Continued from previous page\)"

    # CSV-dump table detection (quoted strings with commas)
    CSV_DUMP_PATTERN: Final[str] = r'^"[^"]*"(?:\s*,\s*"[^"]*")+'

    # Citation normalization
    CITATION_BRACKETS: Final[str] = r"\[(\d+(?:[-,]\d+)*)\]"
    CITATION_CARET: Final[str] = r"\^(\d+(?:[-,]\d+)*)\^"

    # Document type headers to remove at start
    ORIGINAL_ARTICLE: Final[str] = r"^#{0,4}\s*\*?\*?original\s+article\*?\*?$"
    ORIGINAL_REPORT: Final[str] = r"^#{0,4}\s*\*?\*?original\s+report\*?\*?$"
    ORIGINAL_RESEARCH: Final[str] = r"^#{0,4}\s*\*?\*?original\s+research\*?\*?$"
    RESEARCH_ARTICLE: Final[str] = r"^#{0,4}\s*\*?\*?research\s+article\*?\*?$"
    RESEARCH_REPORT: Final[str] = r"^#{0,4}\s*\*?\*?research\s+report\*?\*?$"
    SHORT_REPORT: Final[str] = r"^#{0,4}\s*\*?\*?short\s+report\*?\*?$"
    BRIEF_REPORT: Final[str] = r"^#{0,4}\s*\*?\*?brief\s+report\*?\*?$"
    JOURNAL_CLINICAL_ONCOLOGY: Final[
        str
    ] = r"^#{0,4}\s*\*?\*?journal\s+of\s+clinical\s+oncology\*?\*?$"
    SCIENCEDIRECT: Final[str] = r"^#{0,4}\s*\*?\*?sciencedirect\*?\*?$"
    CROSSMARK: Final[str] = r"^#{0,4}\s*\*?\*?crossmark\*?\*?$"
    JAMA_ONCOLOGY: Final[str] = r"^#{0,4}\s*\*?\*?jama\s+oncology.*\*?\*?$"
    AVAILABLE_ONLINE: Final[str] = r"^Available\s+online.*"
    JOURNAL_HOMEPAGE: Final[str] = r"^journal\s+homepage:.*"
    OPEN_ACCESS: Final[str] = r"^#{0,4}\s*\*?\*?open\s+access\*?\*?$"
    ESTABLISHED_IN: Final[str] = r"^established\s+in\s+\d{4}.*"
    ORIGINAL_ARTICLE_WITH_JOURNAL: Final[
        str
    ] = r"^#{0,4}\s*\*?\*?original\s+article\s+.*\*?\*?$"
