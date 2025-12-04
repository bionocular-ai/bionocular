"""Domain interfaces for clinical trials API operations."""

from abc import ABC, abstractmethod
from typing import Optional

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
