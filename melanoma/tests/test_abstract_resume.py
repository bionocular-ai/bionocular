"""Resume must retry partial abstracts without deleting them first.

A partial record (one whose family extraction 429'd) is reprocessed on the next
run. If the retry also fails, the partial content we already had must still be
on disk - dropping it from the in-memory list deletes it at the first
incremental save, which is how ASCO_2026 abstracts 9511/9545/9556 were lost.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from run_abstract_pipeline import _process_conference_year
from src.domain.extraction_models import ABSTRACT_ATTRIBUTES

PARTIAL = {
    "abstract_id": "ASCO_2026_9511",
    "total_arms": 1,
    "total_attributes_extracted": 7,
    "overall_confidence": 0.32,
    "processing_time_ms": 1,
    "errors": ["family_extraction_failed: efs_rfs_mfs"],
    "warnings": [],
    "arm_results": {"arm_1": {"arm_name": "pembrolizumab"}},
}


class _Result:
    """Minimal stand-in for an extraction result."""

    arm_results: dict = {}
    total_attributes_extracted = 14
    overall_confidence = 0.34
    processing_time_ms = 1
    errors: list = []
    warnings: list = []


class _FailingOnPartial:
    """Succeeds for the new abstract, fails for the one being retried."""

    async def extract(self, _text: str, abstract_id: str, _doc_type: object) -> _Result:
        if abstract_id == "ASCO_2026_9511":
            raise RuntimeError("429 RESOURCE_EXHAUSTED")
        return _Result()


def _run(tmp_path: Path) -> dict:
    abstracts_dir = tmp_path / "abstracts"
    abstracts_dir.mkdir()
    (abstracts_dir / "ASCO_2026.md").write_text(
        "### Abstract ID: 9511\nPartial abstract body.\n"
        "### Abstract ID: 9501\nFresh abstract body.\n",
        encoding="utf-8",
    )
    output_file = tmp_path / "extraction_results_ASCO_2026.json"
    output_file.write_text(
        json.dumps({"conference": "ASCO", "year": 2026, "abstracts": [PARTIAL]}),
        encoding="utf-8",
    )

    asyncio.run(
        _process_conference_year(
            conference="ASCO",
            year=2026,
            abstracts_dir=abstracts_dir,
            extraction_service=_FailingOnPartial(),
            canonical_attributes=ABSTRACT_ATTRIBUTES,
            output_file=output_file,
        )
    )
    return json.loads(output_file.read_text(encoding="utf-8"))


def test_failed_retry_keeps_the_existing_partial(tmp_path: Path) -> None:
    """The partial survives a failed retry, even once a later save has run."""
    written = {a["abstract_id"]: a for a in _run(tmp_path)["abstracts"]}
    assert "ASCO_2026_9511" in written, "partial was deleted by a failed retry"
    assert written["ASCO_2026_9511"]["total_attributes_extracted"] == 7
    assert written["ASCO_2026_9501"]["total_attributes_extracted"] == 14


def test_partial_is_actually_retried_not_skipped(tmp_path: Path) -> None:
    """Keeping the partial must not make resume treat it as already done."""
    attempted: list[str] = []

    class _Recording(_FailingOnPartial):
        async def extract(
            self, text: str, abstract_id: str, doc_type: object
        ) -> _Result:
            attempted.append(abstract_id)
            return await super().extract(text, abstract_id, doc_type)

    abstracts_dir = tmp_path / "abstracts"
    abstracts_dir.mkdir()
    (abstracts_dir / "ASCO_2026.md").write_text(
        "### Abstract ID: 9511\nPartial abstract body.\n", encoding="utf-8"
    )
    output_file = tmp_path / "extraction_results_ASCO_2026.json"
    output_file.write_text(
        json.dumps({"conference": "ASCO", "year": 2026, "abstracts": [PARTIAL]}),
        encoding="utf-8",
    )
    asyncio.run(
        _process_conference_year(
            conference="ASCO",
            year=2026,
            abstracts_dir=abstracts_dir,
            extraction_service=_Recording(),
            canonical_attributes=ABSTRACT_ATTRIBUTES,
            output_file=output_file,
        )
    )
    assert attempted == ["ASCO_2026_9511"]
