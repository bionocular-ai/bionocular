"""ASH test run: arms, then per field family: extract, check, judge, look for missed values.

Usage (from melanoma/):
  poetry run python3 scripts/ash_test_run.py --ids 94 --out data/ash_test_run/probe.json

Results go to --out after each abstract; a rerun skips abstracts that finished cleanly.
The results file records a fingerprint of the prompts and fields; a rerun with
different prompts or fields refuses to resume into it.
"""

import argparse
import asyncio
import csv
import hashlib
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

from ash_checks import cell_flags, same_on_arms  # noqa: E402
from ash_fields import (  # noqa: E402
    ARM_PROMPT,
    Arm,
    ArmList,
    Family,
    JudgeVerdict,
    family_prompt,
    fields_for,
    judge_items,
    judge_prompt,
    load_families,
    missed_model,
    missed_prompt,
    response_model,
)

from src.domain.structured_llm_interfaces import StructuredLLMService  # noqa: E402
from src.infrastructure.cost_calculator import CostCalculator, ModelType  # noqa: E402
from src.infrastructure.openrouter_structured_service import (  # noqa: E402
    OpenRouterStructuredService,
)

logger = logging.getLogger(__name__)

MAX_TOKENS = 16384  # a 4-arm family with 25 fields of value + quote runs ~8k tokens
META = "_meta"
_NCT = re.compile(r"NCT\d{8}")
_FINGERPRINT_FILES = ("ash_fields.py", "ash_checks.py")


def parse_md(path: Path) -> dict[str, str]:
    """Abstract number -> full block text (including its '### Abstract ID:' line)."""
    blocks = path.read_text(encoding="utf-8").split("### Abstract ID:")[1:]
    out = {}
    for block in blocks:
        number = block.strip().splitlines()[0].strip()
        out[number] = ("### Abstract ID:" + block).strip() + "\n"
    return out


def fingerprint(families: tuple[Family, ...]) -> str:
    """Changes whenever a prompt, a check or a field does."""
    h = hashlib.sha256(repr(families).encode())
    for name in _FINGERPRINT_FILES:
        h.update((Path(__file__).parent / name).read_bytes())
    return h.hexdigest()[:16]


def _with_abstract(prompt: str, text: str) -> str:
    return f"{prompt}\n\nABSTRACT:\n{text}"


async def find_arms(text: str, llm: StructuredLLMService) -> tuple[list[Arm], str]:
    found = await llm.generate_structured(
        prompt=ARM_PROMPT.replace("{abstract_text}", text),
        response_schema=ArmList,
        temperature=0.0,
        max_tokens=4096,
        operation="ash_arms",
    )
    arms: list[Arm] = []
    seen: set[str] = set()
    for item in found.arms:
        name = " ".join(item.arm_name.split())
        if not name or name.lower() in seen:  # same drugs twice is one arm
            continue
        seen.add(name.lower())
        arms.append(Arm(f"arm_{len(arms) + 1}", name, item.role))
    return arms, found.results_reported


def _flags(
    family: Family, extracted: dict[str, Any], text: str
) -> dict[str, list[str]]:
    """Code-check flags per filled value, keyed 'arm_id.key'."""
    by_key = {f.key: f for f in family.fields}
    repeated = same_on_arms(family, extracted)
    scopes = list(extracted.get("arms", {}).items())
    if "trial" in extracted:
        scopes.append(("trial", extracted["trial"]))
    out: dict[str, list[str]] = {}
    for arm_id, cells in scopes:
        for key, cell in cells.items():
            if key == "extra" or not cell["value"]:
                continue
            flags = cell_flags(by_key[key], cell, text)
            if (arm_id, key) in repeated:
                flags.append("same_on_arms")
            if flags:
                out[f"{arm_id}.{key}"] = flags
    return out


def _truly_missed(
    items: list[dict[str, Any]], extracted: dict[str, Any]
) -> list[dict[str, Any]]:
    """Keep only items for a field the extraction asked for and left empty.

    The model tends to repeat values that are already filled, or to put a pooled
    value back on an arm.
    """
    cells = {"trial": extracted.get("trial", {}), **extracted.get("arms", {})}
    pooled = {(p["field"], p["value"].strip()) for p in extracted.get("pooled", [])}
    return [
        i
        for i in items
        if i["value"].strip()
        and i["field"] in cells.get(i["arm_id"], {})
        and not cells[i["arm_id"]][i["field"]]["value"]
        and (i["field"], i["value"].strip()) not in pooled
    ]


