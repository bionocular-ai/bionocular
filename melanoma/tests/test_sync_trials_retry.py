"""Retry behaviour of the daily ClinicalTrials.gov -> Supabase sync writes."""

from __future__ import annotations

import pytest

from scripts import sync_trials_supabase as sync


class FlakyTable:
    """Fails the first `failures` executes, then succeeds; counts every call."""

    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls = 0

    def table(self, _name: str) -> FlakyTable:
        return self

    def upsert(self, _row: dict) -> FlakyTable:
        return self

    def execute(self) -> None:
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError("Gateway Timeout")


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sync.upsert_with_retry.retry, "sleep", lambda _s: None)


def test_transient_failure_is_retried() -> None:
    client = FlakyTable(failures=2)
    sync.upsert_with_retry(client, "clinical_trials_cache", {})
    assert client.calls == 3


def test_persistent_failure_raises_after_three_attempts() -> None:
    client = FlakyTable(failures=99)
    with pytest.raises(RuntimeError):
        sync.upsert_with_retry(client, "clinical_trials_cache", {})
    assert client.calls == 3
