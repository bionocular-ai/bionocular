"""Cost calculation utility for LLM API usage.

This module provides comprehensive cost tracking and calculation for OpenAI API usage
across the enhanced extraction system.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import tiktoken

logger = logging.getLogger(__name__)


class ModelType(str, Enum):
    """Supported models with their pricing (OpenAI and OpenRouter/Gemini)."""

    GPT_4O_MINI = "gpt-4o-mini"
    GPT_4O = "gpt-4o"
    GPT_5_MINI = "gpt-5-mini"
    GPT_5 = "gpt-5"

    # Google Gemini via OpenRouter (prices per 1M tokens, as of March 2026)
    GEMINI_31_PRO_PREVIEW = "google/gemini-3.1-pro-preview"
    GEMINI_25_PRO = "google/gemini-2.5-pro"
    GEMINI_25_FLASH = "google/gemini-2.5-flash"

    # Google Gemini via direct Gemini API (bare model names)
    GEMINI_31_PRO_PREVIEW_DIRECT = "gemini-3.1-pro-preview"
    GEMINI_25_PRO_DIRECT = "gemini-2.5-pro"
    GEMINI_25_FLASH_DIRECT = "gemini-2.5-flash"


@dataclass
class ModelPricing:
    """Pricing information for OpenAI models."""

    model: ModelType
    prompt_cost_per_1m: float
    completion_cost_per_1m: float
    max_tokens: int
    description: str


@dataclass
class APICall:
    """Record of a single API call."""

    timestamp: datetime
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost: float
    operation: str  # e.g., "arm_separation", "attribute_extraction", "api_lookup"
    attribute_type: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None


@dataclass
class CostSummary:
    """Summary of API usage and costs."""

    total_requests: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    successful_requests: int = 0
    failed_requests: int = 0
    calls_by_operation: dict[str, int] = field(default_factory=dict)
    calls_by_attribute: dict[str, int] = field(default_factory=dict)
    calls_by_model: dict[str, int] = field(default_factory=dict)
    cost_by_operation: dict[str, float] = field(default_factory=dict)
    cost_by_attribute: dict[str, float] = field(default_factory=dict)
    cost_by_model: dict[str, float] = field(default_factory=dict)


class CostCalculator:
    """Comprehensive cost calculator for LLM API usage."""

    # Model pricing (per 1M tokens) - Standard tier
    # OpenAI: https://platform.openai.com/docs/pricing
    # OpenRouter/Gemini: https://openrouter.ai/google
    MODEL_PRICING = {
        ModelType.GPT_4O_MINI: ModelPricing(
            model=ModelType.GPT_4O_MINI,
            prompt_cost_per_1m=0.15,
            completion_cost_per_1m=0.60,
            max_tokens=128000,
            description="GPT-4o Mini - Fast and cost-effective",
        ),
        ModelType.GPT_4O: ModelPricing(
            model=ModelType.GPT_4O,
            prompt_cost_per_1m=2.50,
            completion_cost_per_1m=10.00,
            max_tokens=128000,
            description="GPT-4o - Most capable GPT-4 model",
        ),
        ModelType.GPT_5_MINI: ModelPricing(
            model=ModelType.GPT_5_MINI,
            prompt_cost_per_1m=0.25,
            completion_cost_per_1m=2.00,
            max_tokens=128000,
            description="GPT-5 Mini - Next-gen fast model",
        ),
        ModelType.GPT_5: ModelPricing(
            model=ModelType.GPT_5,
            prompt_cost_per_1m=1.25,
            completion_cost_per_1m=10.00,
            max_tokens=128000,
            description="GPT-5 - Next-generation flagship model",
        ),
        # Gemini via OpenRouter — token counts come directly from API response
        ModelType.GEMINI_31_PRO_PREVIEW: ModelPricing(
            model=ModelType.GEMINI_31_PRO_PREVIEW,
            prompt_cost_per_1m=2.00,
            completion_cost_per_1m=12.00,
            max_tokens=1048576,
            description="Gemini 3.1 Pro Preview - Latest Google flagship (OpenRouter)",
        ),
        ModelType.GEMINI_25_PRO: ModelPricing(
            model=ModelType.GEMINI_25_PRO,
            prompt_cost_per_1m=1.25,
            completion_cost_per_1m=10.00,
            max_tokens=1048576,
            description="Gemini 2.5 Pro - Google production model (OpenRouter)",
        ),
        ModelType.GEMINI_25_FLASH: ModelPricing(
            model=ModelType.GEMINI_25_FLASH,
            prompt_cost_per_1m=0.30,
            completion_cost_per_1m=2.50,
            max_tokens=1048576,
            description="Gemini 2.5 Flash - Fast and cost-effective Gemini (OpenRouter)",
        ),
        # Gemini via direct Gemini API (same pricing, bare model names)
        ModelType.GEMINI_31_PRO_PREVIEW_DIRECT: ModelPricing(
            model=ModelType.GEMINI_31_PRO_PREVIEW_DIRECT,
            prompt_cost_per_1m=2.00,
            completion_cost_per_1m=12.00,
            max_tokens=1048576,
            description="Gemini 3.1 Pro Preview - Latest Google flagship (Gemini API)",
        ),
        ModelType.GEMINI_25_PRO_DIRECT: ModelPricing(
            model=ModelType.GEMINI_25_PRO_DIRECT,
            prompt_cost_per_1m=1.25,
            completion_cost_per_1m=10.00,
            max_tokens=1048576,
            description="Gemini 2.5 Pro - Google production model (Gemini API)",
        ),
        ModelType.GEMINI_25_FLASH_DIRECT: ModelPricing(
            model=ModelType.GEMINI_25_FLASH_DIRECT,
            prompt_cost_per_1m=0.30,
            completion_cost_per_1m=2.50,
            max_tokens=1048576,
            description="Gemini 2.5 Flash - Fast and cost-effective Gemini (Gemini API)",
        ),
    }

    def __init__(self, default_model: ModelType = ModelType.GPT_4O):
        """Initialize cost calculator.

        Args:
            default_model: Default model to use for cost calculations
        """
        self.default_model = default_model
        self.api_calls: list[APICall] = []
        self.encoders: dict[str, tiktoken.Encoding] = {}  # Cache for tiktoken encoders
        logger.info(f"Cost calculator initialized with default model: {default_model}")

    def get_encoder(self, model: str) -> tiktoken.Encoding:
        """Get or create tiktoken encoder for a model.

        Args:
            model: Model name

        Returns:
            Tiktoken encoder
        """
        if model not in self.encoders:
            try:
                self.encoders[model] = tiktoken.encoding_for_model(model)
            except KeyError:
                # Fallback to cl100k_base encoding for unknown models
                self.encoders[model] = tiktoken.get_encoding("cl100k_base")
                logger.warning(f"Unknown model {model}, using cl100k_base encoding")
        return self.encoders[model]

    def count_tokens(self, text: str, model: str) -> int:
        """Count tokens in text for a specific model.

        Args:
            text: Text to count tokens for
            model: Model name

        Returns:
            Number of tokens
        """
        try:
            encoder = self.get_encoder(model)
            return len(encoder.encode(text))
        except Exception as e:
            logger.error(f"Error counting tokens for model {model}: {e}")
            # Fallback: rough estimate (1 token ≈ 4 characters)
            return len(text) // 4

    def calculate_cost(
        self, prompt_tokens: int, completion_tokens: int, model: str = None
    ) -> float:
        """Calculate cost for API call.

        Args:
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            model: Model name (uses default if not provided)

        Returns:
            Cost in USD
        """
        if model is None:
            model = self.default_model.value

        # Find model pricing
        model_type = None
        for mt in ModelType:
            if mt.value == model:
                model_type = mt
                break

        if model_type is None or model_type not in self.MODEL_PRICING:
            logger.warning(f"Unknown model {model}, using default pricing")
            model_type = self.default_model

        pricing = self.MODEL_PRICING[model_type]

        prompt_cost = (prompt_tokens / 1_000_000) * pricing.prompt_cost_per_1m
        completion_cost = (
            completion_tokens / 1_000_000
        ) * pricing.completion_cost_per_1m

        return prompt_cost + completion_cost

    def record_api_call(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model: str,
        operation: str,
        attribute_type: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> APICall:
        """Record an API call for cost tracking.

        Args:
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            model: Model name
            operation: Type of operation (e.g., "arm_separation", "attribute_extraction")
            attribute_type: Specific attribute being extracted (if applicable)
            success: Whether the call was successful
            error_message: Error message if call failed

        Returns:
            APICall record
        """
        cost = self.calculate_cost(prompt_tokens, completion_tokens, model)

        api_call = APICall(
            timestamp=datetime.now(),
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost=cost,
            operation=operation,
            attribute_type=attribute_type,
            success=success,
            error_message=error_message,
        )

        self.api_calls.append(api_call)

        logger.debug(
            f"Recorded API call: {operation} | {model} | "
            f"{prompt_tokens + completion_tokens} tokens | ${cost:.6f}"
        )

        return api_call

    def get_summary(self) -> CostSummary:
        """Get comprehensive cost summary.

        Returns:
            CostSummary with detailed breakdown
        """
        if not self.api_calls:
            return CostSummary()

        total_requests = len(self.api_calls)
        total_prompt_tokens = sum(call.prompt_tokens for call in self.api_calls)
        total_completion_tokens = sum(call.completion_tokens for call in self.api_calls)
        total_tokens = total_prompt_tokens + total_completion_tokens
        total_cost = sum(call.cost for call in self.api_calls)
        successful_requests = sum(1 for call in self.api_calls if call.success)
        failed_requests = total_requests - successful_requests

        # Breakdown by operation
        calls_by_operation: dict[str, int] = {}
        cost_by_operation: dict[str, float] = {}
        for call in self.api_calls:
            op = call.operation
            calls_by_operation[op] = calls_by_operation.get(op, 0) + 1
            cost_by_operation[op] = cost_by_operation.get(op, 0) + call.cost

        # Breakdown by attribute
        calls_by_attribute: dict[str, int] = {}
        cost_by_attribute: dict[str, float] = {}
        for call in self.api_calls:
            if call.attribute_type:
                attr = call.attribute_type
                calls_by_attribute[attr] = calls_by_attribute.get(attr, 0) + 1
                cost_by_attribute[attr] = cost_by_attribute.get(attr, 0) + call.cost

        # Breakdown by model
        calls_by_model: dict[str, int] = {}
        cost_by_model: dict[str, float] = {}
        for call in self.api_calls:
            model = call.model
            calls_by_model[model] = calls_by_model.get(model, 0) + 1
            cost_by_model[model] = cost_by_model.get(model, 0) + call.cost

        return CostSummary(
            total_requests=total_requests,
            total_prompt_tokens=total_prompt_tokens,
            total_completion_tokens=total_completion_tokens,
            total_tokens=total_tokens,
            total_cost=total_cost,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            calls_by_operation=calls_by_operation,
            calls_by_attribute=calls_by_attribute,
            calls_by_model=calls_by_model,
            cost_by_operation=cost_by_operation,
            cost_by_attribute=cost_by_attribute,
            cost_by_model=cost_by_model,
        )

    def print_summary(self):
        """Print formatted cost summary."""
        summary = self.get_summary()

        print("\n" + "=" * 80)
        print("LLM API COST SUMMARY")
        print("=" * 80)
        print(f"Total Requests: {summary.total_requests:,}")
        print(f"Successful Requests: {summary.successful_requests:,}")
        print(f"Failed Requests: {summary.failed_requests:,}")
        print(
            f"Success Rate: {(summary.successful_requests / max(summary.total_requests, 1)) * 100:.1f}%"
        )
        print()
        print(f"Total Prompt Tokens: {summary.total_prompt_tokens:,}")
        print(f"Total Completion Tokens: {summary.total_completion_tokens:,}")
        print(f"Total Tokens: {summary.total_tokens:,}")
        print(f"Total Cost: ${summary.total_cost:.6f}")
        print()

        if summary.calls_by_operation:
            print("COST BY OPERATION:")
            print("-" * 40)
            for operation, cost in sorted(
                summary.cost_by_operation.items(), key=lambda x: x[1], reverse=True
            ):
                calls = summary.calls_by_operation[operation]
                print(f"{operation:25} | {calls:3d} calls | ${cost:8.6f}")
            print()

        if summary.calls_by_attribute:
            print("COST BY ATTRIBUTE:")
            print("-" * 40)
            for attribute, cost in sorted(
                summary.cost_by_attribute.items(), key=lambda x: x[1], reverse=True
            ):
                calls = summary.calls_by_attribute[attribute]
                print(f"{attribute:25} | {calls:3d} calls | ${cost:8.6f}")
            print()

        if summary.calls_by_model:
            print("COST BY MODEL:")
            print("-" * 40)
            for model, cost in sorted(
                summary.cost_by_model.items(), key=lambda x: x[1], reverse=True
            ):
                calls = summary.calls_by_model[model]
                print(f"{model:25} | {calls:3d} calls | ${cost:8.6f}")
            print()

        print("=" * 80)

    def save_detailed_report(self, filepath: str):
        """Save detailed cost report to JSON file.

        Args:
            filepath: Path to save the report
        """
        summary = self.get_summary()

        report = {
            "summary": {
                "total_requests": summary.total_requests,
                "total_prompt_tokens": summary.total_prompt_tokens,
                "total_completion_tokens": summary.total_completion_tokens,
                "total_tokens": summary.total_tokens,
                "total_cost": summary.total_cost,
                "successful_requests": summary.successful_requests,
                "failed_requests": summary.failed_requests,
                "success_rate": (
                    summary.successful_requests / max(summary.total_requests, 1)
                )
                * 100,
            },
            "breakdown": {
                "by_operation": summary.cost_by_operation,
                "by_attribute": summary.cost_by_attribute,
                "by_model": summary.cost_by_model,
            },
            "api_calls": [
                {
                    "timestamp": call.timestamp.isoformat(),
                    "model": call.model,
                    "prompt_tokens": call.prompt_tokens,
                    "completion_tokens": call.completion_tokens,
                    "cost": call.cost,
                    "operation": call.operation,
                    "attribute_type": call.attribute_type,
                    "success": call.success,
                    "error_message": call.error_message,
                }
                for call in self.api_calls
            ],
        }

        with open(filepath, "w") as f:
            json.dump(report, f, indent=2)

        logger.info(f"Detailed cost report saved to: {filepath}")

    def estimate_cost_for_text(
        self,
        prompt_text: str,
        estimated_completion_length: int = 1000,
        model: str = None,
    ) -> dict[str, Any]:
        """Estimate cost for processing text.

        Args:
            prompt_text: Text to be sent as prompt
            estimated_completion_length: Estimated completion length in characters
            model: Model to use (uses default if not provided)

        Returns:
            Dictionary with cost estimates
        """
        if model is None:
            model = self.default_model.value

        prompt_tokens = self.count_tokens(prompt_text, model)
        # Rough estimate: 1 token ≈ 4 characters
        estimated_completion_tokens = estimated_completion_length // 4

        cost = self.calculate_cost(prompt_tokens, estimated_completion_tokens, model)

        return {
            "model": model,
            "prompt_tokens": prompt_tokens,
            "estimated_completion_tokens": estimated_completion_tokens,
            "estimated_total_tokens": prompt_tokens + estimated_completion_tokens,
            "estimated_cost": cost,
        }

    def reset(self):
        """Reset all tracking data."""
        self.api_calls.clear()
        logger.info("Cost calculator reset")
