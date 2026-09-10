"""Gemini LLM service for clinical trial parameter extraction.
"""

import asyncio
import json
import logging
import os
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


def is_retryable_error(exc: BaseException) -> bool:
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


# Quota rejections that arrive with no server retry hint are admission-control
# refusals, not congestion: the answer does not change however long we wait, and
# every attempt re-sends the whole prompt. One ASCO run burned ~2.7M input tokens
# on 455 such retries, all of which failed. Retry a quota error only when the
# server tells us to; a run-level resume is the real retry mechanism.
_QUOTA_TOKENS = ("429", "RESOURCE_EXHAUSTED", "RATE_LIMIT")


# A run that has been refused this many times in a row is not going to recover
# inside the same run: the refusals are admission control, not congestion. One
# ASCO 2026 run attempted 62 abstracts, completed 2, and spent a separator call
# on each of the other 60 before anyone noticed. Stop and let resume retry later.
QUOTA_BREAKER_THRESHOLD = 5


class QuotaRefusedError(Exception):
    """Raised when consecutive quota refusals show the run cannot make progress.

    An ordinary exception on purpose. Making it travel was tried twice and lost
    twice: the separator degrades on ``except Exception``, and the family
    ``gather(return_exceptions=True)`` captures ``BaseException`` too and turns
    it into a "family_extraction_failed" string. So the breaker is *state* on
    this service - see :attr:`quota_tripped` - and it does not matter who eats
    this exception, because the next call short-circuits regardless.
    """


class TruncatedResponseError(RuntimeError):
    """Raised when the model stopped at max_output_tokens.

    The JSON repair path can make a truncated response parse, which turns a
    cut-off answer into a plausible-looking one. Truncation is a real failure -
    surface it so the caller records it and a re-run can retry the document.
    """


def _is_hintless_quota_refusal(exc: BaseException) -> bool:
    """True for a quota rejection carrying no server retry hint."""
    if _parse_retry_after(str(exc)) is not None:
        return False
    return any(token in str(exc).upper() for token in _QUOTA_TOKENS)


def _finish_reason_of(response: Any) -> str:
    """Best-effort finish reason of a response or stream chunk, "" when absent."""
    candidates = getattr(response, "candidates", None) or []
    if not isinstance(candidates, (list, tuple)) or not candidates:
        return ""
    reason = getattr(candidates[0], "finish_reason", None)
    if reason is None:
        return ""
    return getattr(reason, "name", None) or str(reason)


def retry_delay_for(exc: BaseException, attempt: int) -> float | None:
    """Seconds to wait before retrying ``exc``, or None to stop retrying now.

    Deliberately distinct from :func:`is_retryable_error`, which answers a
    different question - "is this transient?" - for callers that degrade rather
    than retry (see treatment_arm_separator).
    """
    if not is_retryable_error(exc):
        return None
    retry_after = _parse_retry_after(str(exc))
    if retry_after is not None:
        return _backoff_seconds(attempt, retry_after)
    if any(token in str(exc).upper() for token in _QUOTA_TOKENS):
        return None
    return _backoff_seconds(attempt)


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


