"""Tests for the three gaps found reviewing the Gemini hot path.

1. the cached branch of ``cached_or_inline_generate`` retried nothing
2. a MAX_TOKENS truncation was repaired blind and looked like a good answer
3. nothing noticed a run being refused over and over (see the ASCO 2026 run:
   62 abstracts attempted, 2 completed, 179 refusals, ~2 minutes)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from src.infrastructure.gemini_service import (
    QUOTA_BREAKER_THRESHOLD,
    GeminiLLMService,
    QuotaRefusedError,
    TruncatedResponseError,
)


class _DummySchema(BaseModel):
    answer: str


@pytest.fixture
def service() -> GeminiLLMService:
    svc = GeminiLLMService(api_key="test-key")
    svc._client = MagicMock()
    return svc


def _response(text: str, finish_reason: Any = "STOP") -> list[MagicMock]:
    """A one-chunk stream, as google-genai yields for a short response."""
    candidate = MagicMock()
    candidate.finish_reason = finish_reason
    chunk = MagicMock()
    chunk.candidates = [candidate]
    chunk.text = text
    chunk.usage_metadata = None
    return [chunk]


_HINTLESS_429 = "429 RESOURCE_EXHAUSTED. {'error': {'code': 429}}"


# --------------------------------------------------------------------------
# 1. the cached branch retries transient errors
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cached_branch_retries_a_transient_error(
    service: GeminiLLMService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A 429 carrying a server retry hint is retried on the cached path too."""
    monkeypatch.setattr(
        "src.infrastructure.gemini_service.asyncio.sleep",
        _no_sleep,
    )
    service._client.models.generate_content_stream.side_effect = [
        RuntimeError("429 RESOURCE_EXHAUSTED retryDelay: '1s'"),
        _response('{"answer": "ok"}'),
    ]

    result = await service.cached_or_inline_generate(
        cache_id="caches/abc",
        doc_text="doc",
        prompt="p",
        response_schema=_DummySchema,
    )

    assert result.answer == "ok"
    assert service._client.models.generate_content_stream.call_count == 2


@pytest.mark.asyncio
async def test_cached_branch_does_not_retry_a_hintless_quota_refusal(
    service: GeminiLLMService,
) -> None:
    """Hintless 429 is admission control - the no-retry policy still holds."""
    service._client.models.generate_content_stream.side_effect = RuntimeError(
        _HINTLESS_429
    )

    with pytest.raises(RuntimeError):
        await service.cached_or_inline_generate(
            cache_id="caches/abc",
            doc_text="doc",
            prompt="p",
            response_schema=_DummySchema,
        )

    assert service._client.models.generate_content_stream.call_count == 1


# --------------------------------------------------------------------------
# 2. truncation is surfaced, not repaired blind
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_truncated_response_raises_instead_of_being_repaired(
    service: GeminiLLMService,
) -> None:
    """finish_reason=MAX_TOKENS must not come back as a plausible answer."""
    service._client.models.generate_content_stream.return_value = _response(
        '{"answer": "half a sen', finish_reason="MAX_TOKENS"
    )

    with pytest.raises(TruncatedResponseError):
        await service.cached_or_inline_generate(
            cache_id="caches/abc",
            doc_text="doc",
            prompt="p",
            response_schema=_DummySchema,
        )


@pytest.mark.asyncio
async def test_complete_response_is_returned_normally(
    service: GeminiLLMService,
) -> None:
    """The guard only fires on MAX_TOKENS, not on every response."""
    service._client.models.generate_content_stream.return_value = _response(
        '{"answer": "whole"}'
    )

    result = await service.cached_or_inline_generate(
        cache_id="caches/abc",
        doc_text="doc",
        prompt="p",
        response_schema=_DummySchema,
    )

    assert result.answer == "whole"


# --------------------------------------------------------------------------
# 3. the circuit breaker
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_breaker_trips_and_then_short_circuits(
    service: GeminiLLMService,
) -> None:
    """N refusals trip the flag; the next call is refused without being sent."""
    service._client.models.generate_content_stream.side_effect = RuntimeError(
        _HINTLESS_429
    )

    for _ in range(QUOTA_BREAKER_THRESHOLD):
        with pytest.raises(RuntimeError) as caught:
            await _call(service)
        assert not isinstance(caught.value, QuotaRefusedError)

    assert service.quota_tripped
    sent_before = service._client.models.generate_content_stream.call_count

    with pytest.raises(QuotaRefusedError):
        await _call(service)

    assert (
        service._client.models.generate_content_stream.call_count == sent_before
    ), "a tripped service still sent the request"


@pytest.mark.asyncio
async def test_a_success_resets_the_breaker(service: GeminiLLMService) -> None:
    """Intermittent refusals must not accumulate into a false trip."""
    refusal = RuntimeError(_HINTLESS_429)
    service._client.models.generate_content_stream.side_effect = (
        [refusal] * (QUOTA_BREAKER_THRESHOLD - 1)
        + [_response('{"answer": "ok"}')]
        + [refusal] * (QUOTA_BREAKER_THRESHOLD - 1)
    )

    for _ in range(QUOTA_BREAKER_THRESHOLD - 1):
        with pytest.raises(RuntimeError):
            await _call(service)

    result = await _call(service)
    assert result.answer == "ok"

    for _ in range(QUOTA_BREAKER_THRESHOLD - 1):
        with pytest.raises(RuntimeError):
            await _call(service)
    assert not service.quota_tripped


@pytest.mark.asyncio
async def test_the_separator_may_swallow_it_and_the_flag_still_trips(
    service: GeminiLLMService,
) -> None:
    """The separator degrades refusals - the breaker must not depend on it.

    Two earlier designs made the refusal a better-travelling exception and were
    swallowed anyway, here and in the family gather. State on the service is
    what survives.
    """
    from src.infrastructure.treatment_arm_separator import TreatmentArmSeparator

    service._client.models.generate_content_stream.side_effect = RuntimeError(
        _HINTLESS_429
    )
    separator = TreatmentArmSeparator(llm_service=service)

    for _ in range(QUOTA_BREAKER_THRESHOLD):
        with pytest.raises(Exception):  # noqa: B017 - the separator's own type
            await separator.separate_treatment_arms("body", "abs_1")

    assert service.quota_tripped


async def _no_sleep(_seconds: float) -> None:
    return None


async def _call(service: GeminiLLMService) -> _DummySchema:
    return await service.cached_or_inline_generate(
        cache_id="caches/abc",
        doc_text="doc",
        prompt="p",
        response_schema=_DummySchema,
    )
