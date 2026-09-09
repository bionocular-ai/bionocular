"""Tests for the Vertex ADC environment lookup shared by the pipeline scripts.

The pipelines authenticate through Application Default Credentials, so a
missing GOOGLE_CLOUD_PROJECT or GOOGLE_CLOUD_LOCATION must fail immediately
with a message naming what is missing, not hundreds of documents later.
"""

from __future__ import annotations

import pytest

from src.infrastructure.gemini_service import vertex_env


def test_returns_project_and_location(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "proj-123")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "global")
    assert vertex_env() == ("proj-123", "global")


@pytest.mark.parametrize("unset", ["GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION"])
def test_raises_naming_the_missing_variable(
    monkeypatch: pytest.MonkeyPatch, unset: str
) -> None:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "proj-123")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "global")
    monkeypatch.delenv(unset)
    with pytest.raises(RuntimeError, match=unset):
        vertex_env()
