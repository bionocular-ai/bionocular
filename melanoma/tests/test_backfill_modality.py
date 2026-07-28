"""Row-pairing rules for the modality backfill.

The script writes one column on rows a human approved from a diff file, so the
pairing is the whole safety story: what becomes a write, what is left alone, and
what the reviewer sees next to each change.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.backfill_modality import pair_rows, sync_cleaned_results


def _result(nct: str, modality: list[str], status: str = "done") -> dict[str, Any]:
    return {
        "nct_number": nct,
        "modality": modality,
        "extraction_status": status,
        "treatment_name": "Radiotherapy",
    }


def _live(nct: str, modality: str | None) -> dict[str, Any]:
    return {
        "nct_id": nct,
        "modality": modality,
        "treatment_name": "External beam radiotherapy",
        "cancer_type": ["Cutaneous Melanoma"],
    }


def _snapshot_row(nct: str, types: list[str]) -> dict[str, Any]:
    return {
        "nct_id": nct,
        "study_type": "INTERVENTIONAL",
        "interventions": [{"type": t, "name": t.title()} for t in types],
    }


def test_other_is_replaced_by_the_extracted_value() -> None:
    diff = pair_rows(
        [_result("NCT00000001", ["Radiotherapy"])],
        [_snapshot_row("NCT00000001", ["RADIATION"])],
        [_live("NCT00000001", "Other")],
    )

    assert len(diff) == 1
    assert diff[0]["before"] == "Other"
    assert diff[0]["after"] == "Radiotherapy"
    assert diff[0]["study_type"] == "INTERVENTIONAL"
    assert diff[0]["intervention_types"] == ["RADIATION"]
    # The stored treatment_name is the review anchor, not the run's.
    assert diff[0]["treatment_name"] == "External beam radiotherapy"


def test_multi_value_modality_is_joined_for_the_text_column() -> None:
    diff = pair_rows(
        [_result("NCT00000001", ["Chemotherapy", "Radiotherapy"])],
        [_snapshot_row("NCT00000001", ["DRUG", "RADIATION"])],
        [_live("NCT00000001", "Other")],
    )

    assert diff[0]["after"] == "Chemotherapy; Radiotherapy"


def test_null_modality_is_backfilled() -> None:
    diff = pair_rows(
        [_result("NCT00000001", ["Device"])],
        [_snapshot_row("NCT00000001", ["DEVICE"])],
        [_live("NCT00000001", None)],
    )

    assert diff[0]["before"] is None
    assert diff[0]["after"] == "Device"


def test_partial_extraction_never_overwrites_a_stored_value() -> None:
    """An empty modality means "could not tell", not "the answer is nothing"."""
    diff = pair_rows(
        [_result("NCT00000001", [], status="partial")],
        [_snapshot_row("NCT00000001", ["DEVICE"])],
        [_live("NCT00000001", "Other")],
    )

    assert diff == []


def test_done_but_empty_modality_is_also_skipped() -> None:
    diff = pair_rows(
        [_result("NCT00000001", [])],
        [_snapshot_row("NCT00000001", ["DEVICE"])],
        [_live("NCT00000001", "Other")],
    )

    assert diff == []


def test_other_only_never_replaces_a_stored_class() -> None:
    """Observed on NCT03772899: `Other; Monoclonal Antibody` -> `Other`.

    The regimen mixed an unclassifiable agent with a checkpoint inhibitor and
    the model answered for the odd agent only. That is strictly worse than the
    stored value, so it is not a write.
    """
    diff = pair_rows(
        [_result("NCT00000001", ["Other"])],
        [_snapshot_row("NCT00000001", ["BIOLOGICAL"])],
        [_live("NCT00000001", "Other; Monoclonal Antibody")],
    )

    assert diff == []


def test_other_only_still_fills_an_empty_value() -> None:
    """Nothing is lost when there was no class stored - Other beats NULL."""
    diff = pair_rows(
        [_result("NCT00000001", ["Other"])],
        [_snapshot_row("NCT00000001", ["OTHER"])],
        [_live("NCT00000001", None)],
    )

    assert diff[0]["after"] == "Other"


def test_other_alongside_a_real_class_is_still_written() -> None:
    """Only an Other-*only* answer is a downgrade."""
    diff = pair_rows(
        [_result("NCT00000001", ["Radiotherapy", "Other"])],
        [_snapshot_row("NCT00000001", ["RADIATION"])],
        [_live("NCT00000001", "Other")],
    )

    assert diff[0]["after"] == "Radiotherapy; Other"


def test_unchanged_value_is_not_a_write() -> None:
    diff = pair_rows(
        [_result("NCT00000001", ["Chemotherapy"])],
        [_snapshot_row("NCT00000001", ["DRUG"])],
        [_live("NCT00000001", "Chemotherapy")],
    )

    assert diff == []


def test_row_absent_from_the_live_table_is_skipped() -> None:
    diff = pair_rows(
        [_result("NCT00000009", ["Radiotherapy"])],
        [_snapshot_row("NCT00000009", ["RADIATION"])],
        [_live("NCT00000001", "Other")],
    )

    assert diff == []


def test_missing_snapshot_context_still_yields_the_update() -> None:
    """Context is for the reviewer; its absence must not drop a real repair."""
    diff = pair_rows(
        [_result("NCT00000001", ["Radiotherapy"])],
        [],
        [_live("NCT00000001", "Other")],
    )

    assert len(diff) == 1
    assert diff[0]["study_type"] is None
    assert diff[0]["intervention_types"] == []


def test_sync_cleaned_results_rewrites_only_backfilled_rows(tmp_path: Path) -> None:
    """Left stale, upload_nonindustry_landscape.py would revert the backfill."""
    path = tmp_path / "results.cleaned.json"
    path.write_text(
        json.dumps(
            {
                "trials": [
                    {"nct_number": "NCT00000001", "modality": ["Other"]},
                    {"nct_number": "NCT00000002", "modality": ["Chemotherapy"]},
                ]
            }
        )
    )

    sync_cleaned_results(
        [{"nct_id": "NCT00000001", "after": "Chemotherapy; Radiotherapy"}], path
    )

    trials = json.loads(path.read_text())["trials"]
    assert trials[0]["modality"] == ["Chemotherapy", "Radiotherapy"]
    assert trials[1]["modality"] == ["Chemotherapy"]


def test_sync_cleaned_results_tolerates_a_missing_file(tmp_path: Path) -> None:
    sync_cleaned_results([{"nct_id": "NCT00000001", "after": "Device"}], tmp_path / "x")
