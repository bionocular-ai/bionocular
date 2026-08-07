"""Tests for the validation Supabase writer's pure functions.

The writer gained a second table (trial_landscape) after it had already written the
trial_outcomes cohorts. These pin the trial_outcomes conversions that were in use before
that change, and cover the landscape spec alongside them.
"""
import pathlib
import sys

import pytest

_scripts = pathlib.Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(_scripts))

from write_validation_supabase import (  # noqa: E402
    SPECS,
    build_patches,
    canonical,
    find_drift,
    read_rows,
    to_db,
)

OUTCOMES = SPECS["trial_outcomes"]
LANDSCAPE = SPECS["trial_landscape"]


class TestToDb:
    def test_empty_becomes_null(self) -> None:
        assert to_db(OUTCOMES, "arm_name", "") is None

    def test_text_passes_through(self) -> None:
        assert to_db(OUTCOMES, "arm_name", "Nivolumab") == "Nivolumab"

    def test_int_column_parses_via_float(self) -> None:
        assert to_db(OUTCOMES, "num_patients", "42.0") == 42

    def test_unlisted_column_is_numeric(self) -> None:
        assert to_db(OUTCOMES, "orr_pct", "37.5") == 37.5

    def test_array_column_is_json_decoded(self) -> None:
        assert to_db(OUTCOMES, "cancer_type", '["Cutaneous Melanoma"]') == [
            "Cutaneous Melanoma"
        ]

    def test_landscape_cancer_type_is_still_an_array(self) -> None:
        assert to_db(LANDSCAPE, "cancer_type", '["Uveal Melanoma"]') == [
            "Uveal Melanoma"
        ]

    def test_landscape_vocabulary_columns_are_text(self) -> None:
        assert to_db(LANDSCAPE, "stage", "Stage III/IV") == "Stage III/IV"
        assert to_db(LANDSCAPE, "line_of_therapy", "1L") == "1L"


class TestCanonical:
    def test_array_order_is_not_a_change(self) -> None:
        as_text = canonical(OUTCOMES, "is_nr", '["os", "pfs"]')
        as_list = canonical(OUTCOMES, "is_nr", ["pfs", "os"])
        assert as_text == as_list

    def test_numeric_strings_compare_equal_across_renderings(self) -> None:
        assert canonical(OUTCOMES, "orr_pct", "37.50") == canonical(
            OUTCOMES, "orr_pct", 37.5
        )

    def test_empty_and_none_agree(self) -> None:
        assert canonical(OUTCOMES, "arm_name", "") == canonical(
            OUTCOMES, "arm_name", None
        )

    def test_landscape_text_is_compared_literally(self) -> None:
        assert canonical(LANDSCAPE, "stage", "Stage IV") == "Stage IV"


class TestBuildPatches:
    def test_only_changed_columns_are_carried(self) -> None:
        baseline = {"NCT1": {"nct_id": "NCT1", "stage": "Stage IV", "biomarker": ""}}
        patched = {"NCT1": {"nct_id": "NCT1", "stage": "Stage III/IV", "biomarker": ""}}

        patches = build_patches(LANDSCAPE, baseline, patched)

        assert patches == {"NCT1": {"stage": "Stage III/IV"}}

    def test_unchanged_row_produces_no_patch(self) -> None:
        rows = {"NCT1": {"nct_id": "NCT1", "stage": "Stage IV"}}

        assert build_patches(LANDSCAPE, rows, dict(rows)) == {}


class TestFindDrift:
    def test_clean_when_live_matches_baseline(self) -> None:
        baseline = {"NCT1": {"nct_id": "NCT1", "stage": "Stage IV"}}
        live = {"NCT1": {"nct_id": "NCT1", "stage": "Stage IV"}}

        assert find_drift(LANDSCAPE, live, baseline) == []

    def test_changed_cell_is_reported(self) -> None:
        baseline = {"NCT1": {"nct_id": "NCT1", "stage": "Stage IV"}}
        live = {"NCT1": {"nct_id": "NCT1", "stage": "Stage III"}}

        drift = find_drift(LANDSCAPE, live, baseline)

        assert [(d[0], d[1]) for d in drift] == [("NCT1", "stage")]

    def test_missing_live_row_is_reported(self) -> None:
        baseline = {"NCT1": {"nct_id": "NCT1", "stage": "Stage IV"}}

        assert find_drift(LANDSCAPE, {}, baseline)[0][3] == "missing"

    def test_exempt_column_never_drifts(self) -> None:
        """created_at renders differently either side; it is never written."""
        baseline = {"NCT1": {"nct_id": "NCT1", "created_at": "2026-07-17 08:06:24+00"}}
        live = {"NCT1": {"nct_id": "NCT1", "created_at": "2026-07-17T08:06:24Z"}}

        assert find_drift(LANDSCAPE, live, baseline) == []


class TestReadRows:
    def test_landscape_reads_every_row_keyed_by_nct_id(
        self, tmp_path: pathlib.Path
    ) -> None:
        path = tmp_path / "rows.csv"
        path.write_text("nct_id,stage\nNCT1,Stage IV\nNCT2,Stage II\n")

        rows = read_rows(path, LANDSCAPE, None)

        assert set(rows) == {"NCT1", "NCT2"}

    def test_outcomes_filters_to_the_requested_cohort(
        self, tmp_path: pathlib.Path
    ) -> None:
        path = tmp_path / "rows.csv"
        path.write_text(
            "id,source_type,arm_name\n"
            "a,abstract,Nivolumab\n"
            "p,publication,Ipilimumab\n"
        )

        rows = read_rows(path, OUTCOMES, "abstract")

        assert set(rows) == {"a"}


@pytest.mark.parametrize("name", sorted(SPECS))
def test_every_spec_exempts_created_at_from_drift(name: str) -> None:
    """The export renders timestamps differently from the API on both tables."""
    assert "created_at" in SPECS[name].drift_exempt
