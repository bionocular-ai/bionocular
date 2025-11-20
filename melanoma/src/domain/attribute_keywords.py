"""Keyword mappings for Tier 3 RAG filtering.

This module contains keyword mappings used to filter retrieval results
and eliminate semantic similarity false positives.

Format:
- List[str] for simple OR matching (any keyword matches)
- List[List[str]] for grouped AND matching (all groups must match)
"""

from typing import Union

from .extraction_models import AttributeType

# Keyword mappings for filtering
# Format: List[str] for simple OR matching
#         List[List[str]] for grouped AND matching (all groups must match)
ATTRIBUTE_KEYWORDS: dict[AttributeType, Union[list[str], list[list[str]]]] = {
    # PFS Family
    AttributeType.MEDIAN_PFS: [
        "pfs",
        "progression-free survival",
        "progression free survival",
        "progression-free",
        "progression free",
    ],
    AttributeType.MEDIAN_FOLLOWUP_PFS: [
        ["pfs", "progression-free", "progression free"],  # Group 1: Must have PFS
        [
            "follow-up",
            "followup",
            "follow up",
            "median follow",
        ],  # Group 2: Must have follow-up
    ],
    AttributeType.P_VALUE_PFS: [
        ["pfs", "progression-free", "progression free"],  # Group 1: Must have PFS
        ["p-value", "p value", "p"],  # Group 2: Must have p-value
    ],
    AttributeType.HR_PFS: [
        ["pfs", "progression-free", "progression free"],  # Group 1: Must have PFS
        ["hr", "hazard ratio"],  # Group 2: Must have HR
    ],
    AttributeType.PFS_RATE_6M: [
        ["pfs", "progression-free", "progression free"],
        [
            "6 month",
            "6 months",
            "6 mo",
            "6m",
            "6 mth",
            "6 mths",
            "six month",
            "six months",
        ],
    ],
    AttributeType.PFS_RATE_9M: [
        ["pfs", "progression-free", "progression free"],
        [
            "9 month",
            "9 months",
            "9 mo",
            "9m",
            "9 mth",
            "9 mths",
            "nine month",
            "nine months",
        ],
    ],
    AttributeType.PFS_RATE_12M: [
        ["pfs", "progression-free", "progression free"],
        [
            "12 month",
            "12 months",
            "12 mo",
            "12mo",
            "12m",
            "1 year",
            "1 years",
            "1 yr",
            "1yr",
            "1 y",
            "1y",
            "12 mth",
            "12 mths",
            "one year",
            "twelve month",
            "twelve months",
        ],
    ],
    AttributeType.PFS_RATE_18M: [
        ["pfs", "progression-free", "progression free"],
        ["18 month", "18 months", "18 mo", "18mo", "18m", "18 mth", "18 mths"],
    ],
    AttributeType.PFS_RATE_24M: [
        ["pfs", "progression-free", "progression free"],
        [
            "24 month",
            "24 months",
            "24 mo",
            "24mo",
            "24m",
            "2 year",
            "2 years",
            "2 yr",
            "2yr",
            "2 y",
            "2y",
            "24 mth",
            "24 mths",
            "two year",
            "two years",
        ],
    ],
    AttributeType.PFS_RATE_36M: [
        ["pfs", "progression-free", "progression free"],
        [
            "36 month",
            "36 months",
            "36 mo",
            "36mo",
            "36m",
            "3 year",
            "3 years",
            "3 yr",
            "3yr",
            "3 y",
            "3y",
            "36 mth",
            "36 mths",
            "three year",
            "three years",
        ],
    ],
    AttributeType.PFS_RATE_48M: [
        ["pfs", "progression-free", "progression free"],
        [
            "48 month",
            "48 months",
            "48 mo",
            "48mo",
            "48m",
            "4 year",
            "4 years",
            "4 yr",
            "4yr",
            "4 y",
            "4y",
            "48 mth",
            "48 mths",
            "four year",
            "four years",
        ],
    ],
    # OS Family
    AttributeType.MEDIAN_OS: ["os", "overall survival"],
    AttributeType.MEDIAN_FOLLOWUP_OS: [
        ["os", "overall survival"],
        ["follow-up", "followup", "follow up", "median follow"],
    ],
    AttributeType.P_VALUE_OS: [["os", "overall survival"], ["p-value", "p value", "p"]],
    AttributeType.HR_OS: [
        ["os", "overall survival"],  # Group 1: Must have OS
        ["hr", "hazard ratio"],  # Group 2: Must have HR
    ],
    AttributeType.OS_RATE_6M: [
        ["os", "overall survival"],
        [
            "6 month",
            "6 months",
            "6 mo",
            "6m",
            "6 mth",
            "6 mths",
            "six month",
            "six months",
        ],
    ],
    AttributeType.OS_RATE_9M: [
        ["os", "overall survival"],
        [
            "9 month",
            "9 months",
            "9 mo",
            "9m",
            "9 mth",
            "9 mths",
            "nine month",
            "nine months",
        ],
    ],
    AttributeType.OS_RATE_12M: [
        ["os", "overall survival"],
        [
            "12 month",
            "12 months",
            "12 mo",
            "12mo",
            "12m",
            "1 year",
            "1 years",
            "1 yr",
            "1yr",
            "1 y",
            "1y",
            "12 mth",
            "12 mths",
            "one year",
            "twelve month",
            "twelve months",
        ],
    ],
    AttributeType.OS_RATE_18M: [
        ["os", "overall survival"],
        ["18 month", "18 months", "18 mo", "18mo", "18m", "18 mth", "18 mths"],
    ],
    AttributeType.OS_RATE_24M: [
        ["os", "overall survival"],
        [
            "24 month",
            "24 months",
            "24 mo",
            "24mo",
            "24m",
            "2 year",
            "2 years",
            "2 yr",
            "2yr",
            "2 y",
            "2y",
            "24 mth",
            "24 mths",
            "two year",
            "two years",
        ],
    ],
    AttributeType.OS_RATE_36M: [
        ["os", "overall survival"],
        [
            "36 month",
            "36 months",
            "36 mo",
            "36mo",
            "36m",
            "3 year",
            "3 years",
            "3 yr",
            "3yr",
            "3 y",
            "3y",
            "36 mth",
            "36 mths",
            "three year",
            "three years",
        ],
    ],
    AttributeType.OS_RATE_48M: [
        ["os", "overall survival"],
        [
            "48 month",
            "48 months",
            "48 mo",
            "48mo",
            "48m",
            "4 year",
            "4 years",
            "4 yr",
            "4yr",
            "4 y",
            "4y",
            "48 mth",
            "48 mths",
            "four year",
            "four years",
        ],
    ],
    # Response Rates
    AttributeType.OBJECTIVE_RESPONSE_RATE: [
        "orr",
        "objective response rate",
        "objective response rates",
        "overall response rate",
        "overall response rates",
        "best overall response",
        "bor",
        "response rate",
        "response rates",
        "rr",
    ],
    AttributeType.COMPLETE_RESPONSE: ["cr", "complete response"],
    AttributeType.PATHOLOGICAL_COMPLETE_RESPONSE: [
        "pcr",
        "pathological complete response",
        "pathologic complete response",
    ],
    AttributeType.COMPLETE_METABOLIC_RESPONSE: ["cmr", "complete metabolic response"],
    AttributeType.DISEASE_CONTROL_RATE: [
        "dcr",
        "disease control rate",
        "disease control",
    ],
    AttributeType.CLINICAL_BENEFIT_RATE: [
        "cbr",
        "clinical benefit rate",
        "clinical benefit",
    ],
    AttributeType.MEDIAN_DOR: ["dor", "duration of response", "response duration"],
    AttributeType.DOR_RATE: ["dor", "duration of response", "response duration"],
    # Other Survival Metrics
    AttributeType.EFS: ["efs", "event-free survival", "event free survival"],
    AttributeType.P_VALUE_EFS: [
        ["efs", "event-free", "event free"],
        ["p-value", "p value", "p"],
    ],
    AttributeType.HR_EFS: [
        ["efs", "event-free", "event free"],  # Group 1: Must have EFS
        ["hr", "hazard ratio"],  # Group 2: Must have HR
    ],
    AttributeType.RFS: [
        "rfs",
        "recurrence-free survival",
        "recurrence free survival",
        "relapse free survival",
    ],
    AttributeType.P_VALUE_RFS: [
        ["rfs", "recurrence-free", "recurrence free", "relapse free"],
        ["p-value", "p value", "p"],
    ],
    AttributeType.LENGTH_RFS: [
        ["rfs", "recurrence-free", "recurrence free", "relapse free"],
        ["median", "month", "year", "follow-up"],
    ],
    AttributeType.HR_RFS: [
        ["rfs", "recurrence-free", "recurrence free", "relapse free"],
        ["hr", "hazard ratio"],
    ],
    AttributeType.MFS: ["mfs", "metastasis-free survival", "metastasis free survival"],
    AttributeType.LENGTH_MFS: [
        ["mfs", "metastasis-free", "metastasis free"],
        ["median", "month", "year", "follow-up"],
    ],
    AttributeType.HR_MFS: [
        ["mfs", "metastasis-free", "metastasis free"],
        ["hr", "hazard ratio"],
    ],
    AttributeType.TTR: ["ttr", "time to response"],
    AttributeType.TTP: ["ttp", "time to progression"],
    AttributeType.TTNT: ["ttnt", "time to next treatment"],
    AttributeType.TTF: ["ttf", "time to failure", "time to treatment failure"],
    # Demographics (only those extracted from abstracts)
    # Note: minimum_age, maximum_age, sex obtained from ClinicalTrials.gov API
    AttributeType.MEDIAN_AGE: ["age", "median age", "years old", "yr", "yrs"],
    AttributeType.NUMBER_OF_PATIENTS: [
        "patient",
        "patients",
        "pts",
        "enrolled",
        "randomized",
        "n=",
        "N=",
        "screened",
        "eligible",
        "accrued",
        "treated",
        "cohort",
    ],
    # Adverse Events
    AttributeType.AE: ["ae", "adverse event", "toxicity", "tox"],
    AttributeType.GRADE_3_PLUS_AE: [
        ["ae", "adverse event", "toxicity", "tox"],
        ["grade 3", "grade 4", "grade 3-4", "grade ≥3", "g3", "g4", "≥g3"],
    ],
    AttributeType.AE_LEADING_TO_DISCONTINUATION: [
        ["ae", "adverse event", "toxicity", "tox"],
        ["discontinuation", "discontinue", "discontinued"],
    ],
    AttributeType.SERIOUS_AE: [
        ["ae", "adverse event", "toxicity", "tox", "sae"],
        ["serious", "sae"],
    ],
    AttributeType.IMMUNE_RELATED_AE: [
        ["ae", "adverse event", "toxicity", "tox", "irae", "iraes"],
        ["immune", "immune-related", "immunotherapy-related", "irae", "iraes"],
    ],
    AttributeType.SERIOUS_IMMUNE_RELATED_AE: [
        ["ae", "adverse event", "toxicity", "tox", "irae", "iraes", "sae"],
        ["immune", "immune-related", "immunotherapy-related", "irae", "iraes"],
        ["serious", "sae"],
    ],
    AttributeType.AE_LEADING_TO_DEATH: [
        ["ae", "adverse event", "toxicity", "tox"],
        ["death", "fatal", "died"],
    ],
    # Treatment-Emergent Adverse Events (TEAE)
    AttributeType.TEAE: [
        "teae",
        "treatment emergent",
        "treatment-emergent",
        "drug-related",
    ],
    AttributeType.GRADE_3_PLUS_TEAE: [
        ["teae", "treatment emergent", "treatment-emergent"],
        ["grade 3", "grade 4", "grade ≥3", "g3", "g4"],
    ],
    AttributeType.GRADE_3_TEAE: [
        ["teae", "treatment emergent", "treatment-emergent"],
        ["grade 3", "g3"],
    ],
    AttributeType.GRADE_4_TEAE: [
        ["teae", "treatment emergent", "treatment-emergent"],
        ["grade 4", "g4"],
    ],
    AttributeType.GRADE_5_TEAE: [
        ["teae", "treatment emergent", "treatment-emergent"],
        ["grade 5", "g5", "fatal"],
    ],
    AttributeType.TEAE_LEADING_TO_DISCONTINUATION: [
        ["teae", "treatment emergent", "treatment-emergent"],
        ["discontinuation", "discontinue", "discontinued"],
    ],
    AttributeType.TEAE_LEADING_TO_DEATH: [
        ["teae", "treatment emergent", "treatment-emergent"],
        ["death", "fatal", "died"],
    ],
    AttributeType.SERIOUS_TEAE: [
        ["teae", "treatment emergent", "treatment-emergent"],
        ["serious"],
    ],
    AttributeType.TEAE_IMMUNE_RELATED: [
        ["teae", "treatment emergent", "treatment-emergent"],
        ["immune", "immune-related"],
    ],
    # Treatment-Related Adverse Events (TRAE)
    AttributeType.TRAE: [
        "trae",
        "treatment related",
        "treatment-related",
        "drug-related",
    ],
    AttributeType.GRADE_3_PLUS_TRAE: [
        ["trae", "treatment related", "treatment-related"],
        ["grade 3", "grade 4", "grade ≥3", "g3", "g4"],
    ],
    AttributeType.GRADE_3_TRAE: [
        ["trae", "treatment related", "treatment-related"],
        ["grade 3", "g3"],
    ],
    AttributeType.GRADE_4_TRAE: [
        ["trae", "treatment related", "treatment-related"],
        ["grade 4", "g4"],
    ],
    AttributeType.GRADE_5_TRAE: [
        ["trae", "treatment related", "treatment-related"],
        ["grade 5", "g5", "fatal"],
    ],
    AttributeType.TRAE_LEADING_TO_DISCONTINUATION: [
        ["trae", "treatment related", "treatment-related"],
        ["discontinuation", "discontinue", "discontinued"],
    ],
    AttributeType.TRAE_LEADING_TO_DEATH: [
        ["trae", "treatment related", "treatment-related"],
        ["death", "fatal", "died"],
    ],
    AttributeType.SERIOUS_TRAE: [
        ["trae", "treatment related", "treatment-related"],
        ["serious"],
    ],
    AttributeType.TRAE_IMMUNE_RELATED: [
        ["trae", "treatment related", "treatment-related"],
        ["immune", "immune-related"],
    ],
    # Special AE Types
    AttributeType.CRS: ["crs", "cytokine release syndrome"],
    AttributeType.WBC_DECREASED: [
        "wbc",
        "white blood cell",
        "leukocyte",
        "decreased",
        "neutropenia",
    ],
    # ============================================================================
    # NEW: Specific Grade 3+ Adverse Events (General / Any Cause)
    # Logic: [Context: AE] AND [Symptom] AND [Grade: 3+]
    # ============================================================================
    AttributeType.GRADE_3_PLUS_AE_ANEMIA: [
        ["ae", "adverse event", "toxicity", "safety"],
        ["anemia", "anaemia", "hemoglobin decreased", "hb decreased"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_AE_THROMBOCYTOPENIA: [
        ["ae", "adverse event", "toxicity", "safety"],
        ["thrombocytopenia", "platelet count decreased"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_AE_NEUTROPENIA: [
        ["ae", "adverse event", "toxicity", "safety"],
        ["neutropenia", "neutrophil count decreased"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_AE_DIARRHEA: [
        ["ae", "adverse event", "toxicity", "safety"],
        ["diarrhea", "diarrhoea"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_AE_COLITIS: [
        ["ae", "adverse event", "toxicity", "safety"],
        ["colitis"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_AE_PNEUMONITIS: [
        ["ae", "adverse event", "toxicity", "safety"],
        ["pneumonitis", "interstitial lung disease", "ild"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_AE_ALANINE_AMINOTRANSFERASE: [
        ["ae", "adverse event", "toxicity", "safety"],
        ["alanine aminotransferase", "alt"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_AE_RASH: [
        ["ae", "adverse event", "toxicity", "safety"],
        ["rash"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_AE_CRS: [
        ["ae", "adverse event", "toxicity", "safety"],
        ["crs", "cytokine release syndrome"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    # ============================================================================
    # NEW: Specific Grade 3+ TRAE (Treatment-Related)
    # Logic: [Context: Drug Related] AND [Symptom] AND [Grade: 3+]
    # ============================================================================
    AttributeType.GRADE_3_PLUS_TRAE_ANEMIA: [
        ["trae", "treatment related", "drug-related", "attributed to", "related to"],
        ["anemia", "anaemia", "hemoglobin decreased"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TRAE_THROMBOCYTOPENIA: [
        ["trae", "treatment related", "drug-related", "attributed to", "related to"],
        ["thrombocytopenia", "platelet count decreased"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TRAE_NEUTROPENIA: [
        ["trae", "treatment related", "drug-related", "attributed to", "related to"],
        ["neutropenia", "neutrophil count decreased"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TRAE_DIARRHEA: [
        ["trae", "treatment related", "drug-related", "attributed to", "related to"],
        ["diarrhea", "diarrhoea"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TRAE_COLITIS: [
        ["trae", "treatment related", "drug-related", "attributed to", "related to"],
        ["colitis"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TRAE_PNEUMONITIS: [
        ["trae", "treatment related", "drug-related", "attributed to", "related to"],
        ["pneumonitis", "interstitial lung disease", "ild"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TRAE_ALANINE_AMINOTRANSFERASE: [
        ["trae", "treatment related", "drug-related", "attributed to", "related to"],
        ["alanine aminotransferase", "alt"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TRAE_RASH: [
        ["trae", "treatment related", "drug-related", "attributed to", "related to"],
        ["rash"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    # ============================================================================
    # NEW: Specific Grade 3+ TEAE (Treatment-Emergent / All Causality)
    # Logic: [Context: Regardless of cause] AND [Symptom] AND [Grade: 3+]
    # ============================================================================
    AttributeType.GRADE_3_PLUS_TEAE_ANEMIA: [
        ["teae", "treatment emergent", "regardless of cause", "any adverse event", "all adverse events"],
        ["anemia", "anaemia", "hemoglobin decreased"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TEAE_THROMBOCYTOPENIA: [
        ["teae", "treatment emergent", "regardless of cause", "any adverse event", "all adverse events"],
        ["thrombocytopenia", "platelet count decreased"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TEAE_NEUTROPENIA: [
        ["teae", "treatment emergent", "regardless of cause", "any adverse event", "all adverse events"],
        ["neutropenia", "neutrophil count decreased"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TEAE_DIARRHEA: [
        ["teae", "treatment emergent", "regardless of cause", "any adverse event", "all adverse events"],
        ["diarrhea", "diarrhoea"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TEAE_COLITIS: [
        ["teae", "treatment emergent", "regardless of cause", "any adverse event", "all adverse events"],
        ["colitis"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TEAE_PNEUMONITIS: [
        ["teae", "treatment emergent", "regardless of cause", "any adverse event", "all adverse events"],
        ["pneumonitis", "interstitial lung disease", "ild"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TEAE_ALANINE_AMINOTRANSFERASE: [
        ["teae", "treatment emergent", "regardless of cause", "any adverse event", "all adverse events"],
        ["alanine aminotransferase", "alt"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    # Keep existing entries for TEAE_RASH and TEAE_CRS that weren't in the user's request
    AttributeType.GRADE_3_PLUS_TEAE_RASH: [
        ["teae", "treatment emergent", "regardless of cause", "any adverse event", "all adverse events"],
        ["rash"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TEAE_CRS: [
        ["teae", "treatment emergent", "regardless of cause", "any adverse event", "all adverse events"],
        ["crs", "cytokine release syndrome"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    # Keep existing entry for TRAE_CRS that wasn't in the user's request
    AttributeType.GRADE_3_PLUS_TRAE_CRS: [
        ["trae", "treatment related", "drug-related", "attributed to", "related to"],
        ["crs", "cytokine release syndrome"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
}


def get_keywords_for_attribute(
    attribute_type: AttributeType,
) -> Union[list[str], list[list[str]], None]:
    """Get keyword list for an attribute type.

    Args:
        attribute_type: The attribute to get keywords for

    Returns:
        List of keywords (simple or grouped), or None if no keywords defined
    """
    return ATTRIBUTE_KEYWORDS.get(attribute_type)


def has_keyword_filter(attribute_type: AttributeType) -> bool:
    """Check if an attribute has keyword filtering enabled.

    Args:
        attribute_type: The attribute to check

    Returns:
        True if keyword filtering is configured for this attribute
    """
    return attribute_type in ATTRIBUTE_KEYWORDS
