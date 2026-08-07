"""Which trials may enter the trial_landscape table.

trial_landscape records what treatment a trial gave, at which line, to whom. An
OBSERVATIONAL study assigns no treatment, so it has no landscape to describe, and 150
such rows had to be deleted from the live table on 2026-08-07 because the uploaders
never checked. This module is the check.

Pure by design: callers resolve study_type from wherever they already have a Supabase
client and pass the mapping in, so the rule stays testable without a database.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from src.domain.constants import TrialLandscape


def partition_by_study_type(
    records: Sequence[Mapping[str, Any]],
    study_types: Mapping[str, str],
) -> tuple[list[Mapping[str, Any]], list[tuple[str, str]]]:
    """Split records into (uploadable, rejected).

    A record is uploadable only when its trial's study_type is one this table accepts.
    A trial absent from `study_types` is rejected rather than assumed acceptable: the
    landscape row references clinical_trials, so a trial that table does not hold has
    no business here either.

    Returns the rejected entries as (nct_id, reason) so the caller can report them.
    """
    uploadable: list[Mapping[str, Any]] = []
    rejected: list[tuple[str, str]] = []
    for record in records:
        nct_id = record["nct_id"]
        study_type = study_types.get(nct_id)
        if study_type is None:
            rejected.append((nct_id, "not in clinical_trials"))
        elif study_type not in TrialLandscape.INCLUDED_STUDY_TYPES:
            rejected.append((nct_id, study_type))
        else:
            uploadable.append(record)
    return uploadable, rejected
