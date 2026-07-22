"""Prompt builder for the LLM-as-a-Judge validation pass.

Reuses the controlled vocabularies that drive extraction (single source of truth
in ``trials_extraction_prompts``) so the judge scores against the identical
allowed values. The judge returns a ``TrialValidationVerdict`` via structured
output; this module supplies the persona, rules, and per-trial context.
"""

from __future__ import annotations

from .trials_extraction_prompts import (
    BIOMARKER_VALUES,
    LINE_OF_THERAPY_VALUES,
    MODALITY_VALUES,
    PREVIOUS_TREATMENT_VALUES,
    STAGE_VALUES,
)

_SYSTEM_PROMPT = (
    "You are a strict, adversarial clinical-data auditor specialising in melanoma "
    "and skin-cancer trials. You verify that structured parameters extracted from a "
    "trial were justified by the source text. Assume each extracted value is wrong "
    "until the source proves it right. Be precise and skeptical; do not be "
    "agreeable. Return ONLY the requested structured verdict."
)


def _render(values: list[str]) -> str:
    return "\n".join(f"  - {v}" for v in values)


_ENUM_VOCAB = (
    f"modality:\n{_render(MODALITY_VALUES)}\n\n"
    f"biomarker:\n{_render(BIOMARKER_VALUES)}\n\n"
    f"stage:\n{_render(STAGE_VALUES)}\n\n"
    f"line_of_therapy:\n{_render(LINE_OF_THERAPY_VALUES)}\n\n"
    f"previous_treatment_criteria:\n{_render(PREVIOUS_TREATMENT_VALUES)}"
)

_USER_TEMPLATE = """\
## Task
Audit the extracted parameters below against the trial source text. Produce a
per-field verdict and an overall judgement.

## Where each field comes from
- treatment_name, modality: the officialTitle, briefSummary, and interventions
  sections. treatment_name is the investigational agent(s), not the comparator,
  placebo, or supportive/diagnostic entries.
- biomarker, stage, line_of_therapy, previous_treatment_criteria: the eligibility
  criteria.

## Values are inferred, not copied
Extracted values are mapped from source language, they do not appear verbatim.
Judge whether the source *justifies* the mapped value. Examples:
  "metastatic" / "advanced" / "unresectable stage IV"      -> stage "Stage IV"
  "resected" / "unresectable" stage III                    -> stage "Stage III"
  "treatment-naive" / "no prior systemic therapy"          -> line_of_therapy "1L"
  relapsed / refractory language                           -> line_of_therapy "R/R"
  a drug name                                              -> its modality class

## Controlled vocabularies (enum fields may only use these values)
{enum_vocab}

## Rules for your verdict
- For every field, set status PASS, FAIL, or UNCERTAIN.
- PASS requires `source_evidence_quote`: a phrase copied VERBATIM from the source
  text (it must be a literal substring), plus a `mapping_justification` explaining
  why that phrase maps to the extracted value. No supporting phrase => never PASS.
- FAIL when the value is unsupported, the mapping is wrong, or the value is
  hallucinated. When the source clearly supports a different, in-vocabulary value,
  put it in `corrected_value` (join multiple with "; "); otherwise leave it null.
- UNCERTAIN when the source is ambiguous or conflicting - not as a hedge.
- A legitimately empty field (source carries no signal for it) is PASS, not a FAIL
  and not a missed value.
- `corrected_value` and `missed_values.suggested_value` for enum fields MUST be
  from the vocabularies above. Never invent new values.
- Report values the source clearly supports but the extractor omitted in
  `missed_values`, each with a verbatim supporting quote.
- Set `is_valid` false if any field is FAIL. Set `validation_score` to your overall
  confidence (0.0-1.0) that the extracted record is correct and complete.

## Source text
{source_text}

## Extracted parameters (candidate under audit)
{candidate_json}
"""


def build_validation_prompt(source_text: str, candidate_json: str) -> str:
    """Assemble the full judge prompt for one trial."""
    user = _USER_TEMPLATE.format(
        enum_vocab=_ENUM_VOCAB,
        source_text=source_text.strip(),
        candidate_json=candidate_json.strip(),
    )
    return f"{_SYSTEM_PROMPT}\n\n{user}"
