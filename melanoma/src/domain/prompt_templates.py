"""Extraction prompt templates — domain layer.

These prompts encode oncology business rules for attribute extraction:
what to look for, how to interpret clinical values, and what format
to return. They are domain knowledge, not infrastructure.

Infrastructure reads these and passes them to LLM API calls via
`ExtractionPromptTemplateProvider`.
"""

from .extraction_models import AttributeFamily, AttributeType

# Prepended for attributes that risk multi-arm / study-level contamination.
ARM_SPECIFIC_VERIFICATION_PREFIX = (
    "Multi-arm study: extract only this arm's value, not the study total. "
    "Single-arm study: use the total enrolled for all arms. "
)

# Prepended to every attribute prompt in ExtractionPromptTemplateProvider.
SHARED_EXTRACTION_RULES = (
    "Rules: "
    "Percentage values shown as 'N (X%)' → return X (e.g., '125 (85%)' → '85'). "
    "In AE tables where the column header says 'number of patients (percent)', "
    "cells are formatted as 'N (X)' meaning N patients = X percent — return X, not N. "
    "For 'Grade 3+' attributes: if Grade 3, Grade 4, and Grade 5 appear in separate table columns, "
    "sum Grade 3% + Grade 4% + Grade 5% to get the Grade 3+ total; return the percentage, not the patient count. "
    "Do not apply these rules to CI ranges like '0.68 (0.55–0.85)'. "
    "If the value is not explicitly stated in the context, return empty string — do not infer or guess from nearby numbers. "
    "Return numbers only, no units — except CI ranges which use 'low-high' format with two decimals (e.g., '0.42-0.64'), never a single number."
)

