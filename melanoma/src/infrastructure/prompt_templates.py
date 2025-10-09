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
        self.description_prompts = self._initialize_description_prompts()
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
        base_prompt = self.extraction_prompts.get(
            attribute_type, self._get_generic_prompt()
        )

        # Format context
        context_text = self._format_context(context)

        # Combine base prompt with context
        full_prompt = f"{base_prompt}\n\nCONTEXT:\n{context_text}\n\nEXTRACTION INSTRUCTIONS:\n{self._get_extraction_instructions(attribute_type)}"

        return full_prompt

    def get_description_prompt(self, attribute_type: AttributeType) -> str:
        """Get description prompt for an attribute type.

        Args:
            attribute_type: Type of attribute

        Returns:
            Description prompt for additional context
        """
        return self.description_prompts.get(
            attribute_type,
            f"Extract {attribute_type.value} from the clinical trial data.",
        )

    def _initialize_extraction_prompts(self) -> dict[AttributeType, str]:
        """Initialize extraction prompts for each attribute type."""
        return {
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
        }

    def _initialize_description_prompts(self) -> dict[AttributeType, str]:
        """Initialize description prompts for additional context."""
        return {
            AttributeType.NCT_NUMBER: """
The NCT number is a unique identifier assigned by ClinicalTrials.gov to registered clinical trials.
It follows the format NCT followed by 8 digits (e.g., NCT03554083). This identifier is crucial for
tracking and referencing specific clinical trials across different publications and databases.
""",
            AttributeType.GENERIC_NAME: """
Generic drug names are the non-proprietary names of pharmaceutical substances, as opposed to brand names.
For combination therapies, multiple generic names are separated by "+". Dose information may be included
for dose-escalation studies or when different doses are compared.
""",
            AttributeType.P_VALUE_OS: """
The p-value for Overall Survival (OS) indicates the statistical significance of survival differences
between treatment groups. A p-value ≤ 0.05 is considered statistically significant, while p ≤ 0.001
is highly significant. This metric is crucial for determining treatment efficacy.
""",
            AttributeType.OBJECTIVE_RESPONSE_RATE: """
Objective Response Rate (ORR) is the percentage of patients who achieve either a Complete Response (CR)
or Partial Response (PR) according to RECIST criteria. It's a key efficacy endpoint in cancer clinical
trials and indicates the proportion of patients who benefit from treatment.
""",
            AttributeType.GRADE_3_PLUS_AE: """
Grade 3+ adverse events are severe or life-threatening toxicities according to CTCAE criteria.
These events often lead to treatment discontinuation and are critical safety endpoints. The percentage
represents the proportion of patients experiencing such events.
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

    def _get_extraction_instructions(self, attribute_type: AttributeType) -> str:
        """Get specific extraction instructions for an attribute type.

        Args:
            attribute_type: Type of attribute

        Returns:
            Extraction instructions
        """
        instructions = {
            AttributeType.NCT_NUMBER: """
1. Search for "NCT" followed by 8 digits
2. Check ClinicalTrials.gov references
3. Look in trial identification sections
4. Return exact format found
""",
            AttributeType.GENERIC_NAME: """
1. Identify primary treatment drugs
2. Use generic names, not brand names
3. For combinations, use "Drug A + Drug B" format
4. Include dose information if relevant
""",
            AttributeType.P_VALUE_OS: """
1. Look for OS-specific p-values
2. Check statistical analysis sections
3. Convert to standard significance levels
4. Focus on primary analysis
""",
            AttributeType.OBJECTIVE_RESPONSE_RATE: """
1. Look for ORR or response rate data
2. Extract percentage from parentheses
3. Calculate if not explicitly stated
4. Check efficacy results sections
""",
            AttributeType.GRADE_3_PLUS_AE: """
1. Look for Grade 3+ adverse events
2. Extract percentage from parentheses
3. Sum grades if not given directly
4. Check safety sections
""",
        }

        return instructions.get(
            attribute_type, "Extract the requested information accurately."
        )
