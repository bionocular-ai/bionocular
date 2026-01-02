#!/usr/bin/env python3
"""Populate extraction_provenance table from deployed JSON files.

This script:
1. Reads all JSON files from data/deployed/
2. Extracts NCT numbers from abstracts and publications
3. Populates extraction_provenance table with source names
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.clinical_trials.factory import create_clinical_trials_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def extract_nct_from_attributes(attributes: dict[str, Any]) -> str | None:
    """Extract NCT number from attributes dictionary.

    Args:
        attributes: Attributes dictionary from arm_results

    Returns:
        NCT number string or None if not found
    """
    # Try different attribute key formats
    nct_keys = [
        "AttributeType.NCT_NUMBER",
        "NCT_NUMBER",
        "nct_number",
        "NCTNumber",
    ]

    for key in nct_keys:
        value = attributes.get(key)
        if value:
            # Handle both direct values and nested dicts
            if isinstance(value, dict):
                nct = value.get("value") or value.get("NCT_NUMBER")
            else:
                nct = value

            if nct and isinstance(nct, str) and nct.strip():
                # Clean and validate NCT format
                nct = nct.strip().upper()
                if nct.startswith("NCT") and len(nct) >= 11:
                    return nct

    return None


def extract_nct_numbers_from_json_file(
    json_file_path: Path,
) -> list[tuple[str, str]]:
    """Extract NCT numbers and source name (abstract_id/publication_id) from a JSON file.

    Args:
        json_file_path: Path to JSON file

    Returns:
        List of tuples (nct_number, source_name) where source_name is abstract_id or publication_id
    """
    nct_records: list[tuple[str, str]] = []

    try:
        logger.info(f"Processing {json_file_path.name}...")
        with open(json_file_path, encoding="utf-8") as f:
            data = json.load(f)

        # Process abstracts
        abstracts = data.get("abstracts", [])
        for abstract in abstracts:
            abstract_id = abstract.get("abstract_id", "")
            if not abstract_id:
                logger.warning(f"Skipping abstract without abstract_id in {json_file_path.name}")
                continue

            arm_results = abstract.get("arm_results", {})
            for arm_key, arm_data in arm_results.items():
                attributes = arm_data.get("attributes", {})
                nct_number = extract_nct_from_attributes(attributes)
                if nct_number:
                    # Use abstract_id as source_name
                    nct_records.append((nct_number, abstract_id))

        # Process publications
        publications = data.get("publications", [])
        for publication in publications:
            publication_id = publication.get("publication_id", "")
            if not publication_id:
                logger.warning(f"Skipping publication without publication_id in {json_file_path.name}")
                continue

            arm_results = publication.get("arm_results", {})
            for arm_key, arm_data in arm_results.items():
                attributes = arm_data.get("attributes", {})
                nct_number = extract_nct_from_attributes(attributes)
                if nct_number:
                    # Use publication_id as source_name
                    nct_records.append((nct_number, publication_id))

        logger.info(
            f"Found {len(nct_records)} NCT number records in {json_file_path.name}"
        )
        return nct_records

    except Exception as e:
        logger.error(f"Error processing {json_file_path}: {e}", exc_info=True)
        return []


def main():
    """Main entry point."""
    logger.info("Starting extraction provenance population...")

    # Initialize service to get repository
    service = create_clinical_trials_service()
    repository = service.repository

    # Get all JSON files from deployed directory
    deployed_dir = Path(__file__).parent.parent / "data" / "deployed"
    json_files = list(deployed_dir.glob("*.json"))

    if not json_files:
        logger.error(f"No JSON files found in {deployed_dir}")
        return

    logger.info(f"Found {len(json_files)} JSON file(s) to process")

    # Extract NCT numbers from all files
    all_records: list[tuple[str, str]] = []
    for json_file in sorted(json_files):
        records = extract_nct_numbers_from_json_file(json_file)
        all_records.extend(records)

    if not all_records:
        logger.warning("No NCT numbers found in any JSON files")
        return

    # Keep all records - one per (nct_number, abstract_id/publication_id) pair
    # This allows the same NCT to appear in multiple abstracts/publications
    unique_records = list(set(all_records))  # Remove exact duplicates

    logger.info(
        f"Found {len(unique_records)} unique (NCT, source) pairs across all files"
    )

    # Batch upsert to extraction_provenance
    repository.batch_upsert_extraction_provenance(unique_records)

    logger.info("✓ Extraction provenance population complete!")

    # Print summary
    print("\n" + "=" * 60)
    print("EXTRACTION PROVENANCE SUMMARY")
    print("=" * 60)
    print(f"Total (NCT, source) pairs: {len(unique_records)}")

    # Count unique NCT numbers
    unique_ncts = set(nct for nct, _ in unique_records)
    print(f"Total unique NCT numbers: {len(unique_ncts)}")

    # Count unique sources (abstracts/publications)
    unique_sources = set(src for _, src in unique_records)
    print(f"Total unique sources (abstracts/publications): {len(unique_sources)}")

    # Count by source type
    abstract_count = sum(1 for _, src in unique_records if src.startswith("ASCO_") or src.startswith("ESMO_"))
    publication_count = sum(1 for _, src in unique_records if src.startswith("Batch-"))
    print(f"\nBy source type:")
    print(f"  Abstracts: {abstract_count} records")
    print(f"  Publications: {publication_count} records")


if __name__ == "__main__":
    main()