# One extraction instruction per AttributeType.
# Infrastructure reads this dict; do not import infrastructure here.
# DEPRECATED — replaced by FAMILY_PROMPTS (Task 4). Kept temporarily so legacy
# RAG extraction path (batch_attribute_extractor.py) still imports cleanly.
# Scheduled for removal in Task 9 / 11. Do not add new entries here.
ATTRIBUTE_PROMPTS: dict[AttributeType, str] = {
    # General Parameters
    AttributeType.NCT_NUMBER: "Extract clinical trial identifier from 'Clinical trial identification:' or 'Clinical Trial Information:' section. Priority: NCT number (NCT + 8 digits), then EudraCT, then other identifiers. Return exactly as found or empty string.",
    AttributeType.CANCER_TYPE: "Extract cancer type. Return exactly one of: Cutaneous Melanoma, Cutaneous Squamous Cell Carcinoma, Cutaneous Melanoma with Brain/CNS Metastasis, Uveal Melanoma, Acral Melanoma, Mucosal Melanoma, Basal Cell Carcinoma, Merkel Cell Carcinoma. Match the most specific applicable type.",
    AttributeType.TRIAL_NAME: "Extract the official trial protocol name (e.g. 'KEYNOTE-716', 'COMBI-AD', 'CheckMate 238'). Return the name token only — no surrounding words like 'the', 'study', 'trial', or NCT numbers. Return 'No Name' if no formal protocol name exists.",
    AttributeType.NUMBER_OF_PATIENTS: "Extract the number of patients for this specific treatment arm. Look for 'N=', 'n=', 'patients', 'pts', 'enrolled'. For multi-arm studies, extract only the value for this arm. The value should be an integer.",
    # Abstract-level metadata
    AttributeType.ABSTRACT_NUMBER: "Extract abstract number. Look for '### Abstract ID: [NUMBER]'. Return the number only.",
    # Publication-level metadata
    AttributeType.PUBLICATION_NAME: "Extract the journal name from citations (e.g., 'N Engl J Med 2010;363:711-23' → 'N Engl J Med').",
    AttributeType.PUBLICATION_YEAR: "Extract the 4-digit publication year from citations or publication dates (e.g., 'N Engl J Med 2010;363:711-23' → '2010').",
    # Efficacy - Response Rates
    AttributeType.OBJECTIVE_RESPONSE_RATE: "Extract ORR percentage. Look for 'Objective response rate', 'ORR'. If not given, calculate: (CR + PR) / Total Patients.",
    AttributeType.COMPLETE_RESPONSE: "Extract Complete Response percentage. Look for 'Complete Response', 'CR'.",
    AttributeType.PATHOLOGICAL_COMPLETE_RESPONSE: "Extract Pathological Complete Response percentage. Look for 'pCR', 'pathological CR'.",
    AttributeType.COMPLETE_METABOLIC_RESPONSE: "Extract Complete Metabolic Response percentage. Look for 'CMR', 'metabolic response'.",
    AttributeType.DISEASE_CONTROL_RATE: "Extract Disease Control Rate percentage. Look for 'DCR', 'disease control'. If not given, calculate: (CR + PR + SD) / Total Patients.",
    AttributeType.CLINICAL_BENEFIT_RATE: "Extract Clinical Benefit Rate percentage. Look for 'CBR', 'clinical benefit'.",
    AttributeType.MEDIAN_DOR: "Extract median Duration of Response in months. Look for 'DOR', 'duration of response'. Return a number or 'NR'.",
    AttributeType.DOR_RATE: "Extract DOR rate percentage at specific timepoints. Look for 'DOR rate', 'duration rate'.",
    # Efficacy - Survival Metrics (PFS Family)
    AttributeType.MEDIAN_PFS: "Extract median PFS in months. Return a number or 'NR'.",
    AttributeType.MEDIAN_FOLLOWUP_PFS: "Extract median follow-up time for PFS in months.",
    AttributeType.P_VALUE_PFS: "Extract p-value for PFS. Return a decimal number or significance level: Non-Significant (p>0.05), Significant (p≤0.05), Highly Significant (p≤0.001).",
    AttributeType.HR_PFS: "Extract Hazard Ratio for PFS. Return a decimal number (e.g., '0.65').",
    # OS Family
    AttributeType.MEDIAN_OS: (
        "Extract median OS in months for this specific treatment arm. "
        "Look for 'median OS', 'mOS', 'median overall survival'. "
        "In results text, the pattern is: 'median overall survival in the [arm] group was X months'. "
        "Return a number or 'NR'."
    ),
    AttributeType.MEDIAN_FOLLOWUP_OS: "Extract median follow-up time for OS in months. Look for 'follow-up for OS', 'OS follow-up'.",
    AttributeType.P_VALUE_OS: "Extract p-value for OS. Return a decimal number or significance level: Non-Significant (p>0.05), Significant (p≤0.05), Highly Significant (p≤0.001).",
    AttributeType.HR_OS: "Extract Hazard Ratio for OS. Look for 'HR for OS', 'OS HR'. Return a decimal number.",
    # PFS Rate Timepoints
    AttributeType.PFS_RATE_6M: "Extract 6-month PFS rate percentage. Look for '6-month PFS', 'PFS at 6 months', 'Month 6' / '6 mo' in PFS table.",
    AttributeType.PFS_RATE_9M: "Extract 9-month PFS rate percentage. Look for '9-month PFS', 'PFS at 9 months'.",
    AttributeType.PFS_RATE_12M: "Extract 12-month (1-year) PFS rate percentage. Look for '12-month PFS', '1-year PFS', 'Year 1' in PFS table.",
    AttributeType.PFS_RATE_18M: "Extract 18-month PFS rate percentage. Look for '18-month PFS', 'PFS at 18 months'.",
    AttributeType.PFS_RATE_24M: "Extract 24-month (2-year) PFS rate percentage. Look for '24-month PFS', '2-year PFS', 'Year 2' in PFS table.",
    AttributeType.PFS_RATE_36M: "Extract 36-month (3-year) PFS rate percentage. Look for '36-month PFS', '3-year PFS', 'Year 3' in PFS table.",
    AttributeType.PFS_RATE_48M: "Extract 48-month (4-year) PFS rate percentage. Look for '48-month PFS', '4-year PFS', 'Year 4' in PFS table.",
    # OS Rate Timepoints
    AttributeType.OS_RATE_6M: "Extract 6-month OS rate percentage. Look for '6-month OS', 'OS at 6 months', 'Month 6' / '6 mo' in OS table.",
    AttributeType.OS_RATE_9M: "Extract 9-month OS rate percentage. Look for '9-month OS', 'OS at 9 months'.",
    AttributeType.OS_RATE_12M: "Extract 12-month (1-year) OS rate percentage. Look for '12-month OS', '1-year OS', 'Year 1' in OS table.",
    AttributeType.OS_RATE_18M: "Extract 18-month OS rate percentage. Look for '18-month OS', 'OS at 18 months'.",
    AttributeType.OS_RATE_24M: "Extract 24-month (2-year) OS rate percentage. Look for '24-month OS', '2-year OS', 'Year 2' in OS table.",
    AttributeType.OS_RATE_36M: "Extract 36-month (3-year) OS rate percentage. Look for '36-month OS', '3-year OS', '3 yr' in OS table.",
    AttributeType.OS_RATE_48M: "Extract 48-month (4-year) OS rate percentage. Look for '48-month OS', '4-year OS', 'Year 4' in OS table.",
    # EFS Family (Event-Free Survival)
    AttributeType.EFS: "Extract median EFS (event-free survival) in months. Return a number or 'NR'.",
    AttributeType.P_VALUE_EFS: "Extract p-value for EFS. Return a decimal number or significance level: Non-Significant (p>0.05), Significant (p≤0.05), Highly Significant (p≤0.001).",
    AttributeType.HR_EFS: "Extract Hazard Ratio for EFS. Look for 'HR for EFS', 'EFS HR'. Return a decimal number.",
    # RFS Family (Recurrence-Free Survival / Relapse-Free Survival)
    AttributeType.RFS: "Extract median RFS (recurrence-free or relapse-free survival) in months. Return a number or 'NR'.",
    AttributeType.P_VALUE_RFS: "Extract p-value for RFS. Return a decimal number or significance level: Non-Significant (p>0.05), Significant (p≤0.05), Highly Significant (p≤0.001).",
    AttributeType.LENGTH_RFS: "Extract follow-up duration for RFS in months. Look for 'follow-up for RFS', 'RFS follow-up'.",
    AttributeType.HR_RFS: "Extract Hazard Ratio for RFS. Look for 'HR for RFS', 'RFS HR'. Return a decimal number.",
    # MFS Family (Metastasis-Free Survival)
    AttributeType.MFS: "Extract median MFS (metastasis-free survival) in months. Return a number or 'NR'.",
    AttributeType.LENGTH_MFS: "Extract follow-up duration for MFS in months. Look for 'follow-up for MFS', 'MFS follow-up'.",
    AttributeType.HR_MFS: "Extract Hazard Ratio for MFS. Look for 'HR for MFS', 'MFS HR'. Return a decimal number.",
    # Time-to Metrics
    AttributeType.TTR: "Extract median Time to Response in months. Look for 'median TTR', 'time to response'. Return a number or 'NR'.",
    AttributeType.TTP: "Extract median Time to Progression in months. Look for 'median TTP', 'time to progression'. Return a number or 'NR'.",
    AttributeType.TTNT: "Extract median Time to Next Treatment in months. Look for 'median TTNT', 'time to next treatment'. Return a number or 'NR'.",
    AttributeType.TTF: "Extract median Time to Treatment Failure in months. Look for 'median TTF', 'time to treatment failure'. Return a number or 'NR'.",
    # Safety - Adverse Events
    AttributeType.AE: "Extract overall Adverse Events percentage. Look for 'adverse events', 'AEs', 'any grade AE'.",
    AttributeType.GRADE_3_PLUS_AE: "Extract Grade 3+ AE percentage. Look for 'Grade 3+', 'Grade 3 or higher'. If not given, sum Grade 3 + Grade 4 + Grade 5.",
    AttributeType.AE_LEADING_TO_DISCONTINUATION: "Extract AE-leading-to-discontinuation percentage. Look for 'discontinuation due to AE', 'AE leading to discontinuation'. Return the overall study rate; ignore induction-phase or maintenance-phase rates if an overall rate is also reported. Map 'no treatment discontinuation' → '0'.",
    AttributeType.SERIOUS_AE: "Extract Serious AE percentage. Look for 'serious adverse events', 'SAE'.",
    AttributeType.IMMUNE_RELATED_AE: "Extract Immune-Related AE percentage. Look for 'immune related AE', 'irAE'.",
    AttributeType.SERIOUS_IMMUNE_RELATED_AE: "Extract Serious Immune-Related AE percentage. Look for 'serious irAE', 'serious immune related AE'.",
    AttributeType.AE_LEADING_TO_DEATH: "Extract AE-leading-to-death percentage. Look for 'AE leading to death', 'fatal AE'.",
    # Safety - Treatment-Emergent Adverse Events (TEAE)
    AttributeType.TEAE: "Extract Treatment-Emergent AE percentage. Look for 'treatment-emergent adverse events', 'TEAE'.",
    AttributeType.GRADE_3_PLUS_TEAE: "Extract Grade 3+ TEAE percentage. Look for 'Grade 3+ TEAE', 'Grade 3 or higher TEAE'. If not given, sum Grade 3 + Grade 4 + Grade 5 TEAE.",
    AttributeType.GRADE_3_TEAE: "Extract Grade 3 TEAE percentage. Look for 'Grade 3 TEAE', 'Grade 3 treatment-emergent'.",
    AttributeType.GRADE_4_TEAE: "Extract Grade 4 TEAE percentage. Look for 'Grade 4 TEAE', 'Grade 4 treatment-emergent'.",
    AttributeType.GRADE_5_TEAE: "Extract Grade 5 TEAE percentage. Look for 'Grade 5 TEAE', 'Grade 5 treatment-emergent'.",
    AttributeType.TEAE_LEADING_TO_DISCONTINUATION: "Extract TEAE-leading-to-discontinuation percentage. Look for 'TEAE leading to discontinuation', 'discontinuation due to TEAE'. Map 'no treatment discontinuation' → '0'.",
    AttributeType.TEAE_LEADING_TO_DEATH: "Extract TEAE-leading-to-death percentage. Look for 'TEAE leading to death', 'fatal TEAE'.",
    AttributeType.SERIOUS_TEAE: "Extract Serious TEAE percentage. Look for 'serious TEAE', 'serious treatment-emergent'.",
    AttributeType.TEAE_IMMUNE_RELATED: "Extract TEAE Immune-Related percentage. Look for 'TEAE immune related', 'irTEAE'.",
    # Safety - Treatment-Related Adverse Events (TRAE)
    AttributeType.TRAE: "Extract Treatment-Related AE percentage. Look for 'treatment-related adverse events', 'TRAE'.",
    AttributeType.GRADE_3_PLUS_TRAE: "Extract Grade 3+ TRAE percentage. Look for 'Grade 3+ TRAE', 'Grade 3 or higher TRAE'. If not given, sum Grade 3 + Grade 4 + Grade 5 TRAE.",
    AttributeType.GRADE_3_TRAE: "Extract Grade 3 TRAE percentage. Look for 'Grade 3 TRAE', 'Grade 3 treatment-related'.",
    AttributeType.GRADE_4_TRAE: "Extract Grade 4 TRAE percentage. Look for 'Grade 4 TRAE', 'Grade 4 treatment-related'.",
    AttributeType.GRADE_5_TRAE: "Extract Grade 5 TRAE percentage. Look for 'Grade 5 TRAE', 'Grade 5 treatment-related'.",
    AttributeType.TRAE_LEADING_TO_DISCONTINUATION: "Extract TRAE-leading-to-discontinuation percentage. Look for 'TRAE leading to discontinuation', 'discontinuation due to TRAE'. Map 'no treatment discontinuation' → '0'.",
    AttributeType.TRAE_LEADING_TO_DEATH: "Extract TRAE-leading-to-death percentage. Look for 'TRAE leading to death', 'fatal TRAE'.",
    AttributeType.SERIOUS_TRAE: "Extract Serious TRAE percentage. Look for 'serious TRAE', 'serious treatment-related'.",
    AttributeType.TRAE_IMMUNE_RELATED: "Extract TRAE Immune-Related percentage. Look for 'TRAE immune related', 'irTRAE'.",
    # Safety - Specific Adverse Events
    AttributeType.CRS: "Extract Cytokine Release Syndrome percentage. Look for 'CRS', 'cytokine release syndrome'.",
    # Safety - Grade 3+ AE (General / Any Cause)
    # G3+G4+G5 summing and "return %, not count" are covered by SHARED_EXTRACTION_RULES.
    AttributeType.GRADE_3_PLUS_AE_CRS: "Extract Grade 3+ CRS percentage for this arm. Look for 'Grade 3-4 CRS', 'G3+ CRS'.",
    AttributeType.GRADE_3_PLUS_AE_THROMBOCYTOPENIA: "Extract Grade 3+ thrombocytopenia percentage for this arm. Look for 'Grade 3-4 thrombocytopenia', 'G3+ thrombocytopenia'.",
    AttributeType.GRADE_3_PLUS_AE_NEUTROPENIA: "Extract Grade 3+ neutropenia percentage for this arm. Look for 'Grade 3-4 neutropenia', 'G3+ neutropenia'.",
    AttributeType.GRADE_3_PLUS_AE_LEUKOPENIA: "Extract Grade 3+ leukopenia percentage for this arm. Look for 'Grade 3-4 leukopenia', 'G3+ leukopenia'.",
    AttributeType.GRADE_3_PLUS_AE_NAUSEA: "Extract Grade 3+ nausea percentage for this arm. Look for 'Grade 3-4 nausea', 'G3+ nausea'.",
    AttributeType.GRADE_3_PLUS_AE_ANEMIA: "Extract Grade 3+ anemia percentage for this arm. Look for 'Grade 3-4 anemia', 'G3+ anemia', 'anaemia'.",
    AttributeType.GRADE_3_PLUS_AE_DIARRHEA: "Extract Grade 3+ diarrhea percentage for this arm. Look for 'Grade 3-4 diarrhea', 'G3+ diarrhea', 'diarrhoea'.",
    AttributeType.GRADE_3_PLUS_AE_COLITIS: "Extract Grade 3+ colitis percentage for this arm. Look for 'Grade 3-4 colitis', 'G3+ colitis', 'immune-related colitis'.",
    AttributeType.GRADE_3_PLUS_AE_HYPERGLYCEMIA: "Extract Grade 3+ hyperglycemia percentage for this arm. Look for 'Grade 3-4 hyperglycemia', 'G3+ hyperglycemia', 'hyperglycaemia'.",
    AttributeType.GRADE_3_PLUS_AE_NEUTROPHIL_COUNT_DECREASED: "Extract Grade 3+ neutrophil count decreased percentage for this arm. Look for 'Grade 3-4 neutrophil count decreased', 'G3+ neutrophil count decreased'.",
    AttributeType.GRADE_3_PLUS_AE_DYSPNEA: "Extract Grade 3+ dyspnea percentage for this arm. Look for 'Grade 3-4 dyspnea', 'G3+ dyspnea', 'dyspnoea'.",
    AttributeType.GRADE_3_PLUS_AE_PYREXIA: "Extract Grade 3+ pyrexia percentage for this arm. Look for 'Grade 3-4 pyrexia', 'G3+ pyrexia', 'fever'.",
    AttributeType.GRADE_3_PLUS_AE_BLEEDING: "Extract Grade 3+ bleeding percentage for this arm. Look for 'Grade 3-4 bleeding', 'G3+ bleeding', 'hemorrhage', 'haemorrhage'.",
    AttributeType.GRADE_3_PLUS_AE_PRURITUS: "Extract Grade 3+ pruritus percentage for this arm. Look for 'Grade 3-4 pruritus', 'G3+ pruritus'.",
    AttributeType.GRADE_3_PLUS_AE_RASH: "Extract Grade 3+ rash percentage for this arm. Look for 'Grade 3-4 rash', 'G3+ rash'.",
    AttributeType.GRADE_3_PLUS_AE_PNEUMONIA: "Extract Grade 3+ pneumonia percentage for this arm. Look for 'Grade 3-4 pneumonia', 'G3+ pneumonia'.",
    AttributeType.GRADE_3_PLUS_AE_THYROIDITIS: "Extract Grade 3+ thyroiditis percentage for this arm. Look for 'Grade 3-4 thyroiditis', 'G3+ thyroiditis'.",
    AttributeType.GRADE_3_PLUS_AE_HYPOPHYSITIS: "Extract Grade 3+ hypophysitis percentage for this arm. Look for 'Grade 3-4 hypophysitis', 'G3+ hypophysitis'.",
    AttributeType.GRADE_3_PLUS_AE_HEPATITIS: "Extract Grade 3+ hepatitis percentage for this arm. Look for 'Grade 3-4 hepatitis', 'G3+ hepatitis'.",
    AttributeType.GRADE_3_PLUS_AE_PNEUMONITIS: "Extract Grade 3+ pneumonitis percentage for this arm. Look for 'Grade 3-4 pneumonitis', 'G3+ pneumonitis', 'ILD'.",
    AttributeType.GRADE_3_PLUS_AE_ALANINE_AMINOTRANSFERASE: "Extract Grade 3+ ALT (alanine aminotransferase) increased percentage for this arm. Look for 'Grade 3-4 ALT increased', 'G3+ ALT', 'increase in alanine aminotransferase'.",
    AttributeType.GRADE_3_PLUS_AE_IMMUNE_RELATED: "Extract Grade 3+ immune-related AE percentage for this arm. Look for 'Grade 3-4 irAE', 'G3+ immune-related', 'any immune-related event' in the Grade 3/4 columns.",
    # Safety - Grade 3+ TRAE (Treatment-Related)
    # All prompts include 'drug-related' synonym and strict empty-string return.
    # G3+G4+G5 summing is covered by SHARED_EXTRACTION_RULES.
    AttributeType.GRADE_3_PLUS_TRAE_IMMUNE_RELATED: "Extract Grade 3+ TRAE immune-related percentage. Look for 'Grade 3+ TRAE immune-related', 'Grade 3-4 drug-related immune-related', 'Grade 3+ irTRAE'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TRAE_CRS: "Extract Grade 3+ TRAE CRS percentage. Look for 'Grade 3+ TRAE CRS', 'Grade 3-4 TRAE CRS', 'Grade 3-4 drug-related CRS'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TRAE_THROMBOCYTOPENIA: "Extract Grade 3+ TRAE thrombocytopenia percentage. Look for 'Grade 3+ TRAE thrombocytopenia', 'Grade 3-4 drug-related thrombocytopenia'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TRAE_NEUTROPENIA: "Extract Grade 3+ TRAE neutropenia percentage. Look for 'Grade 3+ TRAE neutropenia', 'Grade 3-4 drug-related neutropenia'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TRAE_LEUKOPENIA: "Extract Grade 3+ TRAE leukopenia percentage. Look for 'Grade 3+ TRAE leukopenia', 'Grade 3-4 drug-related leukopenia'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TRAE_NAUSEA: "Extract Grade 3+ TRAE nausea percentage. Look for 'Grade 3+ TRAE nausea', 'Grade 3-4 drug-related nausea'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TRAE_ANEMIA: "Extract Grade 3+ TRAE anemia percentage. Look for 'Grade 3+ TRAE anemia', 'Grade 3-4 drug-related anemia', 'anaemia'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TRAE_DIARRHEA: "Extract Grade 3+ TRAE diarrhea percentage. Look for 'Grade 3+ TRAE diarrhea', 'Grade 3-4 drug-related diarrhea', 'diarrhoea'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TRAE_COLITIS: "Extract Grade 3+ TRAE colitis percentage. Look for 'Grade 3+ TRAE colitis', 'Grade 3-4 TRAE colitis', 'Grade 3-4 drug-related colitis'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TRAE_HYPERGLYCEMIA: "Extract Grade 3+ TRAE hyperglycemia percentage. Look for 'Grade 3+ TRAE hyperglycemia', 'Grade 3-4 drug-related hyperglycemia', 'hyperglycaemia'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TRAE_NEUTROPHIL_COUNT_DECREASED: "Extract Grade 3+ TRAE neutrophil count decreased percentage. Look for 'Grade 3+ TRAE neutrophil count decreased', 'Grade 3-4 drug-related neutrophil count decreased'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TRAE_DYSPNEA: "Extract Grade 3+ TRAE dyspnea percentage. Look for 'Grade 3+ TRAE dyspnea', 'Grade 3-4 drug-related dyspnea', 'dyspnoea'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TRAE_PYREXIA: "Extract Grade 3+ TRAE pyrexia percentage. Look for 'Grade 3+ TRAE pyrexia', 'Grade 3-4 drug-related pyrexia', 'fever'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TRAE_BLEEDING: "Extract Grade 3+ TRAE bleeding percentage. Look for 'Grade 3+ TRAE bleeding', 'Grade 3-4 drug-related bleeding', 'hemorrhage'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TRAE_PRURITUS: "Extract Grade 3+ TRAE pruritus percentage. Look for 'Grade 3+ TRAE pruritus', 'Grade 3-4 drug-related pruritus'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TRAE_RASH: "Extract Grade 3+ TRAE rash percentage. Look for 'Grade 3+ TRAE rash', 'Grade 3-4 drug-related rash'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TRAE_PNEUMONIA: "Extract Grade 3+ TRAE pneumonia percentage. Look for 'Grade 3+ TRAE pneumonia', 'Grade 3-4 drug-related pneumonia'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TRAE_THYROIDITIS: "Extract Grade 3+ TRAE thyroiditis percentage. Look for 'Grade 3+ TRAE thyroiditis', 'Grade 3-4 drug-related thyroiditis'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TRAE_HYPOPHYSITIS: "Extract Grade 3+ TRAE hypophysitis percentage. Look for 'Grade 3+ TRAE hypophysitis', 'Grade 3-4 drug-related hypophysitis'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TRAE_HEPATITIS: "Extract Grade 3+ TRAE hepatitis percentage. Look for 'Grade 3+ TRAE hepatitis', 'Grade 3-4 TRAE hepatitis', 'Grade 3-4 drug-related hepatitis'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TRAE_PNEUMONITIS: "Extract Grade 3+ TRAE pneumonitis percentage. Look for 'Grade 3+ TRAE pneumonitis', 'Grade 3-4 drug-related pneumonitis', 'TRAE ILD'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TRAE_ALANINE_AMINOTRANSFERASE: "Extract Grade 3+ TRAE ALT (alanine aminotransferase) increased percentage. Look for 'Grade 3+ TRAE ALT', 'Grade 3-4 drug-related ALT increased', 'G3+ TRAE ALT'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TRAE_HYPOTHYROIDISM: "Extract Grade 3+ TRAE hypothyroidism percentage. Look for 'Grade 3+ TRAE hypothyroidism', 'Grade 3-4 drug-related hypothyroidism'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TRAE_HYPERTHYROIDISM: "Extract Grade 3+ TRAE hyperthyroidism percentage. Look for 'Grade 3+ TRAE hyperthyroidism', 'Grade 3-4 drug-related hyperthyroidism'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TRAE_AST_INCREASED: "Extract Grade 3+ TRAE AST (aspartate aminotransferase) increased percentage. Look for 'Grade 3+ TRAE AST', 'Grade 3-4 drug-related AST increased', 'G3+ TRAE AST'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TRAE_VOMITING: "Extract Grade 3+ TRAE vomiting percentage. Look for 'Grade 3+ TRAE vomiting', 'Grade 3-4 drug-related vomiting'. If none of these phrases appear in the context, return empty string.",
    # Safety - Grade 3+ TEAE (Treatment-Emergent / All Causality)
    # All prompts have strict empty-string return. G3+G4+G5 summing via SHARED_EXTRACTION_RULES.
    AttributeType.GRADE_3_PLUS_TEAE_IMMUNE_RELATED: "Extract Grade 3+ TEAE immune-related percentage. Look for 'Grade 3+ TEAE immune-related', 'Grade 3-4 TEAE immune-related', 'Grade 3+ irTEAE'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TEAE_CRS: "Extract Grade 3+ TEAE CRS percentage. Look for 'Grade 3+ TEAE CRS', 'Grade 3-4 TEAE CRS'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TEAE_THROMBOCYTOPENIA: "Extract Grade 3+ TEAE thrombocytopenia percentage. Look for 'Grade 3+ TEAE thrombocytopenia', 'Grade 3-4 TEAE thrombocytopenia'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TEAE_NEUTROPENIA: "Extract Grade 3+ TEAE neutropenia percentage. Look for 'Grade 3+ TEAE neutropenia', 'Grade 3-4 TEAE neutropenia'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TEAE_LEUKOPENIA: "Extract Grade 3+ TEAE leukopenia percentage. Look for 'Grade 3+ TEAE leukopenia', 'Grade 3-4 TEAE leukopenia'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TEAE_NAUSEA: "Extract Grade 3+ TEAE nausea percentage. Look for 'Grade 3+ TEAE nausea', 'Grade 3-4 TEAE nausea'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TEAE_ANEMIA: "Extract Grade 3+ TEAE anemia percentage. Look for 'Grade 3+ TEAE anemia', 'Grade 3-4 TEAE anemia', 'anaemia'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TEAE_DIARRHEA: "Extract Grade 3+ TEAE diarrhea percentage. Look for 'Grade 3+ TEAE diarrhea', 'Grade 3-4 TEAE diarrhea', 'diarrhoea'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TEAE_COLITIS: "Extract Grade 3+ TEAE colitis percentage. Look for 'Grade 3+ TEAE colitis', 'Grade 3-4 TEAE colitis'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TEAE_HYPERGLYCEMIA: "Extract Grade 3+ TEAE hyperglycemia percentage. Look for 'Grade 3+ TEAE hyperglycemia', 'Grade 3-4 TEAE hyperglycemia', 'hyperglycaemia'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TEAE_NEUTROPHIL_COUNT_DECREASED: "Extract Grade 3+ TEAE neutrophil count decreased percentage. Look for 'Grade 3+ TEAE neutrophil count decreased', 'Grade 3-4 TEAE neutrophil count decreased'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TEAE_DYSPNEA: "Extract Grade 3+ TEAE dyspnea percentage. Look for 'Grade 3+ TEAE dyspnea', 'Grade 3-4 TEAE dyspnea', 'dyspnoea'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TEAE_PYREXIA: "Extract Grade 3+ TEAE pyrexia percentage. Look for 'Grade 3+ TEAE pyrexia', 'Grade 3-4 TEAE pyrexia', 'fever'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TEAE_BLEEDING: "Extract Grade 3+ TEAE bleeding percentage. Look for 'Grade 3+ TEAE bleeding', 'Grade 3-4 TEAE bleeding', 'hemorrhage'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TEAE_PRURITUS: "Extract Grade 3+ TEAE pruritus percentage. Look for 'Grade 3+ TEAE pruritus', 'Grade 3-4 TEAE pruritus'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TEAE_RASH: "Extract Grade 3+ TEAE rash percentage. Look for 'Grade 3+ TEAE rash', 'Grade 3-4 TEAE rash'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TEAE_PNEUMONIA: "Extract Grade 3+ TEAE pneumonia percentage. Look for 'Grade 3+ TEAE pneumonia', 'Grade 3-4 TEAE pneumonia'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TEAE_THYROIDITIS: "Extract Grade 3+ TEAE thyroiditis percentage. Look for 'Grade 3+ TEAE thyroiditis', 'Grade 3-4 TEAE thyroiditis'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TEAE_HYPOPHYSITIS: "Extract Grade 3+ TEAE hypophysitis percentage. Look for 'Grade 3+ TEAE hypophysitis', 'Grade 3-4 TEAE hypophysitis'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TEAE_HEPATITIS: "Extract Grade 3+ TEAE hepatitis percentage. Look for 'Grade 3+ TEAE hepatitis', 'Grade 3-4 TEAE hepatitis'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TEAE_PNEUMONITIS: "Extract Grade 3+ TEAE pneumonitis percentage. Look for 'Grade 3+ TEAE pneumonitis', 'Grade 3-4 TEAE pneumonitis', 'TEAE ILD'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TEAE_ALANINE_AMINOTRANSFERASE: "Extract Grade 3+ TEAE ALT (alanine aminotransferase) increased percentage. Look for 'Grade 3+ TEAE ALT', 'Grade 3-4 TEAE ALT increased'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TEAE_HYPOTHYROIDISM: "Extract Grade 3+ TEAE hypothyroidism percentage. Look for 'Grade 3+ TEAE hypothyroidism', 'Grade 3-4 TEAE hypothyroidism'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TEAE_HYPERTHYROIDISM: "Extract Grade 3+ TEAE hyperthyroidism percentage. Look for 'Grade 3+ TEAE hyperthyroidism', 'Grade 3-4 TEAE hyperthyroidism'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TEAE_AST_INCREASED: "Extract Grade 3+ TEAE AST (aspartate aminotransferase) increased percentage. Look for 'Grade 3+ TEAE AST', 'Grade 3-4 TEAE AST increased'. If none of these phrases appear in the context, return empty string.",
    AttributeType.GRADE_3_PLUS_TEAE_VOMITING: "Extract Grade 3+ TEAE vomiting percentage. Look for 'Grade 3+ TEAE vomiting', 'Grade 3-4 TEAE vomiting'. If none of these phrases appear in the context, return empty string.",
    # Efficacy - 95% Confidence Intervals for Hazard Ratios
    AttributeType.CI_HR_PFS: "Extract the 95% CI for the PFS hazard ratio. Look for '95% CI' near HR PFS values. Return 'lower-upper' format (e.g., '0.54-0.89').",
    AttributeType.CI_HR_OS: "Extract the 95% CI for the OS hazard ratio. Look for '95% CI' near HR OS values. Return 'lower-upper' format (e.g., '0.59-0.87').",
    AttributeType.CI_HR_EFS: "Extract the 95% CI for the EFS hazard ratio. Look for '95% CI' near HR EFS values. Return 'lower-upper' format (e.g., '0.54-0.89').",
    AttributeType.CI_HR_RFS: "Extract the 95% CI for the RFS hazard ratio. Look for '95% CI' near HR RFS values. Return 'lower-upper' format (e.g., '0.54-0.89').",
    AttributeType.CI_HR_MFS: "Extract the 95% CI for the MFS hazard ratio. Look for '95% CI' near HR MFS values. Return 'lower-upper' format (e.g., '0.54-0.89').",
    AttributeType.HR_TTP: "Extract Hazard Ratio for TTP. Look for 'HR for TTP', 'TTP HR'. Return a decimal number.",
    AttributeType.CI_HR_TTP: "Extract the 95% CI for the TTP hazard ratio. Look for '95% CI' near HR TTP values. Return 'lower-upper' format (e.g., '0.54-0.89').",
    # Safety - Dose reduction, interruption, hospitalization (AE)
    AttributeType.AE_LEADING_TO_DOSE_REDUCTION: "Extract AE-leading-to-dose-reduction percentage. Look for 'dose reduction', 'AE leading to dose reduction', 'dose modifications due to AE'.",
    AttributeType.AE_LEADING_TO_DOSE_INTERRUPTION: "Extract AE-leading-to-dose-interruption percentage. Look for 'dose interruption', 'dose delay', 'AE leading to dose interruption'.",
    AttributeType.AE_REQUIRING_HOSPITALIZATION: "Extract AE-requiring-hospitalization percentage. Look for 'hospitalization', 'AE requiring hospitalization'.",
    # Safety - IRR (Infusion-Related Reaction)
    AttributeType.IRR: "Extract Infusion-Related Reaction (IRR) percentage. Look for 'infusion-related reaction', 'IRR', 'infusion reaction'.",
    # Safety - Dose reduction, interruption, hospitalization (TEAE)
    AttributeType.TEAE_LEADING_TO_DOSE_REDUCTION: "Extract TEAE-leading-to-dose-reduction percentage. Look for 'TEAE dose reduction', 'dose reduction due to TEAE'.",
    AttributeType.TEAE_LEADING_TO_DOSE_INTERRUPTION: "Extract TEAE-leading-to-dose-interruption percentage. Look for 'TEAE dose interruption', 'dose interruption due to TEAE'.",
    AttributeType.TEAE_REQUIRING_HOSPITALIZATION: "Extract TEAE-requiring-hospitalization percentage. Look for 'TEAE requiring hospitalization', 'TEAE-related hospitalization'.",
    # Safety - Dose reduction, interruption, hospitalization (TRAE)
    AttributeType.TRAE_LEADING_TO_DOSE_REDUCTION: "Extract TRAE-leading-to-dose-reduction percentage. Look for 'TRAE dose reduction', 'dose reduction due to TRAE'.",
    AttributeType.TRAE_LEADING_TO_DOSE_INTERRUPTION: "Extract TRAE-leading-to-dose-interruption percentage. Look for 'TRAE dose interruption', 'dose interruption due to TRAE'.",
    AttributeType.TRAE_REQUIRING_HOSPITALIZATION: "Extract TRAE-requiring-hospitalization percentage. Look for 'TRAE requiring hospitalization', 'TRAE-related hospitalization'.",
    # Safety - Grade 3+ IRR and Fatigue (AE)
    AttributeType.GRADE_3_PLUS_AE_IRR: "Extract Grade 3+ AE IRR (infusion-related reaction) percentage. Look for 'Grade 3+ AE IRR', 'Grade 3-4 IRR', 'G3+ infusion reaction'.",
    AttributeType.GRADE_3_PLUS_AE_FATIGUE: "Extract Grade 3+ AE fatigue percentage. Look for 'Grade 3+ AE fatigue', 'Grade 3-4 fatigue', 'G3+ fatigue'.",
    # Safety - Grade 3+ IRR and Fatigue (TRAE)
    AttributeType.GRADE_3_PLUS_TRAE_IRR: "Extract Grade 3+ TRAE IRR (infusion-related reaction) percentage. Look for 'Grade 3+ TRAE IRR', 'Grade 3-4 TRAE IRR', 'G3+ TRAE infusion reaction'.",
    AttributeType.GRADE_3_PLUS_TRAE_FATIGUE: "Extract Grade 3+ TRAE fatigue percentage. Look for 'Grade 3+ TRAE fatigue', 'Grade 3-4 TRAE fatigue', 'G3+ TRAE fatigue'.",
    # Safety - Grade 3+ IRR and Fatigue (TEAE)
    AttributeType.GRADE_3_PLUS_TEAE_IRR: "Extract Grade 3+ TEAE IRR (infusion-related reaction) percentage. Look for 'Grade 3+ TEAE IRR', 'Grade 3-4 TEAE IRR', 'G3+ TEAE infusion reaction'.",
    AttributeType.GRADE_3_PLUS_TEAE_FATIGUE: "Extract Grade 3+ TEAE fatigue percentage. Look for 'Grade 3+ TEAE fatigue', 'Grade 3-4 TEAE fatigue', 'G3+ TEAE fatigue'.",
    # Safety - Grade 3+ AE (Hypothyroidism, Hyperthyroidism, AST, Vomiting)
    AttributeType.GRADE_3_PLUS_AE_HYPOTHYROIDISM: "Extract Grade 3+ AE hypothyroidism percentage. Look for 'Grade 3+ AE hypothyroidism', 'Grade 3-4 hypothyroidism', 'G3+ hypothyroidism'.",
    AttributeType.GRADE_3_PLUS_AE_HYPERTHYROIDISM: "Extract Grade 3+ AE hyperthyroidism percentage. Look for 'Grade 3+ AE hyperthyroidism', 'Grade 3-4 hyperthyroidism', 'G3+ hyperthyroidism'.",
    AttributeType.GRADE_3_PLUS_AE_AST_INCREASED: "Extract Grade 3+ AE AST (aspartate aminotransferase) increased percentage. Look for 'Grade 3+ AE AST', 'Grade 3-4 AST increased', 'G3+ AST'.",
    AttributeType.GRADE_3_PLUS_AE_VOMITING: "Extract Grade 3+ AE vomiting percentage. Look for 'Grade 3+ AE vomiting', 'Grade 3-4 vomiting', 'G3+ vomiting'.",
}


