"""Tests for the ASH triage filter."""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from ash_triage import kept_rows, run  # noqa: E402


def test_only_treatment_outcomes_rows_are_kept():
    rows = [{"abstract": n} for n in ("1", "2", "3")]
    triage = {"1": {"kind": "treatment_outcomes"}, "2": {"kind": "trial_in_progress"}}
    assert kept_rows(rows, triage) == [{"abstract": "1"}]


def test_rerun_with_a_different_prompt_is_refused(tmp_path):
    out = tmp_path / "triage.json"
    out.write_text('{"_meta": {"fingerprint": "old"}}', encoding="utf-8")
    with pytest.raises(ValueError, match="different prompt"):
        asyncio.run(run({}, out, None, 1))  # type: ignore[arg-type]
