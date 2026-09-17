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
readout you are looking at; always carry them into the answer.

## Retrieval

- Filter this table directly. `phase`, `status` and `funding` reach it through
  the registry join, so a phase-scoped outcomes question is one call with
  `table: 'trial_outcomes'` and `phase` set - not a sweep of `clinical_trials`
  followed by an `nctIds` handoff, which the key cap cannot hold.
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
- `num_patients` is the arm's size and the strength of the evidence. Say it.
- Two arms of the same trial can be compared. Arms from different trials can be
  set side by side but not compared as if randomised - say so.
- `line_of_treatment` changes what a number means; first-line and later-line
  arms are not the same population.

## Answer shape

Open with the shape: how many arms, from how many trials, grouped by the
thing the question asked about (treatment, line, phase). Then what is notable,
what is absent, and which rows are exceptions and why. Cite `nct_id` where a
row has one, otherwise `abstract_id` or `publication_id`. The interface draws
every row of the result as a table beside your answer; do not reproduce rows.
