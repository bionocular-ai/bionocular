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

        # Verification prefix for arm-specific values to prevent total/other arm contamination
        # Note: This is still needed as it's about arm vs study-level, not metric contamination
        self.arm_specific_verification_prefix = """
⚠️ ARM-SPECIFIC VERIFICATION:
✓ For multi-arm studies: Extract ONLY arm-specific value (e.g., "pembrolizumab N=514")
✓ For single-arm studies: Extract the total enrolled and use the same value for all arms
✓ If you see only one total value (e.g., "n=60", "60 patients") and multiple arms listed, this is likely a single-arm study - use that total for all arms
✗ NOT study totals in multi-arm studies when arms have separate values (e.g., "1019 randomized" when arms have N=514 and N=505)
✗ NOT other arm values
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

The value should be the extracted value, or "Not found" if not available.
"""

    def _initialize_extraction_prompts(self) -> dict[AttributeType, str]:
        """Initialize streamlined extraction prompts.

        Note: Context is pre-filtered by 3-tier optimization (Tier 1-3),
        so prompts can focus on extraction logic rather than section awareness.
        """
        return {
            # General Parameters
            AttributeType.ABSTRACT_NUMBER: "Extract abstract number. Look for '### Abstract ID: [NUMBER]' pattern. The value should be just the number.",
            AttributeType.COMMENTS: "Extract full text availability statements from the full text reference section. Look for 'meetings.asco.org', 'Journal of Clinical Oncology', or similar publication references. If no full text reference section exists or no relevant statements are found, the value should be an empty string (\"\"). Do not include explanatory text.",
            # TRIAL_NAME - API-sourced, no prompt needed
            AttributeType.CANCER_TYPE: "Extract cancer type associated with the treatment. The value should be exactly one of these classes: Resected Cutaneous Melanoma, Unresectable Cutaneous Melanoma, Cutaneous melanoma with Brain metastasis, Cutaneous Melanoma with CNS metastasis, Uveal Melanoma, Mucosal Melanoma, Acral Melanoma, Basal Cell Carcinoma, Merkel Cell Carcinoma, Cutaneous Squamous Cell Carcinoma. Match the most specific applicable type from the abstract.",
            AttributeType.CANCER_STAGE: "Extract cancer stage. The value should be exactly one of these classes: Stage I, Stage I/II, Stage II, Stage II/III, Stage III, Stage III/Stage IV, Stage IV. Match the most specific applicable stage from the abstract, or empty string if not found.",
            AttributeType.NCT_NUMBER: "Extract clinical trial identifier from 'Clinical trial identification:' or 'Clinical Trial Information:' section. Priority: NCT number (NCT + 8 digits), then EudraCT, then other identifiers. Return exactly as found or empty string.",
            # AttributeType.SPONSORS: "Extract research sponsor(s) from Research Sponsor or Funding sections. Look for 'Research Sponsor:', 'Lead Sponsor:', 'sponsor', or funding organization names. The value should be the sponsor name(s) or empty string if not found.",
            # SPONSORS - API-sourced, no prompt needed (extracted from Clinical Trials API)
            # Treatment Details
            AttributeType.BRAND_NAME: "Extract brand names (e.g., Keytruda, Opdivo, Yervoy). The value should be commercial names or empty string.",
            AttributeType.GENERIC_NAME: "Extract generic drug names. For combinations use 'Drug A + Drug B' format. Include dose if specified (e.g., 'Nivolumab 1mg/kg').",
            AttributeType.TYPE_OF_THERAPY: "Extract therapy type: Immunotherapy, Cellular therapy, Targeted Therapy, Oncolytic Virus, Chemotherapy.",
            AttributeType.MECHANISM_OF_ACTION: "Extract mechanism of action. Look for descriptions of how the drug works, such as 'PD-1 inhibitor', 'CTLA-4 blocker', 'BRAF inhibitor', 'MEK inhibitor', 'anti-angiogenic', 'immune checkpoint blockade', or similar mechanisms. The value should be the mechanism of action described in the abstract.",
            AttributeType.TARGET_PROTEIN: "Extract target protein. Look for protein targets such as 'PD-1', 'PD-L1', 'CTLA-4', 'BRAF', 'MEK', 'VEGF', 'EGFR', 'HER2', or similar protein targets. The value should be the target protein(s) mentioned in the abstract.",
            AttributeType.SUB_THERAPY: "Extract sub-therapy from controlled vocabulary: Immune Checkpoint Inhibitor/Antibody, Vaccine/Immunostimulant, Bispecific, CAR-T, NK-Cell, Myeloid Cells, TIL Therapy, Antibody, Tyrosine kinase inhibitor, Angiogenesis inhibitor, Antibody-Drug Conjugate, Oncolytic Virus, Chemotherapy.",
            # CLINICAL_TRIAL_PHASE - API-sourced, no prompt needed
            AttributeType.BIOSIMILAR: "Extract whether the drug is a biosimilar. Look for 'biosimilar', 'biosimilar to', or similar terms. The value should be 'true' if biosimilar is mentioned, 'false' if explicitly stated as not biosimilar, or empty string if not mentioned.",
            AttributeType.MEDIAN_AGE: "Extract median age in years. Look for 'median age', 'age range'. The value should be a number (e.g., '65').",
            AttributeType.NUMBER_OF_PATIENTS: "Extract the number of patients for this specific treatment arm. Look for 'N=', 'n=', 'patients', 'pts', 'enrolled', or similar patterns. For multi-arm studies, extract ONLY the value associated with this specific arm name. For single-arm studies, extract the total enrolled. The value should be an integer.",
            # Efficacy - Response Rates
            AttributeType.OBJECTIVE_RESPONSE_RATE: "Extract ORR percentage. Look for 'Objective response rate', 'ORR'. The value should be a number (e.g., '25'). If not given, calculate: (CR + PR) / Total Patients.",
            AttributeType.COMPLETE_RESPONSE: "Extract Complete Response percentage. Look for 'Complete Response', 'CR'. The value should be a number.",
            AttributeType.PATHOLOGICAL_COMPLETE_RESPONSE: "Extract Pathological Complete Response percentage. Look for 'pCR', 'pathological CR'. The value should be a number.",
            AttributeType.COMPLETE_METABOLIC_RESPONSE: "Extract Complete Metabolic Response percentage. Look for 'CMR', 'metabolic response'. The value should be a number.",
            AttributeType.DISEASE_CONTROL_RATE: "Extract Disease Control Rate percentage. Look for 'DCR', 'disease control'. The value should be a number. If not given, calculate: (CR + PR + SD) / Total Patients.",
            AttributeType.CLINICAL_BENEFIT_RATE: "Extract Clinical Benefit Rate percentage. Look for 'CBR', 'clinical benefit'. The value should be a number.",
            AttributeType.MEDIAN_DOR: "Extract median Duration of Response in months. Look for 'DOR', 'duration of response'. The value should be a number in months, or 'NR' if not reached.",
            AttributeType.DOR_RATE: "Extract DOR rate percentage at specific timepoints. Look for 'DOR rate', 'duration rate'. The value should be a number.",
            # Efficacy - Survival Metrics (PFS Family)
            AttributeType.MEDIAN_PFS: "Extract median PFS in months. The value should be a number in months, or 'NR' if not reached.",
            AttributeType.MEDIAN_FOLLOWUP_PFS: "Extract median follow-up time for PFS in months. The value should be a number.",
            AttributeType.P_VALUE_PFS: "Extract p-value for PFS. The value should be a decimal number or significance level: Non-Significant (p>0.05), Significant (p≤0.05), Highly Significant (p≤0.001).",
            AttributeType.HR_PFS: "Extract Hazard Ratio for PFS. The value should be a decimal number (e.g., '0.65').",
            # OS Family
            AttributeType.MEDIAN_OS: "Extract median OS in months. Look for 'median OS', 'mOS', 'overall survival'. The value should be a number in months, or 'NR' if not reached.",
            AttributeType.MEDIAN_FOLLOWUP_OS: "Extract median follow-up time for OS measurement in months. Look for 'follow-up for OS', 'OS follow-up'. The value should be a number.",
            AttributeType.P_VALUE_OS: "Extract p-value for OS. Look for 'p-value for OS', 'OS p-value'. The value should be a decimal number or significance level: Non-Significant (p>0.05), Significant (p≤0.05), Highly Significant (p≤0.001).",
            AttributeType.HR_OS: "Extract Hazard Ratio for OS. Look for 'HR for OS', 'OS HR'. The value should be a decimal number (e.g., '0.65').",
            # PFS Rate Timepoints
            AttributeType.PFS_RATE_6M: "Extract 6-month PFS rate percentage. Look for '6-month PFS', 'PFS at 6 months'. The value should be a number.",
            AttributeType.PFS_RATE_9M: "Extract 9-month PFS rate percentage. Look for '9-month PFS', 'PFS at 9 months'. The value should be a number.",
            AttributeType.PFS_RATE_12M: "Extract 12-month PFS rate percentage. Look for '12-month PFS', '1-year PFS', 'PFS at 12 months'. The value should be a number.",
            AttributeType.PFS_RATE_18M: "Extract 18-month PFS rate percentage. Look for '18-month PFS', 'PFS at 18 months'. The value should be a number.",
            AttributeType.PFS_RATE_24M: "Extract 24-month PFS rate percentage. Look for '24-month PFS', '2-year PFS', 'PFS at 24 months'. The value should be a number.",
            AttributeType.PFS_RATE_36M: "Extract 36-month PFS rate percentage. Look for '36-month PFS', '3-year PFS', 'PFS at 36 months'. The value should be a number.",
            AttributeType.PFS_RATE_48M: "Extract 48-month PFS rate percentage. Look for '48-month PFS', '4-year PFS', 'PFS at 48 months'. The value should be a number.",
            # OS Rate Timepoints
            AttributeType.OS_RATE_6M: "Extract 6-month OS rate percentage. Look for '6-month OS', 'OS at 6 months'. The value should be a number.",
            AttributeType.OS_RATE_9M: "Extract 9-month OS rate percentage. Look for '9-month OS', 'OS at 9 months'. The value should be a number.",
            AttributeType.OS_RATE_12M: "Extract 12-month OS rate percentage. Look for '12-month OS', '1-year OS', 'OS at 12 months'. The value should be a number.",
            AttributeType.OS_RATE_18M: "Extract 18-month OS rate percentage. Look for '18-month OS', 'OS at 18 months'. The value should be a number.",
            AttributeType.OS_RATE_24M: "Extract 24-month OS rate percentage. Look for '24-month OS', '2-year OS', 'OS at 24 months'. The value should be a number.",
            AttributeType.OS_RATE_36M: "Extract 36-month OS rate percentage. Look for '36-month OS', '3-year OS', 'OS at 36 months'. The value should be a number.",
            AttributeType.OS_RATE_48M: "Extract 48-month OS rate percentage. Look for '48-month OS', '4-year OS', 'OS at 48 months'. The value should be a number.",
            # EFS Family (Event-Free Survival)
            AttributeType.EFS: "Extract median Event-Free Survival (EFS) in months. Look for 'median EFS', 'mEFS', 'event-free survival', 'event free survival', 'median event-free survival'. The value should be a number in months, or 'NR' if not reached.",
            AttributeType.P_VALUE_EFS: "Extract p-value for Event-Free Survival (EFS). Look for 'p-value for EFS', 'EFS p-value', 'p-value for event-free survival', 'event-free survival p-value', 'p value EFS'. The value should be a decimal number or significance level: Non-Significant (p>0.05), Significant (p≤0.05), Highly Significant (p≤0.001).",
            AttributeType.HR_EFS: "Extract Hazard Ratio (HR) for Event-Free Survival (EFS). Look for 'HR for EFS', 'EFS HR', 'hazard ratio for EFS', 'hazard ratio for event-free survival', 'EFS hazard ratio'. The value should be a decimal number (e.g., '0.65').",
            # RFS Family (Recurrence-Free Survival / Relapse-Free Survival)
            AttributeType.RFS: "Extract median Recurrence-Free Survival (RFS) in months. Look for 'median RFS', 'mRFS', 'recurrence-free survival', 'recurrence free survival', 'relapse-free survival', 'relapse free survival', 'median recurrence-free survival', 'median relapse-free survival'. The value should be a number in months, or 'NR' if not reached.",
            AttributeType.P_VALUE_RFS: "Extract p-value for Recurrence-Free Survival (RFS). Look for 'p-value for RFS', 'RFS p-value', 'p-value for recurrence-free survival', 'p-value for relapse-free survival', 'recurrence-free survival p-value', 'relapse-free survival p-value', 'p value RFS'. The value should be a decimal number or significance level: Non-Significant (p>0.05), Significant (p≤0.05), Highly Significant (p≤0.001).",
            AttributeType.LENGTH_RFS: "Extract follow-up duration for Recurrence-Free Survival (RFS) in months. Look for 'follow-up for RFS', 'RFS follow-up', 'follow-up for recurrence-free survival', 'follow-up for relapse-free survival', 'RFS follow-up duration', 'median follow-up RFS'. The value should be a number.",
            AttributeType.HR_RFS: "Extract Hazard Ratio (HR) for Recurrence-Free Survival (RFS). Look for 'HR for RFS', 'RFS HR', 'hazard ratio for RFS', 'hazard ratio for recurrence-free survival', 'hazard ratio for relapse-free survival', 'RFS hazard ratio'. The value should be a decimal number (e.g., '0.56').",
            # MFS Family (Metastasis-Free Survival)
            AttributeType.MFS: "Extract median Metastasis-Free Survival (MFS) in months. Look for 'median MFS', 'mMFS', 'metastasis-free survival', 'metastasis free survival', 'median metastasis-free survival'. The value should be a number in months, or 'NR' if not reached.",
            AttributeType.LENGTH_MFS: "Extract follow-up duration for Metastasis-Free Survival (MFS) in months. Look for 'follow-up for MFS', 'MFS follow-up', 'follow-up for metastasis-free survival', 'MFS follow-up duration', 'median follow-up MFS'. The value should be a number.",
            AttributeType.HR_MFS: "Extract Hazard Ratio (HR) for Metastasis-Free Survival (MFS). Look for 'HR for MFS', 'MFS HR', 'hazard ratio for MFS', 'hazard ratio for metastasis-free survival', 'MFS hazard ratio'. The value should be a decimal number (e.g., '0.55').",
            # Time-to Metrics
            AttributeType.TTR: "Extract Time to Response in months. Look for 'median TTR', 'time to response'. The value should be a number in months, or 'NR' if not reached.",
            AttributeType.TTP: "Extract Time to Progression in months. Look for 'median TTP', 'time to progression'. The value should be a number in months, or 'NR' if not reached.",
            AttributeType.TTNT: "Extract Time to Next Treatment in months. Look for 'median TTNT', 'time to next treatment'. The value should be a number in months, or 'NR' if not reached.",
            AttributeType.TTF: "Extract Time to Treatment Failure in months. Look for 'median TTF', 'time to treatment failure'. The value should be a number in months, or 'NR' if not reached.",
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
            # Publication-level metadata
            AttributeType.PUBLICATION_NAME: "Extract the journal name from citations (e.g., 'N Engl J Med 2010;363:711-23' → 'N Engl J Med' or 'New England Journal of Medicine'). Return empty string if not found.",
            AttributeType.PUBLICATION_YEAR: "Extract the 4-digit publication year from citations or publication dates (e.g., 'N Engl J Med 2010;363:711-23' → '2010'). Return empty string if not found.",
            # Safety - Grade 3+ AE Specific Adverse Events (General / Any Cause)
            AttributeType.GRADE_3_PLUS_AE_CRS: "Extract Grade 3+ Adverse Events (AE) Cytokine Release Syndrome (CRS) percentage. Look for 'Grade 3+ AE CRS', 'Grade 3+ adverse event CRS', 'Grade 3+ CRS', 'Grade 3-4 CRS', 'G3+ CRS', 'severe CRS', 'Grade 3+ safety CRS'. Extract from parentheses (e.g., '15 (10%)' → '10').",
            AttributeType.GRADE_3_PLUS_AE_THROMBOCYTOPENIA: "Extract Grade 3+ Adverse Events (AE) Thrombocytopenia percentage. Look for 'Grade 3+ AE thrombocytopenia', 'Grade 3+ adverse event thrombocytopenia', 'Grade 3+ thrombocytopenia', 'Grade 3-4 thrombocytopenia', 'G3+ thrombocytopenia', 'Grade 3+ platelet count decreased'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_AE_NEUTROPENIA: "Extract Grade 3+ Adverse Events (AE) Neutropenia percentage. Look for 'Grade 3+ AE neutropenia', 'Grade 3+ adverse event neutropenia', 'Grade 3+ neutropenia', 'Grade 3-4 neutropenia', 'G3+ neutropenia', 'Grade 3+ neutrophil count decreased'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_AE_LEUKOPENIA: "Extract Grade 3+ Adverse Events (AE) Leukopenia percentage. Look for 'Grade 3+ AE leukopenia', 'Grade 3+ adverse event leukopenia', 'Grade 3+ leukopenia', 'Grade 3-4 leukopenia', 'G3+ leukopenia'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_AE_NAUSEA: "Extract Grade 3+ Adverse Events (AE) Nausea percentage. Look for 'Grade 3+ AE nausea', 'Grade 3+ adverse event nausea', 'Grade 3+ nausea', 'Grade 3-4 nausea', 'G3+ nausea'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_AE_ANEMIA: "Extract Grade 3+ Adverse Events (AE) Anemia percentage. Look for 'Grade 3+ AE anemia', 'Grade 3+ adverse event anemia', 'Grade 3+ anemia', 'Grade 3-4 anemia', 'G3+ anemia', 'anaemia', 'Grade 3+ hemoglobin decreased', 'Grade 3+ HB decreased'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_AE_DIARRHEA: "Extract Grade 3+ Adverse Events (AE) Diarrhea percentage. Look for 'Grade 3+ AE diarrhea', 'Grade 3+ adverse event diarrhea', 'Grade 3+ diarrhea', 'Grade 3-4 diarrhea', 'G3+ diarrhea', 'diarrhoea'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_AE_COLITIS: "Extract Grade 3+ Adverse Events (AE) Colitis percentage. Look for 'Grade 3+ AE colitis', 'Grade 3+ adverse event colitis', 'Grade 3+ colitis', 'Grade 3-4 colitis', 'G3+ colitis'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_AE_HYPERGLYCEMIA: "Extract Grade 3+ Adverse Events (AE) Hyperglycemia percentage. Look for 'Grade 3+ AE hyperglycemia', 'Grade 3+ adverse event hyperglycemia', 'Grade 3+ hyperglycemia', 'Grade 3-4 hyperglycemia', 'G3+ hyperglycemia', 'hyperglycaemia'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_AE_NEUTROPHIL_COUNT_DECREASED: "Extract Grade 3+ Adverse Events (AE) Neutrophil count decreased percentage. Look for 'Grade 3+ AE neutrophil count decreased', 'Grade 3+ adverse event neutrophil count decreased', 'Grade 3+ neutrophil count decreased', 'Grade 3-4 neutrophil count decreased', 'G3+ neutrophil count decreased'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_AE_DYSPNEA: "Extract Grade 3+ Adverse Events (AE) Dyspnea percentage. Look for 'Grade 3+ AE dyspnea', 'Grade 3+ adverse event dyspnea', 'Grade 3+ dyspnea', 'Grade 3-4 dyspnea', 'G3+ dyspnea', 'dyspnoea', 'shortness of breath'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_AE_PYREXIA: "Extract Grade 3+ Adverse Events (AE) Pyrexia percentage. Look for 'Grade 3+ AE pyrexia', 'Grade 3+ adverse event pyrexia', 'Grade 3+ pyrexia', 'Grade 3-4 pyrexia', 'G3+ pyrexia', 'fever'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_AE_BLEEDING: "Extract Grade 3+ Adverse Events (AE) Bleeding percentage. Look for 'Grade 3+ AE bleeding', 'Grade 3+ adverse event bleeding', 'Grade 3+ bleeding', 'Grade 3-4 bleeding', 'G3+ bleeding', 'hemorrhage', 'haemorrhage'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_AE_PRURITUS: "Extract Grade 3+ Adverse Events (AE) Pruritus percentage. Look for 'Grade 3+ AE pruritus', 'Grade 3+ adverse event pruritus', 'Grade 3+ pruritus', 'Grade 3-4 pruritus', 'G3+ pruritus', 'itching'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_AE_RASH: "Extract Grade 3+ Adverse Events (AE) Rash percentage. Look for 'Grade 3+ AE rash', 'Grade 3+ adverse event rash', 'Grade 3+ rash', 'Grade 3-4 rash', 'G3+ rash'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_AE_PNEUMONIA: "Extract Grade 3+ Adverse Events (AE) Pneumonia percentage. Look for 'Grade 3+ AE pneumonia', 'Grade 3+ adverse event pneumonia', 'Grade 3+ pneumonia', 'Grade 3-4 pneumonia', 'G3+ pneumonia'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_AE_THYROIDITIS: "Extract Grade 3+ Adverse Events (AE) Thyroiditis percentage. Look for 'Grade 3+ AE thyroiditis', 'Grade 3+ adverse event thyroiditis', 'Grade 3+ thyroiditis', 'Grade 3-4 thyroiditis', 'G3+ thyroiditis'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_AE_HYPOPHYSITIS: "Extract Grade 3+ Adverse Events (AE) Hypophysitis percentage. Look for 'Grade 3+ AE hypophysitis', 'Grade 3+ adverse event hypophysitis', 'Grade 3+ hypophysitis', 'Grade 3-4 hypophysitis', 'G3+ hypophysitis'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_AE_HEPATITIS: "Extract Grade 3+ Adverse Events (AE) Hepatitis percentage. Look for 'Grade 3+ AE hepatitis', 'Grade 3+ adverse event hepatitis', 'Grade 3+ hepatitis', 'Grade 3-4 hepatitis', 'G3+ hepatitis'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_AE_PNEUMONITIS: "Extract Grade 3+ Adverse Events (AE) Pneumonitis percentage. Look for 'Grade 3+ AE pneumonitis', 'Grade 3+ adverse event pneumonitis', 'Grade 3+ pneumonitis', 'Grade 3-4 pneumonitis', 'G3+ pneumonitis', 'Grade 3+ interstitial lung disease', 'Grade 3+ ILD'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_AE_ALANINE_AMINOTRANSFERASE: "Extract Grade 3+ Adverse Events (AE) Alanine aminotransferase (ALT) increased percentage. Look for 'Grade 3+ AE ALT', 'Grade 3+ adverse event ALT', 'Grade 3+ ALT', 'Grade 3+ alanine aminotransferase', 'Grade 3-4 ALT increased', 'G3+ ALT'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_AE_WBC_DECREASED: "Extract Grade 3+ Adverse Events (AE) WBC (White Blood Cell) decreased percentage. Look for 'Grade 3+ AE WBC decreased', 'Grade 3+ adverse event WBC decreased', 'Grade 3+ WBC decreased', 'Grade 3-4 WBC decreased', 'G3+ white blood cell decreased'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_AE_IMMUNE_RELATED: "Extract Grade 3+ Adverse Events (AE) Immune-related adverse events (irAE) percentage. Look for 'Grade 3+ AE irAE', 'Grade 3+ adverse event irAE', 'Grade 3+ irAE', 'Grade 3+ immune-related AE', 'Grade 3-4 irAE', 'G3+ immune-related'. Extract from parentheses.",
            # Safety - Grade 3+ TRAE Specific Adverse Events (Treatment-Related)
            AttributeType.GRADE_3_PLUS_TRAE_IMMUNE_RELATED: "Extract Grade 3+ Treatment-Related Adverse Events (TRAE) Immune-related adverse events (irTRAE) percentage. Look for 'Grade 3+ TRAE immune-related', 'Grade 3+ treatment-related irAE', 'Grade 3+ irTRAE', 'Grade 3+ drug-related irAE', 'Grade 3-4 TRAE immune-related', 'G3+ irTRAE'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TRAE_CRS: "Extract Grade 3+ Treatment-Related Adverse Events (TRAE) Cytokine Release Syndrome (CRS) percentage. Look for 'Grade 3+ TRAE CRS', 'Grade 3+ treatment-related CRS', 'Grade 3+ drug-related CRS', 'Grade 3-4 TRAE CRS', 'G3+ TRAE CRS'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TRAE_THROMBOCYTOPENIA: "Extract Grade 3+ Treatment-Related Adverse Events (TRAE) Thrombocytopenia percentage. Look for 'Grade 3+ TRAE thrombocytopenia', 'Grade 3+ treatment-related thrombocytopenia', 'Grade 3+ drug-related thrombocytopenia', 'Grade 3-4 TRAE thrombocytopenia', 'G3+ TRAE thrombocytopenia', 'Grade 3+ TRAE platelet count decreased'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TRAE_NEUTROPENIA: "Extract Grade 3+ Treatment-Related Adverse Events (TRAE) Neutropenia percentage. Look for 'Grade 3+ TRAE neutropenia', 'Grade 3+ treatment-related neutropenia', 'Grade 3+ drug-related neutropenia', 'Grade 3-4 TRAE neutropenia', 'G3+ TRAE neutropenia', 'Grade 3+ TRAE neutrophil count decreased'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TRAE_LEUKOPENIA: "Extract Grade 3+ Treatment-Related Adverse Events (TRAE) Leukopenia percentage. Look for 'Grade 3+ TRAE leukopenia', 'Grade 3+ treatment-related leukopenia', 'Grade 3+ drug-related leukopenia', 'Grade 3-4 TRAE leukopenia', 'G3+ TRAE leukopenia'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TRAE_NAUSEA: "Extract Grade 3+ Treatment-Related Adverse Events (TRAE) Nausea percentage. Look for 'Grade 3+ TRAE nausea', 'Grade 3+ treatment-related nausea', 'Grade 3+ drug-related nausea', 'Grade 3-4 TRAE nausea', 'G3+ TRAE nausea'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TRAE_ANEMIA: "Extract Grade 3+ Treatment-Related Adverse Events (TRAE) Anemia percentage. Look for 'Grade 3+ TRAE anemia', 'Grade 3+ treatment-related anemia', 'Grade 3+ drug-related anemia', 'Grade 3-4 TRAE anemia', 'G3+ TRAE anemia', 'anaemia', 'Grade 3+ TRAE hemoglobin decreased'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TRAE_DIARRHEA: "Extract Grade 3+ Treatment-Related Adverse Events (TRAE) Diarrhea percentage. Look for 'Grade 3+ TRAE diarrhea', 'Grade 3+ treatment-related diarrhea', 'Grade 3+ drug-related diarrhea', 'Grade 3-4 TRAE diarrhea', 'G3+ TRAE diarrhea', 'diarrhoea'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TRAE_COLITIS: "Extract Grade 3+ Treatment-Related Adverse Events (TRAE) Colitis percentage. Look for 'Grade 3+ TRAE colitis', 'Grade 3+ treatment-related colitis', 'Grade 3+ drug-related colitis', 'Grade 3-4 TRAE colitis', 'G3+ TRAE colitis'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TRAE_HYPERGLYCEMIA: "Extract Grade 3+ Treatment-Related Adverse Events (TRAE) Hyperglycemia percentage. Look for 'Grade 3+ TRAE hyperglycemia', 'Grade 3+ treatment-related hyperglycemia', 'Grade 3+ drug-related hyperglycemia', 'Grade 3-4 TRAE hyperglycemia', 'G3+ TRAE hyperglycemia', 'hyperglycaemia'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TRAE_NEUTROPHIL_COUNT_DECREASED: "Extract Grade 3+ Treatment-Related Adverse Events (TRAE) Neutrophil count decreased percentage. Look for 'Grade 3+ TRAE neutrophil count decreased', 'Grade 3+ treatment-related neutrophil count decreased', 'Grade 3+ drug-related neutrophil count decreased', 'Grade 3-4 TRAE neutrophil count decreased', 'G3+ TRAE neutrophil count decreased'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TRAE_DYSPNEA: "Extract Grade 3+ Treatment-Related Adverse Events (TRAE) Dyspnea percentage. Look for 'Grade 3+ TRAE dyspnea', 'Grade 3+ treatment-related dyspnea', 'Grade 3+ drug-related dyspnea', 'Grade 3-4 TRAE dyspnea', 'G3+ TRAE dyspnea', 'dyspnoea'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TRAE_PYREXIA: "Extract Grade 3+ Treatment-Related Adverse Events (TRAE) Pyrexia percentage. Look for 'Grade 3+ TRAE pyrexia', 'Grade 3+ treatment-related pyrexia', 'Grade 3+ drug-related pyrexia', 'Grade 3-4 TRAE pyrexia', 'G3+ TRAE pyrexia', 'fever'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TRAE_BLEEDING: "Extract Grade 3+ Treatment-Related Adverse Events (TRAE) Bleeding percentage. Look for 'Grade 3+ TRAE bleeding', 'Grade 3+ treatment-related bleeding', 'Grade 3+ drug-related bleeding', 'Grade 3-4 TRAE bleeding', 'G3+ TRAE bleeding', 'hemorrhage'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TRAE_PRURITUS: "Extract Grade 3+ Treatment-Related Adverse Events (TRAE) Pruritus percentage. Look for 'Grade 3+ TRAE pruritus', 'Grade 3+ treatment-related pruritus', 'Grade 3+ drug-related pruritus', 'Grade 3-4 TRAE pruritus', 'G3+ TRAE pruritus'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TRAE_RASH: "Extract Grade 3+ Treatment-Related Adverse Events (TRAE) Rash percentage. Look for 'Grade 3+ TRAE rash', 'Grade 3+ treatment-related rash', 'Grade 3+ drug-related rash', 'Grade 3-4 TRAE rash', 'G3+ TRAE rash'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TRAE_PNEUMONIA: "Extract Grade 3+ Treatment-Related Adverse Events (TRAE) Pneumonia percentage. Look for 'Grade 3+ TRAE pneumonia', 'Grade 3+ treatment-related pneumonia', 'Grade 3+ drug-related pneumonia', 'Grade 3-4 TRAE pneumonia', 'G3+ TRAE pneumonia'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TRAE_THYROIDITIS: "Extract Grade 3+ Treatment-Related Adverse Events (TRAE) Thyroiditis percentage. Look for 'Grade 3+ TRAE thyroiditis', 'Grade 3+ treatment-related thyroiditis', 'Grade 3+ drug-related thyroiditis', 'Grade 3-4 TRAE thyroiditis', 'G3+ TRAE thyroiditis'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TRAE_HYPOPHYSITIS: "Extract Grade 3+ Treatment-Related Adverse Events (TRAE) Hypophysitis percentage. Look for 'Grade 3+ TRAE hypophysitis', 'Grade 3+ treatment-related hypophysitis', 'Grade 3+ drug-related hypophysitis', 'Grade 3-4 TRAE hypophysitis', 'G3+ TRAE hypophysitis'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TRAE_HEPATITIS: "Extract Grade 3+ Treatment-Related Adverse Events (TRAE) Hepatitis percentage. Look for 'Grade 3+ TRAE hepatitis', 'Grade 3+ treatment-related hepatitis', 'Grade 3+ drug-related hepatitis', 'Grade 3-4 TRAE hepatitis', 'G3+ TRAE hepatitis'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TRAE_PNEUMONITIS: "Extract Grade 3+ Treatment-Related Adverse Events (TRAE) Pneumonitis percentage. Look for 'Grade 3+ TRAE pneumonitis', 'Grade 3+ treatment-related pneumonitis', 'Grade 3+ drug-related pneumonitis', 'Grade 3-4 TRAE pneumonitis', 'G3+ TRAE pneumonitis', 'Grade 3+ TRAE interstitial lung disease', 'Grade 3+ TRAE ILD'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TRAE_ALANINE_AMINOTRANSFERASE: "Extract Grade 3+ Treatment-Related Adverse Events (TRAE) Alanine aminotransferase (ALT) increased percentage. Look for 'Grade 3+ TRAE ALT', 'Grade 3+ treatment-related ALT', 'Grade 3+ drug-related ALT', 'Grade 3+ TRAE alanine aminotransferase', 'Grade 3-4 TRAE ALT increased', 'G3+ TRAE ALT'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TRAE_WBC_DECREASED: "Extract Grade 3+ Treatment-Related Adverse Events (TRAE) WBC (White Blood Cell) decreased percentage. Look for 'Grade 3+ TRAE WBC decreased', 'Grade 3+ treatment-related WBC decreased', 'Grade 3+ drug-related WBC decreased', 'Grade 3-4 TRAE WBC decreased', 'G3+ TRAE white blood cell decreased'. Extract from parentheses.",
            # Safety - Grade 3+ TEAE Specific Adverse Events (Treatment-Emergent / All Causality)
            AttributeType.GRADE_3_PLUS_TEAE_IMMUNE_RELATED: "Extract Grade 3+ Treatment-Emergent Adverse Events (TEAE) Immune-related adverse events (irTEAE) percentage. Look for 'Grade 3+ TEAE immune-related', 'Grade 3+ treatment-emergent irAE', 'Grade 3+ irTEAE', 'Grade 3+ regardless of cause irAE', 'Grade 3-4 TEAE immune-related', 'G3+ irTEAE'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TEAE_CRS: "Extract Grade 3+ Treatment-Emergent Adverse Events (TEAE) Cytokine Release Syndrome (CRS) percentage. Look for 'Grade 3+ TEAE CRS', 'Grade 3+ treatment-emergent CRS', 'Grade 3+ regardless of cause CRS', 'Grade 3-4 TEAE CRS', 'G3+ TEAE CRS'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TEAE_THROMBOCYTOPENIA: "Extract Grade 3+ Treatment-Emergent Adverse Events (TEAE) Thrombocytopenia percentage. Look for 'Grade 3+ TEAE thrombocytopenia', 'Grade 3+ treatment-emergent thrombocytopenia', 'Grade 3+ regardless of cause thrombocytopenia', 'Grade 3-4 TEAE thrombocytopenia', 'G3+ TEAE thrombocytopenia', 'Grade 3+ TEAE platelet count decreased'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TEAE_NEUTROPENIA: "Extract Grade 3+ Treatment-Emergent Adverse Events (TEAE) Neutropenia percentage. Look for 'Grade 3+ TEAE neutropenia', 'Grade 3+ treatment-emergent neutropenia', 'Grade 3+ regardless of cause neutropenia', 'Grade 3-4 TEAE neutropenia', 'G3+ TEAE neutropenia', 'Grade 3+ TEAE neutrophil count decreased'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TEAE_LEUKOPENIA: "Extract Grade 3+ Treatment-Emergent Adverse Events (TEAE) Leukopenia percentage. Look for 'Grade 3+ TEAE leukopenia', 'Grade 3+ treatment-emergent leukopenia', 'Grade 3+ regardless of cause leukopenia', 'Grade 3-4 TEAE leukopenia', 'G3+ TEAE leukopenia'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TEAE_NAUSEA: "Extract Grade 3+ Treatment-Emergent Adverse Events (TEAE) Nausea percentage. Look for 'Grade 3+ TEAE nausea', 'Grade 3+ treatment-emergent nausea', 'Grade 3+ regardless of cause nausea', 'Grade 3-4 TEAE nausea', 'G3+ TEAE nausea'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TEAE_ANEMIA: "Extract Grade 3+ Treatment-Emergent Adverse Events (TEAE) Anemia percentage. Look for 'Grade 3+ TEAE anemia', 'Grade 3+ treatment-emergent anemia', 'Grade 3+ regardless of cause anemia', 'Grade 3-4 TEAE anemia', 'G3+ TEAE anemia', 'anaemia', 'Grade 3+ TEAE hemoglobin decreased'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TEAE_DIARRHEA: "Extract Grade 3+ Treatment-Emergent Adverse Events (TEAE) Diarrhea percentage. Look for 'Grade 3+ TEAE diarrhea', 'Grade 3+ treatment-emergent diarrhea', 'Grade 3+ regardless of cause diarrhea', 'Grade 3-4 TEAE diarrhea', 'G3+ TEAE diarrhea', 'diarrhoea'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TEAE_COLITIS: "Extract Grade 3+ Treatment-Emergent Adverse Events (TEAE) Colitis percentage. Look for 'Grade 3+ TEAE colitis', 'Grade 3+ treatment-emergent colitis', 'Grade 3+ regardless of cause colitis', 'Grade 3-4 TEAE colitis', 'G3+ TEAE colitis'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TEAE_HYPERGLYCEMIA: "Extract Grade 3+ Treatment-Emergent Adverse Events (TEAE) Hyperglycemia percentage. Look for 'Grade 3+ TEAE hyperglycemia', 'Grade 3+ treatment-emergent hyperglycemia', 'Grade 3+ regardless of cause hyperglycemia', 'Grade 3-4 TEAE hyperglycemia', 'G3+ TEAE hyperglycemia', 'hyperglycaemia'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TEAE_NEUTROPHIL_COUNT_DECREASED: "Extract Grade 3+ Treatment-Emergent Adverse Events (TEAE) Neutrophil count decreased percentage. Look for 'Grade 3+ TEAE neutrophil count decreased', 'Grade 3+ treatment-emergent neutrophil count decreased', 'Grade 3+ regardless of cause neutrophil count decreased', 'Grade 3-4 TEAE neutrophil count decreased', 'G3+ TEAE neutrophil count decreased'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TEAE_DYSPNEA: "Extract Grade 3+ Treatment-Emergent Adverse Events (TEAE) Dyspnea percentage. Look for 'Grade 3+ TEAE dyspnea', 'Grade 3+ treatment-emergent dyspnea', 'Grade 3+ regardless of cause dyspnea', 'Grade 3-4 TEAE dyspnea', 'G3+ TEAE dyspnea', 'dyspnoea'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TEAE_PYREXIA: "Extract Grade 3+ Treatment-Emergent Adverse Events (TEAE) Pyrexia percentage. Look for 'Grade 3+ TEAE pyrexia', 'Grade 3+ treatment-emergent pyrexia', 'Grade 3+ regardless of cause pyrexia', 'Grade 3-4 TEAE pyrexia', 'G3+ TEAE pyrexia', 'fever'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TEAE_BLEEDING: "Extract Grade 3+ Treatment-Emergent Adverse Events (TEAE) Bleeding percentage. Look for 'Grade 3+ TEAE bleeding', 'Grade 3+ treatment-emergent bleeding', 'Grade 3+ regardless of cause bleeding', 'Grade 3-4 TEAE bleeding', 'G3+ TEAE bleeding', 'hemorrhage'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TEAE_PRURITUS: "Extract Grade 3+ Treatment-Emergent Adverse Events (TEAE) Pruritus percentage. Look for 'Grade 3+ TEAE pruritus', 'Grade 3+ treatment-emergent pruritus', 'Grade 3+ regardless of cause pruritus', 'Grade 3-4 TEAE pruritus', 'G3+ TEAE pruritus'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TEAE_RASH: "Extract Grade 3+ Treatment-Emergent Adverse Events (TEAE) Rash percentage. Look for 'Grade 3+ TEAE rash', 'Grade 3+ treatment-emergent rash', 'Grade 3+ regardless of cause rash', 'Grade 3-4 TEAE rash', 'G3+ TEAE rash'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TEAE_PNEUMONIA: "Extract Grade 3+ Treatment-Emergent Adverse Events (TEAE) Pneumonia percentage. Look for 'Grade 3+ TEAE pneumonia', 'Grade 3+ treatment-emergent pneumonia', 'Grade 3+ regardless of cause pneumonia', 'Grade 3-4 TEAE pneumonia', 'G3+ TEAE pneumonia'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TEAE_THYROIDITIS: "Extract Grade 3+ Treatment-Emergent Adverse Events (TEAE) Thyroiditis percentage. Look for 'Grade 3+ TEAE thyroiditis', 'Grade 3+ treatment-emergent thyroiditis', 'Grade 3+ regardless of cause thyroiditis', 'Grade 3-4 TEAE thyroiditis', 'G3+ TEAE thyroiditis'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TEAE_HYPOPHYSITIS: "Extract Grade 3+ Treatment-Emergent Adverse Events (TEAE) Hypophysitis percentage. Look for 'Grade 3+ TEAE hypophysitis', 'Grade 3+ treatment-emergent hypophysitis', 'Grade 3+ regardless of cause hypophysitis', 'Grade 3-4 TEAE hypophysitis', 'G3+ TEAE hypophysitis'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TEAE_HEPATITIS: "Extract Grade 3+ Treatment-Emergent Adverse Events (TEAE) Hepatitis percentage. Look for 'Grade 3+ TEAE hepatitis', 'Grade 3+ treatment-emergent hepatitis', 'Grade 3+ regardless of cause hepatitis', 'Grade 3-4 TEAE hepatitis', 'G3+ TEAE hepatitis'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TEAE_PNEUMONITIS: "Extract Grade 3+ Treatment-Emergent Adverse Events (TEAE) Pneumonitis percentage. Look for 'Grade 3+ TEAE pneumonitis', 'Grade 3+ treatment-emergent pneumonitis', 'Grade 3+ regardless of cause pneumonitis', 'Grade 3-4 TEAE pneumonitis', 'G3+ TEAE pneumonitis', 'Grade 3+ TEAE interstitial lung disease', 'Grade 3+ TEAE ILD'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TEAE_ALANINE_AMINOTRANSFERASE: "Extract Grade 3+ Treatment-Emergent Adverse Events (TEAE) Alanine aminotransferase (ALT) increased percentage. Look for 'Grade 3+ TEAE ALT', 'Grade 3+ treatment-emergent ALT', 'Grade 3+ regardless of cause ALT', 'Grade 3+ TEAE alanine aminotransferase', 'Grade 3-4 TEAE ALT increased', 'G3+ TEAE ALT'. Extract from parentheses.",
            AttributeType.GRADE_3_PLUS_TEAE_WBC_DECREASED: "Extract Grade 3+ Treatment-Emergent Adverse Events (TEAE) WBC (White Blood Cell) decreased percentage. Look for 'Grade 3+ TEAE WBC decreased', 'Grade 3+ treatment-emergent WBC decreased', 'Grade 3+ regardless of cause WBC decreased', 'Grade 3-4 TEAE WBC decreased', 'G3+ TEAE white blood cell decreased'. Extract from parentheses.",
        }

    def _get_generic_prompt(self) -> str:
        """Get generic extraction prompt for unknown attribute types."""
        return """
TASK: Extract the requested attribute from the clinical trial data.

INSTRUCTIONS:
1. Read the provided context carefully
2. Look for information related to the requested attribute
3. Extract the most relevant and accurate information
4. If not found, the value should be empty string ""
5. Maintain the original format and precision of the data

OUTPUT FORMAT:
The value should be the extracted value as a string or number.
"""

    def _is_numeric_attribute(self, attribute_type: AttributeType) -> bool:
        """Determine if an attribute is numeric (should extract from Results/Conclusions only).

        Args:
            attribute_type: Type of attribute to check

        Returns:
            True if numeric attribute, False otherwise
        """
        # Non-numeric attributes (can extract from any section)
        # NOTE: API-sourced attributes (TRIAL_NAME, SPONSORS, TYPE_OF_THERAPY, etc.) are not included here
        # as they won't be extracted from abstracts
        non_numeric_attributes = {
            AttributeType.ABSTRACT_NUMBER,
            AttributeType.COMMENTS,
            AttributeType.NCT_NUMBER,  # Kept - used as link/identifier
            AttributeType.CANCER_TYPE,
            AttributeType.CANCER_STAGE,
            # AttributeType.SPONSORS,  # API-sourced, removed from LLM extraction
            AttributeType.BRAND_NAME,
            AttributeType.GENERIC_NAME,
            AttributeType.TYPE_OF_THERAPY,
            AttributeType.MECHANISM_OF_ACTION,
            AttributeType.TARGET_PROTEIN,
            AttributeType.BIOSIMILAR,
            AttributeType.SUB_THERAPY,
            AttributeType.PUBLICATION_NAME,
            AttributeType.PUBLICATION_YEAR,
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
