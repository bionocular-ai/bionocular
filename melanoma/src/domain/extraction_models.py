"""Domain models for clinical trial attribute extraction.

This module contains the core business entities and value objects
for the extraction system, following clean architecture principles.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field, validator


class AttributeType(str, Enum):
    """Enumeration of extractable clinical trial attributes.

    Order matches the desired output sequence for clinical trial data extraction.
    """

    # General Parameters (Abstract-level) - First Section
    ABSTRACT_NUMBER = "abstract_number"
    NCT_NUMBER = "nct_number"
    TRIAL_NAME = "trial_name"
    CANCER_TYPE = "cancer_type"
    CANCER_STAGE = "cancer_stage"

    # Company and Sponsors
    COMPANY_EU = "company_eu"  # Note: Not yet implemented
    COMPANY_US = "company_us"  # Note: Not yet implemented
    COMPANY_CHINA = "company_china"  # Note: Not yet implemented
    SPONSORS = "sponsors"

    # Trial Characteristics
    CLINICAL_TRIAL_PHASE = "clinical_trial_phase"
    STUDY_TYPE = "study_type"  # e.g., "Interventional", "Observational"
    CHEMOTHERAPY_NAIVE = "chemotherapy_naive"
    CHEMOTHERAPY_FAILED = "chemotherapy_failed"
    ICI_NAIVE = "ici_naive"
    ICI_FAILED = "ici_failed"
    IPILIMUMAB_FAILURE = "ipilimumab_failure"
    ANTI_PD1_FAILURE = "anti_pd1_failure"
    MUTATION_STATUS = "mutation_status"
    BRAF_MUTATION = "braf_mutation"
    NRAS_MUTATION = "nras_mutation"
    BIOSIMILAR = "biosimilar"
    LINE_OF_TREATMENT = (
        "line_of_treatment"  # e.g., "first-line", "second-line", "previously untreated"
    )
    MODALITY = "modality"  # arm-level, derived from drug_knowledge (Antibody, Small Molecule, ADC, ...)
    TARGET = "target"  # arm-level, derived from drug_knowledge (PD-1, BRAF, MEK, ...)

    # Endpoints and Biomarkers
    PRIMARY_ENDPOINT = "primary_endpoint"
    SECONDARY_ENDPOINT = "secondary_endpoint"
    BIOMARKER_INCLUSION = "biomarker_inclusion"
    BIOMARKERS_INCLUSION_CRITERIA = "biomarkers_inclusion_criteria"
    BIOMARKERS_EXCLUSION_CRITERIA = "biomarkers_exclusion_criteria"

    # Trial Timeline
    STUDY_START_DATE = "study_start_date"
    PRIMARY_COMPLETION_DATE = (
        "primary_completion_date"  # Primary completion date (estimated or actual)
    )
    STUDY_COMPLETION_DATE = "study_completion_date"
    FIRST_RESULTS = "first_results"

    # Trial Geography
    TRIAL_RUN_IN_EUROPE = "trial_run_in_europe"
    TRIAL_RUN_IN_US = "trial_run_in_us"
    TRIAL_RUN_IN_CHINA = "trial_run_in_china"

    # Treatment Details (Arm-level)
    GENERIC_NAME = "generic_name"
    BRAND_NAME = "brand_name"
    DOSAGE = "dosage"
    TYPE_OF_DOSING = "type_of_dosing"
    MECHANISM_OF_ACTION = "mechanism_of_action"
    TARGET_PROTEIN = "target_protein"
    TYPE_OF_THERAPY = "type_of_therapy"
    SUB_THERAPY = "sub_therapy"  # Moved after TYPE_OF_THERAPY

    # Patient Demographics
    MEDIAN_AGE = "median_age"
    NUMBER_OF_PATIENTS = "number_of_patients"

    # Efficacy - Survival Metrics (PFS)
    MEDIAN_PFS = "median_pfs"
    MEDIAN_FOLLOWUP_PFS = "median_followup_pfs"
    P_VALUE_PFS = "p_value_pfs"
    HR_PFS = "hr_pfs"
    CI_HR_PFS = "ci_hr_pfs"

    # Efficacy - Survival Metrics (OS)
    MEDIAN_OS = "median_os"
    MEDIAN_FOLLOWUP_OS = "median_followup_os"
    P_VALUE_OS = "p_value_os"
    HR_OS = "hr_os"
    CI_HR_OS = "ci_hr_os"

    # Efficacy - Response Rates
    OBJECTIVE_RESPONSE_RATE = "objective_response_rate"
    COMPLETE_RESPONSE = "complete_response"
    PATHOLOGICAL_COMPLETE_RESPONSE = "pathological_complete_response"
    COMPLETE_METABOLIC_RESPONSE = "complete_metabolic_response"
    DISEASE_CONTROL_RATE = "disease_control_rate"
    CLINICAL_BENEFIT_RATE = "clinical_benefit_rate"
    MEDIAN_DOR = "median_dor"
    DOR_RATE = "dor_rate"

    # Efficacy - PFS Rates at Timepoints
    PFS_RATE_6M = "pfs_rate_6m"
    PFS_RATE_9M = "pfs_rate_9m"
    PFS_RATE_12M = "pfs_rate_12m"
    PFS_RATE_18M = "pfs_rate_18m"
    PFS_RATE_24M = "pfs_rate_24m"
    PFS_RATE_36M = "pfs_rate_36m"
    PFS_RATE_48M = "pfs_rate_48m"

    # Efficacy - OS Rates at Timepoints
    OS_RATE_6M = "os_rate_6m"
    OS_RATE_9M = "os_rate_9m"
    OS_RATE_12M = "os_rate_12m"
    OS_RATE_18M = "os_rate_18m"
    OS_RATE_24M = "os_rate_24m"
    OS_RATE_36M = "os_rate_36m"
    OS_RATE_48M = "os_rate_48m"

    # Efficacy - Other Survival Metrics (EFS)
    EFS = "efs"
    P_VALUE_EFS = "p_value_efs"
    HR_EFS = "hr_efs"
    CI_HR_EFS = "ci_hr_efs"

    # Efficacy - Other Survival Metrics (RFS)
    RFS = "rfs"
    P_VALUE_RFS = "p_value_rfs"
    LENGTH_RFS = "length_rfs"
    HR_RFS = "hr_rfs"
    CI_HR_RFS = "ci_hr_rfs"

    # Efficacy - Other Survival Metrics (MFS)
    MFS = "mfs"
    LENGTH_MFS = "length_mfs"
    HR_MFS = "hr_mfs"
    CI_HR_MFS = "ci_hr_mfs"

    # Efficacy - Time-to Metrics
    TTR = "ttr"
    TTP = "ttp"
    HR_TTP = "hr_ttp"
    CI_HR_TTP = "ci_hr_ttp"
    TTNT = "ttnt"
    TTF = "ttf"

    # Safety - Adverse Events (AE)
    AE = "ae"
    GRADE_3_PLUS_AE = "grade_3_plus_ae"
    AE_LEADING_TO_DISCONTINUATION = "ae_leading_to_discontinuation"
    SERIOUS_AE = "serious_ae"
    IMMUNE_RELATED_AE = "immune_related_ae"
    SERIOUS_IMMUNE_RELATED_AE = "serious_immune_related_ae"
    AE_LEADING_TO_DEATH = "ae_leading_to_death"
    AE_LEADING_TO_DOSE_REDUCTION = "ae_leading_to_dose_reduction"
    AE_LEADING_TO_DOSE_INTERRUPTION = "ae_leading_to_dose_interruption"
    AE_REQUIRING_HOSPITALIZATION = "ae_requiring_hospitalization"

    # Safety - Treatment-Emergent Adverse Events (TEAE)
    TEAE = "teae"
    GRADE_3_PLUS_TEAE = "grade_3_plus_teae"
    GRADE_3_TEAE = "grade_3_teae"
    GRADE_4_TEAE = "grade_4_teae"
    GRADE_5_TEAE = "grade_5_teae"
    TEAE_LEADING_TO_DISCONTINUATION = "teae_leading_to_discontinuation"
    TEAE_LEADING_TO_DEATH = "teae_leading_to_death"
    SERIOUS_TEAE = "serious_teae"
    TEAE_IMMUNE_RELATED = "teae_immune_related"
    TEAE_LEADING_TO_DOSE_REDUCTION = "teae_leading_to_dose_reduction"
    TEAE_LEADING_TO_DOSE_INTERRUPTION = "teae_leading_to_dose_interruption"
    TEAE_REQUIRING_HOSPITALIZATION = "teae_requiring_hospitalization"

    # Safety - Treatment-Related Adverse Events (TRAE)
    TRAE = "trae"
    GRADE_3_PLUS_TRAE = "grade_3_plus_trae"
    GRADE_3_TRAE = "grade_3_trae"
    GRADE_4_TRAE = "grade_4_trae"
    GRADE_5_TRAE = "grade_5_trae"
    TRAE_LEADING_TO_DISCONTINUATION = "trae_leading_to_discontinuation"
    TRAE_LEADING_TO_DEATH = "trae_leading_to_death"
    TRAE_IMMUNE_RELATED = "trae_immune_related"
    SERIOUS_TRAE = "serious_trae"
    TRAE_LEADING_TO_DOSE_REDUCTION = "trae_leading_to_dose_reduction"
    TRAE_LEADING_TO_DOSE_INTERRUPTION = "trae_leading_to_dose_interruption"
    TRAE_REQUIRING_HOSPITALIZATION = "trae_requiring_hospitalization"

    # Safety - Specific Adverse Events
    CRS = "crs"
    IRR = "irr"
    WBC_DECREASED = "wbc_decreased"

    # Safety - Grade 3+ AE Specific Adverse Events
    GRADE_3_PLUS_AE_CRS = "grade_3_plus_ae_crs"
    GRADE_3_PLUS_AE_THROMBOCYTOPENIA = "grade_3_plus_ae_thrombocytopenia"
    GRADE_3_PLUS_AE_NEUTROPENIA = "grade_3_plus_ae_neutropenia"
    GRADE_3_PLUS_AE_LEUKOPENIA = "grade_3_plus_ae_leukopenia"
    GRADE_3_PLUS_AE_NAUSEA = "grade_3_plus_ae_nausea"
    GRADE_3_PLUS_AE_ANEMIA = "grade_3_plus_ae_anemia"
    GRADE_3_PLUS_AE_DIARRHEA = "grade_3_plus_ae_diarrhea"
    GRADE_3_PLUS_AE_COLITIS = "grade_3_plus_ae_colitis"
    GRADE_3_PLUS_AE_HYPERGLYCEMIA = "grade_3_plus_ae_hyperglycemia"
    GRADE_3_PLUS_AE_NEUTROPHIL_COUNT_DECREASED = (
        "grade_3_plus_ae_neutrophil_count_decreased"
    )
    GRADE_3_PLUS_AE_DYSPNEA = "grade_3_plus_ae_dyspnea"
    GRADE_3_PLUS_AE_PYREXIA = "grade_3_plus_ae_pyrexia"
    GRADE_3_PLUS_AE_BLEEDING = "grade_3_plus_ae_bleeding"
    GRADE_3_PLUS_AE_PRURITUS = "grade_3_plus_ae_pruritus"
    GRADE_3_PLUS_AE_RASH = "grade_3_plus_ae_rash"
    GRADE_3_PLUS_AE_PNEUMONIA = "grade_3_plus_ae_pneumonia"
    GRADE_3_PLUS_AE_THYROIDITIS = "grade_3_plus_ae_thyroiditis"
    GRADE_3_PLUS_AE_HYPOPHYSITIS = "grade_3_plus_ae_hypophysitis"
    GRADE_3_PLUS_AE_HEPATITIS = "grade_3_plus_ae_hepatitis"
    GRADE_3_PLUS_AE_PNEUMONITIS = "grade_3_plus_ae_pneumonitis"
    GRADE_3_PLUS_AE_ALANINE_AMINOTRANSFERASE = (
        "grade_3_plus_ae_alanine_aminotransferase"
    )
    GRADE_3_PLUS_AE_WBC_DECREASED = "grade_3_plus_ae_wbc_decreased"
    GRADE_3_PLUS_AE_IMMUNE_RELATED = "grade_3_plus_ae_immune_related"
    GRADE_3_PLUS_AE_IRR = "grade_3_plus_ae_irr"
    GRADE_3_PLUS_AE_FATIGUE = "grade_3_plus_ae_fatigue"
    GRADE_3_PLUS_AE_HYPOTHYROIDISM = "grade_3_plus_ae_hypothyroidism"
    GRADE_3_PLUS_AE_HYPERTHYROIDISM = "grade_3_plus_ae_hyperthyroidism"
    GRADE_3_PLUS_AE_AST_INCREASED = "grade_3_plus_ae_ast_increased"
    GRADE_3_PLUS_AE_VOMITING = "grade_3_plus_ae_vomiting"

    # Safety - Grade 3+ TRAE Specific Adverse Events
    GRADE_3_PLUS_TRAE_IMMUNE_RELATED = "grade_3_plus_trae_immune_related"
    GRADE_3_PLUS_TRAE_CRS = "grade_3_plus_trae_crs"
    GRADE_3_PLUS_TRAE_THROMBOCYTOPENIA = "grade_3_plus_trae_thrombocytopenia"
    GRADE_3_PLUS_TRAE_NEUTROPENIA = "grade_3_plus_trae_neutropenia"
    GRADE_3_PLUS_TRAE_LEUKOPENIA = "grade_3_plus_trae_leukopenia"
    GRADE_3_PLUS_TRAE_NAUSEA = "grade_3_plus_trae_nausea"
    GRADE_3_PLUS_TRAE_ANEMIA = "grade_3_plus_trae_anemia"
    GRADE_3_PLUS_TRAE_DIARRHEA = "grade_3_plus_trae_diarrhea"
    GRADE_3_PLUS_TRAE_COLITIS = "grade_3_plus_trae_colitis"
    GRADE_3_PLUS_TRAE_HYPERGLYCEMIA = "grade_3_plus_trae_hyperglycemia"
    GRADE_3_PLUS_TRAE_NEUTROPHIL_COUNT_DECREASED = (
        "grade_3_plus_trae_neutrophil_count_decreased"
    )
    GRADE_3_PLUS_TRAE_DYSPNEA = "grade_3_plus_trae_dyspnea"
    GRADE_3_PLUS_TRAE_PYREXIA = "grade_3_plus_trae_pyrexia"
    GRADE_3_PLUS_TRAE_BLEEDING = "grade_3_plus_trae_bleeding"
    GRADE_3_PLUS_TRAE_PRURITUS = "grade_3_plus_trae_pruritus"
    GRADE_3_PLUS_TRAE_RASH = "grade_3_plus_trae_rash"
    GRADE_3_PLUS_TRAE_PNEUMONIA = "grade_3_plus_trae_pneumonia"
    GRADE_3_PLUS_TRAE_THYROIDITIS = "grade_3_plus_trae_thyroiditis"
    GRADE_3_PLUS_TRAE_HYPOPHYSITIS = "grade_3_plus_trae_hypophysitis"
    GRADE_3_PLUS_TRAE_HEPATITIS = "grade_3_plus_trae_hepatitis"
    GRADE_3_PLUS_TRAE_PNEUMONITIS = "grade_3_plus_trae_pneumonitis"
    GRADE_3_PLUS_TRAE_ALANINE_AMINOTRANSFERASE = (
        "grade_3_plus_trae_alanine_aminotransferase"
    )
    GRADE_3_PLUS_TRAE_WBC_DECREASED = "grade_3_plus_trae_wbc_decreased"
    GRADE_3_PLUS_TRAE_IRR = "grade_3_plus_trae_irr"
    GRADE_3_PLUS_TRAE_FATIGUE = "grade_3_plus_trae_fatigue"
    GRADE_3_PLUS_TRAE_HYPOTHYROIDISM = "grade_3_plus_trae_hypothyroidism"
    GRADE_3_PLUS_TRAE_HYPERTHYROIDISM = "grade_3_plus_trae_hyperthyroidism"
    GRADE_3_PLUS_TRAE_AST_INCREASED = "grade_3_plus_trae_ast_increased"
    GRADE_3_PLUS_TRAE_VOMITING = "grade_3_plus_trae_vomiting"

    # Safety - Grade 3+ TEAE Specific Adverse Events
    GRADE_3_PLUS_TEAE_IMMUNE_RELATED = "grade_3_plus_teae_immune_related"
    GRADE_3_PLUS_TEAE_CRS = "grade_3_plus_teae_crs"
    GRADE_3_PLUS_TEAE_THROMBOCYTOPENIA = "grade_3_plus_teae_thrombocytopenia"
    GRADE_3_PLUS_TEAE_NEUTROPENIA = "grade_3_plus_teae_neutropenia"
    GRADE_3_PLUS_TEAE_LEUKOPENIA = "grade_3_plus_teae_leukopenia"
    GRADE_3_PLUS_TEAE_NAUSEA = "grade_3_plus_teae_nausea"
    GRADE_3_PLUS_TEAE_ANEMIA = "grade_3_plus_teae_anemia"
    GRADE_3_PLUS_TEAE_DIARRHEA = "grade_3_plus_teae_diarrhea"
    GRADE_3_PLUS_TEAE_COLITIS = "grade_3_plus_teae_colitis"
    GRADE_3_PLUS_TEAE_HYPERGLYCEMIA = "grade_3_plus_teae_hyperglycemia"
    GRADE_3_PLUS_TEAE_NEUTROPHIL_COUNT_DECREASED = (
        "grade_3_plus_teae_neutrophil_count_decreased"
    )
    GRADE_3_PLUS_TEAE_DYSPNEA = "grade_3_plus_teae_dyspnea"
    GRADE_3_PLUS_TEAE_PYREXIA = "grade_3_plus_teae_pyrexia"
    GRADE_3_PLUS_TEAE_BLEEDING = "grade_3_plus_teae_bleeding"
    GRADE_3_PLUS_TEAE_PRURITUS = "grade_3_plus_teae_pruritus"
    GRADE_3_PLUS_TEAE_RASH = "grade_3_plus_teae_rash"
    GRADE_3_PLUS_TEAE_PNEUMONIA = "grade_3_plus_teae_pneumonia"
    GRADE_3_PLUS_TEAE_THYROIDITIS = "grade_3_plus_teae_thyroiditis"
    GRADE_3_PLUS_TEAE_HYPOPHYSITIS = "grade_3_plus_teae_hypophysitis"
    GRADE_3_PLUS_TEAE_HEPATITIS = "grade_3_plus_teae_hepatitis"
    GRADE_3_PLUS_TEAE_PNEUMONITIS = "grade_3_plus_teae_pneumonitis"
    GRADE_3_PLUS_TEAE_ALANINE_AMINOTRANSFERASE = (
        "grade_3_plus_teae_alanine_aminotransferase"
    )
    GRADE_3_PLUS_TEAE_WBC_DECREASED = "grade_3_plus_teae_wbc_decreased"
    GRADE_3_PLUS_TEAE_IRR = "grade_3_plus_teae_irr"
    GRADE_3_PLUS_TEAE_FATIGUE = "grade_3_plus_teae_fatigue"
    GRADE_3_PLUS_TEAE_HYPOTHYROIDISM = "grade_3_plus_teae_hypothyroidism"
    GRADE_3_PLUS_TEAE_HYPERTHYROIDISM = "grade_3_plus_teae_hyperthyroidism"
    GRADE_3_PLUS_TEAE_AST_INCREASED = "grade_3_plus_teae_ast_increased"
    GRADE_3_PLUS_TEAE_VOMITING = "grade_3_plus_teae_vomiting"

    # Metadata (for internal use)
    CONFERENCE = "conference"
    PUBLISHED_YEAR = "published_year"
    COMMENTS = "comments"
    MINIMUM_AGE = "minimum_age"
    MAXIMUM_AGE = "maximum_age"
    SEX = "sex"

    # Publication-level metadata
    PUBLICATION_NAME = "publication_name"
    PUBLICATION_YEAR = "publication_year"
    PDF_NUMBER = "pdf_number"


class AttributeFamily(str, Enum):
    """Coarse attribute groupings for grouped LLM extraction calls."""

    IDENTIFICATION = "identification"
    RESPONSE_RATES = "response_rates"
    PFS_FAMILY = "pfs_family"
    OS_FAMILY = "os_family"
    EFS_RFS_MFS = "efs_rfs_mfs"
    TIME_TO_METRICS = "time_to_metrics"
    AE_GENERAL = "ae_general"
    AE_GRADE3_SPECIFIC = "ae_grade3_specific"
    TEAE_GENERAL = "teae_general"
    TEAE_GRADE3_SPECIFIC = "teae_grade3_specific"
    TRAE_GENERAL = "trae_general"
    TRAE_GRADE3_SPECIFIC = "trae_grade3_specific"


DERIVED_ATTRIBUTES: frozenset[AttributeType] = frozenset(
    {
        AttributeType.MODALITY,
        AttributeType.TARGET,
    }
)

SEPARATOR_SOURCED_ATTRIBUTES: frozenset[AttributeType] = frozenset(
    {
        AttributeType.NUMBER_OF_PATIENTS,
        AttributeType.PDF_NUMBER,
        AttributeType.PUBLICATION_NAME,
        AttributeType.PUBLICATION_YEAR,
        AttributeType.CONFERENCE,
        AttributeType.PUBLISHED_YEAR,
    }
)

TRIAL_LEVEL_ATTRIBUTES: frozenset[AttributeType] = frozenset(
    {
        AttributeType.NCT_NUMBER,
        AttributeType.TRIAL_NAME,
        AttributeType.CANCER_TYPE,
        AttributeType.ABSTRACT_NUMBER,
    }
)

FAMILY_TO_ATTRIBUTES: dict[AttributeFamily, tuple[AttributeType, ...]] = {
    AttributeFamily.IDENTIFICATION: (
        AttributeType.TRIAL_NAME,
        AttributeType.CANCER_TYPE,
        AttributeType.NCT_NUMBER,
        AttributeType.LINE_OF_TREATMENT,
        AttributeType.ABSTRACT_NUMBER,
    ),
    AttributeFamily.RESPONSE_RATES: (
        AttributeType.OBJECTIVE_RESPONSE_RATE,
        AttributeType.COMPLETE_RESPONSE,
        AttributeType.PATHOLOGICAL_COMPLETE_RESPONSE,
        AttributeType.COMPLETE_METABOLIC_RESPONSE,
        AttributeType.DISEASE_CONTROL_RATE,
        AttributeType.CLINICAL_BENEFIT_RATE,
        AttributeType.MEDIAN_DOR,
        AttributeType.DOR_RATE,
    ),
    AttributeFamily.PFS_FAMILY: (
        # Efficacy - Survival Metrics (PFS Family)
        AttributeType.MEDIAN_PFS,
        AttributeType.MEDIAN_FOLLOWUP_PFS,
        AttributeType.P_VALUE_PFS,
        AttributeType.HR_PFS,
        AttributeType.CI_HR_PFS,
        # Efficacy - PFS Rate Timepoints
        AttributeType.PFS_RATE_6M,
        AttributeType.PFS_RATE_9M,
        AttributeType.PFS_RATE_12M,
        AttributeType.PFS_RATE_18M,
        AttributeType.PFS_RATE_24M,
        AttributeType.PFS_RATE_36M,
        AttributeType.PFS_RATE_48M,
    ),
    AttributeFamily.OS_FAMILY: (
        # Efficacy - OS Family
        AttributeType.MEDIAN_OS,
        AttributeType.MEDIAN_FOLLOWUP_OS,
        AttributeType.P_VALUE_OS,
        AttributeType.HR_OS,
        AttributeType.CI_HR_OS,
        # Efficacy - OS Rate Timepoints
        AttributeType.OS_RATE_6M,
        AttributeType.OS_RATE_9M,
        AttributeType.OS_RATE_12M,
        AttributeType.OS_RATE_18M,
        AttributeType.OS_RATE_24M,
        AttributeType.OS_RATE_36M,
        AttributeType.OS_RATE_48M,
    ),
    AttributeFamily.EFS_RFS_MFS: (
        # Efficacy - EFS Family (Event-Free Survival)
        AttributeType.EFS,
        AttributeType.P_VALUE_EFS,
        AttributeType.HR_EFS,
        AttributeType.CI_HR_EFS,
        # Efficacy - RFS Family (Recurrence-Free Survival / Relapse-Free Survival)
        AttributeType.RFS,
        AttributeType.P_VALUE_RFS,
        AttributeType.LENGTH_RFS,
        AttributeType.HR_RFS,
        AttributeType.CI_HR_RFS,
        # Efficacy - MFS Family (Metastasis-Free Survival)
        AttributeType.MFS,
        AttributeType.LENGTH_MFS,
        AttributeType.HR_MFS,
        AttributeType.CI_HR_MFS,
    ),
    AttributeFamily.TIME_TO_METRICS: (
        AttributeType.TTR,
        AttributeType.TTP,
        AttributeType.HR_TTP,
        AttributeType.CI_HR_TTP,
        AttributeType.TTNT,
        AttributeType.TTF,
    ),
    AttributeFamily.AE_GENERAL: (
        # Safety — AE
        AttributeType.AE,
        AttributeType.GRADE_3_PLUS_AE,
        AttributeType.AE_LEADING_TO_DISCONTINUATION,
        AttributeType.SERIOUS_AE,
        AttributeType.IMMUNE_RELATED_AE,
        AttributeType.SERIOUS_IMMUNE_RELATED_AE,
        AttributeType.AE_LEADING_TO_DEATH,
        AttributeType.AE_LEADING_TO_DOSE_REDUCTION,
        AttributeType.AE_LEADING_TO_DOSE_INTERRUPTION,
        AttributeType.AE_REQUIRING_HOSPITALIZATION,
        # Safety — Specific AEs
        AttributeType.CRS,
        AttributeType.IRR,
    ),
    AttributeFamily.AE_GRADE3_SPECIFIC: (
        AttributeType.GRADE_3_PLUS_AE_IMMUNE_RELATED,
        AttributeType.GRADE_3_PLUS_AE_IRR,
        AttributeType.GRADE_3_PLUS_AE_CRS,
        AttributeType.GRADE_3_PLUS_AE_COLITIS,
        AttributeType.GRADE_3_PLUS_AE_THROMBOCYTOPENIA,
        AttributeType.GRADE_3_PLUS_AE_NEUTROPENIA,
        AttributeType.GRADE_3_PLUS_AE_LEUKOPENIA,
        AttributeType.GRADE_3_PLUS_AE_FATIGUE,
        AttributeType.GRADE_3_PLUS_AE_NAUSEA,
        AttributeType.GRADE_3_PLUS_AE_ANEMIA,
        AttributeType.GRADE_3_PLUS_AE_DIARRHEA,
        AttributeType.GRADE_3_PLUS_AE_HYPERGLYCEMIA,
        AttributeType.GRADE_3_PLUS_AE_DYSPNEA,
        AttributeType.GRADE_3_PLUS_AE_PYREXIA,
        AttributeType.GRADE_3_PLUS_AE_BLEEDING,
        AttributeType.GRADE_3_PLUS_AE_PRURITUS,
        AttributeType.GRADE_3_PLUS_AE_RASH,
        AttributeType.GRADE_3_PLUS_AE_PNEUMONIA,
        AttributeType.GRADE_3_PLUS_AE_THYROIDITIS,
        AttributeType.GRADE_3_PLUS_AE_HYPOPHYSITIS,
        AttributeType.GRADE_3_PLUS_AE_HEPATITIS,
        AttributeType.GRADE_3_PLUS_AE_PNEUMONITIS,
        AttributeType.GRADE_3_PLUS_AE_ALANINE_AMINOTRANSFERASE,
        AttributeType.GRADE_3_PLUS_AE_HYPOTHYROIDISM,
        AttributeType.GRADE_3_PLUS_AE_HYPERTHYROIDISM,
        AttributeType.GRADE_3_PLUS_AE_AST_INCREASED,
        AttributeType.GRADE_3_PLUS_AE_VOMITING,
    ),
    AttributeFamily.TEAE_GENERAL: (
        AttributeType.TEAE,
        AttributeType.GRADE_3_PLUS_TEAE,
        AttributeType.GRADE_3_TEAE,
        AttributeType.GRADE_4_TEAE,
        AttributeType.GRADE_5_TEAE,
        AttributeType.TEAE_LEADING_TO_DISCONTINUATION,
        AttributeType.TEAE_LEADING_TO_DEATH,
        AttributeType.SERIOUS_TEAE,
        AttributeType.TEAE_IMMUNE_RELATED,
        AttributeType.TEAE_LEADING_TO_DOSE_REDUCTION,
        AttributeType.TEAE_LEADING_TO_DOSE_INTERRUPTION,
        AttributeType.TEAE_REQUIRING_HOSPITALIZATION,
    ),
    AttributeFamily.TEAE_GRADE3_SPECIFIC: (
        AttributeType.GRADE_3_PLUS_TEAE_IMMUNE_RELATED,
        AttributeType.GRADE_3_PLUS_TEAE_IRR,
        AttributeType.GRADE_3_PLUS_TEAE_CRS,
        AttributeType.GRADE_3_PLUS_TEAE_COLITIS,
        AttributeType.GRADE_3_PLUS_TEAE_THROMBOCYTOPENIA,
        AttributeType.GRADE_3_PLUS_TEAE_NEUTROPENIA,
        AttributeType.GRADE_3_PLUS_TEAE_LEUKOPENIA,
        AttributeType.GRADE_3_PLUS_TEAE_FATIGUE,
        AttributeType.GRADE_3_PLUS_TEAE_NAUSEA,
        AttributeType.GRADE_3_PLUS_TEAE_ANEMIA,
        AttributeType.GRADE_3_PLUS_TEAE_DIARRHEA,
        AttributeType.GRADE_3_PLUS_TEAE_HYPERGLYCEMIA,
        AttributeType.GRADE_3_PLUS_TEAE_DYSPNEA,
        AttributeType.GRADE_3_PLUS_TEAE_PYREXIA,
        AttributeType.GRADE_3_PLUS_TEAE_BLEEDING,
        AttributeType.GRADE_3_PLUS_TEAE_PRURITUS,
        AttributeType.GRADE_3_PLUS_TEAE_RASH,
        AttributeType.GRADE_3_PLUS_TEAE_PNEUMONIA,
        AttributeType.GRADE_3_PLUS_TEAE_THYROIDITIS,
        AttributeType.GRADE_3_PLUS_TEAE_HYPOPHYSITIS,
        AttributeType.GRADE_3_PLUS_TEAE_HEPATITIS,
        AttributeType.GRADE_3_PLUS_TEAE_PNEUMONITIS,
        AttributeType.GRADE_3_PLUS_TEAE_ALANINE_AMINOTRANSFERASE,
        AttributeType.GRADE_3_PLUS_TEAE_HYPOTHYROIDISM,
        AttributeType.GRADE_3_PLUS_TEAE_HYPERTHYROIDISM,
        AttributeType.GRADE_3_PLUS_TEAE_AST_INCREASED,
        AttributeType.GRADE_3_PLUS_TEAE_VOMITING,
    ),
    AttributeFamily.TRAE_GENERAL: (
        AttributeType.TRAE,
        AttributeType.GRADE_3_PLUS_TRAE,
        AttributeType.GRADE_3_TRAE,
        AttributeType.GRADE_4_TRAE,
        AttributeType.GRADE_5_TRAE,
        AttributeType.TRAE_LEADING_TO_DISCONTINUATION,
        AttributeType.TRAE_LEADING_TO_DEATH,
        AttributeType.SERIOUS_TRAE,
        AttributeType.TRAE_IMMUNE_RELATED,
        AttributeType.TRAE_LEADING_TO_DOSE_REDUCTION,
        AttributeType.TRAE_LEADING_TO_DOSE_INTERRUPTION,
        AttributeType.TRAE_REQUIRING_HOSPITALIZATION,
    ),
    AttributeFamily.TRAE_GRADE3_SPECIFIC: (
        AttributeType.GRADE_3_PLUS_TRAE_IMMUNE_RELATED,
        AttributeType.GRADE_3_PLUS_TRAE_IRR,
        AttributeType.GRADE_3_PLUS_TRAE_CRS,
        AttributeType.GRADE_3_PLUS_TRAE_COLITIS,
        AttributeType.GRADE_3_PLUS_TRAE_THROMBOCYTOPENIA,
        AttributeType.GRADE_3_PLUS_TRAE_NEUTROPENIA,
        AttributeType.GRADE_3_PLUS_TRAE_LEUKOPENIA,
        AttributeType.GRADE_3_PLUS_TRAE_FATIGUE,
        AttributeType.GRADE_3_PLUS_TRAE_NAUSEA,
        AttributeType.GRADE_3_PLUS_TRAE_ANEMIA,
        AttributeType.GRADE_3_PLUS_TRAE_DIARRHEA,
        AttributeType.GRADE_3_PLUS_TRAE_HYPERGLYCEMIA,
        AttributeType.GRADE_3_PLUS_TRAE_DYSPNEA,
        AttributeType.GRADE_3_PLUS_TRAE_PYREXIA,
        AttributeType.GRADE_3_PLUS_TRAE_BLEEDING,
        AttributeType.GRADE_3_PLUS_TRAE_PRURITUS,
        AttributeType.GRADE_3_PLUS_TRAE_RASH,
        AttributeType.GRADE_3_PLUS_TRAE_PNEUMONIA,
        AttributeType.GRADE_3_PLUS_TRAE_THYROIDITIS,
        AttributeType.GRADE_3_PLUS_TRAE_HYPOPHYSITIS,
        AttributeType.GRADE_3_PLUS_TRAE_HEPATITIS,
        AttributeType.GRADE_3_PLUS_TRAE_PNEUMONITIS,
        AttributeType.GRADE_3_PLUS_TRAE_ALANINE_AMINOTRANSFERASE,
        AttributeType.GRADE_3_PLUS_TRAE_HYPOTHYROIDISM,
        AttributeType.GRADE_3_PLUS_TRAE_HYPERTHYROIDISM,
        AttributeType.GRADE_3_PLUS_TRAE_AST_INCREASED,
        AttributeType.GRADE_3_PLUS_TRAE_VOMITING,
    ),
}


class ValidationStatus(str, Enum):
    """Validation status for extracted attributes."""

    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"
    WARNING = "warning"
    VERIFIED = "verified"
    EMPTY = "empty"
    FAILED = "failed"


class ExtractionConfidence(str, Enum):
    """Confidence levels for extraction results."""

    HIGH = "high"  # > 0.8
    MEDIUM = "medium"  # 0.5 - 0.8
    LOW = "low"  # < 0.5


class PValueSignificance(str, Enum):
    """P-value significance levels."""

    NON_SIGNIFICANT = "Non-Significant"  # p > 0.05
    SIGNIFICANT = "Significant"  # p ≤ 0.05
    HIGHLY_SIGNIFICANT = "Highly Significant"  # p ≤ 0.001


class ValueKind(str, Enum):
    """Value kinds for different attribute types."""

    # Basic types
    STRING = "string"
    TEXT = "text"
    INTEGER = "integer"
    DECIMAL = "decimal"
    PERCENTAGE = "percentage"
    MONTHS = "months"
    HAZARD_RATIO = "hazard_ratio"
    BINARY = "binary"
    DATE = "date"
    CATEGORICAL = "categorical"

    # Special types
    NCT_NUMBER = "nct_number"
    TRIAL_NAME = "trial_name"
    DRUG_NAME = "drug_name"
    THERAPY_TYPE = "therapy_type"
    CANCER_TYPE = "cancer_type"
    CONFERENCE = "conference"
    LINE_OF_TREATMENT = "line_of_treatment"
    P_VALUE = "p_value"
    SURVIVAL_METRIC = "survival_metric"
    RESPONSE_RATE = "response_rate"
    ADVERSE_EVENT = "adverse_event"


class AttributeConfiguration(BaseModel):
    """Configuration for attribute extraction and validation."""

    attribute_type: AttributeType
    value_kind: ValueKind
    required: bool = False
    critical: bool = False
    validation_pattern: Optional[str] = None
    validation_range: Optional[tuple[float, float]] = None
    controlled_vocabulary: Optional[list[str]] = None
    special_values: Optional[list[str]] = None
    calculation_formula: Optional[str] = None
    extraction_priority: int = 1
    api_source: bool = False

    class Config:
        use_enum_values = True


class AttributeConfigurationFactory:
    """Factory for creating attribute configurations based on legacy system patterns."""

    @staticmethod
    def get_all_configurations() -> dict[AttributeType, AttributeConfiguration]:
        """Get all attribute configurations based on legacy system analysis."""
        return {
            # Current 5 attributes
            AttributeType.NCT_NUMBER: AttributeConfiguration(
                attribute_type=AttributeType.NCT_NUMBER,
                value_kind=ValueKind.NCT_NUMBER,
                required=True,
                critical=True,
                validation_pattern=r"NCT\d{8}",
                extraction_priority=1,
                api_source=False,
            ),
            AttributeType.GENERIC_NAME: AttributeConfiguration(
                attribute_type=AttributeType.GENERIC_NAME,
                value_kind=ValueKind.DRUG_NAME,
                required=True,
                critical=True,
                extraction_priority=1,
                api_source=False,
            ),
            AttributeType.P_VALUE_OS: AttributeConfiguration(
                attribute_type=AttributeType.P_VALUE_OS,
                value_kind=ValueKind.P_VALUE,
                required=False,
                controlled_vocabulary=[
                    "Non-Significant",
                    "Significant",
                    "Highly Significant",
                ],
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.OBJECTIVE_RESPONSE_RATE: AttributeConfiguration(
                attribute_type=AttributeType.OBJECTIVE_RESPONSE_RATE,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                calculation_formula="(CR + PR) / Total_Patients * 100",
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_AE: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_AE,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                calculation_formula="Grade3 + Grade4 + Grade5",
                extraction_priority=2,
                api_source=False,
            ),
            # Safety - Adverse Events (AE)
            AttributeType.AE: AttributeConfiguration(
                attribute_type=AttributeType.AE,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.AE_LEADING_TO_DISCONTINUATION: AttributeConfiguration(
                attribute_type=AttributeType.AE_LEADING_TO_DISCONTINUATION,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.AE_LEADING_TO_DEATH: AttributeConfiguration(
                attribute_type=AttributeType.AE_LEADING_TO_DEATH,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.SERIOUS_AE: AttributeConfiguration(
                attribute_type=AttributeType.SERIOUS_AE,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.IMMUNE_RELATED_AE: AttributeConfiguration(
                attribute_type=AttributeType.IMMUNE_RELATED_AE,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.SERIOUS_IMMUNE_RELATED_AE: AttributeConfiguration(
                attribute_type=AttributeType.SERIOUS_IMMUNE_RELATED_AE,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            # General Parameters (Abstract-level)
            AttributeType.CONFERENCE: AttributeConfiguration(
                attribute_type=AttributeType.CONFERENCE,
                value_kind=ValueKind.CONFERENCE,
                required=True,
                controlled_vocabulary=["ASCO", "ESMO", "AACR", "SITC"],
                extraction_priority=1,
                api_source=False,
            ),
            AttributeType.PUBLISHED_YEAR: AttributeConfiguration(
                attribute_type=AttributeType.PUBLISHED_YEAR,
                value_kind=ValueKind.INTEGER,
                required=True,
                validation_range=(1990, 2030),
                extraction_priority=1,
                api_source=False,
            ),
            AttributeType.ABSTRACT_NUMBER: AttributeConfiguration(
                attribute_type=AttributeType.ABSTRACT_NUMBER,
                value_kind=ValueKind.STRING,
                required=False,
                extraction_priority=1,
                api_source=False,
            ),
            AttributeType.COMMENTS: AttributeConfiguration(
                attribute_type=AttributeType.COMMENTS,
                value_kind=ValueKind.STRING,
                required=False,
                extraction_priority=3,
                api_source=False,
            ),
            AttributeType.TRIAL_NAME: AttributeConfiguration(
                attribute_type=AttributeType.TRIAL_NAME,
                value_kind=ValueKind.TRIAL_NAME,
                required=True,
                controlled_vocabulary=[
                    "Keynote-\\d+",
                    "Checkmate-\\d+",
                    "Masterkey-\\d+",
                    "No Name",
                ],
                extraction_priority=1,
                api_source=False,  # Extract from abstract text
            ),
            AttributeType.CANCER_TYPE: AttributeConfiguration(
                attribute_type=AttributeType.CANCER_TYPE,
                value_kind=ValueKind.CANCER_TYPE,
                required=True,
                controlled_vocabulary=[
                    "Cutaneous Melanoma",
                    "Cutaneous Squamous Cell Carcinoma",
                    "Cutaneous Melanoma with Brain/CNS Metastasis",
                    "Uveal Melanoma",
                    "Acral Melanoma",
                    "Mucosal Melanoma",
                    "Basal Cell Carcinoma",
                    "Merkel Cell Carcinoma",
                ],
                extraction_priority=1,
                api_source=False,  # Extract from abstract
            ),
            AttributeType.CANCER_STAGE: AttributeConfiguration(
                attribute_type=AttributeType.CANCER_STAGE,
                value_kind=ValueKind.STRING,
                required=False,
                controlled_vocabulary=[
                    "Stage I",
                    "Stage I/II",
                    "Stage II",
                    "Stage II/III",
                    "Stage III",
                    "Stage III/Stage IV",
                    "Stage IV",
                ],
                extraction_priority=1,
                api_source=False,  # Extract from abstract
            ),
            AttributeType.MEDIAN_AGE: AttributeConfiguration(
                attribute_type=AttributeType.MEDIAN_AGE,
                value_kind=ValueKind.DECIMAL,
                required=False,
                validation_range=(0, 120),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.NUMBER_OF_PATIENTS: AttributeConfiguration(
                attribute_type=AttributeType.NUMBER_OF_PATIENTS,
                value_kind=ValueKind.INTEGER,
                required=True,
                critical=True,
                validation_range=(1, 10000),
                extraction_priority=1,
                api_source=False,  # Extract from abstract (Methods/Results sections)
            ),
            # Treatment Details (Arm-level)
            AttributeType.BRAND_NAME: AttributeConfiguration(
                attribute_type=AttributeType.BRAND_NAME,
                value_kind=ValueKind.STRING,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.SUB_THERAPY: AttributeConfiguration(
                attribute_type=AttributeType.SUB_THERAPY,
                value_kind=ValueKind.STRING,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.DOSAGE: AttributeConfiguration(
                attribute_type=AttributeType.DOSAGE,
                value_kind=ValueKind.STRING,
                required=False,
                extraction_priority=2,
                api_source=True,
            ),
            AttributeType.TYPE_OF_DOSING: AttributeConfiguration(
                attribute_type=AttributeType.TYPE_OF_DOSING,
                value_kind=ValueKind.STRING,
                required=False,
                extraction_priority=2,
                api_source=True,
            ),
            AttributeType.MECHANISM_OF_ACTION: AttributeConfiguration(
                attribute_type=AttributeType.MECHANISM_OF_ACTION,
                value_kind=ValueKind.STRING,
                required=False,
                extraction_priority=2,
                api_source=False,  # Extract from abstract instead of API
            ),
            AttributeType.TARGET_PROTEIN: AttributeConfiguration(
                attribute_type=AttributeType.TARGET_PROTEIN,
                value_kind=ValueKind.STRING,
                required=False,
                extraction_priority=2,
                api_source=False,  # Extract from abstract instead of API
            ),
            AttributeType.TYPE_OF_THERAPY: AttributeConfiguration(
                attribute_type=AttributeType.TYPE_OF_THERAPY,
                value_kind=ValueKind.THERAPY_TYPE,
                required=False,
                controlled_vocabulary=[
                    "Immunotherapy",
                    "Cellular therapy",
                    "Targeted Therapy",
                    "Oncolytic Virus",
                    "Chemotherapy",
                ],
                extraction_priority=2,
                api_source=False,  # Extract from abstract instead of API
            ),
            # Efficacy - Response Rates
            AttributeType.COMPLETE_RESPONSE: AttributeConfiguration(
                attribute_type=AttributeType.COMPLETE_RESPONSE,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.PATHOLOGICAL_COMPLETE_RESPONSE: AttributeConfiguration(
                attribute_type=AttributeType.PATHOLOGICAL_COMPLETE_RESPONSE,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.COMPLETE_METABOLIC_RESPONSE: AttributeConfiguration(
                attribute_type=AttributeType.COMPLETE_METABOLIC_RESPONSE,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.DISEASE_CONTROL_RATE: AttributeConfiguration(
                attribute_type=AttributeType.DISEASE_CONTROL_RATE,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                calculation_formula="(CR + PR + SD) / Total_Patients * 100",
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.CLINICAL_BENEFIT_RATE: AttributeConfiguration(
                attribute_type=AttributeType.CLINICAL_BENEFIT_RATE,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.MEDIAN_DOR: AttributeConfiguration(
                attribute_type=AttributeType.MEDIAN_DOR,
                value_kind=ValueKind.MONTHS,
                required=False,
                special_values=["NR"],
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.DOR_RATE: AttributeConfiguration(
                attribute_type=AttributeType.DOR_RATE,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            # Efficacy - Survival Metrics
            AttributeType.MEDIAN_PFS: AttributeConfiguration(
                attribute_type=AttributeType.MEDIAN_PFS,
                value_kind=ValueKind.MONTHS,
                required=False,
                special_values=["NR"],
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.MEDIAN_FOLLOWUP_PFS: AttributeConfiguration(
                attribute_type=AttributeType.MEDIAN_FOLLOWUP_PFS,
                value_kind=ValueKind.MONTHS,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.P_VALUE_PFS: AttributeConfiguration(
                attribute_type=AttributeType.P_VALUE_PFS,
                value_kind=ValueKind.P_VALUE,
                required=False,
                controlled_vocabulary=[
                    "Non-Significant",
                    "Significant",
                    "Highly Significant",
                ],
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.HR_PFS: AttributeConfiguration(
                attribute_type=AttributeType.HR_PFS,
                value_kind=ValueKind.HAZARD_RATIO,
                required=False,
                validation_range=(0, 10),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.CI_HR_PFS: AttributeConfiguration(
                attribute_type=AttributeType.CI_HR_PFS,
                value_kind=ValueKind.STRING,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.MEDIAN_OS: AttributeConfiguration(
                attribute_type=AttributeType.MEDIAN_OS,
                value_kind=ValueKind.MONTHS,
                required=False,
                special_values=["NR"],
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.MEDIAN_FOLLOWUP_OS: AttributeConfiguration(
                attribute_type=AttributeType.MEDIAN_FOLLOWUP_OS,
                value_kind=ValueKind.MONTHS,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.HR_OS: AttributeConfiguration(
                attribute_type=AttributeType.HR_OS,
                value_kind=ValueKind.HAZARD_RATIO,
                required=False,
                validation_range=(0, 10),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.CI_HR_OS: AttributeConfiguration(
                attribute_type=AttributeType.CI_HR_OS,
                value_kind=ValueKind.STRING,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            # Safety - Treatment-Emergent Adverse Events (TEAE)
            AttributeType.TEAE: AttributeConfiguration(
                attribute_type=AttributeType.TEAE,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TEAE: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TEAE,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                calculation_formula="Grade3_TEAE + Grade4_TEAE + Grade5_TEAE",
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_TEAE: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_TEAE,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_4_TEAE: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_4_TEAE,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_5_TEAE: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_5_TEAE,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.TEAE_LEADING_TO_DISCONTINUATION: AttributeConfiguration(
                attribute_type=AttributeType.TEAE_LEADING_TO_DISCONTINUATION,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.TEAE_LEADING_TO_DEATH: AttributeConfiguration(
                attribute_type=AttributeType.TEAE_LEADING_TO_DEATH,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.SERIOUS_TEAE: AttributeConfiguration(
                attribute_type=AttributeType.SERIOUS_TEAE,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.TEAE_IMMUNE_RELATED: AttributeConfiguration(
                attribute_type=AttributeType.TEAE_IMMUNE_RELATED,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            # Safety - Treatment-Related Adverse Events (TRAE)
            AttributeType.TRAE: AttributeConfiguration(
                attribute_type=AttributeType.TRAE,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TRAE: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TRAE,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                calculation_formula="Grade3_TRAE + Grade4_TRAE + Grade5_TRAE",
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_TRAE: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_TRAE,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_4_TRAE: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_4_TRAE,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_5_TRAE: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_5_TRAE,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.TRAE_LEADING_TO_DISCONTINUATION: AttributeConfiguration(
                attribute_type=AttributeType.TRAE_LEADING_TO_DISCONTINUATION,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.TRAE_LEADING_TO_DEATH: AttributeConfiguration(
                attribute_type=AttributeType.TRAE_LEADING_TO_DEATH,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.SERIOUS_TRAE: AttributeConfiguration(
                attribute_type=AttributeType.SERIOUS_TRAE,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.TRAE_IMMUNE_RELATED: AttributeConfiguration(
                attribute_type=AttributeType.TRAE_IMMUNE_RELATED,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            # Safety - Specific Adverse Events
            AttributeType.CRS: AttributeConfiguration(
                attribute_type=AttributeType.CRS,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.WBC_DECREASED: AttributeConfiguration(
                attribute_type=AttributeType.WBC_DECREASED,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            # Grade 3+ AE Specific Adverse Events
            AttributeType.GRADE_3_PLUS_AE_CRS: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_AE_CRS,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_AE_THROMBOCYTOPENIA: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_AE_THROMBOCYTOPENIA,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_AE_NEUTROPENIA: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_AE_NEUTROPENIA,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_AE_LEUKOPENIA: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_AE_LEUKOPENIA,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_AE_NAUSEA: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_AE_NAUSEA,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_AE_ANEMIA: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_AE_ANEMIA,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_AE_DIARRHEA: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_AE_DIARRHEA,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_AE_COLITIS: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_AE_COLITIS,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_AE_HYPERGLYCEMIA: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_AE_HYPERGLYCEMIA,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_AE_NEUTROPHIL_COUNT_DECREASED: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_AE_NEUTROPHIL_COUNT_DECREASED,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_AE_DYSPNEA: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_AE_DYSPNEA,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_AE_PYREXIA: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_AE_PYREXIA,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_AE_BLEEDING: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_AE_BLEEDING,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_AE_PRURITUS: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_AE_PRURITUS,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_AE_RASH: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_AE_RASH,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_AE_PNEUMONIA: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_AE_PNEUMONIA,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_AE_THYROIDITIS: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_AE_THYROIDITIS,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_AE_HYPOPHYSITIS: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_AE_HYPOPHYSITIS,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_AE_HEPATITIS: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_AE_HEPATITIS,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_AE_PNEUMONITIS: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_AE_PNEUMONITIS,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_AE_ALANINE_AMINOTRANSFERASE: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_AE_ALANINE_AMINOTRANSFERASE,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_AE_WBC_DECREASED: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_AE_WBC_DECREASED,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_AE_IMMUNE_RELATED: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_AE_IMMUNE_RELATED,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            # Grade 3+ TRAE Specific Adverse Events
            AttributeType.GRADE_3_PLUS_TRAE_IMMUNE_RELATED: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TRAE_IMMUNE_RELATED,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TRAE_CRS: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TRAE_CRS,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TRAE_THROMBOCYTOPENIA: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TRAE_THROMBOCYTOPENIA,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TRAE_NEUTROPENIA: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TRAE_NEUTROPENIA,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TRAE_LEUKOPENIA: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TRAE_LEUKOPENIA,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TRAE_NAUSEA: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TRAE_NAUSEA,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TRAE_ANEMIA: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TRAE_ANEMIA,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TRAE_DIARRHEA: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TRAE_DIARRHEA,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TRAE_COLITIS: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TRAE_COLITIS,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TRAE_HYPERGLYCEMIA: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TRAE_HYPERGLYCEMIA,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TRAE_NEUTROPHIL_COUNT_DECREASED: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TRAE_NEUTROPHIL_COUNT_DECREASED,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TRAE_DYSPNEA: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TRAE_DYSPNEA,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TRAE_PYREXIA: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TRAE_PYREXIA,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TRAE_BLEEDING: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TRAE_BLEEDING,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TRAE_PRURITUS: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TRAE_PRURITUS,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TRAE_RASH: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TRAE_RASH,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TRAE_PNEUMONIA: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TRAE_PNEUMONIA,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TRAE_THYROIDITIS: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TRAE_THYROIDITIS,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TRAE_HYPOPHYSITIS: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TRAE_HYPOPHYSITIS,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TRAE_HEPATITIS: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TRAE_HEPATITIS,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TRAE_PNEUMONITIS: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TRAE_PNEUMONITIS,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TRAE_ALANINE_AMINOTRANSFERASE: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TRAE_ALANINE_AMINOTRANSFERASE,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TRAE_WBC_DECREASED: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TRAE_WBC_DECREASED,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            # Grade 3+ TEAE Specific Adverse Events
            AttributeType.GRADE_3_PLUS_TEAE_IMMUNE_RELATED: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TEAE_IMMUNE_RELATED,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TEAE_CRS: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TEAE_CRS,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TEAE_THROMBOCYTOPENIA: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TEAE_THROMBOCYTOPENIA,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TEAE_NEUTROPENIA: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TEAE_NEUTROPENIA,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TEAE_LEUKOPENIA: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TEAE_LEUKOPENIA,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TEAE_NAUSEA: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TEAE_NAUSEA,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TEAE_ANEMIA: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TEAE_ANEMIA,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TEAE_DIARRHEA: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TEAE_DIARRHEA,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TEAE_COLITIS: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TEAE_COLITIS,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TEAE_HYPERGLYCEMIA: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TEAE_HYPERGLYCEMIA,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TEAE_NEUTROPHIL_COUNT_DECREASED: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TEAE_NEUTROPHIL_COUNT_DECREASED,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TEAE_DYSPNEA: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TEAE_DYSPNEA,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TEAE_PYREXIA: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TEAE_PYREXIA,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TEAE_BLEEDING: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TEAE_BLEEDING,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TEAE_PRURITUS: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TEAE_PRURITUS,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TEAE_RASH: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TEAE_RASH,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TEAE_PNEUMONIA: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TEAE_PNEUMONIA,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TEAE_THYROIDITIS: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TEAE_THYROIDITIS,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TEAE_HYPOPHYSITIS: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TEAE_HYPOPHYSITIS,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TEAE_HEPATITIS: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TEAE_HEPATITIS,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TEAE_PNEUMONITIS: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TEAE_PNEUMONITIS,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TEAE_ALANINE_AMINOTRANSFERASE: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TEAE_ALANINE_AMINOTRANSFERASE,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TEAE_WBC_DECREASED: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TEAE_WBC_DECREASED,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            # Efficacy - CI and additional HR configs for new attributes
            AttributeType.CI_HR_EFS: AttributeConfiguration(
                attribute_type=AttributeType.CI_HR_EFS,
                value_kind=ValueKind.STRING,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.CI_HR_RFS: AttributeConfiguration(
                attribute_type=AttributeType.CI_HR_RFS,
                value_kind=ValueKind.STRING,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.CI_HR_MFS: AttributeConfiguration(
                attribute_type=AttributeType.CI_HR_MFS,
                value_kind=ValueKind.STRING,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.HR_TTP: AttributeConfiguration(
                attribute_type=AttributeType.HR_TTP,
                value_kind=ValueKind.HAZARD_RATIO,
                required=False,
                validation_range=(0, 10),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.CI_HR_TTP: AttributeConfiguration(
                attribute_type=AttributeType.CI_HR_TTP,
                value_kind=ValueKind.STRING,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            # Safety - New AE dose/hospitalization attributes
            AttributeType.AE_LEADING_TO_DOSE_REDUCTION: AttributeConfiguration(
                attribute_type=AttributeType.AE_LEADING_TO_DOSE_REDUCTION,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.AE_LEADING_TO_DOSE_INTERRUPTION: AttributeConfiguration(
                attribute_type=AttributeType.AE_LEADING_TO_DOSE_INTERRUPTION,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.AE_REQUIRING_HOSPITALIZATION: AttributeConfiguration(
                attribute_type=AttributeType.AE_REQUIRING_HOSPITALIZATION,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.IRR: AttributeConfiguration(
                attribute_type=AttributeType.IRR,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            # Safety - New TEAE dose/hospitalization attributes
            AttributeType.TEAE_LEADING_TO_DOSE_REDUCTION: AttributeConfiguration(
                attribute_type=AttributeType.TEAE_LEADING_TO_DOSE_REDUCTION,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.TEAE_LEADING_TO_DOSE_INTERRUPTION: AttributeConfiguration(
                attribute_type=AttributeType.TEAE_LEADING_TO_DOSE_INTERRUPTION,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.TEAE_REQUIRING_HOSPITALIZATION: AttributeConfiguration(
                attribute_type=AttributeType.TEAE_REQUIRING_HOSPITALIZATION,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            # Safety - New TRAE dose/hospitalization attributes
            AttributeType.TRAE_LEADING_TO_DOSE_REDUCTION: AttributeConfiguration(
                attribute_type=AttributeType.TRAE_LEADING_TO_DOSE_REDUCTION,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.TRAE_LEADING_TO_DOSE_INTERRUPTION: AttributeConfiguration(
                attribute_type=AttributeType.TRAE_LEADING_TO_DOSE_INTERRUPTION,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.TRAE_REQUIRING_HOSPITALIZATION: AttributeConfiguration(
                attribute_type=AttributeType.TRAE_REQUIRING_HOSPITALIZATION,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            # Safety - Grade 3+ IRR and Fatigue for AE/TRAE/TEAE
            AttributeType.GRADE_3_PLUS_AE_IRR: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_AE_IRR,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_AE_FATIGUE: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_AE_FATIGUE,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TRAE_IRR: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TRAE_IRR,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TRAE_FATIGUE: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TRAE_FATIGUE,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TEAE_IRR: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TEAE_IRR,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.GRADE_3_PLUS_TEAE_FATIGUE: AttributeConfiguration(
                attribute_type=AttributeType.GRADE_3_PLUS_TEAE_FATIGUE,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                validation_range=(0, 100),
                extraction_priority=2,
                api_source=False,
            ),
            # Publication-level metadata
            AttributeType.PUBLICATION_NAME: AttributeConfiguration(
                attribute_type=AttributeType.PUBLICATION_NAME,
                value_kind=ValueKind.STRING,
                required=False,
                extraction_priority=1,
                api_source=False,
            ),
            AttributeType.PUBLICATION_YEAR: AttributeConfiguration(
                attribute_type=AttributeType.PUBLICATION_YEAR,
                value_kind=ValueKind.INTEGER,
                required=False,
                validation_range=(1990, 2030),
                extraction_priority=1,
                api_source=False,
            ),
            AttributeType.PDF_NUMBER: AttributeConfiguration(
                attribute_type=AttributeType.PDF_NUMBER,
                value_kind=ValueKind.STRING,
                required=False,
                extraction_priority=1,
                api_source=False,
            ),
            # API-sourced attributes (Phase 1)
            AttributeType.STUDY_START_DATE: AttributeConfiguration(
                attribute_type=AttributeType.STUDY_START_DATE,
                value_kind=ValueKind.DATE,
                required=False,
                extraction_priority=1,
                api_source=True,
            ),
            AttributeType.STUDY_COMPLETION_DATE: AttributeConfiguration(
                attribute_type=AttributeType.STUDY_COMPLETION_DATE,
                value_kind=ValueKind.DATE,
                required=False,
                extraction_priority=1,
                api_source=True,
            ),
            AttributeType.FIRST_RESULTS: AttributeConfiguration(
                attribute_type=AttributeType.FIRST_RESULTS,
                value_kind=ValueKind.DATE,
                required=False,
                extraction_priority=1,
                api_source=True,
            ),
            AttributeType.SPONSORS: AttributeConfiguration(
                attribute_type=AttributeType.SPONSORS,
                value_kind=ValueKind.STRING,
                required=False,
                extraction_priority=1,
                api_source=True,  # Extract from Clinical Trials API
            ),
            AttributeType.CLINICAL_TRIAL_PHASE: AttributeConfiguration(
                attribute_type=AttributeType.CLINICAL_TRIAL_PHASE,
                value_kind=ValueKind.STRING,
                required=False,
                controlled_vocabulary=[
                    "PHASE1",
                    "PHASE2",
                    "PHASE3",
                    "PHASE4",
                    "PHASE1_2",
                    "PHASE2_3",
                ],
                extraction_priority=1,
                api_source=True,  # Source from Clinical Trials API
            ),
            AttributeType.STUDY_TYPE: AttributeConfiguration(
                attribute_type=AttributeType.STUDY_TYPE,
                value_kind=ValueKind.STRING,
                required=False,
                controlled_vocabulary=[
                    "Interventional",
                    "Observational",
                    "Expanded Access",
                ],
                extraction_priority=1,
                api_source=True,  # Source from Clinical Trials API
            ),
            AttributeType.PRIMARY_ENDPOINT: AttributeConfiguration(
                attribute_type=AttributeType.PRIMARY_ENDPOINT,
                value_kind=ValueKind.STRING,
                required=False,
                extraction_priority=1,
                api_source=True,  # Source from Clinical Trials API
            ),
            AttributeType.SECONDARY_ENDPOINT: AttributeConfiguration(
                attribute_type=AttributeType.SECONDARY_ENDPOINT,
                value_kind=ValueKind.STRING,
                required=False,
                extraction_priority=1,
                api_source=True,  # Source from Clinical Trials API
            ),
            AttributeType.PRIMARY_COMPLETION_DATE: AttributeConfiguration(
                attribute_type=AttributeType.PRIMARY_COMPLETION_DATE,
                value_kind=ValueKind.DATE,
                required=False,
                extraction_priority=1,
                api_source=True,  # Source from Clinical Trials API
            ),
            AttributeType.LINE_OF_TREATMENT: AttributeConfiguration(
                attribute_type=AttributeType.LINE_OF_TREATMENT,
                value_kind=ValueKind.STRING,
                required=False,
                controlled_vocabulary=[
                    "Neoadjuvant",
                    "First Line",
                    "2nd Line",
                    "3rd Line+",
                ],
                extraction_priority=2,
                api_source=True,  # Source from Clinical Trials API (arm-specific)
            ),
            AttributeType.MINIMUM_AGE: AttributeConfiguration(
                attribute_type=AttributeType.MINIMUM_AGE,
                value_kind=ValueKind.STRING,
                required=False,
                extraction_priority=1,
                api_source=True,
            ),
            AttributeType.MAXIMUM_AGE: AttributeConfiguration(
                attribute_type=AttributeType.MAXIMUM_AGE,
                value_kind=ValueKind.STRING,
                required=False,
                extraction_priority=1,
                api_source=True,
            ),
            AttributeType.SEX: AttributeConfiguration(
                attribute_type=AttributeType.SEX,
                value_kind=ValueKind.STRING,
                required=False,
                extraction_priority=1,
                api_source=True,
            ),
            AttributeType.TRIAL_RUN_IN_EUROPE: AttributeConfiguration(
                attribute_type=AttributeType.TRIAL_RUN_IN_EUROPE,
                value_kind=ValueKind.BINARY,
                required=False,
                extraction_priority=1,
                api_source=True,
            ),
            AttributeType.TRIAL_RUN_IN_US: AttributeConfiguration(
                attribute_type=AttributeType.TRIAL_RUN_IN_US,
                value_kind=ValueKind.BINARY,
                required=False,
                extraction_priority=1,
                api_source=True,
            ),
            AttributeType.TRIAL_RUN_IN_CHINA: AttributeConfiguration(
                attribute_type=AttributeType.TRIAL_RUN_IN_CHINA,
                value_kind=ValueKind.BINARY,
                required=False,
                extraction_priority=1,
                api_source=True,
            ),
            AttributeType.CHEMOTHERAPY_NAIVE: AttributeConfiguration(
                attribute_type=AttributeType.CHEMOTHERAPY_NAIVE,
                value_kind=ValueKind.BINARY,
                required=False,
                extraction_priority=2,
                api_source=True,
            ),
            AttributeType.ICI_NAIVE: AttributeConfiguration(
                attribute_type=AttributeType.ICI_NAIVE,
                value_kind=ValueKind.BINARY,
                required=False,
                extraction_priority=2,
                api_source=True,
            ),
            AttributeType.BRAF_MUTATION: AttributeConfiguration(
                attribute_type=AttributeType.BRAF_MUTATION,
                value_kind=ValueKind.BINARY,
                required=False,
                extraction_priority=2,
                api_source=True,
            ),
            AttributeType.BIOMARKER_INCLUSION: AttributeConfiguration(
                attribute_type=AttributeType.BIOMARKER_INCLUSION,
                value_kind=ValueKind.BINARY,
                required=False,
                extraction_priority=2,
                api_source=True,
            ),
            # Additional API-sourced attributes
            AttributeType.CHEMOTHERAPY_FAILED: AttributeConfiguration(
                attribute_type=AttributeType.CHEMOTHERAPY_FAILED,
                value_kind=ValueKind.BINARY,
                required=False,
                extraction_priority=2,
                api_source=True,
            ),
            AttributeType.ICI_FAILED: AttributeConfiguration(
                attribute_type=AttributeType.ICI_FAILED,
                value_kind=ValueKind.BINARY,
                required=False,
                extraction_priority=2,
                api_source=True,
            ),
            AttributeType.IPILIMUMAB_FAILURE: AttributeConfiguration(
                attribute_type=AttributeType.IPILIMUMAB_FAILURE,
                value_kind=ValueKind.BINARY,
                required=False,
                extraction_priority=2,
                api_source=True,
            ),
            AttributeType.ANTI_PD1_FAILURE: AttributeConfiguration(
                attribute_type=AttributeType.ANTI_PD1_FAILURE,
                value_kind=ValueKind.BINARY,
                required=False,
                extraction_priority=2,
                api_source=True,
            ),
            AttributeType.MUTATION_STATUS: AttributeConfiguration(
                attribute_type=AttributeType.MUTATION_STATUS,
                value_kind=ValueKind.TEXT,
                required=False,
                extraction_priority=2,
                api_source=True,
            ),
            AttributeType.NRAS_MUTATION: AttributeConfiguration(
                attribute_type=AttributeType.NRAS_MUTATION,
                value_kind=ValueKind.BINARY,
                required=False,
                extraction_priority=2,
                api_source=True,
            ),
            AttributeType.BIOSIMILAR: AttributeConfiguration(
                attribute_type=AttributeType.BIOSIMILAR,
                value_kind=ValueKind.BINARY,
                required=False,
                extraction_priority=2,
                api_source=False,  # Extract from abstract
            ),
            AttributeType.BIOMARKERS_INCLUSION_CRITERIA: AttributeConfiguration(
                attribute_type=AttributeType.BIOMARKERS_INCLUSION_CRITERIA,
                value_kind=ValueKind.TEXT,
                required=False,
                extraction_priority=2,
                api_source=True,
            ),
            AttributeType.BIOMARKERS_EXCLUSION_CRITERIA: AttributeConfiguration(
                attribute_type=AttributeType.BIOMARKERS_EXCLUSION_CRITERIA,
                value_kind=ValueKind.TEXT,
                required=False,
                extraction_priority=2,
                api_source=True,
            ),
            # PFS Rate Attributes
            AttributeType.PFS_RATE_6M: AttributeConfiguration(
                attribute_type=AttributeType.PFS_RATE_6M,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.PFS_RATE_9M: AttributeConfiguration(
                attribute_type=AttributeType.PFS_RATE_9M,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.PFS_RATE_12M: AttributeConfiguration(
                attribute_type=AttributeType.PFS_RATE_12M,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.PFS_RATE_18M: AttributeConfiguration(
                attribute_type=AttributeType.PFS_RATE_18M,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.PFS_RATE_24M: AttributeConfiguration(
                attribute_type=AttributeType.PFS_RATE_24M,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.PFS_RATE_36M: AttributeConfiguration(
                attribute_type=AttributeType.PFS_RATE_36M,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.PFS_RATE_48M: AttributeConfiguration(
                attribute_type=AttributeType.PFS_RATE_48M,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            # OS Rate Attributes
            AttributeType.OS_RATE_6M: AttributeConfiguration(
                attribute_type=AttributeType.OS_RATE_6M,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.OS_RATE_9M: AttributeConfiguration(
                attribute_type=AttributeType.OS_RATE_9M,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.OS_RATE_12M: AttributeConfiguration(
                attribute_type=AttributeType.OS_RATE_12M,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.OS_RATE_18M: AttributeConfiguration(
                attribute_type=AttributeType.OS_RATE_18M,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.OS_RATE_24M: AttributeConfiguration(
                attribute_type=AttributeType.OS_RATE_24M,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.OS_RATE_36M: AttributeConfiguration(
                attribute_type=AttributeType.OS_RATE_36M,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.OS_RATE_48M: AttributeConfiguration(
                attribute_type=AttributeType.OS_RATE_48M,
                value_kind=ValueKind.PERCENTAGE,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            # EFS Family
            AttributeType.EFS: AttributeConfiguration(
                attribute_type=AttributeType.EFS,
                value_kind=ValueKind.MONTHS,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.P_VALUE_EFS: AttributeConfiguration(
                attribute_type=AttributeType.P_VALUE_EFS,
                value_kind=ValueKind.DECIMAL,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.HR_EFS: AttributeConfiguration(
                attribute_type=AttributeType.HR_EFS,
                value_kind=ValueKind.HAZARD_RATIO,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            # RFS Family
            AttributeType.RFS: AttributeConfiguration(
                attribute_type=AttributeType.RFS,
                value_kind=ValueKind.MONTHS,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.P_VALUE_RFS: AttributeConfiguration(
                attribute_type=AttributeType.P_VALUE_RFS,
                value_kind=ValueKind.DECIMAL,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.LENGTH_RFS: AttributeConfiguration(
                attribute_type=AttributeType.LENGTH_RFS,
                value_kind=ValueKind.MONTHS,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.HR_RFS: AttributeConfiguration(
                attribute_type=AttributeType.HR_RFS,
                value_kind=ValueKind.HAZARD_RATIO,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            # MFS Family
            AttributeType.MFS: AttributeConfiguration(
                attribute_type=AttributeType.MFS,
                value_kind=ValueKind.MONTHS,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.LENGTH_MFS: AttributeConfiguration(
                attribute_type=AttributeType.LENGTH_MFS,
                value_kind=ValueKind.MONTHS,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.HR_MFS: AttributeConfiguration(
                attribute_type=AttributeType.HR_MFS,
                value_kind=ValueKind.HAZARD_RATIO,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            # Time-to Metrics
            AttributeType.TTR: AttributeConfiguration(
                attribute_type=AttributeType.TTR,
                value_kind=ValueKind.MONTHS,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.TTP: AttributeConfiguration(
                attribute_type=AttributeType.TTP,
                value_kind=ValueKind.MONTHS,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.TTNT: AttributeConfiguration(
                attribute_type=AttributeType.TTNT,
                value_kind=ValueKind.MONTHS,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
            AttributeType.TTF: AttributeConfiguration(
                attribute_type=AttributeType.TTF,
                value_kind=ValueKind.MONTHS,
                required=False,
                extraction_priority=2,
                api_source=False,
            ),
        }

    @staticmethod
    def get_configuration(attribute_type: AttributeType) -> AttributeConfiguration:
        """Get configuration for a specific attribute type."""
        return AttributeConfigurationFactory.get_all_configurations()[attribute_type]

    @staticmethod
    def get_abstract_level_attributes() -> list[AttributeType]:
        """Get attributes that are extracted at the abstract level."""
        return [
            AttributeType.CONFERENCE,
            AttributeType.PUBLISHED_YEAR,
            AttributeType.ABSTRACT_NUMBER,
            AttributeType.COMMENTS,
        ]

    @staticmethod
    def get_publication_level_attributes() -> list[AttributeType]:
        """Get attributes that are extracted at the publication level."""
        return [
            AttributeType.PUBLICATION_NAME,
            AttributeType.PUBLICATION_YEAR,
            AttributeType.PDF_NUMBER,
        ]

    @staticmethod
    def get_arm_level_attributes() -> list[AttributeType]:
        """Get attributes that are extracted at the treatment arm level."""
        abstract_level = AttributeConfigurationFactory.get_abstract_level_attributes()
        publication_level = (
            AttributeConfigurationFactory.get_publication_level_attributes()
        )
        return [
            attr
            for attr in AttributeType
            if attr not in abstract_level and attr not in publication_level
        ]

    @staticmethod
    def get_api_sourced_attributes() -> list[AttributeType]:
        """Get attributes that should be sourced from Clinical Trials API."""
        return [
            attr
            for attr, config in AttributeConfigurationFactory.get_all_configurations().items()
            if config.api_source
        ]


class ExtractedAttribute(BaseModel):
    """Core entity representing an extracted attribute."""

    attribute_type: AttributeType
    value: Union[str, float, int, None]
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence score between 0 and 1"
    )
    source_chunks: list[str] = Field(
        default_factory=list, description="Chunk IDs that contributed to extraction"
    )
    source_quote: str = Field(
        default="",
        description="Verbatim sentence(s) from the source doc supporting the extracted value.",
    )
    source: str = Field(
        default="abstract_llm_extraction", description="Source of the extracted data"
    )
    validation_status: ValidationStatus = ValidationStatus.PENDING
    validation_errors: list[str] = Field(default_factory=list)
    extracted_at: datetime = Field(default_factory=datetime.now)

    @validator("confidence")
    def validate_confidence(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        return v

    @property
    def confidence_level(self) -> ExtractionConfidence:
        """Get confidence level based on confidence score."""
        if self.confidence >= 0.8:
            return ExtractionConfidence.HIGH
        elif self.confidence >= 0.5:
            return ExtractionConfidence.MEDIUM
        else:
            return ExtractionConfidence.LOW


class NCTNumber(ExtractedAttribute):
    """Specialized model for NCT number extraction."""

    attribute_type: Literal[AttributeType.NCT_NUMBER] = AttributeType.NCT_NUMBER

    @validator("value")
    def validate_nct_format(cls, v):
        if v is None:
            return v
        if not isinstance(v, str):
            raise ValueError("NCT number must be a string")
        if not v.startswith("NCT") or len(v) != 11:
            raise ValueError("NCT number must be in format NCT########")
        return v


class GenericName(ExtractedAttribute):
    """Specialized model for generic drug name extraction."""

    attribute_type: Literal[AttributeType.GENERIC_NAME] = AttributeType.GENERIC_NAME

    @validator("value")
    def validate_generic_name(cls, v):
        if v is None:
            return v
        if not isinstance(v, str):
            raise ValueError("Generic name must be a string")
        if len(v.strip()) == 0:
            raise ValueError("Generic name cannot be empty")
        return v


class PValueOS(ExtractedAttribute):
    """Specialized model for OS p-value extraction."""

    attribute_type: Literal[AttributeType.P_VALUE_OS] = AttributeType.P_VALUE_OS

    @validator("value")
    def validate_p_value(cls, v):
        if v is None:
            return v
        if isinstance(v, str):
            if v in ["Non-Significant", "Significant", "Highly Significant"]:
                return v
            try:
                float_val = float(v)
                if not 0 <= float_val <= 1:
                    raise ValueError("P-value must be between 0 and 1")
                return float_val
            except ValueError as e:
                raise ValueError(
                    "P-value must be numeric or valid significance level"
                ) from e
        elif isinstance(v, (int, float)):
            if not 0 <= v <= 1:
                raise ValueError("P-value must be between 0 and 1")
            return v
        else:
            raise ValueError("P-value must be numeric or string")


class ObjectiveResponseRate(ExtractedAttribute):
    """Specialized model for ORR extraction."""

    attribute_type: Literal[
        AttributeType.OBJECTIVE_RESPONSE_RATE
    ] = AttributeType.OBJECTIVE_RESPONSE_RATE

    @validator("value")
    def validate_orr(cls, v):
        if v is None:
            return v
        if isinstance(v, str):
            try:
                float_val = float(v)
                if not 0 <= float_val <= 100:
                    raise ValueError("ORR must be between 0 and 100")
                return float_val
            except ValueError as e:
                raise ValueError("ORR must be numeric") from e
        elif isinstance(v, (int, float)):
            if not 0 <= v <= 100:
                raise ValueError("ORR must be between 0 and 100")
            return v
        else:
            raise ValueError("ORR must be numeric")


class Grade3PlusAE(ExtractedAttribute):
    """Specialized model for Grade 3+ AE extraction."""

    attribute_type: Literal[
        AttributeType.GRADE_3_PLUS_AE
    ] = AttributeType.GRADE_3_PLUS_AE

    @validator("value")
    def validate_grade_3_plus_ae(cls, v):
        if v is None:
            return v
        if isinstance(v, str):
            try:
                float_val = float(v)
                if not 0 <= float_val <= 100:
                    raise ValueError("Grade 3+ AE must be between 0 and 100")
                return float_val
            except ValueError as e:
                raise ValueError("Grade 3+ AE must be numeric") from e
        elif isinstance(v, (int, float)):
            if not 0 <= v <= 100:
                raise ValueError("Grade 3+ AE must be between 0 and 100")
            return v
        else:
            raise ValueError("Grade 3+ AE must be numeric")


class ExtractionRequest(BaseModel):
    """Request model for attribute extraction."""

    document_id: str = Field(..., description="Unique identifier for the document")
    attributes: list[AttributeType] = Field(
        ..., description="List of attributes to extract"
    )
    context_chunks: int = Field(
        default=5, ge=1, le=20, description="Number of context chunks to retrieve"
    )
    similarity_threshold: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Minimum similarity threshold for context",
    )
    metadata_filters: dict[str, Any] = Field(
        default_factory=dict, description="Metadata filters for context retrieval"
    )


class ExtractionResult(BaseModel):
    """Result model for attribute extraction."""

    document_id: str
    extracted_attributes: dict[AttributeType, ExtractedAttribute]
    processing_time_ms: int
    total_chunks_processed: int
    extraction_confidence: float = Field(ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=datetime.now)

    @property
    def success_rate(self) -> float:
        """Calculate success rate of extraction."""
        if not self.extracted_attributes:
            return 0.0
        valid_count = sum(
            1
            for attr in self.extracted_attributes.values()
            if attr.validation_status == ValidationStatus.VALID
        )
        return valid_count / len(self.extracted_attributes)

    @property
    def high_confidence_attributes(self) -> list[AttributeType]:
        """Get attributes with high confidence extraction."""
        return [
            attr_type
            for attr_type, attr in self.extracted_attributes.items()
            if attr.confidence_level == ExtractionConfidence.HIGH
        ]


class ValidationRule(BaseModel):
    """Validation rule for attribute extraction."""

    attribute_type: AttributeType
    required: bool = False
    pattern: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    allowed_values: Optional[list[str]] = None
    custom_validator: Optional[str] = None  # Function name for custom validation


# The set of attributes extracted from full journal publications.
# Abstracts extract a smaller subset; the pipeline script imports this
# constant rather than defining its own list.
PUBLICATION_ATTRIBUTES: list[AttributeType] = [
    # Publication identification
    AttributeType.PUBLICATION_NAME,
    AttributeType.PUBLICATION_YEAR,
    AttributeType.PDF_NUMBER,
    AttributeType.TRIAL_NAME,
    AttributeType.CANCER_TYPE,
    AttributeType.NCT_NUMBER,
    AttributeType.NUMBER_OF_PATIENTS,
    AttributeType.LINE_OF_TREATMENT,
    AttributeType.MODALITY,
    AttributeType.TARGET,
    # Efficacy - Response Rates
    AttributeType.OBJECTIVE_RESPONSE_RATE,
    AttributeType.COMPLETE_RESPONSE,
    AttributeType.PATHOLOGICAL_COMPLETE_RESPONSE,
    AttributeType.COMPLETE_METABOLIC_RESPONSE,
    AttributeType.DISEASE_CONTROL_RATE,
    AttributeType.CLINICAL_BENEFIT_RATE,
    AttributeType.MEDIAN_DOR,
    AttributeType.DOR_RATE,
    # Efficacy - Survival Metrics (PFS Family)
    AttributeType.MEDIAN_PFS,
    AttributeType.MEDIAN_FOLLOWUP_PFS,
    AttributeType.P_VALUE_PFS,
    AttributeType.HR_PFS,
    AttributeType.CI_HR_PFS,
    # Efficacy - OS Family
    AttributeType.MEDIAN_OS,
    AttributeType.MEDIAN_FOLLOWUP_OS,
    AttributeType.P_VALUE_OS,
    AttributeType.HR_OS,
    AttributeType.CI_HR_OS,
    # Efficacy - PFS Rate Timepoints
    AttributeType.PFS_RATE_6M,
    AttributeType.PFS_RATE_9M,
    AttributeType.PFS_RATE_12M,
    AttributeType.PFS_RATE_18M,
    AttributeType.PFS_RATE_24M,
    AttributeType.PFS_RATE_36M,
    AttributeType.PFS_RATE_48M,
    # Efficacy - OS Rate Timepoints
    AttributeType.OS_RATE_6M,
    AttributeType.OS_RATE_9M,
    AttributeType.OS_RATE_12M,
    AttributeType.OS_RATE_18M,
    AttributeType.OS_RATE_24M,
    AttributeType.OS_RATE_36M,
    AttributeType.OS_RATE_48M,
    # Efficacy - EFS Family (Event-Free Survival)
    AttributeType.EFS,
    AttributeType.P_VALUE_EFS,
    AttributeType.HR_EFS,
    AttributeType.CI_HR_EFS,
    # Efficacy - RFS Family (Recurrence-Free Survival / Relapse-Free Survival)
    AttributeType.RFS,
    AttributeType.P_VALUE_RFS,
    AttributeType.LENGTH_RFS,
    AttributeType.HR_RFS,
    AttributeType.CI_HR_RFS,
    # Efficacy - MFS Family (Metastasis-Free Survival)
    AttributeType.MFS,
    AttributeType.LENGTH_MFS,
    AttributeType.HR_MFS,
    AttributeType.CI_HR_MFS,
    # Efficacy - Time-to Metrics
    AttributeType.TTR,
    AttributeType.TTP,
    AttributeType.HR_TTP,
    AttributeType.CI_HR_TTP,
    AttributeType.TTNT,
    AttributeType.TTF,
    # Safety — AE
    AttributeType.AE,
    AttributeType.GRADE_3_PLUS_AE,
    AttributeType.AE_LEADING_TO_DISCONTINUATION,
    AttributeType.SERIOUS_AE,
    AttributeType.IMMUNE_RELATED_AE,
    AttributeType.SERIOUS_IMMUNE_RELATED_AE,
    AttributeType.AE_LEADING_TO_DEATH,
    AttributeType.AE_LEADING_TO_DOSE_REDUCTION,
    AttributeType.AE_LEADING_TO_DOSE_INTERRUPTION,
    AttributeType.AE_REQUIRING_HOSPITALIZATION,
    # Safety — Specific AEs
    AttributeType.CRS,
    AttributeType.IRR,
    # Safety — Grade 3+ AE specific
    AttributeType.GRADE_3_PLUS_AE_IMMUNE_RELATED,
    AttributeType.GRADE_3_PLUS_AE_IRR,
    AttributeType.GRADE_3_PLUS_AE_CRS,
    AttributeType.GRADE_3_PLUS_AE_COLITIS,
    AttributeType.GRADE_3_PLUS_AE_THROMBOCYTOPENIA,
    AttributeType.GRADE_3_PLUS_AE_NEUTROPENIA,
    AttributeType.GRADE_3_PLUS_AE_LEUKOPENIA,
    AttributeType.GRADE_3_PLUS_AE_FATIGUE,
    AttributeType.GRADE_3_PLUS_AE_NAUSEA,
    AttributeType.GRADE_3_PLUS_AE_ANEMIA,
    AttributeType.GRADE_3_PLUS_AE_DIARRHEA,
    AttributeType.GRADE_3_PLUS_AE_HYPERGLYCEMIA,
    AttributeType.GRADE_3_PLUS_AE_DYSPNEA,
    AttributeType.GRADE_3_PLUS_AE_PYREXIA,
    AttributeType.GRADE_3_PLUS_AE_BLEEDING,
    AttributeType.GRADE_3_PLUS_AE_PRURITUS,
    AttributeType.GRADE_3_PLUS_AE_RASH,
    AttributeType.GRADE_3_PLUS_AE_PNEUMONIA,
    AttributeType.GRADE_3_PLUS_AE_THYROIDITIS,
    AttributeType.GRADE_3_PLUS_AE_HYPOPHYSITIS,
    AttributeType.GRADE_3_PLUS_AE_HEPATITIS,
    AttributeType.GRADE_3_PLUS_AE_PNEUMONITIS,
    AttributeType.GRADE_3_PLUS_AE_ALANINE_AMINOTRANSFERASE,
    AttributeType.GRADE_3_PLUS_AE_HYPOTHYROIDISM,
    AttributeType.GRADE_3_PLUS_AE_HYPERTHYROIDISM,
    AttributeType.GRADE_3_PLUS_AE_AST_INCREASED,
    AttributeType.GRADE_3_PLUS_AE_VOMITING,
    # Safety — TEAE
    AttributeType.TEAE,
    AttributeType.GRADE_3_PLUS_TEAE,
    AttributeType.GRADE_3_TEAE,
    AttributeType.GRADE_4_TEAE,
    AttributeType.GRADE_5_TEAE,
    AttributeType.TEAE_LEADING_TO_DISCONTINUATION,
    AttributeType.TEAE_LEADING_TO_DEATH,
    AttributeType.SERIOUS_TEAE,
    AttributeType.TEAE_IMMUNE_RELATED,
    AttributeType.TEAE_LEADING_TO_DOSE_REDUCTION,
    AttributeType.TEAE_LEADING_TO_DOSE_INTERRUPTION,
    AttributeType.TEAE_REQUIRING_HOSPITALIZATION,
    # Safety — Grade 3+ TEAE specific
    AttributeType.GRADE_3_PLUS_TEAE_IMMUNE_RELATED,
    AttributeType.GRADE_3_PLUS_TEAE_IRR,
    AttributeType.GRADE_3_PLUS_TEAE_CRS,
    AttributeType.GRADE_3_PLUS_TEAE_COLITIS,
    AttributeType.GRADE_3_PLUS_TEAE_THROMBOCYTOPENIA,
    AttributeType.GRADE_3_PLUS_TEAE_NEUTROPENIA,
    AttributeType.GRADE_3_PLUS_TEAE_LEUKOPENIA,
    AttributeType.GRADE_3_PLUS_TEAE_FATIGUE,
    AttributeType.GRADE_3_PLUS_TEAE_NAUSEA,
    AttributeType.GRADE_3_PLUS_TEAE_ANEMIA,
    AttributeType.GRADE_3_PLUS_TEAE_DIARRHEA,
    AttributeType.GRADE_3_PLUS_TEAE_HYPERGLYCEMIA,
    AttributeType.GRADE_3_PLUS_TEAE_DYSPNEA,
    AttributeType.GRADE_3_PLUS_TEAE_PYREXIA,
    AttributeType.GRADE_3_PLUS_TEAE_BLEEDING,
    AttributeType.GRADE_3_PLUS_TEAE_PRURITUS,
    AttributeType.GRADE_3_PLUS_TEAE_RASH,
    AttributeType.GRADE_3_PLUS_TEAE_PNEUMONIA,
    AttributeType.GRADE_3_PLUS_TEAE_THYROIDITIS,
    AttributeType.GRADE_3_PLUS_TEAE_HYPOPHYSITIS,
    AttributeType.GRADE_3_PLUS_TEAE_HEPATITIS,
    AttributeType.GRADE_3_PLUS_TEAE_PNEUMONITIS,
    AttributeType.GRADE_3_PLUS_TEAE_ALANINE_AMINOTRANSFERASE,
    AttributeType.GRADE_3_PLUS_TEAE_HYPOTHYROIDISM,
    AttributeType.GRADE_3_PLUS_TEAE_HYPERTHYROIDISM,
    AttributeType.GRADE_3_PLUS_TEAE_AST_INCREASED,
    AttributeType.GRADE_3_PLUS_TEAE_VOMITING,
    # Safety — TRAE
    AttributeType.TRAE,
    AttributeType.GRADE_3_PLUS_TRAE,
    AttributeType.GRADE_3_TRAE,
    AttributeType.GRADE_4_TRAE,
    AttributeType.GRADE_5_TRAE,
    AttributeType.TRAE_LEADING_TO_DISCONTINUATION,
    AttributeType.TRAE_LEADING_TO_DEATH,
    AttributeType.SERIOUS_TRAE,
    AttributeType.TRAE_IMMUNE_RELATED,
    AttributeType.TRAE_LEADING_TO_DOSE_REDUCTION,
    AttributeType.TRAE_LEADING_TO_DOSE_INTERRUPTION,
    AttributeType.TRAE_REQUIRING_HOSPITALIZATION,
    # Safety — Grade 3+ TRAE specific
    AttributeType.GRADE_3_PLUS_TRAE_IMMUNE_RELATED,
    AttributeType.GRADE_3_PLUS_TRAE_IRR,
    AttributeType.GRADE_3_PLUS_TRAE_CRS,
    AttributeType.GRADE_3_PLUS_TRAE_COLITIS,
    AttributeType.GRADE_3_PLUS_TRAE_THROMBOCYTOPENIA,
    AttributeType.GRADE_3_PLUS_TRAE_NEUTROPENIA,
    AttributeType.GRADE_3_PLUS_TRAE_LEUKOPENIA,
    AttributeType.GRADE_3_PLUS_TRAE_FATIGUE,
    AttributeType.GRADE_3_PLUS_TRAE_NAUSEA,
    AttributeType.GRADE_3_PLUS_TRAE_ANEMIA,
    AttributeType.GRADE_3_PLUS_TRAE_DIARRHEA,
    AttributeType.GRADE_3_PLUS_TRAE_HYPERGLYCEMIA,
    AttributeType.GRADE_3_PLUS_TRAE_DYSPNEA,
    AttributeType.GRADE_3_PLUS_TRAE_PYREXIA,
    AttributeType.GRADE_3_PLUS_TRAE_BLEEDING,
    AttributeType.GRADE_3_PLUS_TRAE_PRURITUS,
    AttributeType.GRADE_3_PLUS_TRAE_RASH,
    AttributeType.GRADE_3_PLUS_TRAE_PNEUMONIA,
    AttributeType.GRADE_3_PLUS_TRAE_THYROIDITIS,
    AttributeType.GRADE_3_PLUS_TRAE_HYPOPHYSITIS,
    AttributeType.GRADE_3_PLUS_TRAE_HEPATITIS,
    AttributeType.GRADE_3_PLUS_TRAE_PNEUMONITIS,
    AttributeType.GRADE_3_PLUS_TRAE_ALANINE_AMINOTRANSFERASE,
    AttributeType.GRADE_3_PLUS_TRAE_HYPOTHYROIDISM,
    AttributeType.GRADE_3_PLUS_TRAE_HYPERTHYROIDISM,
    AttributeType.GRADE_3_PLUS_TRAE_AST_INCREASED,
    AttributeType.GRADE_3_PLUS_TRAE_VOMITING,
]


# The set of attributes extracted from conference abstracts (ASCO, ESMO).
# Abstracts expose fewer attributes than publications; the abstract pipeline
# imports this constant rather than defining its own list.
ABSTRACT_ATTRIBUTES: list[AttributeType] = [
    # General
    AttributeType.CONFERENCE,
    AttributeType.PUBLISHED_YEAR,
    AttributeType.ABSTRACT_NUMBER,
    AttributeType.TRIAL_NAME,
    AttributeType.CANCER_TYPE,
    AttributeType.NCT_NUMBER,
    AttributeType.NUMBER_OF_PATIENTS,
    AttributeType.LINE_OF_TREATMENT,
    AttributeType.MODALITY,
    AttributeType.TARGET,
    # Efficacy - Response Rates
    AttributeType.OBJECTIVE_RESPONSE_RATE,
    AttributeType.COMPLETE_RESPONSE,
    AttributeType.PATHOLOGICAL_COMPLETE_RESPONSE,
    AttributeType.COMPLETE_METABOLIC_RESPONSE,
    AttributeType.DISEASE_CONTROL_RATE,
    AttributeType.CLINICAL_BENEFIT_RATE,
    AttributeType.MEDIAN_DOR,
    AttributeType.DOR_RATE,
    # Efficacy - Survival Metrics (PFS Family)
    AttributeType.MEDIAN_PFS,
    AttributeType.MEDIAN_FOLLOWUP_PFS,
    AttributeType.P_VALUE_PFS,
    AttributeType.HR_PFS,
    AttributeType.CI_HR_PFS,
    # Efficacy - OS Family
    AttributeType.MEDIAN_OS,
    AttributeType.MEDIAN_FOLLOWUP_OS,
    AttributeType.P_VALUE_OS,
    AttributeType.HR_OS,
    AttributeType.CI_HR_OS,
    # Efficacy - PFS Rate Timepoints
    AttributeType.PFS_RATE_6M,
    AttributeType.PFS_RATE_9M,
    AttributeType.PFS_RATE_12M,
    AttributeType.PFS_RATE_18M,
    AttributeType.PFS_RATE_24M,
    AttributeType.PFS_RATE_36M,
    AttributeType.PFS_RATE_48M,
    # Efficacy - OS Rate Timepoints
    AttributeType.OS_RATE_6M,
    AttributeType.OS_RATE_9M,
    AttributeType.OS_RATE_12M,
    AttributeType.OS_RATE_18M,
    AttributeType.OS_RATE_24M,
    AttributeType.OS_RATE_36M,
    AttributeType.OS_RATE_48M,
    # Efficacy - EFS Family (Event-Free Survival)
    AttributeType.EFS,
    AttributeType.P_VALUE_EFS,
    AttributeType.HR_EFS,
    AttributeType.CI_HR_EFS,
    # Efficacy - RFS Family (Recurrence-Free Survival / Relapse-Free Survival)
    AttributeType.RFS,
    AttributeType.P_VALUE_RFS,
    AttributeType.LENGTH_RFS,
    AttributeType.HR_RFS,
    AttributeType.CI_HR_RFS,
    # Efficacy - MFS Family (Metastasis-Free Survival)
    AttributeType.MFS,
    AttributeType.LENGTH_MFS,
    AttributeType.HR_MFS,
    AttributeType.CI_HR_MFS,
    # Efficacy - Time-to Metrics
    AttributeType.TTR,
    AttributeType.TTP,
    AttributeType.HR_TTP,
    AttributeType.CI_HR_TTP,
    AttributeType.TTNT,
    AttributeType.TTF,
    # Safety — AE
    AttributeType.AE,
    AttributeType.GRADE_3_PLUS_AE,
    AttributeType.AE_LEADING_TO_DISCONTINUATION,
    AttributeType.SERIOUS_AE,
    AttributeType.IMMUNE_RELATED_AE,
    AttributeType.SERIOUS_IMMUNE_RELATED_AE,
    AttributeType.AE_LEADING_TO_DEATH,
    AttributeType.AE_LEADING_TO_DOSE_REDUCTION,
    AttributeType.AE_LEADING_TO_DOSE_INTERRUPTION,
    AttributeType.AE_REQUIRING_HOSPITALIZATION,
    # Safety — Specific AEs
    AttributeType.CRS,
    AttributeType.IRR,
    # Safety — Grade 3+ AE specific
    AttributeType.GRADE_3_PLUS_AE_IMMUNE_RELATED,
    AttributeType.GRADE_3_PLUS_AE_IRR,
    AttributeType.GRADE_3_PLUS_AE_CRS,
    AttributeType.GRADE_3_PLUS_AE_COLITIS,
    AttributeType.GRADE_3_PLUS_AE_THROMBOCYTOPENIA,
    AttributeType.GRADE_3_PLUS_AE_NEUTROPENIA,
    AttributeType.GRADE_3_PLUS_AE_LEUKOPENIA,
    AttributeType.GRADE_3_PLUS_AE_FATIGUE,
    # Safety — TEAE
    AttributeType.TEAE,
    AttributeType.GRADE_3_PLUS_TEAE,
    AttributeType.GRADE_3_TEAE,
    AttributeType.GRADE_4_TEAE,
    AttributeType.GRADE_5_TEAE,
    AttributeType.TEAE_LEADING_TO_DISCONTINUATION,
    AttributeType.TEAE_LEADING_TO_DEATH,
    AttributeType.SERIOUS_TEAE,
    AttributeType.TEAE_IMMUNE_RELATED,
    AttributeType.TEAE_LEADING_TO_DOSE_REDUCTION,
    AttributeType.TEAE_LEADING_TO_DOSE_INTERRUPTION,
    AttributeType.TEAE_REQUIRING_HOSPITALIZATION,
    # Safety — Grade 3+ TEAE specific
    AttributeType.GRADE_3_PLUS_TEAE_IMMUNE_RELATED,
    AttributeType.GRADE_3_PLUS_TEAE_IRR,
    AttributeType.GRADE_3_PLUS_TEAE_CRS,
    AttributeType.GRADE_3_PLUS_TEAE_COLITIS,
    AttributeType.GRADE_3_PLUS_TEAE_THROMBOCYTOPENIA,
    AttributeType.GRADE_3_PLUS_TEAE_NEUTROPENIA,
    AttributeType.GRADE_3_PLUS_TEAE_LEUKOPENIA,
    AttributeType.GRADE_3_PLUS_TEAE_FATIGUE,
    # Safety — TRAE
    AttributeType.TRAE,
    AttributeType.GRADE_3_PLUS_TRAE,
    AttributeType.GRADE_3_TRAE,
    AttributeType.GRADE_4_TRAE,
    AttributeType.GRADE_5_TRAE,
    AttributeType.TRAE_LEADING_TO_DISCONTINUATION,
    AttributeType.TRAE_LEADING_TO_DEATH,
    AttributeType.SERIOUS_TRAE,
    AttributeType.TRAE_IMMUNE_RELATED,
    AttributeType.TRAE_LEADING_TO_DOSE_REDUCTION,
    AttributeType.TRAE_LEADING_TO_DOSE_INTERRUPTION,
    AttributeType.TRAE_REQUIRING_HOSPITALIZATION,
    # Safety — Grade 3+ TRAE specific
    AttributeType.GRADE_3_PLUS_TRAE_IMMUNE_RELATED,
    AttributeType.GRADE_3_PLUS_TRAE_IRR,
    AttributeType.GRADE_3_PLUS_TRAE_CRS,
    AttributeType.GRADE_3_PLUS_TRAE_COLITIS,
    AttributeType.GRADE_3_PLUS_TRAE_THROMBOCYTOPENIA,
    AttributeType.GRADE_3_PLUS_TRAE_NEUTROPENIA,
    AttributeType.GRADE_3_PLUS_TRAE_LEUKOPENIA,
    AttributeType.GRADE_3_PLUS_TRAE_FATIGUE,
]
