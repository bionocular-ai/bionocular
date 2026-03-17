"""Domain interfaces for clinical trials API operations."""

from abc import ABC, abstractmethod
from typing import Any, Optional

from .clinical_trial_models import ClinicalTrialData


class ClinicalTrialsAPIClient(ABC):
    """Interface for fetching clinical trial data from external API."""

    @abstractmethod
    def fetch_trial_data(self, nct_number: str) -> Optional[dict]:
        """Fetch raw trial data from API.

        Args:
            nct_number: NCT number to fetch

        Returns:
            Raw JSON response or None if error
        """
        pass

    @abstractmethod
    def search_trials_by_condition(
        self, condition: str, status_list: Optional[list[str]] = None
    ) -> list[str]:
        """Search for trials by condition and optional status filter.

        Args:
            condition: Condition/cancer type to search for
            status_list: Optional list of trial statuses to filter by.
                        If None or empty, returns all trials for the condition.

        Returns:
            List of NCT numbers matching the search criteria
        """
        pass


class ClinicalTrialRepository(ABC):
    """Interface for caching clinical trial data."""

    @abstractmethod
    def get_cached_trial(self, nct_number: str) -> Optional[ClinicalTrialData]:
        """Retrieve trial data from cache if available and not expired.

        Args:
            nct_number: NCT number to look up

        Returns:
            ClinicalTrialData if found and not expired, None otherwise
        """
        pass

    @abstractmethod
    def save_trial_to_cache(self, nct_number: str, api_response: dict) -> None:
        """Save API response to cache.

        Args:
            nct_number: NCT number
            api_response: Raw JSON response from API
        """
        pass

    @abstractmethod
    def clear_cache(self, nct_number: Optional[str] = None) -> int:
        """Clear cache entries.

        Args:
            nct_number: If provided, clear only this NCT number. Otherwise, clear all expired entries.

        Returns:
            Number of entries cleared
        """
        pass

    @abstractmethod
    def get_cache_stats(self) -> dict[str, int]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        pass

    @abstractmethod
    def upsert_discovery_record(
        self, nct_number: str, cancer_type_tag: str, current_status: str
    ) -> None:
        """Insert or update a record in the api_discovery table.

        Args:
            nct_number: NCT number
            cancer_type_tag: Normalized cancer type tag
            current_status: Current trial status
        """
        pass

    @abstractmethod
    def get_landscape_stats(self) -> list[dict[str, Any]]:
        """Get landscape statistics grouped by cancer type.

        Returns:
            List of dictionaries with cancer_type, total_api_count, extracted_count
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def batch_upsert_discovery(self, records: list[tuple[str, str, str]]) -> None:
        """Efficiently batch insert discovery records.

        Args:
            records: List of tuples (nct_number, cancer_type_tag, current_status)
        """
        pass

    @abstractmethod
    def get_cached_api_json(self, nct_number: str) -> Optional[dict]:
        """Get raw API JSON from cache without parsing.

        Args:
            nct_number: NCT number to look up

        Returns:
            Raw JSON dict from cache or None if not found/expired
        """
        pass

    @abstractmethod
    def get_cached_trial_api_json(self, nct_number: str) -> Optional[dict]:
        """Get full ClinicalTrials.gov API response JSON from cache for a single trial.

        Args:
            nct_number: NCT number to look up

        Returns:
            Raw API response (protocolSection, resultsSection, etc.) or None if not in cache
        """
        pass

    @abstractmethod
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
            cancer_type_tag: Normalized cancer type tag.
            phase_filter: Optional list of display phase names to include.
            has_abstracts_only: If True, only include trials with abstract/conference/published_year.
            status_filter: Optional list of study_status display values to include.
            sponsor_type_filter: Optional list of "Industry" and/or "Non-Industry".
            skip: Number of trials to skip (pagination).
            limit: Maximum number of trials to return.
            balance_by_modality: If True, return up to per_group trials per modality (balanced view).
            per_group: When balance_by_modality, max trials per modality (default 15).
            modality_filter: If set, return only trials in this modality (normalized name); skip/limit apply within this modality.
            modality_skip: When modality_filter set, skip this many trials in that modality.
            modality_limit: When modality_filter set, return at most this many trials.
            balance_by_group: If set ("stage"|"biomarker"|"line_of_therapy"|"previous_treatment"), return balanced trials per category.
            category_filter: When balance_by_group set, if provided return only this category with pagination (category_skip, category_limit).
            category_skip: When category_filter set, skip this many trials in that category.
            category_limit: When category_filter set, return at most this many trials.

        Returns:
            Tuple of (cards, total, totals_by_modality or None, totals_by_group or None).
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def upsert_extraction_provenance(self, nct_number: str, source_name: str) -> None:
        """Insert or update a record in the extraction_provenance table.

        Args:
            nct_number: NCT number
            source_name: Source name (e.g., 'ASCO 2025', 'ESMO 2024', 'Publication')
        """
        pass

    @abstractmethod
    def batch_upsert_extraction_provenance(
        self, records: list[tuple[str, str]]
    ) -> None:
        """Efficiently batch insert extraction provenance records.

        Args:
            records: List of tuples (nct_number, source_name)
        """
        pass

    @abstractmethod
    def get_disease_landscape_stats(
        self,
        cancer_type_tag: str,
        sponsor_type_filter: list[str] | None = None,
    ) -> dict[str, Any]:
        """Get disease landscape statistics for a specific cancer type.

        Args:
            cancer_type_tag: Normalized cancer type tag
            sponsor_type_filter: If set, only include trials whose lead sponsor
                class is in this list (e.g. ["Industry"]).

        Returns:
            Dictionary with status, phase, and funder_type counts:
            {
                "status": {
                    "NOT_YET_RECRUITING": int,
                    "RECRUITING": int,
                    "ACTIVE_NOT_RECRUITING": int,
                    "COMPLETED": int,
                    "TERMINATED": int,
                    "ENROLLING_BY_INVITATION": int,
                    "SUSPENDED": int,
                    "WITHDRAWN": int,
                    "UNKNOWN": int,
                },
                "phase": {
                    "Early Phase 1": int,
                    "Phase 1": int,
                    "Phase 2": int,
                    "Phase 3": int,
                    "Phase 4": int,
                    "Not applicable": int,
                },
                "funder_type": {
                    "Industry": int,
                    "Non-Industry": int,
                }
            }
        """
        pass

    @abstractmethod
    def get_disease_landscape_stats_from_json(
        self, cancer_type_tag: str
    ) -> dict[str, Any]:
        """Get disease landscape statistics from pre-computed JSON file.

        Args:
            cancer_type_tag: Normalized cancer type tag

        Returns:
            Dictionary with status, phase, and funder_type counts (same format as get_disease_landscape_stats)
        """
        pass

    @abstractmethod
    def get_disease_landscape_stats_from_sqlite(
        self, cancer_type_tag: str
    ) -> dict[str, Any]:
        """Get disease landscape statistics from SQLite database table.

        Args:
            cancer_type_tag: Normalized cancer type tag

        Returns:
            Dictionary with status, phase, and funder_type counts (same format as get_disease_landscape_stats)
        """
        pass

    @abstractmethod
    def get_live_ticker_from_sqlite(self, category: str) -> dict[str, Any]:
        """Get live ticker data (articles and results) from SQLite.

        Args:
            category: Category slug (e.g. "cutaneous-melanoma")

        Returns:
            Dict with "articles" and "results" lists; empty lists if not found.
        """
        pass

    @abstractmethod
    def get_live_ticker_from_json(self, category: str) -> dict[str, Any]:
        """Get live ticker data from pre-computed JSON file.

        Args:
            category: Category slug (e.g. "cutaneous-melanoma")

        Returns:
            Dict with "articles" and "results" lists; empty lists if not found.
        """
        pass

    @abstractmethod
    def get_trial_updates_counts(
        self, cancer_type_tag: str, days: int = 30
    ) -> dict[str, Any]:
        """Count trials first posted or last updated within a rolling window.

        Args:
            cancer_type_tag: Normalized cancer type tag.
            days: Window size in days.

        Returns:
            Dict with new_records_added, updates, window_start_iso, window_end_iso.
        """
        pass

    @abstractmethod
    def get_latest_trial_updates(
        self, cancer_type_tag: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Return the latest trials by last updated/first posted date.

        Args:
            cancer_type_tag: Normalized cancer type tag.
            limit: Maximum number of trials to return.

        Returns:
            List of dicts with nct_id, title, sponsor_name, date_iso, update_type.
        """
        pass


class ClinicalTrialParser(ABC):
    """Interface for parsing API responses into domain models."""

    @abstractmethod
    def parse_api_response(self, api_json: dict) -> ClinicalTrialData:
        """Parse API v2 JSON response into ClinicalTrialData domain model.

        Args:
            api_json: Raw JSON response from ClinicalTrials.gov v2 API

        Returns:
            ClinicalTrialData domain model
        """
        pass

    @abstractmethod
    def extract_status_from_api_json(self, api_json: dict) -> str:
        """Extract trial status from API JSON response.

        Args:
            api_json: Raw JSON response from ClinicalTrials.gov v2 API

        Returns:
            Trial status string or "UNKNOWN" if not found
        """
        pass
