"""Tests for the ASH registry-side test run (no network, no model)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from ash_registry_run import flags, record_text, registry_family  # noqa: E402

from src.infrastructure.openrouter_structured_service import (  # noqa: E402
    to_strict_schema,
)

CSV = Path(__file__).parent.parent / "resources" / "ash" / "book1_sheet2.csv"
STUDY = {
    "protocolSection": {
        "identificationModule": {
            "nctId": "NCT01234567",
            "briefTitle": "Drug X in RRMM",
        },
        "armsInterventionsModule": {
            "armGroups": [
                {
                    "label": "Arm A",
                    "type": "EXPERIMENTAL",
                    "description": "Drug X orally until progression",
                    "interventionNames": ["Drug: Drug X"],
                }
            ],
            "interventions": [
                {"type": "DRUG", "name": "Drug X", "otherNames": ["Xbrand"]}
            ],
        },
        "eligibilityModule": {"eligibilityCriteria": "At least 3 prior lines"},
    }
}


def test_registry_family_has_the_registry_rows_and_setting() -> None:
    fam = registry_family(CSV)
    names = [f.name for f in fam.fields]
    assert len(names) == 12 and names[-1] == "Setting (line of therapy)"
    assert "Route" in names and "Median PFS" not in names
    assert not any("abstract" in f.definition for f in fam.fields)


def test_record_text_keeps_arms_interventions_and_criteria() -> None:
    text = record_text(STUDY)
    assert "- Arm A [EXPERIMENTAL]: Drug X orally until progression" in text
    assert "other names: Xbrand" in text and "At least 3 prior lines" in text


def test_flags() -> None:
    def cell(v: str, q: str) -> dict[str, object]:
        return {"value": v, "quote": q, "detail": "", "derived": False}

    extracted = {
        "trial": {"setting": cell("relapsed/refractory + second line", "3 prior")},
        "arms": {"arm_1": {"route": cell("oral", "Drug X orally"), "extra": []}},
    }
    got = flags(extracted, record_text(STUDY))
    assert got == {"trial.setting": ["setting_not_in_list"]}
    extracted["arms"]["arm_1"]["route"]["quote"] = "taken by mouth"
    assert flags(extracted, record_text(STUDY))["arm_1.route"] == [
        "quote_not_in_record"
    ]


def test_schema_has_no_pooled_list() -> None:
    from ash_fields import Arm, response_model

    arms = [Arm("arm_1", "X", "experimental"), Arm("arm_2", "Y", "control")]
    schema = to_strict_schema(
        response_model(registry_family(CSV), arms, pooled_list=False)
    )
    assert "pooled" not in schema["properties"]