# AE / TEAE / TRAE definitions block, reused in all 6 safety-family prompts.
# This text is intentionally inlined inside each AE/TEAE/TRAE family prompt
# (not as a separate constant prepended by the extractor) because the LLM
# must see it adjacent to the attribute list it is being asked to extract.
_AE_DEFINITIONS_BLOCK = (
    "DEFINITIONS — read carefully, these are commonly confused:\n"
    "- AE (Adverse Event): any untoward medical occurrence, regardless of relationship to treatment.\n"
    "- TEAE (Treatment-Emergent AE): an AE that started or worsened after the first study dose.\n"
    "- TRAE (Treatment-Related AE / Drug-Related AE): an AE the investigator judged related to treatment.\n"
    "The denominators differ. Extract values ONLY from rows / columns explicitly labeled with this family's term. "
    'If only "AEs" are reported and you are extracting TRAE, return empty string — do not assume.'
)

_NO_INFERENCE_CLAUSE = (
    "If the value is not explicitly stated for THIS arm, return empty string. "
    "Do not infer from study totals or other arms. Do not compute values."
)

_VALUE_FORMAT_NOTE = (
    "Accepted values per attribute: 'NR' (not reached, where applicable), "
    "'' (empty string when not stated), a decimal number, or a 'lower-upper' range for CIs."
)

