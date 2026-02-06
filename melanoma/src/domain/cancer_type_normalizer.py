"""Cancer type normalization for pipeline.

This module normalizes various cancer type names to the standard 8 categories
used in the bionocular pipeline.
"""

from typing import Optional

# Standard cancer types in the pipeline
STANDARD_CANCER_TYPES = [
    "Basal Cell Carcinoma",
    "Cutaneous Squamous Cell Carcinoma",
    "Cutaneous melanoma",
    "Uveal Melanoma",
    "Merkel Cell Carcinoma",
    "Acral Melanoma",
    "Mucosal Melanoma",
    "Cutaneous melanoma with Brain/CNS metastasis",
]

# Mapping from various names to standard names
CANCER_TYPE_MAPPING = {
    # Basal Cell Carcinoma
    "basal cell carcinoma": "Basal Cell Carcinoma",
    "bcc": "Basal Cell Carcinoma",
    # Cutaneous Squamous Cell Carcinoma
    "cutaneous squamous cell carcinoma": "Cutaneous Squamous Cell Carcinoma",
    "cscc": "Cutaneous Squamous Cell Carcinoma",
    "squamous cell carcinoma": "Cutaneous Squamous Cell Carcinoma",
    # Cutaneous melanoma - ALL variants map to the same category
    "cutaneous melanoma": "Cutaneous melanoma",
    "resected cutaneous melanoma": "Cutaneous melanoma",
    "unresectable cutaneous melanoma": "Cutaneous melanoma",
    "unresectable or metastatic cutaneous melanoma": "Cutaneous melanoma",
    "unresectable or metastatic melanoma": "Cutaneous melanoma",
    "advanced cutaneous melanoma": "Cutaneous melanoma",
    "metastatic melanoma": "Cutaneous melanoma",
    "metastatic cutaneous melanoma": "Cutaneous melanoma",
    "advanced melanoma": "Cutaneous melanoma",
    "melanoma": "Cutaneous melanoma",
    "cutaneous malignant melanoma": "Cutaneous melanoma",
    # Uveal Melanoma
    "uveal melanoma": "Uveal Melanoma",
    "uveal / mucosal / acral melanoma": "Uveal Melanoma",  # Mixed, defaulting to first
    # Merkel Cell Carcinoma
    "merkel cell carcinoma": "Merkel Cell Carcinoma",
    "mcc": "Merkel Cell Carcinoma",
    # Acral Melanoma
    "acral melanoma": "Acral Melanoma",
    "acral melanoma, mucosal melanoma, unresectable cutaneous melanoma": "Acral Melanoma",  # Mixed
    # Mucosal Melanoma
    "mucosal melanoma": "Mucosal Melanoma",
    # Cutaneous melanoma with Brain/CNS metastasis (parent category)
    "cutaneous melanoma with brain metastasis": "Cutaneous melanoma with Brain/CNS metastasis",
    "cutaneous melanoma with cns metastasis": "Cutaneous melanoma with Brain/CNS metastasis",
    "cutaneous melanoma with brain/cns metastasis": "Cutaneous melanoma with Brain/CNS metastasis",
    "melanoma with brain metastases": "Cutaneous melanoma with Brain/CNS metastasis",
    "melanoma of unknown primary": "Cutaneous melanoma",  # Default to cutaneous
    # Other/generic terms
    "cutaneous head and neck melanomas": "Cutaneous melanoma",
    "(unspecified)": None,  # No specific cancer type
    "[n/a]": None,
    "": None,
}


def normalize_cancer_type(cancer_type: str) -> Optional[str]:
    """Normalize a cancer type to one of the 8 standard categories.

    Args:
        cancer_type: Raw cancer type string from data

    Returns:
        Normalized cancer type from STANDARD_CANCER_TYPES, or None if no match
    """
    if not cancer_type or not cancer_type.strip():
        return None

    # Normalize input
    normalized_input = cancer_type.strip().lower()

    # Direct lookup
    if normalized_input in CANCER_TYPE_MAPPING:
        return CANCER_TYPE_MAPPING[normalized_input]

    # Fuzzy matching for common patterns

    # Brain/CNS metastasis takes priority (more specific)
    if (
        "brain" in normalized_input or "cns" in normalized_input
    ) and "melanoma" in normalized_input:
        return "Cutaneous melanoma with Brain/CNS metastasis"

    # Resected/Unresectable melanoma → all map to Cutaneous melanoma
    if (
        "resected" in normalized_input or "unresectable" in normalized_input
    ) and "melanoma" in normalized_input:
        return "Cutaneous melanoma"

    # Melanoma types
    if "uveal" in normalized_input:
        return "Uveal Melanoma"
    if "mucosal" in normalized_input:
        return "Mucosal Melanoma"
    if "acral" in normalized_input:
        return "Acral Melanoma"
    if "melanoma" in normalized_input:
        return "Cutaneous melanoma"

    # Skin cancer types
    if "merkel" in normalized_input:
        return "Merkel Cell Carcinoma"
    if "basal cell" in normalized_input:
        return "Basal Cell Carcinoma"
    if "squamous cell" in normalized_input:
        return "Cutaneous Squamous Cell Carcinoma"

    # Unknown - return None
    return None


def is_subcategory_match(specific: str, general: str) -> bool:
    """Check if a specific cancer type matches a general category.

    For example:
    - "Resected Cutaneous Melanoma" matches "Cutaneous melanoma"
    - "Cutaneous melanoma with Brain metastasis" matches "Cutaneous melanoma with Brain/CNS metastasis"

    Args:
        specific: Specific cancer type (e.g., from trial data)
        general: General category (one of STANDARD_CANCER_TYPES)

    Returns:
        True if specific is a subcategory of general
    """
    if not specific or not general:
        return False

    normalized_specific = normalize_cancer_type(specific)
    normalized_general = normalize_cancer_type(general)

    return normalized_specific == normalized_general


def normalize_cancer_type_with_splitting(cancer_type: str) -> list[str]:
    """
    Normalize cancer types with splitting for combinations.

    Examples:
        "Melanoma" -> ["Cutaneous melanoma"]
        "Melanoma, Basal Cell Carcinoma" -> ["Cutaneous melanoma", "Basal Cell Carcinoma"]
        "Advanced Melanoma" -> ["Cutaneous melanoma"]

    Args:
        cancer_type: Raw cancer type string (may contain comma-separated types)

    Returns:
        List of normalized cancer type strings (may be empty if none found)
    """
    if not cancer_type:
        return []

    # Split by comma and normalize each part
    parts = [part.strip() for part in cancer_type.split(",")]
    normalized = []

    for part in parts:
        if part:
            normalized_type = normalize_cancer_type(part)
            if normalized_type and normalized_type not in normalized:
                normalized.append(normalized_type)

    return normalized


def get_primary_cancer_type(cancer_type: str) -> str:
    """
    Get the primary (first) normalized cancer type from a string.

    Examples:
        "Melanoma" -> "Cutaneous melanoma"
        "Melanoma, Basal Cell Carcinoma" -> "Cutaneous melanoma"
        "Advanced Melanoma" -> "Cutaneous melanoma"
        "Unknown Type" -> ""

    Args:
        cancer_type: Raw cancer type string (may contain comma-separated types)

    Returns:
        String with the primary normalized cancer type, or empty string if none found
    """
    normalized_types = normalize_cancer_type_with_splitting(cancer_type)
    return normalized_types[0] if normalized_types else ""
