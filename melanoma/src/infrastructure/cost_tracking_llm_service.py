"""Cost tracking wrapper for LLM service.

This module provides a wrapper around the LLM service that tracks API costs
and usage statistics.
"""

import logging
from typing import Any, Optional

from ..domain.extraction_interfaces import LLMService
from .cost_calculator import CostCalculator

logger = logging.getLogger(__name__)


class CostTrackingLLMService(LLMService):
    """LLM service wrapper that tracks API costs and usage."""

    def __init__(self, llm_service: LLMService, cost_calculator: CostCalculator):
        """Initialize cost tracking LLM service.

        Args:
            llm_service: Underlying LLM service
            cost_calculator: Cost calculator instance
        """
        self.llm_service = llm_service
        self.cost_calculator = cost_calculator
        logger.info("Cost tracking LLM service initialized")

    async def generate_text(
        self,
        prompt: str,
        model: str = None,
        operation: str = "text_generation",
        attribute_type: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Generate text with cost tracking.

        Args:
            prompt: Input prompt
            model: Model to use
            operation: Type of operation for cost tracking
            attribute_type: Specific attribute being processed
            **kwargs: Additional arguments for LLM service

        Returns:
            Generated text
        """
        try:
            # Count tokens before making the call
            prompt_tokens = self.cost_calculator.count_tokens(
                prompt, model or "gpt-4o-mini"
            )

            # Generate text using underlying service
            response = await self.llm_service.generate_response(
                prompt=prompt, model_name=model, **kwargs
            )

            # Count completion tokens
            completion_tokens = self.cost_calculator.count_tokens(
                response, model or "gpt-4o-mini"
            )

            # Record the API call
            self.cost_calculator.record_api_call(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model=model or "gpt-4o-mini",
                operation=operation,
                attribute_type=attribute_type,
                success=True,
            )

            logger.debug(f"Generated text for {operation}: {len(response)} chars")
            return response

        except Exception as e:
            # Record failed call
            prompt_tokens = self.cost_calculator.count_tokens(
                prompt, model or "gpt-4o-mini"
            )
            self.cost_calculator.record_api_call(
                prompt_tokens=prompt_tokens,
                completion_tokens=0,
                model=model or "gpt-4o-mini",
                operation=operation,
                attribute_type=attribute_type,
                success=False,
                error_message=str(e),
            )

            logger.error(f"Failed to generate text for {operation}: {e}")
            raise

    async def generate_response(
        self,
        prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 1000,
        model_name: str = "gpt-4o-mini",
    ) -> str:
        """Generate response with cost tracking.

        Args:
            prompt: Input prompt
            temperature: Generation temperature
            max_tokens: Maximum tokens to generate
            model_name: LLM model to use

        Returns:
            Generated response
        """
        try:
            # Count tokens before making the call
            prompt_tokens = self.cost_calculator.count_tokens(prompt, model_name)

            # Generate response using underlying service
            response = await self.llm_service.generate_response(
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                model_name=model_name,
            )

            # Count completion tokens
            completion_tokens = self.cost_calculator.count_tokens(response, model_name)

            # Record the API call
            self.cost_calculator.record_api_call(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model=model_name,
                operation="response_generation",
                attribute_type=None,
                success=True,
            )

            logger.debug(f"Generated response: {len(response)} chars")
            return response

        except Exception as e:
            # Record failed call
            prompt_tokens = self.cost_calculator.count_tokens(prompt, model_name)
            self.cost_calculator.record_api_call(
                prompt_tokens=prompt_tokens,
                completion_tokens=0,
                model=model_name,
                operation="response_generation",
                attribute_type=None,
                success=False,
                error_message=str(e),
            )

            logger.error(f"Failed to generate response: {e}")
            raise

    async def extract_structured_data(
        self, prompt: str, expected_format: str
    ) -> dict[str, Any]:
        """Extract structured data with cost tracking.

        Args:
            prompt: Input prompt
            expected_format: Expected output format

        Returns:
            Extracted structured data
        """
        try:
            # Count tokens before making the call
            prompt_tokens = self.cost_calculator.count_tokens(prompt, "gpt-4o-mini")

            # Extract structured data using underlying service
            data = await self.llm_service.extract_structured_data(
                prompt, expected_format
            )

            # Count completion tokens (estimate based on response length)
            response_str = str(data)
            completion_tokens = self.cost_calculator.count_tokens(
                response_str, "gpt-4o-mini"
            )

            # Record the API call
            self.cost_calculator.record_api_call(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model="gpt-4o-mini",
                operation="structured_data_extraction",
                attribute_type=None,
                success=True,
            )

            logger.debug(f"Extracted structured data: {len(response_str)} chars")
            return data

        except Exception as e:
            # Record failed call
            prompt_tokens = self.cost_calculator.count_tokens(prompt, "gpt-4o-mini")
            self.cost_calculator.record_api_call(
                prompt_tokens=prompt_tokens,
                completion_tokens=0,
                model="gpt-4o-mini",
                operation="structured_data_extraction",
                attribute_type=None,
                success=False,
                error_message=str(e),
            )

            logger.error(f"Failed to extract structured data: {e}")
            raise

    async def extract_json(
        self,
        prompt: str,
        operation: str = "extraction",
        attribute_type: Optional[str] = None,
        max_retries: int = 1,
    ) -> dict[str, Any]:
        """Extract JSON data with cost tracking."""
        try:
            prompt_tokens = self.cost_calculator.count_tokens(prompt, "gpt-4o-mini")

            data = await self.llm_service.extract_json(
                prompt,
                operation=operation,
                attribute_type=attribute_type,
                max_retries=max_retries,
            )

            response_str = str(data)
            completion_tokens = self.cost_calculator.count_tokens(
                response_str, "gpt-4o-mini"
            )

            self.cost_calculator.record_api_call(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model="gpt-4o-mini",
                operation=operation,
                attribute_type=attribute_type,
                success=True,
            )

            return data
        except Exception as e:
            prompt_tokens = self.cost_calculator.count_tokens(prompt, "gpt-4o-mini")
            self.cost_calculator.record_api_call(
                prompt_tokens=prompt_tokens,
                completion_tokens=0,
                model="gpt-4o-mini",
                operation=operation,
                attribute_type=attribute_type,
                success=False,
                error_message=str(e),
            )
            logger.error(f"Failed to extract JSON: {e}")
            raise

    def get_cost_summary(self):
        """Get current cost summary."""
        return self.cost_calculator.get_summary()

    def print_cost_summary(self):
        """Print formatted cost summary."""
        self.cost_calculator.print_summary()

    def save_cost_report(self, filepath: str):
        """Save detailed cost report."""
        self.cost_calculator.save_detailed_report(filepath)

    def reset_costs(self):
        """Reset cost tracking."""
        self.cost_calculator.reset()
