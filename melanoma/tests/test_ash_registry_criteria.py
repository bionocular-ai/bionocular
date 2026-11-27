"""Tests for filling response criteria from the trial registry."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from ash_registry_criteria import criteria_sets, fill_criteria  # noqa: E402


def study(*measures: str, eligibility: str = "") -> dict:
    return {
        "protocolSection": {
            "outcomesModule": {
                "primaryOutcomes": [{"measure": m, "description": ""} for m in measures]
            },
            "eligibilityModule": {"eligibilityCriteria": eligibility},
        }
    }


IMWG = study("Overall response rate per IMWG criteria")
RESP = {"orr"}


def rec(abstract="1", key="orr", ncts=("NCT1",)):
    return {"abstract": abstract, "doi": "d", "indication": "i", "nct_ids": list(ncts),
            "arm_id": "arm_1", "arm_name": "a", "arm_role": "x", "field_key": key,
            "context": "", "value_text": "50", "n": None, "detail": "", "derived": False,
            "origin": "abstract", "caveat": None}  # fmt: skip


def test_one_set():
    assert criteria_sets(IMWG) == {"IMWG"}
    out = fill_criteria([rec()], {"NCT1": IMWG}, RESP)
    new = out[-1]
    assert (new["field_key"], new["value_text"], new["origin"], new["arm_id"]) == (
        "response_criteria", "IMWG", "registry", None)  # fmt: skip
    assert new["detail"] == "criteria per the trial registry"


def test_two_sets_not_filled():
    s = study("ORR by iwCLL", "CR by Lugano")
    assert criteria_sets(s) == {"iwCLL", "Lugano/Cheson"}
    assert len(fill_criteria([rec()], {"NCT1": s}, RESP)) == 1


def test_none_not_filled():
    assert len(fill_criteria([rec()], {"NCT1": study("ORR")}, RESP)) == 1


def test_existing_criteria_untouched():
    recs = [rec(), rec(key="response_criteria")]
    assert fill_criteria(recs, {"NCT1": IMWG}, RESP) == recs


def test_set_named_for_a_non_response_outcome_ignored():
    for m in (
        "PFS per the 2018 iwCLL Criteria",
        "Treatment failure as per ELN, loss of MMR while on study treatment",
        "Incidence of graft versus host disease according to MAGIC and NIH criteria",
    ):
        assert criteria_sets(study(m)) == set(), m
    assert criteria_sets(study("CR rate per Lugano 2014")) == {"Lugano/Cheson"}


def test_eln_risk_only_in_eligibility_ignored():
    s = study("Overall survival", eligibility="Adverse risk per ELN 2017")
    assert criteria_sets(s) == set()
