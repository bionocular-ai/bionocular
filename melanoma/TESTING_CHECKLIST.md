# Pre-Deployment Testing Checklist

## ✅ Current Status

- [x] JSON files moved to `data/deployed/` directory
- [x] All 8 JSON files present:
  - [x] ASCO_2020.json
  - [x] ASCO_2021.json
  - [x] ASCO_2022.json
  - [x] ASCO_2023.json
  - [x] ASCO_2024.json
  - [x] ASCO_2025.json
  - [x] ESMO_2020-2024.json
  - [x] Publications_70.json

---

## Step 1: Test JSON Files Locally

### 1.1 Verify JSON Files Are Valid

```bash
cd /Users/marcus/Developer/bionocular/melanoma

# Test each JSON file
for file in data/deployed/*.json; do
  echo "Testing $file..."
  python3 -c "import json; json.load(open('$file'))" && echo "✅ Valid" || echo "❌ Invalid"
done
```

**Expected**: All files should show "✅ Valid"

### 1.2 Verify JSON Structure

Check that files have the expected structure:

```bash
# Check structure of one file
python3 -c "
import json
with open('data/deployed/ASCO_2020.json') as f:
    data = json.load(f)
    print('Keys:', list(data.keys()))
    if 'abstracts' in data:
        print(f'Abstracts: {len(data[\"abstracts\"])} found')
    if 'publications' in data:
        print(f'Publications: {len(data[\"publications\"])} found')
"
```

**Expected**: Should show `abstracts` and/or `publications` keys with counts

---

## Step 2: Test Backend Locally with Deployed JSON Files

### 2.1 Set Environment Variable

```bash
export TRIALS_DATA_SOURCE=json
export TRIALS_JSON_FILES="data/deployed/ASCO_2020.json,data/deployed/ASCO_2021.json,data/deployed/ASCO_2022.json,data/deployed/ASCO_2023.json,data/deployed/ASCO_2024.json,data/deployed/ASCO_2025.json,data/deployed/ESMO_2020-2024.json,data/deployed/Publications_70.json"
export DISABLE_PDF_PROCESSING=true
```

### 2.2 Start Backend Server

```bash
cd /Users/marcus/Developer/bionocular/melanoma
python3 -m uvicorn src.app.api:app --reload --host 0.0.0.0 --port 8000
```

**Expected Output**:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
INFO:     Using JSON file data source - skipping database initialization
```

### 2.3 Test Health Endpoint

```bash
curl http://localhost:8000/health
```

**Expected**: `{"status":"healthy"}`

### 2.4 Test Trials Endpoint

```bash
# Get first 5 trials
curl "http://localhost:8000/api/trials?skip=0&limit=5" | python3 -m json.tool
```

**Expected**: JSON response with:
- `trials` array with 5 trial objects
- Each trial has: `id`, `nct_id`, `title`, `phase`, `sponsor`, `status`
- `total` field showing total number of trials
- `skip` and `limit` fields

### 2.5 Test NCT Endpoint

```bash
# Get trials by NCT ID (use an NCT ID from your data)
curl "http://localhost:8000/api/trials/nct/NCT02388906?limit=10" | python3 -m json.tool
```

**Expected**: JSON response with trials matching that NCT ID

### 2.6 Test Abstract Endpoint

```bash
# Get full abstract by ID (use an abstract_id from your data)
curl "http://localhost:8000/api/trials/abstract/ASCO_2020_001" | python3 -m json.tool
```

**Expected**: Full abstract data with all attributes and arm_results

### 2.7 Check Backend Logs

Look for these log messages:
- ✅ "Using JSON file data source - skipping database initialization"
- ✅ "Loading trials data from: data/deployed/..."
- ✅ "Loaded X items from ..."

**No errors should appear!**

---

## Step 3: Test Docker Build Locally

### 3.1 Build Docker Image

```bash
cd /Users/marcus/Developer/bionocular/melanoma
docker build -t bionocular-api:test .
```

**Expected**: Build completes successfully without errors

**Note**: This may take 5-10 minutes the first time

### 3.2 Run Docker Container

```bash
docker run -d \
  -p 8000:8000 \
  -e TRIALS_DATA_SOURCE=json \
  -e TRIALS_JSON_FILES="data/deployed/ASCO_2020.json,data/deployed/ASCO_2021.json,data/deployed/ASCO_2022.json,data/deployed/ASCO_2023.json,data/deployed/ASCO_2024.json,data/deployed/ASCO_2025.json,data/deployed/ESMO_2020-2024.json,data/deployed/Publications_70.json" \
  -e DISABLE_PDF_PROCESSING=true \
  --name bionocular-test \
  bionocular-api:test
