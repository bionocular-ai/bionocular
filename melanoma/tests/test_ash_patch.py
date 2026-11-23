"""Tests for patching an earlier ASH run (no live model calls)."""

import sys
from pathlib import Path
from typing import Any

import pytest

_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root / "scripts"))

from ash_patch import NList, fill_n, merge, pending_n, stated_n  # noqa: E402

ARMS = [{"arm_id": "arm_1", "arm_name": "Drug X", "role": "single arm"}]


def _cell(value: str, **kw: Any) -> dict[str, Any]:
    return {"value": value, "quote": f"q {value}", "detail": "", "derived": False, **kw}


def _entry() -> dict[str, Any]:
    return {
        "arms": ARMS,
        "errors": [],
        "families": {
            "response_rates": {
                "extracted": {
                    "pooled": [{"field": "orr", "context": "", **_cell("70")}],
                    "arms": {
                        "arm_1": {
                            "orr": _cell("80"),
                            "cr_rate": _cell("40", n="20"),  # already has n
                            "median_dor": _cell("12.1"),  # not a percent
                            "extra": [
                                {"field": "orr", "context": "age >=75", **_cell("75")}
                            ],
                        }
                    },
                }
            },
            "regimen_drug": {
                "extracted": {"arms": {"arm_1": {"dose": _cell("48 mg")}}}
            },
        },
    }


PERCENT = {"orr", "cr_rate"}


def test_pending_n_is_filled_percent_values_without_n() -> None:
    got = pending_n(_entry(), PERCENT)
    assert [(t["arm"], t["field"], t["value"]) for t in got] == [
        ("all arms together", "orr", "70"),
        ("Drug X", "orr", "80"),
        ("Drug X", "orr", "75"),
    ]
    assert got[2]["context"] == "age >=75"


def test_stated_n_keeps_only_whole_numbers_in_the_text() -> None:
    text = "ORR was 80% among 21 evaluable patients; 2.1 months; 121 enrolled"
    assert stated_n(" 21 ", text) == "21"
    assert stated_n("2", text) == ""  # only inside 2.1
    assert stated_n("12", text) == ""  # only inside 121
    assert stated_n("about 21", text) == ""


class FakeN:
    def __init__(self, reply: list[dict[str, Any]]) -> None:
        self.reply = reply
        self.prompts: list[str] = []

    async def generate_structured(
        self, prompt: str, response_schema: Any, **kw: Any
    ) -> Any:
        self.prompts.append(prompt)
        assert response_schema is NList
        return NList.model_validate({"items": self.reply})


@pytest.mark.asyncio
async def test_fill_n_sets_n_on_every_pending_value_and_is_idempotent() -> None:
    entry = _entry()
    llm = FakeN([{"id": 1, "n": "30"}, {"id": 2, "n": "21"}])  # id 3 missing
    count = await fill_n(entry, "21 of 30 patients", llm, PERCENT)  # type: ignore[arg-type]
    rates = entry["families"]["response_rates"]["extracted"]
    assert count == 3
    assert rates["pooled"][0]["n"] == "30"
    assert rates["arms"]["arm_1"]["orr"]["n"] == "21"
    assert rates["arms"]["arm_1"]["extra"][0]["n"] == ""
    assert rates["arms"]["arm_1"]["cr_rate"]["n"] == "20"
    assert "n" not in rates["arms"]["arm_1"]["median_dor"]
    assert await fill_n(entry, "", llm, PERCENT) == 0  # type: ignore[arg-type]
    assert len(llm.prompts) == 1


def test_merge_replaces_entries_whole_and_families_by_key() -> None:
    base = {"1": _entry(), "2": _entry(), "3": _entry()}
    rerun = {"2": {"arms": [], "errors": ["new"], "families": {}}}
    fam_run = {
        "1": {
            "arms": [{**ARMS[0], "dose_level": ""}],
            "errors": [],
            "families": {"ae_reporting": {"extracted": {"trial": {}}}},
        }
    }
    out = merge(base, rerun, fam_run, ["1", "2"])
    assert set(out) == {"1", "2"}  # selection only
    assert out["2"] == rerun["2"]
    assert set(out["1"]["families"]) == {
        "response_rates",
        "regimen_drug",
        "ae_reporting",
    }
    assert "ae_reporting" not in base["1"]["families"]  # base untouched


def test_merge_refuses_families_run_on_other_arms() -> None:
    fam_run = {"1": {"arms": [{**ARMS[0], "arm_name": "Drug Z", "dose_level": ""}],
                     "errors": [], "families": {}}}  # fmt: skip
    with pytest.raises(ValueError, match="other arms"):
        merge({"1": _entry()}, {}, fam_run, ["1"])
    with pytest.raises(ValueError, match="in no input"):
        merge({}, {}, {}, ["9"])
