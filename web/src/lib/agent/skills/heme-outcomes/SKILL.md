---
name: heme-outcomes
description: How to read `arm_outcomes` rows in a hematology session - response criteria, denominators, pooled "All arms" rows, contexts, NR and qualifiers, registry origin. Load before answering any question about response, ORR or CR, survival, PFS or OS, adverse events, or comparing arms.
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
- A read over budget comes back partial with `coverage`. Say what was left out.

## Reading response rates

- Name the response criteria before comparing response rates. Read them from
  `Response criteria` on the arm's abstract.
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

## Policy rules

- Duration of CR counts as duration of response only when every responder is
  a CR. Otherwise do not call it DOR.
- Target dose and step-up dose are different. Do not mix them in one comparison.
- `±` and `or` in a regimen mark optional drugs. Do not read them as part of
  every patient's treatment.
- Arms from different trials are not randomised against each other - say so.
