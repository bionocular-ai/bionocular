"""Factory for creating clinical trials service components."""

from typing import Optional

from ...app.clinical_trials_service import ClinicalTrialsService
from ...domain.clinical_trial_interfaces import (
    ClinicalTrialParser,
    ClinicalTrialRepository,
    ClinicalTrialsAPIClient,
)
from ..clinical_trials.api_client import ClinicalTrialsGovAPIClient
from ..clinical_trials.parser import ClinicalTrialDataParser
from ..clinical_trials.repository import SQLiteClinicalTrialRepository
from ..config import CLINICAL_TRIAL_DB_PATH


def create_clinical_trials_service(
    cache_db_path: Optional[str] = CLINICAL_TRIAL_DB_PATH,
    api_base_url: str = "https://clinicaltrials.gov/api/v2/studies/",
) -> ClinicalTrialsService:
    """Create a configured ClinicalTrialsService instance.

    Args:
        cache_db_path: Path to SQLite database for caching
        api_base_url: Base URL for ClinicalTrials.gov API

    Returns:
        Configured ClinicalTrialsService instance
    """
    # Create infrastructure components
    api_client: ClinicalTrialsAPIClient = ClinicalTrialsGovAPIClient(
        base_url=api_base_url
    )
    parser: ClinicalTrialParser = ClinicalTrialDataParser()
    repository: ClinicalTrialRepository = SQLiteClinicalTrialRepository(
        db_path=cache_db_path, parser=parser
    )

    # Create and return service
    return ClinicalTrialsService(
        api_client=api_client, repository=repository, parser=parser
    )
