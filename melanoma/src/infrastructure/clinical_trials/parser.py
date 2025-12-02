"""Parser for ClinicalTrials.gov v2 API responses."""

import logging
import re
from typing import Optional

from ...domain.cancer_type_normalizer import get_primary_cancer_type
from ...domain.clinical_trial_interfaces import ClinicalTrialParser
from ...domain.clinical_trial_models import ClinicalTrialData, TreatmentArm
from ..config import COUNTRY_VARIANTS

logger = logging.getLogger(__name__)


class ClinicalTrialDataParser(ClinicalTrialParser):
    """Parser for converting API v2 JSON responses to domain models."""

    def parse_api_response(self, api_json: dict) -> ClinicalTrialData:
        """Parse API v2 JSON response into ClinicalTrialData domain model.

        Args:
            api_json: Raw JSON response from ClinicalTrials.gov v2 API

        Returns:
            ClinicalTrialData domain model
        """
        # Get the main data sections
        protocol = api_json.get("protocolSection", {})
        results = api_json.get("resultsSection", {})

        # Extract modules from protocolSection
        id_module = protocol.get("identificationModule", {})
        design_module = protocol.get("designModule", {})
        status_module = protocol.get("statusModule", {})
        eligibility_module = protocol.get("eligibilityModule", {})
        locations_module = protocol.get("contactsLocationsModule", {})
        interventions_module = protocol.get("armsInterventionsModule", {})
        outcomes_module = protocol.get("outcomesModule", {})

        # Direct mappings from API v2 JSON
        nct_number = id_module.get("nctId")
        trial_name = id_module.get("briefTitle")

        # Clinical trial phase - join list if present
        phases = design_module.get("phases", [])
        clinical_trial_phase = ", ".join(phases) if phases else None

        # Study type
        study_type = design_module.get("studyType")

        # Primary endpoint - get first outcome measure
        primary_outcomes = outcomes_module.get("primaryOutcomes", [])
        primary_endpoint = (
            primary_outcomes[0].get("measure") if primary_outcomes else None
        )

        # Secondary endpoints - join all measures
        secondary_outcomes = outcomes_module.get("secondaryOutcomes", [])
        secondary_endpoint = (
            "; ".join(
                [
                    outcome.get("measure", "")
                    for outcome in secondary_outcomes
                    if outcome.get("measure")
                ]
            )
            if secondary_outcomes
            else None
        )

        # Dates
        start_date_struct = status_module.get("startDateStruct", {})
        study_start_date = start_date_struct.get("date") if start_date_struct else None

        # Primary completion date
        primary_completion_date_struct = status_module.get(
            "primaryCompletionDateStruct", {}
        )
        primary_completion_date = (
            primary_completion_date_struct.get("date")
            if primary_completion_date_struct
            else None
        )

        completion_date_struct = status_module.get("completionDateStruct", {})
        study_completion_date = (
            completion_date_struct.get("date") if completion_date_struct else None
        )

        # First results - check statusModule first (v2 API structure)
        # In v2 API, resultsFirstPostDateStruct is in statusModule, not resultsSection
        first_posted = status_module.get("resultsFirstPostDateStruct", {})
        if not first_posted:
            # Try resultsSection as fallback
            first_posted = results.get("resultsFirstPostDateStruct", {})
        if not first_posted:
            # Fallback to firstPostedDateStruct if available
            first_posted = results.get("firstPostedDateStruct", {})
        first_results = first_posted.get("date") if first_posted else None

        # Enrollment
        enrollment_info = design_module.get("enrollmentInfo", {})
        number_of_patients = enrollment_info.get("count")

        # Demographics
        eligibility_info = eligibility_module.get("eligibilityInfo", {})
        minimum_age = eligibility_info.get("minimumAge")
        maximum_age = eligibility_info.get("maximumAge")
        sex = eligibility_info.get("sex")

        # Sponsors
        sponsor_module = protocol.get("sponsorCollaboratorsModule", {})
        lead_sponsor = sponsor_module.get("leadSponsor", {})
        sponsors = lead_sponsor.get("name") if lead_sponsor else None

        # Locations - parse from locations list
        locations_list = locations_module.get("locations", [])
        countries = {loc.get("country") for loc in locations_list if loc.get("country")}
        trial_locations = ", ".join(sorted(countries)) if countries else None

        # Determine trial location flags
        trial_run_in_europe = self._check_trial_location(trial_locations, "Europe")
        trial_run_in_us = self._check_trial_location(trial_locations, "United States")
        trial_run_in_china = self._check_trial_location(trial_locations, "China")

        # Conditions (cancer type)
        conditions_list = id_module.get("conditions", [])
        cancer_type = ", ".join(conditions_list) if conditions_list else None

        # Parse conditions for biomarker inclusion
        _, biomarker_inclusion = self._parse_conditions_from_list(conditions_list)

        # Extract eligibility criteria (needed for both line of treatment and eligibility parsing)
        eligibility_criteria = eligibility_module.get("eligibilityCriteria", "")

        # Parse treatment arms and interventions (arm-wise data)
        # Pass eligibility_criteria for line of treatment determination
        treatment_arms = self._parse_arms_and_interventions(
            interventions_module, eligibility_criteria
        )

        # Get all intervention names for backward compatibility
        all_intervention_names = []
        for arm in treatment_arms:
            all_intervention_names.extend(arm.intervention_names)
        drug_info = (
            ", ".join(set(all_intervention_names)) if all_intervention_names else None
        )

        # Extract legacy fields from first arm for backward compatibility
        first_arm = treatment_arms[0] if treatment_arms else None
        generic_name_extracted = first_arm.generic_name if first_arm else None
        dosage_extracted = first_arm.dosage if first_arm else None
        dosing_extracted = first_arm.type_of_dosing if first_arm else None
        mechanism_of_action = first_arm.mechanism_of_action if first_arm else None
        target_protein = first_arm.target_protein if first_arm else None
        type_of_therapy = first_arm.type_of_therapy if first_arm else None
        brand_name = first_arm.brand_name if first_arm else None

        # Parse eligibility criteria for all interpretive attributes
        eligibility_data = self._parse_eligibility_criteria_comprehensive(
            eligibility_criteria
        )

        # Extract biomarker criteria text
        biomarkers_inclusion_criteria = self._extract_biomarker_inclusion_criteria(
            eligibility_criteria
        )
        biomarkers_exclusion_criteria = self._extract_biomarker_exclusion_criteria(
            eligibility_criteria
        )

        return ClinicalTrialData(
            nct_number=nct_number,
            trial_name=trial_name,
            cancer_type=cancer_type,
            primary_endpoint=primary_endpoint,
            secondary_endpoint=secondary_endpoint,
            study_start_date=study_start_date,
            primary_completion_date=primary_completion_date,
            study_completion_date=study_completion_date,
            first_results=first_results,
            trial_locations=trial_locations,
            sponsors=sponsors,
            clinical_trial_phase=clinical_trial_phase,
            study_type=study_type,
            number_of_patients=number_of_patients,
            minimum_age=minimum_age,
            maximum_age=maximum_age,
            sex=sex,
            drug_info=drug_info,
            # Location flags
            trial_run_in_europe=trial_run_in_europe,
            trial_run_in_us=trial_run_in_us,
            trial_run_in_china=trial_run_in_china,
            # Parsed from interventions
            generic_name=generic_name_extracted,
            dosage=dosage_extracted,
            type_of_dosing=dosing_extracted,
            mechanism_of_action=mechanism_of_action,
            target_protein=target_protein,
            type_of_therapy=type_of_therapy,
            brand_name=brand_name,
            # Parsed from eligibility criteria
            chemotherapy_naive=eligibility_data.get("chemotherapy_naive"),
            chemotherapy_failed=eligibility_data.get("chemotherapy_failed"),
            ici_naive=eligibility_data.get("ici_naive"),
            ici_failed=eligibility_data.get("ici_failed"),
            ipilimumab_failure=eligibility_data.get("ipilimumab_failure"),
            anti_pd1_failure=eligibility_data.get("anti_pd1_failure"),
            braf_mutation=eligibility_data.get("braf_mutation"),
            nras_mutation=eligibility_data.get("nras_mutation"),
            mutation_status=eligibility_data.get("mutation_status"),  # type: ignore[arg-type]
            biomarker_inclusion=biomarker_inclusion,
            biomarkers_inclusion_criteria=biomarkers_inclusion_criteria,
            biomarkers_exclusion_criteria=biomarkers_exclusion_criteria,
            # Treatment arms (arm-specific data)
            treatment_arms=treatment_arms,
            # Legacy fields (from first arm for backward compatibility)
            biosimilar=None,  # Not easily extractable from API
            sub_therapy=first_arm.sub_therapy if first_arm else None,
        )

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

        variants = COUNTRY_VARIANTS.get(target_country, [target_country])
        locations_lower = locations_str.lower()

        for variant in variants:
            if variant.lower() in locations_lower:
                return True

        return False

    def _parse_conditions_from_list(
        self, conditions_list: list[str]
    ) -> tuple[Optional[str], Optional[bool]]:
        """Parse conditions list to extract normalized cancer type and biomarker inclusion.

        Args:
            conditions_list: List of condition strings

        Returns:
            Tuple of (normalized_cancer_type, biomarker_inclusion)
        """
        if not conditions_list:
            return None, None

        # Combine all conditions into a single string for normalization
        # This handles cases where multiple conditions are listed
        combined_conditions = ", ".join(
            [c for c in conditions_list if isinstance(c, str)]
        )

        # Use the centralized normalization utility
        normalized_cancer_type = get_primary_cancer_type(combined_conditions)

        # If normalization returned "Review Required", try to extract from individual conditions
        if normalized_cancer_type == "Review Required":
            # Try normalizing each condition individually
            for condition in conditions_list:
                if isinstance(condition, str):
                    normalized = get_primary_cancer_type(condition)
                    if normalized != "Review Required":
                        normalized_cancer_type = normalized
                        break

        # Set to None if still "Review Required" (so it's not stored as a value)
        if normalized_cancer_type == "Review Required":
            normalized_cancer_type = None

        # Extract biomarker inclusion information
        biomarker_inclusion = None
        for condition in conditions_list:
            if isinstance(condition, str):
                condition_lower = condition.lower()

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

        if biomarker_inclusion is None:
            biomarker_inclusion = False

        return normalized_cancer_type, biomarker_inclusion

    def _parse_arms_and_interventions(
        self, interventions_module: dict, eligibility_criteria: str = ""
    ) -> list[TreatmentArm]:
        """Parse arms and interventions to create TreatmentArm objects.

        Args:
            interventions_module: The armsInterventionsModule from the API response

        Returns:
            List of TreatmentArm objects
        """
        if not interventions_module:
            return []

        arm_groups = interventions_module.get("armGroups", [])
        interventions = interventions_module.get("interventions", [])

        # Create a lookup dictionary for interventions for easy access
        # Map by both full name and base name (e.g., "Biological: pembrolizumab" -> "pembrolizumab")
        intervention_map = {}
        for item in interventions:
            name = item.get("name")
            if name:
                intervention_map[name] = item
                # Also map without prefix (e.g., "Biological: pembrolizumab" -> "pembrolizumab")
                if ": " in name:
                    base_name = name.split(": ", 1)[1]
                    intervention_map[base_name] = item

        parsed_arms = []

        for arm in arm_groups:
            arm_label = arm.get("label", "Unknown Arm")
            arm_description = arm.get("description", "")
            arm_type = arm.get("type")  # e.g., "Experimental", "Active Comparator"
            arm_intervention_names = arm.get("interventionNames", [])

            # Combine all intervention descriptions for this arm
            # Also include arm description as it often contains dosage info
            intervention_text_list = [arm_description] if arm_description else []

            for name in arm_intervention_names:
                # Try exact match first
                intervention_obj = intervention_map.get(name)
                if not intervention_obj and ": " in name:
                    # Try without prefix
                    base_name = name.split(": ", 1)[1]
                    intervention_obj = intervention_map.get(base_name)

                if intervention_obj:
                    # Add both name and description for parsing
                    intervention_text_list.append(intervention_obj.get("name", ""))
                    intervention_text_list.append(
                        intervention_obj.get("description", "")
                    )

            full_intervention_text = " ".join(intervention_text_list)

            # Parse intervention details for this arm
            intervention_details = self._parse_intervention_details(
                full_intervention_text
            )

            # Determine line of treatment for this arm
            # Combine eligibility criteria and arm description for context
            line_of_treatment = self._determine_line_of_treatment(
                eligibility_criteria, arm_description
            )

            # Create TreatmentArm object
            treatment_arm = TreatmentArm(
                arm_label=arm_label,
                arm_description=arm_description,
                arm_type=arm_type,
                intervention_names=arm_intervention_names,
                generic_name=intervention_details.get("generic_name"),
                brand_name=intervention_details.get("brand_name"),
                dosage=intervention_details.get("dosage"),
                type_of_dosing=intervention_details.get("type_of_dosing"),
                mechanism_of_action=intervention_details.get("mechanism_of_action"),
                target_protein=intervention_details.get("target_protein"),
                type_of_therapy=intervention_details.get("type_of_therapy"),
                sub_therapy=None,  # Could be enhanced later
                line_of_treatment=line_of_treatment,
            )

            parsed_arms.append(treatment_arm)

        return parsed_arms

    def _parse_intervention_details(
        self, intervention_text: str
    ) -> dict[str, Optional[str]]:
        """Comprehensively parse intervention text to extract all drug-related attributes.

        Args:
            intervention_text: Combined text from intervention names and descriptions

        Returns:
            Dictionary with all extracted intervention attributes
        """
        if not intervention_text:
            return {
                "generic_name": None,
                "dosage": None,
                "type_of_dosing": None,
                "mechanism_of_action": None,
                "target_protein": None,
                "type_of_therapy": None,
                "brand_name": None,
            }

        text_lower = intervention_text.lower()

        # Dosage patterns
        dosage_pattern = re.compile(
            r"\b(\d+\s*(?:mg|mg/kg|mcg|g|units?))(?:/\w+)?\b", re.IGNORECASE
        )
        dosage_match = dosage_pattern.search(intervention_text)
        dosage = dosage_match.group(1) if dosage_match else None

        # Dosing schedule patterns
        schedule_patterns = [
            re.compile(
                r"every\s+\d+\s+(?:week|weeks|day|days|month|months)", re.IGNORECASE
            ),
            re.compile(r"\bq\d+w\b", re.IGNORECASE),  # Q3W, Q4W, etc.
            re.compile(r"once\s+(?:weekly|daily|monthly|twice)", re.IGNORECASE),
            re.compile(r"twice\s+(?:daily|weekly)", re.IGNORECASE),
            re.compile(r"\d+x\s+per\s+(?:day|week|month)", re.IGNORECASE),
        ]
        type_of_dosing = None
        for pat in schedule_patterns:
            schedule_match = pat.search(intervention_text)
            if schedule_match:
                type_of_dosing = schedule_match.group(0)
                break

        # Generic name extraction (improved)
        generic_name = None
        # Known drug names (prioritize these)
        known_drugs = [
            "pembrolizumab",
            "nivolumab",
            "ipilimumab",
            "dabrafenib",
            "trametinib",
            "vemurafenib",
            "cobimetinib",
            "encorafenib",
            "binimetinib",
        ]
        text_lower = intervention_text.lower()
        for drug in known_drugs:
            if drug in text_lower:
                generic_name = drug.capitalize()
                break

        # If not found in known drugs, try pattern matching
        if not generic_name:
            # Look for capitalized drug names (common pattern)
            name_pattern = re.compile(
                r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:hydrochloride|sodium|mesylate))?)\b"
            )
            name_matches = name_pattern.findall(intervention_text)
            if name_matches:
                common_words = {
                    "the",
                    "and",
                    "or",
                    "with",
                    "for",
                    "to",
                    "of",
                    "in",
                    "on",
                    "via",
                    "plus",
                    "versus",
                    "part",
                    "participants",
                    "receive",
                    "administered",
                    "therapy",
                }
                for match in name_matches:
                    if (
                        match.lower() not in common_words
                        and len(match) > 3
                        and not match.lower().startswith("mg")
                        and not match.lower().startswith("iv")
                    ):
                        generic_name = match
                        break

        # Brand name extraction
        brand_name = None
        brand_patterns = [
            re.compile(
                r"\b(Keytruda|Pembrolizumab|Opdivo|Nivolumab|Yervoy|Ipilimumab)\b",
                re.IGNORECASE,
            ),
            re.compile(r"\b(Tafinlar|Dabrafenib|Mekinist|Trametinib)\b", re.IGNORECASE),
            re.compile(r"\b(Zelboraf|Vemurafenib)\b", re.IGNORECASE),
        ]
        for pattern in brand_patterns:
            brand_match = pattern.search(intervention_text)
            if brand_match:
                brand_name = brand_match.group(1)
                break

        # Mechanism of action (improved detection)
        mechanism_of_action = None
        moa_keywords = {
            # PD-1/PD-L1 inhibitors
            "anti-pd-1": "PD-1 inhibitor",
            "anti-pd1": "PD-1 inhibitor",
            "anti pd-1": "PD-1 inhibitor",
            "anti-pd-l1": "PD-L1 inhibitor",
            "anti-pdl1": "PD-L1 inhibitor",
            "anti pd-l1": "PD-L1 inhibitor",
            "pd-1 inhibitor": "PD-1 inhibitor",
            "pd1 inhibitor": "PD-1 inhibitor",
            "pd-l1 inhibitor": "PD-L1 inhibitor",
            "pembrolizumab": "PD-1 inhibitor",  # Pembrolizumab is a PD-1 inhibitor
            "nivolumab": "PD-1 inhibitor",  # Nivolumab is a PD-1 inhibitor
            "keytruda": "PD-1 inhibitor",
            "opdivo": "PD-1 inhibitor",
            # CTLA-4 inhibitors
            "anti-ctla-4": "CTLA-4 inhibitor",
            "anti-ctla4": "CTLA-4 inhibitor",
            "ctla-4 inhibitor": "CTLA-4 inhibitor",
            "ipilimumab": "CTLA-4 inhibitor",
            "yervoy": "CTLA-4 inhibitor",
            # BRAF inhibitors
            "braf inhibitor": "BRAF inhibitor",
            "braf": "BRAF inhibitor",
            "dabrafenib": "BRAF inhibitor",
            "vemurafenib": "BRAF inhibitor",
            "tafinlar": "BRAF inhibitor",
            "zelboraf": "BRAF inhibitor",
            "encorafenib": "BRAF inhibitor",
            # MEK inhibitors
            "mek inhibitor": "MEK inhibitor",
            "mek": "MEK inhibitor",
            "trametinib": "MEK inhibitor",
            "cobimetinib": "MEK inhibitor",
            "binimetinib": "MEK inhibitor",
            "mekinist": "MEK inhibitor",
            # General categories
            "checkpoint inhibitor": "Immune checkpoint inhibitor",
            "immunotherapy": "Immunotherapy",
            "targeted therapy": "Targeted therapy",
            "monoclonal antibody": "Monoclonal antibody",
            "tyrosine kinase inhibitor": "Tyrosine kinase inhibitor",
            "tki": "Tyrosine kinase inhibitor",
        }
        for keyword, moa in moa_keywords.items():
            if keyword in text_lower:
                mechanism_of_action = moa
                break

        # Target protein (improved detection)
        target_protein = None
        target_keywords = {
            # PD-1/PD-L1
            "pd-1": "PD-1",
            "pd1": "PD-1",
            "programmed cell death-1": "PD-1",
            "programmed cell death 1": "PD-1",
            "pd-l1": "PD-L1",
            "pdl1": "PD-L1",
            "programmed death-ligand 1": "PD-L1",
            "programmed death ligand 1": "PD-L1",
            # CTLA-4
            "ctla-4": "CTLA-4",
            "ctla4": "CTLA-4",
            "cytotoxic t-lymphocyte antigen-4": "CTLA-4",
            # BRAF/MEK
            "braf": "BRAF",
            "braf v600": "BRAF",
            "mek": "MEK",
            "mitogen-activated protein kinase": "MEK",
            # Other targets
            "vegf": "VEGF",
            "egfr": "EGFR",
            "her2": "HER2",
        }
        # Check for drug-specific targets
        if (
            "pembrolizumab" in text_lower
            or "nivolumab" in text_lower
            or "keytruda" in text_lower
            or "opdivo" in text_lower
        ):
            target_protein = "PD-1"
        elif "ipilimumab" in text_lower or "yervoy" in text_lower:
            target_protein = "CTLA-4"
        elif (
            "dabrafenib" in text_lower
            or "vemurafenib" in text_lower
            or "encorafenib" in text_lower
        ):
            target_protein = "BRAF"
        elif (
            "trametinib" in text_lower
            or "cobimetinib" in text_lower
            or "binimetinib" in text_lower
        ):
            target_protein = "MEK"
        else:
            # Fallback to keyword matching
            for keyword, target in target_keywords.items():
                if keyword in text_lower:
                    target_protein = target
                    break

        # Type of therapy (improved detection)
        type_of_therapy = None
        # Determine from mechanism of action if available
        if mechanism_of_action:
            if (
                "checkpoint" in mechanism_of_action.lower()
                or "pd-1" in mechanism_of_action.lower()
                or "ctla-4" in mechanism_of_action.lower()
            ):
                type_of_therapy = "Immunotherapy"
            elif (
                "braf" in mechanism_of_action.lower()
                or "mek" in mechanism_of_action.lower()
                or "targeted" in mechanism_of_action.lower()
            ):
                type_of_therapy = "Targeted therapy"
            elif "immunotherapy" in mechanism_of_action.lower():
                type_of_therapy = "Immunotherapy"

        # Fallback to keyword matching
        if not type_of_therapy:
            therapy_keywords = {
                "immunotherapy": "Immunotherapy",
                "checkpoint inhibitor": "Immunotherapy",
                "targeted therapy": "Targeted therapy",
                "braf inhibitor": "Targeted therapy",
                "mek inhibitor": "Targeted therapy",
                "chemotherapy": "Chemotherapy",
                "combination therapy": "Combination therapy",
            }
            for keyword, therapy in therapy_keywords.items():
                if keyword in text_lower:
                    type_of_therapy = therapy
                    break

        return {
            "generic_name": generic_name,
            "dosage": dosage,
            "type_of_dosing": type_of_dosing,
            "mechanism_of_action": mechanism_of_action,
            "target_protein": target_protein,
            "type_of_therapy": type_of_therapy,
            "brand_name": brand_name,
        }

    def _parse_eligibility_criteria_comprehensive(
        self, eligibility_text: str
    ) -> dict[str, Optional[bool]]:
        """Comprehensively parse eligibility criteria to extract all interpretive attributes.

        Args:
            eligibility_text: Eligibility criteria text string

        Returns:
            Dictionary with all extracted eligibility flags
        """
        if not eligibility_text:
            return {}

        eligibility_lower = eligibility_text.lower()

        # Chemotherapy naive
        chemo_naive = None
        chemo_naive_positive = [
            "no prior chemotherapy",
            "chemotherapy naive",
            "chemo-naive",
            "no prior systemic therapy",
            "no prior treatment",
            "treatment naive",
            "previously untreated",
            "treatment-naive",
        ]
        if any(phrase in eligibility_lower for phrase in chemo_naive_positive):
            chemo_naive = True
        elif any(
            phrase in eligibility_lower
            for phrase in [
                "prior chemotherapy",
                "chemotherapy experienced",
                "previously treated",
            ]
        ):
            chemo_naive = False

        # Chemotherapy failed
        chemotherapy_failed = None
        chemo_failed_keywords = [
            "progressed on chemotherapy",
            "chemotherapy-refractory",
            "chemotherapy refractory",
            "chemotherapy resistant",
            "failed chemotherapy",
            "refractory to chemotherapy",
        ]
        if any(phrase in eligibility_lower for phrase in chemo_failed_keywords):
            chemotherapy_failed = True

        # ICI naive
        ici_naive = None
        ici_naive_positive = [
            "no prior immunotherapy",
            "ici naive",
            "ici-naive",
            "no prior checkpoint inhibitor",
            "no prior anti-pd",
            "no prior anti-ctla",
            "immunotherapy naive",
            "no prior anti-pd-1",
            "no prior anti-pd-l1",
        ]
        if any(phrase in eligibility_lower for phrase in ici_naive_positive):
            ici_naive = True
        elif any(
            phrase in eligibility_lower
            for phrase in [
                "prior immunotherapy",
                "prior checkpoint inhibitor",
                "prior anti-pd",
                "prior anti-ctla",
                "immunotherapy experienced",
            ]
        ):
            ici_naive = False

        # ICI failed
        ici_failed = None
        ici_failed_keywords = [
            "progressed on anti-pd-1",
            "progressed on anti-pd1",
            "progressed on anti-pd-l1",
            "progressed on immunotherapy",
            "immunotherapy failure",
            "ici-refractory",
            "ici refractory",
            "refractory to immunotherapy",
            "refractory to anti-pd-1",
            "refractory to checkpoint inhibitor",
        ]
        if any(phrase in eligibility_lower for phrase in ici_failed_keywords):
            ici_failed = True

        # Ipilimumab failure
        ipilimumab_failure = None
        ipi_failure_keywords = [
            "ipilimumab failure",
            "progressed on ipi",
            "progressed on ipilimumab",
            "ipilimumab-refractory",
            "ipilimumab refractory",
            "refractory to ipilimumab",
            "yervoy failure",
        ]
        if any(phrase in eligibility_lower for phrase in ipi_failure_keywords):
            ipilimumab_failure = True

        # Anti-PD-1/L1 failure
        anti_pd1_failure = None
        anti_pd1_failure_keywords = [
            "anti-pd-1 failure",
            "anti-pd1 failure",
            "anti-pd-l1 failure",
            "pembrolizumab refractory",
            "pembrolizumab-refractory",
            "nivolumab refractory",
            "nivolumab-refractory",
            "keytruda refractory",
            "opdivo refractory",
            "refractory to pembrolizumab",
            "refractory to nivolumab",
            "refractory to anti-pd-1",
            "refractory to anti-pd-l1",
        ]
        if any(phrase in eligibility_lower for phrase in anti_pd1_failure_keywords):
            anti_pd1_failure = True

        # BRAF mutation
        braf_mutation = None
        braf_positive = [
            "braf mutation",
            "braf v600",
            "braf positive",
            "braf mutated",
            "braf-mutant",
            "braf mutant",
            "braf v600e",
            "braf v600k",
        ]
        braf_negative = [
            "braf wild-type",
            "braf negative",
            "no braf mutation",
            "braf wt",
        ]
        if any(phrase in eligibility_lower for phrase in braf_positive):
            braf_mutation = True
        elif any(phrase in eligibility_lower for phrase in braf_negative):
            braf_mutation = False

        # NRAS mutation
        nras_mutation = None
        nras_positive = [
            "nras mutation",
            "nras positive",
            "nras mutated",
            "nras-mutant",
            "nras mutant",
        ]
        nras_negative = [
            "nras wild-type",
            "nras negative",
            "no nras mutation",
            "nras wt",
        ]
        if any(phrase in eligibility_lower for phrase in nras_positive):
            nras_mutation = True
        elif any(phrase in eligibility_lower for phrase in nras_negative):
            nras_mutation = False

        # Mutation status (combined)
        mutation_status: Optional[str] = None
        if braf_mutation is True:
            mutation_status = "BRAF-mutant"
        elif nras_mutation is True:
            mutation_status = "NRAS-mutant"
        elif braf_mutation is False and nras_mutation is False:
            mutation_status = "Wild-type"

        return {
            "chemotherapy_naive": chemo_naive,
            "chemotherapy_failed": chemotherapy_failed,
            "ici_naive": ici_naive,
            "ici_failed": ici_failed,
            "ipilimumab_failure": ipilimumab_failure,
            "anti_pd1_failure": anti_pd1_failure,
            "braf_mutation": braf_mutation,
            "nras_mutation": nras_mutation,
            "mutation_status": mutation_status,  # type: ignore[dict-item]
        }

    def _determine_line_of_treatment(
        self, eligibility_text: str, arm_description: Optional[str] = None
    ) -> Optional[str]:
        """Determine line of treatment for a specific arm.

        Returns one of: "Neoadjuvant", "First Line", "2nd Line", "3rd Line+"

        Logic:
        - Neoadjuvant: treatment before surgery
        - First Line: previously untreated, treatment naive
        - 2nd Line: first treatment failed (progressed on, refractory to first treatment)
        - 3rd Line+: second treatment failed (progressed on, refractory to second treatment)

        Args:
            eligibility_text: Full eligibility criteria text
            arm_description: Optional arm description for additional context

        Returns:
            Line of treatment classification or None
        """
        if not eligibility_text:
            return None

        text_to_analyze = eligibility_text.lower()
        if arm_description:
            text_to_analyze += " " + arm_description.lower()

        # Check for Neoadjuvant (treatment before surgery)
        neoadjuvant_keywords = [
            "neoadjuvant",
            "pre-operative",
            "preoperative",
            "before surgery",
            "prior to surgery",
        ]
        # Check if it mentions surgery before treatment (neoadjuvant context)
        if (
            "adjuvant" not in text_to_analyze
            and "before" in text_to_analyze
            and "surgery" in text_to_analyze
        ):
            # Additional context check for neoadjuvant
            if "treatment" in text_to_analyze or "therapy" in text_to_analyze:
                return "Neoadjuvant"

        # Direct neoadjuvant keywords
        if any(keyword in text_to_analyze for keyword in neoadjuvant_keywords):
            return "Neoadjuvant"

        # Check for 3rd Line+ (second treatment failed)
        # Keywords indicating failure of second-line treatment
        third_line_plus_keywords = [
            "progressed on second",
            "refractory to second",
            "failed second",
            "second-line treatment failed",
            "second line treatment failed",
            "progressed after second",
            "heavily pretreated",
            "multiple prior",
            "two or more prior",
            "2 or more prior",
            "≥2 prior",
            ">=2 prior",
        ]
        if any(keyword in text_to_analyze for keyword in third_line_plus_keywords):
            return "3rd Line+"

        # Check for First Line FIRST (previously untreated, treatment naive)
        # This must be checked before 2nd line to avoid false positives
        first_line_keywords = [
            "previously untreated",
            "treatment naive",
            "treatment-naive",
            "treatment naïve",  # With accent
            "chemo-naive",
            "chemotherapy naive",
            "ici naive",
            "ici-naive",
            "no prior",
            "first-line",
            "first line",
            "1st-line",
            "1st line",
        ]
        if any(keyword in text_to_analyze for keyword in first_line_keywords):
            return "First Line"

        # Check for 2nd Line (first treatment failed)
        # Keywords indicating failure of first-line treatment
        second_line_keywords = [
            "progressed on",
            "refractory to",
            "failed",
            "after",
            "previously treated",
            "prior treatment",
            "chemotherapy failed",
            "chemotherapy-refractory",
            "ici failed",
            "immunotherapy failure",
            "anti-pd-1 failure",
            "anti-pd1 failure",
            "ipilimumab failure",
        ]

        has_second_line_indicator = any(
            keyword in text_to_analyze for keyword in second_line_keywords
        )

        if has_second_line_indicator:
            return "2nd Line"

        return None

    def _extract_biomarker_inclusion_criteria(
        self, eligibility_text: str
    ) -> Optional[str]:
        """Extract biomarker inclusion criteria from eligibility text.

        Args:
            eligibility_text: Full eligibility criteria text

        Returns:
            Extracted inclusion criteria text or None
        """
        if not eligibility_text:
            return None

        # Look for inclusion sections mentioning biomarkers
        inclusion_keywords = [
            "must have",
            "required",
            "inclusion",
            "biomarker",
            "pd-l1",
            "pdl1",
            "pd1",
            "braf",
            "nras",
            "mutation",
            "expression",
        ]

        sentences = re.split(r"[.!?]\s+", eligibility_text)
        inclusion_sentences = []

        for sentence in sentences:
            sentence_lower = sentence.lower()
            if any(keyword in sentence_lower for keyword in inclusion_keywords):
                # Check if it's an inclusion (not exclusion)
                if not any(
                    word in sentence_lower
                    for word in ["exclusion", "exclude", "not have", "without"]
                ):
                    inclusion_sentences.append(sentence.strip())

        if inclusion_sentences:
            return " ".join(inclusion_sentences[:3])  # Limit to first 3 sentences

        return None

    def _extract_biomarker_exclusion_criteria(
        self, eligibility_text: str
    ) -> Optional[str]:
        """Extract biomarker exclusion criteria from eligibility text.

        Args:
            eligibility_text: Full eligibility criteria text

        Returns:
            Extracted exclusion criteria text or None
        """
        if not eligibility_text:
            return None

        exclusion_keywords = [
            "exclusion",
            "exclude",
            "not have",
            "without",
            "must not",
            "cannot have",
        ]

        sentences = re.split(r"[.!?]\s+", eligibility_text)
        exclusion_sentences = []

        for sentence in sentences:
            sentence_lower = sentence.lower()
            if any(keyword in sentence_lower for keyword in exclusion_keywords):
                # Check if it mentions biomarkers
                if any(
                    word in sentence_lower
                    for word in [
                        "biomarker",
                        "pd-l1",
                        "pdl1",
                        "pd1",
                        "braf",
                        "nras",
                        "mutation",
                    ]
                ):
                    exclusion_sentences.append(sentence.strip())

        if exclusion_sentences:
            return " ".join(exclusion_sentences[:3])  # Limit to first 3 sentences

        return None
