"""Configuration constants for Clinical Trials API service and related infra."""

import os
from pathlib import Path

# Resolve paths relative to this package so they work regardless of process cwd.
# config.py lives at melanoma/src/infrastructure/config.py -> parent.parent = melanoma
_MELANOMA_ROOT = Path(__file__).resolve().parent.parent.parent
# Base data directory (melanoma/data)
DATA_DIR = _MELANOMA_ROOT / "data"

# Database configuration
DB_PATH = str(DATA_DIR / "doctorci.db")  # Legacy database for abstracts fallback

# Clinical trials database path (absolute so it works from any cwd)
# Override with CLINICAL_TRIAL_DB_PATH environment variable if needed
_default_trials_db = str((DATA_DIR / "trials_db" / "trials.db").resolve())
CLINICAL_TRIAL_DB_PATH = os.getenv("CLINICAL_TRIAL_DB_PATH", _default_trials_db)

# Disease landscape stats JSON file
DISEASE_LANDSCAPE_STATS_PATH = str(
    (DATA_DIR / "deployed" / "disease_landscape_stats.json").resolve()
)
# Live ticker JSON file (articles + efficacy/safety results per category)
LIVE_TICKER_PATH = str((DATA_DIR / "deployed" / "live_ticker.json").resolve())

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
