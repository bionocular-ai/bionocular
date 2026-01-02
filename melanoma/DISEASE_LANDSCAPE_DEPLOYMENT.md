# Disease Landscape Data on Render

## Overview

The Disease Landscape page displays statistics from **SQLite database** (on Render) or **pre-computed JSON file** (local development):

- **On Render** (`TRIALS_DATA_SOURCE=sqlite`): Stats are computed from SQLite database tables:
  - `api_discovery` - All trials discovered via API
  - `clinical_trials_cache` - Full trial details
  - `extraction_provenance` - Extracted subset (therapeutic-index trials)
  
- **Local Development** (`TRIALS_DATA_SOURCE=json`): Stats are read from:
  - **`data/deployed/disease_landscape_stats.json`** - Pre-computed statistics for each cancer type
    - Status counts (Overall Status, Recruiting, Completed, etc.)
    - Phase counts (Phase 1, Phase 2, etc.)
    - Funder type counts (Industry, Non-Industry)
    - Extracted count (therapeutic-index trials)

## Data Flow

### Disease Landscape Page (`/dashboard/[category]/disease-landscape`)

When a user visits the Disease Landscape page:

1. Frontend calls: `GET /api/landscape/disease-stats/{category}`
2. Backend checks `TRIALS_DATA_SOURCE` environment variable:
   - **If `sqlite`** (Render): Queries SQLite database directly using `get_disease_landscape_stats()`
   - **If `json`** (local dev): Reads from `data/deployed/disease_landscape_stats.json`
3. Returns statistics for that cancer type

**On Render**: Stats are computed live from SQLite (same database as trial data).
**Local Dev**: Stats are read from pre-computed JSON file (faster for development).

### Therapeutic Index Page (`/dashboard/[category]/therapeutic-index`)

Uses data from:
- `extraction_provenance` table (trials from `data/deployed/` JSON files)
- `clinical_trials_cache` table (for full trial details)

## Setup Required on Render

### On Render (Production)

**No special setup needed!** The Disease Landscape stats are computed from the SQLite database:

1. **Environment Variable**: Set `TRIALS_DATA_SOURCE=sqlite` on Render
2. **Database**: The SQLite database (`data/trials_db/trials.db`) is built from JSON files during Docker build
3. **API Data**: Run `sync_dashboard_data.py` to populate `api_discovery` and `clinical_trials_cache` tables
4. **Stats**: The backend automatically queries SQLite when `TRIALS_DATA_SOURCE=sqlite`

The stats are computed **live from SQLite** - no JSON file needed on Render!

### Local Development (Optional JSON File)

For faster local development, you can pre-compute stats to JSON:

```bash
cd melanoma
python scripts/sync_dashboard_data.py
```

This script:
- Fetches ALL trials for each of the 8 cancer types from ClinicalTrials.gov API
- Calculates statistics (status, phase, funder type) for each cancer type
- Saves to: `data/deployed/disease_landscape_stats.json`

**Note**: This JSON file is only used when `TRIALS_DATA_SOURCE=json` (local dev). On Render with `TRIALS_DATA_SOURCE=sqlite`, the backend queries SQLite directly.

## Deployment Strategy

### On Render (Production with SQLite)

1. **Set Environment Variable**: `TRIALS_DATA_SOURCE=sqlite`
2. **Build Database**: SQLite database is built from JSON files during Docker build
3. **Sync API Data**: Run `sync_dashboard_data.py` to populate:
   - `api_discovery` table (all trials by cancer type)
   - `clinical_trials_cache` table (full trial details)
   - `extraction_provenance` table (extracted subset)
4. **Stats Computed Live**: Backend queries SQLite directly - no JSON file needed!

### Local Development (Optional JSON)

1. **Set Environment Variable**: `TRIALS_DATA_SOURCE=json` (or leave unset)
2. **Generate JSON** (optional, for faster dev):
   - Run `sync_dashboard_data.py` locally
   - This generates `data/deployed/disease_landscape_stats.json`
   - Backend reads from JSON instead of querying SQLite

### Scheduled Sync on Render

To keep stats fresh on Render:

1. Use Render's Cron Jobs to run `sync_dashboard_data.py` weekly/monthly
2. This updates the SQLite database (`api_discovery`, `clinical_trials_cache`)
3. Stats are automatically computed from updated SQLite data
4. No JSON file commit needed!

## Data Refresh

The Disease Landscape data should be refreshed periodically because:
- New trials are added to ClinicalTrials.gov
- Trial statuses change over time
- New abstracts/publications are added to `data/deployed/`

**Recommended refresh schedule:**
- **On Render**: Run `sync_dashboard_data.py` via Cron Job (weekly/monthly)
- This updates SQLite database (`api_discovery`, `clinical_trials_cache`)
- Stats are automatically computed from updated SQLite data
- **Local Dev**: Optionally regenerate JSON file for faster development

## Current Status

✅ **Therapeutic Index**: Works with SQLite database
- Data is loaded from SQLite (`extraction_provenance`, `clinical_trials_cache`)
- Uses `TRIALS_DATA_SOURCE=sqlite` on Render

✅ **Disease Landscape**: Works with SQLite database (on Render)
- Stats are computed live from SQLite (`api_discovery`, `clinical_trials_cache`)
- Uses `TRIALS_DATA_SOURCE=sqlite` on Render
- Falls back to JSON file for local development (`TRIALS_DATA_SOURCE=json`)

## Quick Start for Render

1. **Set Environment Variable on Render:**
   - `TRIALS_DATA_SOURCE=sqlite`

2. **Build Database:**
   - SQLite database is built from JSON files during Docker build
   - Database location: `data/trials_db/trials.db`

3. **Sync API Data (Initial Setup):**
   ```bash
   # Run on Render or locally, then deploy database
   cd melanoma
   python scripts/sync_dashboard_data.py
   ```
   This populates:
   - `api_discovery` table (all trials by cancer type)
   - `clinical_trials_cache` table (full trial details)
   - `extraction_provenance` table (extracted subset)

4. **Deploy to Render:**
   - Database is included in Docker image
   - Backend automatically queries SQLite for stats
   - No JSON file needed!

5. **Test Endpoints:**
   - `GET /api/landscape/stats` - Should return bubble data
   - `GET /api/landscape/disease-stats/{category}` - Should return statistics from SQLite

## Troubleshooting

### No data showing on Disease Landscape page

**On Render (SQLite):**
1. Check environment variable: `TRIALS_DATA_SOURCE=sqlite`
2. Check if SQLite database exists: `data/trials_db/trials.db`
3. Check if `api_discovery` table has data:
   ```sql
   SELECT COUNT(*) FROM api_discovery;
   ```
4. Check backend logs for SQLite query errors

**Local Dev (JSON):**
1. Check if JSON file exists:
   ```bash
   ls -la data/deployed/disease_landscape_stats.json
   ```
2. Check JSON file content:
   ```bash
   cat data/deployed/disease_landscape_stats.json | jq '. | keys'
   ```
3. Check environment variable: `TRIALS_DATA_SOURCE=json` (or unset)

### Database not found (Render)

- Ensure SQLite database is built during Docker build
- Check Dockerfile: `python scripts/build_db.py --db-path data/trials_db/trials.db`
- Verify database file exists in Docker image

### Stats are outdated

**On Render:**
- Run `sync_dashboard_data.py` via Cron Job to update SQLite
- Stats are automatically computed from updated database

**Local Dev:**
- Run `sync_dashboard_data.py` to regenerate JSON file
- Or switch to `TRIALS_DATA_SOURCE=sqlite` to use SQLite like Render

