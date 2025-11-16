"""RAG optimization configuration for attribute extraction.

This module provides configuration for optimizing RAG context retrieval,
including:
- Dynamic chunk count based on attribute complexity
- Smart filtering of irrelevant context chunks
- Token usage optimization
"""

from enum import Enum

from .extraction_models import AttributeConfigurationFactory, AttributeType


class AttributeComplexity(str, Enum):
    """Attribute complexity levels for RAG optimization."""

    SIMPLE = "simple"  # 2 chunks - Simple identifiers
    STANDARD = "standard"  # 3 chunks - Standard attributes
    COMPLEX = "complex"  # 5 chunks - Complex survival metrics, rates


class ChunkRelevanceType(str, Enum):
    """Types of chunks based on their content."""

    NCT_INFO = "nct_info"  # Clinical Trial Information: NCT####
    SPONSOR_INFO = "sponsor_info"  # Research Sponsor information
    RESULTS_DATA = "results_data"  # Results, efficacy, safety data
    DEMOGRAPHICS = "demographics"  # Patient demographics
    METHODS = "methods"  # Methods, study design
    GENERAL = "general"  # Other content


class RAGOptimizationConfig:
    """Configuration for RAG optimization strategies."""

    # Simple attributes - need minimal context (2 chunks)
    SIMPLE_ATTRIBUTES: set[AttributeType] = {
        AttributeType.ABSTRACT_NUMBER,
        AttributeType.NCT_NUMBER,
        AttributeType.TRIAL_NAME,
        AttributeType.CONFERENCE,
        AttributeType.PUBLISHED_YEAR,
        AttributeType.COMMENTS,
    }

    # Standard attributes - need moderate context (3 chunks)
    STANDARD_ATTRIBUTES: set[AttributeType] = {
        AttributeType.GENERIC_NAME,
        AttributeType.BRAND_NAME,
        AttributeType.CANCER_TYPE,
        AttributeType.CANCER_STAGE,
        AttributeType.SPONSORS,
        AttributeType.CLINICAL_TRIAL_PHASE,
        AttributeType.STUDY_START_DATE,
        AttributeType.STUDY_COMPLETION_DATE,
        AttributeType.FIRST_RESULTS,
        AttributeType.BIOSIMILAR,
        AttributeType.DOSAGE,
        AttributeType.TYPE_OF_DOSING,
        AttributeType.TYPE_OF_THERAPY,
        AttributeType.SUB_THERAPY,
        AttributeType.MECHANISM_OF_ACTION,
        AttributeType.TARGET_PROTEIN,
        AttributeType.PRIMARY_ENDPOINT,
        AttributeType.SECONDARY_ENDPOINT,
        AttributeType.BIOMARKER_INCLUSION,
        AttributeType.TRIAL_RUN_IN_EUROPE,
        AttributeType.TRIAL_RUN_IN_US,
        AttributeType.TRIAL_RUN_IN_CHINA,
    }

    # Attributes obtained exclusively from ClinicalTrials.gov API
    # These should NOT be extracted from abstracts - skip retrieval entirely
    # Note: Using AttributeConfigurationFactory.get_api_sourced_attributes() for single source of truth
    _api_only_attributes_cache = None  # Lazy-loaded cache

    # 🎯 TIER 1: Numeric attributes - MUST retrieve from Results/Table sections only
    NUMERIC_ATTRIBUTES: set[AttributeType] = {
        # Demographics (extracted from abstracts)
        # Note: MINIMUM_AGE, MAXIMUM_AGE, SEX obtained from ClinicalTrials.gov API
        AttributeType.MEDIAN_AGE,
        AttributeType.NUMBER_OF_PATIENTS,
        # PFS Family - all in Results
        AttributeType.MEDIAN_PFS,
        AttributeType.MEDIAN_FOLLOWUP_PFS,
        AttributeType.P_VALUE_PFS,
        AttributeType.HR_PFS,
        AttributeType.PFS_RATE_6M,
        AttributeType.PFS_RATE_9M,
        AttributeType.PFS_RATE_12M,
        AttributeType.PFS_RATE_18M,
        AttributeType.PFS_RATE_24M,
        AttributeType.PFS_RATE_36M,
        AttributeType.PFS_RATE_48M,
        # OS Family - all in Results
        AttributeType.MEDIAN_OS,
        AttributeType.MEDIAN_FOLLOWUP_OS,
        AttributeType.P_VALUE_OS,
        AttributeType.HR_OS,
        AttributeType.OS_RATE_6M,
        AttributeType.OS_RATE_9M,
        AttributeType.OS_RATE_12M,
        AttributeType.OS_RATE_18M,
        AttributeType.OS_RATE_24M,
        AttributeType.OS_RATE_36M,
        AttributeType.OS_RATE_48M,
        # Response Rates - all in Results
        AttributeType.OBJECTIVE_RESPONSE_RATE,
        AttributeType.COMPLETE_RESPONSE,
        AttributeType.PATHOLOGICAL_COMPLETE_RESPONSE,
        AttributeType.COMPLETE_METABOLIC_RESPONSE,
        AttributeType.DISEASE_CONTROL_RATE,
        AttributeType.CLINICAL_BENEFIT_RATE,
        AttributeType.MEDIAN_DOR,
        AttributeType.DOR_RATE,
        # Other Survival Metrics - all in Results
        AttributeType.EFS,
        AttributeType.P_VALUE_EFS,
        AttributeType.HR_EFS,
        AttributeType.RFS,
        AttributeType.P_VALUE_RFS,
        AttributeType.LENGTH_RFS,
        AttributeType.HR_RFS,
        AttributeType.MFS,
        AttributeType.LENGTH_MFS,
        AttributeType.HR_MFS,
        # Time-to Metrics - all in Results
        AttributeType.TTR,
        AttributeType.TTP,
        AttributeType.TTNT,
        AttributeType.TTF,
        # Adverse Events - all in Results/Safety
        AttributeType.AE,
        AttributeType.GRADE_3_PLUS_AE,
        AttributeType.AE_LEADING_TO_DISCONTINUATION,
        AttributeType.SERIOUS_AE,
        AttributeType.IMMUNE_RELATED_AE,
        AttributeType.SERIOUS_IMMUNE_RELATED_AE,
        AttributeType.AE_LEADING_TO_DEATH,
        # TEAEs - all in Results/Safety
        AttributeType.TEAE,
        AttributeType.GRADE_3_PLUS_TEAE,
        AttributeType.GRADE_3_TEAE,
        AttributeType.GRADE_4_TEAE,
        AttributeType.GRADE_5_TEAE,
        AttributeType.TEAE_LEADING_TO_DISCONTINUATION,
        AttributeType.TEAE_LEADING_TO_DEATH,
        AttributeType.SERIOUS_TEAE,
        AttributeType.TEAE_IMMUNE_RELATED,
        # TRAEs - all in Results/Safety
        AttributeType.TRAE,
        AttributeType.GRADE_3_PLUS_TRAE,
        AttributeType.GRADE_3_TRAE,
        AttributeType.GRADE_4_TRAE,
        AttributeType.GRADE_5_TRAE,
        AttributeType.TRAE_LEADING_TO_DISCONTINUATION,
        AttributeType.TRAE_LEADING_TO_DEATH,
        AttributeType.TRAE_IMMUNE_RELATED,
        AttributeType.SERIOUS_TRAE,
        # Specific AEs - all in Results/Safety
        AttributeType.CRS,
        AttributeType.WBC_DECREASED,
    }

    # Attributes that specifically need NCT chunks
    NCT_DEPENDENT_ATTRIBUTES: set[AttributeType] = {
        AttributeType.NCT_NUMBER,
        AttributeType.TRIAL_NAME,
    }

    # Attributes that specifically need Sponsor chunks
    SPONSOR_DEPENDENT_ATTRIBUTES: set[AttributeType] = {
        AttributeType.SPONSORS,
    }

    @staticmethod
    def get_optimal_chunk_count(attribute_type: AttributeType) -> int:
        """Get optimal chunk count for an attribute.

        Returns:
            2 for simple attributes (identifiers)
            3 for standard attributes (basic extraction)
            5 for complex attributes (survival metrics, rates with verification)
        """
        if attribute_type in RAGOptimizationConfig.SIMPLE_ATTRIBUTES:
            return 2
        elif attribute_type in RAGOptimizationConfig.STANDARD_ATTRIBUTES:
            return 3
        else:
            # Complex attributes (survival metrics, response rates, AE rates, etc.)
            return 5

    @staticmethod
    def should_include_chunk(chunk_content: str, attribute_type: AttributeType) -> bool:
        """Determine if a chunk should be included for an attribute.

        Multi-tier filtering to reduce token waste and improve precision:
        - TIER 2: NCT chunks only for NCT-dependent attributes
        - TIER 2: Sponsor chunks only for sponsor attributes
        - TIER 3: Keyword filtering for semantic false positives

        Args:
            chunk_content: The text content of the chunk
            attribute_type: The attribute being extracted

        Returns:
            True if chunk is relevant, False if it should be filtered out
        """
        # TIER 2: Content-type filtering (NCT/Sponsor)
        chunk_type = RAGOptimizationConfig._classify_chunk(chunk_content)

        # NCT chunks only for NCT-dependent attributes
        if chunk_type == ChunkRelevanceType.NCT_INFO:
            return attribute_type in RAGOptimizationConfig.NCT_DEPENDENT_ATTRIBUTES

        # Sponsor chunks only for sponsor attributes
        if chunk_type == ChunkRelevanceType.SPONSOR_INFO:
            return attribute_type in RAGOptimizationConfig.SPONSOR_DEPENDENT_ATTRIBUTES

        # TIER 3: Keyword filtering (semantic false positive elimination)
        from ..infrastructure.keyword_filter import chunk_contains_keywords
        from .attribute_keywords import get_keywords_for_attribute

        keywords = get_keywords_for_attribute(attribute_type)
        if keywords is not None:
            # Keyword filter is defined - apply it
            return chunk_contains_keywords(chunk_content, keywords)

        # No keyword filter defined - include chunk
        return True

    @staticmethod
    def _classify_chunk(chunk_content: str) -> ChunkRelevanceType:
        """Classify chunk type based on content.

        Args:
            chunk_content: The text content of the chunk

        Returns:
            ChunkRelevanceType indicating the type of information in the chunk
        """
        content_lower = chunk_content.lower().strip()

        # Check for NCT information chunks (both ASCO and ESMO formats)
        if (
            ("clinical trial information:" in content_lower or "clinical trial identification:" in content_lower)
            and "nct" in content_lower
        ):
            # Only if this is a pure NCT chunk (no other substantial content)
            if len(content_lower.split("\n")) <= 3:
                return ChunkRelevanceType.NCT_INFO

        # Check for sponsor information chunks
        if "research sponsor:" in content_lower or "lead sponsor:" in content_lower:
            # Only if this is a pure sponsor chunk
            if len(content_lower.split("\n")) <= 3:
                return ChunkRelevanceType.SPONSOR_INFO

        # All other chunks are general and relevant
        return ChunkRelevanceType.GENERAL

    @staticmethod
    def get_complexity_level(attribute_type: AttributeType) -> AttributeComplexity:
        """Get the complexity level of an attribute.

        Args:
            attribute_type: The attribute type

        Returns:
            AttributeComplexity level
        """
        if attribute_type in RAGOptimizationConfig.SIMPLE_ATTRIBUTES:
            return AttributeComplexity.SIMPLE
        elif attribute_type in RAGOptimizationConfig.STANDARD_ATTRIBUTES:
            return AttributeComplexity.STANDARD
        else:
            return AttributeComplexity.COMPLEX

    @staticmethod
    def is_api_only_attribute(attribute_type: AttributeType) -> bool:
        """Check if an attribute is obtained exclusively from the API.

        Uses AttributeConfigurationFactory.get_api_sourced_attributes() for single source of truth.

        Args:
            attribute_type: The attribute type to check

        Returns:
            True if the attribute is sourced from API and should skip abstract extraction
        """
        # Lazy-load and cache API-sourced attributes
        if RAGOptimizationConfig._api_only_attributes_cache is None:
            RAGOptimizationConfig._api_only_attributes_cache = set(
                AttributeConfigurationFactory.get_api_sourced_attributes()
            )

        return attribute_type in RAGOptimizationConfig._api_only_attributes_cache

    @staticmethod
    def is_numeric_attribute(attribute_type: AttributeType) -> bool:
        """Check if an attribute is numeric (requires Results/Table section).

        Numeric attributes should only be extracted from Results, Conclusions,
        or Table sections to avoid confusion with Background references to
        other studies.

        Args:
            attribute_type: The attribute type to check

        Returns:
            True if the attribute is numeric and requires Results section filtering
        """
        return attribute_type in RAGOptimizationConfig.NUMERIC_ATTRIBUTES

    @staticmethod
    def get_required_chunk_types(attribute_type: AttributeType) -> list[str] | None:
        """Get required chunk types for filtering retrieval.

        For numeric attributes, this returns chunk type strings that should be
        used to filter retrieval to only Results/Table/Conclusions sections.

        For specific attributes, returns their designated chunk types.

        Args:
            attribute_type: The attribute type

        Returns:
            List of chunk type strings (lowercase) to filter on, or None for no filtering.
            Returns chunk types compatible with ChunkType enum values.
        """
        # Special case: Abstract number only in abstract ID section
        if attribute_type == AttributeType.ABSTRACT_NUMBER:
            return ["abstract_id"]

        # Special case: NCT number only in clinical trial info section
        if attribute_type == AttributeType.NCT_NUMBER:
            return ["clinical_trial"]

        # Special case: Comments only in full text reference section
        if attribute_type == AttributeType.COMMENTS:
            return ["full_text_reference"]

        # Special case: Sponsors only in Research Sponsor or Funding sections
        if attribute_type == AttributeType.SPONSORS:
            return ["sponsor", "funding"]

        # Special case: Number of patients can be in methods OR results
        if attribute_type == AttributeType.NUMBER_OF_PATIENTS:
            return ["methods", "results", "table", "conclusions"]

        # Numeric attributes: ONLY search Results, Table, and Conclusions chunks
        if RAGOptimizationConfig.is_numeric_attribute(attribute_type):
            return ["results", "table", "conclusions"]

        # All other attributes: search all chunk types EXCEPT abstract_id
        # (abstract_id is just metadata - the ID number itself, not useful for most extraction)
        # Title IS included as it may contain useful context for some attributes
        return [
            "title",
            "background",
            "methods",
            "results",
            "conclusions",
            "table",
            "trial_design",
            "clinical_trial",
            "sponsor",
            "funding",
            "legal_entity",
            "doi",
            "full_text_reference",
        ]

    @staticmethod
    def estimate_token_savings(
        total_attributes: int,
        simple_count: int,
        standard_count: int,
        complex_count: int,
    ) -> dict:
        """Estimate token savings from optimization.

        Args:
            total_attributes: Total number of attributes
            simple_count: Number of simple attributes
            standard_count: Number of standard attributes
            complex_count: Number of complex attributes

        Returns:
            Dictionary with savings estimates
        """
        # Average chunk size
        avg_chunk_chars = 200

        # Calculate savings
        # Simple: save 3 chunks (5 -> 2)
        simple_savings = simple_count * 3 * avg_chunk_chars

        # Standard: save 2 chunks (5 -> 3)
        standard_savings = standard_count * 2 * avg_chunk_chars

        # Complex: no change (5 -> 5)
        complex_savings = 0

        total_char_savings = simple_savings + standard_savings + complex_savings
        total_token_savings = total_char_savings // 4

        # Cost savings (GPT-4o @ $2.50 per 1M input tokens)
        cost_savings_per_abstract = (total_token_savings / 1_000_000) * 2.50

        return {
            "simple_savings_chars": simple_savings,
            "standard_savings_chars": standard_savings,
            "complex_savings_chars": complex_savings,
            "total_char_savings": total_char_savings,
            "total_token_savings": total_token_savings,
            "cost_savings_per_abstract": cost_savings_per_abstract,
            "cost_savings_per_1000_abstracts": cost_savings_per_abstract * 1000,
        }
