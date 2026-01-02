"""Cancer type mapping and status utilities for clinical trials."""

# Active statuses for clinical trials (used for bubble sizing)
ACTIVE_STATUSES = ["RECRUITING", "ACTIVE_NOT_RECRUITING", "NOT_YET_RECRUITING"]

# Normalized skin cancer types
SKIN_CANCER_TYPES = [
    "Basal Cell Carcinoma",
    "Cutaneous Squamous Cell Carcinoma",
    "Cutaneous melanoma",
    "Uveal Melanoma",
    "Merkel Cell Carcinoma",
    "Acral Melanoma",
    "Mucosal Melanoma",
    "Cutaneous melanoma with Brain/CNS metastasis",
]

# Mapping from normalized cancer type to ClinicalTrials.gov search terms
CANCER_TYPE_MAPPING = {
    "Basal Cell Carcinoma": [
        "Basal Cell Carcinoma",
        "BCC",
        "Basal cell cancer",
    ],
    "Cutaneous Squamous Cell Carcinoma": [
        "Cutaneous Squamous Cell Carcinoma",
        "CSCC",
        "Cutaneous SCC",
        "Squamous cell carcinoma of skin",
    ],
    "Cutaneous melanoma": [
        "Cutaneous melanoma",
        "Melanoma",
        "Skin melanoma",
    ],
    "Uveal Melanoma": [
        "Uveal Melanoma",
        "Uveal melanoma",
        "Choroidal melanoma",
        "Iris melanoma",
    ],
    "Merkel Cell Carcinoma": [
        "Merkel Cell Carcinoma",
        "MCC",
        "Merkel cell cancer",
    ],
    "Acral Melanoma": [
        "Acral Melanoma",
        "Acral lentiginous melanoma",
        "Acral melanoma",
    ],
    "Mucosal Melanoma": [
        "Mucosal Melanoma",
        "Mucosal melanoma",
    ],
    "Cutaneous melanoma with Brain/CNS metastasis": [
        "Cutaneous melanoma with Brain metastasis",
        "Cutaneous melanoma with CNS metastasis",
        "Melanoma brain metastasis",
        "Melanoma CNS metastasis",
        "Melanoma brain metastases",
        "Melanoma CNS metastases",
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
