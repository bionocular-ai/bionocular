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

Usage:
    cd melanoma
    poetry run python3 scripts/download_clinical_trials_snapshot.py
    poetry run python3 scripts/download_clinical_trials_snapshot.py --out /tmp/snap.json
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
_PAGE_SIZE = 1000

# Columns saved: extractor inputs + deferred outcome filter + provenance.
# `interventions` is the structured CT.gov arms/interventions list; it grounds
# treatment_name / modality extraction (see snapshot_source.load_trial).
_COLUMNS = [
    "nct_id",
    "cancer_type",
    "official_title",
    "brief_title",
    "brief_summary",
    "interventions",
    "eligibility_criteria",
    "primary_outcomes",
    "secondary_outcomes",
    "lead_sponsor_class",
    "study_type",
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
    return parser


def _fetch_all(client: object) -> list[dict]:
    """Paginate the filtered clinical_trials query into a single list."""
    rows: list[dict] = []
    start = 0
    while True:
        resp = (
            client.table("clinical_trials")  # type: ignore[attr-defined]
            .select(",".join(_COLUMNS))
            .neq("lead_sponsor_class", _EXCLUDED_SPONSOR_CLASS)
            .in_("study_type", _INCLUDED_STUDY_TYPES)
            .range(start, start + _PAGE_SIZE - 1)
            .execute()
        )
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

    client = create_client(url, key)
    logger.info(
        "Fetching non-industry %s trials from clinical_trials...",
        "/".join(_INCLUDED_STUDY_TYPES),
    )
    rows = _fetch_all(client)

    null_title = sum(1 for r in rows if not r.get("official_title"))
    logger.info(
        "Fetched %d trials (%d with null official_title)", len(rows), null_title
    )

    out_path = args.out or (
        _DEFAULT_OUT_DIR / f"{date.today().isoformat()}-clinical-trials.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    snapshot = {
        "metadata": {
            "source_table": "clinical_trials",
            "fetched_at": date.today().isoformat(),
            "filters": {
                "lead_sponsor_class_ne": _EXCLUDED_SPONSOR_CLASS,
                "study_type_in": _INCLUDED_STUDY_TYPES,
            },
            "columns": _COLUMNS,
            "row_count": len(rows),
        },
        "trials": rows,
    }
    out_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    logger.info("Snapshot written to %s (%d trials)", out_path, len(rows))


if __name__ == "__main__":
    main()
