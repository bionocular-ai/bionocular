"""Row rules for promoting cancer_type_derived into cancer_type.

This is the step users see: 4345 rows of a filter every dashboard and the chat
agent read. The rules that matter are what counts as a change, what must block
the run, and what the backup has to contain for a revert to be possible.
"""

from __future__ import annotations

from typing import Any

import pytest

from scripts.promote_cancer_type import (
    IncompleteBackfillError,
    backup_payload,
    plan_promotions,
    summarise_plan,
)


def _row(
    nct: str, stored: list[str] | None, derived: list[str] | None
) -> dict[str, Any]:
    return {"nct_id": nct, "cancer_type": stored, "cancer_type_derived": derived}


# --- what counts as a change ----------------------------------------------


def test_a_row_already_agreeing_is_not_a_write() -> None:
    rows = [_row("NCT00000001", ["Uveal Melanoma"], ["Uveal Melanoma"])]
    assert plan_promotions(rows) == []


def test_order_alone_is_not_a_change() -> None:
    rows = [
        _row(
            "NCT00000002",
            ["Merkel Cell Carcinoma", "Basal Cell Carcinoma"],
            ["Basal Cell Carcinoma", "Merkel Cell Carcinoma"],
        )
    ]
    assert plan_promotions(rows) == []


def test_a_corrected_row_is_planned_with_both_values() -> None:
    rows = [
        _row(
            "NCT06581406",
            ["Cutaneous Melanoma", "Uveal Melanoma"],
            ["Uveal Melanoma"],
        )
    ]
    (change,) = plan_promotions(rows)
    assert change["nct_id"] == "NCT06581406"
    assert change["before"] == ["Cutaneous Melanoma", "Uveal Melanoma"]
    assert change["after"] == ["Uveal Melanoma"]


def test_a_row_losing_every_bucket_is_planned_and_flagged() -> None:
    """These drop out of every dashboard filter, so they are counted separately."""
    rows = [_row("NCT00448552", ["Basal Cell Carcinoma"], [])]
    (change,) = plan_promotions(rows)
    assert change["after"] == []
    assert change["empties"] is True


def test_a_null_stored_value_is_treated_as_empty() -> None:
    rows = [_row("NCT00000003", None, ["Uveal Melanoma"])]
    (change,) = plan_promotions(rows)
    assert change["before"] == []


# --- guards ---------------------------------------------------------------


def test_an_unbackfilled_row_blocks_the_whole_run() -> None:
    """A NULL derived value would blank a real label. Never promote a partial table."""
    rows = [
        _row("NCT00000001", ["Uveal Melanoma"], ["Uveal Melanoma"]),
        _row("NCT00000002", ["Cutaneous Melanoma"], None),
    ]
    with pytest.raises(IncompleteBackfillError, match="NCT00000002"):
        plan_promotions(rows)


# --- backup ---------------------------------------------------------------


def test_backup_carries_the_stored_value_for_every_row_not_just_changes() -> None:
    """A diff-shaped backup cannot recover a row the run touched unexpectedly."""
    rows = [
        _row("NCT00000001", ["Uveal Melanoma"], ["Uveal Melanoma"]),
        _row("NCT00000002", ["Cutaneous Melanoma"], []),
    ]
    payload = backup_payload(rows)
    assert payload["row_count"] == 2
    assert payload["rows"] == [
        {"nct_id": "NCT00000001", "cancer_type": ["Uveal Melanoma"]},
        {"nct_id": "NCT00000002", "cancer_type": ["Cutaneous Melanoma"]},
    ]


# --- summary --------------------------------------------------------------


def test_summary_separates_emptied_rows_from_relabelled_ones() -> None:
    rows = [
        _row("NCT00000001", ["Cutaneous Melanoma"], ["Uveal Melanoma"]),
        _row("NCT00000002", ["Cutaneous Melanoma"], []),
        _row("NCT00000003", ["Uveal Melanoma"], ["Uveal Melanoma"]),
    ]
    counts = summarise_plan(plan_promotions(rows))
    assert counts["changed"] == 2
    assert counts["emptied"] == 1
    assert counts["relabelled"] == 1
