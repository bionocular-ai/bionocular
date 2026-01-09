#!/usr/bin/env python3
"""Sync clinical trials data from ClinicalTrials.gov for dashboard.

This script:
1. Searches for trials by cancer type and status
2. Updates the discovery database
3. Fetches and caches full trial data
4. Generates JSON output for dashboard
"""

import json
import logging
import sys
from pathlib import Path

# Add src to path - need to add parent directory to make relative imports work
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(project_root))

# Import with proper path structure (using absolute imports from src)
from src.infrastructure.clinical_trials.cancer_type_mapping import (
    ACTIVE_STATUSES,
    SKIN_CANCER_TYPES,
)
from src.infrastructure.clinical_trials.factory import create_clinical_trials_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for sync script."""
    logger.info("Starting dashboard data sync...")

    # Initialize service
    service = create_clinical_trials_service()
    repository = service.repository

    # Define target cancer types (8 types as specified)
    cancer_types = SKIN_CANCER_TYPES

    # Note: We fetch ALL trials for each cancer type (no status filter)
    # The status filter is only used for bubble sizing on the dashboard
    logger.info(f"Syncing {len(cancer_types)} cancer types (all statuses)")
    logger.info(f"Status filter {ACTIVE_STATUSES} will be used for bubble sizing only")

    # Sync each cancer type - fetch ALL trials regardless of status
    sync_results = []
    for cancer_type in cancer_types:
        logger.info(f"\n{'='*60}")
        logger.info(f"Syncing: {cancer_type}")
        logger.info(f"{'='*60}")

        try:
            # Pass None to fetch all trials, not just active ones
            result = service.sync_cancer_type_universe(cancer_type, status_list=None)
            sync_results.append(result)
            logger.info(
                f"✓ {cancer_type}: {result['new_trials']} new, "
                f"{result['total_found']} total, {result['cached']} cached"
            )
        except Exception as e:
            logger.error(f"✗ Error syncing {cancer_type}: {e}", exc_info=True)
            sync_results.append(
                {
                    "cancer_type": cancer_type,
                    "new_trials": 0,
                    "total_found": 0,
                    "cached": 0,
                    "error": str(e),
                }
            )

    # Get landscape statistics for bubbles
    logger.info("\n" + "=" * 60)
    logger.info("Generating landscape statistics...")
    landscape_stats = repository.get_landscape_stats()

    # Generate disease landscape stats (status, phase, funder_type) for each cancer type
    logger.info("Generating disease landscape statistics...")
    disease_landscape_stats = {}

    for cancer_type in cancer_types:
        logger.info(f"Computing stats for: {cancer_type}")
        try:
            stats = repository.get_disease_landscape_stats(cancer_type)
            disease_landscape_stats[cancer_type] = stats
        except Exception as e:
            logger.error(f"Error computing stats for {cancer_type}: {e}")
            disease_landscape_stats[cancer_type] = {
                "status": {},
                "phase": {},
                "funder_type": {"Industry": 0, "Non-Industry": 0},
                "extracted_count": 0,
            }

    # Save disease landscape stats to JSON file
    deployed_dir = Path(__file__).parent.parent / "data" / "deployed"
    deployed_dir.mkdir(parents=True, exist_ok=True)
    disease_landscape_file = deployed_dir / "disease_landscape_stats.json"

    with open(disease_landscape_file, "w") as f:
        json.dump(disease_landscape_stats, f, indent=2, default=str)

    logger.info(f"\n✓ Disease landscape stats saved to: {disease_landscape_file}")
    logger.info(f"  - Landscape (Bubbles): {len(landscape_stats)} cancer types")

    # Note: Dashboard data (bubbles and therapeutic index) is served directly from SQLite
    # via API endpoints, so no JSON file is needed

    # Print summary
    print("\n" + "=" * 60)
    print("SYNC SUMMARY")
    print("=" * 60)
    for result in sync_results:
        if "error" in result:
            print(f"✗ {result['cancer_type']}: ERROR - {result['error']}")
        else:
            print(
                f"✓ {result['cancer_type']}: "
                f"{result['new_trials']} new, {result['total_found']} total"
            )

    print("\n" + "=" * 60)
    print("LANDSCAPE STATISTICS")
    print("=" * 60)
    for stat in landscape_stats:
        print(
            f"{stat['cancer_type']}: "
            f"{stat['bubble_size']} active trials, "
            f"{stat['extracted_count']}/{stat['total_api_count']} extracted"
        )

    logger.info("\n✓ Sync complete!")


if __name__ == "__main__":
    main()
