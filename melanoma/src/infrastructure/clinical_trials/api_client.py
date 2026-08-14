"""API client for ClinicalTrials.gov v2 API."""

import logging
import re
import time
from datetime import date
from typing import Optional

import requests  # type: ignore[import-untyped]

from ...domain.clinical_trial_interfaces import ClinicalTrialsAPIClient

logger = logging.getLogger(__name__)

# NCT number validation pattern
NCT_PATTERN = re.compile(r"^NCT\d{8}$")


class ClinicalTrialsGovAPIClient(ClinicalTrialsAPIClient):
    """Implementation of ClinicalTrials.gov v2 API client with robust error handling."""

    def __init__(
        self,
        base_url: str = "https://clinicaltrials.gov/api/v2/studies/",
        search_base_url: str = "https://clinicaltrials.gov/api/v2/studies",
        max_retries: int = 3,
        retry_delay: float = 2.0,
        timeout: int = 60,
    ):
        """Initialize the API client.

        Args:
            base_url: Base URL for fetching individual studies
            search_base_url: Base URL for searching studies
            max_retries: Maximum number of retry attempts for failed requests
            retry_delay: Base delay in seconds for exponential backoff
            timeout: Request timeout in seconds
        """
        self.base_url = base_url
        self.search_base_url = search_base_url
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout

        # Use session for connection pooling and better performance
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Bionocular-ClinicalTrials-Client/1.0",
                "Accept": "application/json",
            }
        )

    def _validate_nct_number(self, nct_number: str) -> bool:
        """Validate NCT number format.

        Args:
            nct_number: NCT number to validate

        Returns:
            True if valid, False otherwise
        """
        if not nct_number or not isinstance(nct_number, str):
            return False
        return bool(NCT_PATTERN.match(nct_number.upper()))

    def fetch_trial_data(self, nct_number: str) -> Optional[dict]:
        """Fetch raw trial data from API with robust error handling and retries.

        Args:
            nct_number: NCT number to fetch

        Returns:
            Raw JSON response or None if error
        """
        if not nct_number:
            logger.warning("No NCT number provided.")
            return None

        # Validate NCT number format
        if not self._validate_nct_number(nct_number):
            logger.warning(f"Invalid NCT number format: {nct_number}")
            return None

        # Normalize to uppercase
        nct_number = nct_number.upper()
        api_url = f"{self.base_url}{nct_number}"

        # Retry logic with exponential backoff
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(api_url, timeout=self.timeout)
                response.raise_for_status()

                # Validate response is JSON
                try:
                    data = response.json()
                except ValueError as e:
                    logger.error(f"Invalid JSON response for {nct_number}: {e}")
                    return None

                # Basic validation of response structure
                if not isinstance(data, dict):
                    logger.error(
                        f"Unexpected response type for {nct_number}: {type(data)}"
                    )
                    return None

                return data

            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if e.response else None

                # Don't retry on 404 (trial doesn't exist)
                if status_code == 404:
                    logger.warning(
                        f"No clinical trial data found for NCT number: {nct_number} (404 Not Found)"
                    )
                    return None

                # Retry on server errors (5xx) and rate limiting (429)
                if status_code and (status_code >= 500 or status_code == 429):
                    if attempt < self.max_retries - 1:
                        wait_time = self.retry_delay * (2**attempt)
                        logger.warning(
                            f"HTTP {status_code} error for {nct_number}, "
                            f"retrying in {wait_time}s (attempt {attempt + 1}/{self.max_retries})"
                        )
                        time.sleep(wait_time)
                        continue

                # Don't retry on client errors (4xx except 429)
                logger.error(
                    f"HTTP {status_code} error when fetching trial data for {nct_number}: {e}"
                )
                return None

            except requests.exceptions.Timeout:
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (attempt + 1)
                    logger.warning(
                        f"Timeout fetching {nct_number}, "
                        f"retrying in {wait_time}s (attempt {attempt + 1}/{self.max_retries})"
                    )
                    time.sleep(wait_time)
                    continue
                logger.error(
                    f"Timeout after {self.max_retries} attempts for {nct_number}"
                )
                return None

            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (attempt + 1)
                    logger.warning(
                        f"Network error for {nct_number}, "
                        f"retrying in {wait_time}s (attempt {attempt + 1}/{self.max_retries}): {e}"
                    )
                    time.sleep(wait_time)
                    continue
                logger.error(
                    f"Network error when fetching trial data for {nct_number} after {self.max_retries} attempts: {e}"
                )
                return None

            except Exception as e:
                logger.error(
                    f"Unexpected error when fetching trial data for {nct_number}: {e}",
                    exc_info=True,
                )
                return None

        return None

    def search_trials_by_condition(
        self,
        condition: str,
        status_list: Optional[list[str]] = None,
        last_update_after: Optional[date] = None,
    ) -> list[str]:
        """Search for trials by condition and optional status / update-date filters.

        Args:
            condition: Condition/cancer type to search for
            status_list: Optional list of trial statuses to filter by.
                        If None or empty, returns all trials for the condition.
            last_update_after: Optional inclusive lower bound on
                LastUpdatePostDate. When set, only trials updated on or after
                this date are returned (used for incremental syncs).

        Returns:
            List of NCT numbers matching the search criteria
        """
        nct_numbers: list[str] = []
        page_token: Optional[str] = None

        try:
            while True:
                # Build query parameters.
                # AREA[Condition] restricts the match to the trial's own
                # conditions. Plain query.cond is an Essie expression that also
                # spans BriefTitle, OfficialTitle, ConditionMeshTerm and
                # ConditionAncestorTerm, so it pulls in trials that never name
                # the condition (measured: 3708 hits vs 3411, a strict subset).
                term_clauses = [f"AREA[Condition]{condition}"]
                if last_update_after is not None:
                    term_clauses.append(
                        f"AREA[LastUpdatePostDate]"
                        f"RANGE[{last_update_after.isoformat()},MAX]"
                    )

                request_params: dict[str, any] = {
                    "query.term": " AND ".join(term_clauses),
                    "pageSize": 100,  # Maximum page size
                }

                # Add status filters as comma-separated string (only if provided)
                if status_list:
                    request_params["filter.overallStatus"] = ",".join(status_list)
                # If status_list is None or empty, don't add filter - get all trials

                if page_token:
                    request_params["pageToken"] = page_token

                # Make API request with retries
                response = None
                for attempt in range(self.max_retries):
                    try:
                        response = self.session.get(
                            self.search_base_url,
                            params=request_params,
                            timeout=self.timeout,
                        )
                        response.raise_for_status()
                        break
                    except requests.exceptions.HTTPError as e:
                        status_code = e.response.status_code if e.response else None
                        if status_code == 429:  # Rate limited
                            if attempt < self.max_retries - 1:
                                wait_time = self.retry_delay * (2**attempt)
                                logger.warning(
                                    f"Rate limited for condition '{condition}', "
                                    f"waiting {wait_time}s before retry {attempt + 1}/{self.max_retries}"
                                )
                                time.sleep(wait_time)
                                continue
                        elif status_code and status_code >= 500:
                            # Retry on server errors
                            if attempt < self.max_retries - 1:
                                wait_time = self.retry_delay * (2**attempt)
                                logger.warning(
                                    f"Server error {status_code} for condition '{condition}', "
                                    f"retrying in {wait_time}s (attempt {attempt + 1}/{self.max_retries})"
                                )
                                time.sleep(wait_time)
                                continue
                        raise
                    except requests.exceptions.Timeout:
                        if attempt < self.max_retries - 1:
                            wait_time = self.retry_delay * (attempt + 1)
                            logger.warning(
                                f"Timeout searching for '{condition}', "
                                f"retrying in {wait_time}s (attempt {attempt + 1}/{self.max_retries})"
                            )
                            time.sleep(wait_time)
                            continue
                        raise
                    except requests.exceptions.RequestException as e:
                        if attempt < self.max_retries - 1:
                            wait_time = self.retry_delay * (attempt + 1)
                            logger.warning(
                                f"Request error for condition '{condition}', "
                                f"waiting {wait_time}s before retry {attempt + 1}/{self.max_retries}: {e}"
                            )
                            time.sleep(wait_time)
                            continue
                        raise

                if not response:
                    raise Exception("Failed to get response after retries")

                # Validate response is JSON
                try:
                    data = response.json()
                except ValueError as e:
                    logger.error(
                        f"Invalid JSON response for condition '{condition}': {e}"
                    )
                    return nct_numbers  # Return what we have so far

                # Extract NCT numbers from current page with validation
                studies = data.get("studies", [])
                if not isinstance(studies, list):
                    logger.warning(
                        f"Unexpected 'studies' type for condition '{condition}': {type(studies)}"
                    )
                    return nct_numbers  # Return what we have so far

                for study in studies:
                    if not isinstance(study, dict):
                        logger.warning(f"Skipping invalid study entry: {type(study)}")
                        continue

                    protocol_section = study.get("protocolSection", {})
                    if not isinstance(protocol_section, dict):
                        continue

                    identification_module = protocol_section.get(
                        "identificationModule", {}
                    )
                    if not isinstance(identification_module, dict):
                        continue

                    nct_id = identification_module.get("nctId")
                    if nct_id and self._validate_nct_number(nct_id):
                        nct_numbers.append(nct_id.upper())
                    elif nct_id:
                        logger.warning(
                            f"Invalid NCT number format in response: {nct_id}"
                        )

                # Check for next page
                next_page_token = data.get("nextPageToken")
                if not next_page_token:
                    break

                page_token = next_page_token
                logger.debug(
                    f"Fetched {len(nct_numbers)} NCT numbers so far, continuing to next page..."
                )

                # Small delay between pages to be respectful
                time.sleep(0.5)

            if status_list:
                logger.info(
                    f"Found {len(nct_numbers)} trials for condition '{condition}' with statuses {status_list}"
                )
            else:
                logger.info(
                    f"Found {len(nct_numbers)} trials for condition '{condition}' (all statuses)"
                )
            return nct_numbers

        except requests.exceptions.HTTPError as e:
            logger.error(
                f"HTTP error when searching trials for condition '{condition}': {e}"
            )
            return nct_numbers  # Return what we have so far
        except requests.exceptions.RequestException as e:
            logger.error(
                f"Network error when searching trials for condition '{condition}': {e}"
            )
            return nct_numbers  # Return what we have so far
        except Exception as e:
            logger.error(
                f"Unexpected error when searching trials for condition '{condition}': {e}"
            )
            return nct_numbers  # Return what we have so far
