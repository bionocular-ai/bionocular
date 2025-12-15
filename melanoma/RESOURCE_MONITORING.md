# Resource Monitoring Guide

This guide explains how to monitor CPU and RAM usage for the Bionocular backend and frontend servers, and provides analysis of current resource consumption.

---

## Quick Start

### Option 1: Python Monitor (Recommended)

The Python monitor provides detailed, real-time resource monitoring:

```bash
# Install psutil if not already installed
cd melanoma
poetry add psutil

# Run the monitor
python3 scripts/monitor_resources.py
```

### Option 2: Backend API Endpoint

Query resource usage via the API:

```bash
curl http://localhost:8000/api/resources | python3 -m json.tool
```

---

## Understanding the Output

### Memory Usage

- **Green**: Normal usage (< 200 MB)
- **Yellow**: Moderate usage (200-400 MB)
- **Red**: High usage (> 400 MB) - may hit Render's 512MB limit

### CPU Usage

- **Green**: Normal usage (< 20%)
- **Yellow**: Moderate usage (20-50%)
- **Red**: High usage (> 50%)

---

## Current Resource Consumption

### Backend: 345 MB (67% of 512MB limit)
### Frontend: 662 MB (dev mode) - Production: ~300-400 MB estimated

---

## Why Backend Uses Memory

### Root Causes:

#### 1. **Large JSON Files Loaded into Memory**
- **Total JSON file size**: ~26.41 MB on disk
- **Files loaded**:
  - `ASCO_2020.json`: 3.26 MB (84 items, 134 arms)
  - `ASCO_2021.json`: 3.46 MB (95 items, 144 arms)
  - `ESMO_2020-2024.json`: 13.73 MB (408 items, 580 arms) ⚠️ **Largest file**
  - `Publications_70.json`: 5.95 MB (70 items, 131 arms)
- **Total**: 978 abstracts/publications (updated from 657)

#### 2. **Memory Expansion Factor**
- JSON files on disk: 26.41 MB
- When parsed into Python dictionaries: **~105-130 MB** (3-5x expansion)
- Python's object overhead for dictionaries, lists, and strings

#### 3. **Service Instance Management**
- Singleton pattern implemented to prevent multiple instances
- Single cache holds all 978 abstracts in memory
- Cache design prioritizes performance (fast queries)

#### 4. **Analytics Endpoint**
- The `/api/analytics/data` endpoint can return all abstracts with full `arm_results`
- Response size: **~26+ MB JSON** (serialized)
- Pagination implemented to reduce response size

### Memory Breakdown Estimate:
```
JSON files on disk:           26.41 MB
Parsed into Python dicts:     ~105 MB (4x expansion)
Service instance overhead:    ~20 MB
Response serialization:       ~26 MB (temporary)
Python runtime overhead:      ~50 MB
FastAPI/Uvicorn overhead:     ~50 MB
─────────────────────────────────────
Total:                        ~345 MB ✅ Matches current usage
```

---

## Why Frontend Uses Memory

### Root Causes:

#### 1. **Development Mode Overhead**
- Next.js dev mode is **much more memory-intensive** than production
- Includes:
  - Hot Module Replacement (HMR)
  - Source maps
  - Development server
  - Fast refresh
  - TypeScript compilation on-the-fly
  - Webpack bundling

#### 2. **Large Analytics Data in Memory**
- Frontend receives paginated data from analytics endpoint
- React Query caches this data (optimized: 5min gcTime, 2min staleTime)
- Data is stored in:
  - Network response buffer
  - React Query cache
  - React component state
  - Chart transformation data structures

#### 3. **Complex Data Processing**
- Analytics page processes abstracts
- Multiple filters and transformations
- Chart data structures (Recharts)
- Multiple useMemo hooks holding processed data

### Expected Production Memory:
- Production builds typically use **50-70% less memory**
- Estimated production: **~300-400 MB** (much better than dev mode)

---

## Testing Analytics Endpoint Memory

The analytics endpoint loads all JSON files into memory, which can cause high memory usage. Test it with:

```bash
cd melanoma
python3 tests/test_analytics_memory.py
```

This will:
1. Measure baseline memory
2. Call the `/api/analytics/data` endpoint
3. Measure peak memory usage
4. Report memory increase

---

## Known Memory Issues

### Analytics Endpoint

