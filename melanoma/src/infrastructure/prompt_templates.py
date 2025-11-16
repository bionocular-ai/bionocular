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
            AttributeType.SPONSORS: "Extract research sponsor(s) from Research Sponsor or Funding sections. Look for 'Research Sponsor:', 'Lead Sponsor:', 'sponsor', or funding organization names. The value should be the sponsor name(s) or empty string if not found.",
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
            # EFS Family
            AttributeType.EFS: "Extract median EFS in months. The value should be a number in months, or 'NR' if not reached.",
            AttributeType.P_VALUE_EFS: "Extract p-value for EFS. The value should be a decimal number or significance level.",
            AttributeType.HR_EFS: "Extract Hazard Ratio for EFS. The value should be a decimal number (e.g., '0.65').",
            # RFS Family
            AttributeType.RFS: "Extract median RFS in months. The value should be a number in months, or 'NR' if not reached.",
            AttributeType.P_VALUE_RFS: "Extract p-value for RFS. The value should be a decimal number or significance level.",
            AttributeType.LENGTH_RFS: "Extract follow-up duration for RFS in months. The value should be a number.",
            AttributeType.HR_RFS: "Extract Hazard Ratio for RFS. The value should be a decimal number (e.g., '0.56').",
            # MFS Family
            AttributeType.MFS: "Extract median MFS in months. The value should be a number in months, or 'NR' if not reached.",
            AttributeType.LENGTH_MFS: "Extract follow-up duration for MFS in months. The value should be a number.",
            AttributeType.HR_MFS: "Extract Hazard Ratio for MFS. The value should be a decimal number (e.g., '0.55').",
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
        # NOTE: API-sourced attributes (TRIAL_NAME, TYPE_OF_THERAPY, etc.) are not included here
        # as they won't be extracted from abstracts
        non_numeric_attributes = {
            AttributeType.ABSTRACT_NUMBER,
            AttributeType.COMMENTS,
            AttributeType.NCT_NUMBER,  # Kept - used as link/identifier
            AttributeType.CANCER_TYPE,
            AttributeType.CANCER_STAGE,
            AttributeType.SPONSORS,
            AttributeType.BRAND_NAME,
            AttributeType.GENERIC_NAME,
            AttributeType.TYPE_OF_THERAPY,
            AttributeType.MECHANISM_OF_ACTION,
            AttributeType.TARGET_PROTEIN,
            AttributeType.BIOSIMILAR,
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
