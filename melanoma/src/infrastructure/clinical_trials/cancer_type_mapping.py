"""Cancer type mapping and status utilities for clinical trials."""

# Active statuses for clinical trials (used for bubble sizing)
ACTIVE_STATUSES = ["RECRUITING", "ACTIVE_NOT_RECRUITING", "NOT_YET_RECRUITING"]

# Normalized skin cancer types
SKIN_CANCER_TYPES = [
    "Basal Cell Carcinoma",
    "Cutaneous Squamous Cell Carcinoma",
    "Cutaneous Melanoma",
    "Uveal Melanoma",
    "Merkel Cell Carcinoma",
    "Acral Melanoma",
    "Mucosal Melanoma",
    "Cutaneous Melanoma with Brain/CNS Metastasis",
]

# Mapping from normalized cancer type to ClinicalTrials.gov search terms.
# One exact canonical term per type — the API's partial matching handles
# variant phrasings (e.g. "Merkel Cell Carcinoma" matches
# "Merkel cell carcinoma of the skin").
CANCER_TYPE_MAPPING = {
    "Cutaneous Melanoma": ["Cutaneous melanoma"],
    "Cutaneous Squamous Cell Carcinoma": ["Cutaneous Squamous Cell Carcinoma"],
    "Uveal Melanoma": ["Uveal Melanoma"],
    "Acral Melanoma": ["Acral Melanoma"],
    "Mucosal Melanoma": ["Mucosal Melanoma"],
    "Basal Cell Carcinoma": ["Basal Cell Carcinoma"],
    "Merkel Cell Carcinoma": ["Merkel Cell Carcinoma"],
    # Brain and CNS are queried separately in the service and merged under this tag
    "Cutaneous Melanoma with Brain/CNS Metastasis": [
        "Cutaneous melanoma with Brain metastasis",
        "Cutaneous melanoma with CNS metastasis",
    ],
}


def is_active_status(status: str) -> bool:
    """Check if a trial status is considered active.

    Args:
        status: Trial status string

    Returns:
        True if status is in ACTIVE_STATUSES, False otherwise
    """
    return status in ACTIVE_STATUSES


def get_condition_search_terms(cancer_type_tag: str) -> list[str]:
    """Get search terms for a cancer type.

    Args:
        cancer_type_tag: Normalized cancer type tag

    Returns:
        List of search terms for ClinicalTrials.gov API
    """
    return CANCER_TYPE_MAPPING.get(cancer_type_tag, [cancer_type_tag])
