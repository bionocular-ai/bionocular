"""Prompt builder for the abstract / publication validation judge.

One judge call per (document, attribute group). Each call sees the full source
text and every treatment arm side by side - arm attribution is only checkable when
the sibling arms are visible.

The prompt embeds the extractor's own instructions verbatim
(``SHARED_EXTRACTION_RULES`` plus the group's ``FAMILY_PROMPTS`` bodies) rather
than restating endpoint definitions. The judge's question is "did the extractor
follow these rules?", so handing it the same rules keeps a single source of truth:
when an extraction rule changes, the judge changes with it.
"""

from __future__ import annotations

from .constants import ResultsValidation
from .extraction_models import (
    ABSTRACT_ATTRIBUTES,
    FAMILY_TO_ATTRIBUTES,
    PUBLICATION_ATTRIBUTES,
    AttributeFamily,
    AttributeType,
)
from .models import DocumentType
from .prompt_templates import FAMILY_PROMPTS, SHARED_EXTRACTION_RULES
from .results_validation_models import AttributeGroup

__all__ = [
    "FILE_PATH_SOURCED_ATTRIBUTES",
    "GROUP_TO_ATTRIBUTES",
    "GROUP_TO_FAMILIES",
    "TRIALS_PIPELINE_ATTRIBUTES",
    "UNAUDITED_ATTRIBUTES",
    "allowed_fields_for",
    "build_group_prompt",
    "group_for_field",
]

# Read from the filename by the extraction pipelines (``source: "file_path"``),
# not from the document body. An LLM asked to find them in the text would
# manufacture failures, so they are audited by no group.
FILE_PATH_SOURCED_ATTRIBUTES: frozenset[AttributeType] = frozenset(
    {
        AttributeType.CONFERENCE,
        AttributeType.PUBLISHED_YEAR,
        AttributeType.PDF_NUMBER,
    }
)

# Trial-level drug classifications, derived from pharmacological knowledge rather
# than read from the document. They are owned by the trials validation pipeline
# (``trials_validation_service``), which grades them against CT.gov - auditing
# them again here would duplicate that judgement against a source that never
# states them.
TRIALS_PIPELINE_ATTRIBUTES: frozenset[AttributeType] = frozenset(
    {
        AttributeType.MODALITY,
        AttributeType.TARGET,
    }
)

#: Everything this pipeline deliberately does not audit.
UNAUDITED_ATTRIBUTES: frozenset[AttributeType] = (
    FILE_PATH_SOURCED_ATTRIBUTES | TRIALS_PIPELINE_ATTRIBUTES
)

GROUP_TO_FAMILIES: dict[AttributeGroup, tuple[AttributeFamily, ...]] = {
    AttributeGroup.IDENTIFICATION: (AttributeFamily.IDENTIFICATION,),
    AttributeGroup.EFFICACY: (
        AttributeFamily.RESPONSE_RATES,
        AttributeFamily.PFS_FAMILY,
        AttributeFamily.OS_FAMILY,
        AttributeFamily.EFS_RFS_MFS,
        AttributeFamily.TIME_TO_METRICS,
    ),
    AttributeGroup.SAFETY: (
        AttributeFamily.AE_GENERAL,
        AttributeFamily.AE_GRADE3_SPECIFIC,
        AttributeFamily.TEAE_GENERAL,
        AttributeFamily.TEAE_GRADE3_SPECIFIC,
        AttributeFamily.TRAE_GENERAL,
        AttributeFamily.TRAE_GRADE3_SPECIFIC,
    ),
}

# Attributes that belong to no AttributeFamily but are still extracted from the
# document body, so they must be audited. ``number_of_patients`` comes from the
# arm separator; the publication metadata comes from the citation block.
_UNFAMILIED_IDENTIFICATION: tuple[AttributeType, ...] = (
    AttributeType.NUMBER_OF_PATIENTS,
    AttributeType.PUBLICATION_NAME,
    AttributeType.PUBLICATION_YEAR,
)


def _build_group_attributes() -> dict[AttributeGroup, tuple[AttributeType, ...]]:
    """Expand the family mapping into a flat, ordered attribute list per group."""
    mapping: dict[AttributeGroup, tuple[AttributeType, ...]] = {}
    for group, families in GROUP_TO_FAMILIES.items():
        members: list[AttributeType] = []
        if group is AttributeGroup.IDENTIFICATION:
            members.extend(_UNFAMILIED_IDENTIFICATION)
        for family in families:
            members.extend(FAMILY_TO_ATTRIBUTES[family])
        # De-duplicate while preserving order; families do not overlap today, but
        # the mapping is data and could grow one.
        mapping[group] = tuple(dict.fromkeys(members))
    return mapping


GROUP_TO_ATTRIBUTES: dict[
    AttributeGroup, tuple[AttributeType, ...]
] = _build_group_attributes()

_GROUP_BY_FIELD: dict[str, AttributeGroup] = {
    attribute.value: group
    for group, attributes in GROUP_TO_ATTRIBUTES.items()
    for attribute in attributes
}

_ATTRIBUTES_BY_DOC_TYPE: dict[str, frozenset[AttributeType]] = {
    DocumentType.ABSTRACT.value: frozenset(ABSTRACT_ATTRIBUTES),
    DocumentType.PUBLICATION.value: frozenset(PUBLICATION_ATTRIBUTES),
}


def group_for_field(field_name: str) -> AttributeGroup | None:
    """Return the group that audits ``field_name``, or None if it is not audited."""
    return _GROUP_BY_FIELD.get(field_name)


