# Test Plan for Analytics Optimization

This document outlines the tests needed to verify the analytics optimization changes.

## Optimizations Implemented

1. **Backend Filtering** - Moved filtering logic from frontend to backend
2. **SQLite Database** - Replaced JSON file loading with SQLite for lower memory usage
3. **Chart Aggregation Endpoint** - Pre-aggregated chart data endpoint
4. **Next.js Standalone Mode** - Optimized production bundle size

## Test Categories

### 1. SQLite Database Functionality ✅

**Status: PASSED**

Tests completed:
- ✅ Database creation from JSON files
- ✅ Data loading from SQLite
- ✅ Service selection (JSON vs SQLite)
- ✅ API endpoint integration
- ✅ Pagination
- ✅ Data integrity

**Test file**: `test_sqlite_api.py`

### 2. Backend Filtering Functionality

**Tests Needed:**

#### 2.1 Filter Parameters
- [ ] Test `resource_type=publication` returns only publications
- [ ] Test `resource_type=conference` returns only conference abstracts
- [ ] Test `resource_type=all` returns both
- [ ] Test `cancer_type` filter works correctly
- [ ] Test `therapy_type` filter works correctly
- [ ] Test `funding_type` filter (industry/non-industry) works correctly
- [ ] Test `has_metric` filter works correctly

#### 2.2 Filter Combinations
- [ ] Test multiple filters together (e.g., `resource_type=publication&cancer_type=Cutaneous Melanoma`)
- [ ] Test filters with pagination
- [ ] Test filters preserve arm_results structure

#### 2.3 Edge Cases
- [ ] Test with invalid filter values
- [ ] Test with empty results
- [ ] Test with special characters in filter values

**How to test:**
```bash
# Test publication filter
curl "http://localhost:8000/api/analytics/data?resource_type=publication&limit=10"

# Test cancer type filter
curl "http://localhost:8000/api/analytics/data?cancer_type=Cutaneous%20Melanoma&limit=10"

# Test combination
curl "http://localhost:8000/api/analytics/data?resource_type=publication&cancer_type=Uveal%20Melanoma&limit=10"
```

### 3. Memory Usage Comparison

**Tests Needed:**

#### 3.1 Backend Memory Usage
- [ ] Measure baseline memory with JSON data source
- [ ] Measure memory with SQLite data source
- [ ] Measure memory during analytics endpoint call (JSON)
- [ ] Measure memory during analytics endpoint call (SQLite)
- [ ] Compare peak memory usage

**How to test:**
```bash
# Use the existing test script
cd melanoma
poetry run python tests/test_analytics_memory.py

# Or manually check
curl "http://localhost:8000/api/resources" | python3 -m json.tool
```

**Expected Results:**
- JSON baseline: ~345MB
- SQLite baseline: ~70-100MB
- JSON analytics call: ~400-500MB peak
- SQLite analytics call: ~100-150MB peak

### 4. Response Time & Performance

**Tests Needed:**

#### 4.1 Response Time Comparison
- [ ] Measure response time for `/api/analytics/data` with JSON
- [ ] Measure response time for `/api/analytics/data` with SQLite
- [ ] Measure response time with filters (JSON)
- [ ] Measure response time with filters (SQLite)
- [ ] Measure response time for `/api/analytics/chart-data`

**How to test:**
```bash
# Time the requests
time curl -s "http://localhost:8000/api/analytics/data?limit=100" > /dev/null
time curl -s "http://localhost:8000/api/analytics/data?limit=100&resource_type=publication" > /dev/null
```

**Expected Results:**
- SQLite should be similar or faster than JSON for filtered queries
- Chart data endpoint should be faster than full data endpoint

### 5. Payload Size Comparison

**Tests Needed:**

