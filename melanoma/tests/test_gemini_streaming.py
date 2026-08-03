"""Tests for streaming structured generation.

Non-streaming `generate_content` buffers the whole generation server-side, so
the client's read timeout measures total generation time. A long judge response
(the results validator emits ~3k completion tokens) blows the 90s budget and
retrying at the same budget fails identically - Batch-I_22 timed out twice.

Streaming makes the same timeout measure the gap *between* chunks, which is what
it was meant to bound: a stalled socket still dies, a long generation completes.
`GenerateContentResponse.parsed` is documented as unavailable for streaming, so
the accumulated text must be parsed by the existing JSON path.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from src.infrastructure.gemini_service import GeminiLLMService


class _DummySchema(BaseModel):
    answer: str


def _chunk(text: str | None, usage: Any = None) -> MagicMock:
    chunk = MagicMock()
    chunk.text = text
    chunk.usage_metadata = usage
    return chunk


def _service(cost_calculator: Any = None) -> GeminiLLMService:
    svc = GeminiLLMService(api_key="test-key", cost_calculator=cost_calculator)
    svc._client = MagicMock()
    return svc


@pytest.mark.asyncio
async def test_structured_generation_streams_and_reassembles_split_json() -> None:
    """JSON split across chunks is concatenated before parsing."""
    svc = _service()
    chunks = [_chunk('{"ans'), _chunk('wer": "st'), _chunk('reamed"}')]
    svc._client.models.generate_content_stream.return_value = iter(chunks)

    result = await svc.generate_structured("PROMPT", response_schema=_DummySchema)

    assert result.answer == "streamed"
    svc._client.models.generate_content_stream.assert_called_once()
    svc._client.models.generate_content.assert_not_called()


@pytest.mark.asyncio
async def test_structured_generation_skips_textless_chunks() -> None:
    """Chunks carrying no text (e.g. a trailing usage-only chunk) are ignored."""
    svc = _service()
    chunks = [_chunk('{"answer":'), _chunk(None), _chunk(' "ok"}'), _chunk("")]
    svc._client.models.generate_content_stream.return_value = iter(chunks)

    result = await svc.generate_structured("PROMPT", response_schema=_DummySchema)

    assert result.answer == "ok"


@pytest.mark.asyncio
async def test_usage_metadata_from_final_chunk_is_recorded() -> None:
    """Token accounting survives streaming - usage arrives on the last chunk."""
    cost_calculator = MagicMock()
    svc = _service(cost_calculator)
    usage = MagicMock(prompt_token_count=1200, candidates_token_count=340)
    chunks = [
        _chunk('{"answer": "ok"}', usage=None),
        _chunk(None, usage=usage),
    ]
    svc._client.models.generate_content_stream.return_value = iter(chunks)

    await svc.generate_structured("PROMPT", response_schema=_DummySchema)

    cost_calculator.record_api_call.assert_called_once()
    kwargs = cost_calculator.record_api_call.call_args.kwargs
    assert kwargs["prompt_tokens"] == 1200
    assert kwargs["completion_tokens"] == 340
    assert kwargs["success"] is True


@pytest.mark.asyncio
async def test_truncated_json_is_repaired() -> None:
    """A stream cut short still goes through the existing JSON repair path."""
    svc = _service()
    svc._client.models.generate_content_stream.return_value = iter(
        [_chunk('{"answer": "cut off"')]
    )

    result = await svc.generate_structured("PROMPT", response_schema=_DummySchema)

    assert result.answer == "cut off"


@pytest.mark.asyncio
async def test_stream_error_is_retried_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mid-stream transient failure retries the whole call."""
    slept: list[float] = []

    async def _no_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr("src.infrastructure.gemini_service.asyncio.sleep", _no_sleep)

    svc = _service()
    calls: list[int] = []

    def _stream(**_kwargs: Any) -> Iterator[MagicMock]:
        calls.append(1)
        if len(calls) == 1:
            raise Exception("504 DEADLINE_EXCEEDED")
        return iter([_chunk('{"answer": "second"}')])

    svc._client.models.generate_content_stream.side_effect = _stream

    result = await svc.generate_structured("PROMPT", response_schema=_DummySchema)

    assert result.answer == "second"
    assert len(calls) == 2
    # Backoff must not sit on the old 60s floor - commit 476fd77 shrank it for
    # generate_response but left the structured path untouched.
    assert slept and slept[0] <= 30.0
