---
name: heme-outcomes
description: How to read `arm_outcomes` rows in a hematology session - response criteria, denominators, pooled "All arms" rows, contexts, NR and qualifiers, registry origin. Load before answering any question about response, ORR or CR, survival, PFS or OS, adverse events, comparing arms, or counting or listing trials.
---

# Heme outcomes

## What a row is

`arm_outcomes` has one row per arm of an abstract, plus one "All arms (pooled
or trial-level)" row per abstract. `trial` maps a label to `{value, origin?,
caveat?, detail?, derived?}`. An arm row carries only Response criteria,
Assessment by, Analysis type and Trial name; the All arms row carries every
other trial-level label. `values` is keyed by family, each entry
`{field, value, n?, context?, detail?, derived?, origin?, caveat?}`. Look a
field up in `outcome_fields` (label, family, value_type, definition) before
interpreting it; do not guess from the label.

## Retrieval

- Pass `families` to fit a whole-cancer read: it narrows the values returned
  and the rows to those that report a selected family. Families are
  `response_rates`, `survival_pfs_os`, `survival_other`, `duration_transplant`,
  `safety_overall`, `dose_events_special`, `population`, `regimen_drug`,
  `ae_reporting` and `registry`. Pick only what the question needs.
- There is no drug-class filter. For a class (BCMA bispecifics, menin
  inhibitors), query `arm_outcomes` once per drug you know in it, by `drug`;
  no other table maps drugs to classes.
- A read over budget comes back partial with `coverage`. Say what was left out.

## Trial scope

- In a hematology session `clinical_trials` holds only the trials an abstract
  in `arm_outcomes` cites, not the whole registry. Every count or list of
  trials covers those trials only.
- Whenever the answer counts or lists trials, say so, naming the meeting from
  the abstracts' `source_id` (ASH_2025_256 is ASH 2025): "4 active Phase 3
  trials with ASH 2025 data". Never write "all trials" or "all 4 Phase 3
  trials".

## Reading response rates

- A response rate is any value in the `response_rates` family,
  MRD negativity included.
- Name the response criteria in the answer for every response rate it gives,
  even a single one. Read them from `Response criteria` on the arm's abstract.
- When it is empty, say "criteria not stated" and compare anyway, with that
  caveat. Never assume the disease's standard criteria.
- When its `origin` is registry, say "criteria per the trial registry".
- Rates under different criteria, or different assessors (`Assessment by`),
  are set side by side, not ranked as equals. The answer must say the criteria
  or assessors differ; never compare them silently.

## Denominators

- Every value's `n` is its denominator. The table shows each value with its
  `n` as "63 (n=165)"; when a bullet cites a rate, give its `n` the same way.
  Do not recompute it.
- ITT, infused and evaluable populations differ. A rate over infused or
  evaluable patients is higher than the same responders over ITT. Say which
  denominator each rate uses; do not compare across them without saying so.

## All arms rows and contexts

- An "All arms" row is pooled or trial-level, never an arm. Do not count it as
  an arm, put it beside arms as a competitor, or attribute its values to one arm.
- A `context` (a subgroup, a dose level, a time point) describes that subset
  only. Never report a contextual value as the ITT result.

## Passing values on

- `NR` is not reached - a finding, not missing data. A `<` or `>` qualifier is
  a bound, not a point value. Quote both as stored.
- Registry-origin values are marked "(registry)". Relay every `caveat`.
- Quote, never derive: do not recompute, convert or round.
- Name arms, trials and field labels. Cite an abstract by `source_id`
  (ASH_2025_256) and a trial by `nct_id`; never show a row `id`
  (abstract_ASH_2025_256_arm_1) or a family key (response_rates).

## Policy rules

- Duration of CR counts as duration of response only when every responder is
  a CR. Otherwise do not call it DOR.
- Target dose and step-up dose are different. Do not mix them in one comparison.
- `±` and `or` in a regimen mark optional drugs. Do not read them as part of
  every patient's treatment.
- Arms from different trials are not randomised against each other - say so.
