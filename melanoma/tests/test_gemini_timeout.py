"""Tests for the Gemini request timeout and retryable-error classification.

A stalled Vertex socket with no client timeout hangs a worker forever (it bit
the 1771-trial validation run). The client must carry a bounded request timeout,
and a timeout/deadline must be treated as a retryable transient so the existing
backoff loop retries it instead of failing.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from src.infrastructure.gemini_service import (
    _REQUEST_TIMEOUT_MS,
    GeminiLLMService,
    _is_retryable_error,
)


@pytest.mark.parametrize(
    "message",
    [
        "429 RESOURCE_EXHAUSTED quota exceeded",
        "RATE_LIMIT reached",
        "504 DEADLINE_EXCEEDED",
        "Timeout of 90000ms exceeded",
        "request timed out",
    ],
)
def test_retryable_errors(message: str) -> None:
    assert _is_retryable_error(Exception(message)) is True


def test_asyncio_timeout_is_retryable() -> None:
    assert _is_retryable_error(asyncio.TimeoutError()) is True


@pytest.mark.parametrize(
    "message",
    ["invalid JSON in response", "400 INVALID_ARGUMENT", "permission denied"],
)
def test_non_retryable_errors(message: str) -> None:
    assert _is_retryable_error(Exception(message)) is False


def test_client_built_with_request_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """The SDK client is constructed with a bounded http request timeout."""
    from google import genai

    captured: dict[str, Any] = {}

    def _fake_client(**kwargs: Any) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(genai, "Client", _fake_client)

    GeminiLLMService(api_key="test-key")

    http_options = captured.get("http_options")
    assert http_options is not None, "client built without http_options"
    assert http_options.timeout == _REQUEST_TIMEOUT_MS


def test_request_timeout_is_bounded_and_sane() -> None:
    """Timeout is generous over p99 (~8s) but far below 'forever'."""
    assert 30_000 <= _REQUEST_TIMEOUT_MS <= 180_000