_CI_HR_RULE = (
    "CI HR FORMAT: 95% CI for the hazard ratio is a 'low-high' range with TWO decimals "
    "separated by a hyphen (e.g., '0.42-0.64'). The CI is the parenthesized range that "
    "accompanies the HR — e.g., 'HR 0.52 (95% CI 0.42-0.64)' → ci_hr='0.42-0.64', NOT '0.52'. "
    "Never return only one number; if the document gives only the HR with no CI, return ''."
)


# One extraction prompt per AttributeFamily. The {arms_block} placeholder is
# filled by the extractor with the per-arm output schema and arm metadata.
# Convention: prompts do NOT inline SHARED_EXTRACTION_RULES; the extractor
# prepends those formatting rules separately.
FAMILY_PROMPTS: dict[AttributeFamily, str] = {
    AttributeFamily.IDENTIFICATION: (
        "FAMILY: Trial / Publication Identification.\n"
        "Definition: study-level metadata identifying the trial, the cancer setting, "
        "the publication or abstract, and per-arm enrollment counts.\n\n"
        "Attributes to extract (canonical name — expected unit / format):\n"
        "- nct_number — NCT identifier (NCT followed by 8 digits) or other registry id.\n"
        "- cancer_type — one of the controlled cancer-type vocabulary entries.\n"
        "- trial_name — protocol name token (e.g. KEYNOTE-716); 'No Name' if none.\n"
        "- number_of_patients — integer, per arm.\n"
        "- line_of_treatment — trial-level (same value across arms). One of: "
        "first_line, second_line, third_line_plus, adjuvant, neoadjuvant, maintenance, unknown. "
        "Inference rules: 'previously untreated' / 'treatment-naive' / 'first-line' → first_line; "
        "'after one prior systemic therapy' / 'after failure of ≥1 prior therapy' → second_line; "
        "'after ≥2 prior therapies' → third_line_plus; trial designs explicitly labeled "
        "adjuvant / neoadjuvant / maintenance → those values; if unclear → unknown.\n"
        "- abstract_number, conference, published_year — abstract metadata when present.\n"
        "- publication_name, publication_year, pdf_number — publication metadata when present.\n\n"
        "WHERE TO LOOK for publication_name / publication_year: the citation block "
        "immediately below the article title and author list, NOT inside the abstract body. "
        "Common shapes:\n"
        "  - 'N Engl J Med 2015;373:23-34.'  → publication_name='N Engl J Med 2015;373:23-34.', publication_year='2015'\n"
        "  - 'Lancet 2015; 386: 444–51'      → publication_name='Lancet 2015; 386: 444–51', publication_year='2015'\n"
        "Return the full citation string (journal + volume + pages) for publication_name, "
        "preserving the journal's original punctuation and dashes (en-dash or hyphen as printed). "
        "Extract the 4-digit year as publication_year. "
        "YEAR FALLBACK: if the citation string itself does not contain a 4-digit year, "
        "look on the line immediately ABOVE the citation — typically a date stamp such as "
        "'Published Online May 31, 2015' or 'This article was published on May 31, 2015' "
        "— and take the 4-digit year from there. "
        "If no citation block is present (e.g., conference abstract), return '' for both.\n\n"
        f"{_VALUE_FORMAT_NOTE}\n"
        f"{_NO_INFERENCE_CLAUSE}\n\n"
        "EXAMPLE — context says 'KEYNOTE-716 (NCT03553836); pembrolizumab arm n=487, placebo arm n=489; "
        "N Engl J Med 2022.' Output:\n"
        "{\n"
        '  "Pembrolizumab": {"nct_number": "NCT03553836", '
        '"trial_name": "KEYNOTE-716", '
        '"number_of_patients": "487"},\n'
        '  "Placebo": {"nct_number": "NCT03553836", '
        '"trial_name": "KEYNOTE-716", '
        '"number_of_patients": "489"}\n'
        "}\n\n"
        "{arms_block}"
    ),
    AttributeFamily.RESPONSE_RATES: (
        "FAMILY: Tumor response rates (RECIST / iRECIST endpoints).\n"
        "Definition: per-arm response rates derived from investigator or BICR assessment, "
        "including ORR, CR, pCR, CMR, DCR, CBR, and duration of response (DOR).\n\n"
        "Attributes to extract (canonical name — expected unit):\n"
        "- objective_response_rate — percentage.\n"
        "- complete_response — percentage.\n"
        "- pathological_complete_response — percentage.\n"
        "- complete_metabolic_response — percentage.\n"
        "- disease_control_rate — percentage.\n"
        "- clinical_benefit_rate — percentage.\n"
        "- median_dor — months (or 'NR').\n"
        "- dor_rate — percentage at a stated timepoint.\n\n"
        f"{_VALUE_FORMAT_NOTE}\n"
        f"{_NO_INFERENCE_CLAUSE}\n\n"
        "SANCTIONED EXCEPTION (ORR ONLY): If `OBJECTIVE_RESPONSE_RATE` is not explicitly stated "
        "for THIS arm but both `COMPLETE_RESPONSE` (CR) and Partial Response (PR) counts/percentages "
        "ARE explicitly stated for THIS arm, compute `ORR = (CR + PR) / NUMBER_OF_PATIENTS`. "
        "Return percentage to one decimal. Apply ONLY to ORR. "
        "No other attribute may be computed.\n\n"
        "EXAMPLE — 'In the nivolumab arm (n=200), CR was 12 (6.0%) and PR was 48 (24.0%). ORR was not reported.' Output:\n"
        "{\n"
        '  "Nivolumab": {\n'
        '    "complete_response": "6.0",\n'
        '    "objective_response_rate": "30.0"\n'
        "  }\n"
        "}\n\n"
        "{arms_block}"
    ),
    AttributeFamily.PFS_FAMILY: (
        "FAMILY: Progression-Free Survival (PFS).\n"
        "Definition: time from randomization (or treatment start) to disease progression or death "
        "from any cause, plus statistical comparators (HR, p-value, CI) and rate timepoints.\n\n"
        "Attributes (canonical name — unit):\n"
        "- median_pfs — months (or 'NR').\n"
        "- median_followup_pfs — months.\n"
        "- p_value_pfs — decimal, OR significance label "
        "(Non-Significant p>0.05, Significant p<=0.05, Highly Significant p<=0.001).\n"
        "- hr_pfs — decimal hazard ratio.\n"
        "- ci_hr_pfs — 'low-high' range (see CI HR FORMAT below).\n"
        "- pfs_rate_6m / 9m / 12m / 18m / 24m / 36m / 48m — percentage at the stated timepoint.\n\n"
        f"{_VALUE_FORMAT_NOTE}\n"
        f"{_CI_HR_RULE}\n"
        f"{_NO_INFERENCE_CLAUSE}\n\n"
        "EXAMPLE — 'Median PFS was 14.7 months (95% CI 10.2-19.8) vs 5.6 months; HR 0.45 (0.33-0.61), p<0.001. "
        "12-month PFS rate was 56% vs 24%.' Output (per arm):\n"
        "{\n"
        '  "Experimental": {"median_pfs": "14.7", '
        '"hr_pfs": "0.45", '
        '"ci_hr_pfs": "0.33-0.61", '
        '"pfs_rate_12m": "56"},\n'
        '  "Control": {"median_pfs": "5.6", '
        '"pfs_rate_12m": "24"}\n'
        "}\n\n"
        "{arms_block}"
    ),
    AttributeFamily.OS_FAMILY: (
        "FAMILY: Overall Survival (OS).\n"
        "Definition: time from randomization (or treatment start) to death from any cause, "
        "plus statistical comparators (HR, p-value, CI) and rate timepoints.\n\n"
        "Attributes (canonical name — unit):\n"
        "- median_os — months (or 'NR').\n"
        "- median_followup_os — months.\n"
        "- p_value_os — decimal, OR significance label "
        "(Non-Significant p>0.05, Significant p<=0.05, Highly Significant p<=0.001).\n"
        "- hr_os — decimal hazard ratio.\n"
        "- ci_hr_os — 'low-high' range (see CI HR FORMAT below).\n"
        "- os_rate_6m / 9m / 12m / 18m / 24m / 36m / 48m — percentage at the stated timepoint.\n\n"
        f"{_VALUE_FORMAT_NOTE}\n"
        f"{_CI_HR_RULE}\n"
        f"{_NO_INFERENCE_CLAUSE}\n\n"
        "EXAMPLE — 'Median OS in the pembrolizumab group was not reached vs 16.9 months in the chemotherapy "
        "group; HR 0.63 (95% CI 0.50-0.79), p<0.001. 24-month OS was 55% vs 38%.' Output:\n"
        "{\n"
        '  "Pembrolizumab": {"median_os": "NR", '
        '"hr_os": "0.63", '
        '"ci_hr_os": "0.50-0.79", '
        '"os_rate_24m": "55"},\n'
        '  "Chemotherapy": {"median_os": "16.9", '
        '"os_rate_24m": "38"}\n'
        "}\n\n"
        "{arms_block}"
    ),
    AttributeFamily.EFS_RFS_MFS: (
        "FAMILY: Event-Free / Recurrence-Free / Metastasis-Free Survival.\n"
        "Definition:\n"
        "- EFS (Event-Free Survival): time to first event (progression, recurrence, or death) "
        "in neoadjuvant / adjuvant settings.\n"
        "- RFS (Recurrence-Free / Relapse-Free Survival): time from definitive treatment to recurrence or death.\n"
        "- MFS (Metastasis-Free Survival): time from definitive treatment to distant metastasis or death.\n"
        "These three endpoints are distinct — extract each only from rows/sections explicitly using its name.\n\n"
        "Attributes (canonical name — unit):\n"
        "- efs — months (or 'NR'); p_value_efs — decimal or significance label; hr_efs — decimal; "
        "ci_hr_efs — 'low-high' range (see CI HR FORMAT below).\n"
        "- rfs — months; p_value_rfs — decimal or label; length_rfs — months follow-up; "
        "hr_rfs — decimal; ci_hr_rfs — 'low-high' range.\n"
        "- mfs — months; length_mfs — months follow-up; hr_mfs — decimal; ci_hr_mfs — 'low-high' range.\n\n"
        f"{_VALUE_FORMAT_NOTE}\n"
        f"{_CI_HR_RULE}\n"
        f"{_NO_INFERENCE_CLAUSE}\n\n"
        "NON-SUBSTITUTION RULE:\n"
        "EFS, RFS, and MFS are NOT interchangeable with PFS or OS. If the document only reports "
        "PFS and OS — with no row, section, or table label using EFS / RFS / MFS or one of their "
        "full names (event-free survival, recurrence-free survival, relapse-free survival, "
        "metastasis-free survival) — leave ALL fields in this family empty. "
        "Do not substitute a PFS or OS value into any EFS/RFS/MFS field under any circumstance.\n\n"
        "EXAMPLE — 'Median RFS was not reached in the dabrafenib+trametinib arm vs 16.6 months in placebo; "
        "HR 0.47 (95% CI 0.39-0.58).' Output:\n"
        "{\n"
        '  "Dabrafenib+Trametinib": {"rfs": "NR", '
        '"hr_rfs": "0.47", '
        '"ci_hr_rfs": "0.39-0.58"},\n'
        '  "Placebo": {"rfs": "16.6"}\n'
        "}\n\n"
        "{arms_block}"
    ),
    AttributeFamily.TIME_TO_METRICS: (
        "FAMILY: Time-to clinical milestone metrics.\n"
        "Definition: per-arm median times measured from a reference event to a clinical milestone.\n"
        "- TTR: Time to Response (treatment start to first documented response).\n"
        "- TTP: Time to Progression (treatment start to disease progression; deaths censored).\n"
        "- TTNT: Time to Next Treatment.\n"
        "- TTF: Time to Treatment Failure (start to discontinuation for any reason).\n\n"
        "Attributes (canonical name — unit):\n"
        "- ttr — months (or 'NR').\n"
        "- ttp — months (or 'NR'); hr_ttp — decimal; ci_hr_ttp — 'low-high' range (see CI HR FORMAT below).\n"
        "- ttnt — months (or 'NR').\n"
        "- ttf — months (or 'NR').\n\n"
        f"{_VALUE_FORMAT_NOTE}\n"
        f"{_CI_HR_RULE}\n"
        f"{_NO_INFERENCE_CLAUSE}\n\n"
        "EXAMPLE — 'Median time to response was 2.8 months in arm A and 3.1 months in arm B. "
        "Median TTP in arm A was 9.4 months.' Output:\n"
        "{\n"
        '  "Arm A": {"ttr": "2.8", '
        '"ttp": "9.4"},\n'
        '  "Arm B": {"ttr": "3.1"}\n'
        "}\n\n"
        "{arms_block}"
    ),
    AttributeFamily.AE_GENERAL: (
        "FAMILY: Adverse Events — general (any-cause).\n"
        f"{_AE_DEFINITIONS_BLOCK}\n\n"
        "Scope of THIS family: any-cause AE rates only. Use rows/columns labeled 'AE', 'adverse event', "
        "'any grade AE', or equivalent.\n\n"
        "Attributes (canonical name — unit, all percentages unless noted):\n"
        "- ae, grade_3_plus_ae, ae_leading_to_discontinuation, serious_ae, immune_related_ae, "
        "serious_immune_related_ae, ae_leading_to_death, ae_leading_to_dose_reduction, "
        "ae_leading_to_dose_interruption, ae_requiring_hospitalization.\n"
        "- crs (cytokine release syndrome), irr (infusion-related reaction).\n\n"
        f"{_VALUE_FORMAT_NOTE}\n"
        f"{_NO_INFERENCE_CLAUSE}\n\n"
        "EXAMPLE — 'Any-grade AEs occurred in 196/200 (98%) in arm A. Grade 3+ AEs in 80 (40%). "
        "Discontinuations due to AE: 12 (6%).' Output:\n"
        "{\n"
        '  "Arm A": {"ae": "98", '
        '"grade_3_plus_ae": "40", '
        '"ae_leading_to_discontinuation": "6"}\n'
        "}\n\n"
        "{arms_block}"
    ),
    AttributeFamily.AE_GRADE3_SPECIFIC: (
        "FAMILY: Adverse Events — Grade 3+ specific (any-cause), per preferred term.\n"
        f"{_AE_DEFINITIONS_BLOCK}\n\n"
        "Scope of THIS family: Grade 3+ AE rates for specific preferred terms, any-cause. "
        "Use rows from any-cause AE tables only. If only TRAE/TEAE tables are present, return empty string.\n\n"
        "Attributes (all percentages, per arm) — extract for each named preferred term:\n"
        "grade_3_plus_ae_immune_related, _irr, _crs, _colitis, _thrombocytopenia, _neutropenia, "
        "_leukopenia, _fatigue, _nausea, _anemia, _diarrhea, _hyperglycemia, _dyspnea, _pyrexia, "
        "_bleeding, _pruritus, _rash, _pneumonia, _thyroiditis, _hypophysitis, _hepatitis, "
        "_pneumonitis, _alanine_aminotransferase, _hypothyroidism, _hyperthyroidism, _ast_increased, "
        "_vomiting.\n\n"
        f"{_VALUE_FORMAT_NOTE}\n"
        f"{_NO_INFERENCE_CLAUSE}\n\n"
        "EXAMPLE — any-cause AE table: 'Grade 3-4 colitis: arm A 5 (2.5%), arm B 1 (0.5%). "
        "Grade 3-4 ALT increased: arm A 8 (4.0%), arm B 2 (1.0%).' Output:\n"
        "{\n"
        '  "Arm A": {"grade_3_plus_ae_colitis": "2.5", '
        '"grade_3_plus_ae_alanine_aminotransferase": "4.0"},\n'
        '  "Arm B": {"grade_3_plus_ae_colitis": "0.5", '
        '"grade_3_plus_ae_alanine_aminotransferase": "1.0"}\n'
        "}\n\n"
        "{arms_block}"
    ),
    AttributeFamily.TEAE_GENERAL: (
        "FAMILY: Treatment-Emergent Adverse Events (TEAE) — general.\n"
        f"{_AE_DEFINITIONS_BLOCK}\n\n"
        "Scope of THIS family: TEAE rates only. Use rows/columns explicitly labeled 'TEAE' or "
        "'treatment-emergent'. Do NOT use any-cause AE rows or TRAE rows.\n\n"
        "Attributes (canonical name — unit, percentages):\n"
        "- teae, grade_3_plus_teae, grade_3_teae, grade_4_teae, grade_5_teae, "
        "teae_leading_to_discontinuation, teae_leading_to_death, serious_teae, "
        "teae_immune_related, teae_leading_to_dose_reduction, teae_leading_to_dose_interruption, "
        "teae_requiring_hospitalization.\n\n"
        f"{_VALUE_FORMAT_NOTE}\n"
        f"{_NO_INFERENCE_CLAUSE}\n\n"
        "EXAMPLE — 'TEAEs of any grade occurred in 95% of patients in arm A. Grade 3+ TEAEs in 38%. "
        "Serious TEAEs in 22%.' Output:\n"
        "{\n"
        '  "Arm A": {"teae": "95", '
        '"grade_3_plus_teae": "38", '
        '"serious_teae": "22"}\n'
        "}\n\n"
        "{arms_block}"
    ),
    AttributeFamily.TEAE_GRADE3_SPECIFIC: (
        "FAMILY: Treatment-Emergent Adverse Events — Grade 3+ specific, per preferred term.\n"
        f"{_AE_DEFINITIONS_BLOCK}\n\n"
        "Scope of THIS family: Grade 3+ TEAE rates for specific preferred terms. Use rows from TEAE "
        "(treatment-emergent) tables only. If a specific term appears only in any-cause AE tables or "
        "TRAE tables, return empty string for this family.\n\n"
        "Attributes (all percentages, per arm) — for each named preferred term:\n"
        "grade_3_plus_teae_immune_related, _irr, _crs, _colitis, _thrombocytopenia, _neutropenia, "
        "_leukopenia, _fatigue, _nausea, _anemia, _diarrhea, _hyperglycemia, _dyspnea, _pyrexia, "
        "_bleeding, _pruritus, _rash, _pneumonia, _thyroiditis, _hypophysitis, _hepatitis, "
        "_pneumonitis, _alanine_aminotransferase, _hypothyroidism, _hyperthyroidism, _ast_increased, "
        "_vomiting.\n\n"
        f"{_VALUE_FORMAT_NOTE}\n"
        f"{_NO_INFERENCE_CLAUSE}\n\n"
        "EXAMPLE — TEAE table: 'Grade 3-4 TEAE neutropenia: arm A 18 (9.0%), arm B 4 (2.0%).' Output:\n"
        "{\n"
        '  "Arm A": {"grade_3_plus_teae_neutropenia": "9.0"},\n'
        '  "Arm B": {"grade_3_plus_teae_neutropenia": "2.0"}\n'
        "}\n\n"
        "{arms_block}"
    ),
    AttributeFamily.TRAE_GENERAL: (
        "FAMILY: Treatment-Related Adverse Events (TRAE) — general.\n"
        f"{_AE_DEFINITIONS_BLOCK}\n\n"
        "Scope of THIS family: TRAE rates only. Use rows/columns explicitly labeled 'TRAE', "
        "'treatment-related', or 'drug-related'. Do NOT use any-cause AE rows or TEAE rows.\n\n"
        "Attributes (canonical name — unit, percentages):\n"
        "- trae, grade_3_plus_trae, grade_3_trae, grade_4_trae, grade_5_trae, "
        "trae_leading_to_discontinuation, trae_leading_to_death, serious_trae, trae_immune_related, "
        "trae_leading_to_dose_reduction, trae_leading_to_dose_interruption, "
        "trae_requiring_hospitalization.\n\n"
        f"{_VALUE_FORMAT_NOTE}\n"
        f"{_NO_INFERENCE_CLAUSE}\n\n"
        "RELABELING RULE (single-arm studies only):\n"
        "If this is a single-arm Phase 1/1b/2 study AND the methods state 'all AEs were considered "
        "treatment-related' (or equivalent — 'drug-related', 'considered related to study drug'), "
        "treat the document's any-grade AE table as TRAE for this family. This relabeling applies "
        "ONLY when (a) one arm in the arms_block AND (b) such a methods statement exists. "
        "Do NOT relabel for randomized or multi-arm studies.\n\n"
        "POSITIVE EXAMPLE: Single-arm Phase 1b reports 'Grade ≥3 AEs in 14/45 patients' with "
        "methods stating 'All AEs were considered treatment-related.' "
        "→ Extract 14/45 as grade_3_plus_trae.\n\n"
        "NEGATIVE EXAMPLE: Randomized Phase 3 reports 'Grade ≥3 AEs in 142/300 (arm A)' without "
        "a TRAE-specific table. → Leave grade_3_plus_trae empty.\n\n"
        "EXAMPLE — 'Treatment-related AEs of any grade occurred in 78% of arm A. Grade 3+ TRAEs in 25%. "
        "TRAEs leading to discontinuation in 7%.' Output:\n"
        "{\n"
        '  "Arm A": {"trae": "78", '
        '"grade_3_plus_trae": "25", '
        '"trae_leading_to_discontinuation": "7"}\n'
        "}\n\n"
        "{arms_block}"
    ),
    AttributeFamily.TRAE_GRADE3_SPECIFIC: (
        "FAMILY: Treatment-Related Adverse Events — Grade 3+ specific, per preferred term.\n"
        f"{_AE_DEFINITIONS_BLOCK}\n\n"
        "Scope of THIS family: Grade 3+ TRAE rates for specific preferred terms. Use rows from TRAE "
        "(treatment-related / drug-related) tables only. If a specific term appears only in any-cause "
        "AE tables or TEAE tables, return empty string for this family.\n\n"
        "Attributes (all percentages, per arm) — for each named preferred term:\n"
        "grade_3_plus_trae_immune_related, _irr, _crs, _colitis, _thrombocytopenia, _neutropenia, "
        "_leukopenia, _fatigue, _nausea, _anemia, _diarrhea, _hyperglycemia, _dyspnea, _pyrexia, "
        "_bleeding, _pruritus, _rash, _pneumonia, _thyroiditis, _hypophysitis, _hepatitis, "
        "_pneumonitis, _alanine_aminotransferase, _hypothyroidism, _hyperthyroidism, _ast_increased, "
        "_vomiting.\n\n"
        f"{_VALUE_FORMAT_NOTE}\n"
        f"{_NO_INFERENCE_CLAUSE}\n\n"
        "EXAMPLE — TRAE table: 'Grade 3-4 drug-related rash: arm A 6 (3.0%), arm B 1 (0.5%).' Output:\n"
        "{\n"
        '  "Arm A": {"grade_3_plus_trae_rash": "3.0"},\n'
        '  "Arm B": {"grade_3_plus_trae_rash": "0.5"}\n'
        "}\n\n"
        "{arms_block}"
    ),
}