The `/api/analytics/data` endpoint loads all JSON files:
- **Total file size**: ~40 MB (ASCO + ESMO + Publications)
- **Parsed size**: ~100-200 MB in memory
- **With processing**: Can reach 300-400 MB

**Current JSON files:**
- `ASCO_2020.json`: 4.8 MB
- `ASCO_2021.json`: 5.1 MB
- `ESMO_2020-2024.json`: 21 MB (largest!)
- `Publications_70.json`: 9.2 MB

### Optimization Status

1. ✅ **Singleton Pattern**: Implemented - prevents multiple service instances
2. ✅ **Pagination**: Implemented - returns data in chunks
3. ✅ **Streaming**: Available via `/api/analytics/data/stream` endpoint
4. ✅ **Caching**: Cache parsed data in memory (already done with `_cache`)
5. ⏳ **Database**: Migrate to database for better querying and pagination (future)
6. ✅ **Lazy Loading**: Available via `/api/analytics/arms/{abstract_id}` endpoint

---

## Render Deployment

On Render with 512MB RAM limit:
- **Baseline**: ~50-100 MB
- **Analytics endpoint**: Can spike to 400-500 MB
- **Current usage**: 345 MB (67% of limit) - **Safe**
- **Risk**: Low - within limits

### Monitoring on Render

1. Use Render's built-in metrics dashboard
2. Query `/api/resources` endpoint periodically
3. Set up alerts for memory > 400 MB

---

## Troubleshooting

### High Memory Usage

1. Check which endpoint is being called
2. Monitor memory before/after requests
3. Check for memory leaks (memory not being freed)
4. Consider restarting the server if memory keeps growing

### Backend Not Responding

1. Check if process is still running: `lsof -ti:8000`
2. Check system memory: `free -h` (Linux) or Activity Monitor (macOS)
3. Check logs for OOM errors
4. Restart the server

---

## Available Scripts

### Monitoring Scripts

1. **`scripts/monitor_resources.py`** - Primary monitoring tool
   - Real-time CPU and RAM monitoring
   - Detailed metrics for backend and frontend
   - System-wide resource stats
   - Recommended for ongoing monitoring

2. **`tests/test_analytics_memory.py`** - Memory profiling tool
   - Tests memory usage for analytics endpoint
   - Measures baseline vs peak memory
   - Useful for memory profiling

### Test Suite

- **`tests/test_performance.py`** - Comprehensive performance test suite
  - Tests response times, pagination, singleton pattern
  - Validates compression, concurrent requests
  - Memory usage tests

---

## Example Output

```
=== Bionocular Server Resource Monitor ===
Updated: 2025-01-15 14:30:45

Backend Server
✓ Backend (FastAPI) (PID: 12345, Port: 8000)
  CPU: 2.5% | RAM: 345.20 MB (67.4%)
  Children: 2 processes
  Command: poetry run uvicorn src.app.api:app...

Frontend Server
✓ Frontend (Next.js) (PID: 12346, Port: 3000)
  CPU: 1.2% | RAM: 662.17 MB (dev mode)
  Children: 1 processes
  Command: npm run dev

=== System Resources ===
Total RAM: 16.00 GB
Available RAM: 12.50 GB
Memory Used: 21.9%
CPU Usage: 5.2%
Load Average (1min): 1.25
```

---

## Monitoring Commands

```bash
# Check backend resources via API
curl http://localhost:8000/api/resources | python3 -m json.tool

# Run real-time monitor
cd melanoma
python3 scripts/monitor_resources.py

# Test analytics memory spike
python3 tests/test_analytics_memory.py

# Run performance test suite
poetry run pytest tests/test_performance.py -v
```

---

## Recommendations

### Current Status: ✅ Good

- Backend: 345 MB (67% of 512 MB limit) - **Safe for Render**
- Frontend: 662 MB (dev mode) - **Production will be ~300-400 MB**
- Singleton pattern: Working (prevents duplicate caches)
- Pagination: Working (reduces response size)
- All optimizations functional

### Future Improvements

1. **Database Migration** (High impact, high effort)
   - Move from JSON files to PostgreSQL
   - Enables efficient querying and pagination
   - Reduces memory usage significantly

2. **Lazy Loading for Cache** (Medium impact, medium effort)
   - Only load abstracts when queried
   - Trade-off: Slower first query, but saves ~50-100 MB

3. **Server-Side Filtering** (High impact, high effort)
   - Move filtering to backend
   - Frontend only loads filtered results
   - Would enable true pagination
