"""Tests for the trials validation patcher.

Covers what the pass must and must not touch: the four vocabulary fields are written,
modality and treatment_name are held back whatever the judge said, and a correction with
nowhere to land is reported rather than dropped silently.
"""
import pathlib
import sys

_scripts = pathlib.Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(_scripts))

from apply_trials_validation import Patcher  # noqa: E402

COLUMNS = [
    "nct_id",
    "treatment_name",
    "modality",
    "biomarker",
    "stage",
    "line_of_therapy",
    "previous_treatment_criteria",
    "created_at",
    "cancer_type",
]


def make_row(nct_id: str, **overrides: str) -> dict:
    row = {column: "" for column in COLUMNS}
    row["nct_id"] = nct_id
    row.update(overrides)
    return row


def candidate(
    nct_id: str = "NCT1",
    field: str = "stage",
    status: str = "FAIL",
    corrected_value: str | None = "Stage III/IV",
    decision: str = "hitl",
) -> dict:
    return {
        "cohort": "industry",
        "nct_id": nct_id,
        "decision": decision,
        "field": field,
        "status": status,
        "corrected_value": corrected_value,
        "issue": "because",
    }


def run(rows: list[dict], candidates: list[dict]) -> Patcher:
    patcher = Patcher(rows)
    for item in candidates:
        patcher.apply(item)
    return patcher


def test_corrected_value_lands_in_the_column() -> None:
    row = make_row("NCT1", stage="Stage IV")
    patcher = run([row], [candidate()])

    assert row["stage"] == "Stage III/IV"
    assert len(patcher.changes) == 1
    assert patcher.changes[0]["old"] == "Stage IV"


def test_all_four_vocabulary_fields_are_patched() -> None:
    row = make_row("NCT1")
    fields = ["biomarker", "stage", "line_of_therapy", "previous_treatment_criteria"]
    patcher = run(
        [row], [candidate(field=field, corrected_value="v") for field in fields]
    )

    assert len(patcher.changes) == 4
    assert all(row[field] == "v" for field in fields)


def test_modality_is_never_written() -> None:
    """The verdicts predate the modality backfill; replaying them would undo it."""
    row = make_row("NCT1", modality="Monoclonal Antibody")
    patcher = run([row], [candidate(field="modality", corrected_value="Vaccine")])

    assert row["modality"] == "Monoclonal Antibody"
    assert not patcher.changes
    assert "excluded field (modality)" in patcher.skips[0]["reason"]


def test_treatment_name_is_never_written() -> None:
    """A multi-arm answer has no representation in a one-row-per-trial column."""
    row = make_row("NCT1", treatment_name="Nivolumab + Ipilimumab")
    patcher = run(
        [row],
        [
            candidate(
                field="treatment_name",
                corrected_value="Nivolumab; Nivolumab + Ipilimumab",
            )
        ],
    )

    assert row["treatment_name"] == "Nivolumab + Ipilimumab"
    assert not patcher.changes


def test_pass_is_not_a_change_and_not_a_skip() -> None:
    row = make_row("NCT1", stage="Stage IV")
    patcher = run([row], [candidate(status="PASS", corrected_value=None)])

    assert row["stage"] == "Stage IV"
    assert not patcher.changes
    assert not patcher.skips


def test_fail_without_a_corrected_value_stays_hitl() -> None:
    row = make_row("NCT1", stage="Stage IV")
    patcher = run([row], [candidate(corrected_value=None)])

    assert row["stage"] == "Stage IV"
    assert not patcher.changes
    assert "stays HITL" in patcher.skips[0]["reason"]


def test_cell_already_holding_the_corrected_value_is_a_no_op() -> None:
    row = make_row("NCT1", stage="Stage III/IV")
    patcher = run([row], [candidate()])

    assert not patcher.changes
    assert "already holds" in patcher.skips[0]["reason"]


def test_correction_for_an_absent_trial_is_reported() -> None:
    patcher = run([make_row("NCT1")], [candidate(nct_id="NCT_GONE")])

    assert not patcher.changes
    assert patcher.skips[0]["reason"] == "no matching trial_landscape row"
    assert patcher.skips[0]["nct_id"] == "NCT_GONE"


def test_other_rows_and_columns_are_untouched() -> None:
    target = make_row("NCT1", stage="Stage IV", modality="Vaccine")
    bystander = make_row("NCT2", stage="Stage II")
    run([target, bystander], [candidate()])

    assert bystander == make_row("NCT2", stage="Stage II")
    assert target["modality"] == "Vaccine"
    assert target["cancer_type"] == ""
