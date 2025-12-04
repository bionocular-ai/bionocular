"""API client for ClinicalTrials.gov v2 API."""

import logging
from typing import Optional

import requests  # type: ignore[import-untyped]

from ...domain.clinical_trial_interfaces import ClinicalTrialsAPIClient

logger = logging.getLogger(__name__)


class ClinicalTrialsGovAPIClient(ClinicalTrialsAPIClient):
    """Implementation of ClinicalTrials.gov v2 API client."""

    def __init__(self, base_url: str = "https://clinicaltrials.gov/api/v2/studies/"):
        """Initialize the API client.

        Args:
            base_url: Base URL for the API endpoint
        """
        self.base_url = base_url

    def fetch_trial_data(self, nct_number: str) -> Optional[dict]:
        """Fetch raw trial data from API.

        Args:
            nct_number: NCT number to fetch

        Returns:
            Raw JSON response or None if error
        """
        if not nct_number:
            logger.warning("No NCT number provided.")
            return None

        api_url = f"{self.base_url}{nct_number}"

        try:
            response = requests.get(api_url, timeout=30)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(
                    f"No clinical trial data found for NCT number: {nct_number} (404 Not Found)"
                )
            else:
                logger.error(
                    f"HTTP error when fetching trial data for {nct_number}: {e}"
                )
            return None
        except requests.exceptions.RequestException as e:
            logger.error(
                f"Network error when fetching trial data for {nct_number}: {e}"
            )
            return None
        except Exception as e:
            logger.error(
                f"Unexpected error when fetching trial data for {nct_number}: {e}"
            )
            return None
