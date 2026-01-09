#!/usr/bin/env python3
"""Test script to generate disease landscape stats JSON from existing database.

This script generates the JSON file WITHOUT calling the ClinicalTrials API.
It only reads from existing SQLite database data.
"""

import json
import logging
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.infrastructure.clinical_trials.cancer_type_mapping import SKIN_CANCER_TYPES
from src.infrastructure.clinical_trials.factory import create_clinical_trials_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Generate disease landscape stats JSON from existing database."""
    logger.info("Generating disease landscape stats JSON from existing database...")
    logger.info("(No API calls will be made)")

    # Initialize service
    service = create_clinical_trials_service()
    repository = service.repository

    # Define target cancer types
    cancer_types = SKIN_CANCER_TYPES

    # Generate disease landscape stats for each cancer type
    logger.info(f"Computing stats for {len(cancer_types)} cancer types...")
    disease_landscape_stats = {}

    for cancer_type in cancer_types:
        logger.info(f"Computing stats for: {cancer_type}")
        try:
            stats = repository.get_disease_landscape_stats(cancer_type)
            disease_landscape_stats[cancer_type] = stats

            # Log summary
            total_status = sum(stats.get("status", {}).values())
            extracted = stats.get("extracted_count", 0)
            logger.info(
                f"  ✓ {cancer_type}: {total_status} total trials, "
                f"{extracted} extracted"
            )
        except Exception as e:
            logger.error(f"  ✗ Error computing stats for {cancer_type}: {e}")
            disease_landscape_stats[cancer_type] = {
                "status": {},
                "phase": {},
                "funder_type": {"Industry": 0, "Non-Industry": 0},
                "extracted_count": 0,
            }

    # Save disease landscape stats to JSON file
    deployed_dir = Path(__file__).parent / "data" / "deployed"
    deployed_dir.mkdir(parents=True, exist_ok=True)
    disease_landscape_file = deployed_dir / "disease_landscape_stats.json"

    with open(disease_landscape_file, "w") as f:
        json.dump(disease_landscape_stats, f, indent=2, default=str)

    logger.info(f"\n✓ Disease landscape stats saved to: {disease_landscape_file}")

    # Print summary
    print("\n" + "=" * 60)
    print("DISEASE LANDSCAPE STATS SUMMARY")
    print("=" * 60)
    for cancer_type, stats in disease_landscape_stats.items():
        total_status = sum(stats.get("status", {}).values())
        extracted = stats.get("extracted_count", 0)
        print(f"{cancer_type}:")
        print(f"  Total trials: {total_status}")
        print(f"  Extracted: {extracted}")
        print("  Status breakdown:")
        for status, count in stats.get("status", {}).items():
            if count > 0:
                print(f"    {status}: {count}")
        print()

    logger.info("\n✓ JSON generation complete!")
    logger.info(f"File location: {disease_landscape_file}")


if __name__ == "__main__":
    main()
