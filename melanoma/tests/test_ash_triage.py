"""Tests for the ASH triage filter."""

import asyncio
import sys
from pathlib import Path
from typing import get_args

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from ash_triage import PROMPT, Triage, kept_rows, run  # noqa: E402


def test_only_treatment_outcomes_rows_are_kept():
    rows = [{"abstract": n} for n in ("1", "2", "3")]
    triage = {"1": {"kind": "treatment_outcomes"}, "2": {"kind": "preclinical"}}
    assert kept_rows(rows, triage) == [{"abstract": "1"}]


def test_rerun_with_a_different_prompt_is_refused(tmp_path):
    out = tmp_path / "triage.json"
    out.write_text('{"_meta": {"fingerprint": "old"}}', encoding="utf-8")
    with pytest.raises(ValueError, match="different prompt"):
        asyncio.run(run({}, out, None, 1))  # type: ignore[arg-type]


def test_animal_and_lab_results_are_preclinical():
    assert "preclinical" in get_args(Triage.model_fields["kind"].annotation)
    assert "results only in animal models, cell lines" in PROMPT
