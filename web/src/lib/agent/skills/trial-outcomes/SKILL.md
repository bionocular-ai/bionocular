---
name: trial-outcomes
description: How to query and read `trial_outcomes` rows - efficacy and safety endpoints per treatment arm, censoring markers, abstracts versus publications. Load before answering any question about ORR, PFS, OS, DoR, response, survival, adverse events, toxicity, or comparing arms.
---

# Trial outcomes

## What a row is

One row is one treatment arm as reported by one source: a conference abstract
(`source_type`, `abstract_id`) or a publication (`publication_id`). The same
trial can appear several times - once per arm, and again per source when both
an abstract and a paper reported it. `arm_name`, `generic_name`,
`line_of_treatment`, `num_patients` and `source_name` say which arm and which
readout you are looking at; carry them into any claim you make about that arm. `lead_sponsor_class`,
`biomarker` and `line_of_therapy` are the trial's, joined in; `line_of_treatment`
is the arm's own and wins when both are present. The interface draws one row
per treatment - its newest readout, with earlier readouts folded beneath it -
but you read every row: cite the readout each number comes from.

## Retrieval

- Filter this table directly. `phase`, `status` and `funding` reach it through
  the registry join, so a phase-scoped outcomes question is one call with
  `table: 'trial_outcomes'` and `phase` set - not a sweep of `clinical_trials`
  followed by an `nctIds` handoff, which the key cap cannot hold.
- "Active", "ongoing" and "recruiting" are `status` on this same call - active
  is RECRUITING, ACTIVE_NOT_RECRUITING, NOT_YET_RECRUITING and
  ENROLLING_BY_INVITATION. An outcomes question never needs `clinical_trials`
  or `trial_landscape`: every row already carries its trial's sponsor class,
  biomarker and line of therapy. Querying them spends the turn's budget and
  truncates the outcomes you came for.
- "Metastatic / cutaneous melanoma" is the cutaneous scope, not a stage
  filter; the interface sections treatments by line of therapy.
- A question setting efficacy against safety ("median PFS vs grade 3+ AEs")
  is answered only by treatments that report the asked efficacy endpoint.
  Adjuvant and neoadjuvant trials report RFS or EFS, not PFS, so they drop
  out; the interface leaves out every treatment with safety but none of the
  asked efficacy, and counts them in the note above the table. Leave them
  out of the prose too.
- A re-query keeps the `endpoints`, `detail` and `columns` of the call it refines.
- When the question names endpoints, pass them as `columns`, in the order it
  names them (up to five): "ORR and grade 3+ treatment-related AEs" is
  `['orr', 'grade_3_plus_trae_pct']`. The interface draws exactly those.
  Efficacy columns use the short clinical names: `orr`, `dcr`, `cr`, `pcr`,
  `median_pfs`, `median_os`, `median_dor`, `hr_pfs`, `pfs_rate_12m`.
  Adverse-event columns carry their class in the name: `ae` (any cause),
  `teae` (treatment-emergent) or `trae` (treatment-related), as in
  `grade_3_plus_teae_pct`, `serious_trae_pct` and `teae_discontinuation_pct`.
  Discontinuation for any cause is `ae_leading_to_discontinuation_pct`.
- `drug` is a substring on `generic_name`; `sponsor` on `sponsors`.
- Ask for `detail: 'detailed'` when the question names endpoints beyond the
  browse set (the concise set carries PFS, OS, ORR, DCR, DoR, grade 3+ TRAE
  and serious AE). Set `endpoints` to `efficacy` or `safety` when the question
  is about one family, so the result is not padded with the other.
- Rows with no `nct_id` are identified by `abstract_id` only. An `nctIds`
  filter, and every registry-joined filter, cannot see them; the result's
  `caveat` or `viaJoin` field says how many were out of reach. Relay it.

## Reading the numbers

- Quote, never derive. Medians, hazard ratios, rates and p-values are reported
  as the row carries them; do not recompute, convert units, or round.
- `is_nr` and `is_lt` hold column names, not values. A column listed in
  `is_nr` was measured and *not reached* - that is a finding (usually a
  favourable one), not missing data; its value is null on purpose. A column
  in `is_lt` is a censored rate ("less than"), stored as the bound.
- Pair a hazard ratio with its `ci_hr_*` and `p_value_*` from the same row.
  Landmark rates (`pfs_rate_12m`, `os_rate_24m`, ...) are the rate at that
  month; report the month.
- `num_patients` is the arm's size and the strength of the evidence. Say it
  when a claim rests on one small arm.
- `expert_review` is a pharmacology expert's check of the row against its
  source: `good` (it matches) or `issues` (errors found). Absent means never
  reviewed, not wrong. When the answer rests on specific rows, say which were
  expert-reviewed; quote an `issues` row only with that warning.
- Two arms of the same trial can be compared. Arms from different trials can be
  set side by side but not compared as if randomised - say so.
- `line_of_treatment` changes what a number means; first-line and later-line
  arms are not the same population.

## Adverse-event classes

- AE, TEAE and TRAE are separate columns, each holding what the source
  labelled that way. A value belongs to its column's class only: never call an
  AE or TRAE value a TEAE, or the reverse.
- When the class the question names is empty on most arms, say so first, in
  words ("no arm reports grade 3+ TEAE", not the column name). Then answer from the other classes and
  name the class on every value. AE counts any cause, as TEAE does; TRAE counts
  only events attributed to the drug, so it runs lower and is a narrower
  stand-in. The interface shows, in place of the asked class when another class
  is reported by more treatments, the class most treatments report, names it
  in the column header, and says so in a note above the table.
- Discontinuation carries the same classes. "Discontinuation due to AEs" is
  `ae_leading_to_discontinuation_pct` - any cause, the class the question
  asks for - not TEAE. Name the class of each discontinuation rate, and do
  not merge a TRAE rate with an AE rate.

## Answer shape

Follow the answer shape in your instructions. The count sentence quotes
`coverage.answered` exactly, distinct treatments first: "`reporting.treatments`
treatments (`reporting.arms` arms) from `reporting.trials` trials report at
least one asked endpoint; `none.treatments` more (`none.arms` arms, in
`none.trials` trials) report none" - grouped by why (adjuvant, still
recruiting), with no number per reason; do not list them. Three cohorts of one
combination in one trial are one treatment and three arms; the same
combination in two trials is two treatments. A trial can be on both sides,
so never add or subtract these; never count rows yourself, since your tally
will not match the table beside the answer. An arm that reports some of the asked endpoints
and not others is in the table, not a trial without a readout. Bullets are for
what the rows cannot show: a missed significance, a press-release-only source,
an `issues` expert review, arms from different trials not being randomised.
