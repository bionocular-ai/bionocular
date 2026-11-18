"""Tests for the ASH triage filter."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from ash_triage import kept_rows  # noqa: E402


def test_only_treatment_outcomes_rows_are_kept():
    rows = [{"abstract": n} for n in ("1", "2", "3")]
    triage = {"1": {"kind": "treatment_outcomes"}, "2": {"kind": "trial_in_progress"}}
    assert kept_rows(rows, triage) == [{"abstract": "1"}]
