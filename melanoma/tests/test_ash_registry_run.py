"""Tests for the ASH registry-side test run (no network, no model)."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from ash_registry_run import (  # noqa: E402
    RecordMatch,
    done,
    drop_unsupported,
    flags,
    record_text,
    registry_family,
    run_one,
)

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
    assert "NCT: NCT01234567\n" in text
    merged = {"protocolSection": {"identificationModule": {
        "nctId": "NCT05289167", "nctIdAliases": ["NCT06681922"]}}}  # fmt: skip
    assert "NCT: NCT05289167 (also registered as NCT06681922)" in record_text(merged)


def test_flags() -> None:
    def cell(v: str, q: str) -> dict[str, Any]:
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


def test_drop_unsupported() -> None:
    def cell(v: str, q: str) -> dict[str, Any]:
        return {"value": v, "quote": q, "detail": "", "derived": False}

    arms = {
        "arm_1": {
            "generic_name_per_component": cell("Drug X + fludarabine", "q"),
            "route": cell("oral + IV", "q"),
            "fixed_duration_vs_continuous": cell("fixed duration", "on days 1-7"),
        },
        "arm_2": {
            "generic_name_per_component": cell("drug x", "q"),
            "fixed_duration_vs_continuous": cell(
                "continuous (treat to progression)", "until progression"
            ),
        },
    }
    dropped = drop_unsupported({"arms": arms}, [STUDY])
    assert [(d["arm_id"], d["key"]) for d in dropped] == [
        ("arm_1", "fixed_duration_vs_continuous"),
        ("arm_1", "generic_name_per_component"),
        ("arm_1", "route"),
    ]
    assert arms["arm_1"]["generic_name_per_component"]["value"] == "Drug X"
    assert arms["arm_1"]["route"]["value"] == "oral"
    assert arms["arm_1"]["fixed_duration_vs_continuous"]["value"] == ""
    assert arms["arm_2"]["fixed_duration_vs_continuous"]["value"].startswith("cont")


def test_a_cited_trial_record_is_not_used(tmp_path: Path) -> None:
    """An abstract that cites another trial's NCT id gets no registry values from it."""

    class FakeLLM:
        def __init__(self) -> None:
            self.ops: list[str] = []

        async def generate_structured(
            self, prompt: str, response_schema: Any, **kw: Any
        ) -> Any:
            self.ops.append(kw["operation"])
            return RecordMatch(
                relation="another trial", reason="phase 3 cited as background"
            )

    (tmp_path / "NCT01234567.json").write_text(json.dumps(STUDY))
    run = {
        "nct_ids": ["NCT01234567"],
        "arms": [{"arm_id": "arm_1", "arm_name": "Drug X", "role": "single arm"}],
    }
    llm = FakeLLM()
    out = asyncio.run(run_one("1", "text", run, registry_family(CSV), llm, tmp_path, None))  # type: ignore[arg-type]
    assert out["error"] == "no record of this study"
    assert out["record_matches"][0]["nct_id"] == "NCT01234567"
    assert llm.ops == ["ash_registry_match"]  # no fill call


def test_resume_redoes_errors_and_changed_arms() -> None:
    run = {"arms": [{"arm_id": "arm_1", "arm_name": "A", "role": "single arm"}]}
    ok = {"arms": run["arms"], "error": None}
    assert done(ok, run)
    assert done({**ok, "error": "no arms"}, run)
    assert not done(None, run)
    assert not done({**ok, "error": "OpenRouterTruncatedError: cut off"}, run)
    assert not done({**ok, "arms": []}, run)