```

### 3.3 Test Docker Container

```bash
# Wait a few seconds for startup
sleep 5

# Test health
curl http://localhost:8000/health

# Test trials endpoint
curl "http://localhost:8000/api/trials?limit=5" | python3 -m json.tool
```

**Expected**: Same results as Step 2

### 3.4 Check Docker Logs

```bash
docker logs bionocular-test
```

**Expected**: 
- ✅ No errors
- ✅ "Application startup complete"
- ✅ "Loading trials data from: data/deployed/..."

### 3.5 Clean Up

```bash
docker stop bionocular-test
docker rm bionocular-test
```

---

## Step 4: Test Frontend Connection

### 4.1 Start Backend (if not running)

```bash
cd /Users/marcus/Developer/bionocular/melanoma
export TRIALS_DATA_SOURCE=json
export TRIALS_JSON_FILES="data/deployed/ASCO_2020.json,data/deployed/ASCO_2021.json,data/deployed/ASCO_2022.json,data/deployed/ASCO_2023.json,data/deployed/ASCO_2024.json,data/deployed/ASCO_2025.json,data/deployed/ESMO_2020-2024.json,data/deployed/Publications_70.json"
export DISABLE_PDF_PROCESSING=true
python3 -m uvicorn src.app.api:app --reload --host 0.0.0.0 --port 8000
```

### 4.2 Start Frontend

```bash
cd /Users/marcus/Developer/bionocular/web
npm run dev
```

### 4.3 Test in Browser

1. Open: `http://localhost:3000/dashboard`
2. **Check**:
   - [ ] Page loads without errors
   - [ ] Trials table displays data
   - [ ] Total trial count is correct
   - [ ] Can filter by sponsor/NCT
   - [ ] Can click on NCT ID to view details
   - [ ] Abstract timeline works (if applicable)

### 4.4 Check Browser Console

Open DevTools (F12) → Console tab

**Expected**: No errors, only warnings (if any)

---

## Step 5: Verify Git Status

### 5.1 Check What Will Be Committed

```bash
cd /Users/marcus/Developer/bionocular
git status
```

**Expected**: 
- ✅ `data/deployed/*.json` files are listed (not ignored)
- ✅ `Dockerfile` is listed
- ✅ `src/infrastructure/null_processor.py` is listed
- ✅ Updated `src/app/api.py` is listed

### 5.2 Verify File Sizes

```bash
cd /Users/marcus/Developer/bionocular/melanoma
du -sh data/deployed/*.json
```

**Note**: If files are very large (>50MB each), consider:
- Using Git LFS
- Compressing JSON files
- Splitting into smaller files

---

## Step 6: Pre-Deployment Checklist

Before deploying to Render:

- [ ] All JSON files are valid (Step 1.1 ✅)
- [ ] Backend runs locally and serves data (Step 2 ✅)
- [ ] Docker build succeeds (Step 3.1 ✅)
- [ ] Docker container runs and serves data (Step 3.2-3.3 ✅)
- [ ] Frontend connects to backend (Step 4 ✅)
- [ ] All files are committed to Git (Step 5 ✅)
- [ ] Environment variables documented
- [ ] Deployment guide reviewed

---

