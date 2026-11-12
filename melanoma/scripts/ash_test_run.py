"""ASH test run: extract every workbook field from ASH abstracts, then judge each family.

Usage (from melanoma/):
  poetry run python3 scripts/ash_test_run.py --ids 94 --out data/ash_test_run/probe.json

Results go to --out after each abstract; a rerun skips abstracts that finished cleanly.
Resume does not fingerprint prompts: delete results.json after a prompt change.
"""

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(Path(__file__).parent))

from ash_fields import (  # noqa: E402
    HEME_SEPARATION_PROMPT,
    Family,
    JudgeVerdict,
    family_prompt,
    judge_prompt,
    load_families,
    response_model,
)

from src.domain.structured_llm_interfaces import StructuredLLMService  # noqa: E402
from src.domain.treatment_arm_models import TreatmentArm  # noqa: E402
from src.infrastructure.cost_calculator import CostCalculator, ModelType  # noqa: E402
from src.infrastructure.openrouter_structured_service import (  # noqa: E402
    OpenRouterStructuredService,
)
from src.infrastructure.treatment_arm_separator import (  # noqa: E402
    TreatmentArmSeparator,
)

logger = logging.getLogger(__name__)

MAX_TOKENS = 16384  # a 4-arm family with 25 fields of value + quote runs ~8k tokens
_WS = re.compile(r"\s+")


def parse_md(path: Path) -> dict[str, str]:
    """Abstract number -> full block text (including its '### Abstract ID:' line)."""
    blocks = path.read_text(encoding="utf-8").split("### Abstract ID:")[1:]
    out = {}
    for block in blocks:
        number = block.strip().splitlines()[0].strip()
        out[number] = ("### Abstract ID:" + block).strip() + "\n"
    return out


def quote_found(quote: str, text: str) -> bool:
    q = _WS.sub(" ", quote).strip()
    return bool(q) and q in _WS.sub(" ", text)


def _with_abstract(prompt: str, text: str) -> str:
    return f"{prompt}\n\nABSTRACT:\n{text}"


async def _run_family(
    family: Family,
    arms: list[TreatmentArm],
    text: str,
    llm: StructuredLLMService,
    sem: asyncio.Semaphore,
) -> dict[str, Any]:
    result: dict[str, Any] = {"extracted": None, "judge": None, "error": None}
    try:
        async with sem:
            model = response_model(family, [a.arm_id for a in arms])
            extracted = await llm.generate_structured(
                prompt=_with_abstract(family_prompt(family, arms), text),
                response_schema=model,
                temperature=0.0,
                max_tokens=MAX_TOKENS,
                operation=f"ash_extract:{family.key}",
            )
            result["extracted"] = extracted.model_dump()
        async with sem:
            verdict = await llm.generate_structured(
                prompt=_with_abstract(
                    judge_prompt(family, result["extracted"], arms), text
                ),
                response_schema=JudgeVerdict,
                temperature=0.0,
                max_tokens=MAX_TOKENS,
                operation=f"ash_judge:{family.key}",
            )
            result["judge"] = verdict.model_dump()
    except Exception as e:  # recorded per family so the other families still finish
        logger.error("family %s failed: %s", family.key, e)
        result["error"] = f"{type(e).__name__}: {e}"
    return result


async def run_abstract(
    number: str,
    text: str,
    llm: StructuredLLMService,
    families: tuple[Family, ...],
    family_sem: asyncio.Semaphore,
) -> dict[str, Any]:
    out: dict[str, Any] = {"abstract": number, "arms": [], "families": {}, "errors": []}
    separator = TreatmentArmSeparator(llm, separation_prompt=HEME_SEPARATION_PROMPT)
    try:
        async with family_sem:
            separation = await separator.separate_treatment_arms(text, number)
    except Exception as e:  # transient errors propagate from the separator
        out["errors"].append(f"arms: {type(e).__name__}: {e}")
        return out
    if not separation.treatment_arms:
        out["errors"].append(f"arms: none found {separation.errors}")
        return out
    # Arm ids become schema property names, so normalise them to arm_<n>.
    arms = [
        a.model_copy(update={"arm_id": f"arm_{i}"})
        for i, a in enumerate(separation.treatment_arms, 1)
    ]
    out["arms"] = [{"arm_id": a.arm_id, "arm_name": a.arm_name} for a in arms]
    results = await asyncio.gather(
        *(_run_family(f, arms, text, llm, family_sem) for f in families)
    )
    out["families"] = {f.key: r for f, r in zip(families, results, strict=True)}
    return out


def _complete(result: dict[str, Any], families: tuple[Family, ...]) -> bool:
    fams = result.get("families", {})
    return (
        not result.get("errors")
        and set(fams) == {f.key for f in families}
        and all(r["error"] is None for r in fams.values())
    )


async def run(
    md_path: Path,
    out_path: Path,
    llm: StructuredLLMService,
    families: tuple[Family, ...],
    concurrency: int = 5,
    family_concurrency: int = 6,
    ids: list[str] | None = None,
) -> None:
    texts = parse_md(md_path)
    if ids:
        missing = set(ids) - set(texts)
        if missing:
            raise ValueError(f"ids not in {md_path}: {sorted(missing)}")
        texts = {n: texts[n] for n in ids}
    results: dict[str, Any] = (
        json.loads(out_path.read_text()) if out_path.exists() else {}
    )
    todo = [n for n in texts if not _complete(results.get(n, {}), families)]
    print(f"{len(texts) - len(todo)} already done, {len(todo)} to run")
    sem = asyncio.Semaphore(concurrency)
    lock = asyncio.Lock()

    async def one(number: str) -> None:
        async with sem:
            r = await run_abstract(
                number,
                texts[number],
                llm,
                families,
                asyncio.Semaphore(family_concurrency),
            )
        async with lock:
            results[number] = r
            tmp = out_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(results, indent=1))
            os.replace(tmp, out_path)
        bad = r["errors"] + [k for k, f in r["families"].items() if f["error"]]
        print(
            f"{number}: {len(r['arms'])} arms, {'errors ' + str(bad) if bad else 'ok'}"
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.gather(*(one(n) for n in todo))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--md", type=Path, default=Path("data/postprocessed/ASH_Abstracts/ASH_2025.md")
    )
    p.add_argument("--out", type=Path, default=Path("data/ash_test_run/results.json"))
    p.add_argument("--ids", help="comma-separated abstract numbers (default: all)")
    p.add_argument("--concurrency", type=int, default=5)
    p.add_argument("--family-concurrency", type=int, default=6)
    args = p.parse_args()

    logging.basicConfig(level=logging.WARNING)
    load_dotenv(_root / ".env")
    costs = CostCalculator(ModelType.DEEPSEEK_V41_FLASH)
    llm = OpenRouterStructuredService(
        ModelType.DEEPSEEK_V41_FLASH.value,
        costs,
        call_log_path=args.out.parent / "calls.jsonl",
    )
    families = load_families(_root / "resources" / "ash" / "book1_sheet2.csv")
    ids = args.ids.split(",") if args.ids else None
    start = time.monotonic()

    async def _run_and_close() -> None:
        try:
            await run(
                args.md,
                args.out,
                llm,
                families,
                args.concurrency,
                args.family_concurrency,
                ids,
            )
        finally:
            await llm.aclose()

    asyncio.run(_run_and_close())
    summary = costs.get_summary()
    print(
        f"spend ${summary.total_cost:.4f} over {summary.total_requests} calls, "
        f"wall {time.monotonic() - start:.0f}s"
    )


if __name__ == "__main__":
    main()
