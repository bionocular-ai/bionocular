# SQLite Trials Database

This directory contains the SQLite database for clinical trials data.

## Database Location
- **Path**: `data/trials_db/trials.db`
- **Records**: 1071 total (1002 abstracts + 69 publications); rebuild to refresh after JSON updates

## Building the Database

To rebuild the database from JSON files:

```bash
cd melanoma
poetry run python scripts/build_db.py --db-path data/trials_db/trials.db
```

## Using SQLite as Data Source

Set the following environment variables:

```bash
export TRIALS_DATA_SOURCE=sqlite
export TRIALS_DB_PATH=data/trials_db/trials.db
```

Or in your `.env` file:
```
TRIALS_DATA_SOURCE=sqlite
TRIALS_DB_PATH=data/trials_db/trials.db
```

## API Endpoints

Once SQLite is configured, all analytics endpoints will use the database:

- `GET /api/analytics/data` - Get analytics data with filtering
- `GET /api/analytics/chart-data` - Get pre-aggregated chart data
- `GET /api/trials` - Get trials list

### Example Queries

```bash
# Get all data (paginated)
curl "http://localhost:8000/api/analytics/data?limit=10&skip=0"

# Filter by resource type (publications only)
curl "http://localhost:8000/api/analytics/data?resource_type=publication&limit=10"

# Filter by resource type (conference abstracts only)
curl "http://localhost:8000/api/analytics/data?resource_type=conference&limit=10"

# Filter by cancer type
curl "http://localhost:8000/api/analytics/data?cancer_type=Cutaneous%20Melanoma&limit=10"

# Get chart data
curl "http://localhost:8000/api/analytics/chart-data?target_metric=MEDIAN_OS"
```

## Benefits

- **Lower Memory Usage**: SQLite reads from disk on-demand instead of loading all data into RAM
- **Faster Queries**: Indexed queries are faster than scanning JSON files
- **Better Scalability**: Can handle larger datasets without memory issues

## Database Schema

The database contains a single table `abstracts` with the following structure:

- `id` - Primary key
- `abstract_id` - Abstract identifier (for conference abstracts)
- `publication_id` - Publication identifier (for publications)
- `file` - Source file name
- `total_arms` - Number of treatment arms
- `total_attributes_extracted` - Number of attributes extracted
- `overall_confidence` - Extraction confidence score
- `processing_time_ms` - Processing time in milliseconds
- `errors` - JSON array of errors
- `warnings` - JSON array of warnings
- `arm_results` - JSON object containing all arm data
- `created_at` - Creation timestamp

## Dashboard clinical trials (api_discovery + clinical_trials_cache)

The main dashboard at `/dashboard` shows trial cards by cancer type. That data comes from:

- **`api_discovery`** – NCT numbers per cancer type
- **`clinical_trials_cache`** – Full API response JSON per NCT

These tables are created and updated by the clinical trials sync (e.g. `scripts/sync_dashboard_data.py`) or by importing from an existing ClinicalTrials.gov API database. If you have data in `data/clinical_trial_api/clinical_trial_api.db`, you can copy it into trials.db:

```bash
cd melanoma
poetry run python scripts/import_clinical_trial_api_to_trials.py
```

See `scripts/import_clinical_trial_api_to_trials.py` for options. Without these tables populated, the dashboard will show zero trials for the selected cancer type.

## Trial categorisation (trial_categorization)

Curated **Modality**, **Target**, **Trial_Name**, and **Cancer type** (e.g. from `data/output/trial_categorizer.txt`) are stored in a separate table **`trial_categorization`** so that:

- The API cache stays a raw copy of ClinicalTrials.gov; categorisation is our layer.
- You can refresh categorisation without touching the cache or api_discovery.
- Dashboard trial cards can show and filter by modality/target; title can use the curated Trial_Name when present.

**Cancer type** is not in the categorizer file; it is mapped from the **`api_discovery`** table (same DB). When you load from the txt file or from the seed, any NCT that appears in `api_discovery` gets its `cancer_type` set from the discovery table (if an NCT appears in multiple cancer types, all tags are stored comma-separated). This keeps a single source of truth for “which cancer type(s) this trial belongs to” in `api_discovery`, while still exposing cancer type on trial categorization for display and filtering.

Load from the txt file:

```bash
cd melanoma
poetry run python scripts/load_trial_categorizer.py
```

To bake categorisation into the Docker image: run `scripts/load_trial_categorizer.py --export-seed`, commit `data/deployed/trial_categorization_seed.json`, and rebuild; `build_db.py` will load it when present.

## Maintenance

To update the database when JSON files change:

1. Update the JSON files in `data/deployed/`
2. Rebuild the database using the build script
3. Restart the API server (if running)

The database is read-only during runtime - all updates must be done by rebuilding from JSON files.
