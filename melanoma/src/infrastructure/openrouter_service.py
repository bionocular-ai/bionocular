"""OpenRouter LLM service for clinical trial parameter extraction.

Wraps LangChain's ChatOpenAI against the OpenRouter API endpoint, which
exposes an OpenAI-compatible interface for 400+ models including Gemini.

Cost tracking uses actual token counts returned in the API response
(via AIMessage.usage_metadata) rather than tiktoken estimates, giving
accurate billing numbers for non-OpenAI models.
"""

import json
import logging
import re
from typing import Any, Optional

from ..domain.extraction_interfaces import LLMService
from .cost_calculator import CostCalculator

logger = logging.getLogger(__name__)

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_DEFAULT_MODEL = "google/gemini-3.1-pro-preview"
_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
_JSON_OBJECT_RE = re.compile(r"\{[\s\S]*\}", re.DOTALL)
# Trailing commas before closing brackets/braces (not valid in strict JSON)
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")


def _repair_truncated_json(text: str) -> str:
    """Attempt to close a JSON object/string that was cut off mid-stream.

    Walks character-by-character tracking open strings and container
    stack, then appends whatever closing characters are needed.  This
    handles the case where a model hits a stop-sequence or token limit
    inside a string value (e.g. ``"Intralesional (IL``).
    """
    in_string = False
    escape_next = False
    stack: list[str] = []

    for ch in text:
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
        elif not in_string:
            if ch in "{[":
                stack.append(ch)
            elif ch in "}]":
                if stack:
                    stack.pop()

    suffix = ""
    if in_string:
        suffix += '"'
    for ch in reversed(stack):
        suffix += "}" if ch == "{" else "]"

    return text + suffix if suffix else text


def _get_chat_openai():
    try:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI
    except ImportError:  # pragma: no cover
        from langchain_community.chat_models import ChatOpenAI

        return ChatOpenAI


ChatOpenAI = _get_chat_openai()


def _clean_json(text: str) -> str:
    """Strip trailing commas that thinking models often leave before closing brackets."""
    return _TRAILING_COMMA_RE.sub(r"\1", text)


