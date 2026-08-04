#!/usr/bin/env python3
"""Download a local snapshot of non-industry skin-cancer trials from Supabase.

Fetches rows from the `clinical_trials` table with the structural filters that
feed the parameter extraction pipeline applied at query time:

    lead_sponsor_class != 'INDUSTRY'
    study_type IN ('INTERVENTIONAL', 'EXPANDED_ACCESS')

and writes them to
`data/output/trials_extraction_nonindustry/<YYYY-MM-DD>-clinical-trials.json`.
The snapshot is a frozen reproducibility anchor: the extraction pipeline reads it
via `--snapshot` instead of hitting Supabase per run, and outcome-measure
filtering happens locally against this file afterwards. It is co-located with the
run's results.json / checkpoint.json so everything for this cohort lives together.

The INDUSTRY cohort (`--sponsor-class INDUSTRY`) inverts the sponsor filter to
`lead_sponsor_class == 'INDUSTRY'` and defaults its output to
`data/output/trials_extraction_industry/`. Pass `--exclude-interventions` when
auditing an extraction that predates interventions grounding so the judge grades
against the same source text the extractor saw.

Usage:
    cd melanoma
    poetry run python3 scripts/download_clinical_trials_snapshot.py
    poetry run python3 scripts/download_clinical_trials_snapshot.py --out /tmp/snap.json
    poetry run python3 scripts/download_clinical_trials_snapshot.py \
        --sponsor-class INDUSTRY --exclude-interventions
"""

import argparse
import json
import logging
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

_MELANOMA_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_OUT_DIR = _MELANOMA_ROOT / "data" / "output" / "trials_extraction_nonindustry"
_DEFAULT_OUT_DIR_INDUSTRY = (
    _MELANOMA_ROOT / "data" / "output" / "trials_extraction_industry"
)
_PAGE_SIZE = 1000

# Columns saved: extractor inputs + deferred outcome filter + provenance.
# `interventions` is the structured CT.gov arms/interventions list; it grounds
# treatment_name / modality extraction (see snapshot_source.load_trial).
# `arm_groups` and `detailed_description` carry mechanism prose the title and
# summary omit; `primary_purpose` separates treatment trials from diagnostic,
# screening and supportive-care ones, which have no modality to assign.
_COLUMNS = [
    "nct_id",
    "cancer_type",
    "official_title",
    "brief_title",
    "brief_summary",
    "detailed_description",
    "interventions",
    "arm_groups",
    "eligibility_criteria",
    "primary_outcomes",
    "secondary_outcomes",
    "lead_sponsor_class",
    "study_type",
    "primary_purpose",
]

_EXCLUDED_SPONSOR_CLASS = "INDUSTRY"
_INCLUDED_STUDY_TYPES = ["INTERVENTIONAL", "EXPANDED_ACCESS"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="download_clinical_trials_snapshot",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        metavar="PATH",
        help="Output file (default: data/snapshots/<date>-clinical-trials.json).",
    )
    parser.add_argument(
        "--sponsor-class",
        choices=["NON_INDUSTRY", "INDUSTRY"],
        default="NON_INDUSTRY",
        help="Which cohort to fetch: NON_INDUSTRY (lead_sponsor_class != INDUSTRY, "
        "the default) or INDUSTRY (lead_sponsor_class == INDUSTRY).",
    )
    parser.add_argument(
        "--exclude-interventions",
        action="store_true",
        help="Drop the interventions column from the snapshot. Use when auditing an "
        "extraction run that predates interventions grounding, so the judge grades "
        "against the same source text the extractor actually saw.",
    )
    parser.add_argument(
        "--all-study-types",
        action="store_true",
        help="Skip the study_type filter and fetch every study type (including "
        "OBSERVATIONAL). Use when auditing an extraction whose cohort was not "
        "restricted to interventional/expanded-access trials.",
    )
    return parser


def _fetch_all(
    client: object, columns: list[str], industry: bool, all_study_types: bool
) -> list[dict]:
    """Paginate the filtered clinical_trials query into a single list."""
    rows: list[dict] = []
    start = 0
    while True:
        query = client.table("clinical_trials").select(  # type: ignore[attr-defined]
            ",".join(columns)
        )
        query = (
            query.eq("lead_sponsor_class", _EXCLUDED_SPONSOR_CLASS)
            if industry
            else query.neq("lead_sponsor_class", _EXCLUDED_SPONSOR_CLASS)
        )
        if not all_study_types:
            query = query.in_("study_type", _INCLUDED_STUDY_TYPES)
        resp = query.range(start, start + _PAGE_SIZE - 1).execute()
        page = resp.data
        if not page:
            break
        rows.extend(page)
        start += _PAGE_SIZE
        if len(page) < _PAGE_SIZE:
            break
    return rows


def main() -> None:
    args = _build_parser().parse_args()
    load_dotenv(_MELANOMA_ROOT / ".env")

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        print(
            "ERROR: SUPABASE_URL and SUPABASE_KEY must be set in melanoma/.env.",
            file=sys.stderr,
        )
        sys.exit(1)

    industry = args.sponsor_class == "INDUSTRY"
    drop_interventions = args.exclude_interventions
    columns = [c for c in _COLUMNS if not (drop_interventions and c == "interventions")]

    client = create_client(url, key)
    logger.info(
        "Fetching %s %s trials from clinical_trials...",
        args.sponsor_class.lower().replace("_", "-"),
        "all-study-type" if args.all_study_types else "/".join(_INCLUDED_STUDY_TYPES),
    )
    rows = _fetch_all(client, columns, industry, args.all_study_types)

    null_title = sum(1 for r in rows if not r.get("official_title"))
    logger.info(
        "Fetched %d trials (%d with null official_title)", len(rows), null_title
    )

    default_dir = _DEFAULT_OUT_DIR_INDUSTRY if industry else _DEFAULT_OUT_DIR
    out_path = args.out or (
        default_dir / f"{date.today().isoformat()}-clinical-trials.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    sponsor_filter = (
        {"lead_sponsor_class_eq": _EXCLUDED_SPONSOR_CLASS}
        if industry
        else {"lead_sponsor_class_ne": _EXCLUDED_SPONSOR_CLASS}
    )
    snapshot = {
        "metadata": {
            "source_table": "clinical_trials",
            "fetched_at": date.today().isoformat(),
            "filters": {
                **sponsor_filter,
                "study_type_in": (
                    "ALL" if args.all_study_types else _INCLUDED_STUDY_TYPES
                ),
            },
            "columns": columns,
            "row_count": len(rows),
        },
        "trials": rows,
    }
    out_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    logger.info("Snapshot written to %s (%d trials)", out_path, len(rows))


if __name__ == "__main__":
    main()
