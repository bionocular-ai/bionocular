"""Gemini LLM service for clinical trial parameter extraction.
"""

import asyncio
import json
import logging
import random
import re
from typing import Any, Optional, TypeVar

from pydantic import BaseModel

from ..domain.extraction_interfaces import LLMService
from .cost_calculator import CostCalculator

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gemini-3.1-pro-preview"
_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
_JSON_OBJECT_RE = re.compile(r"\{[\s\S]*\}", re.DOTALL)
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")

# Minimum input tokens required for Gemini explicit context caching on the
# Gemini 3.x Pro family. Historically 32_768 on 2.5 Pro; conservatively reused
# here for 3.1 Pro until Google publishes a different floor.
# Source: https://ai.google.dev/gemini-api/docs/caching (see "Minimum input
# token count" section per model).
GEMINI_CACHE_MIN_TOKENS = 32_768

# Cheap rule-of-thumb: 1 token ~= 4 chars of English. Intentionally conservative
# so we only short-circuit when we are clearly below the floor; borderline docs
# still attempt the SDK call and fall back gracefully on rejection.
_CHARS_PER_TOKEN_ESTIMATE = 4


def _inline_pydantic_schema(schema_cls: type[BaseModel]) -> dict[str, Any]:
    """Render a Pydantic JSON schema with all ``$ref`` / ``$defs`` inlined.

    Gemini's ``types.Schema`` validator does not understand ``$ref``; it
    expects every nested sub-schema to be inlined. Pydantic's default
    ``model_json_schema()`` emits ``$ref`` for nested models — including the
    ``additionalProperties`` shape produced by ``dict[str, NestedModel]``.
    Resolve refs once at the API boundary so callers can keep using Pydantic
    models naturally for both schema declaration and response validation.
    """
    schema = schema_cls.model_json_schema()
    defs: dict[str, Any] = schema.get("$defs", {})

    def _resolve(node: Any) -> Any:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                target = defs.get(ref.removeprefix("#/$defs/"))
                if target is None:
                    raise ValueError(f"Unresolvable $ref in schema: {ref}")
                return _resolve(target)
            return {k: _resolve(v) for k, v in node.items() if k != "$defs"}
        if isinstance(node, list):
            return [_resolve(v) for v in node]
        return node

    return _resolve(schema)


def _repair_truncated_json(text: str) -> str:
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


def _clean_json(text: str) -> str:
    return _TRAILING_COMMA_RE.sub(r"\1", text)


def _try_parse(text: str) -> dict[str, Any] | None:
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
    fence_match = _CODE_FENCE_RE.search(text)
    candidate = fence_match.group(1).strip() if fence_match else text.strip()

    result = _try_parse(candidate)
    if result is not None:
        return result

    obj_match = _JSON_OBJECT_RE.search(candidate)
    if obj_match:
        obj_text = obj_match.group()
        result = _try_parse(obj_text)
        if result is not None:
            return result
        repaired = _repair_truncated_json(obj_text)
        if repaired != obj_text:
            result = _try_parse(repaired)
            if result is not None:
                return result

    stripped = candidate.lstrip()
    if stripped.startswith("{"):
        repaired = _repair_truncated_json(stripped)
        if repaired != stripped:
            result = _try_parse(repaired)
            if result is not None:
                return result

    logger.warning("Could not parse JSON from response: %s", text[:200])
    return {}


