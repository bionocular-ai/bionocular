"""Heme cancer tags for the trials ASH 2025 abstracts cite.

The skin rules in `cancer_type_derivation` cannot name a heme cancer, so the
daily sync adds these tags to the ones it derives. The file is written by
`scripts/ash_resolve.py` (<run>/trial_cancer_types.csv) and committed here.
"""

import csv
from pathlib import Path
from typing import Final

HEME_TAGS_CSV: Final[Path] = (
    Path(__file__).resolve().parents[3] / "resources" / "ash" / "trial_cancer_types.csv"
)


def load_heme_tags(path: Path = HEME_TAGS_CSV) -> dict[str, list[str]]:
    """NCT id -> its heme cancers (full names, as indications.csv spells them)."""
    with path.open(newline="", encoding="utf-8") as f:
        return {r["nct_id"]: r["cancer_types"].split(";") for r in csv.DictReader(f)}
