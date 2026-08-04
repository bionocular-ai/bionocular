"""Unit tests for the LLM-as-a-Judge validation prompt content.

cancer_type is a TRUSTED tag from the CT.gov condition query - not an LLM
extraction - so the judge must not grade it. It is provided only as the scoping
anchor: it identifies the skin-cancer cohort so every other field is graded
against that cohort's eligibility and other tumour types are discarded.
"""

from __future__ import annotations

from src.domain.trials_extraction_prompts import CANCER_TYPE_VALUES
from src.domain.trials_validation_prompts import _ENUM_VOCAB, build_validation_prompt

_SOURCE = (
    "officialTitle:\nStudy of Nivolumab in advanced melanoma\n\n"
    "eligibilityCriteria:\nStage IV cutaneous melanoma; brain metastases allowed."
)
_CANDIDATE = '{\n  "cancer_type": ["Cutaneous Melanoma"]\n}'


def test_cancer_type_values_match_live_tags() -> None:
    """The SSOT vocabulary is exactly the 8 tags emitted by discovery/Supabase."""
    assert set(CANCER_TYPE_VALUES) == {
        "Cutaneous Melanoma",
        "Cutaneous Squamous Cell Carcinoma",
        "Cutaneous Melanoma with Brain/CNS Metastasis",
        "Uveal Melanoma",
        "Acral Melanoma",
        "Mucosal Melanoma",
        "Basal Cell Carcinoma",
        "Merkel Cell Carcinoma",
    }


def test_cancer_type_not_in_graded_vocabulary() -> None:
    """cancer_type is not a graded enum - the judge never PASS/FAILs it."""
    assert "cancer_type" not in _ENUM_VOCAB


def test_cancer_type_marked_trusted_not_audited() -> None:
    """The prompt tells the judge cancer_type is a trusted, given tag, not audited."""
    prompt = build_validation_prompt(_SOURCE, _CANDIDATE).lower()
    assert "cancer_type" in prompt
    assert "trusted" in prompt or "not audit" in prompt or "do not grade" in prompt
    # sourced from the CT.gov query, not the eligibility text
    assert "ct.gov" in prompt or "condition query" in prompt or "discovery" in prompt


def test_cancer_type_indications_listed_as_context() -> None:
    """The 8 skin-cancer indications appear as context to identify the cohort."""
    prompt = build_validation_prompt(_SOURCE, _CANDIDATE)
    for value in CANCER_TYPE_VALUES:
        assert value in prompt, f"missing cancer_type value: {value}"


def test_brain_cns_interpretation_rule() -> None:
    """Combined Brain/CNS tag is understood as brain OR CNS metastases."""
    prompt = build_validation_prompt(_SOURCE, _CANDIDATE).lower()
    assert "brain" in prompt and "cns" in prompt
    assert " or " in prompt  # brain OR CNS


def test_rare_melanoma_grouping_rule() -> None:
    """Rare Melanoma is defined as Acral / Uveal / Mucosal."""
    prompt = build_validation_prompt(_SOURCE, _CANDIDATE)
    assert "Rare Melanoma" in prompt
    lowered = prompt.lower()
    assert "acral" in lowered and "uveal" in lowered and "mucosal" in lowered


def test_basket_trial_scoping_rule() -> None:
    """The judge grades every other field only against the skin-cancer cohort."""
    prompt = build_validation_prompt(_SOURCE, _CANDIDATE).lower()
    assert "basket" in prompt or "multiple tumour" in prompt or "pan-tumour" in prompt
    assert "discard" in prompt or "ignore" in prompt or "only" in prompt