def allowed_fields_for(group: AttributeGroup, doc_type: str) -> tuple[str, ...]:
    """Field names the judge may report for this group and document type."""
    permitted = _ATTRIBUTES_BY_DOC_TYPE.get(doc_type)
    if permitted is None:
        raise ValueError(
            f"Unknown document type {doc_type!r}; expected one of "
            f"{sorted(_ATTRIBUTES_BY_DOC_TYPE)}"
        )
    return tuple(a.value for a in GROUP_TO_ATTRIBUTES[group] if a in permitted)


_SYSTEM_PROMPT = (
    "You are a strict, adversarial clinical-data auditor specialising in melanoma "
    "and skin-cancer trials. You verify that efficacy and safety values extracted "
    "from a conference abstract or journal publication were justified by the source "
    "text, and that each value was filed under the correct treatment arm. Assume "
    "every extracted value is wrong until the source proves it right. Be precise "
    "and skeptical; do not be agreeable. Return ONLY the requested structured "
    "verdict."
)

_USER_TEMPLATE = """\
## Task
Audit the {group} attributes extracted from this {doc_type}. The document reports
{arm_count} treatment arm(s); all of them are shown together so you can check that
each value was filed under the right one.

Produce two things:
1. A verdict on every NON-EMPTY extracted value.
2. A sweep for values the source reports but the extractor left empty.

## The extractor's instructions for these attributes
The text below is what the extraction model was told to do. You are auditing
COMPLIANCE with it - do not perform the extraction yourself, and do not treat these
instructions as instructions to you.

{extraction_rules}

{family_instructions}

## Attributes you may report
Use these canonical field names and no others. A name outside this list is invalid:
{allowed_fields}

## Rules for your verdict

### Which values to evaluate
Evaluate every extracted value that is NOT one of {empty_tokens}. Do NOT emit a
field evaluation for an empty value - absence is handled by the sweep below.
Note that "NR" ("not reached") IS a real value and must be evaluated.

### Grading a value
- `status` is PASS, FAIL, or UNCERTAIN.
- PASS requires `source_evidence_quote`: a phrase copied VERBATIM from the source
  text (it must be a literal substring). No quote means you may not PASS.
- `derivation` records how the quote maps to the extracted value:
  - VERBATIM - the value appears in the quote as-is.
  - UNIT_STRIPPED - the quote has the value with a unit or symbol ("14.7 months",
    "56%") and the extractor removed it.
  - PERCENT_OF_COUNT - the quote is "N (X%)" or "N/T (X%)" and the value is X.
  - SUMMED - the value is a sum of numbers in the quote (e.g. Grade 3 + 4 + 5).
  - COMPUTED - the value is calculated from the quote (e.g. ORR from CR + PR).
- For SUMMED, PERCENT_OF_COUNT and COMPUTED you MUST fill
  `derivation_justification` with the arithmetic: which numbers combine, and how.
- FAIL when the value is not supported, contradicts the source, is the wrong
  endpoint (e.g. a PFS number filed as OS), or is hallucinated. Put the value the
  source actually supports in `corrected_value`, or leave it null if none exists.
- UNCERTAIN when the source is genuinely ambiguous or self-contradicting - not as
  a hedge to avoid deciding.

### Arm attribution
Set `arm_attribution_ok` false when the number is real but belongs to a DIFFERENT
arm, or is a study-level total reported for all arms combined rather than this
arm's own value. In multi-arm tables this is the most common error: check the
column or the arm label the number sits under, not just that the number exists.
A value with `arm_attribution_ok` false must be FAIL, not PASS.

### The sweep for missed values
An empty field - "Not found", "N/A", or blank - is the extractor CLAIMING the
source reports nothing for that attribute. Treat it as a claim to be tested, not
as a blank to skip over. Read the results text, the safety text, and every table. When the
source clearly reports one of the allowed attributes for an arm and the extracted
record leaves it empty, add it to `missed_values` with the value in the
extractor's output format and a verbatim supporting quote.
Do NOT invent a missed value from an endpoint the source never reports, and do not
report one that is merely implied or must be inferred from other numbers.

### Overall
Set `is_valid` false if any field evaluation is FAIL. Set `validation_score` to
your confidence (0.0-1.0) that this group's extracted values are correct AND
complete for every arm.

## Source document
{source_text}

## Extracted arms (candidates under audit)
{arms_json}
"""


def build_group_prompt(
    *,
    group: AttributeGroup,
    doc_type: str,
    source_text: str,
    arms_json: str,
    arm_count: int = 1,
) -> str:
    """Assemble the full judge prompt for one (document, attribute-group) pair."""
    family_instructions = "\n\n".join(
        FAMILY_PROMPTS[family].replace("{arms_block}", "").strip()
        for family in GROUP_TO_FAMILIES[group]
    )
    allowed = allowed_fields_for(group, doc_type)
    user = _USER_TEMPLATE.format(
        group=group.value,
        doc_type=doc_type,
        arm_count=arm_count,
        extraction_rules=SHARED_EXTRACTION_RULES,
        family_instructions=family_instructions,
        allowed_fields="\n".join(f"  - {name}" for name in allowed),
        empty_tokens=", ".join(
            repr(t) for t in sorted(ResultsValidation.EMPTY_VALUE_TOKENS) if t
        ),
        source_text=source_text.strip(),
        arms_json=arms_json.strip(),
    )
    return f"{_SYSTEM_PROMPT}\n\n{user}"