def vertex_env() -> tuple[str, str]:
    """Read the Vertex ADC project and location from the environment.

    Raises:
        RuntimeError: if either variable is unset, naming the missing ones.
    """
    project = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "")
    missing = [
        name
        for name, value in (
            ("GOOGLE_CLOUD_PROJECT", project),
            ("GOOGLE_CLOUD_LOCATION", location),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(f"{', '.join(missing)} is not set in the environment")
    return project, location


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
        self._consecutive_quota_refusals = 0
        self._client = self._build_client()

        logger.info(
            "GeminiLLMService initialised | model=%s (Vertex AI, auth=%s)",
            model,
            "api_key" if api_key else "adc",
        )

    @property
    def quota_tripped(self) -> bool:
        """True once consecutive refusals show the run cannot make progress."""
        return self._consecutive_quota_refusals >= QUOTA_BREAKER_THRESHOLD

    def _raise_if_quota_tripped(self) -> None:
        """Refuse to send a request the service already knows will be refused.

        ponytail: a tripped run drains its queue as instant failures rather than
        halting - each remaining document costs no network call but is still
        written as a partial, and resume retries it. Check `quota_tripped` in
        the pipeline loop if a run must stop dead instead.
        """
        if not self.quota_tripped:
            return
        raise QuotaRefusedError(
            f"{self._consecutive_quota_refusals} consecutive quota refusals from "
            f"{self._model} - not sending further requests. Progress already "
            "written is kept; re-run to resume."
        )

    def _note_quota_refusal(self, exc: BaseException) -> None:
        """Count a hintless quota refusal; raise once the run is clearly stuck.

        Any successful call resets the count, so intermittent refusals never
        accumulate into a trip.
        """
        if not _is_hintless_quota_refusal(exc):
            return
        self._consecutive_quota_refusals += 1
        if self.quota_tripped:
            logger.error(
                "Quota breaker tripped after %d consecutive refusals from %s",
                self._consecutive_quota_refusals,
                self._model,
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
        max_retries: int = 6,
    ) -> str:
        self._raise_if_quota_tripped()

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
                self._consecutive_quota_refusals = 0
                return text
            except Exception as exc:
                last_exc = exc
                wait_sec = retry_delay_for(exc, attempt)
                if wait_sec is not None and attempt < max_retries - 1:
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
                    self._note_quota_refusal(exc)
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
        max_retries: int = 6,
        cache_id: str | None = None,
    ) -> T:
        """Generate a response constrained to `response_schema` (a Pydantic class).

        Returns a parsed instance of `response_schema`. Raises on rate limit
        exhaustion or unrecoverable API failure (same retry policy as
        `generate_response`).
        """
        self._raise_if_quota_tripped()

        from google.genai import types

        effective_model = (model_name or self._model).removeprefix("google/")
        effective_max_tokens = max(max_tokens, self._max_tokens)
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=effective_max_tokens,
            response_mime_type="application/json",
            response_schema=_inline_pydantic_schema(response_schema),
            cached_content=cache_id,
        )

        def _sync_call() -> tuple[str, Any, str]:
            # Streamed, not buffered: a non-streaming call sends nothing until the
            # whole generation finishes, so the client read timeout ends up bounding
            # total generation time and long judge responses trip it. Streaming makes
            # the same timeout bound the gap between chunks instead.
            text_parts: list[str] = []
            usage: Any = None
            finish_reason = ""
            for chunk in self._client.models.generate_content_stream(
                model=effective_model,
                contents=prompt,
                config=config,
            ):
                part = chunk.text
                if part:
                    text_parts.append(part)
                # Usage and the finish reason arrive on the final chunk.
                if getattr(chunk, "usage_metadata", None) is not None:
                    usage = chunk.usage_metadata
                reason = _finish_reason_of(chunk)
                if reason:
                    finish_reason = reason
            return "".join(text_parts), usage, finish_reason

        last_exc: Optional[Exception] = None
        for attempt in range(max_retries):
            try:
                text, usage_metadata, finish_reason = await asyncio.to_thread(
                    _sync_call
                )
                self._record_usage(
                    usage_metadata,
                    model=effective_model,
                    operation=operation,
                    attribute_type=attribute_type,
                    success=True,
                )
                self._consecutive_quota_refusals = 0
                if finish_reason == "MAX_TOKENS":
                    # Repairing this would close the dangling braces and hand the
                    # caller a cut-off answer stamped with a normal confidence.
                    raise TruncatedResponseError(
                        f"{operation} stopped at max_output_tokens "
                        f"({effective_max_tokens}); response is incomplete"
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
            except TruncatedResponseError:
                raise
            except Exception as exc:
                last_exc = exc
                wait_sec = retry_delay_for(exc, attempt)
                if wait_sec is not None and attempt < max_retries - 1:
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
                    self._note_quota_refusal(exc)
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

        If `cache_id` is provided, the document context comes from the cache;
        otherwise `doc_text` is prepended inline to `prompt`. Both branches go
        through `generate_structured`, so both get its retry policy, streaming
        read-timeout behaviour, usage recording and truncation guard - an
        earlier version issued the cached call bare, which bypassed all four on
        exactly the path the 429s arrive on.
        """
        return await self.generate_structured(
            prompt if cache_id is not None else f"{doc_text}\n\n{prompt}",
            response_schema=response_schema,
            temperature=temperature,
            max_tokens=max_tokens,
            operation=(
                "cached_structured_extraction"
                if cache_id is not None
                else "structured_extraction"
            ),
            cache_id=cache_id,
        )

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
