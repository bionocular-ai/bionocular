"""Tests for ResultWriter persistence semantics."""

import json
from datetime import datetime
from pathlib import Path

from src.app.trials_parameter_extraction_service import ResultWriter
from src.domain.trial_parameter_models import (
    ExtractionRunSummary,
    ExtractionStatus,
    TrialParameterResult,
)


def _result(nct: str, treatment: str | None = "Nivolumab") -> TrialParameterResult:
    return TrialParameterResult(
        nct_number=nct,
        treatment_name=treatment,
        extraction_status=ExtractionStatus.DONE,
    )


def _summary() -> ExtractionRunSummary:
    return ExtractionRunSummary(
        model="gemini-3.1-pro-preview", run_date=datetime(2026, 7, 17)
    )


def _trials_on_disk(path: Path) -> list[dict]:
    return json.loads(path.read_text())["trials"]


def test_write_results_preserves_trials_from_earlier_runs(tmp_path: Path) -> None:
    """A resumed run that processes one trial must not drop the other trials.

    Reproduces the resume clobber: run() only accumulates newly-processed
    trials, so a resumed run passes a short list to write_results. Without
    merge semantics that truncates results.json to just the new trial.
    """
    writer = ResultWriter(tmp_path)
    writer.write_results([_result("NCT001"), _result("NCT002")], _summary())

    # Simulate a resumed run: NCT001/NCT002 skipped, only NCT003 processed.
    writer.write_results([_result("NCT003")], _summary())

    ncts = {t["nct_number"] for t in _trials_on_disk(tmp_path / "results.json")}
    assert ncts == {"NCT001", "NCT002", "NCT003"}


def test_write_results_updates_a_retried_trial_in_place(tmp_path: Path) -> None:
    """Re-processing an existing trial replaces its row rather than duplicating."""
    writer = ResultWriter(tmp_path)
    writer.write_results([_result("NCT001", treatment=None)], _summary())

    writer.write_results([_result("NCT001", treatment="Pembrolizumab")], _summary())

    trials = _trials_on_disk(tmp_path / "results.json")
    assert len(trials) == 1
    assert trials[0]["treatment_name"] == "Pembrolizumab"


def test_write_results_metadata_counts_describe_the_whole_file(tmp_path: Path) -> None:
    """Status counts must describe every trial on disk, not just this run's."""
    writer = ResultWriter(tmp_path)
    writer.write_results([_result("NCT001"), _result("NCT002")], _summary())

    writer.write_results([_result("NCT003")], _summary())

    metadata = json.loads((tmp_path / "results.json").read_text())["metadata"]
    assert metadata["successful"] == 3
