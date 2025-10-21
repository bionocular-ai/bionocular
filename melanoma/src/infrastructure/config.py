"""Configuration constants for Clinical Trials API service and related infra."""

# Database configuration
DB_PATH = "data/doctorci.db"

# Country variants for location checking
COUNTRY_VARIANTS = {
    "United States": ["United States", "USA", "US"],
    "Europe": ["Europe", "European", "EU"],
    "China": ["China", "Chinese"],
}

# JSON field parsing configuration
JSON_FIELD_TYPES = {
    "cancer_type": "list_of_strings",
    "phase": "list_of_strings",
    "primary_endpoint": "primary_endpoint",
    "secondary_endpoint": "secondary_endpoint",
    "locations": "locations",
    "interventions": "interventions",
}

# Eligibility criteria keywords for attribute extraction (reserved for Phase 2)
ELIGIBILITY_KEYWORDS = {
    "chemotherapy_naive": [
        "no prior chemotherapy",
        "chemotherapy naive",
        "no prior systemic therapy",
    ],
    "ici_naive": [
        "no prior immunotherapy",
        "ici naive",
        "no prior checkpoint inhibitor",
    ],
    "braf_mutation": ["braf mutation", "braf v600", "braf positive"],
    "biomarker_inclusion": ["pd-l1", "biomarker", "molecular marker"],
}