#### 5.1 Response Size
- [ ] Measure payload size for full data (no filters)
- [ ] Measure payload size with `resource_type=publication` filter
- [ ] Measure payload size with `resource_type=conference` filter
- [ ] Measure payload size with multiple filters
- [ ] Measure payload size for `/api/analytics/chart-data`

**How to test:**
```bash
# Get response size
curl -s "http://localhost:8000/api/analytics/data?limit=2000" | wc -c
curl -s "http://localhost:8000/api/analytics/data?resource_type=publication&limit=2000" | wc -c
curl -s "http://localhost:8000/api/analytics/chart-data?target_metric=MEDIAN_OS" | wc -c
```

**Expected Results:**
- Full data: ~26MB (unchanged)
- Filtered data: Significantly smaller (e.g., publications only: ~2-3MB)
- Chart data: <100KB

### 6. Frontend Integration

**Tests Needed:**

#### 6.1 API Client
- [ ] Verify `analyticsApi.getData()` accepts filter parameters
- [ ] Verify filters are correctly passed to backend
- [ ] Verify response handling

#### 6.2 Analytics Page
- [ ] Verify page loads with filtered data
- [ ] Verify filters update API calls
- [ ] Verify chart renders correctly with filtered data
- [ ] Verify no client-side filtering remains (except therapy selection)

**How to test:**
1. Open browser DevTools Network tab
2. Navigate to analytics page
3. Change filters (resource type, therapy type, etc.)
4. Verify API calls include filter parameters
5. Verify response sizes are smaller with filters

### 7. Chart Aggregation Endpoint

**Tests Needed:**

#### 7.1 Endpoint Functionality
- [ ] Test endpoint returns correct structure
- [ ] Test aggregation calculations (average, median, min, max)
- [ ] Test treatment grouping
- [ ] Test approval status classification
- [ ] Test with different metrics

#### 7.2 Performance
- [ ] Compare response time vs full data endpoint
- [ ] Verify payload size reduction

**How to test:**
```bash
curl "http://localhost:8000/api/analytics/chart-data?target_metric=MEDIAN_OS" | python3 -m json.tool
curl "http://localhost:8000/api/analytics/chart-data?target_metric=OBJECTIVE_RESPONSE_RATE" | python3 -m json.tool
```

### 8. Production Build

**Tests Needed:**

#### 8.1 Next.js Standalone
- [ ] Verify standalone build creates `.next/standalone` directory
- [ ] Verify build size is reduced
- [ ] Verify production server starts correctly

**How to test:**
```bash
cd web
npm run build
ls -lh .next/standalone
```

### 9. Regression Tests

**Tests Needed:**

#### 9.1 Existing Functionality
- [ ] Verify all existing tests still pass
- [ ] Verify analytics page still works without filters
- [ ] Verify chart rendering works correctly
- [ ] Verify trial detail pages work

**How to test:**
```bash
cd melanoma
poetry run pytest tests/ -v
```

### 10. Integration Tests

**Tests Needed:**

#### 10.1 End-to-End Flow
- [ ] Test complete user flow: Select category → Apply filters → View chart
- [ ] Test switching between filters
- [ ] Test pagination with filters
- [ ] Test export functionality with filtered data

## Test Execution Order

1. ✅ SQLite Database Functionality (COMPLETED)
2. Backend Filtering Functionality
3. Memory Usage Comparison
4. Response Time & Performance
5. Payload Size Comparison
6. Frontend Integration
7. Chart Aggregation Endpoint
8. Production Build
9. Regression Tests
10. Integration Tests

## Success Criteria

- ✅ SQLite database loads 978 records correctly
- ✅ Backend filtering returns correct filtered results
- ✅ Memory usage with SQLite < 150MB (vs ~400MB with JSON)
- ✅ Response times acceptable (< 2s for filtered queries)
- ✅ Payload sizes reduced with filters
- ✅ Frontend correctly uses filtered data
- ✅ Chart aggregation endpoint works
- ✅ All existing tests pass
- ✅ No regressions in functionality
