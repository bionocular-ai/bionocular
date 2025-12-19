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

                if row["created_at"]:
                    abstract["created_at"] = row["created_at"]

                abstracts.append(abstract)

            logger.info(
                f"Loaded {len(abstracts)} abstracts/publications from SQLite database"
            )
            return abstracts

        finally:
            conn.close()

    def get_all_trials(
        self, skip: int = 0, limit: int = 100
    ) -> tuple[list[dict[str, Any]], int]:
        """Get all trials with pagination.

        This is a simplified version that returns basic trial info.
        For full analytics data, use _load_json_files() instead.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            Tuple of (list of trial dictionaries, total count)
        """
        if not self.db_path.exists():
            return [], 0

        conn = self._get_connection()
        try:
            # Get total count
            cursor = conn.execute("SELECT COUNT(*) FROM abstracts")
            total = cursor.fetchone()[0]

            # Get paginated results
            cursor = conn.execute(
                """
                SELECT
                    abstract_id,
                    publication_id,
                    file,
                    arm_results
                FROM abstracts
                LIMIT ? OFFSET ?
            """,
                (limit, skip),
            )

            trials = []
            for row in cursor.fetchall():
                arm_results = (
                    json.loads(row["arm_results"]) if row["arm_results"] else {}
                )

                # Extract basic info from first arm
                trial_info = {
                    "id": row["abstract_id"] or row["publication_id"] or "",
                    "abstract_id": row["abstract_id"],
                    "publication_id": row["publication_id"],
                    "file": row["file"],
                }

                # Try to extract NCT number and other info from arm_results
                if arm_results:
                    first_arm: dict[str, Any] = next(iter(arm_results.values()), {})
                    attributes = first_arm.get("attributes", {})

                    # Extract NCT number
                    nct_attr = attributes.get(
                        "AttributeType.NCT_NUMBER"
                    ) or attributes.get("nct_number")
                    if nct_attr:
                        if isinstance(nct_attr, dict):
                            trial_info["nct_id"] = nct_attr.get("value", "")
                        else:
                            trial_info["nct_id"] = str(nct_attr)

                trials.append(trial_info)

            return trials, total

        finally:
            conn.close()

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

            if row["created_at"]:
                abstract["created_at"] = row["created_at"]

            return abstract

        finally:
            conn.close()
