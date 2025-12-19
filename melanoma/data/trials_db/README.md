# SQLite Trials Database

This directory contains the SQLite database for clinical trials data.

## Database Location
- **Path**: `data/trials_db/trials.db`
- **Size**: ~43MB
- **Records**: 978 total (909 abstracts + 69 publications)

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

## Maintenance

To update the database when JSON files change:

1. Update the JSON files in `data/deployed/`
2. Rebuild the database using the build script
3. Restart the API server (if running)

The database is read-only during runtime - all updates must be done by rebuilding from JSON files.
