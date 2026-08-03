"""Gemini LLM service for clinical trial parameter extraction.
"""

import asyncio
import json
import logging
import random
import re
from typing import Any, Optional, TypeVar

from pydantic import BaseModel, ValidationError

from ..domain.extraction_interfaces import LLMService
from ..domain.structured_llm_interfaces import StructuredLLMService
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

# 429 backoff. Vertex Gemini runs on Dynamic Shared Quota: a 429 means demand
# momentarily exceeded the shared pool and usually clears in 1-5s, so we start
# small and grow exponentially with jitter rather than sitting on a 60s floor.
_BACKOFF_BASE_SECONDS = 1.0
_BACKOFF_CAP_SECONDS = 30.0

# Bounded per-request timeout (ms); there is no default client timeout, so a
# stalled socket would otherwise hang a worker forever. On the streamed path
# (generate_structured) this bounds the gap between chunks, not total generation
# time - so a long response is free to take as long as it needs.
_REQUEST_TIMEOUT_MS = 90_000

_RETRYABLE_TOKENS = (
    "429",
    "RESOURCE_EXHAUSTED",
    "RATE_LIMIT",
    "DEADLINE_EXCEEDED",
    "504",
    "TIMEOUT",
    "TIMED OUT",
)


def _is_retryable_error(exc: BaseException) -> bool:
    """True for transient errors worth retrying: 429/quota and timeout/deadline.

    Retrying a timed-out generate call is safe - the call is side-effect-free,
    so at worst a completed-but-undelivered response is re-billed (rare, cheap).
    """
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return True
    msg = str(exc).upper()
    return any(token in msg for token in _RETRYABLE_TOKENS)


_RETRY_AFTER_RE = re.compile(
    r"retry[-_ ]?(?:delay|after)['\"\s:]+(\d+(?:\.\d+)?)\s*s", re.IGNORECASE
)


def _parse_retry_after(error: str) -> float | None:
    """Extract a server-suggested retry delay (seconds) from an error string.

    Vertex RESOURCE_EXHAUSTED errors may carry a ``retryDelay: '7s'`` hint.
    Returns None when no hint is present.
    """
    match = _RETRY_AFTER_RE.search(error)
    return float(match.group(1)) if match else None


def _backoff_seconds(attempt: int, retry_after: float | None = None) -> float:
    """Seconds to wait before retry ``attempt`` (0-indexed).

    Honors a server-provided ``retry_after`` when present (still capped),
    otherwise exponential base*2**attempt plus jitter, capped.
    """
    if retry_after is not None and retry_after > 0:
        return min(retry_after, _BACKOFF_CAP_SECONDS)
    exp = min(_BACKOFF_BASE_SECONDS * (2**attempt), _BACKOFF_CAP_SECONDS)
    return exp + random.uniform(0, _BACKOFF_BASE_SECONDS)


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


class GeminiLLMService(LLMService, StructuredLLMService):
    """LLM service backed by Vertex AI via the google-genai SDK.

    Supports two authentication modes:

    * API key (Vertex Express Mode) — pass ``api_key``. No ADC or gcloud
      CLI required.
    * Application Default Credentials — pass ``project`` and ``location``
      instead, and the SDK resolves credentials from the ambient ADC.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = _DEFAULT_MODEL,
        temperature: float = 0.0,
        max_tokens: int = 16384,
        cost_calculator: Optional[CostCalculator] = None,
        project: Optional[str] = None,
        location: Optional[str] = None,
    ) -> None:
        if not api_key and not project:
            raise ValueError(
                "Either api_key (Express Mode) or project (ADC) is required"
            )

        # Accept OpenRouter-style names like "google/gemini-3.1-pro-preview"
        model = model.removeprefix("google/")

        self._api_key = api_key
        self._project = project
        self._location = location
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._cost_calculator = cost_calculator
        self._client = self._build_client()

        logger.info(
            "GeminiLLMService initialised | model=%s (Vertex AI, auth=%s)",
            model,
            "api_key" if api_key else "adc",
        )

    def _build_client(self) -> Any:
        from google import genai
        from google.genai import types

        http_options = types.HttpOptions(timeout=_REQUEST_TIMEOUT_MS)
        if self._api_key:
            return genai.Client(
                vertexai=True, api_key=self._api_key, http_options=http_options
            )
        return genai.Client(
            vertexai=True,
            project=self._project,
            location=self._location,
            http_options=http_options,
        )

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
                if _is_retryable_error(exc) and attempt < max_retries - 1:
                    # DSQ-aware backoff: honor a server retry hint, else a small
                    # exponential with jitter (see _backoff_seconds).
                    wait_sec = _backoff_seconds(attempt, _parse_retry_after(str(exc)))
                    logger.warning(
                        "Transient error (429/timeout) on attempt %d/%d — retrying in %.0fs",
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

        def _sync_call() -> tuple[str, Any]:
            # Streamed, not buffered: a non-streaming call sends nothing until the
            # whole generation finishes, so the client read timeout ends up bounding
            # total generation time and long judge responses trip it. Streaming makes
            # the same timeout bound the gap between chunks instead.
            text_parts: list[str] = []
            usage: Any = None
            for chunk in self._client.models.generate_content_stream(
                model=effective_model,
                contents=prompt,
                config=config,
            ):
                part = chunk.text
                if part:
                    text_parts.append(part)
                # Usage arrives on the final chunk.
                if getattr(chunk, "usage_metadata", None) is not None:
                    usage = chunk.usage_metadata
            return "".join(text_parts), usage

        last_exc: Optional[Exception] = None
        for attempt in range(max_retries):
            try:
                text, usage_metadata = await asyncio.to_thread(_sync_call)
                self._record_usage(
                    usage_metadata,
                    model=effective_model,
                    operation=operation,
                    attribute_type=attribute_type,
                    success=True,
                )
                # `response.parsed` is not populated for streamed responses, so the
                # accumulated text always goes through the JSON path below.
                try:
                    return response_schema.model_validate_json(text)
                except ValidationError:
                    # Gemini may return truncated JSON when output is long (e.g.
                    # a verbatim quote that hits max_tokens). Try the repair path
                    # before treating this as a hard failure.
                    repaired = _parse_json_response(text)
                    if repaired:
                        return response_schema.model_validate(repaired)
                    raise
            except Exception as exc:
                last_exc = exc
                if _is_retryable_error(exc) and attempt < max_retries - 1:
                    wait_sec = _backoff_seconds(attempt, _parse_retry_after(str(exc)))
                    logger.warning(
                        "Transient error (429/timeout) on attempt %d/%d — retrying in %.0fs",
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
            max_output_tokens=max(max_tokens, self._max_tokens),
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
        try:
            return response_schema.model_validate_json(text)
        except ValidationError:
            repaired = _parse_json_response(text)
            if repaired:
                return response_schema.model_validate(repaired)
            raise

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
