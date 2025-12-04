# Clinical Trials API Data Fetching - Documentation

## Overview

The clinical trials API service fetches structured clinical trial data from a SQLite database (`doctorci.db`) using NCT (National Clinical Trial) numbers. This service is integrated into the enhanced extraction pipeline to provide authoritative data for certain attributes.

## Architecture

### Main Service Component

**File:** `src/infrastructure/clinical_trials_api_service.py`

The `ClinicalTrialsAPIService` class is the core component that:
- Connects to a SQLite database (`data/doctorci.db`)
- Queries the `clinical_trials` table using NCT numbers
- Parses JSON fields from the database
- Returns structured `ClinicalTrialData` objects
- Provides fallback to `abstracts` table when API data is missing

### Key Methods

1. **`get_trial_data(nct_number: str)`** - Fetches complete trial data for an NCT number
2. **`get_attribute_value(nct_number: str, attribute_type: AttributeType)`** - Gets a single attribute value
3. **`get_multiple_attributes(nct_number: str, attribute_types: list, arm_info: dict)`** - Gets multiple attributes at once (used in extraction pipeline)
4. **`_get_abstracts_fallback(nct_number: str, attribute_types: list)`** - Falls back to abstracts table for missing data

## Database Structure

The service queries the `clinical_trials` table with the following key columns:

```sql
SELECT
    nct_number,
    brief_title as trial_name,
    conditions_json as cancer_type,
    primary_outcomes_json as primary_endpoint,
    secondary_outcomes_json as secondary_endpoint,
    start_date as study_start_date,
    completion_date as study_completion_date,
    results_first_posted_date as first_results,
    locations_json as trial_locations,
    sponsor_name as sponsors,
    phase_json as clinical_trial_phase,
    enrollment_count as number_of_patients,
    minimum_age,
    maximum_age,
    sex,
    interventions_json as drug_info,
    data_json
FROM clinical_trials
WHERE nct_number = ?
```

## How It Works

### 1. Initialization

```python
from src.infrastructure.clinical_trials_api_service import ClinicalTrialsAPIService

# Initialize the service with database path
api_service = ClinicalTrialsAPIService("data/doctorci.db")

# Test connection
if api_service.test_connection():
    logger.info("Clinical Trials API service connected successfully")
else:
    logger.warning("Clinical Trials API service connection failed")
    api_service = None
```

### 2. Integration in Extraction Pipeline

The service is integrated into `EnhancedExtractionService`:

**File:** `src/app/enhanced_extraction_service.py` (lines 745-781)

```python
# Extract API-sourced attributes
if include_api_data and self.clinical_trials_api_service and nct_number:
    try:
        logger.debug(f"Fetching API data for NCT: {nct_number}")
        # Prepare arm info for API service
        arm_info = {
            "arm_id": arm.arm_id,
            "arm_name": arm.arm_name,
            "generic_name": arm.generic_name,
            "brand_name": arm.brand_name,
            "dose": arm.dose,
            "dosing_schedule": arm.dosing_schedule,
        }

        api_data = self.clinical_trials_api_service.get_multiple_attributes(
            nct_number, api_attributes, arm_info
        )

        for attr_type, value in api_data.items():
            if value is not None:
                extracted_attributes[attr_type] = {
                    "value": value,
                    "source": "clinical_trials_api",
                    "confidence": 0.9,  # High confidence for API data
                    "nct_number": nct_number,
                }
    except Exception as e:
        logger.error(f"Failed to fetch API data: {e}")
```

### 3. Data Processing Flow

1. **JSON Parsing**: The service parses JSON fields from the database:
   - `conditions_json` → cancer type (normalized)
   - `primary_outcomes_json` → primary endpoint
   - `secondary_outcomes_json` → secondary endpoints
   - `locations_json` → trial locations (countries)
   - `interventions_json` → drug information
   - `phase_json` → clinical trial phase
   - `data_json` → eligibility criteria (for chemo/ICI naive, BRAF status)

2. **Location Detection**: Determines if trial runs in:
   - Europe
   - United States
   - China

3. **Eligibility Criteria Parsing**: Extracts from `data_json`:
   - Chemotherapy naive status
   - ICI (Immune Checkpoint Inhibitor) naive status
   - BRAF mutation status

4. **Drug Details Extraction**: From `interventions_json`:
   - Generic name
   - Dosage (using regex patterns)
   - Dosing schedule (using regex patterns)

5. **Fallback Mechanism**: If API data is missing, falls back to `abstracts` table for:
   - Conference, published year, abstract number
   - Trial name, sponsors, NCT number
   - Cancer type, median age, number of patients
   - Treatment details (generic name, brand name, dosage, etc.)
   - Trial design (endpoints, phase, dates)
   - Biomarker data
   - Efficacy metrics (RFS, OS, PFS, etc.)

## Scripts Using the Service

### 1. `demo_enhanced_extraction.py`

**Purpose:** Main demo script for enhanced extraction with API integration

**Key Usage:**
```python
# Initialize API service
api_service = ClinicalTrialsAPIService("data/doctorci.db")

# Pass to extraction service
extraction_service = EnhancedExtractionService(
    treatment_arm_separator=arm_separator,
    arm_aware_rag_provider=rag_provider,
    attribute_extractor=attribute_extractor,
    llm_service=llm_service,
    clinical_trials_api_service=api_service,  # <-- API service injected
)

# Extract attributes with API data enabled
result = await extraction_service.extract_attributes_from_abstract_batch(
    abstract_text=abstract_text,
    abstract_id=abstract_id,
    attributes=attributes_to_extract,
    include_api_data=True,  # <-- Enable API data fetching
)
```

