# Quick Start Guide - View Data on Frontend

## Shortcut (start both servers)

From the repo root:

```bash
chmod +x start_servers.sh   # first time only
./start_servers.sh          # or: ./start_servers.sh start
```

To stop the servers (from any terminal):

```bash
./start_servers.sh stop
```

## Step 1: Start the Backend Server

Open a terminal and run:

**Recommended: Using Poetry**
```bash
cd melanoma
poetry install   # first time only, to install dependencies
poetry run uvicorn src.app.api:app --reload --host 0.0.0.0 --port 8000
```

**Alternative: Using Python directly (if dependencies are installed)**
```bash
cd melanoma
python3 -m uvicorn src.app.api:app --reload --host 0.0.0.0 --port 8000
```

**Note:** If you get "ModuleNotFoundError: No module named 'fastapi'", install dependencies first:
```bash
cd melanoma
poetry install
```

**Expected output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**Verify it's working:**
```bash
# In another terminal
curl http://localhost:8000/health
# Should return: {"status":"healthy"}

curl "http://localhost:8000/api/trials?limit=2"
# Should return JSON with trials data
```

## Step 2: Start the Frontend

Open a **new terminal** and run:

```bash
cd web
npm run dev
```

**Expected output:**
```
  ▲ Next.js 16.0.3
  - Local:        http://localhost:3000
  - Ready in 2.3s
```

## Step 3: View the Dashboard

1. Open your browser and go to: **http://localhost:3000/dashboard**
2. You should see:
   - **1,034 trials** loaded from JSON files
   - Statistics cards showing total trials, phases, statuses, cancer types
   - A data table with all trials
   - Pagination controls

## What You'll See

- **Total Trials**: 1,034 (from all JSON files)
- **ASCO Abstracts**: 626 trials
- **ESMO Abstracts**: 408 trials
- **Years**: 2020-2025
- **Phases**: Phase 1, 2, 3, 4, etc.

## Troubleshooting

### Backend won't start?
- Make sure port 8000 is not already in use
- Check Python environment: `python3 --version`
- Verify you're in the `melanoma` directory

### Frontend shows "Backend Unavailable"?
- Make sure backend is running on port 8000
- Check browser console (F12) for errors
- Verify `NEXT_PUBLIC_API_URL` is set to `http://localhost:8000` (or leave unset for default)

### No data showing?
- Check backend logs for errors
- Test API directly: `curl http://localhost:8000/api/trials?limit=5`
- Verify JSON files exist in `melanoma/data/output/`

## Quick Test

Test the API endpoint directly:
```bash
curl "http://localhost:8000/api/trials?skip=0&limit=5" | python3 -m json.tool
```

You should see JSON with 5 trials, each containing:
- `id`, `nct_id`, `title`, `phase`, `sponsor`, `status`
- `abstract_id` (from AttributeType.ABSTRACT_NUMBER)
- `cancer_type`, `year`

