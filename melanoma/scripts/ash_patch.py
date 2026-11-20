"""Patch an earlier ASH run up to the current harness without redoing every value.

Usage (from melanoma/):
  # 1. new arms for every abstract (one call each); prints the ones split by dose
  poetry run python3 scripts/ash_patch.py arms --selection S --out full_v2/arms.json
  # 2. ash_test_run.py: full run for the dose-split + new abstracts (--arms-from
  #    full_v2/arms.json), and --families for new or changed families on the rest
  #    (--arms-from full_v1/results.json)
  # 3. one results file: base, whole entries from the full run, families from the rest
  poetry run python3 scripts/ash_patch.py merge --base full_v1/results.json \\
      --entries full_v2/rerun.json --families-from full_v2/families.json \\
      --selection S --out full_v2/results.json
  # 4. n (patients a rate is over) for every percent value written before n existed
  poetry run python3 scripts/ash_patch.py n --results full_v2/results.json

Steps 1 and 4 save after each abstract and resume.
"""

import argparse
import asyncio
import csv
import json
import os
import re
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel

_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(Path(__file__).parent))

from ash_fields import Arm, Family, load_families  # noqa: E402
from ash_test_run import META, find_arms, parse_md  # noqa: E402

from src.domain.structured_llm_interfaces import StructuredLLMService  # noqa: E402
from src.infrastructure.cost_calculator import CostCalculator, ModelType  # noqa: E402
from src.infrastructure.openrouter_structured_service import (  # noqa: E402
    OpenRouterStructuredService,
)

CSV = _root / "resources" / "ash" / "book1_sheet2.csv"
MD = Path("data/postprocessed/ASH_Abstracts/ASH_2025_all.md")