### 2. `debug_extraction_queries.py`

**Purpose:** Debug script for analyzing extraction queries

**Usage:** Similar to demo script, initializes API service and passes it to extraction service.

### 3. `diagnose_rag_retrieval.py`

**Purpose:** Diagnostic tool for RAG retrieval analysis

**Usage:** Initializes API service for testing retrieval with API data integration.

## API-Sourced Attributes

The service provides data for attributes marked as "API-sourced" in the attribute configuration:

- **Trial Information:**
  - `TRIAL_NAME`
  - `CANCER_TYPE`
  - `SPONSORS`
  - `CLINICAL_TRIAL_PHASE`
  - `NUMBER_OF_PATIENTS`

- **Trial Dates:**
  - `STUDY_START_DATE`
  - `STUDY_COMPLETION_DATE`
  - `FIRST_RESULTS`

- **Endpoints:**
  - `PRIMARY_ENDPOINT`
  - `SECONDARY_ENDPOINT`

- **Locations:**
  - `TRIAL_RUN_IN_EUROPE`
  - `TRIAL_RUN_IN_US`
  - `TRIAL_RUN_IN_CHINA`

- **Demographics:**
  - `MINIMUM_AGE`
  - `MAXIMUM_AGE`
  - `SEX`

- **Treatment Details:**
  - `GENERIC_NAME` (arm-specific)
  - `BRAND_NAME` (arm-specific)
  - `DOSAGE` (arm-specific)
  - `TYPE_OF_DOSING` (arm-specific)

- **Eligibility:**
  - `CHEMOTHERAPY_NAIVE`
  - `ICI_NAIVE`
  - `BRAF_MUTATION`
  - `BIOMARKER_INCLUSION`

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Extraction Request                        │
│  (Abstract Text + NCT Number + Attributes to Extract)       │
└──────────────────────┬────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│           EnhancedExtractionService                          │
│  - Separates treatment arms                                  │
│  - Extracts attributes from abstract (LLM)                   │
│  - Fetches API data for API-sourced attributes               │
└──────────────────────┬────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│         ClinicalTrialsAPIService                             │
│  1. Query clinical_trials table by NCT number                │
│  2. Parse JSON fields                                        │
│  3. Extract eligibility criteria                             │
│  4. Determine locations                                      │
│  5. Extract drug details                                     │
│  6. Fallback to abstracts table if needed                   │
└──────────────────────┬────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              SQLite Database (doctorci.db)                   │
│  - clinical_trials table (primary source)                    │
│  - abstracts table (fallback source)                         │
└─────────────────────────────────────────────────────────────┘
```

## Configuration

**File:** `src/infrastructure/config.py`

- **Database Path:** `DB_PATH = "data/doctorci.db"`
- **JSON Field Types:** Maps field types to parser functions
- **Country Variants:** For location detection
- **Eligibility Keywords:** For parsing eligibility criteria

## Error Handling

The service includes comprehensive error handling:

1. **Database Connection Errors:** Logged and returns `None`
2. **JSON Parsing Errors:** Logged with warnings, returns `None` for that field
3. **Missing NCT Numbers:** Logged as warnings, returns `None`
4. **Missing Attributes:** Falls back to abstracts table when possible

## Example Usage

```python
from src.infrastructure.clinical_trials_api_service import ClinicalTrialsAPIService
from src.domain.extraction_models import AttributeType

# Initialize service
api_service = ClinicalTrialsAPIService("data/doctorci.db")

# Get single attribute
nct_number = "NCT01234567"
trial_name = api_service.get_attribute_value(
    nct_number, 
    AttributeType.TRIAL_NAME
)

# Get multiple attributes
attributes = [
    AttributeType.TRIAL_NAME,
    AttributeType.CANCER_TYPE,
    AttributeType.PRIMARY_ENDPOINT,
    AttributeType.CLINICAL_TRIAL_PHASE,
]

arm_info = {
    "arm_id": "arm_1",
    "arm_name": "Treatment Arm A",
    "generic_name": "pembrolizumab",
    "brand_name": "Keytruda",
    "dose": "200 mg",
    "dosing_schedule": "every 3 weeks",
}

api_data = api_service.get_multiple_attributes(
    nct_number, 
    attributes, 
    arm_info
)

# api_data will contain:
# {
#     AttributeType.TRIAL_NAME: "Study Name",
#     AttributeType.CANCER_TYPE: "Melanoma",
#     AttributeType.PRIMARY_ENDPOINT: "Overall Survival",
#     AttributeType.CLINICAL_TRIAL_PHASE: "Phase 3",
# }
```

## Notes

- The service uses **high confidence (0.9)** for API-sourced data since it comes from authoritative database
- Arm-specific attributes (like `GENERIC_NAME`, `DOSAGE`) can use arm info if provided
- The service automatically falls back to abstracts table for missing attributes
- JSON parsing is modular and configurable via `JSON_FIELD_TYPES`
- Location detection supports multiple country name variants

