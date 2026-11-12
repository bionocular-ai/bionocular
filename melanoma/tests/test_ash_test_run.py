"""Tests for the ASH test-run harness (no live model calls)."""

import asyncio
import json
import sys
import types
from pathlib import Path
from typing import Any, Literal, get_args, get_origin

import pytest
from pydantic import BaseModel

_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root / "scripts"))

from ash_fields import ArmList, JudgeVerdict, load_families  # noqa: E402
from ash_test_run import (  # noqa: E402
    META,
    _truly_missed,
    fingerprint,
    parse_md,
    run,
    run_abstract,
)

FAMILIES = load_families(_root / "resources" / "ash" / "book1_sheet2.csv")[:3]


def _fill(model: type[BaseModel]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, info in model.model_fields.items():
        ann = info.annotation
        if get_origin(ann) is Literal:
            out[name] = get_args(ann)[0]
        elif get_origin(ann) in (list, types.GenericAlias) or ann is list:
            out[name] = []
        elif ann is bool:
            out[name] = False
        elif isinstance(ann, type) and issubclass(ann, BaseModel):
            out[name] = _fill(ann)
        else:
            out[name] = "80" if name == "value" else "ORR 80%"
    return out


class FakeLLM:
    def __init__(self, fail_op: str | None = None, delay: float = 0.0) -> None:
        self.fail_op = fail_op
        self.delay = delay
        self.calls: list[tuple[str, str]] = []  # (operation, prompt)
        self.in_flight = 0
        self.max_in_flight = 0

    async def generate_structured(
        self, prompt: str, response_schema: type[Any], **kw: Any
    ) -> Any:
        op = kw.get("operation", "")
        self.calls.append((op, prompt))
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(self.delay)
            if op == self.fail_op:
                raise RuntimeError("boom")
            if response_schema is ArmList:
                arm = {"role": "experimental", "n": "", "source_text": "s"}
                return ArmList.model_validate(
                    {
                        "results_reported": "per_arm",
                        "arms": [
                            {"arm_name": "Drug X", **arm},
                            {"arm_name": "drug  x", **arm},  # same drugs: one arm
                            {"arm_name": "Placebo", **arm, "role": "control"},
                        ],
                    }
                )
            if response_schema is JudgeVerdict:
                return JudgeVerdict(items=[])
            return response_schema.model_validate(_fill(response_schema))
        finally:
            self.in_flight -= 1


def _abstract(n: str) -> str:
    return f"### Abstract ID: {n}\n\n#### Title:\nT {n} NCT01234567\n\n#### Results:\nORR 80% in arm A.\n"


def _ops(llm: FakeLLM, prefix: str) -> list[str]:
    return [op for op, _ in llm.calls if op.startswith(prefix)]


def test_parse_md(tmp_path: Path) -> None:
    md = tmp_path / "a.md"
    md.write_text(_abstract("94") + "\n" + _abstract("2264"))
    texts = parse_md(md)
    assert list(texts) == ["94", "2264"]
    assert texts["94"].startswith("### Abstract ID: 94")
    assert "2264" not in texts["94"]


def test_missed_items_must_target_an_empty_asked_field() -> None:
    extracted = {
        "arms": {"arm_1": {"orr": {"value": "80"}, "cr": {"value": ""}, "extra": []}}
    }
    items = [
        {"arm_id": "arm_1", "field": "orr", "value": "80", "quote": "q"},  # filled
        {"arm_id": "arm_1", "field": "cr", "value": " ", "quote": ""},  # no value
        {"arm_id": "arm_2", "field": "cr", "value": "5", "quote": "q"},  # not asked
        {"arm_id": "arm_1", "field": "cr", "value": "40", "quote": "q"},
    ]
    assert _truly_missed(items, extracted) == [items[3]]


@pytest.mark.asyncio
async def test_run_abstract_arms_families_checks_and_passes() -> None:
    llm = FakeLLM()
    out = await run_abstract("94", _abstract("94"), llm, FAMILIES, asyncio.Semaphore(4))
    assert out["errors"] == [] and out["nct_ids"] == ["NCT01234567"]
    assert [a["arm_id"] for a in out["arms"]] == ["arm_1", "arm_2"]
    assert [a["role"] for a in out["arms"]] == ["experimental", "control"]
    assert set(out["families"]) == {f.key for f in FAMILIES}
    fam = out["families"][FAMILIES[0].key]
    assert fam["error"] is None and fam["items"] and fam["judge"] == {"items": []}
    assert fam["missed"] == {"items": []}
    assert fam["flags"]  # the filler repeats one value on both arms
    n = len(FAMILIES)
    assert len(_ops(llm, "ash_extract")) == len(_ops(llm, "ash_judge")) == n
    assert len(_ops(llm, "ash_missed")) == n and len(_ops(llm, "ash_arms")) == 1


@pytest.mark.asyncio
async def test_fields_filtered_by_indication_and_missed_pass_off() -> None:
    llm = FakeLLM()
    out = await run_abstract(
        "94",
        _abstract("94"),
        llm,
        FAMILIES,
        asyncio.Semaphore(4),
        indication="Multiple myeloma",
        missed_pass=False,
    )
    assert "survival_other" not in out["families"]  # EFS/RFS do not apply to myeloma
    assert not _ops(llm, "ash_missed")
    assert all(f["missed"] is None for f in out["families"].values())


@pytest.mark.asyncio
async def test_family_failure_isolated() -> None:
    bad = f"ash_extract:{FAMILIES[1].key}"
    out = await run_abstract(
        "94", _abstract("94"), FakeLLM(fail_op=bad), FAMILIES, asyncio.Semaphore(4)
    )
    assert "boom" in out["families"][FAMILIES[1].key]["error"]
    assert out["families"][FAMILIES[0].key]["error"] is None


@pytest.mark.asyncio
async def test_arm_failure_recorded() -> None:
    out = await run_abstract(
        "94",
        _abstract("94"),
        FakeLLM(fail_op="ash_arms"),
        FAMILIES,
        asyncio.Semaphore(4),
    )
    assert out["arms"] == [] and out["families"] == {}
    assert out["errors"] and "boom" in out["errors"][0]


@pytest.mark.asyncio
async def test_resume_skips_complete_and_redoes_partial(tmp_path: Path) -> None:
    md, out = tmp_path / "a.md", tmp_path / "r.json"
    md.write_text(_abstract("1") + "\n" + _abstract("2"))
    await run(md, out, FakeLLM(), FAMILIES)
    saved = json.loads(out.read_text())
    assert saved[META]["fingerprint"] == fingerprint(FAMILIES)
    saved["2"]["families"][FAMILIES[0].key]["error"] = "x"
    out.write_text(json.dumps(saved))
    llm = FakeLLM()
    await run(md, out, llm, FAMILIES)
    assert len(_ops(llm, "ash_arms")) == 1  # only abstract 2 is redone
    assert (
        json.loads(out.read_text())["2"]["families"][FAMILIES[0].key]["error"] is None
    )


@pytest.mark.asyncio
async def test_resume_refuses_results_from_other_prompts(tmp_path: Path) -> None:
    md, out = tmp_path / "a.md", tmp_path / "r.json"
    md.write_text(_abstract("1"))
    out.write_text(json.dumps({META: {"fingerprint": "old"}, "1": {}}))
    with pytest.raises(ValueError, match="different prompts or fields"):
        await run(md, out, FakeLLM(), FAMILIES)


@pytest.mark.asyncio
async def test_ids_subset(tmp_path: Path) -> None:
    md, out = tmp_path / "a.md", tmp_path / "r.json"
    md.write_text(_abstract("1") + "\n" + _abstract("2"))
    await run(md, out, FakeLLM(), FAMILIES, ids=["2"])
    assert set(json.loads(out.read_text())) == {META, "2"}
    with pytest.raises(ValueError):
        await run(md, out, FakeLLM(), FAMILIES, ids=["9"])


@pytest.mark.asyncio
async def test_concurrency_bounds(tmp_path: Path) -> None:
    md, out = tmp_path / "a.md", tmp_path / "r.json"
    md.write_text("\n".join(_abstract(str(i)) for i in range(4)))
    llm = FakeLLM(delay=0.01)
    await run(md, out, llm, FAMILIES, concurrency=2, family_concurrency=2)
    assert 1 < llm.max_in_flight <= 4
