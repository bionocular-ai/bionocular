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

        # Section awareness prefix for numeric attributes
        self.numeric_section_prefix = """
⚠️ SECTION AWARENESS:
- PREFER: Results, Conclusions, Study Results sections, or Tables
- USE CAREFULLY: Background section (may contain current study data OR citations to other studies)
- When multiple sections have the value, prefer Results/Conclusions over Background
- Prioritize table data when available

"""

        # Verification prefix for survival metrics to prevent contamination
        self.survival_verification_prefix = """
🔍 CRITICAL VERIFICATION - PREVENT VALUE CONTAMINATION:
Clinical trials report DIFFERENT survival metrics (PFS, RFS, OS, EFS, MFS).
Each metric is INDEPENDENT and has its OWN values.

COMMON CONTAMINATION ERROR (DO NOT DO THIS):
❌ Context mentions "hazard ratio for RFS was 0.56"
   Asked to extract: HR for PFS
   WRONG: Extracting "0.56" (this is RFS, not PFS!)
   CORRECT: Return "Not found" (PFS not mentioned, only RFS)

VERIFICATION REQUIREMENT:
"""

        # Verification prefix for arm-specific values to prevent total/other arm contamination
        self.arm_specific_verification_prefix = """
⚠️ ARM-SPECIFIC VERIFICATION:
✓ Extract ONLY arm-specific value (e.g., "pembrolizumab N=514")
✗ NOT study totals (e.g., "1019 randomized")
✗ NOT other arm values
Pattern: Value MUST be near arm name ("arm_name N=###", "arm: N=###")
"""
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

        # Add verification prefix for arm-specific attributes to prevent contamination
        if self._needs_arm_specific_verification(attribute_type):
            base_prompt = self.arm_specific_verification_prefix + base_prompt

        # Add verification prefix for survival metrics to prevent contamination
        elif self._needs_survival_verification(attribute_type):
            verification_rules = self._get_survival_verification_rules(attribute_type)
            base_prompt = (
                self.survival_verification_prefix
                + verification_rules
                + "\n"
                + base_prompt
            )

        # Add section awareness prefix for numeric attributes
        if self._is_numeric_attribute(attribute_type):
            base_prompt = self.numeric_section_prefix + base_prompt

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
        """Initialize streamlined extraction prompts.

        IMPORTANT EXTRACTION GUIDELINES:
        - Numeric attributes: Prefer Results, Conclusions, Study Results sections, or Tables
        - Background section may contain current study data, but use carefully
        - Prioritize data from tables when available
        - Non-numeric attributes: Can be extracted from any section
        """
        return {
            # General Parameters
            AttributeType.ABSTRACT_NUMBER: "Extract abstract number. Look for '### Abstract ID: [NUMBER]' pattern. Return just the number.",
            AttributeType.COMMENTS: "Extract full text availability statements. Look for 'meetings.asco.org', 'Journal of Clinical Oncology'. Return complete statement or empty string.",
            AttributeType.TRIAL_NAME: "Extract trial name. Look for 'Keynote-', 'Checkmate-', 'Masterkey-' patterns. Return full name or 'No Name'.",
            AttributeType.CANCER_TYPE: "Extract cancer type from controlled vocabulary: Resected Cutaneous Melanoma, Unresectable Cutaneous Melanoma, Cutaneous melanoma with Brain metastasis, Cutaneous Melanoma with CNS metastasis, Uveal Melanoma, Mucosal Melanoma, Acral Melanoma, Basal Cell Carcinoma, Merkel Cell Carcinoma, Cutaneous Squamous Cell Carcinoma.",
            AttributeType.NCT_NUMBER: "Extract NCT number. Look for 'NCT' followed by 8 digits. Return exactly as found or empty string.",
            # Treatment Details
            AttributeType.BRAND_NAME: "Extract brand names (e.g., Keytruda, Opdivo, Yervoy). Return commercial names or empty string.",
            AttributeType.GENERIC_NAME: "Extract generic drug names. For combinations use 'Drug A + Drug B' format. Include dose if specified (e.g., 'Nivolumab 1mg/kg').",
            AttributeType.TYPE_OF_THERAPY: "Extract therapy type: Immunotherapy, Cellular therapy, Targeted Therapy, Oncolytic Virus, Chemotherapy.",
            AttributeType.SUB_THERAPY: "Extract sub-therapy from controlled vocabulary: Immune Checkpoint Inhibitor/Antibody, Vaccine/Immunostimulant, Bispecific, CAR-T, NK-Cell, Myeloid Cells, TIL Therapy, Antibody, Tyrosine kinase inhibitor, Angiogenesis inhibitor, Antibody-Drug Conjugate, Oncolytic Virus, Chemotherapy.",
            AttributeType.MEDIAN_AGE: "Extract median age in years. Look for 'median age', 'age range'. Return number only (e.g., '65').",
            AttributeType.NUMBER_OF_PATIENTS: """Extract the number of patients in this specific treatment arm. Look for 'N=' or 'n=' immediately after the arm name. Return integer only.""",
            # Efficacy - Response Rates
            AttributeType.OBJECTIVE_RESPONSE_RATE: "Extract ORR percentage. Look for 'Objective response rate', 'ORR'. Return number only (e.g., '25' not '25%'). If not given, calculate: (CR + PR) / Total Patients.",
            AttributeType.COMPLETE_RESPONSE: "Extract Complete Response percentage. Look for 'Complete Response', 'CR'. Return number only.",
            AttributeType.PATHOLOGICAL_COMPLETE_RESPONSE: "Extract Pathological Complete Response percentage. Look for 'pCR', 'pathological CR'. Return number only.",
            AttributeType.COMPLETE_METABOLIC_RESPONSE: "Extract Complete Metabolic Response percentage. Look for 'CMR', 'metabolic response'. Return number only.",
            AttributeType.DISEASE_CONTROL_RATE: "Extract Disease Control Rate percentage. Look for 'DCR', 'disease control'. Return number only. If not given, calculate: (CR + PR + SD) / Total Patients.",
            AttributeType.CLINICAL_BENEFIT_RATE: "Extract Clinical Benefit Rate percentage. Look for 'CBR', 'clinical benefit'. Return number only.",
            AttributeType.MEDIAN_DOR: "Extract median Duration of Response in months. Look for 'DOR', 'duration of response'. Return number or 'NR' if not reached.",
            AttributeType.DOR_RATE: "Extract DOR rate percentage at specific timepoints. Look for 'DOR rate', 'duration rate'. Return number only.",
            # Efficacy - Survival Metrics (PFS Family)
            # NOTE: PFS is PROGRESSION-free survival, used in advanced/metastatic disease
            # DO NOT confuse with RFS (recurrence-free), EFS (event-free), or MFS (metastasis-free)
            AttributeType.MEDIAN_PFS: """Extract median progression-free survival (PFS) in months. Return numeric value or 'NR' if not reached. Return empty string if not found.""",
            AttributeType.MEDIAN_FOLLOWUP_PFS: "Extract median follow-up time for PFS measurement in months. Look for 'follow-up for PFS', 'PFS follow-up'. Verify 'PFS' is mentioned. Return number only or empty string.",
            AttributeType.P_VALUE_PFS: "Extract p-value for PFS. Look for 'p-value for PFS', 'PFS p-value'. Verify 'PFS' is mentioned. Return decimal value or significance level: Non-Significant (p>0.05), Significant (p≤0.05), Highly Significant (p≤0.001).",
            AttributeType.HR_PFS: "Extract Hazard Ratio for PFS. Look for 'HR for PFS', 'PFS HR'. Verify 'PFS' is mentioned. Return decimal value (e.g., '0.65') or empty string.",
            AttributeType.MEDIAN_OS: "Extract median OS in months. Look for 'median OS', 'mOS', 'overall survival'. Return number or 'NR' if not reached.",
            AttributeType.MEDIAN_FOLLOWUP_OS: "Extract median follow-up time for OS measurement in months. Look for 'follow-up for OS', 'OS follow-up'. Return number only.",
            AttributeType.P_VALUE_OS: "Extract p-value for OS. Look for 'p-value for OS', 'OS p-value'. Return decimal value or significance level: Non-Significant (p>0.05), Significant (p≤0.05), Highly Significant (p≤0.001).",
            AttributeType.HR_OS: "Extract Hazard Ratio for OS. Look for 'HR for OS', 'OS HR'. Return decimal value (e.g., '0.65').",
            # PFS Rate Timepoints
            AttributeType.PFS_RATE_6M: "Extract 6-month PFS rate percentage. Look for '6-month PFS', 'PFS at 6 months'. Return number only.",
            AttributeType.PFS_RATE_9M: "Extract 9-month PFS rate percentage. Look for '9-month PFS', 'PFS at 9 months'. Return number only.",
            AttributeType.PFS_RATE_12M: "Extract 12-month PFS rate percentage. Look for '12-month PFS', '1-year PFS', 'PFS at 12 months'. Return number only.",
            AttributeType.PFS_RATE_18M: "Extract 18-month PFS rate percentage. Look for '18-month PFS', 'PFS at 18 months'. Return number only.",
            AttributeType.PFS_RATE_24M: "Extract 24-month PFS rate percentage. Look for '24-month PFS', '2-year PFS', 'PFS at 24 months'. Return number only.",
            AttributeType.PFS_RATE_36M: "Extract 36-month PFS rate percentage. Look for '36-month PFS', '3-year PFS', 'PFS at 36 months'. Return number only.",
            AttributeType.PFS_RATE_48M: "Extract 48-month PFS rate percentage. Look for '48-month PFS', '4-year PFS', 'PFS at 48 months'. Return number only.",
            # OS Rate Timepoints
            AttributeType.OS_RATE_6M: "Extract 6-month OS rate percentage. Look for '6-month OS', 'OS at 6 months'. Return number only.",
            AttributeType.OS_RATE_9M: "Extract 9-month OS rate percentage. Look for '9-month OS', 'OS at 9 months'. Return number only.",
            AttributeType.OS_RATE_12M: "Extract 12-month OS rate percentage. Look for '12-month OS', '1-year OS', 'OS at 12 months'. Return number only.",
            AttributeType.OS_RATE_18M: "Extract 18-month OS rate percentage. Look for '18-month OS', 'OS at 18 months'. Return number only.",
            AttributeType.OS_RATE_24M: "Extract 24-month OS rate percentage. Look for '24-month OS', '2-year OS', 'OS at 24 months'. Return number only.",
            AttributeType.OS_RATE_36M: "Extract 36-month OS rate percentage. Look for '36-month OS', '3-year OS', 'OS at 36 months'. Return number only.",
            AttributeType.OS_RATE_48M: "Extract 48-month OS rate percentage. Look for '48-month OS', '4-year OS', 'OS at 48 months'. Return number only.",
            # EFS Family
            # NOTE: EFS is EVENT-free survival (any event: progression, recurrence, death)
            # Typically used in pediatric oncology and some adjuvant trials
            AttributeType.EFS: """Extract median event-free survival (EFS) in months. Return numeric value or 'NR' if not reached. Return empty string if not found.""",
            AttributeType.P_VALUE_EFS: "Extract p-value for EFS. Look for 'p-value for EFS', 'EFS p-value'. Verify 'EFS' is mentioned. Return decimal value or significance level.",
            AttributeType.HR_EFS: "Extract Hazard Ratio for EFS. Look for 'HR for EFS', 'EFS HR'. Verify 'EFS' is mentioned. Return decimal value (e.g., '0.65') or empty string.",
            # RFS Family
            # NOTE: RFS is RECURRENCE-free survival (post-surgery recurrence)
            # Typically used in adjuvant therapy trials after surgical resection
            AttributeType.RFS: """Extract median recurrence-free survival (RFS) in months. Return numeric value or 'NR' if not reached. Return empty string if not found.""",
            AttributeType.P_VALUE_RFS: "Extract p-value for RFS. Look for 'p-value for RFS', 'RFS p-value'. Verify 'RFS' is mentioned. Return decimal value or significance level.",
            AttributeType.LENGTH_RFS: "Extract follow-up duration for RFS measurement in months. Look for 'follow-up for RFS', 'RFS follow-up', 'observation period'. Verify 'RFS' is mentioned. Return number only or empty string.",
            AttributeType.HR_RFS: "Extract Hazard Ratio for RFS. Look for 'HR for RFS', 'RFS HR'. Verify 'RFS' is mentioned. Return decimal value (e.g., '0.56') or empty string.",
            # MFS Family
            # NOTE: MFS is METASTASIS-free survival (distant metastasis)
            # Typically used in localized/regional disease trials
            AttributeType.MFS: """Extract median metastasis-free survival (MFS/DMFS) in months. Return numeric value or 'NR' if not reached. Return empty string if not found.""",
            AttributeType.LENGTH_MFS: "Extract follow-up duration for MFS measurement in months. Look for 'follow-up for MFS', 'MFS follow-up', 'observation period'. Verify 'MFS' is mentioned. Return number only or empty string.",
            AttributeType.HR_MFS: "Extract Hazard Ratio for MFS. Look for 'HR for MFS', 'MFS HR'. Verify 'MFS' is mentioned. Return decimal value (e.g., '0.55') or empty string.",
            # Time-to Metrics
            AttributeType.TTR: "Extract Time to Response in months. Look for 'median TTR', 'time to response'. Return number or 'NR' if not reached.",
            AttributeType.TTP: "Extract Time to Progression in months. Look for 'median TTP', 'time to progression'. Return number or 'NR' if not reached.",
            AttributeType.TTNT: "Extract Time to Next Treatment in months. Look for 'median TTNT', 'time to next treatment'. Return number or 'NR' if not reached.",
            AttributeType.TTF: "Extract Time to Treatment Failure in months. Look for 'median TTF', 'time to treatment failure'. Return number or 'NR' if not reached.",
            # Safety - Adverse Events
            AttributeType.AE: "Extract overall Adverse Events percentage. Look for 'adverse events', 'AEs', 'any grade AE'. Extract from parentheses (e.g., '125 (85%)' → '85').",
            AttributeType.GRADE_3_PLUS_AE: "Extract Grade 3+ AE percentage. Look for 'Grade 3+', 'Grade 3 or higher', 'Grade 3 higher'. Extract from parentheses. If not given, sum Grade 3 + Grade 4 + Grade 5.",
            AttributeType.AE_LEADING_TO_DISCONTINUATION: "Extract AE leading to discontinuation percentage. Look for 'AE leading to discontinuation', 'discontinuation due to AE'. Extract from parentheses. 'No treatment discontinuation' → '0'.",
            AttributeType.SERIOUS_AE: "Extract Serious AE percentage. Look for 'serious adverse events', 'SAE', 'serious AE'. Extract from parentheses.",
            AttributeType.IMMUNE_RELATED_AE: "Extract Immune Related AE percentage. Look for 'immune related AE', 'irAE', 'immune adverse events'. Extract from parentheses.",
            AttributeType.SERIOUS_IMMUNE_RELATED_AE: "Extract Serious Immune Related AE percentage. Look for 'serious immune related AE', 'serious irAE'. Extract from parentheses.",
            AttributeType.AE_LEADING_TO_DEATH: "Extract AE leading to death percentage. Look for 'AE leading to death', 'death due to AE', 'fatal AE'. Extract from parentheses.",
            # Safety - Treatment-Emergent Adverse Events (TEAE)
            AttributeType.TEAE: "Extract Treatment-Emergent AE percentage. Look for 'treatment-emergent adverse events', 'TEAE', 'treatment emergent AE'. Extract from parentheses (e.g., '125 (85%)' → '85').",
            AttributeType.GRADE_3_PLUS_TEAE: "Extract Grade 3+ TEAE percentage. Look for 'Grade 3+ TEAE', 'Grade 3 or higher TEAE'. Extract from parentheses. If not given, sum Grade 3 + Grade 4 + Grade 5 TEAE.",
            AttributeType.GRADE_3_TEAE: "Extract Grade 3 TEAE percentage. Look for 'Grade 3 TEAE', 'Grade 3 treatment-emergent'. Extract from parentheses.",
            AttributeType.GRADE_4_TEAE: "Extract Grade 4 TEAE percentage. Look for 'Grade 4 TEAE', 'Grade 4 treatment-emergent'. Extract from parentheses.",
            AttributeType.GRADE_5_TEAE: "Extract Grade 5 TEAE percentage. Look for 'Grade 5 TEAE', 'Grade 5 treatment-emergent'. Extract from parentheses.",
            AttributeType.TEAE_LEADING_TO_DISCONTINUATION: "Extract TEAE leading to discontinuation percentage. Look for 'TEAE leading to discontinuation', 'discontinuation due to TEAE'. Extract from parentheses. 'No treatment discontinuation' → '0'.",
            AttributeType.TEAE_LEADING_TO_DEATH: "Extract TEAE leading to death percentage. Look for 'TEAE leading to death', 'death due to TEAE', 'fatal TEAE'. Extract from parentheses.",
            AttributeType.SERIOUS_TEAE: "Extract Serious TEAE percentage. Look for 'serious TEAE', 'serious treatment-emergent'. Extract from parentheses.",
            AttributeType.TEAE_IMMUNE_RELATED: "Extract TEAE Immune Related percentage. Look for 'TEAE immune related', 'immune related TEAE', 'irTEAE'. Extract from parentheses.",
            # Safety - Treatment-Related Adverse Events (TRAE)
            AttributeType.TRAE: "Extract Treatment-Related AE percentage. Look for 'treatment-related adverse events', 'TRAE', 'treatment related AE'. Extract from parentheses (e.g., '125 (85%)' → '85').",
            AttributeType.GRADE_3_PLUS_TRAE: "Extract Grade 3+ TRAE percentage. Look for 'Grade 3+ TRAE', 'Grade 3 or higher TRAE'. Extract from parentheses. If not given, sum Grade 3 + Grade 4 + Grade 5 TRAE.",
            AttributeType.GRADE_3_TRAE: "Extract Grade 3 TRAE percentage. Look for 'Grade 3 TRAE', 'Grade 3 treatment-related'. Extract from parentheses.",
            AttributeType.GRADE_4_TRAE: "Extract Grade 4 TRAE percentage. Look for 'Grade 4 TRAE', 'Grade 4 treatment-related'. Extract from parentheses.",
            AttributeType.GRADE_5_TRAE: "Extract Grade 5 TRAE percentage. Look for 'Grade 5 TRAE', 'Grade 5 treatment-related'. Extract from parentheses.",
            AttributeType.TRAE_LEADING_TO_DISCONTINUATION: "Extract TRAE leading to discontinuation percentage. Look for 'TRAE leading to discontinuation', 'discontinuation due to TRAE'. Extract from parentheses. 'No treatment discontinuation' → '0'.",
            AttributeType.TRAE_LEADING_TO_DEATH: "Extract TRAE leading to death percentage. Look for 'TRAE leading to death', 'death due to TRAE', 'fatal TRAE'. Extract from parentheses.",
            AttributeType.SERIOUS_TRAE: "Extract Serious TRAE percentage. Look for 'serious TRAE', 'serious treatment-related'. Extract from parentheses.",
            AttributeType.TRAE_IMMUNE_RELATED: "Extract TRAE Immune Related percentage. Look for 'TRAE immune related', 'immune related TRAE', 'irTRAE'. Extract from parentheses.",
            # Safety - Specific Adverse Events
            AttributeType.CRS: "Extract Cytokine Release Syndrome percentage. Look for 'Cytokine Release Syndrome', 'CRS', 'cytokine release'. Extract from parentheses.",
            AttributeType.WBC_DECREASED: "Extract WBC decreased percentage. Look for 'WBC decreased', 'white blood cell decreased', 'leukopenia'. Extract from parentheses.",
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

    def _is_numeric_attribute(self, attribute_type: AttributeType) -> bool:
        """Determine if an attribute is numeric (should extract from Results/Conclusions only).

        Args:
            attribute_type: Type of attribute to check

        Returns:
            True if numeric attribute, False otherwise
        """
        # Non-numeric attributes (can extract from any section)
        non_numeric_attributes = {
            AttributeType.ABSTRACT_NUMBER,
            AttributeType.COMMENTS,
            AttributeType.TRIAL_NAME,
            AttributeType.CANCER_TYPE,
            AttributeType.NCT_NUMBER,
            AttributeType.BRAND_NAME,
            AttributeType.GENERIC_NAME,
            AttributeType.TYPE_OF_THERAPY,
            AttributeType.SUB_THERAPY,
        }

        # If it's in the non-numeric list, return False
        # Otherwise, assume it's numeric (most attributes are numeric)
        return attribute_type not in non_numeric_attributes

    def _needs_arm_specific_verification(self, attribute_type: AttributeType) -> bool:
        """Determine if attribute needs arm-specific verification to prevent contamination.

        Arm-specific values (like number of patients per arm) are easily contaminated
        by study-level totals or values from other arms.

        Args:
            attribute_type: Type of attribute to check

        Returns:
            True if attribute needs arm-specific verification, False otherwise
        """
        # Attributes that need arm-specific verification
        arm_specific_attributes = {
            AttributeType.NUMBER_OF_PATIENTS,
            # Could add more arm-specific attributes here if needed
            # AttributeType.MEDIAN_AGE,  # Usually study-level, but could be arm-specific
        }

        return attribute_type in arm_specific_attributes

    def _needs_survival_verification(self, attribute_type: AttributeType) -> bool:
        """Determine if attribute needs survival metric verification to prevent contamination.

        Survival metrics (PFS, OS, RFS, EFS, MFS) are easily confused and values can
        contaminate each other (e.g., HR_RFS value incorrectly extracted as HR_PFS).

        Args:
            attribute_type: Type of attribute to check

        Returns:
            True if attribute needs verification, False otherwise
        """
        # Attributes that need verification (survival-related metrics)
        survival_attributes = {
            # Hazard Ratios
            AttributeType.HR_PFS,
            AttributeType.HR_OS,
            AttributeType.HR_EFS,
            AttributeType.HR_RFS,
            AttributeType.HR_MFS,
            # P-values
            AttributeType.P_VALUE_PFS,
            AttributeType.P_VALUE_OS,
            AttributeType.P_VALUE_EFS,
            AttributeType.P_VALUE_RFS,
            # Median values
            AttributeType.MEDIAN_PFS,
            AttributeType.MEDIAN_OS,
            AttributeType.EFS,
            AttributeType.RFS,
            AttributeType.MFS,
            # Follow-up times
            AttributeType.MEDIAN_FOLLOWUP_PFS,
            AttributeType.MEDIAN_FOLLOWUP_OS,
            AttributeType.LENGTH_RFS,
            AttributeType.LENGTH_MFS,
            # Rate timepoints (these are less contamination-prone but included for consistency)
            AttributeType.PFS_RATE_6M,
            AttributeType.PFS_RATE_9M,
            AttributeType.PFS_RATE_12M,
            AttributeType.PFS_RATE_18M,
            AttributeType.PFS_RATE_24M,
            AttributeType.PFS_RATE_36M,
            AttributeType.PFS_RATE_48M,
            AttributeType.OS_RATE_6M,
            AttributeType.OS_RATE_9M,
            AttributeType.OS_RATE_12M,
            AttributeType.OS_RATE_18M,
            AttributeType.OS_RATE_24M,
            AttributeType.OS_RATE_36M,
            AttributeType.OS_RATE_48M,
        }

        return attribute_type in survival_attributes

    def _get_survival_verification_rules(self, attribute_type: AttributeType) -> str:
        """Get specific verification rules for survival metric attributes.

        Args:
            attribute_type: Type of attribute

        Returns:
            Verification rules string
        """
        verification_rules = {
            # Hazard Ratio verification rules
            AttributeType.HR_PFS: """
✓ Context MUST explicitly mention "PFS" or "progression-free survival"
✓ Look for "HR for PFS", "PFS HR", "hazard ratio for progression-free survival"
✗ DO NOT extract if you only see: RFS, OS, EFS, MFS, or other survival metrics
✗ If context only has "hazard ratio" without specifying PFS, return "Not found"
""",
            AttributeType.HR_OS: """
✓ Context MUST explicitly mention "OS" or "overall survival"
✓ Look for "HR for OS", "OS HR", "hazard ratio for overall survival"
✗ DO NOT extract if you only see: PFS, RFS, EFS, MFS, or other survival metrics
✗ If context only has "hazard ratio" without specifying OS, return "Not found"
""",
            AttributeType.HR_RFS: """
✓ Context MUST explicitly mention "RFS", "recurrence-free survival", or "relapse-free survival"
✓ Look for "HR for RFS", "RFS HR", "hazard ratio for recurrence-free survival"
✗ DO NOT extract if you only see: PFS, OS, EFS, MFS, or other survival metrics
✗ If context only has "hazard ratio" without specifying RFS, return "Not found"
""",
            AttributeType.HR_EFS: """
✓ Context MUST explicitly mention "EFS" or "event-free survival"
✓ Look for "HR for EFS", "EFS HR", "hazard ratio for event-free survival"
✗ DO NOT extract if you only see: PFS, OS, RFS, MFS, or other survival metrics
✗ If context only has "hazard ratio" without specifying EFS, return "Not found"
""",
            AttributeType.HR_MFS: """
✓ Context MUST explicitly mention "MFS", "DMFS", or "metastasis-free survival"
✓ Look for "HR for MFS", "MFS HR", "hazard ratio for metastasis-free survival"
✗ DO NOT extract if you only see: PFS, OS, RFS, EFS, or other survival metrics
✗ If context only has "hazard ratio" without specifying MFS/DMFS, return "Not found"
""",
            # P-value verification rules
            AttributeType.P_VALUE_PFS: """
✓ Context MUST explicitly mention "PFS" or "progression-free survival" WITH the p-value
✓ Look for "p-value for PFS", "PFS p=", "PFS p<", "PFS: p="
✗ DO NOT extract p-value if it's associated with RFS, OS, EFS, or MFS
✗ If you see "p<0.001" but it's for RFS (not PFS), return "Not found"
""",
            AttributeType.P_VALUE_OS: """
✓ Context MUST explicitly mention "OS" or "overall survival" WITH the p-value
✓ Look for "p-value for OS", "OS p=", "OS p<", "OS: p="
✗ DO NOT extract p-value if it's associated with PFS, RFS, EFS, or MFS
✗ If you see "p<0.001" but it's for PFS (not OS), return "Not found"
""",
            AttributeType.P_VALUE_RFS: """
✓ Context MUST explicitly mention "RFS" or "recurrence-free survival" WITH the p-value
✓ Look for "p-value for RFS", "RFS p=", "RFS p<", "RFS: p="
✗ DO NOT extract p-value if it's associated with PFS, OS, EFS, or MFS
✗ If you see "p<0.001" but it's for PFS (not RFS), return "Not found"
""",
            AttributeType.P_VALUE_EFS: """
✓ Context MUST explicitly mention "EFS" or "event-free survival" WITH the p-value
✓ Look for "p-value for EFS", "EFS p=", "EFS p<", "EFS: p="
✗ DO NOT extract p-value if it's associated with PFS, OS, RFS, or MFS
✗ If you see "p<0.001" but it's for PFS (not EFS), return "Not found"
""",
            # Median survival verification rules
            AttributeType.MEDIAN_PFS: """
✓ Context MUST explicitly mention "median PFS" or "mPFS" or "progression-free survival"
✓ Must be specifically for PFS, not RFS/OS/EFS/MFS
✗ DO NOT extract median values for other survival metrics (RFS, OS, EFS, MFS)
✗ If context says "median RFS" (not PFS), return "Not found"
""",
            AttributeType.MEDIAN_OS: """
✓ Context MUST explicitly mention "median OS" or "mOS" or "overall survival"
✓ Must be specifically for OS, not PFS/RFS/EFS/MFS
✗ DO NOT extract median values for other survival metrics (PFS, RFS, EFS, MFS)
✗ If context says "median PFS" (not OS), return "Not found"
""",
            AttributeType.RFS: """
✓ Context MUST explicitly mention "median RFS" or "mRFS" or "recurrence-free survival"
✓ Must be specifically for RFS, not PFS/OS/EFS/MFS
✗ DO NOT extract median values for other survival metrics (PFS, OS, EFS, MFS)
✗ If context says "median PFS" (not RFS), return "Not found"
""",
            AttributeType.EFS: """
✓ Context MUST explicitly mention "median EFS" or "mEFS" or "event-free survival"
✓ Must be specifically for EFS, not PFS/OS/RFS/MFS
✗ DO NOT extract median values for other survival metrics (PFS, OS, RFS, MFS)
✗ If context says "median PFS" (not EFS), return "Not found"
""",
            AttributeType.MFS: """
✓ Context MUST explicitly mention "median MFS/DMFS" or "mMFS" or "metastasis-free survival"
✓ Must be specifically for MFS/DMFS, not PFS/OS/RFS/EFS
✗ DO NOT extract median values for other survival metrics (PFS, OS, RFS, EFS)
✗ If context says "median PFS" (not MFS), return "Not found"
""",
            # Follow-up time verification rules
            AttributeType.MEDIAN_FOLLOWUP_PFS: """
✓ Context MUST mention "follow-up" specifically in relation to "PFS"
✓ Look for "follow-up for PFS", "PFS follow-up", "median follow-up for PFS assessment"
✗ DO NOT extract follow-up times not associated with PFS
✗ General "median follow-up" without PFS specification → "Not found"
""",
            AttributeType.MEDIAN_FOLLOWUP_OS: """
✓ Context MUST mention "follow-up" specifically in relation to "OS"
✓ Look for "follow-up for OS", "OS follow-up", "median follow-up for OS assessment"
✗ DO NOT extract follow-up times not associated with OS
✗ General "median follow-up" without OS specification → "Not found"
""",
            AttributeType.LENGTH_RFS: """
✓ Context MUST mention "follow-up" or "observation period" in relation to "RFS"
✓ Look for "RFS follow-up", "follow-up for RFS measurement"
✗ DO NOT extract follow-up times not associated with RFS
""",
            AttributeType.LENGTH_MFS: """
✓ Context MUST mention "follow-up" or "observation period" in relation to "MFS"
✓ Look for "MFS follow-up", "follow-up for MFS measurement"
✗ DO NOT extract follow-up times not associated with MFS
""",
        }

        # For rate timepoints, use a generic verification rule
        if attribute_type in [
            AttributeType.PFS_RATE_6M,
            AttributeType.PFS_RATE_9M,
            AttributeType.PFS_RATE_12M,
            AttributeType.PFS_RATE_18M,
            AttributeType.PFS_RATE_24M,
            AttributeType.PFS_RATE_36M,
            AttributeType.PFS_RATE_48M,
        ]:
            timepoint = attribute_type.value.replace("PFS_RATE_", "").replace(
                "M", " month"
            )
            return f"""
✓ Context MUST mention "PFS" or "progression-free survival" at the {timepoint} timepoint
✓ Look for "PFS at {timepoint}", "{timepoint} PFS rate", "PFS rate at {timepoint}"
✗ DO NOT extract RFS/OS/EFS/MFS rates at this timepoint
✗ If context only has "{timepoint} RFS" (not PFS), return "Not found"
"""

        if attribute_type in [
            AttributeType.OS_RATE_6M,
            AttributeType.OS_RATE_9M,
            AttributeType.OS_RATE_12M,
            AttributeType.OS_RATE_18M,
            AttributeType.OS_RATE_24M,
            AttributeType.OS_RATE_36M,
            AttributeType.OS_RATE_48M,
        ]:
            timepoint = attribute_type.value.replace("OS_RATE_", "").replace(
                "M", " month"
            )
            return f"""
✓ Context MUST mention "OS" or "overall survival" at the {timepoint} timepoint
✓ Look for "OS at {timepoint}", "{timepoint} OS rate", "OS rate at {timepoint}"
✗ DO NOT extract PFS/RFS/EFS/MFS rates at this timepoint
✗ If context only has "{timepoint} PFS" (not OS), return "Not found"
"""

        return verification_rules.get(attribute_type, "")

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
