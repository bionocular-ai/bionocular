"""Keyword mappings for Tier 3 RAG filtering.

This module contains keyword mappings used to filter retrieval results
and eliminate semantic similarity false positives.

Format:
- List[str] for simple OR matching (any keyword matches)
- List[List[str]] for grouped AND matching (all groups must match)
"""

from typing import Union

from .extraction_models import AttributeType

# All three AE reporting standards — used as the first keyword group in all
# GRADE_3_PLUS_* attributes so they can retrieve from whichever single AE table
# the paper uses (papers report in exactly one of: AE, TEAE, or TRAE).
_GRADE3_AE_REPORTING_TERMS: list[str] = [
    "teae",
    "treatment emergent",
    "treatment-emergent",
    "trae",
    "treatment related",
    "treatment-related",
    "drug-related",
    "regardless of cause",
    "any adverse event",
    "all adverse events",
    "adverse event",
    "toxicity",
]

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
        _GRADE3_AE_REPORTING_TERMS,
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
        _GRADE3_AE_REPORTING_TERMS,
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
        _GRADE3_AE_REPORTING_TERMS,
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
        _GRADE3_AE_REPORTING_TERMS,
        ["anemia", "anaemia", "hemoglobin decreased", "hb decreased"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_AE_THROMBOCYTOPENIA: [
        _GRADE3_AE_REPORTING_TERMS,
        ["thrombocytopenia", "platelet count decreased"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_AE_NEUTROPENIA: [
        _GRADE3_AE_REPORTING_TERMS,
        ["neutropenia", "neutrophil count decreased"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_AE_DIARRHEA: [
        _GRADE3_AE_REPORTING_TERMS,
        ["diarrhea", "diarrhoea"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_AE_COLITIS: [
        _GRADE3_AE_REPORTING_TERMS,
        ["colitis"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_AE_PNEUMONITIS: [
        _GRADE3_AE_REPORTING_TERMS,
        ["pneumonitis", "interstitial lung disease", "ild"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_AE_ALANINE_AMINOTRANSFERASE: [
        _GRADE3_AE_REPORTING_TERMS,
        ["alanine aminotransferase", "alt"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_AE_RASH: [
        _GRADE3_AE_REPORTING_TERMS,
        ["rash"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_AE_CRS: [
        _GRADE3_AE_REPORTING_TERMS,
        ["crs", "cytokine release syndrome"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    # ============================================================================
    # NEW: Specific Grade 3+ TRAE (Treatment-Related)
    # Logic: [Context: Drug Related] AND [Symptom] AND [Grade: 3+]
    # ============================================================================
    AttributeType.GRADE_3_PLUS_TRAE_ANEMIA: [
        _GRADE3_AE_REPORTING_TERMS,
        ["anemia", "anaemia", "hemoglobin decreased"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TRAE_THROMBOCYTOPENIA: [
        _GRADE3_AE_REPORTING_TERMS,
        ["thrombocytopenia", "platelet count decreased"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TRAE_NEUTROPENIA: [
        _GRADE3_AE_REPORTING_TERMS,
        ["neutropenia", "neutrophil count decreased"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TRAE_DIARRHEA: [
        _GRADE3_AE_REPORTING_TERMS,
        ["diarrhea", "diarrhoea"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TRAE_COLITIS: [
        _GRADE3_AE_REPORTING_TERMS,
        ["colitis"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TRAE_PNEUMONITIS: [
        _GRADE3_AE_REPORTING_TERMS,
        ["pneumonitis", "interstitial lung disease", "ild"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TRAE_ALANINE_AMINOTRANSFERASE: [
        _GRADE3_AE_REPORTING_TERMS,
        ["alanine aminotransferase", "alt"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TRAE_RASH: [
        _GRADE3_AE_REPORTING_TERMS,
        ["rash"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    # ============================================================================
    # NEW: Specific Grade 3+ TEAE (Treatment-Emergent / All Causality)
    # Logic: [Context: Regardless of cause] AND [Symptom] AND [Grade: 3+]
    # ============================================================================
    AttributeType.GRADE_3_PLUS_TEAE_ANEMIA: [
        _GRADE3_AE_REPORTING_TERMS,
        ["anemia", "anaemia", "hemoglobin decreased"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TEAE_THROMBOCYTOPENIA: [
        _GRADE3_AE_REPORTING_TERMS,
        ["thrombocytopenia", "platelet count decreased"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TEAE_NEUTROPENIA: [
        _GRADE3_AE_REPORTING_TERMS,
        ["neutropenia", "neutrophil count decreased"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TEAE_DIARRHEA: [
        _GRADE3_AE_REPORTING_TERMS,
        ["diarrhea", "diarrhoea"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TEAE_COLITIS: [
        _GRADE3_AE_REPORTING_TERMS,
        ["colitis"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TEAE_PNEUMONITIS: [
        _GRADE3_AE_REPORTING_TERMS,
        ["pneumonitis", "interstitial lung disease", "ild"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TEAE_ALANINE_AMINOTRANSFERASE: [
        _GRADE3_AE_REPORTING_TERMS,
        ["alanine aminotransferase", "alt"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    # Keep existing entries for TEAE_RASH and TEAE_CRS that weren't in the user's request
    AttributeType.GRADE_3_PLUS_TEAE_RASH: [
        _GRADE3_AE_REPORTING_TERMS,
        ["rash"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TEAE_CRS: [
        _GRADE3_AE_REPORTING_TERMS,
        ["crs", "cytokine release syndrome"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    # Keep existing entry for TRAE_CRS that wasn't in the user's request
    AttributeType.GRADE_3_PLUS_TRAE_CRS: [
        _GRADE3_AE_REPORTING_TERMS,
        ["crs", "cytokine release syndrome"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    # Efficacy - 95% Confidence Intervals for Hazard Ratios
    AttributeType.CI_HR_PFS: [
        ["pfs", "progression-free", "progression free"],
        ["confidence interval", "95% ci", "ci", "95%ci"],
    ],
    AttributeType.CI_HR_OS: [
        ["os", "overall survival"],
        ["confidence interval", "95% ci", "ci", "95%ci"],
    ],
    AttributeType.CI_HR_EFS: [
        ["efs", "event-free", "event free"],
        ["confidence interval", "95% ci", "ci", "95%ci"],
    ],
    AttributeType.CI_HR_RFS: [
        ["rfs", "recurrence-free", "relapse-free", "recurrence free", "relapse free"],
        ["confidence interval", "95% ci", "ci", "95%ci"],
    ],
    AttributeType.CI_HR_MFS: [
        ["mfs", "metastasis-free", "metastasis free"],
        ["confidence interval", "95% ci", "ci", "95%ci"],
    ],
    AttributeType.HR_TTP: [
        ["ttp", "time to progression"],
        ["hr", "hazard ratio"],
    ],
    AttributeType.CI_HR_TTP: [
        ["ttp", "time to progression"],
        ["confidence interval", "95% ci", "ci", "95%ci"],
    ],
    # Safety - IRR
    AttributeType.IRR: [
        "infusion-related reaction",
        "infusion related reaction",
        "irr",
        "infusion reaction",
    ],
    # Safety - AE dose/hospitalization
    AttributeType.AE_LEADING_TO_DOSE_REDUCTION: [
        ["dose reduction", "reduced dose", "dose modification"],
        ["adverse event", "ae", "any grade", "safety"],
    ],
    AttributeType.AE_LEADING_TO_DOSE_INTERRUPTION: [
        ["dose interruption", "dose delay", "interrupted"],
        ["adverse event", "ae", "any grade", "safety"],
    ],
    AttributeType.AE_REQUIRING_HOSPITALIZATION: [
        ["hospitalization", "hospitalized", "hospitalisation"],
        ["adverse event", "ae", "safety"],
    ],
    # Safety - TEAE dose/hospitalization
    AttributeType.TEAE_LEADING_TO_DOSE_REDUCTION: [
        ["dose reduction", "reduced dose", "dose modification"],
        ["teae", "treatment-emergent", "treatment emergent"],
    ],
    AttributeType.TEAE_LEADING_TO_DOSE_INTERRUPTION: [
        ["dose interruption", "dose delay", "interrupted"],
        ["teae", "treatment-emergent", "treatment emergent"],
    ],
    AttributeType.TEAE_REQUIRING_HOSPITALIZATION: [
        ["hospitalization", "hospitalized", "hospitalisation"],
        ["teae", "treatment-emergent", "treatment emergent"],
    ],
    # Safety - TRAE dose/hospitalization
    AttributeType.TRAE_LEADING_TO_DOSE_REDUCTION: [
        ["dose reduction", "reduced dose", "dose modification"],
        ["trae", "treatment-related", "treatment related", "drug-related"],
    ],
    AttributeType.TRAE_LEADING_TO_DOSE_INTERRUPTION: [
        ["dose interruption", "dose delay", "interrupted"],
        ["trae", "treatment-related", "treatment related", "drug-related"],
    ],
    AttributeType.TRAE_REQUIRING_HOSPITALIZATION: [
        ["hospitalization", "hospitalized", "hospitalisation"],
        ["trae", "treatment-related", "treatment related", "drug-related"],
    ],
    # Safety - Grade 3+ IRR (AE/TRAE/TEAE) — all three share unified reporting terms
    AttributeType.GRADE_3_PLUS_AE_IRR: [
        ["irr", "infusion-related reaction", "infusion reaction"],
        _GRADE3_AE_REPORTING_TERMS,
        ["grade 3", "grade 4", "grade 3-4", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TRAE_IRR: [
        ["irr", "infusion-related reaction", "infusion reaction"],
        _GRADE3_AE_REPORTING_TERMS,
        ["grade 3", "grade 4", "grade 3-4", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TEAE_IRR: [
        ["irr", "infusion-related reaction", "infusion reaction"],
        _GRADE3_AE_REPORTING_TERMS,
        ["grade 3", "grade 4", "grade 3-4", "grade ≥3", "severe", "≥g3"],
    ],
    # Safety - Grade 3+ Fatigue (AE/TRAE/TEAE) — all three share unified reporting terms
    AttributeType.GRADE_3_PLUS_AE_FATIGUE: [
        _GRADE3_AE_REPORTING_TERMS,
        ["fatigue", "asthenia"],
        ["grade 3", "grade 4", "grade 3-4", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TRAE_FATIGUE: [
        _GRADE3_AE_REPORTING_TERMS,
        ["fatigue", "asthenia"],
        ["grade 3", "grade 4", "grade 3-4", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TEAE_FATIGUE: [
        _GRADE3_AE_REPORTING_TERMS,
        ["fatigue", "asthenia"],
        ["grade 3", "grade 4", "grade 3-4", "grade ≥3", "severe", "≥g3"],
    ],
    # ============================================================================
    # Missing Grade 3+ AE Specific Adverse Events (General / Any Cause)
    # ============================================================================
    AttributeType.GRADE_3_PLUS_AE_LEUKOPENIA: [
        _GRADE3_AE_REPORTING_TERMS,
        ["leukopenia", "leukocyte", "white blood cell", "wbc"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_AE_NAUSEA: [
        _GRADE3_AE_REPORTING_TERMS,
        ["nausea"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_AE_HYPERGLYCEMIA: [
        _GRADE3_AE_REPORTING_TERMS,
        ["hyperglycemia", "blood glucose", "glucose"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_AE_NEUTROPHIL_COUNT_DECREASED: [
        _GRADE3_AE_REPORTING_TERMS,
        ["neutrophil count decreased", "neutropenia", "neutrophil"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_AE_DYSPNEA: [
        _GRADE3_AE_REPORTING_TERMS,
        ["dyspnea", "dyspnoea", "shortness of breath"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_AE_PYREXIA: [
        _GRADE3_AE_REPORTING_TERMS,
        ["pyrexia", "fever"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_AE_BLEEDING: [
        _GRADE3_AE_REPORTING_TERMS,
        ["bleeding", "hemorrhage", "haemorrhage"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_AE_PRURITUS: [
        _GRADE3_AE_REPORTING_TERMS,
        ["pruritus", "itching", "itch"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_AE_PNEUMONIA: [
        _GRADE3_AE_REPORTING_TERMS,
        ["pneumonia", "lung infection"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_AE_THYROIDITIS: [
        _GRADE3_AE_REPORTING_TERMS,
        ["thyroiditis", "thyroid"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_AE_HYPOPHYSITIS: [
        _GRADE3_AE_REPORTING_TERMS,
        ["hypophysitis", "pituitary"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_AE_HEPATITIS: [
        _GRADE3_AE_REPORTING_TERMS,
        ["hepatitis", "liver"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_AE_WBC_DECREASED: [
        _GRADE3_AE_REPORTING_TERMS,
        ["wbc", "white blood cell", "leukocyte", "leukopenia"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_AE_IMMUNE_RELATED: [
        _GRADE3_AE_REPORTING_TERMS,
        ["immune", "immune-related", "immunotherapy-related", "irae"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_AE_HYPOTHYROIDISM: [
        _GRADE3_AE_REPORTING_TERMS,
        ["hypothyroidism", "thyroid"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_AE_HYPERTHYROIDISM: [
        _GRADE3_AE_REPORTING_TERMS,
        ["hyperthyroidism", "thyroid"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_AE_AST_INCREASED: [
        _GRADE3_AE_REPORTING_TERMS,
        ["ast", "aspartate aminotransferase", "aspartate transaminase"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_AE_VOMITING: [
        _GRADE3_AE_REPORTING_TERMS,
        ["vomiting", "emesis", "nausea"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    # ============================================================================
    # Missing Grade 3+ TRAE Specific Adverse Events (Treatment-Related)
    # ============================================================================
    AttributeType.GRADE_3_PLUS_TRAE_LEUKOPENIA: [
        _GRADE3_AE_REPORTING_TERMS,
        ["leukopenia", "leukocyte", "white blood cell", "wbc"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TRAE_NAUSEA: [
        _GRADE3_AE_REPORTING_TERMS,
        ["nausea"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TRAE_HYPERGLYCEMIA: [
        _GRADE3_AE_REPORTING_TERMS,
        ["hyperglycemia", "blood glucose", "glucose"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TRAE_NEUTROPHIL_COUNT_DECREASED: [
        _GRADE3_AE_REPORTING_TERMS,
        ["neutrophil count decreased", "neutropenia", "neutrophil"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TRAE_DYSPNEA: [
        _GRADE3_AE_REPORTING_TERMS,
        ["dyspnea", "dyspnoea", "shortness of breath"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TRAE_PYREXIA: [
        _GRADE3_AE_REPORTING_TERMS,
        ["pyrexia", "fever"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TRAE_BLEEDING: [
        _GRADE3_AE_REPORTING_TERMS,
        ["bleeding", "hemorrhage", "haemorrhage"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TRAE_PRURITUS: [
        _GRADE3_AE_REPORTING_TERMS,
        ["pruritus", "itching", "itch"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TRAE_PNEUMONIA: [
        _GRADE3_AE_REPORTING_TERMS,
        ["pneumonia", "lung infection"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TRAE_THYROIDITIS: [
        _GRADE3_AE_REPORTING_TERMS,
        ["thyroiditis", "thyroid"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TRAE_HYPOPHYSITIS: [
        _GRADE3_AE_REPORTING_TERMS,
        ["hypophysitis", "pituitary"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TRAE_HEPATITIS: [
        _GRADE3_AE_REPORTING_TERMS,
        ["hepatitis", "liver"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TRAE_WBC_DECREASED: [
        _GRADE3_AE_REPORTING_TERMS,
        ["wbc", "white blood cell", "leukocyte", "leukopenia"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TRAE_IMMUNE_RELATED: [
        _GRADE3_AE_REPORTING_TERMS,
        ["immune", "immune-related", "immunotherapy-related", "irae"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TRAE_HYPOTHYROIDISM: [
        _GRADE3_AE_REPORTING_TERMS,
        ["hypothyroidism", "thyroid"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TRAE_HYPERTHYROIDISM: [
        _GRADE3_AE_REPORTING_TERMS,
        ["hyperthyroidism", "thyroid"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TRAE_AST_INCREASED: [
        _GRADE3_AE_REPORTING_TERMS,
        ["ast", "aspartate aminotransferase", "aspartate transaminase"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TRAE_VOMITING: [
        _GRADE3_AE_REPORTING_TERMS,
        ["vomiting", "emesis", "nausea"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    # ============================================================================
    # Missing Grade 3+ TEAE Specific Adverse Events (Treatment-Emergent)
    # ============================================================================
    AttributeType.GRADE_3_PLUS_TEAE_LEUKOPENIA: [
        _GRADE3_AE_REPORTING_TERMS,
        ["leukopenia", "leukocyte", "white blood cell", "wbc"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TEAE_NAUSEA: [
        _GRADE3_AE_REPORTING_TERMS,
        ["nausea"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TEAE_HYPERGLYCEMIA: [
        _GRADE3_AE_REPORTING_TERMS,
        ["hyperglycemia", "blood glucose", "glucose"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TEAE_NEUTROPHIL_COUNT_DECREASED: [
        _GRADE3_AE_REPORTING_TERMS,
        ["neutrophil count decreased", "neutropenia", "neutrophil"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TEAE_DYSPNEA: [
        _GRADE3_AE_REPORTING_TERMS,
        ["dyspnea", "dyspnoea", "shortness of breath"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TEAE_PYREXIA: [
        _GRADE3_AE_REPORTING_TERMS,
        ["pyrexia", "fever"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TEAE_BLEEDING: [
        _GRADE3_AE_REPORTING_TERMS,
        ["bleeding", "hemorrhage", "haemorrhage"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TEAE_PRURITUS: [
        _GRADE3_AE_REPORTING_TERMS,
        ["pruritus", "itching", "itch"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TEAE_PNEUMONIA: [
        _GRADE3_AE_REPORTING_TERMS,
        ["pneumonia", "lung infection"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TEAE_THYROIDITIS: [
        _GRADE3_AE_REPORTING_TERMS,
        ["thyroiditis", "thyroid"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TEAE_HYPOPHYSITIS: [
        _GRADE3_AE_REPORTING_TERMS,
        ["hypophysitis", "pituitary"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TEAE_HEPATITIS: [
        _GRADE3_AE_REPORTING_TERMS,
        ["hepatitis", "liver"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TEAE_WBC_DECREASED: [
        _GRADE3_AE_REPORTING_TERMS,
        ["wbc", "white blood cell", "leukocyte", "leukopenia"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TEAE_IMMUNE_RELATED: [
        _GRADE3_AE_REPORTING_TERMS,
        ["immune", "immune-related", "immunotherapy-related", "irae"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TEAE_HYPOTHYROIDISM: [
        _GRADE3_AE_REPORTING_TERMS,
        ["hypothyroidism", "thyroid"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TEAE_HYPERTHYROIDISM: [
        _GRADE3_AE_REPORTING_TERMS,
        ["hyperthyroidism", "thyroid"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TEAE_AST_INCREASED: [
        _GRADE3_AE_REPORTING_TERMS,
        ["ast", "aspartate aminotransferase", "aspartate transaminase"],
        ["grade 3", "grade 4", "grade 3-4", "grade 3-5", "grade ≥3", "severe", "≥g3"],
    ],
    AttributeType.GRADE_3_PLUS_TEAE_VOMITING: [
        _GRADE3_AE_REPORTING_TERMS,
        ["vomiting", "emesis", "nausea"],
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
