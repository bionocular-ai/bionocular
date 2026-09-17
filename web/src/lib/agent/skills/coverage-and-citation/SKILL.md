---
name: coverage-and-citation
description: How to read a tool result's coverage report (matched, returned, complete, truncated, missing, viaJoin, caveat, budget), how to phrase absence and partial results, and how to cite. Load when a result is incomplete, a lookup misses, a query is refused, or the user asks how complete an answer is.
---

# Coverage and citation

## The coverage report

Every `query_proprietary_data` result carries `coverage`:

- `matched` is how many rows exist for the filters; `returned` is how many
  you received; `complete` is whether they are the same. When `complete` is
  false, `truncatedBy` says why:
  - `limit`: you asked for fewer than matched. Re-run with a higher `limit`
    if the user wants all of them; until then call it a sample.
  - `size`: one result cannot carry them all. Narrow the filters.
  - `turn_budget`: this turn has spent its result budget. Answer from what
    you have and say the result is partial. Do not retry the same query.
- `requested` and `missing` appear when you passed `nctIds`: `missing` names
  the trials that have no row in that table. They exist; this table does not
  cover them. Say "N of M are covered here" - never drop them, never fill the
  gap from memory.
- `viaJoin` appears when `phase`, `status` or `funding` resolved through the
  registry join. Rows with no `nct_id` could not be filtered and are not in
  the result; that is a linkage gap, not evidence they fail the filter.
- `caveat` is the table's standing limitation. Relay it when it bears on the
  answer.

`lookup_trial` reports `presentIn` and `absentFrom` for the five tables, and
`truncated` when a table's rows were cut to fit. A trial absent from
`trial_outcomes` under an NCT lookup has not been shown to lack outcome data.

## Refusals and misses

- `unfiltered_sweep`: add a filter from `supportedFilters`, or find the
  trials in another table first and pass `nctIds`.
- `unsupported_filter`: this table has no such filter; the result names the
  ones it has.
- `no_rows`: an answer. Say what was searched and that nothing matched.
- `turn_budget_exhausted`: the counts are still facts; the rows are not
  available this turn.
- `lookup_trial` `not_in_bionocular`: the database has no record. `other_cancer_type`:
  it exists but is tagged to a different cancer type than the one in view.
  Say which; describe neither from memory.

## Citation

- Cite the identifier the row carried: `nct_id` for trials, `abstract_id` or
  `publication_id` for outcome rows, the article `url` for news.
- Never cite an identifier that no result in this conversation contained,
  and never construct one.
- Numbers, names and statuses come from rows, not from what is usually true
  of a drug or a trial.
- `store_finding` refuses citations that no result carried; pass only
  identifiers from results.

## Phrasing partial evidence

State the count you have against the count that exists, name what is
unreachable and why, then answer on what is in hand. "48 of 53 have a curated
modality; five are not yet covered" is the shape. "No rows matched" is a
finding, not a failure.
