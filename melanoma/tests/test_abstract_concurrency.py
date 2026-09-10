"""Abstract extraction runs in parallel, bounded by the concurrency setting.

Vertex 429s when too many extractions are in flight, so the semaphore must
actually cap the overlap - and every finished abstract must still reach the
output file, since the writers now race for it.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from run_abstract_pipeline import _process_conference_year
from src.domain.extraction_models import ABSTRACT_ATTRIBUTES

ABSTRACT_COUNT = 6
CONCURRENCY = 2


class _Result:
    """Minimal stand-in for an extraction result."""

    arm_results: dict = {}
    total_attributes_extracted = 14
    overall_confidence = 0.34
    processing_time_ms = 1
    errors: list = []
    warnings: list = []


class _TracksOverlap:
    """Records how many extractions are in flight at once."""

    def __init__(self) -> None:
        self.in_flight = 0
        self.peak = 0

    async def extract(
        self, _text: str, _abstract_id: str, _doc_type: object
    ) -> _Result:
        self.in_flight += 1
        self.peak = max(self.peak, self.in_flight)
        try:
            await asyncio.sleep(0.01)  # yield, so overlap is observable
            return _Result()
        finally:
            self.in_flight -= 1


def _run(tmp_path: Path, concurrency: int) -> tuple[_TracksOverlap, dict]:
    abstracts_dir = tmp_path / "abstracts"
    abstracts_dir.mkdir()
    (abstracts_dir / "ASCO_2026.md").write_text(
        "".join(
            f"### Abstract ID: {9500 + i}\nBody {i}.\n" for i in range(ABSTRACT_COUNT)
        ),
        encoding="utf-8",
    )
    output_file = tmp_path / "extraction_results_ASCO_2026.json"
    service = _TracksOverlap()

    asyncio.run(
        _process_conference_year(
            conference="ASCO",
            year=2026,
            abstracts_dir=abstracts_dir,
            extraction_service=service,
            canonical_attributes=ABSTRACT_ATTRIBUTES,
            output_file=output_file,
            concurrency=concurrency,
        )
    )
    return service, json.loads(output_file.read_text(encoding="utf-8"))


def test_extractions_overlap_up_to_the_limit(tmp_path: Path) -> None:
    service, _ = _run(tmp_path, CONCURRENCY)
    assert service.peak == CONCURRENCY, f"peak overlap was {service.peak}"


def test_concurrency_one_never_overlaps(tmp_path: Path) -> None:
    service, _ = _run(tmp_path, 1)
    assert service.peak == 1


def test_every_abstract_is_written_despite_racing_writers(tmp_path: Path) -> None:
    _, payload = _run(tmp_path, CONCURRENCY)
    written = {a["abstract_id"] for a in payload["abstracts"]}
    assert written == {f"ASCO_2026_{9500 + i}" for i in range(ABSTRACT_COUNT)}
    assert payload["total_abstracts"] == ABSTRACT_COUNT
