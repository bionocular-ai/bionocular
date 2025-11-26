"""Cancer type normalization utility.

This module provides functions to normalize various cancer type variations
to the 10 main skin cancer categories used for filtering and categorization.
"""

from typing import Optional


# The 10 main skin cancer categories
MAIN_CANCER_TYPES = [
    "Resected Cutaneous Melanoma",
    "Unresectable Cutaneous Melanoma",
    "Cutaneous melanoma with Brain metastasis",
    "Cutaneous Melanoma with CNS metastasis",
    "Uveal Melanoma",
    "Mucosal Melanoma",
    "Acral Melanoma",
    "Basal Cell Carcinoma",
    "Merkel Cell Carcinoma",
    "Cutaneous Squamous Cell Carcinoma",
]


def normalize_cancer_type(cancer_type: str | None) -> str:
    """Normalize a cancer type string to one of the 10 main categories.
    
    This function handles:
    - Various melanoma type variations
    - Combinations (takes first type from comma-separated values)
    - Case-insensitive matching
    - Whitespace normalization
    
    Args:
        cancer_type: The cancer type string to normalize (can be None or empty)
        
    Returns:
        Normalized cancer type string from MAIN_CANCER_TYPES, or "Review Required"
        if the type cannot be mapped to a known category.
        
    Examples:
        >>> normalize_cancer_type("Melanoma")
        'Unresectable Cutaneous Melanoma'
        >>> normalize_cancer_type("Acral Melanoma, Mucosal Melanoma")
        'Acral Melanoma'  # Returns first type
        >>> normalize_cancer_type("High-risk stage II melanoma")
        'Resected Cutaneous Melanoma'
    """
    if not cancer_type:
        return "Review Required"
    
    # Normalize input: strip whitespace and convert to lowercase for matching
    clean_input = cancer_type.strip().lower()
    
    if not clean_input:
        return "Review Required"
    
    # Check if it's already one of the main types (case-insensitive)
    for main_type in MAIN_CANCER_TYPES:
        if clean_input == main_type.lower():
            return main_type
    
    # Mapping dictionary: lowercase input -> normalized output
    # This handles all the variations mentioned in the mapping strategy
    mapping = {
        # --- Mucosal Mappings ---
        "advanced mucosal melanoma": "Mucosal Melanoma",
        "resectable mucosal melanoma": "Mucosal Melanoma",
        "resected mucosal melanoma": "Mucosal Melanoma",
        "mucosal melanoma": "Mucosal Melanoma",
        
        # --- Resected Cutaneous Mappings ---
        "fully resectable, locally advanced melanoma": "Resected Cutaneous Melanoma",
        "high-risk stage ii melanoma": "Resected Cutaneous Melanoma",
        "high-risk stage 2 melanoma": "Resected Cutaneous Melanoma",
        "stage ii melanoma": "Resected Cutaneous Melanoma",
        "stage 2 melanoma": "Resected Cutaneous Melanoma",
        "resectable cutaneous melanoma": "Resected Cutaneous Melanoma",
        "resected cutaneous melanoma": "Resected Cutaneous Melanoma",
        
        # --- Unresectable/Advanced Mappings ---
        "advanced cutaneous melanoma": "Unresectable Cutaneous Melanoma",
        "advanced non-uveal melanoma": "Unresectable Cutaneous Melanoma",
        "advanced, metastatic melanoma": "Unresectable Cutaneous Melanoma",
        "advanced metastatic melanoma": "Unresectable Cutaneous Melanoma",
        "advanced melanoma": "Unresectable Cutaneous Melanoma",
        "cutaneous malignant melanoma": "Unresectable Cutaneous Melanoma",
        "cutaneous melanoma": "Unresectable Cutaneous Melanoma",
        "melanoma": "Unresectable Cutaneous Melanoma",
        "melanoma of unknown primary": "Unresectable Cutaneous Melanoma",
        "metastatic cutaneous melanoma": "Unresectable Cutaneous Melanoma",
        "metastatic melanoma": "Unresectable Cutaneous Melanoma",
        "unresectable or metastatic melanoma": "Unresectable Cutaneous Melanoma",
        "unresectable or metastatic cutaneous melanoma": "Unresectable Cutaneous Melanoma",
        "unresectable cutaneous melanoma": "Unresectable Cutaneous Melanoma",
        "malignant melanoma": "Unresectable Cutaneous Melanoma",
        "melanoma stage iii": "Unresectable Cutaneous Melanoma",
        "melanoma stage iv": "Unresectable Cutaneous Melanoma",
        "melanoma stage 3": "Unresectable Cutaneous Melanoma",
        "melanoma stage 4": "Unresectable Cutaneous Melanoma",
        
        # --- Brain/CNS Metastasis Mappings ---
        "cutaneous melanoma with brain metastasis": "Cutaneous melanoma with Brain metastasis",
        "cutaneous melanoma with cns metastasis": "Cutaneous Melanoma with CNS metastasis",
        "melanoma with brain metastasis": "Cutaneous melanoma with Brain metastasis",
        "melanoma with cns metastasis": "Cutaneous Melanoma with CNS metastasis",
        "brain metastasis melanoma": "Cutaneous melanoma with Brain metastasis",
        "cns metastasis melanoma": "Cutaneous Melanoma with CNS metastasis",
        
        # --- Exact Matches (Self-Mapping) ---
        "acral melanoma": "Acral Melanoma",
        "basal cell carcinoma": "Basal Cell Carcinoma",
        "cutaneous squamous cell carcinoma": "Cutaneous Squamous Cell Carcinoma",
        "uveal melanoma": "Uveal Melanoma",
        "merkel cell carcinoma": "Merkel Cell Carcinoma",
        
        # --- Additional variations ---
        "squamous cell carcinoma": "Cutaneous Squamous Cell Carcinoma",  # Assume cutaneous if not specified
        "carcinoma, basal cell": "Basal Cell Carcinoma",
    }
    
    # Direct mapping lookup (exact match)
    if clean_input in mapping:
        return mapping[clean_input]
    
    # If input contains commas, check if it's a comma-separated list of types
    # by trying to match the first part first
    # This handles cases like "Acral Melanoma, Mucosal Melanoma" where
    # we want to match the first type, not a partial match from later in the string
    if "," in clean_input:
        first_part = clean_input.split(",")[0].strip()
        if first_part:
            # Try to normalize the first part first
            first_part_result = normalize_cancer_type(first_part)
            if first_part_result != "Review Required":
                return first_part_result
            # If first part doesn't match, continue with full string matching
    
    # Handle partial matches for more flexible matching
    # Check if any key in the mapping is contained in the input
    # We iterate in order to prioritize more specific matches
    # (e.g., "advanced mucosal melanoma" should match before just "mucosal melanoma")
    matched_key = None
    matched_length = 0
    
    for key, value in mapping.items():
        # Check if the key is contained in the input
        if key in clean_input:
            # Prefer longer/more specific matches
            if len(key) > matched_length:
                matched_key = key
                matched_length = len(key)
    
    if matched_key:
        return mapping[matched_key]
    
    # If no match found, return "Review Required" for manual review
    return "Review Required"