class GeminiLLMService(LLMService):
    """LLM service backed by Vertex AI via the google-genai SDK.

    Authenticates using GOOGLE_API_KEY (linked to the GCP project on
    Google's backend) — no ADC or gcloud CLI required.
    """

    def __init__(
        self,
        api_key: str,
        model: str = _DEFAULT_MODEL,
        temperature: float = 0.0,
        max_tokens: int = 8192,
        cost_calculator: Optional[CostCalculator] = None,
    ) -> None:
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is required")

        # Accept OpenRouter-style names like "google/gemini-3.1-pro-preview"
        model = model.removeprefix("google/")

        self._api_key = api_key
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._cost_calculator = cost_calculator
        self._client = self._build_client()

        logger.info("GeminiLLMService initialised | model=%s (Vertex AI)", model)

    def _build_client(self) -> Any:
        from google import genai

        return genai.Client(vertexai=True, api_key=self._api_key)

    def _record_usage(
        self,
        usage_metadata: Any,
        model: str,
        operation: str,
        attribute_type: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> None:
        # Capture into a local so static analysers can narrow Optional → concrete type.
        # Instance attributes cannot be safely narrowed through if-guards because
        # another coroutine could mutate them between the check and the use.
        cost_calc = self._cost_calculator
        if cost_calc is None:
            return
        input_tokens = getattr(usage_metadata, "prompt_token_count", 0) or 0
        output_tokens = getattr(usage_metadata, "candidates_token_count", 0) or 0
        cost_calc.record_api_call(
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
            model=model,
            operation=operation,
            attribute_type=attribute_type,
            success=success,
            error_message=error_message,
        )

    def _is_rate_limit_error(self, exc: BaseException) -> bool:
        """Return True for 429 / RESOURCE_EXHAUSTED transient quota errors."""
        msg = str(exc).upper()
        return "429" in msg or "RESOURCE_EXHAUSTED" in msg or "RATE_LIMIT" in msg

    async def generate_response(
        self,
        prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        model_name: Optional[str] = None,
        operation: str = "trial_extraction",
        attribute_type: Optional[str] = None,
        max_retries: int = 3,
    ) -> str:
        from google.genai import types

        effective_model = (model_name or self._model).removeprefix("google/")
        # Use the larger of the per-call override and the instance default
        # to avoid truncated responses on large prompts.
        effective_max_tokens = max(max_tokens, self._max_tokens)
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=effective_max_tokens,
        )

        def _sync_call() -> Any:
            return self._client.models.generate_content(
                model=effective_model,
                contents=prompt,
                config=config,
            )

        last_exc: Optional[Exception] = None
        for attempt in range(max_retries):
            try:
                response = await asyncio.to_thread(_sync_call)
                text: str = response.text or ""
                self._record_usage(
                    response.usage_metadata,
                    model=effective_model,
                    operation=operation,
                    attribute_type=attribute_type,
                    success=True,
                )
                logger.debug(
                    "Gemini response | model=%s op=%s len=%d",
                    effective_model,
                    operation,
                    len(text),
                )
                return text
            except Exception as exc:
                last_exc = exc
                if self._is_rate_limit_error(exc) and attempt < max_retries - 1:
                    # Exponential backoff starting at 60 s with ±5 s jitter,
                    # capped at 300 s — matches Google's recommended handling
                    # for RESOURCE_EXHAUSTED / 429 responses.
                    wait_sec = min(60 * (2**attempt) + random.uniform(0, 5), 300)
                    logger.warning(
                        "Rate limit (429) on attempt %d/%d — retrying in %.0fs",
                        attempt + 1,
                        max_retries,
                        wait_sec,
                    )
                    await asyncio.sleep(wait_sec)
                else:
                    logger.error(
                        "Gemini call failed | model=%s op=%s error=%s",
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

        assert last_exc is not None
        self._record_usage(
            None,
            model=effective_model,
            operation=operation,
            attribute_type=attribute_type,
            success=False,
            error_message=str(last_exc),
        )
        raise last_exc

    async def generate_structured(
        self,
        prompt: str,
        response_schema: type[T],
        temperature: float = 0.0,
        max_tokens: int = 4096,
        model_name: Optional[str] = None,
        operation: str = "structured_extraction",
        attribute_type: Optional[str] = None,
        max_retries: int = 3,
    ) -> T:
        """Generate a response constrained to `response_schema` (a Pydantic class).

        Returns a parsed instance of `response_schema`. Raises on rate limit
        exhaustion or unrecoverable API failure (same retry policy as
        `generate_response`).
        """
        from google.genai import types

        effective_model = (model_name or self._model).removeprefix("google/")
        effective_max_tokens = max(max_tokens, self._max_tokens)
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=effective_max_tokens,
            response_mime_type="application/json",
            response_schema=_inline_pydantic_schema(response_schema),
        )

        def _sync_call() -> Any:
            return self._client.models.generate_content(
                model=effective_model,
                contents=prompt,
                config=config,
            )

        last_exc: Optional[Exception] = None
        for attempt in range(max_retries):
            try:
                response = await asyncio.to_thread(_sync_call)
                self._record_usage(
                    response.usage_metadata,
                    model=effective_model,
                    operation=operation,
                    attribute_type=attribute_type,
                    success=True,
                )
                # SDK exposes `parsed` when response_schema is a Pydantic class.
                parsed = getattr(response, "parsed", None)
                if isinstance(parsed, response_schema):
                    return parsed
                # Fallback: parse from JSON text (covers SDK versions that don't
                # populate `parsed` reliably).
                text = response.text or ""
                return response_schema.model_validate_json(text)
            except Exception as exc:
                last_exc = exc
                if self._is_rate_limit_error(exc) and attempt < max_retries - 1:
                    wait_sec = min(60 * (2**attempt) + random.uniform(0, 5), 300)
                    logger.warning(
                        "Rate limit (429) on attempt %d/%d — retrying in %.0fs",
                        attempt + 1,
                        max_retries,
                        wait_sec,
                    )
                    await asyncio.sleep(wait_sec)
                else:
                    logger.error(
                        "Gemini structured call failed | model=%s op=%s error=%s",
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

        assert last_exc is not None
        raise last_exc

    async def create_context_cache(
        self,
        doc_text: str,
        system_instruction: str,
        ttl_seconds: int = 3600,
    ) -> str | None:
        """Create an explicit Gemini context cache for `doc_text`.

        Returns the cache resource name (usable as a `cached_content` reference)
        or `None` if the document is below Gemini's caching floor or the SDK
        rejects the request as too small.
        """
        estimated_tokens = len(doc_text) // _CHARS_PER_TOKEN_ESTIMATE
        if estimated_tokens < GEMINI_CACHE_MIN_TOKENS:
            logger.warning(
                "Skipping context cache — doc too short (chars=%d, est_tokens=%d, floor=%d)",
                len(doc_text),
                estimated_tokens,
                GEMINI_CACHE_MIN_TOKENS,
            )
            return None

        from google.genai import types
        from google.genai.errors import ClientError

        config = types.CreateCachedContentConfig(
            contents=[doc_text],
            system_instruction=system_instruction,
            ttl=f"{ttl_seconds}s",
        )

        def _sync_call() -> Any:
            return self._client.caches.create(model=self._model, config=config)

        try:
            cached = await asyncio.to_thread(_sync_call)
        except ClientError as exc:
            # 400 INVALID_ARGUMENT covers the MIN_TOKEN rejection path. Other
            # 4xx (auth, quota) we still want to swallow into a fallback rather
            # than fail extraction — the caller will inline the doc instead.
            logger.warning(
                "Gemini cache create rejected (chars=%d, est_tokens=%d): %s",
                len(doc_text),
                estimated_tokens,
                exc,
            )
            return None

        name: str | None = getattr(cached, "name", None)
        return name

    async def cached_or_inline_generate(
        self,
        cache_id: str | None,
        doc_text: str,
        prompt: str,
        response_schema: type[T],
        temperature: float = 0.1,
        max_tokens: int = 4000,
    ) -> T:
        """Generate structured output, transparently using a cache when available.

        If `cache_id` is provided, generates against the cached document context.
        Otherwise prepends `doc_text` inline to `prompt` and falls through to
        `generate_structured`. Callers receive the same parsed `response_schema`
        instance regardless of branch.
        """
        if cache_id is None:
            inline_prompt = f"{doc_text}\n\n{prompt}"
            return await self.generate_structured(
                inline_prompt,
                response_schema=response_schema,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        from google.genai import types

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            response_mime_type="application/json",
            response_schema=_inline_pydantic_schema(response_schema),
            cached_content=cache_id,
        )

        def _sync_call() -> Any:
            return self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=config,
            )

        response = await asyncio.to_thread(_sync_call)
        self._record_usage(
            getattr(response, "usage_metadata", None),
            model=self._model,
            operation="cached_structured_extraction",
            success=True,
        )
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, response_schema):
            return parsed
        text = response.text or ""
        return response_schema.model_validate_json(text)

    async def delete_cache(self, cache_id: str | None) -> None:
        """Delete a previously created context cache. No-op when `cache_id` is None."""
        if cache_id is None:
            return

        def _sync_call() -> Any:
            return self._client.caches.delete(name=cache_id)

        await asyncio.to_thread(_sync_call)

    async def extract_structured_data(
        self,
        prompt: str,
        expected_format: str,
        operation: str = "structured_extraction",
        attribute_type: Optional[str] = None,
    ) -> dict[str, Any]:
        full_prompt = (
            f"{prompt}\n\nReturn ONLY valid JSON. No prose, no markdown fences.\n"
            f"Schema: {expected_format}"
        )
        text = await self.generate_response(
            full_prompt, operation=operation, attribute_type=attribute_type
        )
        return _parse_json_response(text)

    async def extract_json(
        self,
        prompt: str,
        operation: str = "extraction",
        attribute_type: Optional[str] = None,
        max_retries: int = 1,
    ) -> dict[str, Any]:
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
