"""Row rules for patching trial_landscape.cancer_type from clinical_trials.

trial_landscape carries its own copy of the label, written by the landscape
uploaders from the same broken query-derived source clinical_trials used to
carry. clinical_trials has since been corrected, so the two disagree and the
landscape pages render trials under buckets the trial never studied.

What matters here: the source is clinical_trials.cancer_type (already promoted
and reviewed, never re-derived), a landscape row with no source row must block
the run rather than be guessed at, and the cleaned extraction JSON that feeds
the landscape uploader has to move with the table or the next upload reverts it.
"""

from __future__ import annotations

from typing import Any

import pytest

from scripts.patch_landscape_cancer_type import (
    MissingSourceRowError,
    backup_payload,
    plan_patches,
    summarise_plan,
    sync_cleaned_payload,
)


def _land(nct: str, cancer_type: list[str] | None) -> dict[str, Any]:
    return {"nct_id": nct, "cancer_type": cancer_type}


def _source(nct: str, cancer_type: list[str] | None) -> dict[str, Any]:
    return {"nct_id": nct, "cancer_type": cancer_type}


# --- what counts as a change ----------------------------------------------


def test_a_row_already_matching_its_source_is_not_a_write() -> None:
    plan = plan_patches(
        [_land("NCT00000001", ["Uveal Melanoma"])],
        [_source("NCT00000001", ["Uveal Melanoma"])],
    )
    assert plan == []


def test_order_alone_is_not_a_change() -> None:
    """Both columns are unordered text[]; a reordering is not a correction."""
    plan = plan_patches(
        [_land("NCT00000002", ["Merkel Cell Carcinoma", "Basal Cell Carcinoma"])],
        [_source("NCT00000002", ["Basal Cell Carcinoma", "Merkel Cell Carcinoma"])],
    )
    assert plan == []


def test_a_fanned_out_row_is_planned_down_to_its_source_value() -> None:
    """The live bug: one BRAF/MEK trial rendered on four landscape pages."""
    (change,) = plan_patches(
        [
            _land(
                "NCT03340506",
                [
                    "Mucosal Melanoma",
                    "Cutaneous Melanoma",
                    "Acral Melanoma",
                    "Uveal Melanoma",
                ],
            )
        ],
        [_source("NCT03340506", ["Cutaneous Melanoma"])],
    )
    assert change["nct_id"] == "NCT03340506"
    assert change["after"] == ["Cutaneous Melanoma"]
    assert change["empties"] is False


def test_a_row_losing_every_bucket_is_planned_and_flagged() -> None:
    """These leave every landscape page, so they are counted apart from relabels."""
    (change,) = plan_patches(
        [_land("NCT01352884", ["Cutaneous Melanoma"])],
        [_source("NCT01352884", [])],
    )
    assert change["after"] == []
    assert change["empties"] is True


def test_a_null_stored_value_is_treated_as_empty() -> None:
    (change,) = plan_patches(
        [_land("NCT00000003", None)],
        [_source("NCT00000003", ["Uveal Melanoma"])],
    )
    assert change["before"] == []


def test_a_null_source_value_is_treated_as_empty() -> None:
    (change,) = plan_patches(
        [_land("NCT00000004", ["Cutaneous Melanoma"])],
        [_source("NCT00000004", None)],
    )
    assert change["after"] == []
    assert change["empties"] is True


def test_source_rows_with_no_landscape_row_are_ignored() -> None:
    """clinical_trials is the larger table; only landscape rows are written."""
    plan = plan_patches(
        [_land("NCT00000001", ["Cutaneous Melanoma"])],
        [
            _source("NCT00000001", ["Cutaneous Melanoma"]),
            _source("NCT00000009", ["Uveal Melanoma"]),
        ],
    )
    assert plan == []


# --- guards ---------------------------------------------------------------


def test_a_landscape_row_with_no_source_row_blocks_the_whole_run() -> None:
    """No source means no reviewed value; guessing would blank a real label."""
    with pytest.raises(MissingSourceRowError, match="NCT00000002"):
        plan_patches(
            [
                _land("NCT00000001", ["Uveal Melanoma"]),
                _land("NCT00000002", ["Cutaneous Melanoma"]),
            ],
            [_source("NCT00000001", ["Uveal Melanoma"])],
        )


# --- backup ---------------------------------------------------------------


def test_backup_carries_the_stored_value_for_every_row_not_just_changes() -> None:
    payload = backup_payload(
        [
            _land("NCT00000001", ["Uveal Melanoma"]),
            _land("NCT00000002", ["Cutaneous Melanoma"]),
        ]
    )
    assert payload["row_count"] == 2
    assert payload["rows"] == [
        {"nct_id": "NCT00000001", "cancer_type": ["Uveal Melanoma"]},
        {"nct_id": "NCT00000002", "cancer_type": ["Cutaneous Melanoma"]},
    ]


# --- keeping the uploader's source in step --------------------------------


def test_cleaned_payload_takes_the_patched_value() -> None:
    """upload_nonindustry_landscape.py upserts cancer_type straight from this file."""
    payload = {
        "trials": [
            {
                "nct_number": "NCT03340506",
                "cancer_type": ["Cutaneous Melanoma", "Uveal Melanoma"],
            }
        ]
    }
    plan = [{"nct_id": "NCT03340506", "after": ["Cutaneous Melanoma"]}]
    assert sync_cleaned_payload(payload, plan) == 1
    assert payload["trials"][0]["cancer_type"] == ["Cutaneous Melanoma"]


def test_cleaned_payload_leaves_trials_the_patch_did_not_touch() -> None:
    payload = {
        "trials": [{"nct_number": "NCT00000009", "cancer_type": ["Uveal Melanoma"]}]
    }
    assert sync_cleaned_payload(payload, []) == 0
    assert payload["trials"][0]["cancer_type"] == ["Uveal Melanoma"]


# --- summary --------------------------------------------------------------


def test_summary_separates_emptied_rows_from_relabelled_ones() -> None:
    plan = plan_patches(
        [
            _land("NCT00000001", ["Cutaneous Melanoma"]),
            _land("NCT00000002", ["Cutaneous Melanoma"]),
            _land("NCT00000003", ["Uveal Melanoma"]),
        ],
        [
            _source("NCT00000001", ["Uveal Melanoma"]),
            _source("NCT00000002", []),
            _source("NCT00000003", ["Uveal Melanoma"]),
        ],
    )
    counts = summarise_plan(plan)
    assert counts["changed"] == 2
    assert counts["emptied"] == 1
    assert counts["relabelled"] == 1
