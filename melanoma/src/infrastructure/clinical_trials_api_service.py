"""Legacy compatibility wrapper for ClinicalTrialsAPIService.

This module provides backward compatibility for existing code.
New code should use ClinicalTrialsService from app.clinical_trials_service
or create instances via clinical_trials.factory.create_clinical_trials_service().

DEPRECATED: This module is kept for backward compatibility only.
"""

import logging
from typing import Optional, Union

from ..app.clinical_trials_service import ClinicalTrialsService
from ..domain.clinical_trial_models import ClinicalTrialData
from ..domain.extraction_models import AttributeType
from ..infrastructure.clinical_trials.factory import create_clinical_trials_service
from .config import CLINICAL_TRIAL_DB_PATH, DB_PATH

logger = logging.getLogger(__name__)

# Re-export for backward compatibility
__all__ = ["ClinicalTrialsAPIService", "ClinicalTrialData"]


class ClinicalTrialsAPIService:
    """Legacy compatibility wrapper for ClinicalTrialsAPIService.

    This class wraps the new modular ClinicalTrialsService to maintain
    backward compatibility with existing code.

    DEPRECATED: Use ClinicalTrialsService directly or via factory.
    """

    def __init__(
        self,
        db_path: Optional[str] = DB_PATH,
        cache_db_path: Optional[str] = CLINICAL_TRIAL_DB_PATH,
    ):
        """Initialize the service (backward compatibility wrapper).

        Args:
            db_path: Legacy parameter (kept for compatibility, not used)
            cache_db_path: Path to the SQLite database for caching API responses
        """
        # Create the new modular service
        self._service: ClinicalTrialsService = create_clinical_trials_service(
            cache_db_path=cache_db_path
        )
        self.db_path = db_path  # Kept for backward compatibility
        self.cache_db_path = cache_db_path
        logger.warning(
            "ClinicalTrialsAPIService is deprecated. "
            "Use ClinicalTrialsService or create_clinical_trials_service() instead."
        )

    def get_trial_data(self, nct_number: str) -> Optional[ClinicalTrialData]:
        """Get clinical trial data for a given NCT number."""
        return self._service.get_trial_data(nct_number)

    def get_attribute_value(
        self, nct_number: str, attribute_type: AttributeType
    ) -> Optional[Union[str, bool, int, float]]:
        """Get a specific attribute value for a given NCT number."""
        return self._service.get_attribute_value(nct_number, attribute_type)

    def get_multiple_attributes(
        self,
        nct_number: str,
        attribute_types: list[AttributeType],
        arm_info: Optional[dict] = None,
    ) -> dict[AttributeType, Optional[Union[str, bool, int, float]]]:
        """Get multiple attribute values for a given NCT number."""
        return self._service.get_multiple_attributes(
            nct_number, attribute_types, arm_info
        )

    def test_connection(self) -> bool:
        """Test the API connection."""
        # Simple test by trying to fetch a known NCT
        test_nct = "NCT02362594"
        result = self._service.get_trial_data(test_nct)
        return result is not None

    def clear_cache(self, nct_number: Optional[str] = None) -> int:
        """Clear cache entries."""
        return self._service.clear_cache(nct_number)

    def get_cache_stats(self) -> dict[str, int]:
        """Get cache statistics."""
        return self._service.get_cache_stats()

    # Legacy methods that may not be needed but kept for compatibility
    def _get_abstracts_fallback(
        self, nct_number: str, attribute_types: list[AttributeType]
    ) -> dict[AttributeType, Optional[Union[str, bool, int, float]]]:
        """Fallback to abstracts table (legacy method, returns empty dict)."""
        logger.warning("_get_abstracts_fallback is deprecated and returns empty dict")
        return {}

    def get_database_schema(self) -> dict[str, list[str]]:
        """Get database schema (legacy method, returns empty dict)."""
        logger.warning("get_database_schema is deprecated and returns empty dict")
        return {}
