"""SQLite repository for caching clinical trial data."""

import json
import logging
import re as _re
import sqlite3
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from ...domain.clinical_trial_interfaces import (
    ClinicalTrialParser,
    ClinicalTrialRepository,
)
from ...domain.clinical_trial_models import ClinicalTrialData
from ..config import (
    CLINICAL_TRIAL_DB_PATH,
    DISEASE_LANDSCAPE_STATS_PATH,
    LIVE_TICKER_PATH,
)
from .cancer_type_mapping import is_active_status

logger = logging.getLogger(__name__)

# Max number of parsed trial JSON objects to keep in the per-instance LRU cache.
# Each entry is typically 20-80 KB of Python dict. 600 entries ~= 30-50 MB.
_TRIAL_JSON_CACHE_SIZE = 600

# Cache expiration: refresh data after 7 days
CACHE_EXPIRATION_DAYS = 7

# Modality buckets for balancing (must match frontend MODALITY_HEADERS + Other)
_MODALITY_HEADERS = (
    "Monoclonal Antibody",
    "Vaccine",
    "Immunostimulant/Cytokine",
    "Bispecific",
    "CAR-T",
    "NK or Myeloid Cell Therapy",
    "TIL Therapy",
    "Cell Therapy",
    "Gene Therapy",
    "Small Molecule",
    "Antibody-Drug Conjugate",
    "Oncolytic Virus",
    "Chemotherapy",
    "Radiotherapy",
    "Radiopharmaceutical",
    "Photodynamic Therapy",
    "Surgery/Procedure",
    "Device",
)
_MODALITY_OTHER = "Other"
_MODALITY_ALIASES = {
    "monoclonal antibody": "Monoclonal Antibody",
    "mab": "Monoclonal Antibody",
    "vaccine": "Vaccine",
    "immunostimulant/cytokine": "Immunostimulant/Cytokine",
    "immunostimulant": "Immunostimulant/Cytokine",
    "cytokine": "Immunostimulant/Cytokine",
    "bispecific": "Bispecific",
    "bi-specific": "Bispecific",
    "bi-specifics": "Bispecific",
    "car-t": "CAR-T",
    "car t": "CAR-T",
    "nk or myeloid cell therapy": "NK or Myeloid Cell Therapy",
    "nk cell": "NK or Myeloid Cell Therapy",
    "til therapy": "TIL Therapy",
    "til": "TIL Therapy",
    "cell therapy": "Cell Therapy",
    "adoptive cell therapy": "Cell Therapy",
    "gene therapy": "Gene Therapy",
    "small molecule": "Small Molecule",
    "antibody-drug conjugate": "Antibody-Drug Conjugate",
    "adc": "Antibody-Drug Conjugate",
    "oncolytic virus": "Oncolytic Virus",
    "chemotherapy": "Chemotherapy",
    "radiotherapy": "Radiotherapy",
    "radiation": "Radiotherapy",
    "radiation therapy": "Radiotherapy",
    "radiopharmaceutical": "Radiopharmaceutical",
    "photodynamic therapy": "Photodynamic Therapy",
    "pdt": "Photodynamic Therapy",
    "surgery/procedure": "Surgery/Procedure",
    "surgery": "Surgery/Procedure",
    "procedure": "Surgery/Procedure",
    "device": "Device",
}


def _normalize_modality(raw: Optional[str]) -> str:
    """Normalize modality to one of MODALITY_HEADERS or Other (matches frontend)."""
    if not raw or not str(raw).strip():
        return _MODALITY_OTHER
    lower = str(raw).strip().lower()
    if lower in _MODALITY_ALIASES:
        return _MODALITY_ALIASES[lower]
    for h in _MODALITY_HEADERS:
        if h.lower() == lower:
            return h
    return _MODALITY_OTHER


def _parse_modalities(raw: Optional[str]) -> list[str]:
    """Split a potentially semicolon-delimited modality string into normalized buckets.

    E.g. "Vaccine; Immunostimulant/Cytokine" → ["Vaccine", "Immunostimulant/Cytokine"]
    Always returns at least one element (falls back to _MODALITY_OTHER).
    """
    if not raw or not str(raw).strip():
        return [_MODALITY_OTHER]
    parts = [_normalize_modality(p.strip()) for p in str(raw).split(";")]
    # Deduplicate while preserving order
    seen: set[str] = set()
    result = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            result.append(p)
    return result


_GROUP_UNSPECIFIED = "Unspecified"

# Canonical category orders for balance_by_group (match trials_extraction_prompts + frontend)
_STAGE_ORDER = [
    "Stage I",
    "Stage I/II",
    "Stage II",
    "Stage II/III",
    "Stage III",
    "Stage III/IV",
    "Stage IV",
]
_BIOMARKER_ORDER = [
    "BRAF (V600)",
    "PD-L1",
    "HLA-A*02:01",
    "LAG-3",
    "TMB",
    "c-KIT",
    "NRAS",
    "NF1",
    "PRAME",
    "CDKN2A / CDK4",
    "MSI-H / dMMR",
    "GNAQ / GNA11",
    "SF3B1 / EIF1AX",
    "BAP1",
    "MCPyV",
    "PTCH1 / SMO",
    "PIK3CA",
    "EGFR",
    "ctDNA (MRD)",
    "MART-1",
    "gp100",
    "Other",
]
_LINE_OF_THERAPY_ORDER = ["1L", "2L", "3L", "R/R", "Adjuvant", "Neoadjuvant"]
_PREVIOUS_TREATMENT_ORDER = ["Failed IO", "No prior BRAFi", "IO Naive"]


def _parse_group_values(raw: Optional[str]) -> list[str]:
    """Split semicolon- or comma-separated category string; return ['Unspecified'] if empty."""
    if not raw or not str(raw).strip():
        return [_GROUP_UNSPECIFIED]
    parts = [p.strip() for p in _re.split(r"[;,]", str(raw)) if p and p.strip()]
    return parts if parts else [_GROUP_UNSPECIFIED]


def _get_group_order(balance_by_group: str) -> list[str]:
    """Return canonical column order for the given group dimension."""
    if balance_by_group == "stage":
        return list(_STAGE_ORDER)
    if balance_by_group == "biomarker":
        return list(_BIOMARKER_ORDER)
    if balance_by_group == "line_of_therapy":
        return list(_LINE_OF_THERAPY_ORDER)
    if balance_by_group == "previous_treatment":
        return list(_PREVIOUS_TREATMENT_ORDER)
    return []


_BRACKET_RE = _re.compile(r"[\(\[]([^\)\]]+)[\)\]]\s*$")


