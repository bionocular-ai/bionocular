"""Domain models for clinical trial data."""

from dataclasses import dataclass, field


@dataclass
class TreatmentArm:
    """Domain model for a single treatment arm within a clinical trial."""

    arm_label: str  # e.g., "Experimental: Pembrolizumab"
    arm_description: str | None = None
    arm_type: str | None = (
        None  # e.g., "Experimental", "Active Comparator", "Placebo Comparator"
    )

    # Arm-specific intervention attributes
    generic_name: str | None = None
    brand_name: str | None = None
    dosage: str | None = None
    type_of_dosing: str | None = None
    mechanism_of_action: str | None = None
    target_protein: str | None = None
    type_of_therapy: str | None = None
    sub_therapy: str | None = None
    line_of_treatment: str | None = (
        None  # Arm-specific: "Neoadjuvant", "First Line", "2nd Line", "3rd Line+"
    )

    # Intervention names for this arm
    intervention_names: list[str] = field(default_factory=list)


@dataclass
class ClinicalTrialData:
    """Domain model for clinical trial information from API.

    Contains study-wide attributes and a list of treatment arms.
    """

    nct_number: str
    trial_name: str | None = None
    cancer_type: str | None = None
    primary_endpoint: str | None = None
    secondary_endpoint: str | None = None
    study_start_date: str | None = None
    primary_completion_date: str | None = None  # Primary completion date
    study_completion_date: str | None = None
    first_results: str | None = None
    trial_locations: str | None = None
    sponsors: str | None = None
    clinical_trial_phase: str | None = None
    study_type: str | None = None  # e.g., "Interventional", "Observational"
    number_of_patients: int | None = None
    minimum_age: str | None = None
    maximum_age: str | None = None
    sex: str | None = None
    drug_info: str | None = (
        None  # Combined intervention names for backward compatibility
    )

    # Study-wide eligibility attributes (apply to all arms)
    trial_run_in_europe: bool | None = None
    trial_run_in_us: bool | None = None
    trial_run_in_china: bool | None = None
    chemotherapy_naive: bool | None = None
    chemotherapy_failed: bool | None = None
    ici_naive: bool | None = None
    ici_failed: bool | None = None
    ipilimumab_failure: bool | None = None
    anti_pd1_failure: bool | None = None
    mutation_status: str | None = None
    braf_mutation: bool | None = None
    nras_mutation: bool | None = None
    biosimilar: bool | None = None
    biomarker_inclusion: bool | None = None
    biomarkers_inclusion_criteria: str | None = None
    biomarkers_exclusion_criteria: str | None = None

    # Treatment arms (arm-specific data)
    treatment_arms: list[TreatmentArm] = field(default_factory=list)

    # Legacy fields for backward compatibility (deprecated - use treatment_arms instead)
    generic_name: str | None = None  # From first arm if available
    brand_name: str | None = None  # From first arm if available
    dosage: str | None = None  # From first arm if available
    type_of_dosing: str | None = None  # From first arm if available
    mechanism_of_action: str | None = None  # From first arm if available
    target_protein: str | None = None  # From first arm if available
    type_of_therapy: str | None = None  # From first arm if available
    sub_therapy: str | None = None  # From first arm if available
