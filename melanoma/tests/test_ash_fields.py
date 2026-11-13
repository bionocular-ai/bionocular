"""Tests for the ASH workbook fields, schemas and prompts."""

import csv
import sys
from pathlib import Path

import pytest

_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root / "scripts"))

from ash_fields import (  # noqa: E402
    ARM_PROMPT,
    INDICATIONS,
    Arm,
    ArmList,
    Family,
    JudgeVerdict,
    applies,
    arm_fields,
    family_prompt,
    fields_for,
    judge_items,
    judge_prompt,
    load_families,
    missed_model,
    missed_prompt,
    response_model,
)

from src.infrastructure.openrouter_structured_service import (  # noqa: E402
    to_strict_schema,
)

CSV_PATH = _root / "resources" / "ash" / "book1_sheet2.csv"
FAMILIES = load_families(CSV_PATH)
ALL_FIELDS = [f for fam in FAMILIES for f in fam.fields]
BY_NAME = {f.name: f for f in ALL_FIELDS}
ARMS = [Arm("arm_1", "Drug X", "experimental"), Arm("arm_2", "Placebo", "control")]


def _family(key: str) -> Family:
    return next(f for f in FAMILIES if f.key == key)


def _cell(value: str = "", quote: str = "", **kw: object) -> dict[str, object]:
    return {
        "value": value,
        "quote": quote,
        "detail": "",
        "derived": False,
        **kw,
    }


def test_only_abstract_rows_are_asked():
    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 148
    asked = [r["field"] for r in rows if r["source"] in ("abstract", "both")]
    got = [f.name for f in ALL_FIELDS]
    assert len(got) == len(set(got)) == 135
    assert sorted(got) == sorted(asked)
    for moved in ("Route", "Modality", "Target", "Arm label"):
        assert moved not in BY_NAME


def test_every_asked_row_has_family_scope_and_type():
    for f in ALL_FIELDS:
        assert f.scope in ("arm", "comparison", "trial"), f.name
        assert f.value_type, f.name
        assert f.key.isidentifier() and len({x.key for x in ALL_FIELDS}) == 135
    assert BY_NAME["HR PFS"].scope == "comparison"
    assert BY_NAME["Biomarker"].scope == "trial"
    assert BY_NAME["Non-relapse mortality"].family == "duration_transplant"
    assert BY_NAME["p-value PFS"].allowed == ()


def test_fields_for_filters_by_indication():
    rates = _family("response_rates")
    mm = {f.name for f in fields_for(rates, "Multiple myeloma").fields}
    cll = {f.name for f in fields_for(rates, "CLL / SLL").fields}
    assert ">=CR rate" in mm and ">=CR rate" not in cll
    assert "CR/CRh rate" not in mm
    assert fields_for(rates, None) == rates
    assert not fields_for(_family("survival_other"), "Multiple myeloma").fields


def test_comparison_fields_only_on_the_experimental_arm():
    pfs = _family("survival_pfs_os")
    exp = {f.key for f in arm_fields(pfs, ARMS[0])}
    ctl = {f.key for f in arm_fields(pfs, ARMS[1])}
    assert "hr_pfs" in exp and "hr_pfs" not in ctl
    assert "median_pfs" in exp and "median_pfs" in ctl
    schema = to_strict_schema(response_model(pfs, ARMS))
    arms = schema["properties"]["arms"]["properties"]
    assert "hr_pfs" in arms["arm_1"]["properties"]
    assert "hr_pfs" not in arms["arm_2"]["properties"]
    assert "extra" in arms["arm_2"]["properties"]


def test_enum_fields_are_schema_enums():
    schema = to_strict_schema(response_model(_family("population"), ARMS))
    value = schema["properties"]["trial"]["properties"]["analysis_type"]["properties"][
        "value"
    ]
    assert "final" in value["enum"] and "" in value["enum"]


def test_response_model_accepts_a_filled_reply():
    fam = fields_for(_family("survival_pfs_os"), "Multiple myeloma")
    model = response_model(fam, ARMS)
    arms = {
        a.arm_id: {f.key: _cell() for f in arm_fields(fam, a)} | {"extra": []}
        for a in ARMS
    }
    arms["arm_1"]["extra"] = [
        {"field": "median_pfs", "value": "22", "context": "age >=75", "quote": "q"}
    ]
    assert model.model_validate({"pooled": [], "arms": arms})
    arms["arm_1"]["extra"][0]["field"] = "not_a_field"
    with pytest.raises(ValueError):
        model.model_validate({"pooled": [], "arms": arms})


