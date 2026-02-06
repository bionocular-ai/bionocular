"""Service for determining therapy approval status.

This service wraps the TherapyClassifier to add approval status to trial arms.
"""

import logging
from pathlib import Path
from typing import Any

from ..domain.cancer_type_normalizer import normalize_cancer_type
from ..domain.therapy_classifier import TherapyClassifier

logger = logging.getLogger(__name__)


class ApprovalStatusService:
    """Service for determining therapy approval status."""

    def __init__(self, config_path: Path | None = None):
        """Initialize the approval status service.

        Args:
            config_path: Optional path to therapy_approval_status.json.
                        If None, uses default config from data/deployed.
        """
        if config_path is None:
            # Use default config path (try multiple locations)
            possible_paths = [
                Path(__file__).parent.parent.parent
                / "data"
                / "deployed"
                / "therapy_approval_status.json",
                Path(__file__).parent.parent.parent
                / "resources"
                / "therapy_approval_status.json",
            ]

            config_path = None
            for path in possible_paths:
                if path.exists():
                    config_path = path
                    logger.info(f"Using approval status config from: {config_path}")
                    break

            if config_path is None:
                logger.warning("Config file not found, using built-in config")

        self.classifier = TherapyClassifier(config_path=config_path)
        logger.info("ApprovalStatusService initialized")

    def get_approval_status(
        self,
        arm_name: str,
        cancer_type: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> str:
        """Get approval status for a treatment arm.

        Args:
            arm_name: Name of the treatment arm
            cancer_type: Cancer type/indication (optional)
            attributes: Arm attributes dict (optional, used to extract cancer_type if not provided)

        Returns:
            Approval status: "Approved", "Investigational", "Control", or "Unknown"
        """
        if not arm_name:
            return "Unknown"

        # Extract cancer type from attributes if not provided
        if not cancer_type and attributes:
            cancer_type = self._extract_cancer_type(attributes)

        # Normalize cancer type
        if cancer_type:
            cancer_type = normalize_cancer_type(cancer_type)

        # Classify
        status = self.classifier.classify_arm(
            arm_name=arm_name,
            cancer_type=cancer_type,
        )

        return status.value.capitalize()  # "approved" -> "Approved"

    def _extract_cancer_type(self, attributes: dict[str, Any]) -> str | None:
        """Extract cancer type from attributes dictionary.

        Args:
            attributes: Arm attributes dictionary

        Returns:
            Cancer type string or None
        """
        # Try AttributeType.CANCER_TYPE (abstracts)
        cancer_type_attr = attributes.get("AttributeType.CANCER_TYPE")
        if cancer_type_attr and isinstance(cancer_type_attr, dict):
            value = cancer_type_attr.get("value")
            if value and value != "Not found":
                return str(value)

        # Try lowercase cancer_type (publications)
        cancer_type_attr = attributes.get("cancer_type")
        if cancer_type_attr and isinstance(cancer_type_attr, dict):
            value = cancer_type_attr.get("value")
            if value and value != "Not found":
                return str(value)

        return None

    def enrich_arm_with_approval_status(self, arm: dict[str, Any]) -> dict[str, Any]:
        """Add approval_status field to an arm dictionary.

        Args:
            arm: Arm dictionary from trial data

        Returns:
            Enriched arm dictionary with approval_status field
        """
        arm_name = arm.get("arm_name", "")
        attributes = arm.get("attributes", {})

        approval_status = self.get_approval_status(
            arm_name=arm_name,
            attributes=attributes,
        )

        # Add approval_status to arm (non-destructive)
        enriched_arm = arm.copy()
        enriched_arm["approval_status"] = approval_status

        return enriched_arm

    def enrich_abstract_with_approval_status(
        self, abstract: dict[str, Any]
    ) -> dict[str, Any]:
        """Add approval_status to all arms in an abstract.

        Args:
            abstract: Abstract dictionary with arm_results

        Returns:
            Enriched abstract with approval_status in all arms
        """
        enriched_abstract = abstract.copy()
        arm_results = enriched_abstract.get("arm_results", {})

        if not arm_results:
            return enriched_abstract

        enriched_arms = {}
        for arm_key, arm_data in arm_results.items():
            if isinstance(arm_data, dict):
                enriched_arms[arm_key] = self.enrich_arm_with_approval_status(arm_data)
            else:
                enriched_arms[arm_key] = arm_data

        enriched_abstract["arm_results"] = enriched_arms
        return enriched_abstract
