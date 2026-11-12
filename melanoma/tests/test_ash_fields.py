"""Tests for the ASH workbook field spec, schemas and prompts."""

import csv
import re
import sys
from pathlib import Path

_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root / "src"))
sys.path.insert(0, str(_root / "scripts"))

from ash_fields import (  # noqa: E402
    HEME_SEPARATION_PROMPT,
    INDICATIONS,
    JudgeVerdict,
    SheetField,
    applies,
    family_prompt,
    judge_prompt,
    load_families,
    response_model,
)
from domain.prompt_templates import SHARED_EXTRACTION_RULES  # noqa: E402
from domain.treatment_arm_models import TreatmentArm  # noqa: E402

CSV_PATH = _root / "resources" / "ash" / "book1_sheet2.csv"
FAMILIES = load_families(CSV_PATH)
ALL_FIELDS = [f for fam in FAMILIES for f in fam.fields]
TEXT_ONLY = {
    "Mechanism of action",
    "Target",
    "Modality",
    "Drug class / sub-type",
    "Generic name (per component)",
    "Brand name",
    "Disease subtype",
}


def _resolve(schema: dict, node: dict) -> dict:
    ref = node.get("$ref")
    return schema["$defs"][ref.split("/")[-1]] if ref else node


def test_every_row_in_one_family():
    with CSV_PATH.open(newline="") as f:
        names = [r["field"] for r in csv.DictReader(f)]
    assert len(names) == 143
    expected = [n for n in names if n != "Cytokine Release Syndrome or CRS"]
    got = [f.name for f in ALL_FIELDS]
    assert len(got) == len(set(got)) == 142
    assert sorted(got) == sorted(expected)


def test_family_sizes():
    for fam in FAMILIES:
        assert 5 <= len(fam.fields) <= 30, fam.key


def test_keys_are_valid_json_identifiers():
    keys = [f.key for f in ALL_FIELDS]
    assert all(re.fullmatch(r"[a-z][a-z0-9_]*", k) for k in keys)
    assert len(keys) == len(set(keys))


def test_response_model_shape():
    fam = next(f for f in FAMILIES if any(x.trial_level for x in f.fields))
    schema = response_model(fam, ["arm_1", "arm_2"]).model_json_schema()
    arms = _resolve(schema, schema["properties"]["arms"])
    arm = _resolve(schema, arms["properties"]["arm_1"])
    assert "other_values" in arm["properties"]
    key = next(f.key for f in fam.fields if not f.trial_level)
    cell = _resolve(schema, arm["properties"][key])
    assert "quote" in cell["properties"] and "value" in cell["properties"]
    assert "trial" in schema["properties"]
    no_trial = next(f for f in FAMILIES if not any(x.trial_level for x in f.fields))
    assert (
        "trial"
        not in response_model(no_trial, ["arm_1"]).model_json_schema()["properties"]
    )


def test_prompt_has_rules_and_definitions():
    arms = [
        TreatmentArm(arm_id="arm_1", arm_name="LINVO + DARA", generic_name="x"),
        TreatmentArm(arm_id="arm_2", arm_name="LINVO + ISA", generic_name="y"),
    ]
    for fam in FAMILIES:
        p = family_prompt(fam, arms)
        assert SHARED_EXTRACTION_RULES in p
        for f in fam.fields:
            assert f.name in p and f.definition in p
        assert "arm_1: LINVO + DARA" in p and "arm_2: LINVO + ISA" in p
        assert "other_values" in p
        assert "second value for the same field" in p


def test_text_only_fields():
    assert {f.name for f in ALL_FIELDS if f.text_only} == TEXT_ONLY
    fam = next(f for f in FAMILIES if any(x.text_only for x in f.fields))
    arms = [TreatmentArm(arm_id="arm_1", arm_name="a", generic_name="a")]
    assert "own knowledge" in family_prompt(fam, arms)


def test_applies():
    crs = SheetField(
        "crs", "CRS any grade", "t", "CAR-T, bispecific antibodies", "d", False, False
    )
    aml = SheetField("a", "CR/CRh rate", "t", "AML", "d", False, False)
    mm = SheetField("m", "sCR rate", "t", "MM", "d", False, False)
    allf = SheetField("x", "Median age", "t", "All", "d", False, False)
    assert len(INDICATIONS) == 20
    assert applies(crs, "DLBCL")
    assert not applies(aml, "Multiple myeloma")
    assert applies(aml, "AML") and not applies(aml, "APL")
    assert applies(mm, "Multiple myeloma")
    assert applies(allf, "CML")
    lym = SheetField("p", "PFS2", "t", "MM, CLL, lymphoma", "d", False, False)
    assert applies(lym, "Follicular lymphoma") and not applies(lym, "Waldenström")
    assert not applies(
        SheetField("c", "MMR rate", "t", "CML", "d", False, False), "CMML"
    )


def test_heme_prompt_placeholder():
    assert "{abstract_text}" in HEME_SEPARATION_PROMPT
    assert chr(0x2014) not in HEME_SEPARATION_PROMPT


def test_judge_models():
    fam = FAMILIES[0]
    assert "pass" in str(JudgeVerdict.model_json_schema())
    assert "other_values" in judge_prompt(fam, {"arms": {}})
