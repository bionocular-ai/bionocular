"""Tests for the trial_landscape study-type guard.

The guard exists because 150 OBSERVATIONAL rows reached the live table and had to be
deleted on 2026-08-07. These pin the rule that keeps them out.
"""

from src.domain.constants import TrialLandscape
from src.domain.trial_landscape_guard import partition_by_study_type


def test_interventional_is_accepted() -> None:
    records = [{"nct_id": "NCT1"}]

    kept, rejected = partition_by_study_type(records, {"NCT1": "INTERVENTIONAL"})

    assert kept == records
    assert rejected == []


def test_expanded_access_is_accepted() -> None:
    """Compassionate use has no arms but is still a treatment record."""
    records = [{"nct_id": "NCT1"}]

    kept, rejected = partition_by_study_type(records, {"NCT1": "EXPANDED_ACCESS"})

    assert kept == records
    assert rejected == []


def test_observational_is_rejected_with_its_type_as_the_reason() -> None:
    kept, rejected = partition_by_study_type(
        [{"nct_id": "NCT1"}], {"NCT1": "OBSERVATIONAL"}
    )

    assert kept == []
    assert rejected == [("NCT1", "OBSERVATIONAL")]


def test_trial_absent_from_clinical_trials_is_rejected() -> None:
    """A landscape row references clinical_trials; no row there means no row here."""
    kept, rejected = partition_by_study_type([{"nct_id": "NCT_GONE"}], {})

    assert kept == []
    assert rejected == [("NCT_GONE", "not in clinical_trials")]


def test_mixed_payload_splits_and_preserves_order() -> None:
    records = [{"nct_id": "NCT1"}, {"nct_id": "NCT2"}, {"nct_id": "NCT3"}]
    types = {
        "NCT1": "INTERVENTIONAL",
        "NCT2": "OBSERVATIONAL",
        "NCT3": "EXPANDED_ACCESS",
    }

    kept, rejected = partition_by_study_type(records, types)

    assert [r["nct_id"] for r in kept] == ["NCT1", "NCT3"]
    assert rejected == [("NCT2", "OBSERVATIONAL")]


def test_observational_is_not_in_the_accepted_set() -> None:
    assert "OBSERVATIONAL" not in TrialLandscape.INCLUDED_STUDY_TYPES
    assert set(TrialLandscape.INCLUDED_STUDY_TYPES) == {
        "INTERVENTIONAL",
        "EXPANDED_ACCESS",
    }
