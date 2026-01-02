"""SQLite repository for caching clinical trial data."""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from ...domain.clinical_trial_interfaces import (
    ClinicalTrialParser,
    ClinicalTrialRepository,
)
from ...domain.clinical_trial_models import ClinicalTrialData
from ..config import CLINICAL_TRIAL_DB_PATH, DISEASE_LANDSCAPE_STATS_PATH
from .cancer_type_mapping import is_active_status

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

                # Create api_discovery table
                # Composite primary key allows same NCT to appear in multiple cancer types
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS api_discovery (
                        nct_number TEXT NOT NULL,
                        cancer_type_tag TEXT NOT NULL,
                        current_status TEXT NOT NULL,
                        discovery_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_active INTEGER DEFAULT 0,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (nct_number, cancer_type_tag)
                    )
                    """
                )

                # Create indexes for api_discovery
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_cancer_type_tag
                    ON api_discovery(cancer_type_tag)
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_api_discovery_nct_number
                    ON api_discovery(nct_number)
                    """
                )

                # Create extraction_provenance table
                # Composite primary key allows same NCT to appear in multiple sources
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS extraction_provenance (
                        nct_number TEXT NOT NULL,
                        source_name TEXT NOT NULL,
                        extraction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (nct_number, source_name)
                    )
                    """
                )

                # Create index for extraction_provenance
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_extraction_provenance_nct_number
                    ON extraction_provenance(nct_number)
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

    def upsert_discovery_record(
        self, nct_number: str, cancer_type_tag: str, current_status: str
    ) -> None:
        """Insert or update a record in the api_discovery table.

        Args:
            nct_number: NCT number
            cancer_type_tag: Normalized cancer type tag
            current_status: Current trial status
        """
        if not self.db_path:
            return

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                is_active = 1 if is_active_status(current_status) else 0

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO api_discovery
                    (nct_number, cancer_type_tag, current_status, is_active, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (nct_number, cancer_type_tag, current_status, is_active),
                )

                conn.commit()
                logger.debug(
                    f"Upserted discovery record for {nct_number} ({cancer_type_tag})"
                )

        except sqlite3.Error as e:
            logger.warning(f"Error upserting discovery record for {nct_number}: {e}")

    def batch_upsert_discovery(self, records: list[tuple[str, str, str]]) -> None:
        """Efficiently batch insert discovery records.

        Args:
            records: List of tuples (nct_number, cancer_type_tag, current_status)
        """
        if not self.db_path or not records:
            return

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Prepare data with is_active flag
                data = [
                    (
                        nct_number,
                        cancer_type_tag,
                        current_status,
                        1 if is_active_status(current_status) else 0,
                    )
                    for nct_number, cancer_type_tag, current_status in records
                ]

                cursor.executemany(
                    """
                    INSERT OR REPLACE INTO api_discovery
                    (nct_number, cancer_type_tag, current_status, is_active, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    data,
                )

                conn.commit()
                logger.info(f"Batch upserted {len(records)} discovery records")

        except sqlite3.Error as e:
            logger.error(f"Error batch upserting discovery records: {e}")

    def get_cached_api_json(self, nct_number: str) -> Optional[dict]:
        """Get raw API JSON from cache without parsing.

        Args:
            nct_number: NCT number to look up

        Returns:
            Raw JSON dict from cache or None if not found/expired
        """
        if not self.db_path:
            return None

        try:
            with sqlite3.connect(self.db_path) as conn:
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
                updated_at_str = row[1]
                try:
                    updated_at = datetime.fromisoformat(
                        updated_at_str.replace("Z", "+00:00")
                    )
                except ValueError:
                    updated_at = datetime.strptime(updated_at_str, "%Y-%m-%d %H:%M:%S")

                expiration_date = updated_at + timedelta(days=CACHE_EXPIRATION_DAYS)

                if datetime.now() > expiration_date:
                    return None  # Cache expired

                # Return raw JSON
                return json.loads(row[0])

        except (sqlite3.Error, json.JSONDecodeError) as e:
            logger.warning(f"Error reading cached JSON for {nct_number}: {e}")
            return None

    def get_existing_discovery_ncts(
        self, nct_numbers: list[str], cancer_type_tag: str
    ) -> set[str]:
        """Get set of NCT numbers that already exist in discovery table for a specific cancer type.

        Args:
            nct_numbers: List of NCT numbers to check
            cancer_type_tag: Cancer type to check for

        Returns:
            Set of NCT numbers that exist in api_discovery table for this cancer type
        """
        if not self.db_path or not nct_numbers:
            return set()

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Safe: placeholders are generated from list length, not user input
                placeholders = ",".join(["?"] * len(nct_numbers))
                # Using parameterized query - placeholders are safe
                query = f"""
                    SELECT nct_number FROM api_discovery
                    WHERE nct_number IN ({placeholders})
                    AND cancer_type_tag = ?
                    """  # nosec B608
                cursor.execute(query, nct_numbers + [cancer_type_tag])
                return {row[0] for row in cursor.fetchall()}

        except sqlite3.Error as e:
            logger.warning(f"Error checking existing NCTs: {e}")
            return set()

    def upsert_extraction_provenance(self, nct_number: str, source_name: str) -> None:
        """Insert or update a record in the extraction_provenance table.

        Args:
            nct_number: NCT number
            source_name: Source name (e.g., 'ASCO 2025', 'ESMO 2024', 'Publication')
        """
        if not self.db_path:
            return

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO extraction_provenance
                    (nct_number, source_name, extraction_date)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    """,
                    (nct_number, source_name),
                )

                conn.commit()
                logger.debug(
                    f"Upserted extraction provenance for {nct_number} from {source_name}"
                )

        except sqlite3.Error as e:
            logger.warning(
                f"Error upserting extraction provenance for {nct_number}: {e}"
            )

    def batch_upsert_extraction_provenance(
        self, records: list[tuple[str, str]]
    ) -> None:
        """Efficiently batch insert extraction provenance records.

        Args:
            records: List of tuples (nct_number, source_name)
        """
        if not self.db_path or not records:
            return

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.executemany(
                    """
                    INSERT OR REPLACE INTO extraction_provenance
                    (nct_number, source_name, extraction_date)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    """,
                    records,
                )

                conn.commit()
                logger.info(
                    f"Batch upserted {len(records)} extraction provenance records"
                )

        except sqlite3.Error as e:
            logger.error(f"Error batch upserting extraction provenance: {e}")

    def get_landscape_stats(self) -> list[dict[str, Any]]:
        """Get landscape statistics grouped by cancer type.

        Returns:
            List of dictionaries with cancer_type, total_api_count, extracted_count, bubble_size
        """
        if not self.db_path:
            return []

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # LEFT JOIN to get total API count and extracted count per cancer type
                # bubble_size is count of DISTINCT active trials (is_active = 1)
                # Use COUNT(DISTINCT ...) to avoid duplicate counting from LEFT JOIN
                cursor.execute(
                    """
                    SELECT
                        ad.cancer_type_tag as cancer_type,
                        COUNT(DISTINCT ad.nct_number) as total_api_count,
                        COUNT(DISTINCT ep.nct_number) as extracted_count,
                        COUNT(DISTINCT CASE WHEN ad.is_active = 1 THEN ad.nct_number ELSE NULL END) as bubble_size
                    FROM api_discovery ad
                    LEFT JOIN extraction_provenance ep ON ad.nct_number = ep.nct_number
                    GROUP BY ad.cancer_type_tag
                    ORDER BY ad.cancer_type_tag
                    """
                )

                results = []
                for row in cursor.fetchall():
                    results.append(
                        {
                            "cancer_type": row["cancer_type"],
                            "total_api_count": row["total_api_count"],
                            "extracted_count": row["extracted_count"],
                            "bubble_size": row["bubble_size"] or 0,
                        }
                    )

                return results

        except sqlite3.Error as e:
            logger.error(f"Error getting landscape stats: {e}")
            return []

    def get_therapeutic_index_trials(
        self, skip: int = 0, limit: int = 100
    ) -> tuple[list[dict], int]:
        """Get full trial details for trials in extraction_provenance.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            Tuple of (list of trial dictionaries, total count)
        """
        if not self.db_path or not self.parser:
            return [], 0

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Get total count
                cursor.execute(
                    """
                    SELECT COUNT(DISTINCT ep.nct_number)
                    FROM extraction_provenance ep
                    INNER JOIN clinical_trials_cache ctc ON ep.nct_number = ctc.nct_number
                    """
                )
                total = cursor.fetchone()[0]

                # Get paginated NCT numbers
                cursor.execute(
                    """
                    SELECT DISTINCT ep.nct_number, ep.source_name, ep.extraction_date
                    FROM extraction_provenance ep
                    INNER JOIN clinical_trials_cache ctc ON ep.nct_number = ctc.nct_number
                    ORDER BY ep.extraction_date DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, skip),
                )

                nct_rows = cursor.fetchall()

                # Fetch full trial data for each NCT
                trials = []
                for row in nct_rows:
                    nct_number = row["nct_number"]
                    trial_data = self.get_cached_trial(nct_number)
                    if trial_data:
                        # Convert ClinicalTrialData to dict format
                        trial_dict = {
                            "nct_number": trial_data.nct_number,
                            "trial_name": trial_data.trial_name,
                            "cancer_type": trial_data.cancer_type,
                            "source_name": row["source_name"],
                            "extraction_date": row["extraction_date"],
                            "clinical_trial_phase": trial_data.clinical_trial_phase,
                            "number_of_patients": trial_data.number_of_patients,
                            "sponsors": trial_data.sponsors,
                            "study_start_date": trial_data.study_start_date,
                            "study_completion_date": trial_data.study_completion_date,
                            "primary_endpoint": trial_data.primary_endpoint,
                            "secondary_endpoint": trial_data.secondary_endpoint,
                        }
                        trials.append(trial_dict)

                return trials, total

        except (sqlite3.Error, Exception) as e:
            logger.error(f"Error getting therapeutic index trials: {e}")
            return [], 0

    def get_disease_landscape_stats(self, cancer_type_tag: str) -> dict[str, Any]:
        """Get disease landscape statistics for a specific cancer type.

        Args:
            cancer_type_tag: Normalized cancer type tag

        Returns:
            Dictionary with status, phase, and funder_type counts
        """
        if not self.db_path or not self.parser:
            return {
                "status": {},
                "phase": {},
                "funder_type": {"Industry": 0, "Non-Industry": 0},
            }

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Get all NCT numbers for this cancer type
                cursor.execute(
                    """
                    SELECT DISTINCT nct_number
                    FROM api_discovery
                    WHERE cancer_type_tag = ?
                    """,
                    (cancer_type_tag,),
                )

                nct_rows = cursor.fetchall()
                nct_numbers = [row["nct_number"] for row in nct_rows]

                # Count distinct extracted NCT numbers for this cancer type
                cursor.execute(
                    """
                    SELECT COUNT(DISTINCT ep.nct_number) as extracted_count
                    FROM extraction_provenance ep
                    INNER JOIN api_discovery ad ON ep.nct_number = ad.nct_number
                    WHERE ad.cancer_type_tag = ?
                    """,
                    (cancer_type_tag,),
                )
                extracted_count_row = cursor.fetchone()
                extracted_count = (
                    extracted_count_row["extracted_count"] if extracted_count_row else 0
                )

                # Initialize counters
                status_counts: dict[str, int] = {
                    "NOT_YET_RECRUITING": 0,
                    "RECRUITING": 0,
                    "ACTIVE_NOT_RECRUITING": 0,
                    "COMPLETED": 0,
                    "TERMINATED": 0,
                    "ENROLLING_BY_INVITATION": 0,
                    "SUSPENDED": 0,
                    "WITHDRAWN": 0,
                    "UNKNOWN": 0,
                }

                phase_counts: dict[str, int] = {
                    "Early Phase 1": 0,
                    "Phase 1": 0,
                    "Phase 2": 0,
                    "Phase 3": 0,
                    "Phase 4": 0,
                    "Not applicable": 0,
                }

                funder_type_counts: dict[str, int] = {
                    "Industry": 0,
                    "Non-Industry": 0,
                }

                # Process each NCT number
                for nct_number in nct_numbers:
                    api_json = self.get_cached_api_json(nct_number)
                    if not api_json:
                        continue

                    # Extract status
                    status = self.parser.extract_status_from_api_json(api_json)
                    # Normalize status to match expected keys
                    # The API returns statuses like "NOT_YET_RECRUITING", "RECRUITING", etc.
                    status_upper = status.upper().strip()
                    # Map API status values to our keys
                    status_mapping = {
                        "NOT_YET_RECRUITING": "NOT_YET_RECRUITING",
                        "RECRUITING": "RECRUITING",
                        "ACTIVE_NOT_RECRUITING": "ACTIVE_NOT_RECRUITING",
                        "COMPLETED": "COMPLETED",
                        "TERMINATED": "TERMINATED",
                        "ENROLLING_BY_INVITATION": "ENROLLING_BY_INVITATION",
                        "SUSPENDED": "SUSPENDED",
                        "WITHDRAWN": "WITHDRAWN",
                        # Handle variations
                        "NOT YET RECRUITING": "NOT_YET_RECRUITING",
                        "ACTIVE, NOT RECRUITING": "ACTIVE_NOT_RECRUITING",
                        "ACTIVE NOT RECRUITING": "ACTIVE_NOT_RECRUITING",
                    }

                    # Try direct match first
                    matched_status = status_mapping.get(status_upper)
                    if not matched_status:
                        # Try normalized version (replace spaces and commas with underscores)
                        status_normalized = (
                            status_upper.replace(" ", "_")
                            .replace(",", "")
                            .replace("-", "_")
                        )
                        matched_status = status_mapping.get(status_normalized)

                    if matched_status and matched_status in status_counts:
                        status_counts[matched_status] += 1
                    else:
                        status_counts["UNKNOWN"] += 1

                    # Extract phase
                    protocol = api_json.get("protocolSection", {})
                    design_module = protocol.get("designModule", {})
                    phases = design_module.get("phases", [])
                    if phases:
                        # Use first phase if multiple
                        phase = phases[0]
                        # Normalize phase names
                        if phase == "EARLY_PHASE1":
                            phase_counts["Early Phase 1"] += 1
                        elif phase == "PHASE1":
                            phase_counts["Phase 1"] += 1
                        elif phase == "PHASE2":
                            phase_counts["Phase 2"] += 1
                        elif phase == "PHASE3":
                            phase_counts["Phase 3"] += 1
                        elif phase == "PHASE4":
                            phase_counts["Phase 4"] += 1
                        else:
                            phase_counts["Not applicable"] += 1
                    else:
                        phase_counts["Not applicable"] += 1

                    # Extract funder type
                    sponsor_module = protocol.get("sponsorCollaboratorsModule", {})
                    lead_sponsor = sponsor_module.get("leadSponsor", {})
                    sponsor_class = lead_sponsor.get("class", "").upper()
                    if sponsor_class == "INDUSTRY":
                        funder_type_counts["Industry"] += 1
                    else:
                        # Everything else is Non-Industry
                        funder_type_counts["Non-Industry"] += 1

                return {
                    "status": status_counts,
                    "phase": phase_counts,
                    "funder_type": funder_type_counts,
                    "extracted_count": extracted_count,
                }

        except (sqlite3.Error, Exception) as e:
            logger.error(f"Error getting disease landscape stats: {e}")
            return {
                "status": {},
                "phase": {},
                "funder_type": {"Industry": 0, "Non-Industry": 0},
            }

    def get_disease_landscape_stats_from_json(
        self, cancer_type_tag: str
    ) -> dict[str, Any]:
        """Get disease landscape statistics from pre-computed JSON file.

        Args:
            cancer_type_tag: Normalized cancer type tag

        Returns:
            Dictionary with status, phase, and funder_type counts
        """
        try:
            stats_file = Path(DISEASE_LANDSCAPE_STATS_PATH)
            if not stats_file.exists():
                logger.warning(f"Disease landscape stats file not found: {stats_file}")
                return {
                    "status": {},
                    "phase": {},
                    "funder_type": {"Industry": 0, "Non-Industry": 0},
                    "extracted_count": 0,
                }

            with open(stats_file) as f:
                all_stats = json.load(f)

            # Get stats for this cancer type
            stats = all_stats.get(cancer_type_tag, {})

            if not stats:
                logger.warning(f"No stats found for cancer type: {cancer_type_tag}")
                return {
                    "status": {},
                    "phase": {},
                    "funder_type": {"Industry": 0, "Non-Industry": 0},
                    "extracted_count": 0,
                }

            # Format status for frontend (convert keys to user-friendly names)
            status_counts = stats.get("status", {})
            status_display = {
                "NOT_YET_RECRUITING": status_counts.get("NOT_YET_RECRUITING", 0),
                "RECRUITING": status_counts.get("RECRUITING", 0),
                "ACTIVE_NOT_RECRUITING": status_counts.get("ACTIVE_NOT_RECRUITING", 0),
                "COMPLETED": status_counts.get("COMPLETED", 0),
                "TERMINATED": status_counts.get("TERMINATED", 0),
                "ENROLLING_BY_INVITATION": status_counts.get(
                    "ENROLLING_BY_INVITATION", 0
                ),
                "SUSPENDED": status_counts.get("SUSPENDED", 0),
                "WITHDRAWN": status_counts.get("WITHDRAWN", 0),
                "UNKNOWN": status_counts.get("UNKNOWN", 0),
            }

            return {
                "status": status_display,
                "phase": stats.get("phase", {}),
                "funder_type": stats.get(
                    "funder_type", {"Industry": 0, "Non-Industry": 0}
                ),
                "extracted_count": stats.get("extracted_count", 0),
            }

        except (OSError, json.JSONDecodeError, Exception) as e:
            logger.error(f"Error reading disease landscape stats from JSON: {e}")
            return {
                "status": {},
                "phase": {},
                "funder_type": {"Industry": 0, "Non-Industry": 0},
                "extracted_count": 0,
            }
