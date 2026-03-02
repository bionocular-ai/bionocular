# Clinical Trial API Data in Production

Production does **not** push a pre-built local DB. The SQLite database (`trials.db`) is created from JSON files when the image is built. So `clinical_trials_cache` and `api_discovery` start empty unless you use one of the options below.

## Options to store API data in production

### Option A: Seed JSON baked into the image (recommended)

**How it works:** Export your local API cache to a JSON file, commit it, and let the existing build step load it into `trials.db` during Docker build. No API calls at deploy or startup; data is ready as soon as the app starts.

**Steps:**

1. **Export once (or periodically) from your local DB:**
   ```bash
   cd melanoma
   poetry run python scripts/export_clinical_trial_api_to_json.py
   ```
   This writes `data/deployed/clinical_trials_api_seed.json`.

2. **Commit the seed file** (and redeploy). The Dockerfile already runs `build_db.py`, which now loads `clinical_trials_api_seed.json` into `trials.db` when that file exists.

3. **To refresh data:** Run the export again (e.g. after re-syncing locally or updating `clinical_trial_api.db`), commit the updated JSON, and redeploy.

**Pros:** Predictable, fast startup, no runtime dependency on ClinicalTrials.gov.  
**Cons:** Data is as of last export; refresh by re-exporting and redeploying (or use a cron to re-export in CI and trigger deploy).

---

### Option B: Sync at runtime (startup or cron)

**How it works:** After deploy, run `sync_dashboard_data.py` so the production DB (same `trials.db`) is filled by calling the ClinicalTrials.gov API.

- **At startup:** Use a wrapper command that runs the sync then starts the app, e.g.  
  `sync_dashboard_data.py && uvicorn ...`  
  First requests may see empty or partial data until the sync finishes.
- **Cron:** Run `sync_dashboard_data.py` on a schedule (e.g. Render Cron Job). Data appears after the first successful run; no API call during build or startup.

**Pros:** No seed file to maintain; data can be fresher if cron runs often.  
**Cons:** Needs network at runtime; first boot (or first run before cron) may have no trial data.

---

## Recommendation

- **Use Option A (seed JSON)** when you want production to have trial data immediately on every deploy, with no API calls at deploy or startup, and you’re fine updating the seed periodically (e.g. weekly export + deploy).
- **Use Option B (runtime sync)** when you prefer not to commit a (possibly large) JSON file and are okay with running a sync after deploy or on a schedule.

You can also combine: ship a seed so the app has data from day one, and run `sync_dashboard_data.py` on a cron to refresh it over time (if your deployment preserves the DB file; on ephemeral disks, the seed is still the only way to have data right after each deploy).

## Summary

| Question | Answer |
|----------|--------|
| Where is API data stored in production? | In the same SQLite DB: `trials.db` (`CLINICAL_TRIAL_DB_PATH`). The full API response is stored as JSON in `clinical_trials_cache.api_response_json`. |
| How do we get that data there if we don’t push a local DB? | **A)** Commit `data/deployed/clinical_trials_api_seed.json` and let `build_db.py` load it during Docker build. **B)** Run `sync_dashboard_data.py` at startup or via cron after deploy. |
| Do we need to “store data in JSON” for production? | Only if you choose Option A: the **seed** is a JSON file that gets loaded into the DB at build time. The app still reads from the DB; the JSON is just the source for that load step. |
