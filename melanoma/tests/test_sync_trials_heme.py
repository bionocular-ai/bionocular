"""The daily sync refreshes the ASH-cited trials and tags them with their heme cancers."""

from __future__ import annotations

import sys

import pytest

from scripts import sync_trials_supabase as sync

CLL = "Chronic Lymphocytic Leukemia"


def test_listed_trials_join_discovered_once():
    discovered = {"NCT1": ["Cutaneous Melanoma"], "NCT2": []}
    heme = {"NCT2": ["Acute Myeloid Leukemia"], "NCT3": ["Multiple Myeloma"]}
    assert sync.sync_targets(discovered, heme) == ["NCT1", "NCT2", "NCT3"]


class OneTrialApi:
    def fetch_trial_data(self, _nct: str) -> dict:
        conditions = ["Chronic Lymphocytic Leukaemia", "Melanoma"]
        return {"protocolSection": {"conditionsModule": {"conditions": conditions}}}


class Recorder:
    """Records each upserted row per table."""

    def __init__(self) -> None:
        self.rows: dict[str, list[dict]] = {}
        self._table = ""

    def table(self, name: str) -> Recorder:
        self._table = name
        return self

    def upsert(self, row: dict) -> Recorder:
        self.rows.setdefault(self._table, []).append(row)
        return self

    def execute(self) -> None:
        pass


def test_sync_one_writes_heme_tags_beside_derived():
    sb = Recorder()
    assert (
        sync.sync_one("NCT04763083", {}, OneTrialApi(), sb, False, [CLL]) == "fetched"
    )
    [row] = sb.rows["clinical_trials"]
    assert row["cancer_type"] == ["Cutaneous Melanoma", CLL]
    assert row["cancer_type_derived"] == ["Cutaneous Melanoma"]


class NoTrialsApi:
    def search_trials_by_condition(self, *_a, **_k) -> list[str]:
        return []


def test_cancer_type_debug_run_skips_listed_trials(monkeypatch: pytest.MonkeyPatch):
    def refuse():
        raise AssertionError("a --cancer-type run must not load the heme tags")

    monkeypatch.setattr(sync, "ClinicalTrialsGovAPIClient", NoTrialsApi)
    monkeypatch.setattr(sync, "load_heme_tags", refuse, raising=False)
    monkeypatch.setattr(
        sys, "argv", ["sync", "--cancer-type", "Uveal Melanoma", "--dry-run"]
    )
    assert sync.main() == 0


def test_full_run_syncs_listed_trials(monkeypatch: pytest.MonkeyPatch):
    seen: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(sync, "ClinicalTrialsGovAPIClient", NoTrialsApi)
    monkeypatch.setattr(sync, "load_heme_tags", lambda: {"NCT9": [CLL]}, raising=False)
    monkeypatch.setattr(
        sync,
        "sync_one",
        lambda nct, _m, _api, _sb, _dry, tags=(): seen.append((nct, list(tags)))
        or "fetched",
    )
    monkeypatch.setattr(sys, "argv", ["sync", "--dry-run"])
    assert sync.main() == 0
    assert seen == [("NCT9", [CLL])]
