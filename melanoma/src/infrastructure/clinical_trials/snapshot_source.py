"""Supabase-snapshot input source for the trial parameter extraction pipeline.

Replaces the file/SQLite input seams (`TrialLoader`, `CancerTypeRepository`,
export-file discovery) with a single source backed by a local JSON snapshot
produced by ``scripts/download_clinical_trials_snapshot.py``. Pure over the
snapshot dict — no network access.
"""
from __future__ import annotations

import logging

from ...domain.trial_parameter_models import TrialText

logger = logging.getLogger(__name__)

# Intervention entries that are never the trial's treatment. Comparators are NOT
# filtered here (the extractor needs to see them to tell investigational from
# comparator); only clearly non-treatment entries are dropped.
_SKIP_INTERVENTION_TYPES = {"DIAGNOSTIC_TEST"}
_SKIP_NAME_MARKERS = ("placebo", "best supportive care", "sham")


def _render_interventions(interventions: list[dict]) -> str:
    """Render the CT.gov interventions list as `type - name - description` lines.

    Returns an empty string when nothing survives filtering, so callers can omit
    the section entirely for trials without usable interventions.
    """
    lines: list[str] = []
    for item in interventions:
        name = (item.get("name") or "").strip()
        if not name:
            continue
        itype = (item.get("type") or "").strip()
        if itype.upper() in _SKIP_INTERVENTION_TYPES:
            continue
        if any(marker in name.lower() for marker in _SKIP_NAME_MARKERS):
            continue
        description = (item.get("description") or "").strip()
        parts = [p for p in (itype, name) if p]
        line = " - ".join(parts)
        if description:
            line = f"{line} - {description}"
        lines.append(f"- {line}")
    return "\n".join(lines)


class SnapshotTrialSource:
    """Serves candidate NCTs, cancer types, and trial text from a snapshot.

    The snapshot is the object written by the download script:
    ``{"metadata": {...}, "trials": [{"nct_id": ..., "cancer_type": [...], ...}]}``.
    """

    def __init__(self, snapshot: dict) -> None:
        self._by_nct: dict[str, dict] = {
            row["nct_id"]: row for row in snapshot.get("trials", [])
        }
        logger.info("SnapshotTrialSource loaded | %d trials", len(self._by_nct))

    def get_all_nct_numbers(
        self, cancer_type_filter: list[str] | None = None
    ) -> list[str]:
        """Return sorted NCT numbers, optionally restricted by cancer type."""
        if not cancer_type_filter:
            return sorted(self._by_nct)
        wanted = set(cancer_type_filter)
        return sorted(
            nct
            for nct, row in self._by_nct.items()
            if wanted.intersection(row.get("cancer_type") or [])
        )

    def get_cancer_types(self, nct_number: str) -> list[str]:
        """Return the cancer_type tags for a trial (empty list if unknown)."""
        row = self._by_nct.get(nct_number)
        if row is None:
            return []
        return list(row.get("cancer_type") or [])

    def load_trial(self, nct_number: str) -> TrialText:
        """Build a TrialText, composing full_text in the March export layout.

        Raises:
            KeyError: if the NCT is absent from the snapshot.
        """
        row = self._by_nct[nct_number]
        official_title = row.get("official_title") or row.get("brief_title") or ""
        brief_summary = row.get("brief_summary") or ""
        eligibility = row.get("eligibility_criteria") or ""
        interventions_text = _render_interventions(row.get("interventions") or [])

        interventions_block = (
            f"interventions:\n{interventions_text}\n\n" if interventions_text else ""
        )
        full_text = (
            f"NCT Number: {nct_number}\n\n"
            f"officialTitle:\n{official_title}\n\n"
            f"briefSummary:\n{brief_summary}\n\n"
            f"{interventions_block}"
            f"eligibilityCriteria:\n{eligibility}\n"
        )
        return TrialText(
            nct_number=nct_number,
            official_title=official_title,
            brief_summary=brief_summary,
            full_text=full_text,
        )
