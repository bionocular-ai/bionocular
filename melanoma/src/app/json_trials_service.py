"""Service for reading trial data from JSON files.

This service reads enhanced extraction results from JSON files and provides
a simple interface that can later be replaced with a database-backed service.
Supports multiple JSON files that will be merged together.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..domain.cancer_type_normalizer import (
    get_primary_cancer_type,
    normalize_cancer_type_with_splitting,
)

logger = logging.getLogger(__name__)


class JSONTrialsService:
    """Service for reading trial data from JSON files."""

    def __init__(self, json_file_paths: str | list[str] | None = None):
        """Initialize the JSON trials service.
        
        Args:
            json_file_paths: Path(s) to JSON file(s). Can be:
                           - Single file path (str)
                           - List of file paths (list[str])
                           - None: uses environment variable or default paths
        """
        if json_file_paths is None:
            # Check for environment variable (can be comma-separated list)
            env_paths = os.getenv("TRIALS_JSON_FILES", "")
            if env_paths:
                json_file_paths = [p.strip() for p in env_paths.split(",") if p.strip()]
            else:
                # Default: use all known abstract files
                json_file_paths = [
                    "data/output/ASCO_2020.json",
                    "data/output/ASCO_2021.json",
                    "data/output/ASCO_2022.json",
                    "data/output/ASCO_2023.json",
                    "data/output/ASCO_2024.json",
                    "data/output/ASCO_2025.json",
                    "data/output/ESMO_2020-2024.json",
                    "data/output/Publications_70.json",
                ]
        
        # Normalize to list
        if isinstance(json_file_paths, str):
            json_file_paths = [json_file_paths]
        
        self.json_file_paths = [Path(p) for p in json_file_paths]
        self._cache: list[dict[str, Any]] | None = None
        self._cache_timestamps: dict[str, float] | None = None

    def _load_json_files(self) -> list[dict[str, Any]]:
        """Load and cache all JSON files, merging abstracts.
        
        Returns:
            List of abstract dictionaries from all files
            
        Raises:
            FileNotFoundError: If any JSON file doesn't exist
            json.JSONDecodeError: If any JSON file is invalid
        """
        # Check if any file has been modified
        current_timestamps = {str(p): p.stat().st_mtime for p in self.json_file_paths if p.exists()}
        
        if self._cache is None or self._cache_timestamps != current_timestamps:
            all_abstracts = []
            total_loaded = 0
            
            for json_file_path in self.json_file_paths:
                if not json_file_path.exists():
                    logger.warning(f"JSON file not found, skipping: {json_file_path}")
                    continue
                
                try:
                    logger.info(f"Loading trials data from: {json_file_path}")
                    with open(json_file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    # Extract abstracts and publications from this file
                    abstracts = data.get("abstracts", [])
                    publications = data.get("publications", [])
                    
                    # Combine abstracts and publications (publications will be treated as abstracts for processing)
                    all_items = abstracts + publications
                    
                    # Filter out items with "No treatment arms identified"
                    filtered_items = [
                        item for item in all_items
                        if "No treatment arms identified" not in item.get("errors", [])
                    ]
                    
                    filtered_count = len(all_items) - len(filtered_items)
                    if filtered_count > 0:
                        logger.info(f"Filtered out {filtered_count} item(s) with no treatment arms from {json_file_path.name}")
                    
                    all_abstracts.extend(filtered_items)
                    total_loaded += len(filtered_items)
                    logger.info(f"Loaded {len(filtered_items)} items ({len(abstracts)} abstracts, {len(publications)} publications) from {json_file_path.name}")
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in {json_file_path}: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Error loading {json_file_path}: {e}")
                    continue
            
            self._cache = all_abstracts
            self._cache_timestamps = current_timestamps
            logger.info(f"Total abstracts loaded: {total_loaded} from {len(self.json_file_paths)} file(s)")
        
        return self._cache or []

    def _extract_attribute_value(
        self, attributes: dict[str, Any], attribute_key: str
    ) -> str:
        """Extract attribute value from the attributes dictionary.
        
        Args:
            attributes: Dictionary of attributes with AttributeType keys
            attribute_key: The attribute key to look for (e.g., "AttributeType.NCT_NUMBER")
            
        Returns:
            The attribute value, or empty string if not found
        """
        # Try the full attribute key first (for abstracts)
        attr = attributes.get(attribute_key)
        if attr and isinstance(attr, dict):
            value = attr.get("value", "")
            # Skip "Not found" values
            if value and value != "Not found":
                return str(value)
        
        # For publications, try the simplified key format (e.g., "nct_number" instead of "AttributeType.NCT_NUMBER")
        # Extract the base key name from AttributeType.NCT_NUMBER -> nct_number
        if attribute_key.startswith("AttributeType."):
            base_key = attribute_key.replace("AttributeType.", "").lower()
            attr = attributes.get(base_key)
            if attr and isinstance(attr, dict):
                value = attr.get("value", "")
                if value and value != "Not found":
                    return str(value)
        
        return ""

    def _extract_trial_from_abstract(self, abstract: dict[str, Any]) -> dict[str, Any]:
        """Extract trial data from an abstract entry.
        
        Args:
            abstract: Abstract dictionary from JSON file (can be abstract or publication)
            
        Returns:
            Formatted trial data dictionary matching TrialResponse format
        """
        # Determine if this is a publication by checking for publication_id field
        # This must be checked before extracting abstract_id
        is_publication = "publication_id" in abstract and abstract.get("publication_id")
        
        # Get the first arm (or best arm) to extract common attributes
        # Most attributes are shared across arms, so we'll use the first arm
        arm_results = abstract.get("arm_results", {})
        first_arm_key = next(iter(arm_results.keys())) if arm_results else None
        attributes = {}
        
        if first_arm_key:
            first_arm = arm_results[first_arm_key]
            attributes = first_arm.get("attributes", {})
        
        # Extract abstract_id or publication_id from top-level field
        # For abstracts: use abstract_id, for publications: use publication_id
        abstract_id = abstract.get("publication_id", "") if is_publication else abstract.get("abstract_id", "")
        if not abstract_id:
            abstract_id = self._extract_attribute_value(attributes, "AttributeType.ABSTRACT_NUMBER")
        
        # Extract values from attributes
        # Try both AttributeType.NCT_NUMBER (for abstracts) and nct_number (for publications)
        nct_number = self._extract_attribute_value(attributes, "AttributeType.NCT_NUMBER")
        if not nct_number:
            nct_number = self._extract_attribute_value(attributes, "nct_number")
        
        trial_name = self._extract_attribute_value(attributes, "AttributeType.TRIAL_NAME")
        if not trial_name:
            trial_name = self._extract_attribute_value(attributes, "trial_name")
        
        phase = self._extract_attribute_value(attributes, "AttributeType.CLINICAL_TRIAL_PHASE")
        if not phase:
            phase = self._extract_attribute_value(attributes, "clinical_trial_phase")
        
        sponsor = self._extract_attribute_value(attributes, "AttributeType.SPONSORS")
        if not sponsor:
            sponsor = self._extract_attribute_value(attributes, "sponsors")
        
        cancer_type = self._extract_attribute_value(attributes, "AttributeType.CANCER_TYPE")
        if not cancer_type:
            cancer_type = self._extract_attribute_value(attributes, "cancer_type")
        
        # Normalize cancer type(s) to the 10 main categories
        # For combinations like "Acral Melanoma, Mucosal Melanoma", we want to store
        # all types so the abstract appears in both category filters
        cancer_types = []
        primary_cancer_type = ""
        if cancer_type:
            # Get all normalized types (handles combinations by splitting)
            cancer_types = normalize_cancer_type_with_splitting(cancer_type)
            # Get primary type for backward compatibility
            primary_cancer_type = get_primary_cancer_type(cancer_type)
        else:
            primary_cancer_type = ""
        
        year = self._extract_attribute_value(attributes, "AttributeType.PUBLISHED_YEAR")
        if not year:
            year = self._extract_attribute_value(attributes, "publication_year") or self._extract_attribute_value(attributes, "published_year")
        
        # Clean up phase value (remove "PHASE" prefix if present)
        if phase:
            phase = phase.replace("PHASE", "").strip()
        
        # Generate a stable ID from abstract_id
        # In the future, this could be a database UUID
        trial_id = str(uuid4())
        
        # Try to get status from attributes (if available)
        status = self._extract_attribute_value(attributes, "AttributeType.STATUS") or "Unknown"
        
        # Extract arms data for flattening on frontend
        arms = []
        if arm_results:
            for arm_key, arm_data in arm_results.items():
                arm_attributes = arm_data.get("attributes", {})
                arm_name = self._extract_attribute_value(arm_attributes, "AttributeType.ARM_NAME")
                generic_name = self._extract_attribute_value(arm_attributes, "AttributeType.GENERIC_NAME")
                
                # Fallback: try to get from arm_data directly if not in attributes
                if not arm_name:
                    arm_name = arm_data.get("arm_name", "")
                if not generic_name:
                    generic_name = arm_data.get("generic_name", "")
                
                if arm_name or generic_name:
                    arms.append({
                        "arm_name": arm_name or "",
                        "generic_name": generic_name or "",
                    })
        
        # If no arms found, create a single arm entry with available data
        if not arms:
            generic_name = self._extract_attribute_value(attributes, "AttributeType.GENERIC_NAME")
            if generic_name:
                arms.append({
                    "arm_name": "",
                    "generic_name": generic_name,
                })
        
        result = {
            "id": trial_id,
            "nct_id": nct_number,
            "title": trial_name or abstract_id or "Untitled",
            "phase": phase,
            "sponsor": sponsor,
            "status": status,
            "abstract_id": abstract_id,  # From AttributeType.ABSTRACT_NUMBER or publication_id
            "cancer_type": primary_cancer_type,  # Primary type for backward compatibility
            "cancer_types": cancer_types,  # Array of all normalized types (for filtering)
            "year": year,
            "type": "publication" if is_publication else "abstract",  # Track if it's a publication or abstract
        }
        
        # Add arms if we have them
        if arms:
            result["arms"] = arms
            # Also add first arm's data for backward compatibility
            if arms:
                result["generic_name"] = arms[0].get("generic_name", "")
                result["arm_name"] = arms[0].get("arm_name", "")
        
        return result

    def get_all_trials(self, skip: int = 0, limit: int = 100) -> tuple[list[dict[str, Any]], int]:
        """Get all trials with pagination.
        
        Only returns trials that have an NCT number.
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            Tuple of (list of trial dictionaries, total count)
        """
        try:
            abstracts = self._load_json_files()
            
            # Transform abstracts to trials
            trials = [self._extract_trial_from_abstract(abstract) for abstract in abstracts]
            
            # Filter out trials without NCT numbers
            trials_with_nct = [
                trial for trial in trials
                if trial.get("nct_id") and trial["nct_id"].strip()
            ]
            
            # Apply pagination
            total = len(trials_with_nct)
            paginated_trials = trials_with_nct[skip : skip + limit]
            
            return paginated_trials, total
            
        except Exception as e:
            logger.error(f"Error loading trials from JSON: {e}", exc_info=True)
            return [], 0

    def get_trial_by_id(self, trial_id: str) -> dict[str, Any] | None:
        """Get a specific trial by ID.
        
        Note: Since we're using generated UUIDs, this won't work well with JSON.
        This method is here for API compatibility but will need to be updated
        when we switch to database (where IDs are stable).
        
        Args:
            trial_id: Trial ID (not currently used with JSON source)
            
        Returns:
            Trial dictionary or None if not found
        """
        # For now, return None since IDs are generated
        # This will work properly once we migrate to database
        return None

    def get_trial_by_abstract_id(self, abstract_id: str) -> dict[str, Any] | None:
        """Get a trial by abstract ID.
        
        Args:
            abstract_id: Abstract ID (e.g., "ESMO_2020_1076O", "ASCO_2020_001", or "Batch-III_11")
            
        Returns:
            Trial dictionary or None if not found
        """
        try:
            abstracts = self._load_json_files()
            
            for abstract in abstracts:
                # Check both abstract_id and publication_id fields
                if abstract.get("abstract_id") == abstract_id or abstract.get("publication_id") == abstract_id:
                    return self._extract_trial_from_abstract(abstract)
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding trial by abstract_id: {e}", exc_info=True)
            return None

    def get_full_abstract_by_id(self, abstract_id: str) -> dict[str, Any] | None:
        """Get full abstract/publication data by abstract ID.
        
        Args:
            abstract_id: Abstract ID (e.g., "ESMO_2020_1076O", "ASCO_2020_001", or "Batch-III_11")
            
        Returns:
            Full abstract dictionary with all attributes and arm_results, or None if not found.
            Cancer type attributes are normalized to the 10 main categories.
        """
        try:
            abstracts = self._load_json_files()
            
            for abstract in abstracts:
                # Check both abstract_id and publication_id fields
                if abstract.get("abstract_id") == abstract_id or abstract.get("publication_id") == abstract_id:
                    # Normalize cancer type attributes in arm_results
                    normalized_abstract = self._normalize_cancer_types_in_abstract(abstract.copy())
                    return normalized_abstract
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding full abstract by abstract_id: {e}", exc_info=True)
            return None
    
    def _normalize_cancer_types_in_abstract(self, abstract: dict[str, Any]) -> dict[str, Any]:
        """Normalize cancer type attributes in an abstract's arm_results.
        
        This ensures that the Complete Information page shows normalized cancer types
        instead of raw values from the JSON files.
        
        Args:
            abstract: Abstract dictionary with arm_results
            
        Returns:
            Abstract dictionary with normalized cancer type attributes
        """
        arm_results = abstract.get("arm_results", {})
        
        for arm_key, arm_data in arm_results.items():
            attributes = arm_data.get("attributes", {})
            
            # Check for cancer type in various formats
            cancer_type_keys = [
                "AttributeType.CANCER_TYPE",
                "cancer_type",
            ]
            
            for key in cancer_type_keys:
                if key in attributes:
                    attr_data = attributes[key]
                    if isinstance(attr_data, dict):
                        original_value = attr_data.get("value", "")
                        if original_value:
                            # Normalize the cancer type
                            normalized_types = normalize_cancer_type_with_splitting(original_value)
                            primary_type = get_primary_cancer_type(original_value)
                            
                            # Update the value to normalized primary type
                            attr_data["value"] = primary_type
                            
                            # Add normalized_types array if not already present
                            if "normalized_types" not in attr_data:
                                attr_data["normalized_types"] = normalized_types
                            
                            # Add original_value for reference if not present
                            if "original_value" not in attr_data:
                                attr_data["original_value"] = original_value
                    elif isinstance(attr_data, str):
                        # Handle case where attribute is just a string
                        normalized_types = normalize_cancer_type_with_splitting(attr_data)
                        primary_type = get_primary_cancer_type(attr_data)
                        attributes[key] = {
                            "value": primary_type,
                            "normalized_types": normalized_types,
                            "original_value": attr_data,
                        }
        
        return abstract

    def get_trials_by_nct_id(self, nct_id: str, skip: int = 0, limit: int = 100) -> tuple[list[dict[str, Any]], int]:
        """Get all trials (abstracts/publications) associated with an NCT number.
        
        Args:
            nct_id: NCT number (e.g., "NCT02388906")
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            Tuple of (list of trial dictionaries, total count)
        """
        try:
            abstracts = self._load_json_files()
            
            # Filter abstracts that have this NCT number
            matching_trials = []
            for abstract in abstracts:
                # Extract NCT number from the abstract
                arm_results = abstract.get("arm_results", {})
                first_arm_key = next(iter(arm_results.keys())) if arm_results else None
                attributes = {}
                
                if first_arm_key:
                    first_arm = arm_results[first_arm_key]
                    attributes = first_arm.get("attributes", {})
                
                abstract_nct = self._extract_attribute_value(attributes, "AttributeType.NCT_NUMBER")
                
                # Normalize NCT IDs for comparison (case-insensitive, strip whitespace)
                if abstract_nct and abstract_nct.upper().strip() == nct_id.upper().strip():
                    trial = self._extract_trial_from_abstract(abstract)
                    matching_trials.append(trial)
            
            # Apply pagination
            total = len(matching_trials)
            paginated_trials = matching_trials[skip : skip + limit]
            
            return paginated_trials, total
            
        except Exception as e:
            logger.error(f"Error finding trials by NCT ID {nct_id}: {e}", exc_info=True)
            return [], 0

