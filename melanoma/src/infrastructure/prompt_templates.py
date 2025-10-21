"""Prompt templates for attribute extraction.

This module reuses the sophisticated prompt logic from your existing
extraction scripts while adapting it for the RAG-enhanced approach.
"""

import logging
from typing import Any

from ..domain.extraction_interfaces import PromptTemplateProvider
from ..domain.extraction_models import AttributeType

logger = logging.getLogger(__name__)


class ExtractionPromptTemplateProvider(PromptTemplateProvider):
    """Provider for extraction prompt templates.

    This implementation reuses the sophisticated prompt logic from
    your existing extraction scripts while adapting it for RAG context.
    """

    def __init__(self):
        """Initialize prompt template provider."""
        self.extraction_prompts = self._initialize_extraction_prompts()
        logger.info("Prompt template provider initialized")

    def get_extraction_prompt(
        self, attribute_type: AttributeType, context: list[str]
    ) -> str:
        """Get extraction prompt for an attribute type.

        Args:
            attribute_type: Type of attribute to extract
            context: Context texts to include in prompt

        Returns:
            Formatted extraction prompt
        """
        # Debug: Check what we're receiving
        logger.debug(
            f"get_extraction_prompt called with attribute_type: {attribute_type} (type: {type(attribute_type)})"
        )

        # Get base prompt - use explicit if available, otherwise generate dynamically
        if attribute_type in self.extraction_prompts:
            logger.debug(f"Found explicit prompt for {attribute_type}")
            base_prompt = self.extraction_prompts[attribute_type]
        else:
            logger.debug(
                f"No explicit prompt for {attribute_type}, using dynamic prompt"
            )
            base_prompt = self._get_dynamic_prompt(attribute_type)

        # Format context
        context_text = self._format_context(context)

        # Combine base prompt with context
        full_prompt = f"{base_prompt}\n\nCONTEXT:\n{context_text}"

        return full_prompt

    def _get_dynamic_prompt(self, attribute_type: AttributeType) -> str:
        """Generate a dynamic prompt for an attribute type.

        Args:
            attribute_type: Type of attribute to extract

        Returns:
            Dynamic extraction prompt
        """
        # Convert attribute type to readable name
        attr_name = attribute_type.value.replace("_", " ").title()

        return f"""
Extract the {attr_name} from the provided context.

Look for:
- Direct mentions of {attr_name}
- Related terms and synonyms
- Numerical values if applicable
- Context clues that indicate the value

Return only the extracted value, or "Not found" if not available.
"""

    def _initialize_extraction_prompts(self) -> dict[AttributeType, str]:
        """Initialize extraction prompts for each attribute type."""
        return {
            # General Parameters (Abstract-level)
            AttributeType.ABSTRACT_NUMBER: """
TASK: Extract the abstract number from the clinical trial abstract.

CRITICAL REQUIREMENTS:
1. Look for abstract number in the Abstract ID section
2. Extract exactly as found (just the number)
3. If not found, return "Not found"

EXTRACTION RULES:
- Primary: Look for "### Abstract ID: [NUMBER]" pattern
- Format: Return just the number (e.g., "10000")
- Look in: Abstract ID header section
- Common patterns: "### Abstract ID: 10000", "Abstract ID: 10000"

COMMON PHRASES:
- "### Abstract ID: 10000"
- "Abstract ID: 10000"
- "Abstract #10000"
- "Abstract LBA9504"

OUTPUT FORMAT:
Return abstract number as string (e.g., "10000").
""",
            AttributeType.COMMENTS: """
TASK: Extract comments or additional information from the clinical trial abstract.

CRITICAL REQUIREMENTS:
1. Look for full text availability statements
2. Extract website references and redirect information
3. If no comments, return empty string ""

EXTRACTION RULES:
- Priority: Full text availability statements
- Include: Website references (meetings.asco.org, journal supplements)
- Note: Non-standard identifiers or special processing
- Look for: Complete sentences about availability

COMMON PHRASES:
- "The full, final text of this abstract will be available at meetings.asco.org"
- "Full text available at Journal of Clinical Oncology"
- "Complete data will be presented at the meeting"

OUTPUT FORMAT:
Return complete comment text as string.
""",
            AttributeType.TRIAL_NAME: """
TASK: Extract the trial name from the clinical trial abstract.

CRITICAL REQUIREMENTS:
1. Look for trial names like "Keynote-xxx", "Checkmate-xxx", "Masterkey-xxx"
2. If not a standard trial name, return "No Name"
3. Extract full trial name including number

EXTRACTION RULES:
- Primary: Look for "Keynote-", "Checkmate-", "Masterkey-" patterns
- Format: Include full name with number (e.g., "Keynote-006")
- Fallback: If no standard pattern, return "No Name"
- Look in: Title, background, methods sections

COMMON PHRASES:
- "KEYNOTE-006 study"
- "Checkmate-067 trial"
- "MASTERKEY-265"
- "Study name: KEYNOTE-001"

OUTPUT FORMAT:
Return trial name or "No Name" if not found.
""",
            AttributeType.CANCER_TYPE: """
TASK: Extract the cancer type from the clinical trial abstract.

CRITICAL REQUIREMENTS:
1. Look for specific melanoma subtypes or cancer types
2. Extract from patient population description
3. Use controlled vocabulary terms

EXTRACTION RULES:
- Primary: Look for melanoma subtypes in patient population
- Format: Use exact controlled vocabulary terms
- Context: Patient eligibility, study population, disease description
- Look in: Methods, patient characteristics, eligibility criteria

CONTROLLED VOCABULARY:
- "Resected Cutaneous Melanoma"
- "Unresectable Cutaneous Melanoma"
- "Cutaneous melanoma with Brain metastasis"
- "Cutaneous Melanoma with CNS metastasis"
- "Uveal Melanoma", "Mucosal Melanoma", "Acral Melanoma"

COMMON PHRASES:
- "patients with resected cutaneous melanoma"
- "unresectable or metastatic melanoma"
- "melanoma with brain metastases"
- "uveal melanoma patients"

OUTPUT FORMAT:
Return cancer type from controlled vocabulary.
""",
            AttributeType.NCT_NUMBER: """
TASK: Extract the NCT (National Clinical Trial) number from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for standard NCT######## format (e.g., NCT03554083)
2. Extract from phrases like "ClinicalTrials.gov, number NCT01515189" or "Clinical trial information: NCT02085070"
3. If no NCT number is found, return empty string ""
4. Do not extract partial or invalid NCT numbers

EXTRACTION RULES:
- Primary: Look for "NCT" followed by 8 digits
- Secondary: Extract from "Clinical trial identification:" field
- Tertiary: Look for "ClinicalTrials.gov" references
- Format: Return exactly as found (e.g., "NCT03554083")

OUTPUT FORMAT:
Return only the NCT number or empty string if not found.
""",
            # Treatment Details (Arm-level)
            AttributeType.BRAND_NAME: """
TASK: Extract the brand name(s) of drugs from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for brand names of drugs used in treatment
2. Extract commercial names, not generic names
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for brand names in drug descriptions
- Format: Extract commercial names (e.g., "Keytruda", "Opdivo")
- Context: Drug information, treatment details
- Look in: Methods, treatment arms, drug descriptions

COMMON BRAND NAMES:
- Pembrolizumab → "Keytruda"
- Nivolumab → "Opdivo"
- Ipilimumab → "Yervoy"
- Vemurafenib → "Zelboraf"

OUTPUT FORMAT:
Return brand name(s) as string.
""",
            AttributeType.GENERIC_NAME: """
TASK: Extract the generic drug name(s) from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Extract the generic (non-brand) names of drugs used in treatment
2. For combination therapies, use "Drug A + Drug B" format
3. For dose variations, include the dose (e.g., "Nivolumab 1mg/kg")
4. Focus on the primary treatment drug(s), not supportive medications

EXTRACTION RULES:
- Single drug: Extract generic name only (e.g., "Pembrolizumab")
- Combination: Use "+" between drug names (e.g., "Nivolumab + Ipilimumab")
- Dose variations: Include dose information (e.g., "Nivolumab 3mg/kg")
- Brand names: Convert to generic names when possible

COMMON GENERIC NAMES:
- Immune Checkpoint Inhibitors: Pembrolizumab, Nivolumab, Ipilimumab, Relatlimab
- Targeted Therapy: Vemurafenib, Dabrafenib, Trametinib, Encorafenib
- Cellular Therapy: Lifileucel, Amtagvi, TIL therapy
- Other: Talimogene laherparepvec, Tebentafusp-tebn

OUTPUT FORMAT:
Return the generic drug name(s) as a string.
""",
            AttributeType.TYPE_OF_THERAPY: """
TASK: Extract the type of therapy from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for therapy type classification in treatment details
2. Extract primary therapy type from controlled vocabulary
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for therapy type in treatment descriptions
- Format: Use exact controlled vocabulary terms
- Context: Drug mechanism, treatment approach, study design
- Look in: Methods, treatment arms, drug descriptions

CONTROLLED VOCABULARY:
- "Immunotherapy"
- "Cellular therapy"
- "Targeted Therapy"
- "Oncolytic Virus"
- "Chemotherapy"

COMMON PHRASES:
- "immune checkpoint inhibitor" → "Immunotherapy"
- "PD-1/PD-L1 inhibitor" → "Immunotherapy"
- "CTLA-4 inhibitor" → "Immunotherapy"
- "cellular therapy" → "Cellular therapy"
- "TIL therapy" → "Cellular therapy"
- "CAR T-cell" → "Cellular therapy"
- "targeted therapy" → "Targeted Therapy"
- "BRAF inhibitor" → "Targeted Therapy"
- "MEK inhibitor" → "Targeted Therapy"
- "oncolytic virus" → "Oncolytic Virus"
- "chemotherapy" → "Chemotherapy"

OUTPUT FORMAT:
Return therapy type from controlled vocabulary.
""",
            AttributeType.SUB_THERAPY: """
TASK: Extract sub-therapy or treatment subtype information.

CRITICAL REQUIREMENTS:
1. Look for specific treatment subtypes or variations
2. Extract detailed treatment information from controlled vocabulary
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for treatment subtypes, variations, or specific approaches
- Format: Use exact controlled vocabulary terms
- Context: Treatment details, study design
- Look in: Methods, treatment arms, study design

CONTROLLED VOCABULARY:
1.1 Immune Checkpoint Inhibitor/Antibody: Pembrolizumab, Nivolumab
1.2 Vaccine/Immunostimulant: NeoVaxMI, mRNA-4157
1.3 Bispecific: Tebentafusp
2.1 CAR-T: IL13Ra2 CAR-T
2.2 NK-Cell: Adoptive NK cell therapy
2.3 Myeloid Cells: Adoptive Myeloid cell therapy
2.4 TIL Therapy: Lifileucel
3.1 Antibody: Trastuzumab, Rituximab
3.2 Tyrosine kinase inhibitor: Imatinib, Erlotinib
3.3 Angiogenesis inhibitor: Bevacizumab
3.4 Antibody-Drug Conjugate: Ozuriftamab vedotin, HER3 ADC
4 Oncolytic Virus: Talimogene laherparepvec (Imlygic)
5 Chemotherapy: Dacarbazine, Temozolomide

COMMON PHRASES:
- "Pembrolizumab" → "Immune Checkpoint Inhibitor/Antibody"
- "Nivolumab" → "Immune Checkpoint Inhibitor/Antibody"
- "CAR T-cell" → "CAR-T"
- "TIL therapy" → "TIL Therapy"
- "Bevacizumab" → "Angiogenesis inhibitor"
- "Dacarbazine" → "Chemotherapy"

OUTPUT FORMAT:
Return sub-therapy from controlled vocabulary.
""",
            AttributeType.MEDIAN_AGE: """
TASK: Extract the median age of patients from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for median age in patient characteristics
2. Extract numeric value in years
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "median age", "median", "age"
- Format: Extract number only (e.g., "65" not "65 years")
- Range: Should be reasonable (0-120 years)
- Look in: Patient characteristics, demographics, baseline data

COMMON PHRASES:
- "median age was 65 years"
- "median age: 58"
- "age range 45-75, median 62"
- "median patient age 70"

OUTPUT FORMAT:
Return numeric value representing years (e.g., "65").
""",
            AttributeType.NUMBER_OF_PATIENTS: """
TASK: Extract the number of patients for this specific treatment arm.

CRITICAL REQUIREMENTS:
1. Look for patient count for the specific treatment arm
2. Extract integer value only
3. Do not sum patients from multiple arms
4. If not found, return "Not found"

EXTRACTION RULES:
- Primary: Look for "N=", "n=", "patients", "enrolled", "randomized"
- Format: Extract integer only (e.g., "514" not "514 patients")
- Context: Treatment arm specific, not total study
- Look in: Methods, patient flow, treatment arms, randomization details

COMMON PHRASES:
- "pembrolizumab at a flat dose of 200 mg (N=514)"
- "placebo (N=505)"
- "n = 313 patients"
- "313 patients were randomized"
- "enrolled 150 patients"
- "arm included 200 patients"

OUTPUT FORMAT:
Return integer value (e.g., "313").
""",
            # Efficacy - Response Rates
            AttributeType.OBJECTIVE_RESPONSE_RATE: """
TASK: Extract the Objective Response Rate (ORR) from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for Objective Response Rate (ORR) percentage
2. Extract numeric value only (no % symbol)
3. If not explicitly stated, calculate using: (CR + PR) / Total Patients
4. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "Objective response rate", "ORR", "response rate"
- Format: Extract number only (e.g., "25" not "25%")
- Range: Should be 0-100
- Calculation: If not given, use (Complete Response + Partial Response) / Total Patients
- Look in Results section, efficacy data

COMMON PHRASES:
- "Objective response rate was 25%"
- "ORR of 30%"
- "Response rate: 18%"
- "n (%) 7 (18)" → extract 18

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.COMPLETE_RESPONSE: """
TASK: Extract the Complete Response (CR) percentage from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for Complete Response (CR) percentage
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "Complete Response", "CR", "complete response rate"
- Format: Extract number only (e.g., "15" not "15%")
- Range: Should be 0-100
- Look in: Results section, efficacy data, response rates

COMMON PHRASES:
- "Complete response rate was 15%"
- "CR: 12%"
- "Complete response: 8%"
- "n (%) 5 (15)" → extract 15

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.PATHOLOGICAL_COMPLETE_RESPONSE: """
TASK: Extract the Pathological Complete Response (pCR) percentage.

CRITICAL REQUIREMENTS:
1. Look for Pathological Complete Response (pCR) percentage
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "Pathological Complete Response", "pCR", "pathological CR"
- Format: Extract number only
- Range: Should be 0-100
- Look in: Results section, pathological response data

COMMON PHRASES:
- "Pathological complete response rate: 25%"
- "pCR: 20%"
- "Pathological CR: 18%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.COMPLETE_METABOLIC_RESPONSE: """
TASK: Extract the Complete Metabolic Response (CMR) percentage.

CRITICAL REQUIREMENTS:
1. Look for Complete Metabolic Response (CMR) percentage
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "Complete Metabolic Response", "CMR", "metabolic response"
- Format: Extract number only
- Range: Should be 0-100
- Look in: Results section, metabolic response data

COMMON PHRASES:
- "Complete metabolic response: 30%"
- "CMR: 25%"
- "Metabolic response rate: 22%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.DISEASE_CONTROL_RATE: """
TASK: Extract the Disease Control Rate (DCR) percentage.

CRITICAL REQUIREMENTS:
1. Look for Disease Control Rate (DCR) percentage
2. Extract numeric value only (no % symbol)
3. If not explicitly stated, calculate using: (CR + PR + SD) / Total Patients
4. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "Disease Control Rate", "DCR", "disease control"
- Format: Extract number only
- Calculation: If not given, use (Complete Response + Partial Response + Stable Disease) / Total Patients
- Range: Should be 0-100

COMMON PHRASES:
- "Disease control rate: 45%"
- "DCR: 40%"
- "Disease control: 35%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.CLINICAL_BENEFIT_RATE: """
TASK: Extract the Clinical Benefit Rate (CBR) percentage.

CRITICAL REQUIREMENTS:
1. Look for Clinical Benefit Rate (CBR) percentage
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "Clinical Benefit Rate", "CBR", "clinical benefit"
- Format: Extract number only
- Range: Should be 0-100
- Look in: Results section, clinical benefit data

COMMON PHRASES:
- "Clinical benefit rate: 50%"
- "CBR: 45%"
- "Clinical benefit: 40%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.MEDIAN_DOR: """
TASK: Extract the median Duration of Response (DOR) from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for median Duration of Response (DOR) in months
2. Extract numeric value or "NR" if not reached
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "Duration of Response", "DOR", "median DOR"
- Format: Extract number in months (e.g., "12.5" not "12.5 months")
- Special: "NR" or "not reached" → "NR"
- Look in: Results section, response duration data

COMMON PHRASES:
- "median DOR was 12.5 months"
- "Duration of response: 8.2 months"
- "DOR: 15.0 months"
- "median DOR not reached"

OUTPUT FORMAT:
Return numeric value in months or "NR".
""",
            AttributeType.DOR_RATE: """
TASK: Extract the Duration of Response (DOR) rate percentage.

CRITICAL REQUIREMENTS:
1. Look for DOR rate percentage at specific timepoints
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "DOR rate", "duration rate", "response duration rate"
- Format: Extract number only
- Range: Should be 0-100
- Look in: Results section, response duration data

COMMON PHRASES:
- "DOR rate at 12 months: 60%"
- "Duration rate: 45%"
- "Response duration rate: 50%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            # Efficacy - Survival Metrics
            AttributeType.MEDIAN_PFS: """
TASK: Extract the median Progression-Free Survival (PFS) from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for median PFS in months
2. Extract numeric value or "NR" if not reached
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "median PFS", "mPFS", "progression-free survival"
- Format: Extract number in months (e.g., "12.3" not "12.3 months")
- Special: "NR" or "not reached" → "NR"
- Look in: Results section, survival data

COMMON PHRASES:
- "median PFS was 12.3 months"
- "mPFS: 8.5 months"
- "Progression-free survival: 15.0 months"
- "median PFS not reached"

OUTPUT FORMAT:
Return numeric value in months or "NR".
""",
            AttributeType.MEDIAN_FOLLOWUP_PFS: """
TASK: Extract the median follow-up time for measuring PFS.

CRITICAL REQUIREMENTS:
1. Look for median follow-up time for PFS measurement
2. Extract numeric value in months
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "median follow-up", "follow-up for PFS", "PFS follow-up"
- Format: Extract number in months
- Context: PFS-specific follow-up time
- Look in: Methods, follow-up data

COMMON PHRASES:
- "median follow-up for PFS was 18.5 months"
- "PFS follow-up: 12.0 months"
- "median follow-up: 24.0 months"

OUTPUT FORMAT:
Return numeric value in months.
""",
            AttributeType.P_VALUE_PFS: """
TASK: Extract the p-value for Progression-Free Survival (PFS).

CRITICAL REQUIREMENTS:
1. Look for p-value specifically related to PFS
2. Extract numeric value or significance level
3. If not reported, return empty string ""

EXTRACTION RULES:
- Numeric: Extract decimal value (e.g., 0.023, 0.001)
- Significance: Convert to standard levels:
  - p > 0.05 → "Non-Significant"
  - p ≤ 0.05 → "Significant"
  - p ≤ 0.001 → "Highly Significant"
- Look for: "p-value for PFS", "PFS p-value", "progression-free survival p"

COMMON PHRASES:
- "p-value for PFS was 0.023"
- "PFS p-value = 0.001"
- "PFS p < 0.05"

OUTPUT FORMAT:
Return numeric value (0.0-1.0) or significance level string.
""",
            AttributeType.HR_PFS: """
TASK: Extract the Hazard Ratio (HR) for Progression-Free Survival (PFS).

CRITICAL REQUIREMENTS:
1. Look for Hazard Ratio specifically related to PFS
2. Extract numeric value
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "HR for PFS", "PFS HR", "hazard ratio PFS"
- Format: Extract decimal value (e.g., 0.65, 1.23)
- Range: Should be reasonable (0.1-10.0)
- Look in: Results section, statistical analysis

COMMON PHRASES:
- "HR for PFS was 0.65"
- "PFS HR: 0.78"
- "Hazard ratio for PFS: 1.15"

OUTPUT FORMAT:
Return numeric value (e.g., "0.65").
""",
            AttributeType.MEDIAN_OS: """
TASK: Extract the median Overall Survival (OS) from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for median OS in months
2. Extract numeric value or "NR" if not reached
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "median OS", "mOS", "overall survival"
- Format: Extract number in months (e.g., "24.1" not "24.1 months")
- Special: "NR" or "not reached" → "NR"
- Look in: Results section, survival data

COMMON PHRASES:
- "median OS was 24.1 months"
- "mOS: 18.5 months"
- "Overall survival: 30.0 months"
- "median OS not reached"

OUTPUT FORMAT:
Return numeric value in months or "NR".
""",
            AttributeType.MEDIAN_FOLLOWUP_OS: """
TASK: Extract the median follow-up time for measuring OS.

CRITICAL REQUIREMENTS:
1. Look for median follow-up time for OS measurement
2. Extract numeric value in months
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "median follow-up", "follow-up for OS", "OS follow-up"
- Format: Extract number in months
- Context: OS-specific follow-up time
- Look in: Methods, follow-up data

COMMON PHRASES:
- "median follow-up for OS was 36.0 months"
- "OS follow-up: 24.0 months"
- "median follow-up: 48.0 months"

OUTPUT FORMAT:
Return numeric value in months.
""",
            AttributeType.P_VALUE_OS: """
TASK: Extract the p-value for Overall Survival (OS) from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for p-value specifically related to Overall Survival (OS)
2. Extract numeric value or significance level
3. If not reported, return empty string ""
4. Focus on primary OS analysis, not subgroup analyses

EXTRACTION RULES:
- Numeric: Extract decimal value (e.g., 0.023, 0.001)
- Significance: Convert to standard levels:
  - p > 0.05 → "Non-Significant"
  - p ≤ 0.05 → "Significant"
  - p ≤ 0.001 → "Highly Significant"
- Look for phrases: "p-value", "p =", "p<", "p>", "statistical significance"
- OS-specific: "overall survival", "OS", "survival analysis"

COMMON PHRASES:
- "p-value for OS was 0.023"
- "Overall survival p = 0.001"
- "OS p-value < 0.05"
- "statistically significant for OS"

OUTPUT FORMAT:
Return numeric value (0.0-1.0) or significance level string.
""",
            AttributeType.HR_OS: """
TASK: Extract the Hazard Ratio (HR) for Overall Survival (OS).

CRITICAL REQUIREMENTS:
1. Look for Hazard Ratio specifically related to OS
2. Extract numeric value
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "HR for OS", "OS HR", "hazard ratio OS"
- Format: Extract decimal value (e.g., 0.65, 1.23)
- Range: Should be reasonable (0.1-10.0)
- Look in: Results section, statistical analysis

COMMON PHRASES:
- "HR for OS was 0.65"
- "OS HR: 0.78"
- "Hazard ratio for OS: 1.15"

OUTPUT FORMAT:
Return numeric value (e.g., "0.65").
""",
            # PFS Rate Timepoints
            AttributeType.PFS_RATE_6M: """
TASK: Extract the PFS rate at 6 months from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for 6-month PFS rate percentage
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""
4. Focus on progression-free survival at 6 months

EXTRACTION RULES:
- Primary: Look for "6-month PFS", "6-mo PFS", "PFS at 6 months"
- Format: Extract number only (e.g., "75" not "75%")
- Range: Should be 0-100
- Look in efficacy data, survival analysis
- Alternative: "6-month progression-free survival"

COMMON PHRASES:
- "6-month PFS rate was 75%"
- "PFS at 6 months: 68%"
- "6-mo PFS: 72%"
- "n (%) 150 (75)" → extract 75

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.PFS_RATE_9M: """
TASK: Extract the PFS rate at 9 months from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for 9-month PFS rate percentage
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""
4. Focus on progression-free survival at 9 months

EXTRACTION RULES:
- Primary: Look for "9-month PFS", "9-mo PFS", "PFS at 9 months"
- Format: Extract number only (e.g., "65" not "65%")
- Range: Should be 0-100
- Look in efficacy data, survival analysis

COMMON PHRASES:
- "9-month PFS rate was 65%"
- "PFS at 9 months: 58%"
- "9-mo PFS: 62%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.PFS_RATE_12M: """
TASK: Extract the PFS rate at 12 months (1 year) from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for 12-month or 1-year PFS rate percentage
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""
4. Focus on progression-free survival at 12 months/1 year

EXTRACTION RULES:
- Primary: Look for "12-month PFS", "1-year PFS", "PFS at 12 months"
- Format: Extract number only (e.g., "55" not "55%")
- Range: Should be 0-100
- Look in efficacy data, survival analysis
- Alternative: "1-year progression-free survival"

COMMON PHRASES:
- "12-month PFS rate was 55%"
- "1-year PFS: 48%"
- "PFS at 12 months: 52%"
- "12-mo PFS: 50%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.PFS_RATE_18M: """
TASK: Extract the PFS rate at 18 months from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for 18-month PFS rate percentage
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""
4. Focus on progression-free survival at 18 months

EXTRACTION RULES:
- Primary: Look for "18-month PFS", "18-mo PFS", "PFS at 18 months"
- Format: Extract number only (e.g., "45" not "45%")
- Range: Should be 0-100
- Look in efficacy data, survival analysis

COMMON PHRASES:
- "18-month PFS rate was 45%"
- "PFS at 18 months: 42%"
- "18-mo PFS: 40%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.PFS_RATE_24M: """
TASK: Extract the PFS rate at 24 months (2 years) from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for 24-month or 2-year PFS rate percentage
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""
4. Focus on progression-free survival at 24 months/2 years

EXTRACTION RULES:
- Primary: Look for "24-month PFS", "2-year PFS", "PFS at 24 months"
- Format: Extract number only (e.g., "35" not "35%")
- Range: Should be 0-100
- Look in efficacy data, survival analysis
- Alternative: "2-year progression-free survival"

COMMON PHRASES:
- "24-month PFS rate was 35%"
- "2-year PFS: 32%"
- "PFS at 24 months: 30%"
- "24-mo PFS: 28%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.PFS_RATE_36M: """
TASK: Extract the PFS rate at 36 months (3 years) from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for 36-month or 3-year PFS rate percentage
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""
4. Focus on progression-free survival at 36 months/3 years

EXTRACTION RULES:
- Primary: Look for "36-month PFS", "3-year PFS", "PFS at 36 months"
- Format: Extract number only (e.g., "25" not "25%")
- Range: Should be 0-100
- Look in efficacy data, survival analysis
- Alternative: "3-year progression-free survival"

COMMON PHRASES:
- "36-month PFS rate was 25%"
- "3-year PFS: 22%"
- "PFS at 36 months: 20%"
- "36-mo PFS: 18%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.PFS_RATE_48M: """
TASK: Extract the PFS rate at 48 months (4 years) from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for 48-month or 4-year PFS rate percentage
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""
4. Focus on progression-free survival at 48 months/4 years

EXTRACTION RULES:
- Primary: Look for "48-month PFS", "4-year PFS", "PFS at 48 months"
- Format: Extract number only (e.g., "15" not "15%")
- Range: Should be 0-100
- Look in efficacy data, survival analysis
- Alternative: "4-year progression-free survival"

COMMON PHRASES:
- "48-month PFS rate was 15%"
- "4-year PFS: 12%"
- "PFS at 48 months: 10%"
- "48-mo PFS: 8%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            # OS Rate Timepoints
            AttributeType.OS_RATE_6M: """
TASK: Extract the OS rate at 6 months from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for 6-month OS rate percentage
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""
4. Focus on overall survival at 6 months

EXTRACTION RULES:
- Primary: Look for "6-month OS", "6-mo OS", "OS at 6 months"
- Format: Extract number only (e.g., "85" not "85%")
- Range: Should be 0-100
- Look in efficacy data, survival analysis
- Alternative: "6-month overall survival"

COMMON PHRASES:
- "6-month OS rate was 85%"
- "OS at 6 months: 82%"
- "6-mo OS: 80%"
- "n (%) 170 (85)" → extract 85

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.OS_RATE_9M: """
TASK: Extract the OS rate at 9 months from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for 9-month OS rate percentage
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""
4. Focus on overall survival at 9 months

EXTRACTION RULES:
- Primary: Look for "9-month OS", "9-mo OS", "OS at 9 months"
- Format: Extract number only (e.g., "75" not "75%")
- Range: Should be 0-100
- Look in efficacy data, survival analysis

COMMON PHRASES:
- "9-month OS rate was 75%"
- "OS at 9 months: 72%"
- "9-mo OS: 70%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.OS_RATE_12M: """
TASK: Extract the OS rate at 12 months (1 year) from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for 12-month or 1-year OS rate percentage
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""
4. Focus on overall survival at 12 months/1 year

EXTRACTION RULES:
- Primary: Look for "12-month OS", "1-year OS", "OS at 12 months"
- Format: Extract number only (e.g., "65" not "65%")
- Range: Should be 0-100
- Look in efficacy data, survival analysis
- Alternative: "1-year overall survival"

COMMON PHRASES:
- "12-month OS rate was 65%"
- "1-year OS: 62%"
- "OS at 12 months: 60%"
- "12-mo OS: 58%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.OS_RATE_18M: """
TASK: Extract the OS rate at 18 months from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for 18-month OS rate percentage
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""
4. Focus on overall survival at 18 months

EXTRACTION RULES:
- Primary: Look for "18-month OS", "18-mo OS", "OS at 18 months"
- Format: Extract number only (e.g., "55" not "55%")
- Range: Should be 0-100
- Look in efficacy data, survival analysis

COMMON PHRASES:
- "18-month OS rate was 55%"
- "OS at 18 months: 52%"
- "18-mo OS: 50%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.OS_RATE_24M: """
TASK: Extract the OS rate at 24 months (2 years) from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for 24-month or 2-year OS rate percentage
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""
4. Focus on overall survival at 24 months/2 years

EXTRACTION RULES:
- Primary: Look for "24-month OS", "2-year OS", "OS at 24 months"
- Format: Extract number only (e.g., "45" not "45%")
- Range: Should be 0-100
- Look in efficacy data, survival analysis
- Alternative: "2-year overall survival"

COMMON PHRASES:
- "24-month OS rate was 45%"
- "2-year OS: 42%"
- "OS at 24 months: 40%"
- "24-mo OS: 38%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.OS_RATE_36M: """
TASK: Extract the OS rate at 36 months (3 years) from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for 36-month or 3-year OS rate percentage
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""
4. Focus on overall survival at 36 months/3 years

EXTRACTION RULES:
- Primary: Look for "36-month OS", "3-year OS", "OS at 36 months"
- Format: Extract number only (e.g., "35" not "35%")
- Range: Should be 0-100
- Look in efficacy data, survival analysis
- Alternative: "3-year overall survival"

COMMON PHRASES:
- "36-month OS rate was 35%"
- "3-year OS: 32%"
- "OS at 36 months: 30%"
- "36-mo OS: 28%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.OS_RATE_48M: """
TASK: Extract the OS rate at 48 months (4 years) from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for 48-month or 4-year OS rate percentage
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""
4. Focus on overall survival at 48 months/4 years

EXTRACTION RULES:
- Primary: Look for "48-month OS", "4-year OS", "OS at 48 months"
- Format: Extract number only (e.g., "25" not "25%")
- Range: Should be 0-100
- Look in efficacy data, survival analysis
- Alternative: "4-year overall survival"

COMMON PHRASES:
- "48-month OS rate was 25%"
- "4-year OS: 22%"
- "OS at 48 months: 20%"
- "48-mo OS: 18%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            # EFS Family
            AttributeType.EFS: """
TASK: Extract the median Event-Free Survival (EFS) from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for median EFS in months
2. Extract numeric value in months (e.g., "12.0" not "12.0 months")
3. If "not reached" or "NR", return "NR"
4. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "median EFS", "event-free survival"
- Format: Extract number only (e.g., "12.0 (8.2–17.1)" -> "12.0")
- Range: Should be positive number or "NR"
- Look in efficacy data, survival analysis
- Alternative: "EFS", "event-free survival"

COMMON PHRASES:
- "Median EFS was 12.0 months"
- "Event-free survival: 10.5 months"
- "EFS: 15.2 (9.8–20.1) months" → extract 15.2
- "EFS not reached" → return "NR"

OUTPUT FORMAT:
Return numeric value in months or "NR" if not reached.
""",
            AttributeType.P_VALUE_EFS: """
TASK: Extract the p-value for Event-Free Survival (EFS) from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for p-value specifically related to EFS
2. Extract numeric value or significance level
3. If not reported, return empty string ""
4. Focus on primary EFS analysis, not subgroup analyses

EXTRACTION RULES:
- Numeric: Extract decimal value (e.g., 0.023, 0.001)
- Significance: Convert to standard levels:
  - p > 0.05 → "Non-Significant"
  - p ≤ 0.05 → "Significant"
  - p ≤ 0.001 → "Highly Significant"
- Look for phrases: "p-value", "p =", "p<", "p>", "statistical significance"
- EFS-specific: "event-free survival", "EFS", "survival analysis"

COMMON PHRASES:
- "p-value for EFS was 0.023"
- "Event-free survival p = 0.001"
- "EFS p-value < 0.05"
- "statistically significant for EFS"

OUTPUT FORMAT:
Return numeric value (0.0-1.0) or significance level string.
""",
            AttributeType.HR_EFS: """
TASK: Extract the Hazard Ratio (HR) for Event-Free Survival (EFS) from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for HR specifically related to EFS
2. Extract numeric value (decimal)
3. If not found, return empty string ""
4. Focus on primary EFS analysis

EXTRACTION RULES:
- Primary: Look for "HR", "hazard ratio", "risk ratio"
- Format: Extract decimal value (e.g., 0.65, 1.25)
- Range: Should be positive number
- Look in efficacy data, survival analysis
- EFS-specific: "event-free survival", "EFS"

COMMON PHRASES:
- "HR for EFS was 0.65"
- "Event-free survival HR: 0.72"
- "EFS hazard ratio 0.58"
- "HR (95% CI) 0.65 (0.45-0.89)" → extract 0.65

OUTPUT FORMAT:
Return numeric value representing hazard ratio.
""",
            # RFS Family
            AttributeType.RFS: """
TASK: Extract the median Recurrence-Free Survival (RFS) from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for median RFS in months
2. Extract numeric value in months (e.g., "24.0" not "24.0 months")
3. If "not reached" or "NR", return "NR"
4. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "median RFS", "recurrence-free survival"
- Format: Extract number only (e.g., "24.0 (18.2–30.1)" -> "24.0")
- Range: Should be positive number or "NR"
- Look in efficacy data, survival analysis
- Alternative: "RFS", "recurrence-free survival"

COMMON PHRASES:
- "Median RFS was 24.0 months"
- "Recurrence-free survival: 22.5 months"
- "RFS: 28.2 (20.8–35.1) months" → extract 28.2
- "RFS not reached" → return "NR"

OUTPUT FORMAT:
Return numeric value in months or "NR" if not reached.
""",
            AttributeType.P_VALUE_RFS: """
TASK: Extract the p-value for Recurrence-Free Survival (RFS) from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for p-value specifically related to RFS
2. Extract numeric value or significance level
3. If not reported, return empty string ""
4. Focus on primary RFS analysis, not subgroup analyses

EXTRACTION RULES:
- Numeric: Extract decimal value (e.g., 0.023, 0.001)
- Significance: Convert to standard levels:
  - p > 0.05 → "Non-Significant"
  - p ≤ 0.05 → "Significant"
  - p ≤ 0.001 → "Highly Significant"
- Look for phrases: "p-value", "p =", "p<", "p>", "statistical significance"
- RFS-specific: "recurrence-free survival", "RFS", "survival analysis"

COMMON PHRASES:
- "p-value for RFS was 0.023"
- "Recurrence-free survival p = 0.001"
- "RFS p-value < 0.05"
- "statistically significant for RFS"

OUTPUT FORMAT:
Return numeric value (0.0-1.0) or significance level string.
""",
            AttributeType.LENGTH_RFS: """
TASK: Extract the length of measuring Recurrence-Free Survival (RFS) from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for follow-up duration for RFS measurement
2. Extract numeric value in months
3. If not found, return empty string ""
4. Focus on RFS follow-up period

EXTRACTION RULES:
- Primary: Look for "follow-up", "median follow-up", "observation period"
- Format: Extract number only (e.g., "36.0" not "36.0 months")
- Range: Should be positive number
- Look in methods, efficacy data
- RFS-specific: "recurrence-free survival", "RFS"

COMMON PHRASES:
- "Median follow-up for RFS was 36.0 months"
- "RFS follow-up: 30.5 months"
- "Observation period for RFS: 24.0 months"
- "RFS median follow-up 42.0 (28.5-48.2) months" → extract 42.0

OUTPUT FORMAT:
Return numeric value in months.
""",
            AttributeType.HR_RFS: """
TASK: Extract the Hazard Ratio (HR) for Recurrence-Free Survival (RFS) from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for HR specifically related to RFS
2. Extract numeric value (decimal)
3. If not found, return empty string ""
4. Focus on primary RFS analysis

EXTRACTION RULES:
- Primary: Look for "HR", "hazard ratio", "risk ratio"
- Format: Extract decimal value (e.g., 0.56, 1.25)
- Range: Should be positive number
- Look in efficacy data, survival analysis
- RFS-specific: "recurrence-free survival", "RFS"

COMMON PHRASES:
- "HR for RFS was 0.56"
- "Recurrence-free survival HR: 0.62"
- "RFS hazard ratio 0.48"
- "HR (95% CI) 0.56 (0.38-0.82)" → extract 0.56

OUTPUT FORMAT:
Return numeric value representing hazard ratio.
""",
            # MFS Family
            AttributeType.MFS: """
TASK: Extract the median Metastasis-Free Survival (MFS) from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for median MFS in months
2. Extract numeric value in months (e.g., "18.0" not "18.0 months")
3. If "not reached" or "NR", return "NR"
4. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "median MFS", "metastasis-free survival"
- Format: Extract number only (e.g., "18.0 (12.2–24.1)" -> "18.0")
- Range: Should be positive number or "NR"
- Look in efficacy data, survival analysis
- Alternative: "MFS", "metastasis-free survival"

COMMON PHRASES:
- "Median MFS was 18.0 months"
- "Metastasis-free survival: 16.5 months"
- "MFS: 20.2 (14.8–26.1) months" → extract 20.2
- "MFS not reached" → return "NR"

OUTPUT FORMAT:
Return numeric value in months or "NR" if not reached.
""",
            AttributeType.LENGTH_MFS: """
TASK: Extract the length of measuring Metastasis-Free Survival (MFS) from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for follow-up duration for MFS measurement
2. Extract numeric value in months
3. If not found, return empty string ""
4. Focus on MFS follow-up period

EXTRACTION RULES:
- Primary: Look for "follow-up", "median follow-up", "observation period"
- Format: Extract number only (e.g., "30.0" not "30.0 months")
- Range: Should be positive number
- Look in methods, efficacy data
- MFS-specific: "metastasis-free survival", "MFS"

COMMON PHRASES:
- "Median follow-up for MFS was 30.0 months"
- "MFS follow-up: 28.5 months"
- "Observation period for MFS: 24.0 months"
- "MFS median follow-up 32.0 (22.5-38.2) months" → extract 32.0

OUTPUT FORMAT:
Return numeric value in months.
""",
            AttributeType.HR_MFS: """
TASK: Extract the Hazard Ratio (HR) for Metastasis-Free Survival (MFS) from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for HR specifically related to MFS
2. Extract numeric value (decimal)
3. If not found, return empty string ""
4. Focus on primary MFS analysis

EXTRACTION RULES:
- Primary: Look for "HR", "hazard ratio", "risk ratio"
- Format: Extract decimal value (e.g., 0.55, 1.25)
- Range: Should be positive number
- Look in efficacy data, survival analysis
- MFS-specific: "metastasis-free survival", "MFS"

COMMON PHRASES:
- "HR for MFS was 0.55"
- "Metastasis-free survival HR: 0.62"
- "MFS hazard ratio 0.48"
- "HR (95% CI) 0.55 (0.35-0.85)" → extract 0.55

OUTPUT FORMAT:
Return numeric value representing hazard ratio.
""",
            # Time-to Metrics
            AttributeType.TTR: """
TASK: Extract the Time to Response (TTR) from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for median TTR in months
2. Extract numeric value in months (e.g., "2.5" not "2.5 months")
3. If "not reached" or "NR", return "NR"
4. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "median TTR", "time to response"
- Format: Extract number only (e.g., "2.5 (1.8–3.2)" -> "2.5")
- Range: Should be positive number or "NR"
- Look in efficacy data, response analysis
- Alternative: "TTR", "time to response"

COMMON PHRASES:
- "Median TTR was 2.5 months"
- "Time to response: 2.0 months"
- "TTR: 3.2 (2.1–4.5) months" → extract 3.2
- "TTR not reached" → return "NR"

OUTPUT FORMAT:
Return numeric value in months or "NR" if not reached.
""",
            AttributeType.TTP: """
TASK: Extract the Time to Progression (TTP) from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for median TTP in months
2. Extract numeric value in months (e.g., "8.5" not "8.5 months")
3. If "not reached" or "NR", return "NR"
4. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "median TTP", "time to progression"
- Format: Extract number only (e.g., "8.5 (6.2–12.1)" -> "8.5")
- Range: Should be positive number or "NR"
- Look in efficacy data, progression analysis
- Alternative: "TTP", "time to progression"

COMMON PHRASES:
- "Median TTP was 8.5 months"
- "Time to progression: 7.0 months"
- "TTP: 10.2 (7.8–14.5) months" → extract 10.2
- "TTP not reached" → return "NR"

OUTPUT FORMAT:
Return numeric value in months or "NR" if not reached.
""",
            AttributeType.TTNT: """
TASK: Extract the Time to Next Treatment (TTNT) from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for median TTNT in months
2. Extract numeric value in months (e.g., "12.0" not "12.0 months")
3. If "not reached" or "NR", return "NR"
4. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "median TTNT", "time to next treatment"
- Format: Extract number only (e.g., "12.0 (8.5–16.2)" -> "12.0")
- Range: Should be positive number or "NR"
- Look in efficacy data, treatment analysis
- Alternative: "TTNT", "time to next treatment"

COMMON PHRASES:
- "Median TTNT was 12.0 months"
- "Time to next treatment: 10.5 months"
- "TTNT: 14.2 (11.8–18.5) months" → extract 14.2
- "TTNT not reached" → return "NR"

OUTPUT FORMAT:
Return numeric value in months or "NR" if not reached.
""",
            AttributeType.TTF: """
TASK: Extract the Time to Treatment Failure (TTF) from the clinical trial data.

CRITICAL REQUIREMENTS:
1. Look for median TTF in months
2. Extract numeric value in months (e.g., "6.5" not "6.5 months")
3. If "not reached" or "NR", return "NR"
4. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "median TTF", "time to treatment failure"
- Format: Extract number only (e.g., "6.5 (4.2–9.1)" -> "6.5")
- Range: Should be positive number or "NR"
- Look in efficacy data, treatment analysis
- Alternative: "TTF", "time to treatment failure"

COMMON PHRASES:
- "Median TTF was 6.5 months"
- "Time to treatment failure: 5.0 months"
- "TTF: 8.2 (6.1–11.5) months" → extract 8.2
- "TTF not reached" → return "NR"

OUTPUT FORMAT:
Return numeric value in months or "NR" if not reached.
""",
            # Safety - Adverse Events
            AttributeType.AE: """
TASK: Extract the overall Adverse Events (AE) percentage.

CRITICAL REQUIREMENTS:
1. Look for overall adverse events percentage
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "adverse events", "AEs", "any grade AE"
- Format: Extract number from parentheses (e.g., "125 (85%)" → "85")
- Range: Should be 0-100
- Look in: Safety section, adverse events data

COMMON PHRASES:
- "adverse events: 85%"
- "any grade AE: 90%"
- "n (%) 125 (85)" → extract 85

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.GRADE_3_PLUS_AE: """
TASK: Extract Grade 3+ or Grade 3 higher Adverse Events (AE) percentage.

CRITICAL REQUIREMENTS:
1. Look for Grade 3+ or Grade 3 higher adverse events
2. Extract percentage from parentheses (e.g., "125 (45%)" → "45")
3. If not given, sum Grade 3 + Grade 4 + Grade 5 percentages
4. If not found, return empty string ""

EXTRACTION RULES:
- Primary: "Grade 3+", "Grade 3 or higher", "Grade 3 higher"
- Format: Extract number from parentheses
- Calculation: If not given, sum Grade 3 + Grade 4 + Grade 5
- Look in Safety section, adverse events data
- Focus on treatment-related events when possible

COMMON PHRASES:
- "Grade 3+ adverse events: 45%"
- "Grade 3 or higher: 125 (45%)"
- "Grade 3 higher AE: 30%"
- "n (%) 15 (30)" → extract 30

SPECIAL HANDLING:
- "<1%" → use "1"
- "<0.5%" → use "0.5"
- "No treatment discontinuation" → "0"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.AE_LEADING_TO_DISCONTINUATION: """
TASK: Extract the percentage of AEs leading to treatment discontinuation.

CRITICAL REQUIREMENTS:
1. Look for AEs leading to discontinuation
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "AE leading to discontinuation", "discontinuation due to AE"
- Format: Extract number from parentheses
- Special: "No treatment discontinuation" → "0"
- Look in: Safety section, discontinuation data

COMMON PHRASES:
- "AE leading to discontinuation: 15%"
- "discontinuation due to AE: 20%"
- "No treatment discontinuation" → "0"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.SERIOUS_AE: """
TASK: Extract the Serious Adverse Events (SAE) percentage.

CRITICAL REQUIREMENTS:
1. Look for serious adverse events percentage
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "serious adverse events", "SAE", "serious AE"
- Format: Extract number from parentheses
- Range: Should be 0-100
- Look in: Safety section, serious events data

COMMON PHRASES:
- "serious adverse events: 25%"
- "SAE: 30%"
- "serious AE: 20%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.IMMUNE_RELATED_AE: """
TASK: Extract the Immune Related Adverse Events percentage.

CRITICAL REQUIREMENTS:
1. Look for immune related adverse events
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "immune related AE", "irAE", "immune adverse events"
- Format: Extract number from parentheses
- Range: Should be 0-100
- Look in: Safety section, immune-related events

COMMON PHRASES:
- "immune related AE: 35%"
- "irAE: 40%"
- "immune adverse events: 30%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.SERIOUS_IMMUNE_RELATED_AE: """
TASK: Extract the Serious Immune Related Adverse Events percentage.

CRITICAL REQUIREMENTS:
1. Look for serious immune related adverse events
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "serious immune related AE", "serious irAE"
- Format: Extract number from parentheses
- Range: Should be 0-100
- Look in: Safety section, serious immune events

COMMON PHRASES:
- "serious immune related AE: 15%"
- "serious irAE: 20%"
- "serious immune adverse events: 18%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.AE_LEADING_TO_DEATH: """
TASK: Extract the percentage of AEs leading to death.

CRITICAL REQUIREMENTS:
1. Look for AEs leading to death
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "AE leading to death", "death due to AE", "fatal AE"
- Format: Extract number from parentheses
- Range: Should be 0-100
- Look in: Safety section, fatal events data

COMMON PHRASES:
- "AE leading to death: 2%"
- "death due to AE: 3%"
- "fatal AE: 1%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            # Safety - Treatment-Emergent Adverse Events (TEAE)
            AttributeType.TEAE: """
TASK: Extract the Treatment-Emergent Adverse Events (TEAE) percentage.

CRITICAL REQUIREMENTS:
1. Look for treatment-emergent adverse events percentage
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "treatment-emergent adverse events", "TEAE", "treatment emergent AE"
- Format: Extract number from parentheses (e.g., "125 (85%)" → "85")
- Range: Should be 0-100
- Look in: Safety section, adverse events data

COMMON PHRASES:
- "treatment-emergent adverse events: 85%"
- "TEAE: 90%"
- "treatment emergent AE: 80%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.GRADE_3_PLUS_TEAE: """
TASK: Extract the Grade 3+ or Grade 3 higher TEAE percentage.

CRITICAL REQUIREMENTS:
1. Look for Grade 3+ or Grade 3 higher TEAE
2. Extract numeric value only (no % symbol)
3. If not given, sum Grade 3 + Grade 4 + Grade 5 TEAE percentages
4. If not found, return empty string ""

EXTRACTION RULES:
- Primary: "Grade 3+ TEAE", "Grade 3 or higher TEAE", "Grade 3 higher TEAE"
- Format: Extract number from parentheses
- Calculation: If not given, sum Grade 3 + Grade 4 + Grade 5 TEAE
- Look in: Safety section, TEAE data

COMMON PHRASES:
- "Grade 3+ TEAE: 45%"
- "Grade 3 or higher TEAE: 125 (45%)"
- "Grade 3 higher TEAE: 30%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.GRADE_3_TEAE: """
TASK: Extract the Grade 3 TEAE percentage.

CRITICAL REQUIREMENTS:
1. Look for Grade 3 TEAE percentage
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "Grade 3 TEAE", "Grade 3 treatment-emergent"
- Format: Extract number from parentheses
- Range: Should be 0-100
- Look in: Safety section, TEAE data

COMMON PHRASES:
- "Grade 3 TEAE: 25%"
- "Grade 3 treatment-emergent: 30%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.GRADE_4_TEAE: """
TASK: Extract the Grade 4 TEAE percentage.

CRITICAL REQUIREMENTS:
1. Look for Grade 4 TEAE percentage
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "Grade 4 TEAE", "Grade 4 treatment-emergent"
- Format: Extract number from parentheses
- Range: Should be 0-100
- Look in: Safety section, TEAE data

COMMON PHRASES:
- "Grade 4 TEAE: 15%"
- "Grade 4 treatment-emergent: 20%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.GRADE_5_TEAE: """
TASK: Extract the Grade 5 TEAE percentage.

CRITICAL REQUIREMENTS:
1. Look for Grade 5 TEAE percentage
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "Grade 5 TEAE", "Grade 5 treatment-emergent"
- Format: Extract number from parentheses
- Range: Should be 0-100
- Look in: Safety section, TEAE data

COMMON PHRASES:
- "Grade 5 TEAE: 5%"
- "Grade 5 treatment-emergent: 3%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.TEAE_LEADING_TO_DISCONTINUATION: """
TASK: Extract the percentage of TEAE leading to treatment discontinuation.

CRITICAL REQUIREMENTS:
1. Look for TEAE leading to discontinuation
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "TEAE leading to discontinuation", "discontinuation due to TEAE"
- Format: Extract number from parentheses
- Special: "No treatment discontinuation" → "0"
- Look in: Safety section, discontinuation data

COMMON PHRASES:
- "TEAE leading to discontinuation: 15%"
- "discontinuation due to TEAE: 20%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.TEAE_LEADING_TO_DEATH: """
TASK: Extract the percentage of TEAE leading to death.

CRITICAL REQUIREMENTS:
1. Look for TEAE leading to death
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "TEAE leading to death", "death due to TEAE", "fatal TEAE"
- Format: Extract number from parentheses
- Range: Should be 0-100
- Look in: Safety section, fatal events data

COMMON PHRASES:
- "TEAE leading to death: 2%"
- "death due to TEAE: 3%"
- "fatal TEAE: 1%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.SERIOUS_TEAE: """
TASK: Extract the Serious TEAE percentage.

CRITICAL REQUIREMENTS:
1. Look for serious TEAE percentage
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "serious TEAE", "serious treatment-emergent"
- Format: Extract number from parentheses
- Range: Should be 0-100
- Look in: Safety section, serious TEAE data

COMMON PHRASES:
- "serious TEAE: 25%"
- "serious treatment-emergent: 30%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.TEAE_IMMUNE_RELATED: """
TASK: Extract the TEAE Immune Related Adverse Events percentage.

CRITICAL REQUIREMENTS:
1. Look for immune related TEAE
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "TEAE immune related", "immune related TEAE", "irTEAE"
- Format: Extract number from parentheses
- Range: Should be 0-100
- Look in: Safety section, immune-related TEAE

COMMON PHRASES:
- "TEAE immune related: 35%"
- "immune related TEAE: 40%"
- "irTEAE: 30%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            # Safety - Treatment-Related Adverse Events (TRAE)
            AttributeType.TRAE: """
TASK: Extract the Treatment-Related Adverse Events (TRAE) percentage.

CRITICAL REQUIREMENTS:
1. Look for treatment-related adverse events percentage
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "treatment-related adverse events", "TRAE", "treatment related AE"
- Format: Extract number from parentheses (e.g., "125 (85%)" → "85")
- Range: Should be 0-100
- Look in: Safety section, adverse events data

COMMON PHRASES:
- "treatment-related adverse events: 85%"
- "TRAE: 90%"
- "treatment related AE: 80%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.GRADE_3_PLUS_TRAE: """
TASK: Extract the Grade 3+ or Grade 3 higher TRAE percentage.

CRITICAL REQUIREMENTS:
1. Look for Grade 3+ or Grade 3 higher TRAE
2. Extract numeric value only (no % symbol)
3. If not given, sum Grade 3 + Grade 4 + Grade 5 TRAE percentages
4. If not found, return empty string ""

EXTRACTION RULES:
- Primary: "Grade 3+ TRAE", "Grade 3 or higher TRAE", "Grade 3 higher TRAE"
- Format: Extract number from parentheses
- Calculation: If not given, sum Grade 3 + Grade 4 + Grade 5 TRAE
- Look in: Safety section, TRAE data

COMMON PHRASES:
- "Grade 3+ TRAE: 45%"
- "Grade 3 or higher TRAE: 125 (45%)"
- "Grade 3 higher TRAE: 30%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.GRADE_3_TRAE: """
TASK: Extract the Grade 3 TRAE percentage.

CRITICAL REQUIREMENTS:
1. Look for Grade 3 TRAE percentage
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "Grade 3 TRAE", "Grade 3 treatment-related"
- Format: Extract number from parentheses
- Range: Should be 0-100
- Look in: Safety section, TRAE data

COMMON PHRASES:
- "Grade 3 TRAE: 25%"
- "Grade 3 treatment-related: 30%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.GRADE_4_TRAE: """
TASK: Extract the Grade 4 TRAE percentage.

CRITICAL REQUIREMENTS:
1. Look for Grade 4 TRAE percentage
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "Grade 4 TRAE", "Grade 4 treatment-related"
- Format: Extract number from parentheses
- Range: Should be 0-100
- Look in: Safety section, TRAE data

COMMON PHRASES:
- "Grade 4 TRAE: 15%"
- "Grade 4 treatment-related: 20%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.GRADE_5_TRAE: """
TASK: Extract the Grade 5 TRAE percentage.

CRITICAL REQUIREMENTS:
1. Look for Grade 5 TRAE percentage
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "Grade 5 TRAE", "Grade 5 treatment-related"
- Format: Extract number from parentheses
- Range: Should be 0-100
- Look in: Safety section, TRAE data

COMMON PHRASES:
- "Grade 5 TRAE: 5%"
- "Grade 5 treatment-related: 3%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.TRAE_LEADING_TO_DISCONTINUATION: """
TASK: Extract the percentage of TRAE leading to treatment discontinuation.

CRITICAL REQUIREMENTS:
1. Look for TRAE leading to discontinuation
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "TRAE leading to discontinuation", "discontinuation due to TRAE"
- Format: Extract number from parentheses
- Special: "No treatment discontinuation" → "0"
- Look in: Safety section, discontinuation data

COMMON PHRASES:
- "TRAE leading to discontinuation: 15%"
- "discontinuation due to TRAE: 20%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.TRAE_LEADING_TO_DEATH: """
TASK: Extract the percentage of TRAE leading to death.

CRITICAL REQUIREMENTS:
1. Look for TRAE leading to death
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "TRAE leading to death", "death due to TRAE", "fatal TRAE"
- Format: Extract number from parentheses
- Range: Should be 0-100
- Look in: Safety section, fatal events data

COMMON PHRASES:
- "TRAE leading to death: 2%"
- "death due to TRAE: 3%"
- "fatal TRAE: 1%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.SERIOUS_TRAE: """
TASK: Extract the Serious TRAE percentage.

CRITICAL REQUIREMENTS:
1. Look for serious TRAE percentage
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "serious TRAE", "serious treatment-related"
- Format: Extract number from parentheses
- Range: Should be 0-100
- Look in: Safety section, serious TRAE data

COMMON PHRASES:
- "serious TRAE: 25%"
- "serious treatment-related: 30%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.TRAE_IMMUNE_RELATED: """
TASK: Extract the TRAE Immune Related Adverse Events percentage.

CRITICAL REQUIREMENTS:
1. Look for immune related TRAE
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "TRAE immune related", "immune related TRAE", "irTRAE"
- Format: Extract number from parentheses
- Range: Should be 0-100
- Look in: Safety section, immune-related TRAE

COMMON PHRASES:
- "TRAE immune related: 35%"
- "immune related TRAE: 40%"
- "irTRAE: 30%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            # Safety - Specific Adverse Events
            AttributeType.CRS: """
TASK: Extract the Cytokine Release Syndrome (CRS) percentage.

CRITICAL REQUIREMENTS:
1. Look for Cytokine Release Syndrome or CRS percentage
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "Cytokine Release Syndrome", "CRS", "cytokine release"
- Format: Extract number from parentheses
- Range: Should be 0-100
- Look in: Safety section, specific adverse events

COMMON PHRASES:
- "Cytokine Release Syndrome: 15%"
- "CRS: 20%"
- "cytokine release: 18%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
            AttributeType.WBC_DECREASED: """
TASK: Extract the White Blood Cell (WBC) decreased percentage.

CRITICAL REQUIREMENTS:
1. Look for WBC decreased percentage
2. Extract numeric value only (no % symbol)
3. If not found, return empty string ""

EXTRACTION RULES:
- Primary: Look for "WBC decreased", "white blood cell decreased", "leukopenia"
- Format: Extract number from parentheses
- Range: Should be 0-100
- Look in: Safety section, specific adverse events

COMMON PHRASES:
- "WBC decreased: 25%"
- "white blood cell decreased: 30%"
- "leukopenia: 28%"

OUTPUT FORMAT:
Return numeric value (0-100) representing percentage.
""",
        }

    def _get_generic_prompt(self) -> str:
        """Get generic extraction prompt for unknown attribute types."""
        return """
TASK: Extract the requested attribute from the clinical trial data.

INSTRUCTIONS:
1. Read the provided context carefully
2. Look for information related to the requested attribute
3. Extract the most relevant and accurate information
4. If not found, return empty string ""
5. Maintain the original format and precision of the data

OUTPUT FORMAT:
Return the extracted value as a string or number.
"""

    def _format_context(self, context: list[Any]) -> str:
        """Format context chunks for inclusion in prompts.

        Args:
            context: List of context chunk objects (ChunkWithEmbedding or strings)

        Returns:
            Formatted context string
        """
        if not context:
            return "No context available."

        formatted_chunks = []
        for i, chunk in enumerate(context, 1):
            # Handle both ChunkWithEmbedding objects and strings
            if hasattr(chunk, "content"):
                chunk_text = chunk.content
            else:
                chunk_text = str(chunk)

            formatted_chunks.append(f"[Context {i}]\n{chunk_text.strip()}\n")

        return "\n".join(formatted_chunks)
