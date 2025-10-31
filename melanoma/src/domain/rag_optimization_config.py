"""RAG optimization configuration for attribute extraction.

This module provides configuration for optimizing RAG context retrieval,
including:
- Dynamic chunk count based on attribute complexity
- Smart filtering of irrelevant context chunks
- Token usage optimization
"""

from enum import Enum

from .extraction_models import AttributeType


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
        AttributeType.SPONSORS,
        AttributeType.CLINICAL_TRIAL_PHASE,
        AttributeType.STUDY_START_DATE,
        AttributeType.STUDY_COMPLETION_DATE,
        AttributeType.FIRST_RESULTS,
        AttributeType.MEDIAN_AGE,
        AttributeType.MINIMUM_AGE,
        AttributeType.MAXIMUM_AGE,
        AttributeType.SEX,
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

        Filters out irrelevant chunks to reduce token waste:
        - NCT chunks only for NCT-dependent attributes
        - Sponsor chunks only for sponsor attributes

        Args:
            chunk_content: The text content of the chunk
            attribute_type: The attribute being extracted

        Returns:
            True if chunk is relevant, False if it should be filtered out
        """
        chunk_type = RAGOptimizationConfig._classify_chunk(chunk_content)

        # NCT chunks only for NCT-dependent attributes
        if chunk_type == ChunkRelevanceType.NCT_INFO:
            return attribute_type in RAGOptimizationConfig.NCT_DEPENDENT_ATTRIBUTES

        # Sponsor chunks only for sponsor attributes
        if chunk_type == ChunkRelevanceType.SPONSOR_INFO:
            return attribute_type in RAGOptimizationConfig.SPONSOR_DEPENDENT_ATTRIBUTES

        # All other chunks are relevant
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

        # Check for NCT information chunks
        if "clinical trial information:" in content_lower and "nct" in content_lower:
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
