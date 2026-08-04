"""Bounded-concurrency behaviour of the extraction run loop.

The 1771-trial run took 7 hours sequentially. The loop now extracts up to
`concurrency` trials in parallel, so these tests pin the two properties that
make that safe: the semaphore is respected, and every trial still lands in
results.json and the checkpoint exactly once.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from src.app.trials_parameter_extraction_service import (
    CancerTypeRepository,
    CheckpointManager,
    ExtractionConfig,
    ResultWriter,
    TrialLoader,
    TrialParameterExtractionService,
    TrialParameterExtractor,
)
from src.infrastructure.clinical_trials.snapshot_source import SnapshotTrialSource
from src.infrastructure.cost_calculator import CostCalculator

_TRIAL_COUNT = 12


def _snapshot() -> dict[str, Any]:
    return {
        "metadata": {"columns": []},
        "trials": [
            {
                "nct_id": f"NCT{i:08d}",
                "cancer_type": ["Cutaneous Melanoma"],
                "official_title": f"Trial {i}",
                "brief_title": f"Trial {i}",
                "brief_summary": "Radiotherapy study.",
                "eligibility_criteria": "Inclusion: adults.",
                "interventions": [
                    {"type": "RADIATION", "name": "External beam", "description": ""}
                ],
            }
            for i in range(1, _TRIAL_COUNT + 1)
        ],
    }


class _TrackingLLM:
    """Sleeps briefly per call and records the peak number of in-flight calls."""

    def __init__(self) -> None:
        self.in_flight = 0
        self.peak_in_flight = 0
        self.calls = 0

    async def extract_json(
        self,
        prompt: str,
        operation: str = "extraction",
        attribute_type: str | None = None,
        max_retries: int = 1,
    ) -> dict[str, Any]:
        self.in_flight += 1
        self.calls += 1
        self.peak_in_flight = max(self.peak_in_flight, self.in_flight)
        try:
            await asyncio.sleep(0.01)
            return {"treatment_name": "External beam", "modality": ["Radiotherapy"]}
        finally:
            self.in_flight -= 1


def _service(
    tmp_path: Path, llm: _TrackingLLM, concurrency: int
) -> TrialParameterExtractionService:
    config = ExtractionConfig(
        trials_db_path=tmp_path / "trials.db",
        exports_dir=tmp_path / "exports",
        output_dir=tmp_path / "out",
        limit=None,
        modality_only=True,
        concurrency=concurrency,
    )
    return TrialParameterExtractionService(
        config=config,
        llm=llm,  # type: ignore[arg-type]
        loader=TrialLoader(),
        cancer_repo=CancerTypeRepository(config.trials_db_path),
        extractor=TrialParameterExtractor(llm, modality_only=True),  # type: ignore[arg-type]
        checkpoint=CheckpointManager(config.output_dir / "checkpoint.json"),
        writer=ResultWriter(config.output_dir),
        cost_calculator=CostCalculator(),
        snapshot_source=SnapshotTrialSource(_snapshot()),
    )


@pytest.mark.asyncio
async def test_run_respects_the_concurrency_ceiling(tmp_path: Path) -> None:
    llm = _TrackingLLM()
    results = await _service(tmp_path, llm, concurrency=4).run()

    assert llm.calls == _TRIAL_COUNT
    assert len(results) == _TRIAL_COUNT
    assert llm.peak_in_flight <= 4
    # Without the semaphore this would be 1; assert work really did overlap.
    assert llm.peak_in_flight > 1


@pytest.mark.asyncio
async def test_concurrency_one_is_sequential(tmp_path: Path) -> None:
    llm = _TrackingLLM()
    await _service(tmp_path, llm, concurrency=1).run()

    assert llm.peak_in_flight == 1


@pytest.mark.asyncio
async def test_every_trial_is_checkpointed_and_written_once(tmp_path: Path) -> None:
    """Concurrent writers share results.json and checkpoint.json under a lock."""
    llm = _TrackingLLM()
    service = _service(tmp_path, llm, concurrency=8)
    results = await service.run()

    ncts = [r.nct_number for r in results]
    assert sorted(ncts) == sorted({r.nct_number for r in results})

    import json

    written = json.loads((tmp_path / "out" / "results.json").read_text())
    assert len(written["trials"]) == _TRIAL_COUNT
    assert written["metadata"]["successful"] == _TRIAL_COUNT

    checkpoint = json.loads((tmp_path / "out" / "checkpoint.json").read_text())
    assert len(checkpoint) == _TRIAL_COUNT
    assert all(entry["status"] == "done" for entry in checkpoint.values())


@pytest.mark.asyncio
async def test_resume_skips_checkpointed_trials(tmp_path: Path) -> None:
    llm = _TrackingLLM()
    await _service(tmp_path, llm, concurrency=8).run()

    second = _TrackingLLM()
    results = await _service(tmp_path, second, concurrency=8).run()

    assert second.calls == 0
    assert results == []
