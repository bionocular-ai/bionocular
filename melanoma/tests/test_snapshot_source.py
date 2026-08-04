"""Unit tests for SnapshotTrialSource — the Supabase-snapshot input source.

Pure functions over an in-memory snapshot dict; no network, no files.
"""
from __future__ import annotations

import pytest

from src.domain.trial_parameter_models import TrialText
from src.infrastructure.clinical_trials.snapshot_source import SnapshotTrialSource


def _snapshot(trials: list[dict]) -> dict:
    return {"metadata": {}, "trials": trials}


_TRIAL_A = {
    "nct_id": "NCT00000001",
    "cancer_type": ["Cutaneous Melanoma"],
    "official_title": "A Phase III Study of Drug X",
    "brief_title": "Drug X Trial",
    "brief_summary": "Testing Drug X in melanoma.",
    "eligibility_criteria": "Inclusion: adults with stage IV melanoma.",
}
_TRIAL_NULL_TITLE = {
    "nct_id": "NCT00000002",
    "cancer_type": ["Basal Cell Carcinoma"],
    "official_title": None,
    "brief_title": "Fallback Title",
    "brief_summary": "Summary.",
    "eligibility_criteria": "Inclusion: BCC.",
}
_TRIAL_BOTH_NULL = {
    "nct_id": "NCT00000003",
    "cancer_type": [],
    "official_title": None,
    "brief_title": None,
    "brief_summary": "Summary only.",
    "eligibility_criteria": "Inclusion: any.",
}


def test_get_all_nct_numbers_sorted() -> None:
    src = SnapshotTrialSource(_snapshot([_TRIAL_NULL_TITLE, _TRIAL_A]))
    assert src.get_all_nct_numbers() == ["NCT00000001", "NCT00000002"]


def test_get_all_nct_numbers_cancer_type_filter() -> None:
    src = SnapshotTrialSource(_snapshot([_TRIAL_A, _TRIAL_NULL_TITLE]))
    assert src.get_all_nct_numbers(["Basal Cell Carcinoma"]) == ["NCT00000002"]


def test_get_cancer_types() -> None:
    src = SnapshotTrialSource(_snapshot([_TRIAL_A]))
    assert src.get_cancer_types("NCT00000001") == ["Cutaneous Melanoma"]


def test_load_trial_full_text_march_format() -> None:
    src = SnapshotTrialSource(_snapshot([_TRIAL_A]))
    trial = src.load_trial("NCT00000001")
    assert isinstance(trial, TrialText)
    assert trial.nct_number == "NCT00000001"
    assert trial.official_title == "A Phase III Study of Drug X"
    expected = (
        "NCT Number: NCT00000001\n\n"
        "officialTitle:\n"
        "A Phase III Study of Drug X\n\n"
        "briefSummary:\n"
        "Testing Drug X in melanoma.\n\n"
        "eligibilityCriteria:\n"
        "Inclusion: adults with stage IV melanoma.\n"
    )
    assert trial.full_text == expected


def test_load_trial_null_title_falls_back_to_brief_title() -> None:
    src = SnapshotTrialSource(_snapshot([_TRIAL_NULL_TITLE]))
    trial = src.load_trial("NCT00000002")
    assert trial.official_title == "Fallback Title"
    assert "officialTitle:\nFallback Title" in trial.full_text


def test_load_trial_both_titles_null_emits_empty() -> None:
    src = SnapshotTrialSource(_snapshot([_TRIAL_BOTH_NULL]))
    trial = src.load_trial("NCT00000003")
    assert trial.official_title == ""
    assert "officialTitle:\n\n" in trial.full_text


def test_load_trial_missing_nct_raises() -> None:
    src = SnapshotTrialSource(_snapshot([_TRIAL_A]))
    with pytest.raises(KeyError):
        src.load_trial("NCT99999999")


_TRIAL_WITH_INTERVENTIONS = {
    "nct_id": "NCT00000010",
    "cancer_type": ["Cutaneous Melanoma"],
    "official_title": "Study of Nivolumab",
    "brief_title": "Nivo Trial",
    "brief_summary": "Testing nivolumab.",
    "eligibility_criteria": "Inclusion: stage IV.",
    "interventions": [
        {
            "type": "BIOLOGICAL",
            "name": "Nivolumab",
            "description": "Anti-PD-1 antibody given IV.",
        },
        # Comparator drug — kept, so the extractor can tell it from the treatment.
        {"type": "DRUG", "name": "Dacarbazine", "description": ""},
        # Non-treatment entries — must be filtered out.
        {"type": "DRUG", "name": "Placebo", "description": "Matching placebo."},
        {"type": "DIAGNOSTIC_TEST", "name": "CT scan", "description": "Imaging."},
        {"type": "PROCEDURE", "name": "Sham surgery", "description": ""},
        {"type": "OTHER", "name": "Best Supportive Care", "description": ""},
        # No name — skipped.
        {"type": "DRUG", "name": "", "description": "orphan"},
    ],
}


def test_load_trial_renders_interventions_section() -> None:
    src = SnapshotTrialSource(_snapshot([_TRIAL_WITH_INTERVENTIONS]))
    trial = src.load_trial("NCT00000010")
    assert (
        "interventions:\n"
        "- BIOLOGICAL - Nivolumab - Anti-PD-1 antibody given IV.\n"
        "- DRUG - Dacarbazine\n\n"
    ) in trial.full_text
    # Section sits between briefSummary and eligibilityCriteria.
    assert trial.full_text.index("interventions:") < trial.full_text.index(
        "eligibilityCriteria:"
    )


def test_load_trial_interventions_filters_non_treatments() -> None:
    src = SnapshotTrialSource(_snapshot([_TRIAL_WITH_INTERVENTIONS]))
    full_text = src.load_trial("NCT00000010").full_text
    for dropped in ("Placebo", "CT scan", "Sham surgery", "Best Supportive Care"):
        assert dropped not in full_text
    assert "orphan" not in full_text


def test_load_trial_no_interventions_omits_section() -> None:
    src = SnapshotTrialSource(_snapshot([_TRIAL_A]))
    assert "interventions:" not in src.load_trial("NCT00000001").full_text


def test_load_trial_all_interventions_filtered_omits_section() -> None:
    trial = dict(_TRIAL_A)
    trial["nct_id"] = "NCT00000011"
    trial["interventions"] = [{"type": "DRUG", "name": "Placebo", "description": ""}]
    src = SnapshotTrialSource(_snapshot([trial]))
    assert "interventions:" not in src.load_trial("NCT00000011").full_text
