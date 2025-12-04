#!/usr/bin/env python3
"""
Script to consolidate corrected attributes from asco_abstract_attributes_extraction file
into the year-wise enhanced_extraction_results files.

The corrected attributes are:
- abstract_number
- comments
- nct_number
- mechanism_of_action
- target_protein
- number_of_patients
"""

import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

# Mapping from corrected attribute keys to AttributeType keys
ATTRIBUTE_MAPPING = {
    "abstract_number": "AttributeType.ABSTRACT_NUMBER",
    "comments": "AttributeType.COMMENTS",
    "nct_number": "AttributeType.NCT_NUMBER",
    "mechanism_of_action": "AttributeType.MECHANISM_OF_ACTION",
    "target_protein": "AttributeType.TARGET_PROTEIN",
    "number_of_patients": "AttributeType.NUMBER_OF_PATIENTS",
}

# Default data directory
DEFAULT_DATA_DIR = Path(__file__).parent / "data" / "output"

# File patterns for finding files dynamically
YEAR_FILE_PATTERN = re.compile(r"enhanced_extraction_results_\d{8}_\d{6}\.json$")
CORRECTED_ATTRIBUTES_PATTERN = re.compile(
    r"asco_abstract_attributes_extraction_\d{8}_\d{6}\.json$"
)


def find_latest_file(directory: Path, pattern: re.Pattern[str]) -> Optional[Path]:
    """Find the most recent file matching the pattern in the directory."""
    matching_files = [
        f for f in directory.iterdir() if f.is_file() and pattern.match(f.name)
    ]
    if not matching_files:
        return None
    # Sort by modification time, most recent first
    return max(matching_files, key=lambda f: f.stat().st_mtime)


def find_year_files(directory: Path) -> dict[int, Path]:
    """
    Find year-wise enhanced_extraction_results files.

    Attempts to match files by year based on filename patterns or file content.
    Returns a dictionary mapping year -> file path.
    """
    year_files: dict[int, Path] = {}
    matching_files = [
        f
        for f in directory.iterdir()
        if f.is_file() and YEAR_FILE_PATTERN.match(f.name)
    ]

    if not matching_files:
        return year_files

    # Try to determine year from file content
    for file_path in matching_files:
        try:
            data = load_json(str(file_path))
            abstracts = data.get("abstracts", [])
            if abstracts:
                # Get year from first abstract
                first_abstract = abstracts[0]
                year = first_abstract.get("year")
                if year and year not in year_files:
                    year_files[year] = file_path
        except (json.JSONDecodeError, KeyError, Exception) as e:
            print(f"Warning: Could not determine year for {file_path.name}: {e}")
            continue

    return year_files


def load_json(file_path: str) -> dict[str, Any]:
    """Load JSON file."""
    with open(file_path, encoding="utf-8") as f:
        return json.load(f)


def save_json(data: dict[str, Any], file_path: str) -> None:
    """Save JSON file with pretty formatting."""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def build_corrected_attributes_map(
    corrected_data: dict[str, Any]
) -> dict[tuple[int, str], dict[str, dict[str, Any]]]:
    """
    Build a mapping: (year, abstract_number) -> arm_id -> attribute_key -> attribute_value

    Returns a nested dictionary structure for quick lookup.
    """
    corrected_map: dict[tuple[int, str], dict[str, dict[str, Any]]] = {}

    for abstract in corrected_data.get("abstracts", []):
        year = abstract.get("year")
        if not year:
            continue

        # Get abstract_number from the first arm (it should be the same across arms)
        arm_results = abstract.get("arm_results", {})
        abstract_number = None

        # Try to find abstract_number from any arm
        for arm_data in arm_results.values():
            attributes = arm_data.get("attributes", {})
            if "abstract_number" in attributes:
                abstract_number = attributes["abstract_number"].get("value")
                break

        if not abstract_number:
            continue

        # Use (year, abstract_number) as the key
        key = (year, str(abstract_number))
        corrected_map[key] = {}

        for arm_id, arm_data in arm_results.items():
            corrected_map[key][arm_id] = {}

            attributes = arm_data.get("attributes", {})
            for attr_key, attr_value in attributes.items():
                if attr_key in ATTRIBUTE_MAPPING:
                    # Map to the AttributeType key
                    mapped_key = ATTRIBUTE_MAPPING[attr_key]
                    corrected_map[key][arm_id][mapped_key] = attr_value

    return corrected_map


