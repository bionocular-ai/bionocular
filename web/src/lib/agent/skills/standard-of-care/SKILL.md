---
name: standard-of-care
description: How to read `approved_therapies` (NCCN-listed therapies and their US regulatory status for this cancer type) - what Approved, On-label and Off label mean, and how to use it as the standard-of-care baseline. Load for approval, standard of care, label, unmet need or comparator questions.
---

# Standard of care

## What the table is

`approved_therapies` holds one NCCN guideline version (its `source`), US
status only, one row per regimen that applies to this cancer type. A regimen
the guideline does not list for this cancer type has no row. Read it whole:
one call, no filters, no limit. The interface draws the rows.

Rows are pinned to the dashboard's cancer type, like every table. Brain/CNS
metastases have their own dashboard and their own rows. Asked about them on
another dashboard, say the Brain/CNS dashboard covers them rather than
answering from this cancer type's rows.

## Statuses

`us_status` is the spreadsheet's wording, stored as-is. Only `Approved` is an
approval for this cancer type; every On-label wording is not, so name the
wording rather than calling it approved. Approval dates or regions inside
`dose` describe a formulation, never this cancer type.

- `Approved`: an FDA approval for this cancer type and setting.
- `On-label (generic)`: the label says "unresectable or metastatic melanoma"
  and does not exclude this subtype. That is permission by silence, not
  evidence for this subtype. Never call it approved.
- `On-label (cutaneous)`: the label says cutaneous melanoma, and acral
  melanoma counts as cutaneous.
- `On-label if BRAF V600+`: generic BRAF V600 melanoma wording. BRAF V600 is
  far less common in acral and mucosal melanoma than in cutaneous, so say the
  option reaches fewer patients there.
- `Off label`: the label wording excludes this cancer type.
- Any other wording is quoted exactly as the row gives it.

## NCCN tier and category

- `nccn_tier`: Preferred, Other Recommended, or Useful in certain
  circumstances (chosen by tumour biology, prior therapy or clinical
  features). `May be substituted` marks a subcutaneous formulation that can
  replace the IV form in any regimen containing it: not a separate regimen,
  so leave it out of regimen counts and name it on its own.
- `nccn_category`: Cat 1 is high-level evidence with uniform consensus;
  Cat 2A is lower-level evidence with uniform consensus; Cat 2B is
  lower-level evidence where the panel did not agree unanimously.

## Answer shape

Lead with how many regimens apply and how many are Approved, On-label and
Off label. Group by setting: peri-operative (Neoadjuvant, Adjuvant) first,
then advanced lines. Name what is missing, such as no approved peri-operative
option. Cite the `source` value. For unmet-need or comparator questions
("which trials test something beyond the standard of care"), also load
`trial-landscape` and read the two tables together.