def normalize_cancer_type_with_splitting(cancer_type: str | None) -> list[str]:
    """Normalize cancer type and handle combinations by splitting.
    
    This function handles cases where multiple cancer types are combined
    with commas (e.g., "Acral Melanoma, Mucosal Melanoma"). It splits
    them into separate normalized types.
    
    Args:
        cancer_type: The cancer type string to normalize (can contain commas)
        
    Returns:
        List of normalized cancer type strings. If the input contains
        multiple types separated by commas, returns a list with each
        type normalized separately. Empty list if input is None/empty.
        
    Examples:
        >>> normalize_cancer_type_with_splitting("Acral Melanoma, Mucosal Melanoma")
        ['Acral Melanoma', 'Mucosal Melanoma']
        >>> normalize_cancer_type_with_splitting("Melanoma")
        ['Unresectable Cutaneous Melanoma']
        >>> normalize_cancer_type_with_splitting("Unknown Type")
        ['Review Required']
    """
    if not cancer_type:
        return []
    
    # Split by comma and normalize each part
    parts = [part.strip() for part in cancer_type.split(",")]
    
    # Normalize each part and collect unique results
    normalized_types = []
    seen = set()
    
    for part in parts:
        if part:  # Skip empty parts
            normalized = normalize_cancer_type(part)
            # Only add if not already seen (avoid duplicates)
            if normalized not in seen:
                normalized_types.append(normalized)
                seen.add(normalized)
    
    return normalized_types if normalized_types else ["Review Required"]


def get_primary_cancer_type(cancer_type: str | None) -> str:
    """Get the primary (first) normalized cancer type from a potentially combined string.
    
    This is useful when you need a single category for filtering, and you want
    to use the first type if multiple are present.
    
    Args:
        cancer_type: The cancer type string (can contain commas)
        
    Returns:
        The first normalized cancer type, or "Review Required" if empty/invalid.
        
    Examples:
        >>> get_primary_cancer_type("Acral Melanoma, Mucosal Melanoma")
        'Acral Melanoma'
        >>> get_primary_cancer_type("Melanoma")
        'Unresectable Cutaneous Melanoma'
    """
    normalized_list = normalize_cancer_type_with_splitting(cancer_type)
    return normalized_list[0] if normalized_list else "Review Required"

