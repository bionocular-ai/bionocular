"""Application service for clinical trials API operations.

This service orchestrates the domain and infrastructure layers to provide
a clean interface for fetching clinical trial data with caching.
"""

import logging
from typing import Optional, Union

from ..domain.clinical_trial_interfaces import (
    ClinicalTrialParser,
    ClinicalTrialRepository,
    ClinicalTrialsAPIClient,
)
from ..domain.clinical_trial_models import ClinicalTrialData, TreatmentArm
from ..domain.extraction_models import AttributeConfigurationFactory, AttributeType

logger = logging.getLogger(__name__)


class ClinicalTrialsService:
    """Application service for clinical trials operations.

    Orchestrates API client, repository, and parser to provide
    a unified interface for fetching clinical trial data.
    """

    def __init__(
        self,
        api_client: ClinicalTrialsAPIClient,
        repository: ClinicalTrialRepository,
        parser: ClinicalTrialParser,
    ):
        """Initialize the service.

        Args:
            api_client: Client for fetching data from API
            repository: Repository for caching data
            parser: Parser for converting API responses to domain models
        """
        self.api_client = api_client
        self.repository = repository
        self.parser = parser
        self.api_sourced_attributes = (
            AttributeConfigurationFactory.get_api_sourced_attributes()
        )

    def get_trial_data(self, nct_number: str) -> Optional[ClinicalTrialData]:
        """Get clinical trial data for a given NCT number.

        Implements caching strategy:
        1. Check local database cache first
        2. If not found or expired, fetch from API
        3. Save API response to cache

        Args:
            nct_number: NCT number to look up (e.g., "NCT02362594")

        Returns:
            ClinicalTrialData object or None if not found
        """
        if not nct_number:
            logger.warning("No NCT number provided.")
            return None

        # Try to get from cache first
        cached_data = self.repository.get_cached_trial(nct_number)
        if cached_data:
            logger.debug(f"Retrieved {nct_number} from cache")
            return cached_data

        # Not in cache or expired, fetch from API
        logger.debug(f"Fetching {nct_number} from API")
        api_json_data = self.api_client.fetch_trial_data(nct_number)
        if not api_json_data:
            return None

        # Convert API JSON to ClinicalTrialData
        trial_data = self.parser.parse_api_response(api_json_data)

        # Save to cache
        if trial_data:
            self.repository.save_trial_to_cache(nct_number, api_json_data)

        return trial_data

    def get_attribute_value(
        self, nct_number: str, attribute_type: AttributeType
    ) -> Optional[Union[str, bool, int, float]]:
        """Get a specific attribute value for a given NCT number.

        Args:
            nct_number: NCT number to look up
            attribute_type: Type of attribute to extract

        Returns:
            Attribute value or None if not found
        """
        if attribute_type not in self.api_sourced_attributes:
            logger.debug(f"Attribute {attribute_type} is not API-sourced")
            return None

        trial_data = self.get_trial_data(nct_number)
        if not trial_data:
            return None

        return self._get_attribute_from_data(trial_data, attribute_type)

    def get_multiple_attributes(
        self,
        nct_number: str,
        attribute_types: list[AttributeType],
        arm_info: Optional[dict] = None,
    ) -> dict[AttributeType, Optional[Union[str, bool, int, float]]]:
        """Get multiple attribute values for a given NCT number.

        Args:
            nct_number: NCT number to look up
            attribute_types: List of attribute types to extract
            arm_info: Optional arm information for arm-specific attributes.
                     Can contain 'arm_label' or 'arm_index' to select specific arm.

        Returns:
            Dictionary mapping attribute types to their values
        """
        trial_data = self.get_trial_data(nct_number)
        if not trial_data:
            return {attr_type: None for attr_type in attribute_types}

        # Find the specific arm if arm_info is provided
        selected_arm = None
        if arm_info and trial_data.treatment_arms:
            if "arm_label" in arm_info:
                # Find arm by label
                for arm in trial_data.treatment_arms:
                    if arm.arm_label == arm_info["arm_label"]:
                        selected_arm = arm
                        break
            elif "arm_index" in arm_info:
                # Find arm by index
                arm_index = arm_info["arm_index"]
                if 0 <= arm_index < len(trial_data.treatment_arms):
                    selected_arm = trial_data.treatment_arms[arm_index]

        results: dict[AttributeType, Optional[Union[str, bool, int, float]]] = {}
        for attribute_type in attribute_types:
            if attribute_type in self.api_sourced_attributes:
                if self._is_arm_specific_attribute(attribute_type):
                    # Try to get from selected arm first, then fallback to arm_info or first arm
                    if selected_arm:
                        results[attribute_type] = self._get_attribute_from_arm(
                            selected_arm, attribute_type
                        )
                    elif arm_info:
                        results[attribute_type] = self._get_arm_specific_attribute(
                            attribute_type, arm_info
                        )
                    elif trial_data.treatment_arms:
                        # Fallback to first arm
                        results[attribute_type] = self._get_attribute_from_arm(
                            trial_data.treatment_arms[0], attribute_type
                        )
                    else:
                        results[attribute_type] = None
                else:
                    results[attribute_type] = self._get_attribute_from_data(
                        trial_data, attribute_type
                    )
            else:
                results[attribute_type] = None

        return results

    def _get_attribute_from_arm(
        self, arm: TreatmentArm, attribute_type: AttributeType
    ) -> Optional[Union[str, bool, int, float]]:
        """Get attribute value from a TreatmentArm object.
        
        Args:
            arm: TreatmentArm object
            attribute_type: Type of attribute to extract
        """
        mapping = {
            AttributeType.GENERIC_NAME: arm.generic_name,
            AttributeType.BRAND_NAME: arm.brand_name,
            AttributeType.DOSAGE: arm.dosage,
            AttributeType.TYPE_OF_DOSING: arm.type_of_dosing,
            AttributeType.MECHANISM_OF_ACTION: arm.mechanism_of_action,
            AttributeType.TARGET_PROTEIN: arm.target_protein,
            AttributeType.TYPE_OF_THERAPY: arm.type_of_therapy,
            AttributeType.SUB_THERAPY: arm.sub_therapy,
            AttributeType.LINE_OF_TREATMENT: arm.line_of_treatment,
        }
        return mapping.get(attribute_type)

    def _is_arm_specific_attribute(self, attribute_type: AttributeType) -> bool:
        """Check if an attribute is arm-specific."""
        arm_specific_attributes = {
            AttributeType.GENERIC_NAME,
            AttributeType.BRAND_NAME,
            AttributeType.DOSAGE,
            AttributeType.TYPE_OF_DOSING,
            AttributeType.MECHANISM_OF_ACTION,
            AttributeType.TARGET_PROTEIN,
            AttributeType.TYPE_OF_THERAPY,
            AttributeType.SUB_THERAPY,
            AttributeType.LINE_OF_TREATMENT,  # Arm-specific: each arm has its own line of treatment
        }
        return attribute_type in arm_specific_attributes

    def _get_arm_specific_attribute(
        self, attribute_type: AttributeType, arm_info: dict
    ) -> Optional[str]:
        """Get arm-specific attribute value from arm_info."""
        mapping = {
            AttributeType.GENERIC_NAME: arm_info.get("generic_name"),
            AttributeType.BRAND_NAME: arm_info.get("brand_name"),
            AttributeType.DOSAGE: arm_info.get("dose"),
            AttributeType.TYPE_OF_DOSING: arm_info.get("dosing_schedule"),
            AttributeType.MECHANISM_OF_ACTION: None,
            AttributeType.TARGET_PROTEIN: None,
            AttributeType.TYPE_OF_THERAPY: None,
            AttributeType.SUB_THERAPY: None,
        }
        return mapping.get(attribute_type)

    def _get_attribute_from_data(
        self,
        trial_data: ClinicalTrialData,
        attribute_type: AttributeType,
    ) -> Optional[Union[str, bool, int, float]]:
        """Map an attribute type to a field on ClinicalTrialData."""
        attribute_mapping: dict[
            AttributeType, Optional[Union[str, bool, int, float]]
        ] = {
            AttributeType.NCT_NUMBER: trial_data.nct_number,
            AttributeType.TRIAL_NAME: trial_data.trial_name,
            AttributeType.CANCER_TYPE: trial_data.cancer_type,
            AttributeType.PRIMARY_ENDPOINT: trial_data.primary_endpoint,
            AttributeType.SECONDARY_ENDPOINT: trial_data.secondary_endpoint,
            AttributeType.STUDY_START_DATE: trial_data.study_start_date,
            AttributeType.PRIMARY_COMPLETION_DATE: trial_data.primary_completion_date,
            AttributeType.STUDY_COMPLETION_DATE: trial_data.study_completion_date,
            AttributeType.FIRST_RESULTS: trial_data.first_results,
            AttributeType.TRIAL_RUN_IN_EUROPE: trial_data.trial_run_in_europe,
            AttributeType.TRIAL_RUN_IN_US: trial_data.trial_run_in_us,
            AttributeType.TRIAL_RUN_IN_CHINA: trial_data.trial_run_in_china,
            AttributeType.SPONSORS: trial_data.sponsors,
            AttributeType.CLINICAL_TRIAL_PHASE: trial_data.clinical_trial_phase,
            AttributeType.STUDY_TYPE: trial_data.study_type,
            AttributeType.NUMBER_OF_PATIENTS: trial_data.number_of_patients,
            AttributeType.MINIMUM_AGE: trial_data.minimum_age,
            AttributeType.MAXIMUM_AGE: trial_data.maximum_age,
            AttributeType.SEX: trial_data.sex,
            AttributeType.GENERIC_NAME: trial_data.generic_name,
            AttributeType.BRAND_NAME: trial_data.brand_name,
            AttributeType.DOSAGE: trial_data.dosage,
            AttributeType.TYPE_OF_DOSING: trial_data.type_of_dosing,
            AttributeType.MECHANISM_OF_ACTION: trial_data.mechanism_of_action,
            AttributeType.TARGET_PROTEIN: trial_data.target_protein,
            AttributeType.TYPE_OF_THERAPY: trial_data.type_of_therapy,
            AttributeType.SUB_THERAPY: trial_data.sub_therapy,
            AttributeType.CHEMOTHERAPY_NAIVE: trial_data.chemotherapy_naive,
            AttributeType.CHEMOTHERAPY_FAILED: trial_data.chemotherapy_failed,
            AttributeType.ICI_NAIVE: trial_data.ici_naive,
            AttributeType.ICI_FAILED: trial_data.ici_failed,
            AttributeType.IPILIMUMAB_FAILURE: trial_data.ipilimumab_failure,
            AttributeType.ANTI_PD1_FAILURE: trial_data.anti_pd1_failure,
            AttributeType.BRAF_MUTATION: trial_data.braf_mutation,
            AttributeType.NRAS_MUTATION: trial_data.nras_mutation,
            AttributeType.MUTATION_STATUS: trial_data.mutation_status,
            AttributeType.BIOMARKER_INCLUSION: trial_data.biomarker_inclusion,
            AttributeType.BIOMARKERS_INCLUSION_CRITERIA: trial_data.biomarkers_inclusion_criteria,
            AttributeType.BIOMARKERS_EXCLUSION_CRITERIA: trial_data.biomarkers_exclusion_criteria,
            # LINE_OF_TREATMENT is arm-specific, not study-wide
        }

        return attribute_mapping.get(attribute_type)

    def clear_cache(self, nct_number: Optional[str] = None) -> int:
        """Clear cache entries."""
        return self.repository.clear_cache(nct_number)

    def get_cache_stats(self) -> dict[str, int]:
        """Get cache statistics."""
        return self.repository.get_cache_stats()

