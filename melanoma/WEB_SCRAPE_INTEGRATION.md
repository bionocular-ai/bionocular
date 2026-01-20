# Web Scrape Data Integration

This document explains how web-scraped clinical trial data is integrated into the trials database and displayed on the frontend.

## Overview

Web-scraped trial data from company press releases and announcements is stored in `web_scrape.json` and imported into the `trials.db` SQLite database, making it available alongside conference abstracts and publications in the comparative analytics dashboard.

## Data Flow

```
web_scrape.json
    ↓
scripts/import_web_scrape.py (or build_db.py)
    ↓
data/trials_db/trials.db (abstracts table)
    ↓
API endpoints (/api/analytics/data, /api/trials)
    ↓
Frontend comparative analytics
```

## File Structure

### web_scrape.json
Location: `data/deployed/web_scrape.json`

Structure:
```json
{
  "total_trials": 4,
  "total_arms": 9,
  "total_attributes_extracted": 194,
  "data_source": "web_scrape",
  "last_updated": "2026-01-19T00:00:00Z",
  "trials": [
    {
      "trial_id": "NCT06014086",
      "nct_number": "NCT06014086",
      "source_url": "https://...",
      "web_scrape_timestamp": "2026-01-19T00:00:00Z",
      "total_arms": 3,
      "total_attributes_extracted": 55,
      "arm_results": {
        "arm_1": {
          "arm_id": "arm_1",
          "arm_name": "...",
          "cancer_type_specific": "...",
          "attributes": {
            "AttributeType.GENERIC_NAME": {
              "value": "...",
              "source": "web_scrape",
              "confidence": 1.0
            }
          }
        }
      },
      "metadata": { ... }
    }
  ]
}
```

## Database Integration

### Import Script
Use the dedicated import script to add web scrape data to an existing database:

```bash
cd melanoma
poetry run python scripts/import_web_scrape.py
```

Options:
- `--db-path`: Path to database (default: `data/trials_db/trials.db`)
- `--web-scrape-path`: Path to web scrape JSON (default: `data/deployed/web_scrape.json`)

### Rebuild Database
The `build_db.py` script now automatically includes web_scrape.json when rebuilding:

```bash
cd melanoma
poetry run python scripts/build_db.py --db-path data/trials_db/trials.db
```

### Database Schema
Web-scraped trials are stored in the `abstracts` table with:
- `abstract_id`: Prefixed with `webscrape_` (e.g., `webscrape_WTX-124`)
- `file`: Set to `web_scrape.json`
- `arm_results`: JSON string containing all arm data and attributes
- `overall_confidence`: Set to 1.0 (high confidence for direct company data)

## Data Transformation

The import script transforms web scrape trial format to match the abstracts table structure:

1. **Trial ID**: Prefixed with `webscrape_` to distinguish from conference abstracts
2. **Arm Results**: Preserved as-is (already in correct format)
3. **Attributes**: Counted across all arms for `total_attributes_extracted`
4. **Confidence**: Set to 1.0 (web-scraped data is authoritative)
5. **Timestamp**: Uses `web_scrape_timestamp` from the trial data

## Frontend Integration

The web-scraped trials automatically appear in:

### 1. Comparative Analytics Dashboard
- Path: `/dashboard/[category]/analytics`
- Web-scraped trials are included in the analytics data query
- Displayed alongside conference abstracts and publications
- Filterable by cancer type, phase, therapy type, etc.

### 2. Therapeutic Index
- Path: `/dashboard/[category]/therapeutic-index`
- Web-scraped trials contribute to therapy comparisons
- Sorted by efficacy/safety metrics

### 3. Trial Detail Pages
- Path: `/trial/nct/[nctId]` or `/trial/abstract/[abstractId]`
- Individual trial details with all arms and attributes
- Timeline view showing data evolution

## Identification

Web-scraped trials can be identified by:
1. `abstract_id` starting with `webscrape_`
2. `file` field set to `web_scrape.json`
3. `source` attribute in arm data set to `web_scrape`

## Supported Trials

Currently includes web-scraped data for:
1. **PH-762 (INTASYL siRNA)** - NCT06014086
   - 3 arms (cSCC, Merkel Cell, Melanoma)
   - Phio Pharmaceuticals

2. **WTX-124 (INDUKINE IL-2)** - WTX-124
   - 3 arms (Melanoma Post-ICI, Combination, cSCC)
   - Werewolf Therapeutics

3. **AMT-253** - NCT05906862, NCT06209580
   - 1 arm (First-Line Melanoma)
   - Multitude Therapeutics

4. **MDNA11 (ABILITY-1)** - NCT05086692
   - 2 arms (Melanoma Checkpoint-Resistant, Combination)
   - Medicenna Therapeutics

## Maintenance

### Adding New Web-Scraped Trials

1. Add trial data to `data/deployed/web_scrape.json` following the structure
2. Run import script:
   ```bash
   poetry run python scripts/import_web_scrape.py
   ```
3. Restart API server if running
4. New trials will appear in frontend analytics

### Updating Existing Trials

1. Update the trial data in `web_scrape.json`
2. Re-run the import script (uses `INSERT OR REPLACE`)
3. Changes will be reflected in the database

### Full Database Rebuild

When rebuilding the entire database:
```bash
poetry run python scripts/build_db.py --db-path data/trials_db/trials.db
```

This will:
1. Create a fresh database
2. Import all conference abstracts and publications
3. Automatically import web_scrape.json data
4. Load disease landscape stats

## API Endpoints

Web-scraped trials are accessible through standard API endpoints:

- `GET /api/analytics/data` - Includes web-scraped trials in results
- `GET /api/trials` - Lists all trials including web-scraped
- `GET /api/trials/nct/{nctId}` - Get trials by NCT number
- `GET /api/trials/abstract/{abstractId}` - Get by abstract ID (e.g., `webscrape_WTX-124`)

## Benefits

1. **Unified Interface**: Web-scraped data uses the same structure as abstracts
2. **No Code Changes**: Existing frontend code automatically handles web-scraped trials
3. **High Quality**: Direct from company press releases (high confidence)
4. **Easy Updates**: Simple JSON file updates followed by re-import
5. **Queryable**: Full SQL query capabilities on web-scraped data

## Troubleshooting

### Data Not Appearing in Frontend

1. Check database:
   ```bash
   sqlite3 data/trials_db/trials.db "SELECT COUNT(*) FROM abstracts WHERE abstract_id LIKE 'webscrape_%'"
   ```

2. Verify import:
   ```bash
   poetry run python scripts/import_web_scrape.py
   ```

3. Check API response:
   ```bash
   curl "http://localhost:8000/api/analytics/data?limit=10" | jq '.abstracts[] | select(.abstract_id | startswith("webscrape_"))'
   ```

4. Restart API server:
   ```bash
   poetry run python -m uvicorn src.app.api:app --reload
   ```

### Database Locked

If you get a "database is locked" error:
1. Stop any running API servers
2. Close any open database connections
3. Re-run the import script

## Notes

- Web-scraped trials have `overall_confidence` of 1.0 (highest confidence)
- Timestamp from `web_scrape_timestamp` tracks when data was scraped
- Source URLs preserved in trial metadata for reference
- All standard attributes (ORR, PFS, OS, etc.) supported
- Compatible with all frontend filtering and charting features

