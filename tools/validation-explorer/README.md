# Validation Explorer

A standalone, read-only tool for exploring the output of the melanoma LLM extraction
validation pipeline. It reads the `validation.json` (and `results.json`) files produced by
a validation run and gives you a dashboard, a sortable/filterable trials table with
per-field drill-down, and a virtualized field-evaluations table - so you can review
LLM-as-a-Judge decisions (kept / fixed / dropped / HITL) without digging through raw JSON.

This tool lives entirely under `tools/validation-explorer/` and is independent of the
`web/` and `melanoma/` packages: no shared build config, no Supabase, no backend calls.

## Setup

```bash
cd tools/validation-explorer
npm install
```

## Load data

```bash
npm run load-runs
```

This script (`scripts/load-runs.mjs`) scans `../../melanoma/data/output/*/validation*/` for
`validation.json` files (one per validation run, alongside the cohort's `results.json`),
copies them into `public/runs/<run-id>/`, and writes a `public/runs.json` manifest that the
app reads to populate the run switcher. Re-run it any time a new validation run is produced
locally - the app only ever reads from `public/`, it never reaches into `melanoma/` at
runtime.

If no runs are found (or `public/runs.json` is missing), the app shows an empty state with
this command as the next step.

## Run

```bash
npm run dev
```

Opens the app at the URL Vite prints (default `http://localhost:5173`). Pick a run from the
switcher in the header, then use the filter bar and tabs (Dashboard / Trials / Field evals)
to explore it.

## Test

```bash
npm test
```

Runs the Vitest suite (unit tests for the normalizer, filters, aggregations, and component
tests for the tables/dashboard).

## Read-only, local-only

This tool only reads static JSON files copied under `public/` by `load-runs`. It makes no
network requests, has no backend, and never talks to Supabase or any other production
service. It is meant to be run locally by whoever is reviewing a validation run.

## Cost/token caveat

The "cost (final proc)" and "tokens (final proc)" tiles on the dashboard come straight from
the validation run's `metadata`. Validation (and the extraction it validates) runs
sequentially and can be resumed across multiple processes if interrupted - when that
happens, the metadata's cost/token totals reflect only the **final** resumed process, not
the full run. Treat these numbers as a lower bound, not the true total cost/tokens for the
run.
