"""Backbone prompt provider for complex attribute extraction.

This module provides enhanced prompts with additional context for complex
attributes that require more sophisticated extraction logic, following
the patterns from the legacy system.
"""

import logging
from typing import Any

from ..domain.extraction_models import AttributeConfigurationFactory, AttributeType

logger = logging.getLogger(__name__)


class BackbonePromptProvider:
    """Provider for backbone prompts that include additional context for complex attributes."""

    def __init__(self):
        """Initialize backbone prompt provider."""
        self.backbone_prompts = self._initialize_backbone_prompts()
        logger.info("Backbone prompt provider initialized")

    def get_backbone_prompt(self, attribute_type: AttributeType) -> str:
        """Get backbone prompt for a complex attribute type.

        Args:
            attribute_type: Type of attribute requiring backbone prompt

        Returns:
            Backbone prompt with additional context
        """
        return self.backbone_prompts.get(
            attribute_type, self._get_generic_backbone_prompt(attribute_type)
        )

    def _initialize_backbone_prompts(self) -> dict[AttributeType, str]:
        """Initialize backbone prompts for complex attributes."""
        return {
            AttributeType.TRIAL_NAME: """
BACKBONE CONTEXT - TRIAL NAME EXTRACTION:

TRIAL NAME PATTERNS:
1. **Keynote Trials**: Look for "KEYNOTE-xxx" pattern (e.g., KEYNOTE-006, KEYNOTE-001)
2. **Checkmate Trials**: Look for "Checkmate-xxx" pattern (e.g., Checkmate-067, Checkmate-066)
3. **Masterkey Trials**: Look for "MASTERKEY-xxx" pattern (e.g., MASTERKEY-265)
4. **Other Patterns**: Look for study names, protocol numbers, or trial identifiers

EXTRACTION RULES:
- Primary: Search title, background, and methods sections
- Format: Extract full name including number (e.g., "KEYNOTE-006")
- Fallback: If no standard pattern found, return "No Name"
- Context: Look for study identification, protocol references

COMMON PHRASES TO SEARCH:
- "KEYNOTE-006 study"
- "Checkmate-067 trial"
- "MASTERKEY-265 protocol"
- "Study name: [TRIAL_NAME]"
- "Protocol [NUMBER]"
- "Clinical trial [IDENTIFIER]"

VALIDATION:
- Must contain letters and numbers
- Should be consistent throughout the abstract
- Avoid generic terms like "study", "trial", "protocol" alone
""",
            AttributeType.CANCER_TYPE: """
BACKBONE CONTEXT - CANCER TYPE EXTRACTION:

MELANOMA SUBTYPES - CONTROLLED VOCABULARY:
1. **Resected Cutaneous Melanoma**: Patients with surgically removed cutaneous melanoma
2. **Unresectable Cutaneous Melanoma**: Patients with non-operable cutaneous melanoma
3. **Cutaneous melanoma with Brain metastasis**: Melanoma with brain metastases
4. **Cutaneous Melanoma with CNS metastasis**: Melanoma with central nervous system metastases
5. **Uveal Melanoma**: Melanoma originating in the eye
6. **Mucosal Melanoma**: Melanoma in mucous membranes
7. **Acral Melanoma**: Melanoma on palms, soles, or under nails

EXTRACTION RULES:
- Primary: Look in patient population, eligibility criteria, methods
- Format: Use exact controlled vocabulary terms
- Context: Patient characteristics, study population description
- Multiple types: If multiple subtypes mentioned, use the primary one

COMMON PHRASES TO SEARCH:
- "patients with resected cutaneous melanoma"
- "unresectable or metastatic melanoma"
- "melanoma with brain metastases"
- "uveal melanoma patients"
- "mucosal melanoma"
- "acral melanoma"
- "cutaneous melanoma"
- "metastatic melanoma"

VALIDATION:
- Must match controlled vocabulary exactly
- Should be consistent with study population
- Consider primary vs. secondary mentions
""",
            AttributeType.TYPE_OF_THERAPY: """
BACKBONE CONTEXT - THERAPY TYPE CLASSIFICATION:

THERAPY CLASSIFICATION GUIDE:
1. **Immunotherapy**:
   - Immune Checkpoint Inhibitor/Antibody: Pembrolizumab, Nivolumab
   - Vaccine/Immunostimulant: NeoVaxMI, mRNA-4157
   - Bispecific: Tebentafusp
2. **Cellular therapy**:
   - CAR-T: IL13Ra2 CAR-T
   - NK-Cell: Adoptive NK cell therapy
   - Myeloid Cells: Adoptive Myeloid cell therapy
   - TIL Therapy: Lifileucel
3. **Targeted Therapy**:
   - Antibody: Trastuzumab, Rituximab
   - Tyrosine kinase inhibitor: Imatinib, Erlotinib
   - Angiogenesis inhibitor: Bevacizumab
   - Antibody-Drug Conjugate: Ozuriftamab vedotin, HER3 ADC
4. **Oncolytic Virus**:
   - Oncolytic Virus: Talimogene laherparepvec (Imlygic)
5. **Chemotherapy**:
   - Chemotherapy: Dacarbazine, Temozolomide

EXTRACTION RULES:
- Primary: Classify by the primary/lead therapy mechanism
- Format: Use exact category names from controlled vocabulary
- Context: Drug mechanism, treatment approach, study design
- Combinations: Classify by the primary therapy when multiple mechanisms

COMMON PHRASES TO SEARCH:
- "immune checkpoint inhibitor"
- "PD-1/PD-L1 inhibitor"
- "CTLA-4 inhibitor"
- "cellular therapy"
- "TIL therapy"
- "CAR T-cell"
- "targeted therapy"
- "BRAF inhibitor"
- "MEK inhibitor"
- "oncolytic virus"
- "chemotherapy"
- "bispecific antibody"
- "cancer vaccine"

VALIDATION:
- Must match controlled vocabulary exactly
- Should reflect primary mechanism of action
- Consider drug class and target
""",
            AttributeType.MEDIAN_AGE: """
BACKBONE CONTEXT - MEDIAN AGE EXTRACTION:

AGE EXTRACTION PATTERNS:
1. **Direct Median**: "median age was 65 years"
2. **Range with Median**: "age range 45-75, median 62"
3. **Patient Characteristics**: Look in demographics section
4. **Baseline Data**: Check baseline characteristics table

EXTRACTION RULES:
- Primary: Look for "median age", "median", "age"
- Format: Extract number only (e.g., "65" not "65 years")
- Range: Should be reasonable (0-120 years)
- Context: Patient characteristics, demographics, baseline data

COMMON PHRASES TO SEARCH:
- "median age was 65 years"
- "median age: 58"
- "age range 45-75, median 62"
- "median patient age 70"
- "baseline age: 65"
- "demographics: median age 60"

VALIDATION:
- Must be numeric value
- Should be reasonable age range (0-120)
- Check for consistency across sections
""",
            AttributeType.NUMBER_OF_PATIENTS: """
BACKBONE CONTEXT - PATIENT COUNT EXTRACTION:

PATIENT COUNT PATTERNS:
1. **Treatment Arm Specific**: "n = 313 patients" (for specific arm)
2. **Randomization**: "313 patients were randomized to [arm]"
3. **Enrollment**: "enrolled 150 patients in [arm]"
4. **Baseline**: Look in baseline characteristics

EXTRACTION RULES:
- Primary: Look for "n =", "patients", "enrolled", "randomized"
- Format: Extract integer only (e.g., "313" not "313 patients")
- Context: Treatment arm specific, not total study
- Critical: This is a required field for each treatment arm

COMMON PHRASES TO SEARCH:
- "n = 313 patients"
- "313 patients were randomized"
- "enrolled 150 patients"
- "arm included 200 patients"
- "baseline characteristics: n=313"
- "patient population: 150 patients"

VALIDATION:
- Must be integer value
- Should be reasonable range (1-10000)
- Must be arm-specific, not total study
- Check for consistency across sections
""",
        }

    def _get_generic_backbone_prompt(self, attribute_type: AttributeType) -> str:
        """Get generic backbone prompt for attributes not explicitly defined."""
        config = AttributeConfigurationFactory.get_configuration(attribute_type)

        return f"""
BACKBONE CONTEXT - {attribute_type.value.replace('_', ' ').upper()} EXTRACTION:

EXTRACTION GUIDANCE:
1. Look for {attribute_type.value.replace('_', ' ')} in relevant sections
2. Extract value according to type: {config.value_kind.value}
3. Use controlled vocabulary if available
4. Validate against expected ranges

COMMON SECTIONS TO SEARCH:
- Results section
- Methods section
- Patient characteristics
- Efficacy data
- Safety data

VALIDATION RULES:
- Check value type matches expected format
- Validate against controlled vocabulary if applicable
- Ensure value is within reasonable ranges
- Cross-reference with other related attributes
"""

    def get_enhanced_prompt(
        self, attribute_type: AttributeType, base_prompt: str, context: list[str]
    ) -> str:
        """Get enhanced prompt with backbone context for complex attributes.

        Args:
            attribute_type: Type of attribute to extract
            base_prompt: Base extraction prompt
            context: Context chunks

        Returns:
            Enhanced prompt with backbone context
        """
        config = AttributeConfigurationFactory.get_configuration(attribute_type)

        # Only add backbone context for attributes that need it
        if not config.needs_backbone_prompt:
            return base_prompt

        backbone_prompt = self.get_backbone_prompt(attribute_type)

        # Format context
        context_text = self._format_context(context)

        # Combine base prompt with backbone context
        enhanced_prompt = f"""
{backbone_prompt}

{base_prompt}

CONTEXT:
{context_text}

ENHANCED EXTRACTION INSTRUCTIONS:
1. Use the backbone context to guide your extraction
2. Apply the specific extraction rules for this attribute
3. Validate against controlled vocabulary if applicable
4. Return the most accurate value based on the context provided
"""

        return enhanced_prompt

    def _format_context(self, context: list[Any]) -> str:
        """Format context chunks for inclusion in prompts.

        Args:
            context: List of context chunk objects or strings

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
