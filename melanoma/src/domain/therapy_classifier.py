"""Therapy approval status classifier.

This module provides functionality to classify treatment arms as
approved/standard of care vs investigational based on therapy names
and arm characteristics.
"""

import json
from enum import Enum
from pathlib import Path
from typing import Optional

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False

from .cancer_type_normalizer import normalize_cancer_type
from .therapy_classifier_config import THERAPY_CONFIG


class TherapyStatus(str, Enum):
    """Therapy approval status."""

    APPROVED = "approved"
    INVESTIGATIONAL = "investigational"
    CONTROL = "control"
    UNKNOWN = "unknown"


class TherapyClassifier:
    """Classifier for therapy approval status."""

    def __init__(
        self, config_path: Optional[Path] = None, config: Optional[dict] = None
    ):
        """Initialize the classifier with therapy status configuration.

        Args:
            config_path: Path to therapy_approval_status.yaml file.
                        If None, uses built-in config from therapy_classifier_config.
            config: Optional dictionary config (overrides config_path if provided).
        """
        if config is not None:
            self.config = config
        elif config_path is not None:
            self.config_path = config_path
            self.config = self._load_config()
        else:
            # Use built-in config
            self.config = THERAPY_CONFIG

        self._build_lookup_tables()

    def _load_config(self) -> dict:
        """Load the therapy approval status configuration from file."""
        try:
            with open(self.config_path, encoding="utf-8") as f:
                if HAS_YAML and self.config_path.suffix in [".yaml", ".yml"]:
                    return yaml.safe_load(f)
                else:
                    # Try JSON as fallback
                    return json.load(f)
        except FileNotFoundError:
            # Return built-in config if file doesn't exist
            return THERAPY_CONFIG

    def _build_lookup_tables(self):
        """Build lookup tables for fast classification."""
        # New structure: {(arm_name_lower, cancer_type_lower): status}
        self.exact_matches = {}
        # For backward compatibility: therapy name -> status (without indication)
        self.approved_agents = set()
        self.investigational_agents = set()
        self.control_keywords = set()
        # List of non-approved terms for exact matching
        self.non_approved_exact = set()

        # Extract approved therapy names with indications
        approved = self.config.get("approved_therapies", [])

        # Handle both dict (old format) and list (new format)
        if isinstance(approved, dict):
            # Old format: {"category": [therapy1, therapy2]}
            therapies_list = []
            for _category, therapies in approved.items():
                therapies_list.extend(therapies)
        else:
            # New format: [therapy1, therapy2]
            therapies_list = approved

        for therapy in therapies_list:
            arm_name = therapy.get("arm_name", "")
            if arm_name:
                arm_lower = arm_name.lower()
                # Add exact arm name
                self.approved_agents.add(arm_lower)

                # Add with cancer types
                cancer_types = therapy.get("cancer_types", [])
                if cancer_types:
                    for ct in cancer_types:
                        key = (arm_lower, ct.lower() if ct else "")
                        self.exact_matches[key] = TherapyStatus.APPROVED
                else:
                    # No specific cancer type, match on arm name only
                    self.exact_matches[(arm_lower, "")] = TherapyStatus.APPROVED

            # Legacy support: extract generic names
            name = therapy.get("name", "").lower()
            if name:
                self.approved_agents.add(name)

            # Also add brand names
            brand_names = therapy.get("brand_name") or therapy.get("brand_names", [])
            if isinstance(brand_names, str):
                brand_names = [brand_names]
            for brand in brand_names:
                if brand:
                    self.approved_agents.add(brand.lower())

        # Extract non-approved therapy names
        non_approved = self.config.get("non_approved_therapies", [])

        # Handle both dict (old format) and list (new format)
        if isinstance(non_approved, dict):
            # Old format: {"category": [item1, item2]}
            items_list = []
            for _category, items in non_approved.items():
                items_list.extend(items)
        else:
            # New format: [item1, item2]
            items_list = non_approved

        for item in items_list:
            if isinstance(item, str):
                # Simple string entry
                self.non_approved_exact.add(item.lower())
            elif isinstance(item, dict):
                # Entry with cancer types
                arm_name = item.get("arm_name", "")
                if arm_name:
                    arm_lower = arm_name.lower()
                    cancer_types = item.get("cancer_types", [])
                    if cancer_types:
                        for ct in cancer_types:
                            key = (arm_lower, ct.lower() if ct else "")
                            self.exact_matches[key] = TherapyStatus.INVESTIGATIONAL
                    else:
                        self.exact_matches[
                            (arm_lower, "")
                        ] = TherapyStatus.INVESTIGATIONAL

        # Extract investigational therapy names (legacy)
        investigational = self.config.get("investigational_therapies", {})
        for _category, therapies in investigational.items():
            for therapy in therapies:
                name = therapy.get("name", "").lower()
                if name:
                    self.investigational_agents.add(name)
                # Also add aliases
                alias = therapy.get("alias")
                if alias:
                    self.investigational_agents.add(alias.lower())

        # Extract control keywords
        control_arms = self.config.get("control_arms") or self.config.get(
            "placebo_and_controls", []
        )
        if isinstance(control_arms, list):
            self.control_keywords = {keyword.lower() for keyword in control_arms}

        # Add indicator keywords if present
        approved_indicators = self.config.get("approved_indicators", [])
        for indicator in approved_indicators:
            self.control_keywords.add(indicator.lower())

    def classify_arm(
        self,
        arm_name: str,
        generic_name: Optional[str] = None,
        title: Optional[str] = None,
        cancer_type: Optional[str] = None,
    ) -> TherapyStatus:
        """Classify a treatment arm as approved, investigational, control, or unknown.

        Args:
            arm_name: Name of the treatment arm
            generic_name: Generic drug name (optional)
            title: Trial title (optional, for context)
            cancer_type: Cancer type/indication (optional but highly recommended for accuracy)
                        Will be normalized to one of the 8 standard pipeline categories

        Returns:
            TherapyStatus enum value
        """
        if not arm_name:
            return TherapyStatus.UNKNOWN

        arm_lower = arm_name.lower().strip()
        title_lower = (title or "").lower()

        # Normalize cancer type to standard pipeline categories
        cancer_type_normalized = None
        if cancer_type:
            cancer_type_normalized = normalize_cancer_type(cancer_type)

        cancer_type_lower = (cancer_type_normalized or "").lower().strip()

        # Check for exact match with normalized cancer type first (most accurate)
        if cancer_type_lower:
            key = (arm_lower, cancer_type_lower)
            if key in self.exact_matches:
                return self.exact_matches[key]

        # Check for exact match without cancer type
        key_no_cancer = (arm_lower, "")
        if key_no_cancer in self.exact_matches:
            return self.exact_matches[key_no_cancer]

        # Check for control/comparator arms
        for keyword in self.control_keywords:
            if keyword in arm_lower:
                return TherapyStatus.CONTROL

        # Check for exact non-approved matches
        if arm_lower in self.non_approved_exact:
            return TherapyStatus.INVESTIGATIONAL

        # Check for approved therapies (partial match for backward compatibility)
        for agent in self.approved_agents:
            if agent in arm_lower:
                # Make sure it's not part of an investigational combination
                # by checking if investigational agents are also present
                has_investigational = any(
                    inv_agent in arm_lower for inv_agent in self.investigational_agents
                )
                # Also check non-approved exact matches
                if not has_investigational and arm_lower not in self.non_approved_exact:
                    return TherapyStatus.APPROVED

        # Check for investigational therapies (partial match)
        for agent in self.investigational_agents:
            if agent in arm_lower:
                return TherapyStatus.INVESTIGATIONAL

        # Check generic name if provided
        if generic_name:
            generic_lower = generic_name.lower()
            for agent in self.approved_agents:
                if agent in generic_lower:
                    return TherapyStatus.APPROVED
            for agent in self.investigational_agents:
                if agent in generic_lower:
                    return TherapyStatus.INVESTIGATIONAL

        # Check title for phase indicators
        investigational_indicators = self.config.get("investigational_indicators", [])
        for indicator in investigational_indicators:
            if indicator.lower() in title_lower:
                return TherapyStatus.INVESTIGATIONAL

        return TherapyStatus.UNKNOWN

    def get_therapy_details(self, arm_name: str) -> Optional[dict]:
        """Get detailed information about a therapy if available.

        Args:
            arm_name: Name of the treatment arm

        Returns:
            Dictionary with therapy details, or None if not found
        """
        arm_lower = arm_name.lower()

        # Search approved therapies
        approved = self.config.get("approved_therapies", {})
        for category, therapies in approved.items():
            for therapy in therapies:
                name = therapy.get("name", "").lower()
                if name in arm_lower:
                    return {"status": "approved", "category": category, **therapy}
                # Check brand names
                brand_names = therapy.get("brand_name") or therapy.get(
                    "brand_names", []
                )
                if isinstance(brand_names, str):
                    brand_names = [brand_names]
                for brand in brand_names:
                    if brand and brand.lower() in arm_lower:
                        return {"status": "approved", "category": category, **therapy}

        # Search investigational therapies
        investigational = self.config.get("investigational_therapies", {})
        for category, therapies in investigational.items():
            for therapy in therapies:
                name = therapy.get("name", "").lower()
                if name in arm_lower:
                    return {
                        "status": "investigational",
                        "category": category,
                        **therapy,
                    }
                # Check aliases
                alias = therapy.get("alias")
                if alias and alias.lower() in arm_lower:
                    return {
                        "status": "investigational",
                        "category": category,
                        **therapy,
                    }

        return None
