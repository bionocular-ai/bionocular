"""Tests for the ASH test-run harness (no live calls)."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "scripts"))

from ash_fields import Cell, JudgeVerdict, load_families  # noqa: E402
from ash_test_run import parse_md, quote_found, run, run_abstract  # noqa: E402

from src.domain.treatment_arm_models import TreatmentArmSeparationSchema  # noqa: E402

FAMILIES = load_families(_root / "resources" / "ash" / "book1_sheet2.csv")[:3]


def _fill(model: type[BaseModel]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, info in model.model_fields.items():
        ann = info.annotation
        if ann is Cell:
            out[name] = {"value": "v", "quote": "ORR 80%"}
        elif isinstance(ann, type) and issubclass(ann, BaseModel):
            out[name] = _fill(ann)
        else:
            out[name] = ""
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
            if response_schema is TreatmentArmSeparationSchema:
                return TreatmentArmSeparationSchema.model_validate(
                    {
                        "treatment_arms": [
                            {
                                "arm_id": "A 1",
                                "arm_name": "Drug X",
                                "generic_name": "x",
                            },
                            {"arm_id": "B", "arm_name": "Control", "generic_name": "y"},
                        ]
                    }
                )
            if response_schema is JudgeVerdict:
                return JudgeVerdict(items=[])
            return response_schema.model_validate(_fill(response_schema))
        finally:
            self.in_flight -= 1


def _abstract(n: str) -> str:
    return f"### Abstract ID: {n}\n\n#### Title:\nT{n}\n\n#### Results:\nORR  80%\n"


def test_parse_md(tmp_path: Path) -> None:
    md = tmp_path / "a.md"
    md.write_text(_abstract("94") + "\n" + _abstract("2264"))
    texts = parse_md(md)
    assert list(texts) == ["94", "2264"]
    assert texts["94"].startswith("### Abstract ID: 94")
    assert "T2264" in texts["2264"] and "T94" not in texts["2264"]


def test_quote_found() -> None:
    text = "ORR was\n 80%  (95% CI 70-90)"
    assert quote_found("ORR was 80% (95% CI 70-90)", text)
    assert not quote_found("ORR was 81%", text)
    assert not quote_found("", text)


@pytest.mark.asyncio
async def test_run_abstract_collects_families_and_judge() -> None:
    llm = FakeLLM()
    r = await run_abstract("94", _abstract("94"), llm, FAMILIES, asyncio.Semaphore(6))
    assert r["abstract"] == "94" and r["errors"] == []
    assert r["arms"] == [
        {"arm_id": "arm_1", "arm_name": "Drug X"},
        {"arm_id": "arm_2", "arm_name": "Control"},
    ]
    assert set(r["families"]) == {f.key for f in FAMILIES}
    for fam in r["families"].values():
        assert fam["error"] is None
        assert set(fam["extracted"]["arms"]) == {"arm_1", "arm_2"}
        assert fam["judge"] == {"items": []}
    # The abstract text reaches both the family and the judge prompts.
    extract_prompts = [p for op, p in llm.calls if op.startswith("ash_extract")]
    judge_prompts = [p for op, p in llm.calls if op.startswith("ash_judge")]
    assert len(extract_prompts) == len(judge_prompts) == len(FAMILIES)
    assert all("ORR  80%" in p for p in extract_prompts + judge_prompts)


@pytest.mark.asyncio
async def test_family_failure_isolated() -> None:
    bad = FAMILIES[1].key
    llm = FakeLLM(fail_op=f"ash_extract:{bad}")
    r = await run_abstract("94", _abstract("94"), llm, FAMILIES, asyncio.Semaphore(6))
    assert "boom" in r["families"][bad]["error"]
    assert r["families"][bad]["extracted"] is None
    for f in FAMILIES:
        if f.key != bad:
            assert r["families"][f.key]["error"] is None
            assert r["families"][f.key]["extracted"] is not None
            assert r["families"][f.key]["judge"] is not None


@pytest.mark.asyncio
async def test_judge_failure_is_a_family_error() -> None:
    bad = FAMILIES[0].key
    llm = FakeLLM(fail_op=f"ash_judge:{bad}")
    r = await run_abstract("94", _abstract("94"), llm, FAMILIES, asyncio.Semaphore(6))
    assert r["families"][bad]["extracted"] is not None
    assert "boom" in r["families"][bad]["error"]


@pytest.mark.asyncio
async def test_arm_failure_recorded() -> None:
    llm = FakeLLM(fail_op="treatment_arm_separation")
    r = await run_abstract("94", _abstract("94"), llm, FAMILIES, asyncio.Semaphore(6))
    assert r["errors"] and r["families"] == {}


@pytest.mark.asyncio
async def test_resume_skips_complete_and_redoes_partial(tmp_path: Path) -> None:
    md = tmp_path / "a.md"
    md.write_text("\n".join(_abstract(n) for n in ("1", "2", "3")))
    out = tmp_path / "results.json"
    done = await run_abstract(
        "1", _abstract("1"), FakeLLM(), FAMILIES, asyncio.Semaphore(6)
    )
    partial = await run_abstract(
        "2",
        _abstract("2"),
        FakeLLM(fail_op=f"ash_extract:{FAMILIES[0].key}"),
        FAMILIES,
        asyncio.Semaphore(6),
    )
    out.write_text(json.dumps({"1": done, "2": partial}))

    llm = FakeLLM()
    await run(md, out, llm, FAMILIES)
    prompts = [p for _, p in llm.calls]
    assert not any("T1\n" in p for p in prompts)
    assert any("T2\n" in p for p in prompts) and any("T3\n" in p for p in prompts)
    saved = json.loads(out.read_text())
    assert set(saved) == {"1", "2", "3"}
    assert all(
        f["error"] is None for r in saved.values() for f in r["families"].values()
    )


@pytest.mark.asyncio
async def test_ids_subset(tmp_path: Path) -> None:
    md = tmp_path / "a.md"
    md.write_text("\n".join(_abstract(n) for n in ("1", "2")))
    out = tmp_path / "results.json"
    await run(md, out, FakeLLM(), FAMILIES, ids=["2"])
    assert set(json.loads(out.read_text())) == {"2"}


@pytest.mark.asyncio
async def test_concurrency_bounds(tmp_path: Path) -> None:
    md = tmp_path / "a.md"
    md.write_text("\n".join(_abstract(str(n)) for n in range(6)))
    llm = FakeLLM(delay=0.01)
    await run(
        md, tmp_path / "r.json", llm, FAMILIES, concurrency=2, family_concurrency=2
    )
    assert 2 < llm.max_in_flight <= 4
