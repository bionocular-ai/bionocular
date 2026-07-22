"""Interface for LLM calls that return a typed, schema-constrained object.

Segregated from the broader ``LLMService`` (text/dict extraction) so callers that
only need structured output - notably the validation judge - depend on just this
one method. ``GeminiLLMService`` implements it; the OpenRouter backend does not,
and is not used for structured output.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class StructuredLLMService(ABC):
    """Contract for generating a response constrained to a Pydantic schema."""

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        response_schema: type[T],
        temperature: float = 0.0,
        max_tokens: int = 4096,
        model_name: str | None = None,
        operation: str = "structured_extraction",
        attribute_type: str | None = None,
        max_retries: int = 3,
    ) -> T:
        """Return a parsed instance of ``response_schema``.

        Implementations must record token usage against their cost calculator and
        apply retry/backoff on rate-limit errors, raising on exhaustion.
        """
        raise NotImplementedError
