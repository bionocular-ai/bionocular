"""Domain models for clinical trial data."""

from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class TreatmentArm:
    """Domain model for a single treatment arm within a clinical trial."""

    arm_label: str  # e.g., "Experimental: Pembrolizumab"
    arm_description: Optional[str] = None
    arm_type: Optional[str] = None  # e.g., "Experimental", "Active Comparator", "Placebo Comparator"

    # Arm-specific intervention attributes
    generic_name: Optional[str] = None
    brand_name: Optional[str] = None
    dosage: Optional[str] = None
    type_of_dosing: Optional[str] = None
    mechanism_of_action: Optional[str] = None
    target_protein: Optional[str] = None
    type_of_therapy: Optional[str] = None
    sub_therapy: Optional[str] = None
    line_of_treatment: Optional[str] = None  # Arm-specific: "Neoadjuvant", "First Line", "2nd Line", "3rd Line+"

    # Intervention names for this arm
    intervention_names: List[str] = field(default_factory=list)


@dataclass
class ClinicalTrialData:
    """Domain model for clinical trial information from API.

    Contains study-wide attributes and a list of treatment arms.
    """

    nct_number: str
    trial_name: Optional[str] = None
    cancer_type: Optional[str] = None
    primary_endpoint: Optional[str] = None
    secondary_endpoint: Optional[str] = None
    study_start_date: Optional[str] = None
    primary_completion_date: Optional[str] = None  # Primary completion date
    study_completion_date: Optional[str] = None
    first_results: Optional[str] = None
    trial_locations: Optional[str] = None
    sponsors: Optional[str] = None
    clinical_trial_phase: Optional[str] = None
    study_type: Optional[str] = None  # e.g., "Interventional", "Observational"
    number_of_patients: Optional[int] = None
    minimum_age: Optional[str] = None
    maximum_age: Optional[str] = None
    sex: Optional[str] = None
    drug_info: Optional[str] = None  # Combined intervention names for backward compatibility

    # Study-wide eligibility attributes (apply to all arms)
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

    # Treatment arms (arm-specific data)
    treatment_arms: List[TreatmentArm] = field(default_factory=list)

    # Legacy fields for backward compatibility (deprecated - use treatment_arms instead)
    generic_name: Optional[str] = None  # From first arm if available
    brand_name: Optional[str] = None  # From first arm if available
    dosage: Optional[str] = None  # From first arm if available
    type_of_dosing: Optional[str] = None  # From first arm if available
    mechanism_of_action: Optional[str] = None  # From first arm if available
    target_protein: Optional[str] = None  # From first arm if available
    type_of_therapy: Optional[str] = None  # From first arm if available
    sub_therapy: Optional[str] = None  # From first arm if available