def _resolve_trial_name(id_module: dict, nct_number: str) -> str:
    """Derive a short, human-readable trial name from identificationModule data.

    Priority:
      1. ``acronym`` field – e.g. "KEYNOTE-006"
      2. Trailing (...) or [...] in ``briefTitle`` – e.g. the "KEYNOTE-006" part
         of "A Phase 3 Study of Pembrolizumab (KEYNOTE-006)"
      3. ``nct_number`` as final fallback.
    """
    acronym = (id_module.get("acronym") or "").strip()
    if acronym:
        return acronym

    brief_title = (id_module.get("briefTitle") or "").strip()
    if brief_title:
        m = _BRACKET_RE.search(brief_title)
        if m:
            return m.group(1).strip()

    return nct_number


def _recreate_trial_categorization_column_order(
    cursor: sqlite3.Cursor, conn: sqlite3.Connection
) -> None:
    """Recreate trial_categorization so cancer_type is the second column (after nct_number)."""
    cursor.execute("PRAGMA table_info(trial_categorization)")
    existing_cols = {r[1] for r in cursor.fetchall()}

    # Desired post-migration schema (target/trial_name intentionally removed).
    desired_cols = [
        "nct_number",
        "cancer_type",
        "modality",
        "treatment_name",
        "biomarker",
        "stage",
        "line_of_therapy",
        "previous_treatment_criteria",
        "extraction_status",
        "error_message",
        "updated_at",
    ]

    cursor.execute(
        """
        CREATE TABLE trial_categorization_new (
            nct_number TEXT PRIMARY KEY,
            cancer_type TEXT,
            modality TEXT,
            treatment_name TEXT,
            biomarker TEXT,
            stage TEXT,
            line_of_therapy TEXT,
            previous_treatment_criteria TEXT,
            extraction_status TEXT,
            error_message TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Build an INSERT ... SELECT that preserves all columns available in the old schema.
    select_exprs: list[str] = []
    insert_cols: list[str] = []
    for col in desired_cols:
        insert_cols.append(col)
        if col in existing_cols:
            select_exprs.append(col)
        else:
            select_exprs.append("NULL")

    cursor.execute(
        f"""
        INSERT INTO trial_categorization_new ({','.join(insert_cols)})
        SELECT {','.join(select_exprs)}
        FROM trial_categorization
        """
    )
    cursor.execute("DROP TABLE trial_categorization")
    cursor.execute(
        "ALTER TABLE trial_categorization_new RENAME TO trial_categorization"
    )


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
        # LRU cache: nct_number -> parsed dict. OrderedDict gives O(1) move-to-end.
        self._json_lru: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
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

                # Create disease_landscape_stats table for pre-computed statistics
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS disease_landscape_stats (
                        cancer_type TEXT PRIMARY KEY,
                        status_json TEXT NOT NULL,
                        phase_json TEXT NOT NULL,
                        funder_type_json TEXT NOT NULL,
                        extracted_count INTEGER DEFAULT 0,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

                # Create live_ticker table (articles + efficacy/safety results per category)
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS live_ticker (
                        category TEXT PRIMARY KEY,
                        articles_json TEXT NOT NULL,
                        results_json TEXT NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

                # Curated categorisation (Modality, Target, Trial_Name) from e.g. trial_categorizer.txt
                # cancer_type is backfilled from api_discovery (one tag per NCT; same DB). Column order: nct_number, cancer_type, ...
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS trial_categorization (
                        nct_number TEXT PRIMARY KEY,
                        cancer_type TEXT,
                        modality TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                # Add cancer_type column to existing DBs that were created before it existed (before creating index on it)
                try:
                    cursor.execute(
                        "ALTER TABLE trial_categorization ADD COLUMN cancer_type TEXT"
                    )
                except sqlite3.OperationalError as e:
                    if "duplicate column name" not in str(e).lower():
                        raise
                for col in (
                    "modality",
                    "treatment_name",
                    "biomarker",
                    "stage",
                    "line_of_therapy",
                    "previous_treatment_criteria",
                    "extraction_status",
                    "error_message",
                ):
                    try:
                        cursor.execute(
                            f"ALTER TABLE trial_categorization ADD COLUMN {col} TEXT"
                        )
                    except sqlite3.OperationalError as e:
                        if "duplicate column name" not in str(e).lower():
                            raise
                # Recreate table so cancer_type is second column if it's currently at the end
                cursor.execute("PRAGMA table_info(trial_categorization)")
                cols = [row[1] for row in cursor.fetchall()]
                if len(cols) >= 2 and cols[1] != "cancer_type":
                    _recreate_trial_categorization_column_order(cursor, conn)
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_trial_categorization_modality ON trial_categorization(modality)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_trial_categorization_cancer_type ON trial_categorization(cancer_type)"
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

    def get_trial_updates_counts(
        self, cancer_type_tag: str, days: int = 30
    ) -> dict[str, Any]:
        """Count trials first posted or last updated (ClinicalTrials.gov API dates) in the window.

        Window is [last_pull - days, last_pull] where last_pull is max(updated_at) from cache.
        Dates are from the API: studyFirstPostDateStruct.date and lastUpdatePostDateStruct.date.

        Returns:
            dict with new_records_added (first posted in window), updates (last updated in window),
            window_end_iso, window_start_iso.
        """

        def _parse_api_date(s: Optional[str]) -> Optional[datetime]:
            if not s or not str(s).strip():
                return None
            s = str(s).strip()
            try:
                if len(s) >= 10:
                    return datetime.strptime(s[:10], "%Y-%m-%d").replace(
                        tzinfo=timezone.utc
                    )
                if len(s) >= 7:
                    return datetime.strptime(s[:7], "%Y-%m").replace(
                        tzinfo=timezone.utc, day=1
                    )
            except ValueError:
                pass
            return None

        if not self.db_path:
            return {
                "new_records_added": 0,
                "updates": 0,
                "window_end_iso": None,
                "window_start_iso": None,
            }

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT max(updated_at) as t FROM clinical_trials_cache")
                row = cursor.fetchone()
                if not row or not row[0]:
                    return {
                        "new_records_added": 0,
                        "updates": 0,
                        "window_end_iso": None,
                        "window_start_iso": None,
                    }
                try:
                    window_end = datetime.fromisoformat(row[0].replace("Z", "+00:00"))
                    if window_end.tzinfo is None:
                        window_end = window_end.replace(tzinfo=timezone.utc)
                except ValueError:
                    window_end = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S").replace(
                        tzinfo=timezone.utc
                    )

                window_start = window_end - timedelta(days=days)

                cursor.execute(
                    """
                    SELECT DISTINCT nct_number
                    FROM api_discovery
                    WHERE cancer_type_tag = ?
                    """,
                    (cancer_type_tag,),
                )
                nct_numbers = [r[0] for r in cursor.fetchall()]

        except sqlite3.Error as e:
            logger.error(f"Error getting trial updates counts: {e}")
            return {
                "new_records_added": 0,
                "updates": 0,
                "window_end_iso": None,
                "window_start_iso": None,
            }

        if not nct_numbers:
            return {
                "new_records_added": 0,
                "updates": 0,
                "window_end_iso": window_end.isoformat(),
                "window_start_iso": window_start.isoformat(),
            }

        api_jsons = self._get_cached_api_json_batch(nct_numbers)
        new_records_added = 0
        updates = 0
        for api_json in api_jsons.values():
            status = (api_json.get("protocolSection") or {}).get("statusModule") or {}
            first_posted = _parse_api_date(
                (status.get("studyFirstPostDateStruct") or {}).get("date")
            )
            if first_posted is not None and window_start <= first_posted <= window_end:
                new_records_added += 1
            last_updated = _parse_api_date(
                (status.get("lastUpdatePostDateStruct") or {}).get("date")
            )
            if last_updated is not None and window_start <= last_updated <= window_end:
                updates += 1

        return {
            "new_records_added": new_records_added,
            "updates": updates,
            "window_end_iso": window_end.isoformat(),
            "window_start_iso": window_start.isoformat(),
        }

    def get_latest_trial_updates(
        self, cancer_type_tag: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Return the latest trials by lastUpdatePostDateStruct (ClinicalTrials.gov API).

        Each item has nct_id, title, sponsor_name, date_iso, update_type ("new" or "updated").
        Sorted by date descending; show up to `limit` trials.
        """

        def _parse_api_date(s: Optional[str]) -> Optional[datetime]:
            if not s or not str(s).strip():
                return None
            s = str(s).strip()
            try:
                if len(s) >= 10:
                    return datetime.strptime(s[:10], "%Y-%m-%d").replace(
                        tzinfo=timezone.utc
                    )
                if len(s) >= 7:
                    return datetime.strptime(s[:7], "%Y-%m").replace(
                        tzinfo=timezone.utc, day=1
                    )
            except ValueError:
                pass
            return None

        if not self.db_path or limit <= 0:
            return []

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT DISTINCT nct_number
                    FROM api_discovery
                    WHERE cancer_type_tag = ?
                    """,
                    (cancer_type_tag,),
                )
                nct_numbers = [r[0] for r in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Error getting latest trial updates: {e}")
            return []

        if not nct_numbers:
            return []

        api_jsons = self._get_cached_api_json_batch(nct_numbers)
        window_end = datetime.now(timezone.utc)
        window_start = window_end - timedelta(days=30)
        rows: list[dict[str, Any]] = []

        for nct_number, api_json in api_jsons.items():
            protocol = api_json.get("protocolSection") or {}
            status = protocol.get("statusModule") or {}
            id_module = protocol.get("identificationModule") or {}
            sponsor_module = protocol.get("sponsorCollaboratorsModule") or {}
            lead_sponsor = sponsor_module.get("leadSponsor") or {}

            last_updated = _parse_api_date(
                (status.get("lastUpdatePostDateStruct") or {}).get("date")
            )
            first_posted = _parse_api_date(
                (status.get("studyFirstPostDateStruct") or {}).get("date")
            )
            date_for_sort = last_updated or first_posted
            if date_for_sort is None:
                continue

            is_new = (
                first_posted is not None and window_start <= first_posted <= window_end
            )
            title = (id_module.get("briefTitle") or "").strip() or nct_number
            sponsor_name = (lead_sponsor.get("name") or "").strip() or None

            rows.append(
                {
                    "nct_id": nct_number,
                    "title": title,
                    "sponsor_name": sponsor_name,
                    "date_iso": date_for_sort.date().isoformat(),
                    "update_type": "new" if is_new else "updated",
                }
            )

        rows.sort(key=lambda r: r["date_iso"], reverse=True)
        return rows[:limit]

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

    def _get_cached_api_json_ignore_expiry(self, nct_number: str) -> Optional[dict]:
        """Get raw API JSON from cache without expiration check (for dashboard display).

        Checks the in-process LRU cache before hitting SQLite.
        """
        if not self.db_path:
            return None
        # LRU hit
        cached = self._json_lru.get(nct_number)
        if cached is not None:
            self._json_lru.move_to_end(nct_number)
            return cached
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT api_response_json FROM clinical_trials_cache WHERE nct_number = ?",
                    (nct_number,),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                parsed = json.loads(row[0])
                # Populate LRU
                self._json_lru[nct_number] = parsed
                self._json_lru.move_to_end(nct_number)
                if len(self._json_lru) > _TRIAL_JSON_CACHE_SIZE:
                    self._json_lru.popitem(last=False)
                return parsed
        except (sqlite3.Error, json.JSONDecodeError) as e:
            logger.warning(f"Error reading cached JSON for {nct_number}: {e}")
            return None

    def _get_cached_api_json_batch(
        self, nct_numbers: list[str]
    ) -> dict[str, dict[str, Any]]:
        """Get raw API JSON for many NCTs in one query, with LRU cache.

        Hits the in-process LRU first; only queries SQLite for cache misses.
        Newly loaded entries are inserted into the LRU (evicting oldest if full).
        """
        if not self.db_path or not nct_numbers:
            return {}

        out: dict[str, dict[str, Any]] = {}
        misses: list[str] = []

        # LRU read pass — O(1) per hit
        for nct in nct_numbers:
            cached = self._json_lru.get(nct)
            if cached is not None:
                self._json_lru.move_to_end(nct)  # mark recently used
                out[nct] = cached
            else:
                misses.append(nct)

        if not misses:
            return out

        # SQLite fetch for misses only
        chunk_size = 500
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                for i in range(0, len(misses), chunk_size):
                    chunk = misses[i : i + chunk_size]
                    placeholders = ",".join("?" * len(chunk))
                    cursor.execute(
                        f"SELECT nct_number, api_response_json FROM clinical_trials_cache WHERE nct_number IN ({placeholders})",
                        chunk,
                    )
                    for row in cursor.fetchall():
                        nct_number, raw_json = row[0], row[1]
                        try:
                            parsed = json.loads(raw_json)
                        except json.JSONDecodeError:
                            continue
                        out[nct_number] = parsed
                        # Insert into LRU, evict oldest if over capacity
                        self._json_lru[nct_number] = parsed
                        self._json_lru.move_to_end(nct_number)
                        if len(self._json_lru) > _TRIAL_JSON_CACHE_SIZE:
                            self._json_lru.popitem(last=False)
        except sqlite3.Error as e:
            logger.warning(f"Error batch reading cached JSON: {e}")
        return out

    def get_cached_trial_api_json(self, nct_number: str) -> Optional[dict]:
        """Get full ClinicalTrials.gov API response JSON from cache for a single trial.

        Returns the raw API response (protocolSection, resultsSection, etc.) for
        use in trial detail views. Returns None if not in cache.
        """
        return self._get_cached_api_json_ignore_expiry(nct_number)

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
        """Get landscape statistics for cancer type bubbles.

        First tries to get from disease_landscape_stats table (pre-computed),
        falls back to computing from api_discovery if table is empty.

        Returns:
            List of dictionaries with cancer_type, bubble_size, total_api_count, extracted_count
        """
        if not self.db_path:
            return []

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Try to get stats from disease_landscape_stats table first
                cursor.execute(
                    """
                    SELECT cancer_type, status_json, extracted_count
                    FROM disease_landscape_stats
                """
                )
                rows = cursor.fetchall()

                if rows:
                    # Use pre-computed stats from table
                    from ..clinical_trials.cancer_type_mapping import ACTIVE_STATUSES

                    stats_list = []
                    for row in rows:
                        status_counts = json.loads(row["status_json"])
                        # Calculate bubble_size from active statuses
                        bubble_size = sum(
                            status_counts.get(status, 0) for status in ACTIVE_STATUSES
                        )
                        # Calculate total_api_count from all statuses
                        total_api_count = sum(status_counts.values())

                        stats_list.append(
                            {
                                "cancer_type": row["cancer_type"],
                                "bubble_size": bubble_size,
                                "total_api_count": total_api_count,
                                "extracted_count": row["extracted_count"],
                            }
                        )
                    return stats_list

                # Fall back to computing from api_discovery if table is empty
                return self._get_landscape_stats_from_api_discovery(conn)

        except (sqlite3.Error, json.JSONDecodeError, Exception) as e:
            logger.error(f"Error getting landscape stats: {e}")
            return []

    def _get_landscape_stats_from_api_discovery(
        self, conn: sqlite3.Connection
    ) -> list[dict[str, Any]]:
        """Get landscape statistics from api_discovery table.

        Args:
            conn: Existing database connection

        Returns:
            List of dictionaries with cancer_type, total_api_count, extracted_count, bubble_size
        """
        try:
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

    def _api_phases_to_display(self, api_phases: list[str]) -> list[str]:
        """Convert API phase values (e.g. PHASE1) to display labels (e.g. Phase 1)."""
        display = []
        for p in api_phases or []:
            if not isinstance(p, str):
                continue
            u = p.upper().strip()
            if u == "EARLY_PHASE1":
                display.append("Early Phase 1")
            elif u == "PHASE1":
                display.append("Phase 1")
            elif u == "PHASE2":
                display.append("Phase 2")
            elif u == "PHASE3":
                display.append("Phase 3")
            elif u == "PHASE4":
                display.append("Phase 4")
            else:
                display.append("Not applicable")
        return display if display else ["Not applicable"]

    def _api_status_to_study_status(self, api_status: str) -> str:
        """Map API status to short study status label for cards."""
        if not api_status:
            return "Unknown"
        u = (api_status or "").upper().strip().replace(" ", "_").replace(",", "")
        if u in ("RECRUITING", "NOT_YET_RECRUITING", "ACTIVE_NOT_RECRUITING"):
            return "Open"
        if u in ("COMPLETED", "TERMINATED", "WITHDRAWN"):
            return "Closed"
        if u == "SUSPENDED":
            return "Suspended"
        if u == "ENROLLING_BY_INVITATION":
            return "Enrolling by invitation"
        return "Unknown"

    def _get_abstract_map(self) -> dict[str, dict[str, Any]]:
        """Build map of NCT to abstract metadata for fast lookup."""
        if not self.db_path:
            return {}

        import re

        nct_map: dict[str, dict[str, Any]] = {}

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT abstract_id, arm_results FROM abstracts")

                rows = cursor.fetchall()
                for row in rows:
                    abstract_id = row["abstract_id"]
                    try:
                        arm_results_str = row["arm_results"]
                        if not arm_results_str:
                            continue

                        # Extract all NCTs mentioned in the blob
                        found_ncts = set(re.findall(r"NCT\d+", arm_results_str))
                        if not found_ncts:
                            continue

                        arm_results = json.loads(arm_results_str)

                        conference = None
                        year = None

                        # Extract conference/year (reused logic)
                        for arm in arm_results.values():
                            attributes = arm.get("attributes", {})

                            # Conference
                            if not conference:
                                for key in ["AttributeType.CONFERENCE", "conference"]:
                                    val = attributes.get(key)
                                    raw = (
                                        val.get("value")
                                        if isinstance(val, dict)
                                        else val
                                    )
                                    if raw and str(raw).lower() not in (
                                        "not found",
                                        "n/a",
                                        "none",
                                        "",
                                    ):
                                        conference = raw
                                        break

                            # Year
                            if not year:
                                for key in [
                                    "AttributeType.PUBLISHED_YEAR",
                                    "published_year",
                                ]:
                                    val = attributes.get(key)
                                    raw = (
                                        val.get("value")
                                        if isinstance(val, dict)
                                        else val
                                    )
                                    if raw and str(raw).lower() not in (
                                        "not found",
                                        "n/a",
                                        "none",
                                        "",
                                    ):
                                        year = raw
                                        break

                            if conference and year:
                                break

                        # Fallback parsing
                        if not conference and abstract_id and "_" in abstract_id:
                            parts = abstract_id.split("_")
                            if len(parts) >= 2:
                                if parts[0].isalpha():
                                    conference = parts[0]
                                if parts[1].isdigit() and len(parts[1]) == 4:
                                    year = parts[1]

                        data = {
                            "abstract_id": abstract_id,
                            "conference": conference,
                            "published_year": year,
                        }

                        for nct in found_ncts:
                            current = nct_map.get(nct)
                            # Prefer data with conference info if we have duplicate NCTs
                            if not current or (
                                not current.get("conference") and conference
                            ):
                                nct_map[nct] = data

                    except (json.JSONDecodeError, Exception):
                        continue

        except Exception as e:
            logger.warning(f"Error building abstract map: {e}")

        return nct_map

    def _get_categorization_map(
        self, conn: sqlite3.Connection, nct_numbers: list[str]
    ) -> dict[str, dict[str, Any]]:
        """Build map of NCT to trial_categorization fields."""
        if not nct_numbers:
            return {}
        out: dict[str, dict[str, Any]] = {}
        chunk_size = 500  # stay under SQLite max bound params
        try:
            cursor = conn.cursor()
            for i in range(0, len(nct_numbers), chunk_size):
                chunk = nct_numbers[i : i + chunk_size]
                placeholders = ",".join("?" * len(chunk))
                cursor.execute(
                    f"""
                    SELECT nct_number, modality, treatment_name, cancer_type,
                           biomarker, stage, line_of_therapy, previous_treatment_criteria
                    FROM trial_categorization
                    WHERE nct_number IN ({placeholders})
                    """,
                    chunk,
                )
                for row in cursor.fetchall():
                    out[row["nct_number"]] = {
                        "modality": row["modality"],
                        "treatment_name": row["treatment_name"],
                        "cancer_type": row["cancer_type"],
                        "biomarker": row["biomarker"],
                        "stage": row["stage"],
                        "line_of_therapy": row["line_of_therapy"],
                        "previous_treatment_criteria": row[
                            "previous_treatment_criteria"
                        ],
                    }
        except sqlite3.Error:
            pass
        return out

    def _get_abstract_data_for_nct(self, nct_number: str) -> dict[str, Any]:
        """Find abstract/publication metadata for an NCT number.

        Args:
            nct_number: NCT ID to search for

        Returns:
            Dict with abstract_id, conference, published_year (or None values)
        """
        if not self.db_path:
            return {}

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                # Search for the NCT number in the arm_results JSON blob
                cursor.execute(
                    """
                    SELECT abstract_id, arm_results
                    FROM abstracts
                    WHERE arm_results LIKE ?
                    LIMIT 1
                    """,
                    (f"%{nct_number}%",),
                )
                row = cursor.fetchone()

                if not row:
                    return {}

                abstract_id = row["abstract_id"]
                arm_results_str = row["arm_results"]

                try:
                    arm_results = json.loads(arm_results_str)

                    # Extract conference and year from attributes
                    conference = None
                    year = None

                    # Look through arms to find attributes
                    for arm in arm_results.values():
                        attributes = arm.get("attributes", {})

                        # Try to find conference
                        if not conference:
                            for key in ["AttributeType.CONFERENCE", "conference"]:
                                val = attributes.get(key)
                                raw = val.get("value") if isinstance(val, dict) else val
                                if raw and str(raw).lower() not in (
                                    "not found",
                                    "n/a",
                                    "none",
                                    "",
                                ):
                                    conference = raw
                                    break

                        # Try to find year
                        if not year:
                            for key in [
                                "AttributeType.PUBLISHED_YEAR",
                                "published_year",
                            ]:
                                val = attributes.get(key)
                                raw = val.get("value") if isinstance(val, dict) else val
                                if raw and str(raw).lower() not in (
                                    "not found",
                                    "n/a",
                                    "none",
                                    "",
                                ):
                                    year = raw
                                    break

                        if conference and year:
                            break

                    # Fallback: parse from abstract_id (e.g., ASCO_2020_10000)
                    if not conference and abstract_id and "_" in abstract_id:
                        parts = abstract_id.split("_")
                        if len(parts) >= 2:
                            # Simple heuristic
                            if parts[0].isalpha():
                                conference = parts[0]
                            if parts[1].isdigit() and len(parts[1]) == 4:
                                year = parts[1]

                    return {
                        "abstract_id": abstract_id,
                        "conference": conference,
                        "published_year": year,
                    }

                except json.JSONDecodeError:
                    return {"abstract_id": abstract_id}

        except Exception as e:
            logger.warning(f"Error getting abstract data for {nct_number}: {e}")
            return {}

    def _trial_passes_dashboard_filters(
        self,
        api_json: dict[str, Any],
        nct_number: str,
        nct_abstract_map: dict[str, dict],
        phase_filter: Optional[list[str]],
        status_filter: Optional[list[str]],
        has_abstracts_only: bool,
        sponsor_type_filter: Optional[list[str]],
    ) -> bool:
        """Return True if this trial passes the dashboard phase/status/abstracts/sponsor filters."""
        if not self.parser:
            return False
        protocol = api_json.get("protocolSection", {})
        design_module = protocol.get("designModule", {})
        sponsor_module = protocol.get("sponsorCollaboratorsModule", {})
        api_phases = design_module.get("phases", [])
        display_phases = self._api_phases_to_display(
            [p for p in api_phases if isinstance(p, str)]
        )
        if phase_filter:
            if not any(p in phase_filter for p in display_phases):
                return False
        status = self.parser.extract_status_from_api_json(api_json)
        study_status = self._api_status_to_study_status(status)
        if status_filter and study_status not in status_filter:
            return False
        abstract_data = nct_abstract_map.get(nct_number, {})
        abstract_id = abstract_data.get("abstract_id")
        conference = abstract_data.get("conference")
        published_year = abstract_data.get("published_year")
        if has_abstracts_only:
            if not abstract_id and not conference and not published_year:
                return False
        lead_sponsor = sponsor_module.get("leadSponsor", {})
        sponsor_class = (lead_sponsor.get("class") or "").upper().strip()
        sponsor_type = "Sponsor" if sponsor_class == "INDUSTRY" else "Non-sponsor"
        if sponsor_type_filter:
            if sponsor_type == "Sponsor" and "Industry" not in sponsor_type_filter:
                return False
            if (
                sponsor_type == "Non-sponsor"
                and "Non-Industry" not in sponsor_type_filter
            ):
                return False
        return True

    def get_dashboard_trials(
        self,
        cancer_type_tag: str,
        phase_filter: Optional[list[str]] = None,
        has_abstracts_only: bool = False,
        status_filter: Optional[list[str]] = None,
        sponsor_type_filter: Optional[list[str]] = None,
        skip: int = 0,
        limit: int = 500,
        balance_by_modality: bool = False,
        per_group: int = 15,
        modality_filter: Optional[str] = None,
        modality_skip: int = 0,
        modality_limit: int = 15,
        balance_by_group: Optional[str] = None,
        category_filter: Optional[str] = None,
        category_skip: int = 0,
        category_limit: int = 15,
    ) -> tuple[
        list[dict[str, Any]], int, Optional[dict[str, int]], Optional[dict[str, int]]
    ]:
        """Get trial card DTOs for dashboard by cancer type.

        Args:
            cancer_type_tag: Normalized cancer type tag (e.g. from api_discovery).
            phase_filter: Optional list of display phase names to include.
            has_abstracts_only: If True, only include trials that have abstract_id or conference or published_year.
            status_filter: Optional list of study_status display values to include.
            sponsor_type_filter: Optional list of "Industry" and/or "Non-Industry" to include.
            skip: Number of trials to skip (pagination).
            limit: Maximum number of trials to return.
            balance_by_modality: If True, return up to per_group trials per modality (balanced columns).
            per_group: When balance_by_modality or balance_by_group, max trials per category (default 15).
            modality_filter: If set, return only this modality with pagination (modality_skip, modality_limit).
            modality_skip, modality_limit: Pagination for single-modality fetch.
            balance_by_group: If set ("stage"|"biomarker"|"line_of_therapy"|"previous_treatment"), return balanced trials per category.
            category_filter: If set with balance_by_group, return only this category with pagination (category_skip, category_limit).
            category_skip, category_limit: Pagination for single-category fetch ("Load more" in one column).

        Returns:
            Tuple of (cards, total, totals_by_modality or None, totals_by_group or None). approval_group set by API layer.
        """
        if not self.db_path or not self.parser:
            return [], 0, None, None

        # Preload abstract map and categorisation (Modality, Target, Trial_Name) for performance
        nct_abstract_map = self._get_abstract_map()

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT DISTINCT nct_number
                    FROM api_discovery
                    WHERE cancer_type_tag = ?
                    ORDER BY nct_number
                    """,
                    (cancer_type_tag,),
                )
                nct_rows = cursor.fetchall()
                all_nct_numbers = [row["nct_number"] for row in nct_rows]
                nct_categorization_map = self._get_categorization_map(
                    conn, all_nct_numbers
                )
        except sqlite3.Error as e:
            logger.error(f"Error getting dashboard trial NCTs: {e}")
            return [], 0, None, None

        # Single-modality pagination: return trials for one modality only (for "Load more" in a column)
        if modality_filter and nct_categorization_map:
            by_modality: dict[str, list[str]] = {}
            seen_in_mod: dict[str, set[str]] = {}  # dedup per modality bucket
            for nct in all_nct_numbers:
                cat = nct_categorization_map.get(nct, {})
                for mod in _parse_modalities(cat.get("modality")):
                    if mod not in by_modality:
                        by_modality[mod] = []
                        seen_in_mod[mod] = set()
                    if nct not in seen_in_mod[mod]:
                        by_modality[mod].append(nct)
                        seen_in_mod[mod].add(nct)
            normalized_filter = _normalize_modality(modality_filter)
            ncts_for_modality = by_modality.get(normalized_filter, [])
            nct_numbers_to_process = ncts_for_modality
            effective_limit = modality_limit
            use_modality_pagination = True
        else:
            use_modality_pagination = False

        if not use_modality_pagination:
            nct_numbers_to_process = all_nct_numbers

        # Single-category pagination: return trials for one category only ("Load more" in Stage/Biomarker/etc. column)
        use_category_pagination = False
        totals_by_group: Optional[dict[str, int]] = None
        group_field = {
            "stage": "stage",
            "biomarker": "biomarker",
            "line_of_therapy": "line_of_therapy",
            "previous_treatment": "previous_treatment_criteria",
        }.get(balance_by_group or "", "")
        if (
            balance_by_group
            and group_field
            and category_filter is not None
            and nct_categorization_map
        ):
            by_group: dict[str, list[str]] = {}
            seen_in_grp: dict[str, set[str]] = {}
            for nct in all_nct_numbers:
                cat = nct_categorization_map.get(nct, {})
                raw = cat.get(group_field)
                for key in _parse_group_values(raw):
                    if key not in by_group:
                        by_group[key] = []
                        seen_in_grp[key] = set()
                    if nct not in seen_in_grp[key]:
                        by_group[key].append(nct)
                        seen_in_grp[key].add(nct)
            cat_label = (category_filter or "").strip()
            ncts_for_category = by_group.get(cat_label, [])
            nct_numbers_to_process = ncts_for_category
            use_category_pagination = True

        # Optionally restrict to a balanced set (up to per_group per category) for Stage/Biomarker/Line/Previous treatment
        if (
            not use_modality_pagination
            and not use_category_pagination
            and balance_by_group
            and group_field
            and nct_categorization_map
        ):
            by_group_bal: dict[str, list[str]] = {}
            seen_in_grp_bal: dict[str, set[str]] = {}
            for nct in all_nct_numbers:
                cat = nct_categorization_map.get(nct, {})
                raw = cat.get(group_field)
                for key in _parse_group_values(raw):
                    if key not in by_group_bal:
                        by_group_bal[key] = []
                        seen_in_grp_bal[key] = set()
                    if nct not in seen_in_grp_bal[key]:
                        by_group_bal[key].append(nct)
                        seen_in_grp_bal[key].add(nct)
            order_grp = _get_group_order(balance_by_group)
            order_grp = (
                order_grp
                + [k for k in by_group_bal if k not in order_grp]
                + [_GROUP_UNSPECIFIED]
            )
            nct_numbers_to_process = []
            seen_in_process_grp: set[str] = set()
            for key in order_grp:
                for nct in by_group_bal.get(key, [])[:per_group]:
                    if nct not in seen_in_process_grp:
                        nct_numbers_to_process.append(nct)
                        seen_in_process_grp.add(nct)
            totals_by_group = {k: 0 for k in by_group_bal}
            all_ncts_with_grp = [
                (nct, k) for k, ncts in by_group_bal.items() for nct in ncts
            ]
            for count_start in range(0, len(all_ncts_with_grp), 500):
                count_chunk = all_ncts_with_grp[count_start : count_start + 500]
                count_ncts = [nct for nct, _ in count_chunk]
                count_json = self._get_cached_api_json_batch(count_ncts)
                for nct_number, k in count_chunk:
                    api_json = count_json.get(nct_number)
                    if api_json and self._trial_passes_dashboard_filters(
                        api_json,
                        nct_number,
                        nct_abstract_map,
                        phase_filter,
                        status_filter,
                        has_abstracts_only,
                        sponsor_type_filter,
                    ):
                        totals_by_group[k] += 1

        # Optionally restrict to a balanced set (up to per_group per modality) so each column has trials
        totals_by_modality: Optional[dict[str, int]] = None
        if not use_modality_pagination and not use_category_pagination:
            if balance_by_modality and nct_categorization_map:
                by_modality_bal: dict[str, list[str]] = {}
                seen_in_bal: dict[str, set[str]] = {}  # dedup per modality bucket
                for nct in all_nct_numbers:
                    cat = nct_categorization_map.get(nct, {})
                    for mod in _parse_modalities(cat.get("modality")):
                        if mod not in by_modality_bal:
                            by_modality_bal[mod] = []
                            seen_in_bal[mod] = set()
                        if nct not in seen_in_bal[mod]:
                            by_modality_bal[mod].append(nct)
                            seen_in_bal[mod].add(nct)
                order = list(_MODALITY_HEADERS) + [_MODALITY_OTHER]
                nct_numbers_to_process = []
                seen_in_process: set[str] = set()
                for mod in order:
                    for nct in by_modality_bal.get(mod, [])[:per_group]:
                        if nct not in seen_in_process:
                            nct_numbers_to_process.append(nct)
                            seen_in_process.add(nct)
                for mod, ncts in by_modality_bal.items():
                    if mod not in order:
                        for nct in ncts[:per_group]:
                            if nct not in seen_in_process:
                                nct_numbers_to_process.append(nct)
                                seen_in_process.add(nct)
                # Count filtered trials per modality so the UI can show overall category totals
                totals_by_modality = {mod: 0 for mod in by_modality_bal}
                all_ncts_with_mod = [
                    (nct, mod) for mod, ncts in by_modality_bal.items() for nct in ncts
                ]
                for count_start in range(0, len(all_ncts_with_mod), 500):
                    count_chunk = all_ncts_with_mod[count_start : count_start + 500]
                    count_ncts = [nct for nct, _ in count_chunk]
                    count_json = self._get_cached_api_json_batch(count_ncts)
                    for nct_number, mod in count_chunk:
                        api_json = count_json.get(nct_number)
                        if api_json and self._trial_passes_dashboard_filters(
                            api_json,
                            nct_number,
                            nct_abstract_map,
                            phase_filter,
                            status_filter,
                            has_abstracts_only,
                            sponsor_type_filter,
                        ):
                            totals_by_modality[mod] += 1

        # When returning a balanced set per modality/group, return all of it (do not apply request limit)
        # When single-modality or single-category pagination, use skip/limit for that dimension
        if use_modality_pagination:
            effective_skip = modality_skip
            effective_limit = modality_limit
        elif use_category_pagination:
            effective_skip = category_skip
            effective_limit = category_limit
        elif balance_by_modality or (balance_by_group and group_field):
            effective_skip = skip
            effective_limit = len(nct_numbers_to_process)
        else:
            effective_skip = skip
            effective_limit = limit

        # Process in chunks so we don't hold 4000+ parsed JSONs in memory (bottleneck on 512MB)
        CARD_CHUNK_SIZE = 500
        cards: list[dict[str, Any]] = []
        total_matching = 0
        for chunk_start in range(0, len(nct_numbers_to_process), CARD_CHUNK_SIZE):
            chunk_ncts = nct_numbers_to_process[
                chunk_start : chunk_start + CARD_CHUNK_SIZE
            ]
            chunk_json = self._get_cached_api_json_batch(chunk_ncts)
            for nct_number in chunk_ncts:
                api_json = chunk_json.get(nct_number)
                if not api_json:
                    continue

                protocol = api_json.get("protocolSection", {})
                design_module = protocol.get("designModule", {})
                sponsor_module = protocol.get("sponsorCollaboratorsModule", {})
                api_phases = design_module.get("phases", [])
                display_phases = self._api_phases_to_display(
                    [p for p in api_phases if isinstance(p, str)]
                )

                if phase_filter:
                    if not any(p in phase_filter for p in display_phases):
                        continue

                trial_data = self.parser.parse_api_response(api_json)
                status = self.parser.extract_status_from_api_json(api_json)
                study_status = self._api_status_to_study_status(status)

                if status_filter and study_status not in status_filter:
                    continue

                abstract_data = nct_abstract_map.get(nct_number, {})
                abstract_id = abstract_data.get("abstract_id")
                conference = abstract_data.get("conference")
                published_year = abstract_data.get("published_year")
                if has_abstracts_only:
                    if not abstract_id and not conference and not published_year:
                        continue

                lead_sponsor = sponsor_module.get("leadSponsor", {})
                sponsor_class = (lead_sponsor.get("class") or "").upper().strip()
                sponsor_type = (
                    "Sponsor" if sponsor_class == "INDUSTRY" else "Non-sponsor"
                )
                if sponsor_type_filter:
                    if (
                        sponsor_type == "Sponsor"
                        and "Industry" not in sponsor_type_filter
                    ):
                        continue
                    if (
                        sponsor_type == "Non-sponsor"
                        and "Non-Industry" not in sponsor_type_filter
                    ):
                        continue

                total_matching += 1
                if total_matching <= effective_skip:
                    continue
                if len(cards) >= effective_limit:
                    continue

                sponsor_name = (lead_sponsor.get("name") or "").strip() or None

                # Use clean treatment names from interventions[].name (e.g. "pembrolizumab", "placebo"),
                # not armGroups[].interventionNames (e.g. "Biological: pembrolizumab").
                arms_interventions = protocol.get("armsInterventionsModule", {})
                interventions = arms_interventions.get("interventions", [])
                drug_parts = []
                for item in interventions:
                    name = (item.get("name") or "").strip()
                    if name and name not in drug_parts:
                        drug_parts.append(name)
                drug_name = ", ".join(drug_parts) if drug_parts else None

                phase_display = (
                    ", ".join(display_phases) if display_phases else "Not applicable"
                )

                cat = nct_categorization_map.get(nct_number, {})

                # Resolve trial name from clinical_trials_cache identificationModule:
                #   1. acronym field (e.g. "KEYNOTE-006")
                #   2. trailing (...) or [...] in briefTitle (e.g. "A Study of X (KEYNOTE-006)")
                #   3. NCT number as final fallback
                id_module = protocol.get("identificationModule", {})
                title = _resolve_trial_name(id_module, nct_number)

                card = {
                    "nct_id": nct_number,
                    "title": title,
                    "drug_name": drug_name,
                    "sponsor_name": sponsor_name,
                    "enrollment_count": trial_data.number_of_patients,
                    "phase": phase_display,
                    "study_status": study_status,
                    "sponsor_type": sponsor_type,
                    "arm_labels": [
                        (arm.arm_label or "") or (arm.generic_name or "")
                        for arm in (trial_data.treatment_arms or [])
                    ],
                    "abstract_id": abstract_id,
                    "conference": conference,
                    "published_year": published_year,
                }
                # Always set trial_name so the frontend has a consistent field
                card["trial_name"] = title
                if cat:
                    card["modality"] = cat.get("modality")
                    card["treatment_name"] = cat.get("treatment_name")
                    card["stage"] = cat.get("stage")
                    card["biomarker"] = cat.get("biomarker")
                    card["line_of_therapy"] = cat.get("line_of_therapy")
                    card["previous_treatment_criteria"] = cat.get(
                        "previous_treatment_criteria"
                    )
                cards.append(card)

        return cards, total_matching, totals_by_modality, totals_by_group

    def get_disease_landscape_stats(
        self,
        cancer_type_tag: str,
        sponsor_type_filter: list[str] | None = None,
    ) -> dict[str, Any]:
        """Get disease landscape statistics using a single SQL query via json_extract.

        Replaces the previous N+1 per-NCT Python loop with a single JOIN + GROUP BY
        query so we never load full JSON blobs into Python memory for stats.

        Args:
            cancer_type_tag: Normalized cancer type tag
            sponsor_type_filter: If set, only include trials whose lead sponsor
                class is in this list (e.g. ["Industry"] or ["Non-Industry"]).

        Returns:
            Dictionary with status, phase, and funder_type counts
        """
        _empty = {
            "status": {},
            "phase": {},
            "funder_type": {"Industry": 0, "Non-Industry": 0},
        }
        if not self.db_path or not self.parser:
            return _empty

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # ── Count extracted trials ──────────────────────────────────────
                cursor.execute(
                    """
                    SELECT COUNT(DISTINCT ep.nct_number) AS extracted_count
                    FROM extraction_provenance ep
                    INNER JOIN api_discovery ad ON ep.nct_number = ad.nct_number
                    WHERE ad.cancer_type_tag = ?
                    """,
                    (cancer_type_tag,),
                )
                row = cursor.fetchone()
                extracted_count = row["extracted_count"] if row else 0

                # ── Single-pass stats query using json_extract ──────────────────
                # Pull only the 3 scalar fields we actually need from each JSON blob;
                # SQLite parses the JSON server-side so Python never allocates the
                # full object tree for every trial.
                cursor.execute(
                    """
                    SELECT
                        json_extract(c.api_response_json,
                            '$.protocolSection.statusModule.overallStatus') AS raw_status,
                        json_extract(c.api_response_json,
                            '$.protocolSection.designModule.phases[0]')     AS raw_phase,
                        upper(ifnull(
                            json_extract(c.api_response_json,
                                '$.protocolSection.sponsorCollaboratorsModule.leadSponsor.class'),
                            '')) AS sponsor_class
                    FROM clinical_trials_cache c
                    INNER JOIN api_discovery ad ON ad.nct_number = c.nct_number
                    WHERE ad.cancer_type_tag = ?
                    """,
                    (cancer_type_tag,),
                )
                rows = cursor.fetchall()

                # ── Map API constants → display keys ───────────────────────────
                _STATUS_MAP: dict[str, str] = {
                    "NOT_YET_RECRUITING": "NOT_YET_RECRUITING",
                    "RECRUITING": "RECRUITING",
                    "ACTIVE_NOT_RECRUITING": "ACTIVE_NOT_RECRUITING",
                    "COMPLETED": "COMPLETED",
                    "TERMINATED": "TERMINATED",
                    "ENROLLING_BY_INVITATION": "ENROLLING_BY_INVITATION",
                    "SUSPENDED": "SUSPENDED",
                    "WITHDRAWN": "WITHDRAWN",
                    # common variants stored in older cache rows
                    "NOT YET RECRUITING": "NOT_YET_RECRUITING",
                    "ACTIVE, NOT RECRUITING": "ACTIVE_NOT_RECRUITING",
                    "ACTIVE NOT RECRUITING": "ACTIVE_NOT_RECRUITING",
                }
                _PHASE_MAP: dict[str, str] = {
                    "EARLY_PHASE1": "Early Phase 1",
                    "PHASE1": "Phase 1",
                    "PHASE2": "Phase 2",
                    "PHASE3": "Phase 3",
                    "PHASE4": "Phase 4",
                }

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
                funder_type_counts: dict[str, int] = {"Industry": 0, "Non-Industry": 0}

                for row in rows:
                    sponsor_class: str = row["sponsor_class"] or ""
                    is_industry = sponsor_class == "INDUSTRY"
                    trial_funder = "Industry" if is_industry else "Non-Industry"

                    # Apply sponsor_type_filter without loading the full JSON
                    if sponsor_type_filter and trial_funder not in sponsor_type_filter:
                        continue

                    # Status
                    raw_status: str = (row["raw_status"] or "").upper().strip()
                    mapped = _STATUS_MAP.get(raw_status)
                    if not mapped:
                        norm = (
                            raw_status.replace(" ", "_")
                            .replace(",", "")
                            .replace("-", "_")
                        )
                        mapped = _STATUS_MAP.get(norm)
                    status_counts[mapped if mapped else "UNKNOWN"] += 1

                    # Phase
                    raw_phase: str = (row["raw_phase"] or "").upper().strip()
                    phase_counts[_PHASE_MAP.get(raw_phase, "Not applicable")] += 1

                    # Funder
                    funder_type_counts[trial_funder] += 1

                return {
                    "status": status_counts,
                    "phase": phase_counts,
                    "funder_type": funder_type_counts,
                    "extracted_count": extracted_count,
                }

        except sqlite3.Error as e:
            logger.error(f"Error getting disease landscape stats: {e}")
            return _empty

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

    def get_disease_landscape_stats_from_sqlite(
        self, cancer_type_tag: str
    ) -> dict[str, Any]:
        """Get disease landscape statistics from SQLite database.

        Args:
            cancer_type_tag: Normalized cancer type tag

        Returns:
            Dictionary with status, phase, and funder_type counts
        """
        if not self.db_path:
            return {
                "status": {},
                "phase": {},
                "funder_type": {"Industry": 0, "Non-Industry": 0},
                "extracted_count": 0,
            }

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Query disease_landscape_stats table
                cursor.execute(
                    """
                    SELECT status_json, phase_json, funder_type_json, extracted_count
                    FROM disease_landscape_stats
                    WHERE cancer_type = ?
                    """,
                    (cancer_type_tag,),
                )

                row = cursor.fetchone()
                if not row:
                    logger.warning(
                        f"No stats found in SQLite for cancer type: {cancer_type_tag}"
                    )
                    return {
                        "status": {},
                        "phase": {},
                        "funder_type": {"Industry": 0, "Non-Industry": 0},
                        "extracted_count": 0,
                    }

                # Parse JSON fields
                status_counts = json.loads(row["status_json"])
                phase_counts = json.loads(row["phase_json"])
                funder_type_counts = json.loads(row["funder_type_json"])
                extracted_count = row["extracted_count"]

                # Format status for frontend (convert keys to user-friendly names)
                status_display = {
                    "NOT_YET_RECRUITING": status_counts.get("NOT_YET_RECRUITING", 0),
                    "RECRUITING": status_counts.get("RECRUITING", 0),
                    "ACTIVE_NOT_RECRUITING": status_counts.get(
                        "ACTIVE_NOT_RECRUITING", 0
                    ),
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
                    "phase": phase_counts,
                    "funder_type": funder_type_counts,
                    "extracted_count": extracted_count,
                }

        except (sqlite3.Error, json.JSONDecodeError, Exception) as e:
            logger.error(f"Error reading disease landscape stats from SQLite: {e}")
            return {
                "status": {},
                "phase": {},
                "funder_type": {"Industry": 0, "Non-Industry": 0},
                "extracted_count": 0,
            }

    def get_live_ticker_from_sqlite(self, category: str) -> dict[str, Any]:
        """Get live ticker data from SQLite live_ticker table."""
        empty: dict[str, Any] = {"articles": [], "results": []}
        if not self.db_path:
            return empty
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT articles_json, results_json
                    FROM live_ticker
                    WHERE category = ?
                    """,
                    (category,),
                )
                row = cursor.fetchone()
                if not row:
                    return empty
                return {
                    "articles": json.loads(row["articles_json"]),
                    "results": json.loads(row["results_json"]),
                }
        except (sqlite3.Error, json.JSONDecodeError, Exception) as e:
            logger.error(f"Error reading live ticker from SQLite: {e}")
            return empty

    def get_live_ticker_from_json(self, category: str) -> dict[str, Any]:
        """Get live ticker data from pre-computed JSON file."""
        empty: dict[str, Any] = {"articles": [], "results": []}
        try:
            path = Path(LIVE_TICKER_PATH)
            if not path.exists():
                logger.warning(f"Live ticker file not found: {path}")
                return empty
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            payload = data.get(category, {})
            return {
                "articles": payload.get("articles", []),
                "results": payload.get("results", []),
            }
        except (OSError, json.JSONDecodeError, Exception) as e:
            logger.error(f"Error reading live ticker from JSON: {e}")
            return empty
