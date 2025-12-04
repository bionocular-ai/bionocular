# Quick Start Testing Guide

## Current Status
- ✅ Frontend is running on port 3000
- ❌ Backend is NOT running on port 8000

---

## Step 1: Start the Backend

Open a new terminal and run:

```bash
cd melanoma
python -m uvicorn src.app.api:app --reload --host 0.0.0.0 --port 8000
```

**Expected output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

---

## Step 2: Quick API Test

Once backend is running, test it:

```bash
# From the web directory
cd web
./test-api.sh
```

Or manually:
```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/trials?limit=5
```

---

## Step 3: Test Frontend

1. **Open browser:** `http://localhost:3000/dashboard`
2. **Check:**
   - Page loads
   - Data appears in table
   - Filter works
   - Click NCT ID → detail page loads

---

## Step 4: Full Testing

Follow the detailed guides:
- `TESTING.md` - Complete testing guide
- `test-frontend.md` - Frontend checklist

---

## Troubleshooting

### Backend won't start?
- Check if port 8000 is already in use
- Verify database connection
- Check Python environment

### No data in dashboard?
- Verify database has abstract documents
- Check backend logs for errors
- Test API endpoint directly

### Frontend errors?
- Check browser console (F12)
- Verify backend is running
- Check network tab for failed requests

