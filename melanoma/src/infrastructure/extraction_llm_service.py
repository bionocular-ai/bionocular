"""LLM service implementation for extraction.

This service provides a simple interface to the existing LangChain LLM service
for attribute extraction, following clean architecture principles.
"""

import logging
from typing import Any

from ..domain.extraction_interfaces import LLMService
from .langchain import LangChainLLMService

logger = logging.getLogger(__name__)


class ExtractionLLMService(LLMService):
    """Simple LLM service implementation for extraction.

    This service wraps the existing LangChain LLM service to provide
    a clean interface for attribute extraction.
    """

    def __init__(self):
        """Initialize extraction LLM service."""
        self.langchain_llm = LangChainLLMService()
        logger.info("Extraction LLM service initialized")

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
        try:
            logger.info("🔍 DEBUG: LLM Service - Generating response")
            logger.info(
                f"🔍 DEBUG: Model: {model_name}, Temperature: {temperature}, Max tokens: {max_tokens}"
            )
            logger.info(f"🔍 DEBUG: Prompt length: {len(prompt)}")

            # Get LLM instance
            llm = self.langchain_llm.get_llm(
                model_name=model_name, temperature=temperature, max_tokens=max_tokens
            )
            logger.info("🔍 DEBUG: LLM instance created, calling ainvoke...")

            # Generate response
            response = await llm.ainvoke(prompt)
            logger.info(f"🔍 DEBUG: LLM response type: {type(response)}")
            logger.info(
                f"🔍 DEBUG: Response has content attr: {hasattr(response, 'content')}"
            )

            # Extract content from response
            if hasattr(response, "content"):
                result = response.content
            else:
                result = str(response)

            logger.info(f"🔍 DEBUG: Final response length: {len(result)}")
            return result

        except Exception as e:
            logger.error(f"🔍 DEBUG: LLM response generation failed: {e}")
            logger.error(f"🔍 DEBUG: Exception type: {type(e)}")
            raise RuntimeError(f"LLM response generation failed: {e}") from e

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
        try:
            # Generate response
            response = await self.generate_response(prompt)

            # For now, return simple structure
            # In production, you might want to parse JSON or structured output
            return {"extracted_text": response, "format": expected_format}

        except Exception as e:
            logger.error(f"Structured data extraction failed: {e}")
            raise RuntimeError(f"Structured data extraction failed: {e}") from e
