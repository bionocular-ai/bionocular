"""Tests for Gemini 429 backoff timing.

Under Vertex Dynamic Shared Quota a 429 means instantaneous demand exceeded
supply and typically clears in 1-5s, so the retry backoff must start small
(seconds, not a 60s floor), grow exponentially with jitter, cap, and honor a
server-provided retry delay when present.
"""

from __future__ import annotations

from src.infrastructure.gemini_service import _backoff_seconds, _parse_retry_after

_CAP = 30.0


def test_first_attempt_backoff_is_seconds_not_a_minute() -> None:
    """attempt 0 waits a couple seconds, never the old 60s floor."""
    for _ in range(50):
        wait = _backoff_seconds(0)
        assert 1.0 <= wait < 3.0, wait


def test_backoff_grows_exponentially() -> None:
    """Later attempts wait longer (base doubles each attempt)."""
    for _ in range(50):
        assert 4.0 <= _backoff_seconds(2) < 6.0


def test_backoff_is_capped() -> None:
    """A high attempt count is capped, not runaway minutes."""
    for _ in range(50):
        assert _backoff_seconds(20) <= _CAP + 1.0


def test_retry_after_hint_is_honored() -> None:
    """A server-provided retry delay overrides the exponential schedule."""
    assert _backoff_seconds(0, retry_after=5.0) == 5.0


def test_retry_after_hint_is_capped() -> None:
    """A pathological server hint is still bounded by the cap."""
    assert _backoff_seconds(0, retry_after=999.0) == _CAP


def test_parse_retry_after_from_google_style_error() -> None:
    """Extract retryDelay seconds from a RESOURCE_EXHAUSTED error string."""
    msg = "429 RESOURCE_EXHAUSTED ... 'retryDelay': '7s' ..."
    assert _parse_retry_after(msg) == 7.0


def test_parse_retry_after_absent_returns_none() -> None:
    """No retry hint in the error yields None (fall back to exponential)."""
    assert _parse_retry_after("429 RESOURCE_EXHAUSTED quota exceeded") is None
