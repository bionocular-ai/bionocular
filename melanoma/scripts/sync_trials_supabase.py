#!/usr/bin/env python3
"""Daily sync of ClinicalTrials.gov data into Supabase.

Fetches new + updated trials for the eight skin-cancer types defined in
`cancer_type_mapping.SKIN_CANCER_TYPES` and upserts them into the Supabase
`clinical_trials_cache` (raw JSON) and `clinical_trials` (parsed) tables.

Incremental strategy: a `query.term=AREA[LastUpdatePostDate]RANGE[cutoff,MAX]`
filter on the v2 API returns trials updated since `cutoff` (default: today - 2
days). Idempotent — re-running the same window is a no-op via PK upsert.

Usage:
    poetry run python3 scripts/sync_trials_supabase.py [--days N] [--full]
                                                       [--cancer-type X]
                                                       [--dry-run]
"""

import argparse
import logging
import os
import pathlib
import sys
from datetime import date, timedelta
from typing import Optional

from dotenv import load_dotenv
from supabase import Client, create_client

# Allow `from src...` imports when running from the melanoma/ root.
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from src.infrastructure.clinical_trials.api_client import (  # noqa: E402
    ClinicalTrialsGovAPIClient,
)
from src.infrastructure.clinical_trials.cancer_type_mapping import (  # noqa: E402
    CANCER_TYPE_MAPPING,
    SKIN_CANCER_TYPES,
)
from src.infrastructure.clinical_trials.supabase_parser import (  # noqa: E402
    extract_processed_trial,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("sync_trials_supabase")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--days",
        type=int,
        default=2,
        help="Lookback window in days for LastUpdatePostDate filter (default: 2)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Skip date filter; fetch every trial for every cancer type (backfill)",
    )
    parser.add_argument(
        "--cancer-type",
        type=str,
        default=None,
        help="Restrict to a single canonical cancer type (debug)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch + parse but do not write to Supabase",
    )
    return parser.parse_args()


def discover_ncts(
    api: ClinicalTrialsGovAPIClient,
    cancer_types: list[str],
    cutoff: Optional[date],
) -> dict[str, list[str]]:
    """Search ClinicalTrials.gov for each (cancer_type, search_term) and build
    a map of NCT id -> list of cancer types it belongs to (deduped).
    """
    nct_to_cancer_types: dict[str, list[str]] = {}
    for cancer_type in cancer_types:
        terms = CANCER_TYPE_MAPPING.get(cancer_type, [cancer_type])
        for term in terms:
            try:
                ncts = api.search_trials_by_condition(term, last_update_after=cutoff)
            except Exception as exc:  # noqa: BLE001 -- per-term failure is recoverable
                logger.error(
                    "Search failed for cancer_type=%r term=%r: %s",
                    cancer_type,
                    term,
                    exc,
                )
                continue

            logger.info(
                "Discovered %d NCTs for cancer_type=%r term=%r%s",
                len(ncts),
                cancer_type,
                term,
                f" (updated since {cutoff})" if cutoff else "",
            )
            for nct in ncts:
                tags = nct_to_cancer_types.setdefault(nct, [])
                if cancer_type not in tags:
                    tags.append(cancer_type)
    return nct_to_cancer_types


def sync_one(
    nct: str,
    cancer_types_map: dict[str, list[str]],
    api: ClinicalTrialsGovAPIClient,
    supabase: Optional[Client],
    dry_run: bool,
) -> str:
    """Fetch + upsert a single trial. Returns 'fetched', 'skipped', or 'error'."""
    raw = api.fetch_trial_data(nct)
    if raw is None:
        logger.warning("Skipping %s: fetch returned None", nct)
        return "skipped"

    parsed = extract_processed_trial(raw, nct, cancer_types_map)

    if dry_run or supabase is None:
        return "fetched"

    try:
        supabase.table("clinical_trials_cache").upsert(
            {"nct_id": nct, "api_response_json": raw}
        ).execute()
    except Exception as exc:  # noqa: BLE001 -- per-row failure must not abort run
        logger.error("Cache upsert failed for %s: %s", nct, exc)
        return "error"

    try:
        supabase.table("clinical_trials").upsert(parsed).execute()
    except Exception as exc:  # noqa: BLE001 -- per-row failure must not abort run
        logger.error("clinical_trials upsert failed for %s: %s", nct, exc)
        return "error"

    return "fetched"


def main() -> int:
    args = parse_args()
    load_dotenv()

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not args.dry_run and (not url or not key):
        logger.error("SUPABASE_URL and SUPABASE_KEY must be set (or use --dry-run)")
        return 2

    supabase: Optional[Client] = (
        create_client(url, key) if (url and key and not args.dry_run) else None
    )

    if args.cancer_type:
        if args.cancer_type not in SKIN_CANCER_TYPES:
            logger.error(
                "Unknown --cancer-type %r. Valid values: %s",
                args.cancer_type,
                SKIN_CANCER_TYPES,
            )
            return 2
        cancer_types = [args.cancer_type]
    else:
        cancer_types = list(SKIN_CANCER_TYPES)

    cutoff: Optional[date] = (
        None if args.full else date.today() - timedelta(days=args.days)
    )

    logger.info(
        "Sync starting: cancer_types=%d, cutoff=%s, dry_run=%s",
        len(cancer_types),
        cutoff if cutoff else "FULL",
        args.dry_run,
    )

    api = ClinicalTrialsGovAPIClient()

    nct_to_cancer_types = discover_ncts(api, cancer_types, cutoff)
    total = len(nct_to_cancer_types)
    logger.info(
        "Discovered %d unique NCTs across %d cancer types", total, len(cancer_types)
    )

    counts = {"fetched": 0, "skipped": 0, "error": 0}
    for idx, nct in enumerate(nct_to_cancer_types, start=1):
        result = sync_one(nct, nct_to_cancer_types, api, supabase, args.dry_run)
        counts[result] += 1
        if idx % 50 == 0 or idx == total:
            logger.info("Progress: %d/%d (%s)", idx, total, counts)

    logger.info("Sync complete: %s", counts)
    return 0 if counts["error"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
