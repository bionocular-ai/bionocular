"""Tests for the judge's attribute grouping and prompt assembly.

The partition tests are the important ones: an attribute that belongs to no group
is never audited, and the omission is silent. These assert coverage is total and
that every exclusion is deliberate.
"""

from __future__ import annotations

import pytest

from src.domain.extraction_models import (
    ABSTRACT_ATTRIBUTES,
    PUBLICATION_ATTRIBUTES,
    AttributeType,
)
from src.domain.results_validation_models import AttributeGroup
from src.domain.results_validation_prompts import (
    FILE_PATH_SOURCED_ATTRIBUTES,
    GROUP_TO_ATTRIBUTES,
    TRIALS_PIPELINE_ATTRIBUTES,
    UNAUDITED_ATTRIBUTES,
    allowed_fields_for,
    build_group_prompt,
    group_for_field,
)

_ARMS_JSON = '{"arm_1": {"median_pfs": "15.3"}}'
_SOURCE = "Median PFS was 15.3 months."


# ---------------------------------------------------------------------------
# Partition
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "attributes"),
    [("abstract", ABSTRACT_ATTRIBUTES), ("publication", PUBLICATION_ATTRIBUTES)],
)
def test_groups_plus_exclusions_cover_every_extracted_attribute(
    label: str, attributes: list[AttributeType]
) -> None:
    grouped: set[AttributeType] = set()
    for members in GROUP_TO_ATTRIBUTES.values():
        grouped |= set(members)

    uncovered = set(attributes) - grouped - UNAUDITED_ATTRIBUTES

    assert uncovered == set(), f"{label} attributes audited by no group: {uncovered}"


def test_groups_are_mutually_disjoint() -> None:
    seen: set[AttributeType] = set()
    for group, members in GROUP_TO_ATTRIBUTES.items():
        overlap = seen & set(members)
        assert overlap == set(), f"{group} repeats {overlap}"
        seen |= set(members)


def test_excluded_attributes_are_only_the_file_path_sourced_ones() -> None:
    """These are read from the filename, not the document body - grading them
    against the text would manufacture false failures."""
    assert {a.value for a in FILE_PATH_SOURCED_ATTRIBUTES} == {
        "conference",
        "published_year",
        "pdf_number",
    }


def test_modality_and_target_are_left_to_the_trials_validation_pipeline() -> None:
    """They are drug classifications, not values stated in the document body."""
    assert {a.value for a in TRIALS_PIPELINE_ATTRIBUTES} == {"modality", "target"}
    assert group_for_field("modality") is None
    assert group_for_field("target") is None


def test_no_excluded_attribute_is_also_grouped() -> None:
    for members in GROUP_TO_ATTRIBUTES.values():
        assert not (set(members) & UNAUDITED_ATTRIBUTES)


def test_every_group_has_at_least_one_attribute() -> None:
    for group in AttributeGroup:
        assert GROUP_TO_ATTRIBUTES[group], f"{group} is empty"


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------


def test_group_for_field_routes_known_attributes() -> None:
    assert group_for_field("nct_number") is AttributeGroup.IDENTIFICATION
    assert group_for_field("median_pfs") is AttributeGroup.EFFICACY
    assert group_for_field("grade_3_plus_trae") is AttributeGroup.SAFETY


def test_group_for_field_returns_none_for_unaudited_and_unknown_fields() -> None:
    assert group_for_field("conference") is None
    assert group_for_field("not_an_attribute") is None


def test_unfamilied_document_attributes_are_audited_as_identification() -> None:
    for field in ("number_of_patients", "publication_name", "publication_year"):
        assert group_for_field(field) is AttributeGroup.IDENTIFICATION


def test_allowed_fields_are_scoped_to_the_document_type() -> None:
    abstract_fields = allowed_fields_for(AttributeGroup.IDENTIFICATION, "abstract")
    publication_fields = allowed_fields_for(
        AttributeGroup.IDENTIFICATION, "publication"
    )

    assert "abstract_number" in abstract_fields
    assert "publication_name" not in abstract_fields
    assert "publication_name" in publication_fields


def test_allowed_fields_rejects_an_unknown_document_type() -> None:
    with pytest.raises(ValueError, match="poster"):
        allowed_fields_for(AttributeGroup.EFFICACY, "poster")


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------


def test_prompt_embeds_the_source_the_candidates_and_the_allowed_fields() -> None:
    prompt = build_group_prompt(
        group=AttributeGroup.EFFICACY,
        doc_type="publication",
        source_text=_SOURCE,
        arms_json=_ARMS_JSON,
    )

    assert _SOURCE in prompt
    assert _ARMS_JSON in prompt
    assert "median_pfs" in prompt


def test_prompt_carries_the_extractors_own_transform_rules() -> None:
    """The judge must know the extractor was told to strip '%' and sum G3+G4+G5,
    otherwise it fails correct values for not matching the source verbatim."""
    prompt = build_group_prompt(
        group=AttributeGroup.SAFETY,
        doc_type="publication",
        source_text=_SOURCE,
        arms_json=_ARMS_JSON,
    )

    assert "no % symbol" in prompt
    assert "sum Grade 3% + Grade 4% + Grade 5%" in prompt


def test_prompt_states_that_not_found_is_a_claim_to_be_tested() -> None:
    prompt = build_group_prompt(
        group=AttributeGroup.EFFICACY,
        doc_type="publication",
        source_text=_SOURCE,
        arms_json=_ARMS_JSON,
    )

    assert "Not found" in prompt
    assert "missed_values" in prompt


def test_prompt_leaves_no_unfilled_template_placeholder() -> None:
    """The family prompts contain JSON examples, so a bare '{' proves nothing -
    check for the specific placeholder names the template substitutes."""
    placeholders = [
        "{arms_block}",
        "{group}",
        "{doc_type}",
        "{arm_count}",
        "{extraction_rules}",
        "{family_instructions}",
        "{allowed_fields}",
        "{empty_tokens}",
        "{source_text}",
        "{arms_json}",
    ]

    for group in AttributeGroup:
        prompt = build_group_prompt(
            group=group,
            doc_type="publication",
            source_text=_SOURCE,
            arms_json=_ARMS_JSON,
        )

        for placeholder in placeholders:
            assert placeholder not in prompt


def test_each_group_prompt_names_only_its_own_attributes_as_allowed() -> None:
    prompt = build_group_prompt(
        group=AttributeGroup.IDENTIFICATION,
        doc_type="publication",
        source_text=_SOURCE,
        arms_json=_ARMS_JSON,
    )
    allowed_block = prompt.split("## Attributes you may report")[1].split("##")[0]

    assert "nct_number" in allowed_block
    assert "grade_3_plus_trae" not in allowed_block
