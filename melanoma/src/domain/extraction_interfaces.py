"""Domain interfaces for extraction system.

This module defines the contracts that the application layer
must implement, following the Dependency Inversion Principle.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional

from .extraction_models import (
    AttributeType,
    ExtractedAttribute,
    ExtractionResult,
    ValidationRule,
)


class RAGContextProvider(ABC):
    """Interface for retrieving context from RAG system."""

    @abstractmethod
    async def get_context_for_attribute(
        self,
        document_id: str,
        attribute_type: AttributeType,
        context_chunks: int = 5,
        similarity_threshold: float = 0.1,
        metadata_filters: Optional[dict[str, Any]] = None,
    ) -> list[str]:
        """Get relevant context chunks for attribute extraction.

        Args:
            document_id: Document identifier
            attribute_type: Type of attribute to extract
            context_chunks: Number of context chunks to retrieve
            similarity_threshold: Minimum similarity threshold
            metadata_filters: Optional metadata filters

        Returns:
            List of context chunk texts
        """
        pass


class AttributeExtractor(ABC):
    """Interface for extracting specific attributes from text."""

    @abstractmethod
    async def extract_attribute(
        self, attribute_type: AttributeType, context: list[str], document_id: str
    ) -> ExtractedAttribute:
        """Extract a specific attribute from context.

        Args:
            attribute_type: Type of attribute to extract
            context: List of context texts
            document_id: Document identifier

        Returns:
            Extracted attribute with confidence score
        """
        pass


class AttributeValidator(ABC):
    """Interface for validating extracted attributes."""

    @abstractmethod
    async def validate_attribute(
        self, attribute: ExtractedAttribute, validation_rules: list[ValidationRule]
    ) -> ExtractedAttribute:
        """Validate an extracted attribute.

        Args:
            attribute: Attribute to validate
            validation_rules: Rules to apply for validation

        Returns:
            Validated attribute with updated status
        """
        pass


class ExtractionRepository(ABC):
    """Interface for persisting extraction results."""

    @abstractmethod
    async def save_extraction_result(self, result: ExtractionResult) -> str:
        """Save extraction result to storage.

        Args:
            result: Extraction result to save

        Returns:
            Unique identifier for saved result
        """
        pass

    @abstractmethod
    async def get_extraction_result(self, result_id: str) -> Optional[ExtractionResult]:
        """Retrieve extraction result by ID.

        Args:
            result_id: Unique identifier

        Returns:
            Extraction result or None if not found
        """
        pass

    @abstractmethod
    async def get_extraction_results_by_document(
        self, document_id: str
    ) -> list[ExtractionResult]:
        """Get all extraction results for a document.

        Args:
            document_id: Document identifier

        Returns:
            List of extraction results
        """
        pass

    @abstractmethod
    async def get_validation_rules(
        self, attribute_type: AttributeType
    ) -> list[ValidationRule]:
        """Get validation rules for an attribute type.

        Args:
            attribute_type: Type of attribute

        Returns:
            List of validation rules
        """
        pass


class PromptTemplateProvider(ABC):
    """Interface for providing extraction prompt templates."""

    @abstractmethod
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
        pass

    @abstractmethod
    def get_description_prompt(self, attribute_type: AttributeType) -> str:
        """Get description prompt for an attribute type.

        Args:
            attribute_type: Type of attribute

        Returns:
            Description prompt for additional context
        """
        pass


class LLMService(ABC):
    """Interface for LLM operations."""

    @abstractmethod
    async def generate_response(
        self,
        prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 1000,
        model_name: str = "gpt-4o-mini",
    ) -> str:
        """Generate response using LLM.

        Args:
            prompt: Input prompt
            temperature: Generation temperature
            max_tokens: Maximum tokens to generate
            model_name: LLM model to use

        Returns:
            Generated response text
        """
        pass

    @abstractmethod
    async def extract_structured_data(
        self, prompt: str, expected_format: str
    ) -> dict[str, Any]:
        """Extract structured data using LLM.

        Args:
            prompt: Input prompt with context
            expected_format: Expected output format description

        Returns:
            Structured data dictionary
        """
        pass