def _save(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def _selection(path: Path) -> list[str]:
    with path.open(encoding="utf-8", newline="") as f:
        return [r["abstract"] for r in csv.DictReader(f)]


def dose_split(entry: dict[str, Any]) -> bool:
    return any(a.get("dose_level") for a in entry.get("arms", []))


def merge(
    base: dict[str, Any],
    entries: dict[str, Any],
    families_from: dict[str, Any],
    selection: list[str],
) -> dict[str, Any]:
    """The selection's abstracts: an entry from `entries` replaces the base entry whole
    (new arms, every family); otherwise families from `families_from` replace those
    families of the base entry, which keeps its arms and other families."""
    out: dict[str, Any] = {}
    for n in selection:
        if n in entries:
            out[n] = entries[n]
            continue
        if n not in base:
            raise ValueError(f"abstract {n} is in no input")
        entry = json.loads(json.dumps(base[n]))  # deep copy
        if n in families_from:
            new = families_from[n]
            if new["arms"] != [asdict(Arm(**x)) for x in entry["arms"]]:
                raise ValueError(f"abstract {n}: families were run on other arms")
            entry["families"].update(new["families"])
            entry["errors"] = entry["errors"] + new["errors"]
        out[n] = entry
    return out


def _percent_keys(families: tuple[Family, ...]) -> set[str]:
    return {f.key for fam in families for f in fam.fields if f.value_type == "percent"}


def pending_n(entry: dict[str, Any], percent: set[str]) -> list[dict[str, Any]]:
    """Filled percent values with no n key yet (written before n existed), each with a
    reference to the dict to patch."""
    labels = {a["arm_id"]: Arm(**a).label for a in entry.get("arms", [])}
    labels |= {"trial": "whole trial", "pooled": "all arms together"}
    out: list[dict[str, Any]] = []

    def add(scope: str, key: str, cell: dict[str, Any], context: str = "") -> None:
        if key in percent and cell.get("value") and "n" not in cell:
            out.append(
                {"cell": cell, "arm": labels.get(scope, scope), "field": key,
                 "value": cell["value"], "context": context, "quote": cell["quote"]}
            )  # fmt: skip

    for fam in entry.get("families", {}).values():
        ex = fam.get("extracted") or {}
        for p in ex.get("pooled", []):
            add("pooled", p["field"], p, p.get("context", ""))
        scopes = list(ex.get("arms", {}).items())
        if "trial" in ex:
            scopes.append(("trial", ex["trial"]))
        for scope, cells in scopes:
            for key, cell in cells.items():
                if key != "extra":
                    add(scope, key, cell)
            for e in cells.get("extra", []):
                add(scope, e["field"], e, e.get("context", ""))
    return out


class NItem(BaseModel):
    id: int
    n: str


class NList(BaseModel):
    items: list[NItem]


N_PROMPT = """TASK: For each rate below, give n: the number of patients the rate is over, when the abstract states it for that rate or its population ("8 of 21" -> "21", "among 20 evaluable patients, ..." -> "20", "(n=45)" for the arm the rate is in -> "45"). Never work it out from the percent. "" when the abstract does not state it. Use only the abstract. Return one item for every id.

RATES (id | arm | field | value | context | quote)
{items}

ABSTRACT:
{text}
"""


def stated_n(n: str, text: str) -> str:
    """Keep n only if it is a whole number the abstract writes."""
    n = n.strip()
    ok = n.isdigit() and re.search(rf"(?<![\d.,]){n}(?![\d]|[.,]\d)", text)
    return n if ok else ""


async def fill_n(
    entry: dict[str, Any], text: str, llm: StructuredLLMService, percent: set[str]
) -> int:
    todo = pending_n(entry, percent)
    if not todo:
        return 0
    lines = "\n".join(
        f"{i} | {t['arm']} | {t['field']} | {t['value']} | {t['context']} | \"{t['quote']}\""
        for i, t in enumerate(todo, 1)
    )
    got = await llm.generate_structured(
        prompt=N_PROMPT.format(items=lines, text=text),
        response_schema=NList,
        temperature=0.0,
        max_tokens=8192,
        operation="ash_patch_n",
    )
    by_id = {i.id: i.n for i in got.items}
    for i, t in enumerate(todo, 1):
        t["cell"]["n"] = stated_n(by_id.get(i, ""), text)
    return len(todo)


def _llm(out_dir: Path) -> tuple[CostCalculator, OpenRouterStructuredService]:
    load_dotenv(_root / ".env")
    costs = CostCalculator(ModelType.DEEPSEEK_V41_FLASH)
    return costs, OpenRouterStructuredService(
        ModelType.DEEPSEEK_V41_FLASH.value, costs, call_log_path=out_dir / "calls.jsonl"
    )


async def _each(
    numbers: list[str],
    work: Any,
    path: Path,
    data: dict[str, Any],
    costs: CostCalculator,
) -> None:
    sem, lock = asyncio.Semaphore(5), asyncio.Lock()

    async def one(n: str) -> None:
        async with sem:
            note = await work(n)
        async with lock:
            _save(path, data)
        print(f"{n}: {note} (spend ${costs.get_summary().total_cost:.2f})")

    await asyncio.gather(*(one(n) for n in numbers))


def cmd_arms(args: argparse.Namespace) -> None:
    texts = parse_md(args.md)
    out: dict[str, Any] = (
        json.loads(args.out.read_text(encoding="utf-8")) if args.out.exists() else {}
    )
    todo = [n for n in _selection(args.selection) if not out.get(n, {}).get("arms")]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    costs, llm = _llm(args.out.parent)

    async def work(n: str) -> str:
        try:
            arms, reported = await find_arms(texts[n], llm)
        except Exception as e:  # recorded; a rerun retries it
            out[n] = {"arms": [], "errors": [f"arms: {type(e).__name__}: {e}"]}
            return out[n]["errors"][0]
        out[n] = {"arms": [asdict(a) for a in arms], "results_reported": reported}
        return f"{len(arms)} arms"

    async def go() -> None:
        try:
            await _each(todo, work, args.out, out, costs)
        finally:
            await llm.aclose()

    asyncio.run(go())
    split = [n for n, e in out.items() if n != META and dose_split(e)]
    print(f"dose-split: {len(split)}\n{','.join(split)}")


def cmd_merge(args: argparse.Namespace) -> None:
    def load(p: Path | None) -> dict[str, Any]:
        d = json.loads(p.read_text(encoding="utf-8")) if p else {}
        d.pop(META, None)
        return d

    out = merge(load(args.base), load(args.entries), load(args.families_from),
                _selection(args.selection))  # fmt: skip
    out[META] = {
        "merged_from": [
            str(p) for p in (args.base, args.entries, args.families_from) if p
        ]
    }
    _save(args.out, out)
    print(f"wrote {args.out}: {len(out) - 1} abstracts")


def cmd_n(args: argparse.Namespace) -> None:
    texts = parse_md(args.md)
    results = json.loads(args.results.read_text(encoding="utf-8"))
    percent = _percent_keys(load_families(CSV))
    todo = [n for n, e in results.items() if n != META and pending_n(e, percent)]
    print(f"{len(todo)} abstracts with rates lacking n")
    costs, llm = _llm(args.results.parent)

    async def work(n: str) -> str:
        try:
            return f"{await fill_n(results[n], texts[n], llm, percent)} rates"
        except Exception as e:  # left pending; a rerun retries it
            return f"failed: {type(e).__name__}: {e}"

    async def go() -> None:
        try:
            await _each(todo, work, args.results, results, costs)
        finally:
            await llm.aclose()

    asyncio.run(go())


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("arms")
    a.add_argument("--selection", type=Path, required=True)
    a.add_argument("--out", type=Path, required=True)
    a.add_argument("--md", type=Path, default=MD)
    m = sub.add_parser("merge")
    m.add_argument("--base", type=Path, required=True)
    m.add_argument("--entries", type=Path)
    m.add_argument("--families-from", type=Path)
    m.add_argument("--selection", type=Path, required=True)
    m.add_argument("--out", type=Path, required=True)
    n = sub.add_parser("n")
    n.add_argument("--results", type=Path, required=True)
    n.add_argument("--md", type=Path, default=MD)
    args = p.parse_args()
    {"arms": cmd_arms, "merge": cmd_merge, "n": cmd_n}[args.cmd](args)


if __name__ == "__main__":
    main()
