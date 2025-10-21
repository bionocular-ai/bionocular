"""Clinical Trials API service for fetching non-numeric attributes.

This service integrates with the existing doctorci.db database to fetch
clinical trial information using NCT numbers, following clean architecture
principles. Phase 1 refactor: single DB fetch, cleaner SQL, modular JSON
parsing, configuration-driven constants.
"""

import json
import logging
import sqlite3
from dataclasses import dataclass
from typing import Optional, Union

from ..domain.extraction_models import AttributeConfigurationFactory, AttributeType
from .config import DB_PATH, JSON_FIELD_TYPES

logger = logging.getLogger(__name__)


@dataclass
class ClinicalTrialData:
    """Data class for clinical trial information from API."""

    nct_number: str
    trial_name: Optional[str] = None
    cancer_type: Optional[str] = None
    primary_endpoint: Optional[str] = None
    secondary_endpoint: Optional[str] = None
    study_start_date: Optional[str] = None
    study_completion_date: Optional[str] = None
    first_results: Optional[str] = None
    trial_locations: Optional[str] = None
    sponsors: Optional[str] = None
    clinical_trial_phase: Optional[str] = None
    number_of_patients: Optional[int] = None
    minimum_age: Optional[str] = None
    maximum_age: Optional[str] = None
    sex: Optional[str] = None
    drug_info: Optional[str] = None
    # Legacy fields for compatibility
    trial_run_in_europe: Optional[bool] = None
    trial_run_in_us: Optional[bool] = None
    trial_run_in_china: Optional[bool] = None
    chemotherapy_naive: Optional[bool] = None
    chemotherapy_failed: Optional[bool] = None
    ici_naive: Optional[bool] = None
    ici_failed: Optional[bool] = None
    ipilimumab_failure: Optional[bool] = None
    anti_pd1_failure: Optional[bool] = None
    mutation_status: Optional[str] = None
    braf_mutation: Optional[bool] = None
    nras_mutation: Optional[bool] = None
    biosimilar: Optional[bool] = None
    biomarker_inclusion: Optional[bool] = None
    biomarkers_inclusion_criteria: Optional[str] = None
    biomarkers_exclusion_criteria: Optional[str] = None
    generic_name: Optional[str] = None
    brand_name: Optional[str] = None
    dosage: Optional[str] = None
    type_of_dosing: Optional[str] = None
    mechanism_of_action: Optional[str] = None
    target_protein: Optional[str] = None
    type_of_therapy: Optional[str] = None
    sub_therapy: Optional[str] = None


