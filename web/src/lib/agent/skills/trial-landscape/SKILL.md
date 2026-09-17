---
name: trial-landscape
description: How to query and read `trial_landscape` (the curated treatment landscape) and `clinical_trials` (the registry mirror) together - treatments, modalities, biomarkers, stage, line of therapy, and what "which trials exist" means. Load for landscape, pipeline, competitor, sponsor, modality or biomarker questions.
---

# Trial landscape

## Two tables, two kinds of truth

- `clinical_trials` mirrors the public registry: one row per trial, the
  sponsor's own title, status, phases, enrollment and `interventions` list.
  It is the only table that filters by `phase`, `status`, `sponsor` and
  `funding` directly, and the one that says whether a trial exists here at all.
- `trial_landscape` is curated by hand: one row per interventional trial with
  a single `treatment_name` (the regimen under study), `modality`,
  `biomarker`, `stage` and `line_of_therapy`. Observational studies are left
  out by design, and curation lags the registry sync, so a trial missing here
  may still exist in `clinical_trials`.

`treatment_name` and `interventions` are not the same claim. The curated name
is the regimen; the registry list is every arm, comparators, procedures and
placebo included. When only the registry list is available, say it is the
registry's list.

## Retrieval

- "Which trials" questions with phase, status, sponsor or funding constraints
  start on `clinical_trials`. `phase`, `status` and `funding` also reach
  `trial_landscape` through the registry join, so a phase-scoped landscape
  question is one call on `trial_landscape` with `phase` set.
- `drug` on `trial_landscape` is a substring on `treatment_name`; there is no
  drug filter on `clinical_trials` - use `interventions` in the rows instead.
- To enrich a registry result with curated fields, pass its `nct_id` values
  as `nctIds` to `trial_landscape` in one call. The coverage report's
  `missing` list names the trials with no curated row; report them as present
  but not yet curated, never as absent.
- `funding` splits trials by the registry's sponsor class (industry versus
  everything else). `sponsor` matches a name. "Industry-sponsored" is
  `funding`, not `sponsor: 'industry'`.

## Reading the rows

- `phases` is a list; a trial can be Phase 2/3. `overall_status` is the
  registry's recruitment state, and "active" usually means several statuses.
- `modality`, `biomarker`, `stage` and `line_of_therapy` are curated labels;
  group by them rather than by free text.
- `enrollment_count` is planned or actual enrollment as the registry states
  it, not the number of patients reported in any readout.

## Answer shape

Lead with the count and the grouping that answers the question (by treatment,
modality, sponsor, phase), then what stands out and what is uncovered. Every
trial the query returned is accounted for - grouped, or named as set aside and
why. Cite `nct_id`. The interface draws the rows; do not reproduce them.