def test_pooled_values_have_one_list_and_only_with_two_arms():
    pfs = _family("survival_pfs_os")
    schema = to_strict_schema(response_model(pfs, ARMS))
    keys = schema["properties"]["pooled"]["items"]["properties"]["field"]["enum"]
    assert "median_pfs" in keys and "hr_pfs" not in keys
    one = to_strict_schema(response_model(pfs, ARMS[:1]))
    assert "pooled" not in one["properties"]
    pooled = [
        {
            "field": "median_pfs",
            "value": "20",
            "context": "",
            "detail": "",
            "quote": "q",
            "derived": False,
        }
    ]
    items = judge_items(pfs, {"pooled": pooled, "arms": {}}, ARMS)
    assert [(i["kind"], i["arm_name"]) for i in items] == [
        ("pooled", "all arms together")
    ]
    line = "1 | all arms together | Median PFS | value: 20 | derived: false"
    assert line in judge_prompt(pfs, items, ARMS)


def test_family_without_fields_cannot_be_asked():
    with pytest.raises(ValueError):
        response_model(Family("x", "X", ()), ARMS)


def test_family_prompt_states_rules_fields_and_arms():
    prompt = family_prompt(_family("survival_pfs_os"), ARMS)
    for needle in (
        "Never use what you know",
        "goes once in 'pooled'",
        "earlier analysis",
        "hr_pfs (HR PFS)",
        "arm_1: Drug X (experimental)",
        "EXAMPLE 2 (invented)",
    ):
        assert needle in prompt
    assert "Grade 3+" not in prompt  # melanoma table rules are gone
    pop = family_prompt(_family("population"), ARMS)
    assert "go under 'trial' once" in pop
    assert "Fill only if the abstract says it in words." in pop


def test_arm_prompt_and_schema():
    assert "{abstract_text}" in ARM_PROMPT and "dose_variation" not in ARM_PROMPT
    assert "Dose levels" in ARM_PROMPT
    assert "even when the abstract itself calls the groups arms" in ARM_PROMPT
    assert "Donor type is a subgroup" in ARM_PROMPT
    to_strict_schema(ArmList)


def test_judge_items_number_fields_and_extras():
    fam = _family("survival_pfs_os")
    extracted = {
        "arms": {
            "arm_1": {
                "median_pfs": _cell("30.1", "median PFS was 30.1"),
                "median_os": _cell(),
                "extra": [
                    {
                        "field": "median_pfs",
                        "value": "22",
                        "context": "age >=75",
                        "quote": "q",
                    }
                ],
            }
        }
    }
    items = judge_items(fam, extracted, ARMS)
    assert [(i["id"], i["kind"], i["key"]) for i in items] == [
        (1, "field", "median_pfs"),
        (2, "extra", "median_pfs"),
    ]
    prompt = judge_prompt(fam, items, ARMS)
    assert "1 | Drug X | Median PFS | value: 30.1 | derived: false" in prompt
    assert "2 | Drug X | Median PFS | value: 22 | extra value for: age >=75" in prompt
    assert "value_ok" in prompt and "quote_ok" in prompt
    JudgeVerdict.model_validate(
        {
            "items": [
                {
                    "id": 1,
                    "value_ok": "no",
                    "quote_ok": "yes",
                    "error": "wrong_measure",
                    "right_value": "",
                    "right_quote": "",
                }
            ]
        }
    )


def test_missed_prompt_lists_only_empty_fields():
    fam = _family("survival_pfs_os")
    extracted = {
        "arms": {
            "arm_1": {"median_pfs": _cell("30", "q"), "median_os": _cell(), "extra": []}
        }
    }
    empty = missed_prompt(fam, extracted, ARMS).split("EMPTY\n")[1]
    assert empty == "arm_1: median_os"
    model = missed_model(fam, ARMS)
    to_strict_schema(model)
    assert model.model_validate(
        {
            "items": [
                {"arm_id": "arm_1", "field": "median_os", "value": "40", "quote": "q"}
            ]
        }
    )


def test_applies():
    assert len(INDICATIONS) == 20
    assert applies(BY_NAME["Median PFS"], "CML")
    assert applies(BY_NAME["sCR rate"], "Multiple myeloma")
    assert not applies(BY_NAME["sCR rate"], "AML")
    assert applies(BY_NAME["Median EFS"], "DLBCL")  # "lymphoma" group
    assert applies(BY_NAME["CRS any grade"], "CML")  # design scope, not a disease
    assert applies(BY_NAME["Median RFS"], "ALL")
    assert not applies(BY_NAME["Median RFS"], "Follicular lymphoma")  # prose "all"
