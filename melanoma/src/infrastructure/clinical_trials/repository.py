"""SQLite repository for caching clinical trial data."""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from ...domain.clinical_trial_interfaces import (
    ClinicalTrialParser,
    ClinicalTrialRepository,
)
from ...domain.clinical_trial_models import ClinicalTrialData
from ..config import CLINICAL_TRIAL_DB_PATH

logger = logging.getLogger(__name__)

# Cache expiration: refresh data after 7 days
CACHE_EXPIRATION_DAYS = 7


class SQLiteClinicalTrialRepository(ClinicalTrialRepository):
    """SQLite implementation of clinical trial cache repository."""

    def __init__(
        self,
        db_path: Optional[str] = CLINICAL_TRIAL_DB_PATH,
        parser: Optional[ClinicalTrialParser] = None,
    ):
        """Initialize the repository.

        Args:
            db_path: Path to SQLite database file
            parser: Parser for converting cached JSON to domain models
        """
        self.db_path = db_path
        self.parser = parser
        self._init_database()

    def _init_database(self) -> None:
        """Initialize the cache database and create tables if they don't exist."""
        if not self.db_path:
            logger.warning("No cache database path configured, caching disabled")
            return

        # Ensure directory structure exists
        db_path = Path(self.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Create clinical_trials_cache table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS clinical_trials_cache (
                        nct_number TEXT PRIMARY KEY,
                        api_response_json TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

                # Create index on updated_at for efficient expiration checks
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_updated_at
                    ON clinical_trials_cache(updated_at)
                    """
                )

                conn.commit()
                logger.debug(f"Cache database initialized: {self.db_path}")

        except sqlite3.Error as e:
            logger.error(f"Failed to initialize cache database: {e}")

    def get_cached_trial(self, nct_number: str) -> Optional[ClinicalTrialData]:
        """Retrieve trial data from cache if available and not expired."""
        if not self.db_path or not self.parser:
            return None

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT api_response_json, updated_at
                    FROM clinical_trials_cache
                    WHERE nct_number = ?
                    """,
                    (nct_number,),
                )

                row = cursor.fetchone()
                if not row:
                    return None

                # Check if cache is expired
                updated_at_str = row["updated_at"]
                try:
                    updated_at = datetime.fromisoformat(
                        updated_at_str.replace("Z", "+00:00")
                    )
                except ValueError:
                    updated_at = datetime.strptime(updated_at_str, "%Y-%m-%d %H:%M:%S")

                expiration_date = updated_at + timedelta(days=CACHE_EXPIRATION_DAYS)

                if datetime.now() > expiration_date:
                    logger.debug(
                        f"Cache expired for {nct_number}, will refresh from API"
                    )
                    cursor.execute(
                        "DELETE FROM clinical_trials_cache WHERE nct_number = ?",
                        (nct_number,),
                    )
                    conn.commit()
                    return None

                # Update last_accessed_at
                cursor.execute(
                    """
                    UPDATE clinical_trials_cache
                    SET last_accessed_at = CURRENT_TIMESTAMP
                    WHERE nct_number = ?
                    """,
                    (nct_number,),
                )
                conn.commit()

                # Parse cached JSON and convert to ClinicalTrialData
                api_json_data = json.loads(row["api_response_json"])
                return self.parser.parse_api_response(api_json_data)

        except (sqlite3.Error, json.JSONDecodeError, Exception) as e:
            logger.warning(f"Error reading from cache for {nct_number}: {e}")
            return None

    def save_trial_to_cache(self, nct_number: str, api_response: dict) -> None:
        """Save API response to cache."""
        if not self.db_path:
            return

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                api_json_str = json.dumps(api_response)

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO clinical_trials_cache
                    (nct_number, api_response_json, updated_at, last_accessed_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    (nct_number, api_json_str),
                )

                conn.commit()
                logger.debug(f"Cached API response for {nct_number}")

        except (sqlite3.Error, Exception) as e:
            logger.warning(f"Error saving to cache for {nct_number}: {e}")

    def clear_cache(self, nct_number: Optional[str] = None) -> int:
        """Clear cache entries."""
        if not self.db_path:
            return 0

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                if nct_number:
                    cursor.execute(
                        "DELETE FROM clinical_trials_cache WHERE nct_number = ?",
                        (nct_number,),
                    )
                    deleted = cursor.rowcount
                else:
                    # Clear all expired entries
                    expiration_date = datetime.now() - timedelta(
                        days=CACHE_EXPIRATION_DAYS
                    )
                    cursor.execute(
                        """
                        DELETE FROM clinical_trials_cache
                        WHERE updated_at < ?
                        """,
                        (expiration_date.isoformat(),),
                    )
                    deleted = cursor.rowcount

                conn.commit()
                logger.info(f"Cleared {deleted} cache entries")
                return deleted

        except sqlite3.Error as e:
            logger.error(f"Error clearing cache: {e}")
            return 0

    def get_cache_stats(self) -> dict[str, int]:
        """Get cache statistics."""
        if not self.db_path:
            return {"total": 0, "expired": 0, "valid": 0}

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Total entries
                cursor.execute("SELECT COUNT(*) FROM clinical_trials_cache")
                total = cursor.fetchone()[0]

                # Expired entries
                expiration_date = datetime.now() - timedelta(days=CACHE_EXPIRATION_DAYS)
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM clinical_trials_cache
                    WHERE updated_at < ?
                    """,
                    (expiration_date.isoformat(),),
                )
                expired = cursor.fetchone()[0]

                return {
                    "total": total,
                    "expired": expired,
                    "valid": total - expired,
                }

        except sqlite3.Error as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"total": 0, "expired": 0, "valid": 0}