def consolidate_attributes(
    year_file: str,
    year: int,
    corrected_map: dict[tuple[int, str], dict[str, dict[str, Any]]],
) -> tuple[dict[str, Any], int, str]:
    """
    Consolidate corrected attributes into a year-wise file.

    Returns: (updated_data, count_of_updates, output_file_path)
    """
    print(f"Processing {year_file}...")
    year_data = load_json(year_file)

    update_count = 0

    for abstract in year_data.get("abstracts", []):
        # Get abstract_number from the first arm
        arm_results = abstract.get("arm_results", {})
        abstract_number = None

        # Try to find abstract_number from any arm
        for arm_data in arm_results.values():
            attributes = arm_data.get("attributes", {})
            if "AttributeType.ABSTRACT_NUMBER" in attributes:
                abstract_number = attributes["AttributeType.ABSTRACT_NUMBER"].get(
                    "value"
                )
                break

        if not abstract_number:
            continue

        # Look up by (year, abstract_number)
        key = (year, str(abstract_number))
        if key not in corrected_map:
            continue

        corrected_arms = corrected_map[key]

        for arm_id, arm_data in arm_results.items():
            # Check if we have corrected attributes for this arm
            if arm_id not in corrected_arms:
                continue

            attributes = arm_data.get("attributes", {})
            corrected_attributes = corrected_arms[arm_id]

            # Update each corrected attribute
            for attr_key, attr_value in corrected_attributes.items():
                # Update the attribute in the year-wise file
                attributes[attr_key] = attr_value
                update_count += 1

    # Create output file path with "_consolidated" suffix
    file_path = Path(year_file)
    output_file = file_path.parent / f"{file_path.stem}_consolidated{file_path.suffix}"

    return year_data, update_count, str(output_file)


def main(data_dir: Optional[Path] = None):
    """
    Main function to consolidate attributes.

    Args:
        data_dir: Directory containing the JSON files. Defaults to data/output.
    """
    # Determine data directory
    if data_dir is None:
        data_dir = DEFAULT_DATA_DIR
    else:
        data_dir = Path(data_dir)

    if not data_dir.exists():
        print(f"Error: Data directory does not exist: {data_dir}")
        print("Please specify a valid directory containing the JSON files.")
        sys.exit(1)

    print(f"Using data directory: {data_dir}")

    # Find corrected attributes file
    print("Searching for corrected attributes file...")
    corrected_attributes_file = find_latest_file(data_dir, CORRECTED_ATTRIBUTES_PATTERN)

    if not corrected_attributes_file:
        print(
            f"Error: Could not find corrected attributes file matching pattern "
            f"'{CORRECTED_ATTRIBUTES_PATTERN.pattern}' in {data_dir}"
        )
        print("Available files:")
        for f in sorted(data_dir.iterdir()):
            if f.is_file() and "asco" in f.name.lower():
                print(f"  - {f.name}")
        sys.exit(1)

    print(f"Found corrected attributes file: {corrected_attributes_file.name}")

    # Load corrected attributes
    print(f"Loading corrected attributes from {corrected_attributes_file.name}...")
    try:
        corrected_data = load_json(str(corrected_attributes_file))
    except FileNotFoundError:
        print(f"Error: File not found: {corrected_attributes_file}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {corrected_attributes_file}: {e}")
        sys.exit(1)

    # Build mapping for quick lookup
    print("Building corrected attributes mapping...")
    corrected_map = build_corrected_attributes_map(corrected_data)

    print(f"Found corrected attributes for {len(corrected_map)} abstracts")

    # Find year-wise files
    print("\nSearching for year-wise enhanced_extraction_results files...")
    year_files = find_year_files(data_dir)

    if not year_files:
        print(
            f"Error: Could not find any year-wise files matching pattern "
            f"'{YEAR_FILE_PATTERN.pattern}' in {data_dir}"
        )
        print("Available files:")
        for f in sorted(data_dir.iterdir()):
            if f.is_file() and "enhanced_extraction_results" in f.name:
                print(f"  - {f.name}")
        sys.exit(1)

    print(f"Found {len(year_files)} year-wise file(s):")
    for year, file_path in sorted(year_files.items()):
        print(f"  Year {year}: {file_path.name}")

    # Process each year-wise file
    total_updates = 0
    for year, file_path in sorted(year_files.items()):
        if not file_path.exists():
            print(f"Warning: File {file_path} not found, skipping...")
            continue

        updated_data, update_count, output_file = consolidate_attributes(
            str(file_path), year, corrected_map
        )

        # Save to new file
        print(f"  Updated {update_count} attributes")
        save_json(updated_data, output_file)
        total_updates += update_count
        print(f"  Saved consolidated file: {output_file}\n")

    print(f"Consolidation complete! Total attributes updated: {total_updates}")
    print("New consolidated files have been created with '_consolidated' suffix.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Consolidate corrected attributes into year-wise extraction results files."
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help=f"Directory containing JSON files (default: {DEFAULT_DATA_DIR})",
    )

    args = parser.parse_args()

    data_dir = Path(args.data_dir) if args.data_dir else None
    main(data_dir)
