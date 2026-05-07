"""Tests for GeminiLLMService context caching with inline fallback.

Unit tests mock the google-genai SDK; the integration test smoke-runs the
real cache lifecycle and is skipped without GOOGLE_API_KEY.
"""
from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
from pydantic import BaseModel

from src.infrastructure.gemini_service import (
    GEMINI_CACHE_MIN_TOKENS,
    GeminiLLMService,
    _inline_pydantic_schema,
)


class _DummySchema(BaseModel):
    answer: str


@pytest.fixture
def service() -> GeminiLLMService:
    svc = GeminiLLMService(api_key="test-key")
    # Replace the real client with a fully-mocked stand-in.
    svc._client = MagicMock()
    return svc


def _short_doc() -> str:
    # Well below the floor: floor*4 chars would be the threshold.
    return "x" * 100


def _long_doc() -> str:
    # Comfortably above the floor.
    return "x" * (GEMINI_CACHE_MIN_TOKENS * 4 + 1000)


# ---------------------------------------------------------------------------
# create_context_cache
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_context_cache_short_doc_returns_none_without_sdk_call(
    service: GeminiLLMService,
) -> None:
    result = await service.create_context_cache(
        doc_text=_short_doc(),
        system_instruction="sys",
    )
    assert result is None
    service._client.caches.create.assert_not_called()


@pytest.mark.asyncio
async def test_create_context_cache_long_doc_calls_sdk_and_returns_id(
    service: GeminiLLMService,
) -> None:
    cached = MagicMock()
    cached.name = "cachedContents/abc123"
    service._client.caches.create.return_value = cached

    result = await service.create_context_cache(
        doc_text=_long_doc(),
        system_instruction="sys",
        ttl_seconds=600,
    )

    assert result == "cachedContents/abc123"
    service._client.caches.create.assert_called_once()
    call_kwargs = service._client.caches.create.call_args.kwargs
    assert call_kwargs["model"] == service._model
    assert call_kwargs["config"].ttl == "600s"
    assert call_kwargs["config"].system_instruction == "sys"


@pytest.mark.asyncio
async def test_create_context_cache_min_token_error_returns_none(
    service: GeminiLLMService,
) -> None:
    from google.genai.errors import ClientError

    fake_response = httpx.Response(
        status_code=400,
        json={
            "error": {
                "code": 400,
                "status": "INVALID_ARGUMENT",
                "message": "Cached content is too small. min_total_token_count=32768",
            }
        },
    )
    service._client.caches.create.side_effect = ClientError(400, fake_response)

    result = await service.create_context_cache(
        doc_text=_long_doc(),
        system_instruction="sys",
    )

    assert result is None


# ---------------------------------------------------------------------------
# cached_or_inline_generate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cached_or_inline_generate_inline_path_prepends_doc(
    service: GeminiLLMService,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_generate_structured(
        prompt: str,
        response_schema: type[_DummySchema],
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> _DummySchema:
        captured["prompt"] = prompt
        captured["temperature"] = temperature
        captured["max_tokens"] = max_tokens
        return response_schema(answer="ok")

    service.generate_structured = fake_generate_structured  # type: ignore[method-assign]

    result = await service.cached_or_inline_generate(
        cache_id=None,
        doc_text="DOCBODY",
        prompt="EXTRACT",
        response_schema=_DummySchema,
        temperature=0.2,
        max_tokens=1234,
    )

    assert result.answer == "ok"
    assert captured["prompt"].startswith("DOCBODY")
    assert "EXTRACT" in captured["prompt"]
    assert captured["temperature"] == 0.2
    assert captured["max_tokens"] == 1234
    service._client.models.generate_content.assert_not_called()


@pytest.mark.asyncio
async def test_cached_or_inline_generate_cached_path_references_cache(
    service: GeminiLLMService,
) -> None:
    parsed = _DummySchema(answer="cached-ok")
    response = MagicMock()
    response.parsed = parsed
    response.text = '{"answer": "cached-ok"}'
    response.usage_metadata = MagicMock(prompt_token_count=10, candidates_token_count=2)
    service._client.models.generate_content.return_value = response

    result = await service.cached_or_inline_generate(
        cache_id="cachedContents/abc",
        doc_text="DOCBODY",
        prompt="EXTRACT",
        response_schema=_DummySchema,
    )

    assert result.answer == "cached-ok"
    service._client.models.generate_content.assert_called_once()
    kwargs = service._client.models.generate_content.call_args.kwargs
    assert kwargs["contents"] == "EXTRACT"  # doc not inlined when cached
    assert kwargs["config"].cached_content == "cachedContents/abc"


# ---------------------------------------------------------------------------
# delete_cache
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_cache_none_is_noop(service: GeminiLLMService) -> None:
    await service.delete_cache(None)
    service._client.caches.delete.assert_not_called()


@pytest.mark.asyncio
async def test_delete_cache_calls_sdk(service: GeminiLLMService) -> None:
    await service.delete_cache("cachedContents/xyz")
    service._client.caches.delete.assert_called_once_with(name="cachedContents/xyz")


# ---------------------------------------------------------------------------
# Integration smoke test
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cache_lifecycle_smoke() -> None:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        pytest.skip("GOOGLE_API_KEY not set")

    svc = GeminiLLMService(api_key=api_key)
    # ~40k chars of filler — over the conservative floor.
    doc = ("This is a clinical trial document. " * 1200)[:40_000]
    cache_id = await svc.create_context_cache(
        doc_text=doc,
        system_instruction="You answer questions about the cached document.",
        ttl_seconds=300,
    )
    if cache_id is None:
        pytest.skip("SDK rejected cache (likely below model-specific floor)")

    try:
        result = await svc.cached_or_inline_generate(
            cache_id=cache_id,
            doc_text=doc,
            prompt='Reply with JSON {"answer": "pong"}.',
            response_schema=_DummySchema,
        )
        assert isinstance(result, _DummySchema)
    finally:
        await svc.delete_cache(cache_id)


# ---------------------------------------------------------------------------
# _inline_pydantic_schema
# ---------------------------------------------------------------------------


def test_inline_pydantic_schema_resolves_refs_and_drops_defs() -> None:
    """$ref entries must be inlined and $defs must be absent in the result."""
    from pydantic import BaseModel as BM

    class Inner(BM):
        x: str

    class Outer(BM):
        inner: Inner
        tag: str

    result = _inline_pydantic_schema(Outer)
    assert "$defs" not in result
    assert "$ref" not in str(result)
    # 'inner' property should be inlined as an object with 'x'
    inner_prop = result["properties"]["inner"]
    assert inner_prop["type"] == "object"
    assert "x" in inner_prop["properties"]


def test_inline_pydantic_schema_idempotent_on_flat_schema() -> None:
    """Flat schemas with no $ref/$defs should pass through unchanged."""
    from pydantic import BaseModel as BM

    class Flat(BM):
        a: str
        b: str

    result = _inline_pydantic_schema(Flat)
    assert "$defs" not in result
    assert "$ref" not in str(result)
    assert set(result["properties"].keys()) == {"a", "b"}
