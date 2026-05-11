#!/usr/bin/env python3
"""Fetch Open Targets knownDrugs data for skin cancer types → trials.db.

Usage:
    poetry run python scripts/fetch_open_targets.py [--cancer-type <name>] [--dry-run]

Options:
    --cancer-type   Only fetch for this one cancer type (exact match on tag name)
    --dry-run       Fetch and print, but do not write to DB
"""
from __future__ import annotations

import argparse
import logging
import sys

from src.infrastructure.config import CLINICAL_TRIAL_DB_PATH
from src.infrastructure.open_targets_service import (
    CANCER_TYPE_EFO_MAP,
    OpenTargetsClient,
    OpenTargetsRepository,
    flatten_row,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

DELAY_BETWEEN_PAGES = 0.3  # seconds — polite, not enforced by API
BATCH_WRITE_SIZE = 200  # upsert in batches to avoid large transactions


def fetch_cancer_type(
    client: OpenTargetsClient,
    repo: OpenTargetsRepository,
    cancer_type: str,
    efo_ids: list[str],
    dry_run: bool,
) -> int:
    """Fetch all knownDrugs rows for a cancer type and store them.

    Returns:
        Total rows written (or that would be written in dry-run).
    """
    total_written = 0
    batch: list = []

    for efo_id in efo_ids:
        logger.info("  EFO ID: %s", efo_id)
        row_count = 0

        for raw_row in client.iter_known_drugs(efo_id, delay_s=DELAY_BETWEEN_PAGES):
            flat_rows = flatten_row(raw_row, cancer_type, efo_id)
            batch.extend(flat_rows)
            row_count += len(flat_rows)

            if len(batch) >= BATCH_WRITE_SIZE:
                if not dry_run:
                    written = repo.upsert_rows(batch)
                    total_written += written
                else:
                    total_written += len(batch)
                logger.info(
                    "    [%s] Wrote batch of %d (total so far: %d)",
                    cancer_type,
                    len(batch),
                    total_written,
                )
                batch.clear()

        # Flush remaining
        if batch:
            if not dry_run:
                written = repo.upsert_rows(batch)
                total_written += written
            else:
                total_written += len(batch)
            batch.clear()

        logger.info(
            "  → EFO %s done: %d flat rows processed for '%s'",
            efo_id,
            row_count,
            cancer_type,
        )

    return total_written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cancer-type",
        default=None,
        help="Only fetch this cancer type (exact tag name). Fetches all if omitted.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch data but do not write to DB.",
    )
    parser.add_argument(
        "--db-path",
        default=CLINICAL_TRIAL_DB_PATH,
        help=f"Path to trials.db (default: {CLINICAL_TRIAL_DB_PATH})",
    )
    args = parser.parse_args()

    db_path = args.db_path
    dry_run = args.dry_run

    logger.info("Database: %s", db_path)
    if dry_run:
        logger.info("DRY RUN — no data will be written")

    # Prepare DB table
    repo = OpenTargetsRepository(db_path)
    if not dry_run:
        repo.ensure_table()

    # Determine which cancer types to fetch
    if args.cancer_type:
        if args.cancer_type not in CANCER_TYPE_EFO_MAP:
            available = "\n  ".join(CANCER_TYPE_EFO_MAP.keys())
            logger.error(
                "Unknown cancer type %r. Available types:\n  %s",
                args.cancer_type,
                available,
            )
            sys.exit(1)
        to_fetch = {args.cancer_type: CANCER_TYPE_EFO_MAP[args.cancer_type]}
    else:
        to_fetch = CANCER_TYPE_EFO_MAP

    client = OpenTargetsClient()
    grand_total = 0

    logger.info("=" * 60)
    logger.info("Fetching Open Targets knownDrugs for %d cancer type(s)", len(to_fetch))
    logger.info("=" * 60)

    summary: list[tuple[str, int]] = []

    for cancer_type, efo_ids in to_fetch.items():
        logger.info("\n[%s]", cancer_type)
        try:
            n = fetch_cancer_type(client, repo, cancer_type, efo_ids, dry_run)
        except Exception as exc:
            logger.error("  FAILED for '%s': %s", cancer_type, exc)
            summary.append((cancer_type, -1))
            continue

        grand_total += n
        summary.append((cancer_type, n))
        logger.info("  Subtotal: %d rows", n)

    # Final summary
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY%s", " (dry run)" if dry_run else "")
    logger.info("=" * 60)
    for cancer_type, n in summary:
        status_str = "ERROR" if n < 0 else f"{n:,} rows"
        logger.info("  %-50s %s", cancer_type, status_str)
    logger.info("  %-50s %s", "TOTAL", f"{grand_total:,} rows")

    if not dry_run:
        counts = repo.count_by_cancer_type()
        logger.info("\nDB row counts after fetch:")
        for ct, cnt in counts.items():
            logger.info("  %-50s %d", ct, cnt)


if __name__ == "__main__":
    main()
