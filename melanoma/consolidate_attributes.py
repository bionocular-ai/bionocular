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
from pathlib import Path
from typing import Dict, Any, Tuple

# Mapping from corrected attribute keys to AttributeType keys
ATTRIBUTE_MAPPING = {
    "abstract_number": "AttributeType.ABSTRACT_NUMBER",
    "comments": "AttributeType.COMMENTS",
    "nct_number": "AttributeType.NCT_NUMBER",
    "mechanism_of_action": "AttributeType.MECHANISM_OF_ACTION",
    "target_protein": "AttributeType.TARGET_PROTEIN",
    "number_of_patients": "AttributeType.NUMBER_OF_PATIENTS",
}

# Year-wise file mapping
YEAR_FILES = {
    2020: "enhanced_extraction_results_20251111_145655.json",
    2021: "enhanced_extraction_results_20251111_171423.json",
    2022: "enhanced_extraction_results_20251111_185013.json",
    2023: "enhanced_extraction_results_20251111_203147.json",
    2024: "enhanced_extraction_results_20251111_221555.json",
    2025: "enhanced_extraction_results_20251111_234658.json",
}

CORRECTED_ATTRIBUTES_FILE = "asco_abstract_attributes_extraction_20251114_155538.json"


def load_json(file_path: str) -> Dict[str, Any]:
    """Load JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(data: Dict[str, Any], file_path: str) -> None:
    """Save JSON file with pretty formatting."""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def build_corrected_attributes_map(corrected_data: Dict[str, Any]) -> Dict[Tuple[int, str], Dict[str, Dict[str, Any]]]:
    """
    Build a mapping: (year, abstract_number) -> arm_id -> attribute_key -> attribute_value
    
    Returns a nested dictionary structure for quick lookup.
    """
    corrected_map = {}
    
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


def consolidate_attributes(year_file: str, year: int, corrected_map: Dict[Tuple[int, str], Dict[str, Dict[str, Any]]]) -> Tuple[Dict[str, Any], int, str]:
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
                abstract_number = attributes["AttributeType.ABSTRACT_NUMBER"].get("value")
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


def main():
    """Main function to consolidate attributes."""
    # Load corrected attributes
    print(f"Loading corrected attributes from {CORRECTED_ATTRIBUTES_FILE}...")
    corrected_data = load_json(CORRECTED_ATTRIBUTES_FILE)
    
    # Build mapping for quick lookup
    print("Building corrected attributes mapping...")
    corrected_map = build_corrected_attributes_map(corrected_data)
    
    print(f"Found corrected attributes for {len(corrected_map)} abstracts")
    
    # Process each year-wise file
    total_updates = 0
    for year, file_path in YEAR_FILES.items():
        if not Path(file_path).exists():
            print(f"Warning: File {file_path} not found, skipping...")
            continue
        
        updated_data, update_count, output_file = consolidate_attributes(file_path, year, corrected_map)
        
        # Save to new file
        print(f"  Updated {update_count} attributes")
        save_json(updated_data, output_file)
        total_updates += update_count
        print(f"  Saved consolidated file: {output_file}\n")
    
    print(f"Consolidation complete! Total attributes updated: {total_updates}")
    print(f"New consolidated files have been created with '_consolidated' suffix.")


if __name__ == "__main__":
    main()

