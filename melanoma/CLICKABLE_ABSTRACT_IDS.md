# Clickable Abstract/Publication IDs

## Summary

Abstract and publication IDs are now clickable throughout the frontend, **including in chart tooltips**. For web-scraped trials, clicking the ID opens the source URL in a new tab.

## Implementation

### Backend Changes

1. **Database Schema** (`scripts/build_db.py`)
   - Added `source_url TEXT` column to `abstracts` table
   - Updated `INSERT` statements to include `source_url`

2. **SQLite Service** (`src/app/sqlite_trials_service.py`)
   - Updated `_load_json_files()` to include `source_url` in SELECT query
   - Updated `get_full_abstract_by_id()` to include `source_url` in SELECT query
   - Added `source_url` to abstract dictionary construction

3. **JSON Service** (`src/app/json_trials_service.py`)
   - Already includes `source_url` from JSON files (no changes needed)

### Frontend Changes

1. **Type Definitions** (`web/src/lib/api.ts`)
   - Added `source_url?: string` to `Trial` interface
   - Added `source_url?: string` to `AbstractData` interface

2. **Trial Utilities** (`web/src/lib/utils/trial-utils.ts`)
   - Updated `extractAbstractDetails()` to extract and return `sourceUrl`

3. **Trial Data Table** (`web/src/components/dashboard/TrialDataTable.tsx`)
   - Updated ABSTRACT/PUBLICATION ID column to detect web-scraped trials
   - For web-scraped trials with `source_url`, creates external link with icon
   - For regular trials, maintains internal link to detail page

4. **Abstract Detail Page** (`web/src/app/trial/abstract/[abstractId]/page.tsx`)
   - Updated abstract ID display to show external link icon for web-scraped trials
   - Clicking the ID opens the source URL in a new tab

## Usage

### All Trials - Clickable in Tooltips

**In chart tooltips/pinned panels:**

#### Web-Scraped Trials
When a trial has:
- `abstract_id` starting with `"webscrape_"`
- Valid `source_url` field

The abstract/publication ID becomes a clickable link with an **external link icon (↗)** that opens the source URL in a new tab.

#### Regular ASCO/ESMO Abstracts & Publications
For conference abstracts and publications:
- Abstract/Publication ID is clickable with a **chevron right icon (→)**
- Clicking navigates to the internal trial detail page
- Uses client-side routing for fast navigation

#### NCT Numbers
- NCT numbers in tooltips are clickable with a **chevron right icon (→)**
- Clicking navigates to the NCT trial page
- Uses client-side routing for fast navigation

### Visual Indicators

- **External link icon (↗)**: Opens in new tab (web-scraped trials)
- **Chevron right icon (→)**: Internal navigation (abstracts, publications, NCT numbers)

## Testing

✅ **Backend**: API returns `source_url` for web-scraped trials
```bash
curl http://localhost:8000/api/trials/abstract/webscrape_NCT06014086
```

✅ **Frontend**: Web-scraped trial IDs are clickable in:
- Trial data tables (analytics dashboard)
- Abstract detail pages
- **Chart tooltips/pinned panels** (head-to-head comparisons)

## Files Modified

### Backend
- `melanoma/scripts/build_db.py` - Added source_url column
- `melanoma/src/app/sqlite_trials_service.py` - Updated queries to include source_url

### Frontend
- `web/src/lib/api.ts` - Added source_url to interfaces
- `web/src/lib/utils/trial-utils.ts` - Extract sourceUrl
- `web/src/types/analytics.ts` - Added sourceUrl to TrialDataPoint interface
- `web/src/lib/chart-transformers.ts` - Include sourceUrl in trial data points
- `web/src/components/dashboard/TrialDataTable.tsx` - Clickable external links in tables
- `web/src/app/trial/abstract/[abstractId]/page.tsx` - Clickable external links in detail pages
- `web/src/components/charts/HeadToHeadChart.tsx` - Clickable external links in chart tooltips

## Database

The database was rebuilt to include the `source_url` column:
```bash
poetry run python scripts/build_db.py
```

**Result**: 1071 records including 4 web-scraped trials with `source_url` populated.

