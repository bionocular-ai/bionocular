"""Therapy approval status classifier.

This module provides functionality to classify treatment arms as
approved/standard of care vs investigational based on therapy names
and arm characteristics.
"""

from enum import Enum
from pathlib import Path
from typing import Optional

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False
    import json

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
        self.approved_agents = set()
        self.investigational_agents = set()
        self.control_keywords = set()

        # Extract approved therapy names
        approved = self.config.get("approved_therapies", {})
        for _category, therapies in approved.items():
            for therapy in therapies:
                name = therapy.get("name", "").lower()
                if name:
                    self.approved_agents.add(name)
                # Also add brand names
                brand_names = therapy.get("brand_name") or therapy.get(
                    "brand_names", []
                )
                if isinstance(brand_names, str):
                    brand_names = [brand_names]
                for brand in brand_names:
                    if brand:
                        self.approved_agents.add(brand.lower())

        # Extract investigational therapy names
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
        self.control_keywords = {
            keyword.lower() for keyword in self.config.get("control_arms", [])
        }

        # Add indicator keywords
        approved_indicators = self.config.get("approved_indicators", [])

        for indicator in approved_indicators:
            self.control_keywords.add(indicator.lower())

    def classify_arm(
        self,
        arm_name: str,
        generic_name: Optional[str] = None,
        title: Optional[str] = None,
    ) -> TherapyStatus:
        """Classify a treatment arm as approved, investigational, control, or unknown.

        Args:
            arm_name: Name of the treatment arm
            generic_name: Generic drug name (optional)
            title: Trial title (optional, for context)

        Returns:
            TherapyStatus enum value
        """
        if not arm_name:
            return TherapyStatus.UNKNOWN

        arm_lower = arm_name.lower()
        title_lower = (title or "").lower()

        # Check for control/comparator arms first
        for keyword in self.control_keywords:
            if keyword in arm_lower:
                return TherapyStatus.CONTROL

        # Check for approved therapies
        for agent in self.approved_agents:
            if agent in arm_lower:
                # Make sure it's not part of an investigational combination
                # by checking if investigational agents are also present
                has_investigational = any(
                    inv_agent in arm_lower for inv_agent in self.investigational_agents
                )
                if not has_investigational:
                    return TherapyStatus.APPROVED

        # Check for investigational therapies
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
