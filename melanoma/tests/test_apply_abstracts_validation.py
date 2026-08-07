"""Tests for the abstracts validation patcher.

Covers the four behaviours that differ from the publications pass: vocabulary
translation, MOVE collision dedupe, a NULL that must not undo a MOVE, and a KEEP
on an auto-repaired ci_hr cell (which is a write, not a no-op).
"""
import pathlib
import sys

_scripts = pathlib.Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(_scripts))

from apply_abstracts_validation import (  # noqa: E402
    apply_verdicts,
    float_residue,
    resolve_column,
)
from apply_publications_validation import Patcher  # noqa: E402

COLUMNS = {
    "id",
    "source_type",
    "source_name",
    "arm_id",
    "is_nr",
    "is_lt",
    "nct_id",
    "trae_pct",
    "grade_3_plus_ae_ir_ae",
    "grade_3_plus_trae_ir_ae",
    "grade_3_plus_teae_ir_ae",
    "grade_3_plus_ae_pct",
    "ci_hr_os",
}
# The two-name bridge the real ATTRIBUTE_MAPPING provides.
BY_NORMALIZED = {
    "trae": "trae_pct",
    "grade3plusaeimmunerelated": "grade_3_plus_ae_ir_ae",
    "grade3plustraeimmunerelated": "grade_3_plus_trae_ir_ae",
    "grade3plusteaeimmunerelated": "grade_3_plus_teae_ir_ae",
    "grade3plusae": "grade_3_plus_ae_pct",
    "cihros": "ci_hr_os",
}


def make_patcher(**cells: str) -> tuple[Patcher, dict]:
    row = {column: "" for column in COLUMNS}
    row.update(
        {
            "id": "abstract_DOC_arm_1",
            "source_type": "abstract",
            "source_name": "DOC",
            "arm_id": "arm_1",
        }
    )
    row.update(cells)
    return Patcher([row], sorted(COLUMNS), source_type="abstract"), row


def verdict(**overrides: object) -> dict:
    base = {
        "doc_id": "DOC",
        "arm_id": "arm_1",
        "db_column": "trae",
        "value_in_db": "50.0",
        "verdict": "JUDGE_RIGHT_NULL",
        "target_column": None,
        "corrected_value": None,
        "confidence": "high",
        "reason": "test",
    }
    base.update(overrides)
    return base


def run(patcher: Patcher, verdicts: list[dict], auto_ci: dict | None = None) -> None:
    apply_verdicts(patcher, verdicts, COLUMNS, BY_NORMALIZED, auto_ci or {})


def test_resolve_column_translates_vocabulary() -> None:
    """Batches say 'trae'; the table says 'trae_pct'."""
    assert resolve_column("trae", COLUMNS, BY_NORMALIZED) == "trae_pct"
    assert resolve_column("ci_hr_os", COLUMNS, BY_NORMALIZED) == "ci_hr_os"


def test_resolve_column_maps_identity_fields_and_drops_homeless_ones() -> None:
    assert resolve_column("nct_number", COLUMNS, BY_NORMALIZED) == "nct_id"
    assert resolve_column("trial_name", COLUMNS, BY_NORMALIZED) == ""
    assert resolve_column("abstract_number", COLUMNS, BY_NORMALIZED) == ""


def test_null_writes_through_the_translated_column() -> None:
    patcher, row = make_patcher(trae_pct="50.0")
    run(patcher, [verdict()])
    assert row["trae_pct"] == ""


def test_move_collision_writes_once_and_empties_both_sources() -> None:
    """69 real collisions, every one same-valued: the first move-in wins."""
    patcher, row = make_patcher(
        grade_3_plus_trae_ir_ae="22.0", grade_3_plus_teae_ir_ae="22.0"
    )
    run(
        patcher,
        [
            verdict(
                db_column="grade_3_plus_trae_immune_related",
                value_in_db="22.0",
                verdict="JUDGE_RIGHT_MOVE",
                target_column="grade_3_plus_ae_immune_related",
            ),
            verdict(
                db_column="grade_3_plus_teae_immune_related",
                value_in_db="22.0",
                verdict="JUDGE_RIGHT_MOVE",
                target_column="grade_3_plus_ae_immune_related",
            ),
        ],
    )
    assert row["grade_3_plus_ae_ir_ae"] == "22.0"
    assert row["grade_3_plus_trae_ir_ae"] == ""
    assert row["grade_3_plus_teae_ir_ae"] == ""
    move_ins = [c for c in patcher.changes if c["action"] == "move-in"]
    assert len(move_ins) == 1, "collision should write the destination once"
    assert any("MOVE collision" in s["reason"] for s in patcher.skips)


def test_null_does_not_undo_a_move_into_the_same_cell() -> None:
    """ASCO_2020_10052: one verdict nulls the old value, another moves in the right one."""
    patcher, row = make_patcher(
        grade_3_plus_ae_ir_ae="70.0", grade_3_plus_ae_pct="100.0"
    )
    run(
        patcher,
        [
            verdict(
                db_column="grade_3_plus_ae_immune_related",
                value_in_db="70.0",
                verdict="JUDGE_RIGHT_NULL",
            ),
            verdict(
                db_column="grade_3_plus_ae",
                value_in_db="100.0",
                verdict="JUDGE_RIGHT_MOVE",
                target_column="grade_3_plus_ae_immune_related",
            ),
        ],
    )
    assert row["grade_3_plus_ae_ir_ae"] == "100.0"
    assert row["grade_3_plus_ae_pct"] == ""
    assert any("NULL superseded" in s["reason"] for s in patcher.skips)


def test_keep_on_an_auto_repaired_cell_writes_the_range() -> None:
    """The table still holds the bare lower bound, so KEEP is not a no-op here."""
    patcher, row = make_patcher(ci_hr_os="0.42")
    run(
        patcher,
        [verdict(db_column="ci_hr_os", verdict="JUDGE_WRONG_KEEP")],
        auto_ci={("DOC", "arm_1", "ci_hr_os"): "0.42-0.79"},
    )
    assert row["ci_hr_os"] == "0.42-0.79"
    assert [c["action"] for c in patcher.changes] == ["keep-ci-repair"]


def test_plain_keep_changes_nothing() -> None:
    patcher, row = make_patcher(trae_pct="50.0")
    run(patcher, [verdict(verdict="JUDGE_WRONG_KEEP")])
    assert row["trae_pct"] == "50.0"
    assert patcher.changes == []


def test_float_residue_cleans_noise_but_spares_real_precision() -> None:
    assert float_residue("64.80000000000001") == "64.8"
    assert float_residue("31.200000000000003") == "31.2"
    # A trailing .0 is not a defect, and a small p-value must not be rounded away.
    assert float_residue("140") is None
    assert float_residue("0.0000033") is None
    assert float_residue("NR") is None
