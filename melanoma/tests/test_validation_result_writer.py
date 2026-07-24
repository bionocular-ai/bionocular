"""Tests for ValidationResultWriter persistence, including cost reporting."""

import json
from pathlib import Path

from src.app.trials_validation_service import ValidationResultWriter
from src.infrastructure.cost_calculator import CostCalculator


def test_write_cost_report_persists_summary(tmp_path: Path) -> None:
    """write_cost_report writes cost_report.json with the calculator's totals.

    Mirrors the extraction pipeline so a validation run leaves a standalone
    cost artifact (and a mid-run kill preserves spend recorded so far).
    """
    writer = ValidationResultWriter(tmp_path)
    calc = CostCalculator()
    calc.record_api_call(
        prompt_tokens=1000,
        completion_tokens=200,
        model="gemini-3.1-pro-preview",
        operation="trial_validation",
        attribute_type="trial_validation",
    )

    path = writer.write_cost_report(calc)

    assert path == tmp_path / "cost_report.json"
    report = json.loads(path.read_text())
    assert report["summary"]["total_requests"] == 1
    assert report["summary"]["total_tokens"] == 1200
    assert report["summary"]["total_cost"] > 0