def _try_parse(text: str) -> dict[str, Any] | None:
    """Attempt json.loads with and without trailing-comma cleanup."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    cleaned = _clean_json(text)
    if cleaned != text:
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
    return None


def _parse_json_response(text: str) -> dict[str, Any]:
    """Robustly extract a JSON object from an LLM response.

    Handles (in order):
    1. Plain JSON (with optional trailing-comma cleanup)
    2. JSON wrapped in markdown code fences (```json ... ```)
    3. Leading/trailing prose around the first JSON object
    4. Truncated JSON (model stopped mid-string/array) — auto-repaired
       Thinking models (e.g. Gemini) can exhaust max_tokens on internal
       reasoning, leaving the JSON object truncated mid-field with a
       trailing comma before the repaired closing brace.
    """
    fence_match = _CODE_FENCE_RE.search(text)
    candidate = fence_match.group(1).strip() if fence_match else text.strip()

    # 1. Direct parse (handles trailing commas too)
    result = _try_parse(candidate)
    if result is not None:
        return result

    # 2. Find the first complete {...} block
    obj_match = _JSON_OBJECT_RE.search(candidate)
    if obj_match:
        obj_text = obj_match.group()
        result = _try_parse(obj_text)
        if result is not None:
            return result
        # Try repairing the matched block
        repaired = _repair_truncated_json(obj_text)
        if repaired != obj_text:
            result = _try_parse(repaired)
            if result is not None:
                logger.debug(
                    "Repaired truncated JSON (%d → %d chars)",
                    len(obj_text),
                    len(repaired),
                )
                return result

    # 3. Repair a top-level truncated object (regex found no closing `}`)
    stripped = candidate.lstrip()
    if stripped.startswith("{"):
        repaired = _repair_truncated_json(stripped)
        if repaired != stripped:
            result = _try_parse(repaired)
            if result is not None:
                logger.debug(
                    "Repaired top-level truncated JSON (%d → %d chars)",
                    len(stripped),
                    len(repaired),
                )
                return result

    logger.warning("Could not parse JSON from response: %s", text[:200])
    return {}


class OpenRouterLLMService(LLMService):
    """LLM service backed by OpenRouter's OpenAI-compatible API.

    Designed for clinical trial parameter extraction. Records actual
    token usage (input + output) reported by the API into the supplied
    CostCalculator so cost reports are exact, not estimated.
    """

    def __init__(
        self,
        api_key: str,
        model: str = _DEFAULT_MODEL,
        temperature: float = 0.0,
        max_tokens: int = 8192,
        cost_calculator: Optional[CostCalculator] = None,
    ) -> None:
        """Initialise the OpenRouter service.

        Args:
            api_key: OPENROUTER_API_KEY value.
            model: OpenRouter model identifier (e.g. google/gemini-3.1-pro-preview).
            temperature: Sampling temperature. 0.0 for deterministic extraction.
            max_tokens: Maximum completion tokens.
            cost_calculator: Optional cost calculator; if supplied, every call
                             is recorded with actual API-reported token counts.
        """
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is required")

        self._api_key = api_key
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._cost_calculator = cost_calculator
        self._client = self._build_client(model, temperature, max_tokens)

        logger.info("OpenRouterLLMService initialised | model=%s", model)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_client(self, model: str, temperature: float, max_tokens: int) -> Any:
        return ChatOpenAI(
            model=model,
            openai_api_key=self._api_key,
            openai_api_base=_OPENROUTER_BASE_URL,
            temperature=temperature,
            max_tokens=max_tokens,
            max_retries=3,
            request_timeout=120,
        )

    def _record_usage(
        self,
        response: Any,
        model: str,
        operation: str,
        attribute_type: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> None:
        """Record token usage from an AIMessage into CostCalculator."""
        if self._cost_calculator is None:
            return

        input_tokens = 0
        output_tokens = 0

        # LangChain v0.3+ exposes usage_metadata on AIMessage
        usage = getattr(response, "usage_metadata", None)
        if usage:
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
        else:
            # Fallback: response_metadata from older LangChain versions
            meta = getattr(response, "response_metadata", {}) or {}
            token_usage = meta.get("token_usage") or meta.get("usage") or {}
            input_tokens = token_usage.get("prompt_tokens", 0) or token_usage.get(
                "input_tokens", 0
            )
            output_tokens = token_usage.get("completion_tokens", 0) or token_usage.get(
                "output_tokens", 0
            )

        self._cost_calculator.record_api_call(
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
            model=model,
            operation=operation,
            attribute_type=attribute_type,
            success=success,
            error_message=error_message,
        )

    # ------------------------------------------------------------------
    # LLMService interface
    # ------------------------------------------------------------------

    async def generate_response(
        self,
        prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        model_name: Optional[str] = None,
        operation: str = "trial_extraction",
        attribute_type: Optional[str] = None,
    ) -> str:
        """Generate a text completion via OpenRouter.

        Args:
            prompt: The full prompt string.
            temperature: Override sampling temperature for this call.
            max_tokens: Override max completion tokens for this call.
            model_name: Override model for this call.
            operation: Label for cost tracking (e.g. "treatment_name").
            attribute_type: Attribute being extracted, for cost breakdown.

        Returns:
            Raw text content of the model response.
        """
        effective_model = model_name or self._model

        client = (
            self._build_client(effective_model, temperature, max_tokens)
            if (model_name and model_name != self._model)
            else self._client
        )

        try:
            response = await client.ainvoke(prompt)
            text: str = (
                response.content if hasattr(response, "content") else str(response)
            )
            self._record_usage(
                response,
                model=effective_model,
                operation=operation,
                attribute_type=attribute_type,
                success=True,
            )
            logger.debug(
                "OpenRouter response | model=%s op=%s len=%d",
                effective_model,
                operation,
                len(text),
            )
            return text

        except Exception as exc:
            logger.error(
                "OpenRouter call failed | model=%s op=%s error=%s",
                effective_model,
                operation,
                exc,
            )
            self._record_usage(
                None,
                model=effective_model,
                operation=operation,
                attribute_type=attribute_type,
                success=False,
                error_message=str(exc),
            )
            raise

    async def extract_structured_data(
        self,
        prompt: str,
        expected_format: str,
        operation: str = "structured_extraction",
        attribute_type: Optional[str] = None,
    ) -> dict[str, Any]:
        """Generate a response and parse it as JSON.

        Args:
            prompt: The full prompt string.
            expected_format: JSON schema hint appended to the prompt.
            operation: Label for cost tracking.
            attribute_type: Attribute being extracted.

        Returns:
            Parsed JSON dict, or empty dict if parsing fails.
        """
        full_prompt = (
            f"{prompt}\n\nReturn ONLY valid JSON. No prose, no markdown fences.\n"
            f"Schema: {expected_format}"
        )
        text = await self.generate_response(
            full_prompt,
            operation=operation,
            attribute_type=attribute_type,
        )
        return _parse_json_response(text)

    async def extract_json(
        self,
        prompt: str,
        operation: str = "extraction",
        attribute_type: Optional[str] = None,
        max_retries: int = 1,
    ) -> dict[str, Any]:
        """Generate a response expected to be pure JSON and parse it.

        Retries once on a completely empty parse result (e.g. truncated
        response that cannot be repaired) so transient model failures
        do not silently produce missing data.

        Args:
            prompt: Fully formed prompt with embedded JSON schema.
            operation: Label for cost tracking.
            attribute_type: Attribute being extracted.
            max_retries: Number of additional attempts if result is empty.

        Returns:
            Parsed JSON dict, or empty dict if all attempts fail.
        """
        for attempt in range(1 + max_retries):
            text = await self.generate_response(
                prompt, operation=operation, attribute_type=attribute_type
            )
            result = _parse_json_response(text)
            if result:
                return result
            if attempt < max_retries:
                logger.warning(
                    "Empty JSON result on attempt %d/%d for %s — retrying",
                    attempt + 1,
                    1 + max_retries,
                    operation,
                )
        return {}
