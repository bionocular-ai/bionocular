"""Tests for ClinicalTrials.gov discovery: search terms and query shape.

`query.cond` is an Essie expression spanning `BriefTitle`, `OfficialTitle`,
`ConditionMeshTerm` and `ConditionAncestorTerm`, so it matches far beyond a
trial's own conditions (`query.cond=Cutaneous melanoma` returns 3708 of the
registry's 3746 melanoma studies). `AREA[Condition]` restricts the match to the
condition list: 3411 studies, a strict subset (added=0).

The "Rare melanoma" search term is dropped for the same reason: 17 hits under
`query.cond`, 16 of them baskets (`['Cancer']`, `['Advanced Solid Tumor']`),
and every one already reachable through another term.
"""

from datetime import date
from typing import Any, Optional

from src.infrastructure.clinical_trials.api_client import ClinicalTrialsGovAPIClient
from src.infrastructure.clinical_trials.cancer_type_mapping import (
    CANCER_TYPE_MAPPING,
    SKIN_CANCER_TYPES,
    get_condition_search_terms,
)


class _FakeResponse:
    """Minimal stand-in for a `requests.Response`."""

    def __init__(self, payload: dict[str, Any]):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _RecordingSession:
    """Captures the params of every GET and replays a queue of payloads."""

    def __init__(self, payloads: list[dict[str, Any]]):
        self._payloads = payloads
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, params: dict[str, Any], timeout: int) -> _FakeResponse:
        self.calls.append(params)
        return _FakeResponse(self._payloads[len(self.calls) - 1])


def _study(nct_id: str) -> dict[str, Any]:
    return {"protocolSection": {"identificationModule": {"nctId": nct_id}}}


def _client(payloads: list[dict[str, Any]]) -> ClinicalTrialsGovAPIClient:
    client = ClinicalTrialsGovAPIClient()
    client.session = _RecordingSession(payloads)  # type: ignore[assignment]
    return client


def _search(
    payloads: list[dict[str, Any]],
    condition: str = "Cutaneous melanoma",
    status_list: Optional[list[str]] = None,
    last_update_after: Optional[date] = None,
) -> tuple[list[str], list[dict[str, Any]]]:
    client = _client(payloads)
    ncts = client.search_trials_by_condition(
        condition, status_list=status_list, last_update_after=last_update_after
    )
    return ncts, client.session.calls  # type: ignore[union-attr]


# --- search terms ---------------------------------------------------------


def test_rare_melanoma_is_not_a_search_term() -> None:
    for cancer_type, terms in CANCER_TYPE_MAPPING.items():
        assert "Rare melanoma" not in terms, cancer_type


def test_rare_melanoma_types_keep_their_own_term() -> None:
    assert get_condition_search_terms("Uveal Melanoma") == ["Uveal Melanoma"]
    assert get_condition_search_terms("Acral Melanoma") == ["Acral Melanoma"]
    assert get_condition_search_terms("Mucosal Melanoma") == ["Mucosal Melanoma"]


def test_every_skin_cancer_type_still_has_a_term() -> None:
    for cancer_type in SKIN_CANCER_TYPES:
        assert get_condition_search_terms(cancer_type)


# --- query shape ----------------------------------------------------------


def test_condition_is_scoped_to_the_condition_area() -> None:
    _, calls = _search([{"studies": []}])
    assert calls[0]["query.term"] == "AREA[Condition]Cutaneous melanoma"
    assert "query.cond" not in calls[0]


def test_date_filter_is_anded_onto_the_condition_clause() -> None:
    _, calls = _search([{"studies": []}], last_update_after=date(2026, 8, 12))
    assert calls[0]["query.term"] == (
        "AREA[Condition]Cutaneous melanoma "
        "AND AREA[LastUpdatePostDate]RANGE[2026-08-12,MAX]"
    )


def test_status_filter_is_unchanged() -> None:
    _, calls = _search([{"studies": []}], status_list=["RECRUITING", "COMPLETED"])
    assert calls[0]["filter.overallStatus"] == "RECRUITING,COMPLETED"


def test_no_status_filter_when_status_list_is_empty() -> None:
    _, calls = _search([{"studies": []}], status_list=[])
    assert "filter.overallStatus" not in calls[0]


def test_query_term_is_stable_across_pages() -> None:
    ncts, calls = _search(
        [
            {"studies": [_study("NCT00000001")], "nextPageToken": "tok"},
            {"studies": [_study("NCT00000002")]},
        ],
        last_update_after=date(2026, 8, 12),
    )
    assert ncts == ["NCT00000001", "NCT00000002"]
    assert calls[1]["query.term"] == calls[0]["query.term"]
    assert calls[1]["pageToken"] == "tok"
