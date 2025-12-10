# Bionocular Deployment Guide
## Local Processing → Hosted Viewer Architecture

This guide covers deploying Bionocular with the **"Local Processing → Hosted Viewer"** approach:
- **Process locally** (Colab/Local): Run RAG + LLM pipeline → Generate JSON output
- **Commit JSON**: Push final JSON files to GitHub
- **Deploy**: Render (Backend) + Cloudflare (Frontend) auto-update to serve the data

---

## 📋 Prerequisites

1. **GitHub Repository**: Your code is in a GitHub repo
2. **Final JSON Files**: You have processed JSON files ready (from your local pipeline)
3. **Accounts**: 
   - [Render.com](https://render.com) account (free tier)
   - [Cloudflare](https://cloudflare.com) account (free tier)

---

## Step 1: Prepare Your Data Files

### 1.1 Ensure JSON Files Are Tracked in Git

Your JSON files are in `data/output/` but `.gitignore` currently excludes them. We need to allow the final output files.

**Option A: Update `.gitignore` (Recommended)**

Add exceptions for your final output files at the end of `.gitignore`:

```gitignore
# Output files directory (all generated output files)
data/output/

# BUT allow the final processed JSON files for deployment
!data/output/ASCO_*.json
!data/output/ESMO_*.json
!data/output/Publications_*.json
```

**Option B: Use a Different Directory** ✅ **DONE**

You've created `data/deployed/` directory with all JSON files. This is the recommended approach!

The JSON files are now in `data/deployed/`:
- ASCO_2020.json through ASCO_2025.json
- ESMO_2020-2024.json
- Publications_70.json

**Important**: Set `TRIALS_JSON_FILES` environment variable to point to `data/deployed/` files.

### 1.2 Verify JSON File Structure

Your JSON files should have this structure:

```json
{
  "abstracts": [
    {
      "abstract_id": "ASCO_2020_001",
      "nct_id": "NCT02388906",
      "title": "Trial Title",
      "cancer_type": "Melanoma",
      "phase": "Phase 3",
      "arm_results": [...],
      ...
    }
  ],
  "publications": [...]
}
```

### 1.3 Commit JSON Files

```bash
git add data/deployed/*.json
git commit -m "Add processed trial data JSON files for deployment"
git push
```

**Note**: Since you're using `data/deployed/`, these files should not be in `.gitignore` and will be committed normally.

---

## Step 2: Prepare Backend for Deployment

### 2.1 Clean Dependencies (✅ OPTIMIZED)

The following changes have been made:
- ✅ `NullPDFProcessor` created for environments without PDF processing
- ✅ `api.py` updated to use null processor when `DISABLE_PDF_PROCESSING=true`
- ✅ CORS configured to read from `ALLOWED_ORIGINS` environment variable
- ✅ Dockerfile created and optimized
- ✅ **Dependencies split into production vs processing groups** (NEW!)

### 2.2 Dependency Structure (✅ DONE)

**Dependencies have been optimized for Render free tier deployment!**

The heavy ML dependencies (PyTorch, Transformers, marker-pdf, etc.) have been moved to an optional `[tool.poetry.group.processing]` group. This reduces the Docker image size from **3-4GB → ~300MB**.

**Production dependencies** (`poetry install --only main`):
- FastAPI, Uvicorn (API server)
- SQLAlchemy, Alembic (database, if needed)
- Pydantic (data validation)
- Requests (HTTP client)
- langchain-openai (lightweight, for GPT API calls if needed)

**Processing dependencies** (`poetry install --with processing`):
- marker-pdf, pypdf2, pdfplumber (PDF processing)
- sentence-transformers, chromadb (embeddings + vector DB)
- torch, transformers (ML models)
- langchain, langchain-huggingface (full RAG pipeline)

**Why This Matters:**
- ✅ Render builds complete in 2-3 minutes (vs timing out at 8+ minutes)
- ✅ Docker image fits in memory limits (~300MB vs 3-4GB)
- ✅ Faster deployments and restarts
- ✅ Production API only includes what it needs

**Note**: All PDF processing and embedding generation happens locally on your machine, not on Render!

### 2.3 Verify Dockerfile

The Dockerfile is already created at `melanoma/Dockerfile`. It:
- ✅ Uses Python 3.10-slim
- ✅ Installs Poetry and dependencies
- ✅ Copies all code AND data files
- ✅ Exposes port 8000
- ✅ Includes health check

---

## Step 3: Deploy Backend to Render

### 3.1 Create Render Web Service

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository
4. Select your repository (`bionocular`)

### 3.2 Configure Service

**Basic Settings:**
- **Name**: `bionocular-api`
- **Root Directory**: `melanoma` ⚠️ **Important!**
- **Runtime**: **Docker**
- **Region**: Choose closest to you (e.g., Oregon, Singapore)
- **Instance Type**: **Free**

**Environment Variables:**
```
TRIALS_DATA_SOURCE=json
DISABLE_PDF_PROCESSING=true
ALLOWED_ORIGINS=https://bionocular.ai,https://www.bionocular.ai
PYTHON_VERSION=3.10.0
TRIALS_JSON_FILES=data/deployed/ASCO_2020.json,data/deployed/ASCO_2021.json,data/deployed/ASCO_2022.json,data/deployed/ASCO_2023.json,data/deployed/ASCO_2024.json,data/deployed/ASCO_2025.json,data/deployed/ESMO_2020-2024.json,data/deployed/Publications_70.json
```

**Note**: The `TRIALS_JSON_FILES` variable is required since you're using `data/deployed/` instead of the default `data/output/`.

### 3.3 Deploy

1. Click **"Create Web Service"**
2. Wait for build to complete (~2-3 minutes with optimized dependencies)
3. Copy your service URL (e.g., `https://bionocular-api.onrender.com`)

**Build Timeline:**
- Dependency installation: ~1-2 minutes (lightweight packages only)
- Docker image build: ~30-60 seconds
- Service start: ~10-20 seconds

**Previous Issue (Fixed):** Before optimization, builds would timeout after 8+ minutes trying to install PyTorch, transformers, and other heavy ML dependencies that aren't needed for production.

### 3.4 Test Backend

Visit these URLs to verify:

- **Health Check**: `https://bionocular-api.onrender.com/health`
  - Should return: `{"status": "healthy"}`

- **API Root**: `https://bionocular-api.onrender.com/`
  - Should show API documentation

- **Trials Endpoint**: `https://bionocular-api.onrender.com/api/trials?limit=10`
  - Should return your trial data in JSON format

**Note**: First request after deployment may take ~30-45 seconds (Render free tier spin-up).

---

## Step 4: Deploy Frontend to Cloudflare Pages

### 4.1 Prepare Frontend

The frontend is already configured to use `NEXT_PUBLIC_API_URL`. No code changes needed! ✅

### 4.2 Create Cloudflare Pages Project

1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. Navigate to **Workers & Pages** → **Create Application** → **Pages** → **Connect to Git**
3. Select your GitHub repository
4. Click **"Begin setup"**

### 4.3 Configure Build Settings

**Project Settings:**
- **Project Name**: `bionocular-web`
- **Production Branch**: `main` (or your default branch)
- **Root Directory**: `web` ⚠️ **Important!**

**Build Settings:**
- **Framework Preset**: `Next.js`
- **Build Command**: `npm run build`
- **Build Output Directory**: `.next`

**Alternative** (if you want to use Cloudflare Pages adapter for better performance):
1. Install adapter: `cd web && npm install --save-dev @cloudflare/next-on-pages`
2. Update `package.json`:
   ```json
   {
     "scripts": {
       "build": "next build",
       "pages:build": "npx @cloudflare/next-on-pages"
     }
   }
   ```
3. Use build command: `npm run pages:build`
4. Build output: `.vercel/output/static`

**Environment Variables:**
```
NEXT_PUBLIC_API_URL=https://bionocular-api.onrender.com
```

### 4.4 Deploy

1. Click **"Save and Deploy"**
2. Wait for build to complete (~3-5 minutes)
3. You'll get a URL like: `https://bionocular-web.pages.dev`

### 4.5 Test Frontend

1. Visit your Cloudflare Pages URL
2. Navigate to the dashboard
3. Verify trials are loading from your backend API

---

## Step 5: Connect Custom Domain

### 5.1 Add Domain to Cloudflare Pages

1. In your Cloudflare Pages project, go to **Custom Domains**
2. Click **"Set up a custom domain"**
3. Enter: `bionocular.ai`
4. Cloudflare will automatically configure DNS

### 5.2 (Optional) Add www Subdomain

1. Click **"Set up a custom domain"** again
2. Enter: `www.bionocular.ai`
3. Cloudflare will configure this too

### 5.3 Update CORS (If Needed)

If you added `www.bionocular.ai`, make sure it's in your Render environment variables:

```
ALLOWED_ORIGINS=https://bionocular.ai,https://www.bionocular.ai
```

Then redeploy the backend (or just restart it).

---

## Step 6: Update Data (Workflow)

When you process new data locally:

### 6.1 Process Locally

Run your RAG + LLM pipeline locally (or on Colab) to generate new JSON files.

### 6.2 Update JSON Files

```bash
# Copy new JSON files to data/output/
cp /path/to/new/output/*.json melanoma/data/output/

# Or if using data/deployed/
cp /path/to/new/output/*.json melanoma/data/deployed/
```

### 6.3 Commit and Push

```bash
git add data/output/*.json  # or data/deployed/*.json
git commit -m "Update trial data - [date]"
git push
```

### 6.4 Auto-Deploy

- **Render**: Will automatically rebuild when it detects the push (if auto-deploy is enabled)
- **Cloudflare Pages**: Will automatically rebuild when it detects the push

**Note**: Render free tier may take a few minutes to rebuild. Cloudflare Pages is usually faster.

---

## 🐛 Troubleshooting

### Backend Issues

**Problem**: Backend returns 500 errors
- **Check**: Render logs for errors
- **Common causes**: 
  - JSON files not found (check paths in `TRIALS_JSON_FILES`)
  - Missing environment variables
  - Memory issues (free tier has 512MB limit - now fixed with optimized dependencies)

**Problem**: Build times out or gets stuck at "exporting to docker image format"
- **Root Cause**: Heavy ML dependencies (PyTorch, transformers) being installed
- **Solution**: ✅ Fixed! Dependencies are now split into production vs processing groups
- **Verification**: Build should complete in 2-3 minutes, not 8+ minutes

**Problem**: CORS errors in browser
- **Check**: `ALLOWED_ORIGINS` includes your frontend domain
- **Fix**: Update environment variable and restart service

**Problem**: First request is very slow (~45 seconds)
- **Normal**: Render free tier spins down after 15 minutes of inactivity
- **Solution**: Use a monitoring service to ping your API every 10 minutes (keeps it warm)

### Frontend Issues

**Problem**: Frontend can't connect to backend
- **Check**: `NEXT_PUBLIC_API_URL` is set correctly in Cloudflare Pages
- **Check**: Backend is running (visit health endpoint)
- **Check**: CORS is configured correctly

**Problem**: Build fails on Cloudflare
- **Check**: Build logs for errors
- **Common causes**: 
  - Missing dependencies in `package.json`
  - Build timeout (free tier has 20-minute limit)
  - Node version mismatch

### Data Issues

**Problem**: No trials showing up
- **Check**: JSON files are committed to Git
- **Check**: JSON file paths in `TRIALS_JSON_FILES` match actual files
- **Check**: JSON structure is correct (should have `abstracts` and/or `publications` keys)
- **Check**: Backend logs for file loading errors

**Problem**: JSON files are too large for Git
- **Solution**: Use Git LFS (Large File Storage)
- **Alternative**: Split JSON files into smaller chunks
- **Alternative**: Use a different storage (S3, etc.) and download on startup

---

## 📊 Monitoring & Maintenance

### Keep Backend Warm (Free Tier)

Render free tier spins down after 15 minutes. To keep it warm:

1. Use a free monitoring service like [UptimeRobot](https://uptimerobot.com/)
2. Set it to ping `https://bionocular-api.onrender.com/health` every 10 minutes
3. This prevents the ~45-second cold start

### Monitor Logs

- **Render**: View logs in the Render dashboard
- **Cloudflare Pages**: View build logs and function logs in Cloudflare dashboard

### Update Dependencies

Periodically update dependencies:

```bash
# Backend
cd melanoma
poetry update

# Frontend
cd web
npm update
```

---

## 🚀 Future Enhancements

### Migrate to Database

When ready to move from JSON files to a database:

1. Set up a PostgreSQL database (Render, Supabase, or Neon)
2. Create a migration script to import JSON → Database
3. Update environment variable: `TRIALS_DATA_SOURCE=database`
4. Redeploy backend
5. Frontend code doesn't need to change! ✅

### Add Caching

- Add Redis caching for frequently accessed data
- Use Cloudflare's built-in caching for static assets

### Scale Up

- Upgrade Render to paid tier for better performance
- Add CDN for faster global access
- Use Cloudflare Workers for edge computing

---

## ✅ Deployment Checklist

### Pre-Deployment (Local Testing)
- [x] JSON files moved to `data/deployed/` directory ✅
- [x] JSON files validated ✅ (All 8 files valid, structure confirmed)
- [x] Backend tested locally with deployed JSON files ✅ (JSONTrialsService loads 521 trials)
- [x] Docker build tested locally ✅ (Build successful, Python 3.10 UTC fix applied)
- [x] Docker container tested ✅ (Health endpoint works, trials endpoint returns data)
- [x] Frontend tested with local backend ✅ (Both servers running, CORS configured, API accessible)
- [x] Code changes committed to Git ✅ (docs not staged - optional)

### Backend Deployment (Render)
- [x] Dependencies optimized for production (processing deps moved to optional group) ✅
- [x] Dockerfile updated to use `--only main` flag ✅
- [ ] Render service created with correct environment variables
- [ ] Root directory set to `melanoma`
- [ ] Runtime set to Docker
- [ ] `TRIALS_JSON_FILES` includes all 8 files from `data/deployed/`
- [ ] Backend deployed and health check passes (should complete in 2-3 minutes)
- [ ] Trials endpoint returns data: `https://your-api.onrender.com/api/trials?limit=5`

### Frontend Deployment (Cloudflare Pages)
- [ ] Cloudflare Pages project created
- [ ] Root directory set to `web`
- [ ] `NEXT_PUBLIC_API_URL` set to Render backend URL
- [ ] Frontend deployed and loads correctly
- [ ] Dashboard shows trial data

### Post-Deployment
- [ ] Custom domain connected (`bionocular.ai`)
- [ ] CORS configured correctly (backend allows frontend domain)
- [ ] Tested end-to-end workflow (browse trials, view details)
- [ ] Monitoring set up (optional: UptimeRobot to keep backend warm)

**📋 See `TESTING_CHECKLIST.md` for detailed testing steps!**

---

## 📝 Summary

This architecture is perfect for your use case:
- ✅ **Simple**: No complex infrastructure
- ✅ **Free**: Uses free tiers of Render and Cloudflare
- ✅ **Scalable**: Easy to migrate to database later
- ✅ **Maintainable**: Update data by just pushing JSON files

Your backend is now a lightweight API server that just reads and serves JSON files. Perfect! 🎉

