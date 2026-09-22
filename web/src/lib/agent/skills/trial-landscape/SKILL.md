---
name: trial-landscape
description: How to query and read `trial_landscape` (the curated treatment landscape) and `clinical_trials` (the registry mirror) together - treatments, modalities, biomarkers, stage, line of therapy, and what "which trials exist" means. Load for landscape, pipeline, competitor, sponsor, modality or biomarker questions.
---

# Trial landscape

## Two tables, two kinds of truth

- `clinical_trials` is the registry: it says which trials exist. One row per
  trial, the sponsor's own title, status, phases, enrollment, dates, sponsor
  class and `interventions` list. It is the only table that filters by
  `phase`, `status`, `sponsor` and `funding` directly, and the only one whose
  count is the inventory.
- `trial_landscape` is the curated reading of each protocol: what a trial
  means clinically. One row per interventional trial with a single
  `treatment_name` (the regimen under study), `modality`, `biomarker`, `stage`
  and `line_of_therapy`. Observational studies are left out by design, and
  curation lags the registry sync, so a trial missing here still exists in
  `clinical_trials`.

`treatment_name` and `interventions` are not the same claim. The curated name
is the regimen; the registry list is every arm, comparators, procedures and
placebo included. When only the registry list is available, say it is the
registry's list.

## Retrieval

- One table answers most questions. Go to `clinical_trials` for phase,
  status, sponsor or funding; to `trial_landscape` for a drug, biomarker,
  modality or an unconstrained browse of the curated landscape.
- Both tables are needed only when the question asks for a *landscape* under
  a registry constraint - "the Phase 3 landscape", "what treatments are in
  active trials" - where the answer needs the full trial set and the curated
  regimen for each. Then: `clinical_trials` first for the set, then its
  `nct_id` values as `nctIds` to `trial_landscape` in one call. Registry
  first, two calls, no more.
- In that case do not instead put `phase` or `status` on `trial_landscape`.
  The registry join makes that query run, but it can only see trials that
  already have a curated row: `coverage.complete` is then true of the curated
  table and false of the question, and every trial not yet curated is
  silently gone.
- When both tables were queried, the inventory count is the registry's and
  the curated count is what `trial_landscape` returned. State both ("N
  trials, M curated"); its coverage report's `missing` list names the trials
  with no curated row, which are present but not yet curated, never absent.
- `drug` on `trial_landscape` is a substring on `treatment_name`; there is no
  drug filter on `clinical_trials` - use `interventions` in the rows instead.
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
- `is_basket` marks a pan-tumour platform (a DETERMINE arm, a multi-cancer
  dosing study) that lists this cancer type among many. Such a row is not a
  therapy for this indication: set it aside from the landscape and say how
  many were set aside, by NCT.
- `ACTIVE_NOT_RECRUITING` covers two different states: still treating, and
  finished enrolling with only follow-up left. When `primary_completion_date`
  is in the past, say the trial is in follow-up rather than presenting it as
  an open option.
- `lead_sponsor_class` is the registry's sponsor class. "Industry" is
  `INDUSTRY`; everything else (NIH, NETWORK, OTHER, OTHER_GOV, FED) is
  non-industry. It says who leads the trial, not who funds it.

## Answer shape

Lead with the registry count and the curated count, then the grouping that
answers the question. For a landscape, group by clinical setting first -
peri-operative (`line_of_therapy` has Adjuvant or Neoadjuvant), advanced or
metastatic (1L, 2L, 3L, R/R), procedural or supportive (radiotherapy,
surgery, diagnostics) - and only then by modality or biomarker within a
setting. Then what stands out and what is uncovered. Every
trial the query returned is accounted for - grouped, or named as set aside and
why. Cite `nct_id`. The interface draws the rows; do not reproduce them.
