"""Service for reading trial data from SQLite database.

This service provides the same interface as JSONTrialsService but uses
SQLite for efficient querying without loading all data into memory.
"""

import json
import logging
import os
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..domain.cancer_type_normalizer import (
    get_primary_cancer_type,
    normalize_cancer_type_with_splitting,
)

logger = logging.getLogger(__name__)


class SQLiteTrialsService:
    """Service for reading trial data from SQLite database."""

    def __init__(self, db_path: str | Path | None = None):
        """Initialize the SQLite trials service.

        Args:
            db_path: Path to SQLite database file. If None, uses default path.
        """
        if db_path is None:
            # Default: look for trials.db in data/trials_db directory
            project_root = Path(__file__).parent.parent.parent
            db_path = project_root / "data" / "trials_db" / "trials.db"
            # Also check for environment variable
            env_path = os.getenv("TRIALS_DB_PATH")
            if env_path:
                db_path = Path(env_path)

        self.db_path = Path(db_path)
        if not self.db_path.exists():
            logger.warning(
                f"SQLite database not found at {self.db_path}. "
                "Analytics endpoints will return empty results."
            )

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection.

        Returns:
            SQLite connection
        """
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found at {self.db_path}")

        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row  # Enable column access by name
        return conn

    def _load_json_files(self) -> list[dict[str, Any]]:
        """Load all abstracts/publications from SQLite database.

        This method provides the same interface as JSONTrialsService._load_json_files()
        but reads from SQLite instead of JSON files.

        Returns:
            List of abstract/publication dictionaries
        """
        if not self.db_path.exists():
            logger.warning(
                f"Database not found at {self.db_path}, returning empty list"
            )
            return []

        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT
                    abstract_id,
                    publication_id,
                    file,
                    source_url,
                    total_arms,
                    total_attributes_extracted,
                    overall_confidence,
                    processing_time_ms,
                    errors,
                    warnings,
                    arm_results,
                    created_at
                FROM abstracts
                ORDER BY abstract_id, publication_id
            """
            )

            abstracts = []
            for row in cursor.fetchall():
                # Parse JSON fields
                errors = json.loads(row["errors"]) if row["errors"] else []
                warnings = json.loads(row["warnings"]) if row["warnings"] else []
                arm_results = (
                    json.loads(row["arm_results"]) if row["arm_results"] else {}
                )

                abstract = {
                    "abstract_id": row["abstract_id"],
                    "publication_id": row["publication_id"],
                    "file": row["file"],
                    "total_arms": row["total_arms"],
                    "total_attributes_extracted": row["total_attributes_extracted"],
                    "overall_confidence": row["overall_confidence"],
                    "processing_time_ms": row["processing_time_ms"],
                    "errors": errors,
                    "warnings": warnings,
                    "arm_results": arm_results,
                }

                if row["source_url"]:
                    abstract["source_url"] = row["source_url"]

                if row["created_at"]:
                    abstract["created_at"] = row["created_at"]

                abstracts.append(abstract)

            logger.info(
                f"Loaded {len(abstracts)} abstracts/publications from SQLite database"
            )
            return abstracts

        finally:
            conn.close()

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
            abstract: Abstract dictionary from SQLite (can be abstract or publication)

        Returns:
            Formatted trial data dictionary matching TrialResponse format
        """
        abstract_id = (
            abstract.get("abstract_id") or abstract.get("publication_id") or ""
        )
        # Ensure abstract_id is always a string, not None
        abstract_id = str(abstract_id) if abstract_id else ""
        is_publication = bool(
            abstract.get("publication_id") and not abstract.get("abstract_id")
        )
        arm_results = abstract.get("arm_results", {})

        # Get attributes from first arm (most abstracts have one arm)
        attributes = {}
        if arm_results:
            first_arm: dict[str, Any] = next(iter(arm_results.values()), {})
            attributes = first_arm.get("attributes", {})

        # Extract various attributes
        nct_number = self._extract_attribute_value(
            attributes, "AttributeType.NCT_NUMBER"
        )
        if not nct_number:
            nct_number = self._extract_attribute_value(attributes, "nct_number")

        trial_name = self._extract_attribute_value(
            attributes, "AttributeType.TRIAL_NAME"
        )
        if not trial_name:
            trial_name = self._extract_attribute_value(attributes, "trial_name")

        phase = self._extract_attribute_value(
            attributes, "AttributeType.CLINICAL_TRIAL_PHASE"
        )
        if not phase:
            phase = self._extract_attribute_value(attributes, "clinical_trial_phase")

        sponsor = self._extract_attribute_value(attributes, "AttributeType.SPONSORS")
        if not sponsor:
            sponsor = self._extract_attribute_value(attributes, "sponsors")

        cancer_type = self._extract_attribute_value(
            attributes, "AttributeType.CANCER_TYPE"
        )
        if not cancer_type:
            cancer_type = self._extract_attribute_value(attributes, "cancer_type")

        # Normalize cancer type(s) to the 10 main categories
        cancer_types = []
        primary_cancer_type = ""
        if cancer_type:
            cancer_types = normalize_cancer_type_with_splitting(cancer_type)
            primary_cancer_type = get_primary_cancer_type(cancer_type)
        else:
            primary_cancer_type = ""

        year = self._extract_attribute_value(attributes, "AttributeType.PUBLISHED_YEAR")
        if not year:
            year = self._extract_attribute_value(
                attributes, "publication_year"
            ) or self._extract_attribute_value(attributes, "published_year")

        # Extract publication_name for publications
        publication_name = self._extract_attribute_value(
            attributes, "AttributeType.PUBLICATION_NAME"
        )
        if not publication_name:
            publication_name = self._extract_attribute_value(
                attributes, "publication_name"
            )

        # Clean up phase value (remove "PHASE" prefix if present)
        if phase:
            phase = phase.replace("PHASE", "").strip()

        # Generate a stable ID from abstract_id
        trial_id = str(uuid4())

        # Try to get status from attributes (if available)
        status = (
            self._extract_attribute_value(attributes, "AttributeType.STATUS")
            or "Unknown"
        )

        # Extract arms data for flattening on frontend
        arms = []
        if arm_results:
            for _arm_key, arm_data in arm_results.items():
                arm_attributes = arm_data.get("attributes", {})
                arm_name = self._extract_attribute_value(
                    arm_attributes, "AttributeType.ARM_NAME"
                )
                generic_name = self._extract_attribute_value(
                    arm_attributes, "AttributeType.GENERIC_NAME"
                )

                # Fallback: try to get from arm_data directly if not in attributes
                if not arm_name:
                    arm_name = arm_data.get("arm_name", "")
                if not generic_name:
                    generic_name = arm_data.get("generic_name", "")

                if arm_name or generic_name:
                    arms.append(
                        {
                            "arm_name": arm_name or "",
                            "generic_name": generic_name or "",
                        }
                    )

        # If no arms found, create a single arm entry with available data
        if not arms:
            generic_name = self._extract_attribute_value(
                attributes, "AttributeType.GENERIC_NAME"
            )
            if generic_name:
                arms.append(
                    {
                        "arm_name": "",
                        "generic_name": generic_name,
                    }
                )

        result = {
            "id": trial_id,
            "nct_id": nct_number,
            "title": trial_name or abstract_id or "Untitled",
            "phase": phase or "",
            "sponsor": sponsor or "",
            "status": status,
            "abstract_id": abstract_id,
            "publication_name": publication_name,
            "cancer_type": primary_cancer_type,
            "cancer_types": cancer_types,
            "year": year,
            "type": "publication" if is_publication else "abstract",
        }

        # Add arms if we have them
        if arms:
            result["arms"] = arms
            # Also add first arm's data for backward compatibility
            if arms:
                result["generic_name"] = arms[0].get("generic_name", "")
                result["arm_name"] = arms[0].get("arm_name", "")

        return result

    def get_all_trials(
        self, skip: int = 0, limit: int = 100
    ) -> tuple[list[dict[str, Any]], int]:
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
            trials = [
                self._extract_trial_from_abstract(abstract) for abstract in abstracts
            ]

            # Filter out trials without NCT numbers
            trials_with_nct = [
                trial
                for trial in trials
                if trial.get("nct_id") and trial["nct_id"].strip()
            ]

            # Apply pagination
            total = len(trials_with_nct)
            paginated_trials = trials_with_nct[skip : skip + limit]

            return paginated_trials, total

        except Exception as e:
            logger.error(f"Error loading trials from SQLite: {e}", exc_info=True)
            return [], 0

    def get_full_abstract_by_id(self, abstract_id: str) -> dict[str, Any] | None:
        """Get full abstract data by abstract_id or publication_id.

        Args:
            abstract_id: Abstract ID or publication ID

        Returns:
            Full abstract dictionary or None if not found
        """
        if not self.db_path.exists():
            return None

        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT
                    abstract_id,
                    publication_id,
                    file,
                    source_url,
                    total_arms,
                    total_attributes_extracted,
                    overall_confidence,
                    processing_time_ms,
                    errors,
                    warnings,
                    arm_results,
                    created_at
                FROM abstracts
                WHERE abstract_id = ? OR publication_id = ?
                LIMIT 1
            """,
                (abstract_id, abstract_id),
            )

            row = cursor.fetchone()
            if not row:
                return None

            # Parse JSON fields
            errors = json.loads(row["errors"]) if row["errors"] else []
            warnings = json.loads(row["warnings"]) if row["warnings"] else []
            arm_results = json.loads(row["arm_results"]) if row["arm_results"] else {}

            abstract = {
                "abstract_id": row["abstract_id"],
                "publication_id": row["publication_id"],
                "file": row["file"],
                "total_arms": row["total_arms"],
                "total_attributes_extracted": row["total_attributes_extracted"],
                "overall_confidence": row["overall_confidence"],
                "processing_time_ms": row["processing_time_ms"],
                "errors": errors,
                "warnings": warnings,
                "arm_results": arm_results,
            }

            if row["source_url"]:
                abstract["source_url"] = row["source_url"]

            if row["created_at"]:
                abstract["created_at"] = row["created_at"]

            return abstract

        finally:
            conn.close()

    def get_trials_by_nct_id(
        self, nct_id: str, skip: int = 0, limit: int = 100
    ) -> tuple[list[dict[str, Any]], int]:
        """Get trials by NCT ID with pagination.

        Args:
            nct_id: NCT number (e.g., "NCT02388906")
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            Tuple of (trials list, total count)
        """
        if not self.db_path.exists():
            return [], 0

        try:
            # Load all abstracts and filter by NCT ID
            all_abstracts = self._load_json_files()
            matching_abstracts = []

            for abstract in all_abstracts:
                # Check all arms for matching NCT number
                arm_results = abstract.get("arm_results", {})
                for arm in arm_results.values():
                    attributes = arm.get("attributes", {})
                    nct_attr = attributes.get(
                        "AttributeType.NCT_NUMBER"
                    ) or attributes.get("nct_number")
                    if nct_attr:
                        nct_value = (
                            nct_attr.get("value")
                            if isinstance(nct_attr, dict)
                            else nct_attr
                        )
                        if str(nct_value).upper().strip() == nct_id.upper().strip():
                            matching_abstracts.append(abstract)
                            break

            # Apply pagination
            total = len(matching_abstracts)
            paginated = matching_abstracts[skip : skip + limit]

            # Convert to trial format using the same method as get_all_trials
            # This ensures all required fields are present with proper defaults
            trials = [
                self._extract_trial_from_abstract(abstract) for abstract in paginated
            ]

            return trials, total

        except Exception as e:
            logger.error(f"Error finding trials by NCT ID {nct_id}: {e}", exc_info=True)
            return [], 0
