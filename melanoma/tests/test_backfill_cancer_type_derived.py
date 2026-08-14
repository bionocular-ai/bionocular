"""Row rules for the cancer_type_derived backfill.

The backfill writes four shadow columns and leaves `cancer_type` alone, so what
matters is the payload shape (what reaches Supabase) and the diff (what a
reviewer sees before the later promote step decides anything).
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from scripts.backfill_cancer_type_derived import (
    build_payload,
    diff_rows,
    summarise,
    write_report,
)


def _row(nct: str, conditions: list[str], stored: list[str] | None) -> dict[str, Any]:
    return {"nct_id": nct, "conditions": conditions, "cancer_type": stored}


# --- payload --------------------------------------------------------------


def test_payload_carries_only_the_four_shadow_columns() -> None:
    payload = build_payload(["Metastatic Uveal Melanoma"])
    assert set(payload) == {
        "cancer_type_derived",
        "cancer_type_evidence",
        "is_basket",
        "melanoma_unspecified",
    }


def test_payload_never_touches_cancer_type() -> None:
    assert "cancer_type" not in build_payload(["Melanoma"])


def test_payload_values_match_the_derivation() -> None:
    payload = build_payload(["Metastatic Uveal Melanoma"])
    assert payload["cancer_type_derived"] == ["Uveal Melanoma"]
    assert payload["cancer_type_evidence"] == {
        "Uveal Melanoma": "Metastatic Uveal Melanoma"
    }
    assert payload["is_basket"] is False


def test_payload_for_a_non_skin_trial_is_an_empty_bucket_list() -> None:
    payload = build_payload(["Cancer"])
    assert payload["cancer_type_derived"] == []
    assert payload["cancer_type_evidence"] == {}
    assert payload["is_basket"] is True


def test_missing_conditions_do_not_raise() -> None:
    assert build_payload(None)["cancer_type_derived"] == []


# --- diff -----------------------------------------------------------------


def test_agreeing_rows_are_left_out_of_the_diff() -> None:
    rows = [_row("NCT00000001", ["Uveal Melanoma"], ["Uveal Melanoma"])]
    assert diff_rows(rows) == []


def test_order_alone_is_not_a_disagreement() -> None:
    rows = [
        _row(
            "NCT00000002",
            ["Basal Cell Carcinoma", "Merkel Cell Carcinoma"],
            ["Merkel Cell Carcinoma", "Basal Cell Carcinoma"],
        )
    ]
    assert diff_rows(rows) == []


def test_diff_records_what_the_search_term_over_tagged() -> None:
    rows = [
        _row(
            "NCT06581406",
            ["Metastatic Uveal Melanoma"],
            ["Cutaneous Melanoma", "Uveal Melanoma"],
        )
    ]
    (diff,) = diff_rows(rows)
    assert diff["nct_id"] == "NCT06581406"
    assert diff["removed"] == ["Cutaneous Melanoma"]
    assert diff["added"] == []
    assert diff["derived"] == ["Uveal Melanoma"]


def test_diff_records_what_the_search_term_missed() -> None:
    rows = [_row("NCT04589832", ["Uveal Melanoma"], ["Cutaneous Melanoma"])]
    (diff,) = diff_rows(rows)
    assert diff["added"] == ["Uveal Melanoma"]
    assert diff["removed"] == ["Cutaneous Melanoma"]


def test_rows_losing_every_bucket_are_flagged_for_the_promote_step() -> None:
    rows = [_row("NCT00020579", ["Cancer"], ["Cutaneous Melanoma"])]
    (diff,) = diff_rows(rows)
    assert diff["derived"] == []
    assert diff["is_basket"] is True


def test_a_null_stored_value_is_treated_as_empty() -> None:
    rows = [_row("NCT00000003", ["Uveal Melanoma"], None)]
    (diff,) = diff_rows(rows)
    assert diff["added"] == ["Uveal Melanoma"]


# --- summary --------------------------------------------------------------


def test_summary_counts_buckets_flags_and_empty_rows() -> None:
    rows = [
        _row("NCT00000001", ["Uveal Melanoma"], None),
        _row("NCT00000002", ["Melanoma"], None),
        _row("NCT00000003", ["Cancer"], None),
    ]
    counts = summarise(rows)
    assert counts["Uveal Melanoma"] == 1
    assert counts["Cutaneous Melanoma"] == 1
    assert counts["(no bucket)"] == 1
    assert counts["is_basket"] == 1


# --- report ---------------------------------------------------------------


def test_report_is_csv_with_one_line_per_disagreement(tmp_path: Path) -> None:
    rows = [
        _row("NCT06581406", ["Metastatic Uveal Melanoma"], ["Cutaneous Melanoma"]),
        _row("NCT00000001", ["Uveal Melanoma"], ["Uveal Melanoma"]),
    ]
    out = tmp_path / "diff.csv"
    write_report(diff_rows(rows), out)

    written = list(csv.DictReader(out.read_text(encoding="utf-8").splitlines()))
    assert [r["nct_id"] for r in written] == ["NCT06581406"]
    assert written[0]["derived"] == "Uveal Melanoma"
    assert written[0]["removed"] == "Cutaneous Melanoma"