class ClinicalTrialsAPIService:
    """Service for fetching clinical trial data from the API database."""

    def __init__(self, db_path: str = DB_PATH):
        """Initialize the Clinical Trials API service.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.api_sourced_attributes = (
            AttributeConfigurationFactory.get_api_sourced_attributes()
        )
        self._json_parsers = {
            "list_of_strings": self._parse_list_of_strings,
            "primary_endpoint": self._parse_primary_endpoint,
            "secondary_endpoint": self._parse_secondary_endpoint,
            "locations": self._parse_locations,
            "interventions": self._parse_interventions,
        }
        logger.info(f"Clinical Trials API service initialized with database: {db_path}")

    def get_trial_data(self, nct_number: str) -> Optional[ClinicalTrialData]:
        """Get clinical trial data for a given NCT number.

        Args:
            nct_number: NCT number to look up

        Returns:
            ClinicalTrialData object or None if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Query the clinical_trials table (cleaner; no hardcoded NULLs)
                query = """
                SELECT
                    nct_number,
                    brief_title as trial_name,
                    conditions_json as cancer_type,
                    primary_outcomes_json as primary_endpoint,
                    secondary_outcomes_json as secondary_endpoint,
                    start_date as study_start_date,
                    completion_date as study_completion_date,
                    results_first_posted_date as first_results,
                    locations_json as trial_locations,
                    sponsor_name as sponsors,
                    phase_json as clinical_trial_phase,
                    enrollment_count as number_of_patients,
                    minimum_age,
                    maximum_age,
                    sex,
                    interventions_json as drug_info,
                    data_json
                FROM clinical_trials
                WHERE nct_number = ?
                """

                cursor.execute(query, (nct_number,))
                row = cursor.fetchone()

                if row:
                    return self._row_to_clinical_trial_data(row)
                else:
                    logger.warning(
                        f"No clinical trial data found for NCT number: {nct_number}"
                    )
                    return None

        except sqlite3.Error as e:
            logger.error(
                f"Database error when fetching trial data for {nct_number}: {e}"
            )
            return None
        except Exception as e:
            logger.error(
                f"Unexpected error when fetching trial data for {nct_number}: {e}"
            )
            return None

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
        # Check if this attribute should be sourced from API
        if attribute_type not in self.api_sourced_attributes:
            logger.debug(f"Attribute {attribute_type} is not API-sourced")
            return None

        trial_data = self.get_trial_data(nct_number)
        if not trial_data:
            return None

        # Map attribute types to trial data fields
        attribute_mapping = {
            AttributeType.TRIAL_NAME: trial_data.trial_name,
            AttributeType.CANCER_TYPE: trial_data.cancer_type,
            AttributeType.PRIMARY_ENDPOINT: trial_data.primary_endpoint,
            AttributeType.SECONDARY_ENDPOINT: trial_data.secondary_endpoint,
            AttributeType.STUDY_START_DATE: trial_data.study_start_date,
            AttributeType.STUDY_COMPLETION_DATE: trial_data.study_completion_date,
            AttributeType.FIRST_RESULTS: trial_data.first_results,
            AttributeType.TRIAL_RUN_IN_EUROPE: trial_data.trial_run_in_europe,
            AttributeType.TRIAL_RUN_IN_US: trial_data.trial_run_in_us,
            AttributeType.TRIAL_RUN_IN_CHINA: trial_data.trial_run_in_china,
            AttributeType.SPONSORS: trial_data.sponsors,
            AttributeType.CLINICAL_TRIAL_PHASE: trial_data.clinical_trial_phase,
            AttributeType.NUMBER_OF_PATIENTS: trial_data.number_of_patients,
            AttributeType.MINIMUM_AGE: trial_data.minimum_age,
            AttributeType.MAXIMUM_AGE: trial_data.maximum_age,
            AttributeType.SEX: trial_data.sex,
            # Legacy fields (set to None for now)
            AttributeType.CHEMOTHERAPY_NAIVE: trial_data.chemotherapy_naive,
            AttributeType.CHEMOTHERAPY_FAILED: trial_data.chemotherapy_failed,
            AttributeType.ICI_NAIVE: trial_data.ici_naive,
            AttributeType.ICI_FAILED: trial_data.ici_failed,
            AttributeType.IPILIMUMAB_FAILURE: trial_data.ipilimumab_failure,
            AttributeType.ANTI_PD1_FAILURE: trial_data.anti_pd1_failure,
            AttributeType.MUTATION_STATUS: trial_data.mutation_status,
            AttributeType.BRAF_MUTATION: trial_data.braf_mutation,
            AttributeType.NRAS_MUTATION: trial_data.nras_mutation,
            AttributeType.BIOSIMILAR: trial_data.biosimilar,
            AttributeType.BIOMARKER_INCLUSION: trial_data.biomarker_inclusion,
            AttributeType.BIOMARKERS_INCLUSION_CRITERIA: trial_data.biomarkers_inclusion_criteria,
            AttributeType.BIOMARKERS_EXCLUSION_CRITERIA: trial_data.biomarkers_exclusion_criteria,
            AttributeType.GENERIC_NAME: trial_data.generic_name,
            AttributeType.BRAND_NAME: trial_data.brand_name,
            AttributeType.DOSAGE: trial_data.dosage,
            AttributeType.TYPE_OF_DOSING: trial_data.type_of_dosing,
            AttributeType.MECHANISM_OF_ACTION: trial_data.mechanism_of_action,
            AttributeType.TARGET_PROTEIN: trial_data.target_protein,
            AttributeType.TYPE_OF_THERAPY: trial_data.type_of_therapy,
            AttributeType.SUB_THERAPY: trial_data.sub_therapy,
        }

        return attribute_mapping.get(attribute_type)

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
            arm_info: Optional arm information for arm-specific attributes

        Returns:
            Dictionary mapping attribute types to their values
        """
        trial_data = self.get_trial_data(nct_number)
        if not trial_data:
            return {attr_type: None for attr_type in attribute_types}

        results: dict[AttributeType, Optional[Union[str, bool, int, float]]] = {}
        for attribute_type in attribute_types:
            if attribute_type in self.api_sourced_attributes:
                # Check if this is an arm-specific attribute that should use arm_info
                if self._is_arm_specific_attribute(attribute_type) and arm_info:
                    results[attribute_type] = self._get_arm_specific_attribute(
                        attribute_type, arm_info
                    )
                else:
                    results[attribute_type] = self._get_attribute_from_data(
                        trial_data, attribute_type
                    )
            else:
                results[attribute_type] = None

        # Phase 2: Fallback from abstracts table for selected attributes if missing
        missing = [a for a in attribute_types if results.get(a) in (None, "")]
        if missing:
            fallback = self._get_abstracts_fallback(nct_number, missing)
            for a, v in fallback.items():
                if results.get(a) in (None, "") and v not in (None, ""):
                    results[a] = v

        return results

    def _is_arm_specific_attribute(self, attribute_type: AttributeType) -> bool:
        """Check if an attribute is arm-specific and should use arm_info."""
        arm_specific_attributes = {
            AttributeType.GENERIC_NAME,
            AttributeType.BRAND_NAME,
            AttributeType.DOSAGE,
            AttributeType.TYPE_OF_DOSING,
            AttributeType.MECHANISM_OF_ACTION,
            AttributeType.TARGET_PROTEIN,
            AttributeType.TYPE_OF_THERAPY,
            AttributeType.SUB_THERAPY,
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
            # These fields are not available in TreatmentArm model, so return None
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
        """Helper to map an attribute type to a field on ClinicalTrialData."""
        attribute_mapping: dict[
            AttributeType, Optional[Union[str, bool, int, float]]
        ] = {
            AttributeType.TRIAL_NAME: trial_data.trial_name,
            AttributeType.CANCER_TYPE: trial_data.cancer_type,
            AttributeType.PRIMARY_ENDPOINT: trial_data.primary_endpoint,
            AttributeType.SECONDARY_ENDPOINT: trial_data.secondary_endpoint,
            AttributeType.STUDY_START_DATE: trial_data.study_start_date,
            AttributeType.STUDY_COMPLETION_DATE: trial_data.study_completion_date,
            AttributeType.FIRST_RESULTS: trial_data.first_results,
            AttributeType.TRIAL_RUN_IN_EUROPE: trial_data.trial_run_in_europe,
            AttributeType.TRIAL_RUN_IN_US: trial_data.trial_run_in_us,
            AttributeType.TRIAL_RUN_IN_CHINA: trial_data.trial_run_in_china,
            AttributeType.SPONSORS: trial_data.sponsors,
            AttributeType.CLINICAL_TRIAL_PHASE: trial_data.clinical_trial_phase,
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
            AttributeType.ICI_NAIVE: trial_data.ici_naive,
            AttributeType.BRAF_MUTATION: trial_data.braf_mutation,
            AttributeType.BIOMARKER_INCLUSION: trial_data.biomarker_inclusion,
        }

        return attribute_mapping.get(attribute_type)

    def _row_to_clinical_trial_data(self, row: sqlite3.Row) -> ClinicalTrialData:
        """Convert database row to ClinicalTrialData object.

        Args:
            row: Database row

        Returns:
            ClinicalTrialData object
        """
        # Parse JSON fields (modular via configured parser types)
        cancer_type = self._parse_json_field(row["cancer_type"], "cancer_type")
        primary_endpoint = self._parse_json_field(
            row["primary_endpoint"], "primary_endpoint"
        )
        secondary_endpoint = self._parse_json_field(
            row["secondary_endpoint"], "secondary_endpoint"
        )
        clinical_trial_phase = self._parse_json_field(
            row["clinical_trial_phase"], "phase"
        )
        trial_locations = self._parse_json_field(row["trial_locations"], "locations")
        drug_info = self._parse_json_field(row["drug_info"], "interventions")
        # Extract finer drug details from raw interventions JSON
        generic_name_extracted, dosage_extracted, dosing_extracted = self._extract_drug_details_from_interventions(row["drug_info"])  # type: ignore[index]

        # Phase 2: Parse conditions_json for biomarkers (keep original cancer_type)
        _, biomarker_inclusion = self._parse_conditions_json(row["cancer_type"])

        # Phase 2: Parse data_json eligibility criteria for chemo/ICI naive and BRAF status
        eligibility_data = self._parse_eligibility_criteria(row["data_json"])

        # Determine trial locations
        trial_run_in_europe = self._check_trial_location(trial_locations, "Europe")
        trial_run_in_us = self._check_trial_location(trial_locations, "United States")
        trial_run_in_china = self._check_trial_location(trial_locations, "China")

        return ClinicalTrialData(
            nct_number=row["nct_number"],
            trial_name=row["trial_name"],
            cancer_type=cancer_type,  # Use exact value from API
            primary_endpoint=primary_endpoint,
            secondary_endpoint=secondary_endpoint,
            study_start_date=row["study_start_date"],
            study_completion_date=row["study_completion_date"],
            first_results=row["first_results"],
            trial_locations=trial_locations,
            sponsors=row["sponsors"],
            clinical_trial_phase=clinical_trial_phase,
            number_of_patients=row["number_of_patients"],
            minimum_age=row["minimum_age"],
            maximum_age=row["maximum_age"],
            sex=row["sex"],
            drug_info=drug_info,
            # Location flags
            trial_run_in_europe=trial_run_in_europe,
            trial_run_in_us=trial_run_in_us,
            trial_run_in_china=trial_run_in_china,
            # Parsed from interventions JSON (Phase 2)
            generic_name=generic_name_extracted,
            dosage=dosage_extracted,
            type_of_dosing=dosing_extracted,
            # Parsed from eligibility criteria (Phase 2)
            chemotherapy_naive=eligibility_data.get("chemotherapy_naive"),
            ici_naive=eligibility_data.get("ici_naive"),
            braf_mutation=eligibility_data.get("braf_mutation"),
            biomarker_inclusion=biomarker_inclusion,
            # Legacy fields (set to None for now)
            chemotherapy_failed=None,
            ici_failed=None,
            ipilimumab_failure=None,
            anti_pd1_failure=None,
            mutation_status=None,
            nras_mutation=None,
            biosimilar=None,
            biomarkers_inclusion_criteria=None,
            biomarkers_exclusion_criteria=None,
            brand_name=None,
            mechanism_of_action=None,
            target_protein=None,
            type_of_therapy=None,
            sub_therapy=None,
        )

    def _parse_json_field(
        self, json_str: Optional[str], field_type: str
    ) -> Optional[str]:
        """Parse JSON field using modular parser mapping.

        Args:
            json_str: JSON string from database
            field_type: Logical field type to parse (see JSON_FIELD_TYPES)
        """
        if not json_str:
            return None

        try:
            data = json.loads(json_str)
            parser_key = JSON_FIELD_TYPES.get(field_type, "list_of_strings")
            parser = self._json_parsers.get(parser_key)
            if parser:
                return parser(data)
            return str(data) if data else None
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.warning(f"Failed to parse JSON field {field_type}: {e}")
            return None

    def _parse_list_of_strings(self, data: list) -> Optional[str]:
        if isinstance(data, list) and data:
            return ", ".join([s for s in data if s])
        return None

    def _parse_primary_endpoint(self, data: list) -> Optional[str]:
        if isinstance(data, list) and data:
            return data[0].get("measure", "")
        return None

    def _parse_secondary_endpoint(self, data: list) -> Optional[str]:
        if isinstance(data, list) and data:
            measures = [item.get("measure", "") for item in data if item.get("measure")]
            return "; ".join(measures)
        return None

    def _parse_locations(self, data: list) -> Optional[str]:
        if isinstance(data, list) and data:
            countries = {item.get("country") for item in data if item.get("country")}
            return ", ".join(sorted(countries)) if countries else None
        return None

    def _parse_interventions(self, data: list) -> Optional[str]:
        if isinstance(data, list) and data:
            drugs = [item.get("name", "") for item in data if item.get("name")]
            return ", ".join([d for d in drugs if d]) if drugs else None
        return None

    def _extract_drug_details_from_interventions(
        self, json_str: Optional[str]
    ) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """Extract generic drug name, dosage, and dosing schedule from interventions JSON."""
        if not json_str:
            return None, None, None
        try:
            data = json.loads(json_str)
        except Exception:
            return None, None, None
        if not isinstance(data, list):
            return None, None, None

        import re

        dosage_pattern = re.compile(
            r"\b(\d+\s*(?:mg|mg/kg|mcg|g))(?:/\w+)?\b", re.IGNORECASE
        )
        schedule_patterns = [
            re.compile(
                r"every\s+\d+\s+(?:week|weeks|day|days|month|months)", re.IGNORECASE
            ),
            re.compile(r"\bq\d+w\b", re.IGNORECASE),
            re.compile(r"once\s+(?:weekly|daily|monthly)", re.IGNORECASE),
        ]

        generic_name: Optional[str] = None
        dosage: Optional[str] = None
        dosing: Optional[str] = None

        for item in data:
            name = (item.get("name") or "").strip()
            desc = (item.get("description") or "").strip()
            text = f"{name} {desc}".strip()

            if not generic_name and name:
                generic_name = name
            if not dosage:
                m = dosage_pattern.search(text)
                if m:
                    dosage = m.group(1)
            if not dosing:
                for pat in schedule_patterns:
                    sm = pat.search(text)
                    if sm:
                        dosing = sm.group(0)
                        break
            if generic_name and dosage and dosing:
                break

        return generic_name, dosage, dosing

    def _parse_conditions_json(
        self, conditions_json: Optional[str]
    ) -> tuple[Optional[str], Optional[bool]]:
        """Parse conditions_json to extract normalized cancer type and biomarker inclusion.

        Focused on melanoma and skin cancers based on actual database content.

        Args:
            conditions_json: JSON string containing conditions data

        Returns:
            Tuple of (normalized_cancer_type, biomarker_inclusion)
        """
        if not conditions_json:
            return None, None

        try:
            data = json.loads(conditions_json)
        except Exception:
            return None, None

        if not isinstance(data, list):
            return None, None

        # Normalize cancer type - focus on melanoma and skin cancers
        cancer_type = None
        biomarker_inclusion = None

        for condition in data:
            if isinstance(condition, str):
                condition_lower = condition.lower()

                # Normalize melanoma and skin cancer types based on actual DB data
                if "melanoma" in condition_lower:
                    if "uveal" in condition_lower:
                        cancer_type = "Uveal Melanoma"
                    elif "mucosal" in condition_lower:
                        cancer_type = "Mucosal Melanoma"
                    elif "cutaneous" in condition_lower:
                        cancer_type = "Cutaneous Melanoma"
                    elif "metastatic" in condition_lower:
                        cancer_type = "Metastatic Melanoma"
                    elif "advanced" in condition_lower:
                        cancer_type = "Advanced Melanoma"
                    elif "malignant" in condition_lower:
                        cancer_type = "Malignant Melanoma"
                    elif "stage" in condition_lower:
                        # Extract stage information
                        if "stage iii" in condition_lower:
                            cancer_type = "Melanoma Stage III"
                        elif "stage iv" in condition_lower:
                            cancer_type = "Melanoma Stage IV"
                        else:
                            cancer_type = "Melanoma"
                    else:
                        cancer_type = "Melanoma"
                elif (
                    "squamous cell carcinoma" in condition_lower
                    or "cutaneous squamous" in condition_lower
                ):
                    cancer_type = "Cutaneous Squamous Cell Carcinoma"
                elif (
                    "basal cell carcinoma" in condition_lower
                    or "carcinoma, basal cell" in condition_lower
                ):
                    cancer_type = "Basal Cell Carcinoma"
                elif "merkel cell carcinoma" in condition_lower:
                    cancer_type = "Merkel Cell Carcinoma"
                elif "kaposi sarcoma" in condition_lower:
                    cancer_type = "Kaposi Sarcoma"
                elif "squamous cell carcinoma" in condition_lower:
                    cancer_type = "Squamous Cell Carcinoma"
                elif "cancer" in condition_lower and not cancer_type:
                    cancer_type = condition  # Use original if no specific match

                # Check for biomarker inclusion keywords
                if biomarker_inclusion is None:
                    biomarker_keywords = [
                        "pd-l1",
                        "pdl1",
                        "pd1",
                        "pd-1",
                        "biomarker",
                        "molecular",
                        "mutation",
                        "expression",
                        "status",
                        "braf",
                        "nras",
                    ]
                    if any(
                        keyword in condition_lower for keyword in biomarker_keywords
                    ):
                        biomarker_inclusion = True
                    elif (
                        "no biomarker" in condition_lower
                        or "without biomarker" in condition_lower
                    ):
                        biomarker_inclusion = False

        # Default biomarker_inclusion to False if no evidence found
        if biomarker_inclusion is None:
            biomarker_inclusion = False

        return cancer_type, biomarker_inclusion

    def _parse_eligibility_criteria(
        self, data_json: Optional[str]
    ) -> dict[str, Optional[bool]]:
        """Parse eligibility criteria from data_json to extract chemo/ICI naive and BRAF status.

        Args:
            data_json: JSON string containing trial data including eligibility criteria

        Returns:
            Dictionary with eligibility flags
        """
        if not data_json:
            return {}

        try:
            data = json.loads(data_json)
        except Exception:
            return {}

        eligibility_text = data.get("eligibility_criteria", "")
        if not eligibility_text:
            return {}

        eligibility_lower = eligibility_text.lower()

        # Check for chemotherapy naive status
        chemo_naive = None
        chemo_naive_positive = [
            "no prior chemotherapy",
            "chemotherapy naive",
            "no prior systemic therapy",
            "no prior treatment",
            "treatment naive",
            "previously untreated",
        ]
        chemo_naive_negative = [
            "prior chemotherapy",
            "chemotherapy experienced",
            "previously treated",
        ]

        if any(phrase in eligibility_lower for phrase in chemo_naive_positive):
            chemo_naive = True
        elif any(phrase in eligibility_lower for phrase in chemo_naive_negative):
            chemo_naive = False

        # Check for ICI naive status
        ici_naive = None
        ici_naive_positive = [
            "no prior immunotherapy",
            "ici naive",
            "no prior checkpoint inhibitor",
            "no prior anti-pd",
            "no prior anti-ctla",
            "immunotherapy naive",
        ]
        ici_naive_negative = [
            "prior immunotherapy",
            "prior checkpoint inhibitor",
            "prior anti-pd",
            "prior anti-ctla",
            "immunotherapy experienced",
        ]

        if any(phrase in eligibility_lower for phrase in ici_naive_positive):
            ici_naive = True
        elif any(phrase in eligibility_lower for phrase in ici_naive_negative):
            ici_naive = False

        # Check for BRAF mutation status
        braf_mutation = None
        braf_positive = [
            "braf mutation",
            "braf v600",
            "braf positive",
            "braf mutated",
            "braf wild-type",
        ]
        braf_negative = ["braf wild-type", "braf negative", "no braf mutation"]

        if any(phrase in eligibility_lower for phrase in braf_positive):
            braf_mutation = True
        elif any(phrase in eligibility_lower for phrase in braf_negative):
            braf_mutation = False

        return {
            "chemotherapy_naive": chemo_naive,
            "ici_naive": ici_naive,
            "braf_mutation": braf_mutation,
        }

    def _get_abstracts_fallback(
        self, nct_number: str, attribute_types: list[AttributeType]
    ) -> dict[AttributeType, Optional[Union[str, bool, int, float]]]:
        """Fallback to abstracts table for selected attributes when API data is missing."""
        fallback_attrs = {
            # Publication and Trial Context
            AttributeType.CONFERENCE: "conference",
            AttributeType.PUBLISHED_YEAR: "published_year",
            AttributeType.ABSTRACT_NUMBER: "abstract_number",
            AttributeType.TRIAL_NAME: "trial_name",
            AttributeType.SPONSORS: "sponsors",
            AttributeType.NCT_NUMBER: "nct_number",
            AttributeType.CANCER_TYPE: "cancer_type",
            AttributeType.MEDIAN_AGE: "median_age",
            AttributeType.NUMBER_OF_PATIENTS: "number_of_patients",
            # Treatment Details
            AttributeType.GENERIC_NAME: "generic_name",
            AttributeType.BRAND_NAME: "brand_name",
            AttributeType.DOSAGE: "dosage",
            AttributeType.TYPE_OF_DOSING: "type_of_dosing",
            AttributeType.TYPE_OF_THERAPY: "type_of_therapy",
            AttributeType.SUB_THERAPY: "sub_therapy",
            # Trial Design
            AttributeType.PRIMARY_ENDPOINT: "primary_endpoint",
            AttributeType.SECONDARY_ENDPOINT: "secondary_endpoint",
            AttributeType.CLINICAL_TRIAL_PHASE: "clinical_trial_phase",
            AttributeType.STUDY_START_DATE: "study_start_date",
            # Biomarker and Mutation Data
            AttributeType.BIOMARKER_INCLUSION: "biomarker_inclusion",
            # Efficacy - Survival Metrics
            AttributeType.RFS: "rfs",
            AttributeType.P_VALUE_RFS: "p_value_rfs",
            AttributeType.HR_RFS: "hr_rfs",
            AttributeType.LENGTH_RFS: "rfs_length",
            AttributeType.MFS: "mfs",
            AttributeType.HR_MFS: "hr_mfs",
            AttributeType.LENGTH_MFS: "mfs_length",
            AttributeType.MEDIAN_OS: "median_os",
            AttributeType.HR_OS: "hr_os",
            AttributeType.P_VALUE_OS: "p_value_os",
            AttributeType.MEDIAN_PFS: "median_pfs",
            AttributeType.HR_PFS: "hr_pfs",
            AttributeType.P_VALUE_PFS: "p_value_pfs",
            AttributeType.EFS: "efs",
            AttributeType.HR_EFS: "hr_efs",
            AttributeType.P_VALUE_EFS: "p_value_efs",
        }
        cols = [fallback_attrs[a] for a in attribute_types if a in fallback_attrs]
        if not cols:
            return {}
        select_cols = ", ".join(cols)
        query = f"""
            SELECT {select_cols}
            FROM abstracts
            WHERE nct_number = ?
            ORDER BY published_year DESC
            LIMIT 1
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute(query, (nct_number,))
                row = cur.fetchone()
                if not row:
                    return {}
                result: dict[AttributeType, Optional[Union[str, bool, int, float]]] = {}
                for attr, col in fallback_attrs.items():
                    if attr in attribute_types and col in row.keys():
                        result[attr] = row[col]
                return result
        except Exception as e:
            logger.warning(f"Abstracts fallback failed for {nct_number}: {e}")
            return {}

    def _check_trial_location(
        self, locations_str: Optional[str], target_country: str
    ) -> Optional[bool]:
        """Check if trial runs in specific country/region.

        Args:
            locations_str: Comma-separated countries string
            target_country: Target country/region to check

        Returns:
            True if trial runs in target country, False otherwise, None if unknown
        """
        if not locations_str:
            return None

        # Check for various forms of the country name
        country_variants = {
            "United States": ["United States", "USA", "US"],
            "Europe": ["Europe", "European", "EU"],
            "China": ["China", "Chinese"],
        }

        variants = country_variants.get(target_country, [target_country])
        locations_lower = locations_str.lower()

        for variant in variants:
            if variant.lower() in locations_lower:
                return True

        return False

    def get_database_schema(self) -> dict[str, list[str]]:
        """Get the database schema information.

        Returns:
            Dictionary mapping table names to column lists
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Get table names
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [row[0] for row in cursor.fetchall()]

                schema = {}
                for table in tables:
                    cursor.execute(f"PRAGMA table_info({table});")
                    columns = [row[1] for row in cursor.fetchall()]
                    schema[table] = columns

                return schema

        except sqlite3.Error as e:
            logger.error(f"Error getting database schema: {e}")
            return {}

    def test_connection(self) -> bool:
        """Test the database connection.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                return result is not None
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