## Step 7: Deployment Environment Variables

Prepare these for Render:

```bash
TRIALS_DATA_SOURCE=json
DISABLE_PDF_PROCESSING=true
ALLOWED_ORIGINS=https://bionocular.ai,https://www.bionocular.ai
TRIALS_JSON_FILES=data/deployed/ASCO_2020.json,data/deployed/ASCO_2021.json,data/deployed/ASCO_2022.json,data/deployed/ASCO_2023.json,data/deployed/ASCO_2024.json,data/deployed/ASCO_2025.json,data/deployed/ESMO_2020-2024.json,data/deployed/Publications_70.json
```

---

## 🐛 Troubleshooting

### JSON Files Not Loading

**Symptom**: Backend logs show "JSON file not found"

**Fix**: 
- Check file paths in `TRIALS_JSON_FILES`
- Verify files exist: `ls -la data/deployed/`
- Use absolute paths or paths relative to project root

### Docker Build Fails

**Symptom**: Build errors during `poetry install`

**Fix**:
- Check `pyproject.toml` for syntax errors
- Verify Poetry version: `poetry --version`
- Try building with `--no-cache`: `docker build --no-cache -t bionocular-api:test .`

### Backend Returns Empty Trials

**Symptom**: `/api/trials` returns `{"trials": [], "total": 0}`

**Fix**:
- Check backend logs for JSON loading errors
- Verify JSON structure (should have `abstracts` or `publications` keys)
- Test JSON loading manually: `python3 -c "import json; print(len(json.load(open('data/deployed/ASCO_2020.json'))['abstracts']))"`

### Frontend Can't Connect

**Symptom**: "Backend Unavailable" error in frontend

**Fix**:
- Verify backend is running: `curl http://localhost:8000/health`
- Check `NEXT_PUBLIC_API_URL` in frontend (should be `http://localhost:8000` for local)
- Check CORS configuration in backend

---

## ✅ Ready to Deploy?

Once all checks pass:
1. ✅ Commit all changes to Git
2. ✅ Push to GitHub
3. ✅ Follow `DEPLOYMENT_GUIDE.md` for Render deployment
4. ✅ Follow `DEPLOYMENT_GUIDE.md` for Cloudflare Pages deployment

---

## 📝 Quick Test Script

Save this as `test_deployment.sh`:

```bash
#!/bin/bash
set -e

echo "🧪 Testing Bionocular Deployment Readiness"
echo ""

# Test 1: JSON files exist
echo "1. Checking JSON files..."
if [ ! -d "data/deployed" ]; then
    echo "❌ data/deployed directory not found"
    exit 1
fi

JSON_COUNT=$(ls -1 data/deployed/*.json 2>/dev/null | wc -l)
if [ "$JSON_COUNT" -lt 8 ]; then
    echo "❌ Expected 8 JSON files, found $JSON_COUNT"
    exit 1
fi
echo "✅ Found $JSON_COUNT JSON files"

# Test 2: JSON files are valid
echo "2. Validating JSON files..."
for file in data/deployed/*.json; do
    if ! python3 -c "import json; json.load(open('$file'))" 2>/dev/null; then
        echo "❌ Invalid JSON: $file"
        exit 1
    fi
done
echo "✅ All JSON files are valid"

# Test 3: Dockerfile exists
echo "3. Checking Dockerfile..."
if [ ! -f "Dockerfile" ]; then
    echo "❌ Dockerfile not found"
    exit 1
fi
echo "✅ Dockerfile exists"

# Test 4: Null processor exists
echo "4. Checking null processor..."
if [ ! -f "src/infrastructure/null_processor.py" ]; then
    echo "❌ null_processor.py not found"
    exit 1
fi
echo "✅ Null processor exists"

echo ""
echo "✅ All pre-deployment checks passed!"
echo "Ready to deploy to Render and Cloudflare Pages"
```

Make it executable and run:
```bash
chmod +x test_deployment.sh
./test_deployment.sh
```