async def _run_family(
    family: Family,
    arms: list[Arm],
    text: str,
    llm: StructuredLLMService,
    sem: asyncio.Semaphore,
    missed_pass: bool,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "extracted": None,
        "flags": {},
        "items": [],
        "judge": None,
        "missed": None,
        "error": None,
    }
    try:
        async with sem:
            extracted = await llm.generate_structured(
                prompt=_with_abstract(family_prompt(family, arms), text),
                response_schema=response_model(family, arms),
                temperature=0.0,
                max_tokens=MAX_TOKENS,
                operation=f"ash_extract:{family.key}",
            )
        result["extracted"] = extracted.model_dump()
        result["flags"] = _flags(family, result["extracted"], text)
        result["items"] = judge_items(family, result["extracted"], arms)
        if result["items"]:
            async with sem:
                verdict = await llm.generate_structured(
                    prompt=_with_abstract(
                        judge_prompt(family, result["items"], arms), text
                    ),
                    response_schema=JudgeVerdict,
                    temperature=0.0,
                    max_tokens=MAX_TOKENS,
                    operation=f"ash_judge:{family.key}",
                )
            result["judge"] = verdict.model_dump()
            got = {i.id for i in verdict.items}
            lost = {i["id"] for i in result["items"]} - got
            if lost:
                logger.warning("judge skipped %d items in %s", len(lost), family.key)
        if missed_pass:
            async with sem:
                missed = await llm.generate_structured(
                    prompt=_with_abstract(
                        missed_prompt(family, result["extracted"], arms), text
                    ),
                    response_schema=missed_model(family, arms),
                    temperature=0.0,
                    max_tokens=4096,
                    operation=f"ash_missed:{family.key}",
                )
            result["missed"] = {
                "items": _truly_missed(
                    missed.model_dump()["items"], result["extracted"]
                )
            }
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
    indication: str | None = None,
    missed_pass: bool = True,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "abstract": number,
        "nct_ids": sorted(set(_NCT.findall(text))),
        "arms": [],
        "families": {},
        "errors": [],
    }
    try:
        async with family_sem:
            arms, out["results_reported"] = await find_arms(text, llm)
    except Exception as e:
        out["errors"].append(f"arms: {type(e).__name__}: {e}")
        return out
    if not arms:
        out["errors"].append("arms: none found")
        return out
    out["arms"] = [
        {"arm_id": a.arm_id, "arm_name": a.arm_name, "role": a.role} for a in arms
    ]
    asked = [g for g in (fields_for(f, indication) for f in families) if g.fields]
    results = await asyncio.gather(
        *(_run_family(f, arms, text, llm, family_sem, missed_pass) for f in asked)
    )
    out["families"] = {f.key: r for f, r in zip(asked, results, strict=True)}
    return out


def _complete(result: dict[str, Any]) -> bool:
    fams = result.get("families", {})
    return (
        not result.get("errors")
        and bool(fams)
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
    indications: dict[str, str] | None = None,
    missed_pass: bool = True,
) -> None:
    texts = parse_md(md_path)
    if ids:
        missing = set(ids) - set(texts)
        if missing:
            raise ValueError(f"ids not in {md_path}: {sorted(missing)}")
        texts = {n: texts[n] for n in ids}
    results: dict[str, Any] = (
        json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    )
    mark = fingerprint(families)
    if results and results.get(META, {}).get("fingerprint") != mark:
        raise ValueError(
            f"{out_path} was written with different prompts or fields; "
            "use a new --out or delete it"
        )
    results[META] = {"fingerprint": mark}
    todo = [n for n in texts if not _complete(results.get(n, {}))]
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
                (indications or {}).get(number),
                missed_pass,
            )
        async with lock:
            results[number] = r
            tmp = out_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(results, indent=1), encoding="utf-8")
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
    p.add_argument(
        "--selection",
        type=Path,
        default=_root / "resources" / "ash" / "test_run_selection.csv",
        help="CSV with abstract,indication; fields are filtered by indication",
    )
    p.add_argument("--ids", help="comma-separated abstract numbers (default: all)")
    p.add_argument("--concurrency", type=int, default=5)
    p.add_argument("--family-concurrency", type=int, default=6)
    p.add_argument(
        "--no-missed-pass", action="store_true", help="skip the missed-value calls"
    )
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
    with args.selection.open(encoding="utf-8", newline="") as f:
        indications = {r["abstract"]: r["indication"] for r in csv.DictReader(f)}
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
                indications,
                not args.no_missed_pass,
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
