"""ASH triage: keep only abstracts that report treatment outcomes.

One call per abstract classifies what it reports. Kept rows of --selection go to
--keep-csv, which ash_test_run.py takes as its --selection.

Usage (from melanoma/):
  poetry run python3 scripts/ash_triage.py --md data/postprocessed/ASH_Abstracts/ASH_2025_all.md \
    --selection resources/ash/full_run_selection.csv \
    --out data/ash_test_run/full_v1/triage.json --keep-csv data/ash_test_run/full_v1/selection.csv

--out is written after each abstract; a rerun skips abstracts already classified.
"""

import argparse
import asyncio
import csv
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from pydantic import BaseModel

_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(Path(__file__).parent))

from ash_test_run import parse_md  # noqa: E402

from src.domain.structured_llm_interfaces import StructuredLLMService  # noqa: E402
from src.infrastructure.cost_calculator import CostCalculator, ModelType  # noqa: E402
from src.infrastructure.openrouter_structured_service import (  # noqa: E402
    OpenRouterStructuredService,
)

KEEP = "treatment_outcomes"


class Triage(BaseModel):
    kind: Literal[
        "treatment_outcomes",
        "trial_in_progress",
        "biomarker_or_translational",
        "patient_reported_only",
        "review_or_meta_analysis",
        "case_report",
        "other_no_outcomes",
    ]
    evidence: str
    reason: str


PROMPT = """TASK: Decide what this hematology conference abstract reports.

kind is "treatment_outcomes" when the abstract reports its own results for patients who received a treatment, of at least one of these:
- efficacy: response rates, CR, MRD negativity, PFS, OS, EFS, duration of response, transfusion independence, relapse, GVHD rates;
- safety: adverse event rates, CRS, ICANS, deaths, discontinuations.
This holds for any design: randomized or single-arm trials, dose escalation, a subgroup or longer follow-up of a trial, a pooled analysis of trials, and observational cohorts that report how treated patients did.
If the abstract has such results anywhere, it is "treatment_outcomes", even when most of it is about something else.
Exception: a substudy whose outcome numbers are only split by a marker, mutation or other lab finding (outcome by marker status), with no result for the treated group or arm as a whole, is "biomarker_or_translational".

Otherwise pick the kind that fits:
- trial_in_progress: a design or enrolment update with no results yet. Planned targets, sample-size assumptions and results of earlier studies quoted as background are not results.
- biomarker_or_translational: results are lab, genomic, imaging, pharmacokinetic or biomarker findings, or associations of a marker with outcome, with no efficacy or safety rate for a treated group.
- patient_reported_only: only quality of life or other patient-reported scores.
- review_or_meta_analysis: a systematic review or meta-analysis of published studies.
- case_report: one to three individual patients.
- other_no_outcomes: anything else without treatment results (methods, cost, epidemiology, prognostic models without treatment results).

evidence: for treatment_outcomes, the sentence with the first such result, copied exactly; else "".
reason: one short sentence.

ABSTRACT:
"""


def kept_rows(
    rows: list[dict[str, str]], triage: dict[str, Any]
) -> list[dict[str, str]]:
    """Selection rows whose abstract was classified as reporting treatment outcomes."""
    return [r for r in rows if triage.get(r["abstract"], {}).get("kind") == KEEP]


async def run(
    texts: dict[str, str],
    out_path: Path,
    llm: StructuredLLMService,
    concurrency: int,
) -> dict[str, Any]:
    results: dict[str, Any] = (
        json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    )
    todo = [n for n in texts if n not in results]
    print(f"{len(texts) - len(todo)} already done, {len(todo)} to run")
    sem = asyncio.Semaphore(concurrency)
    lock = asyncio.Lock()

    async def one(number: str) -> None:
        async with sem:
            t = await llm.generate_structured(
                prompt=PROMPT + texts[number],
                response_schema=Triage,
                temperature=0.0,
                max_tokens=1024,
                operation="ash_triage",
            )
        async with lock:
            results[number] = t.model_dump()
            tmp = out_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(results, indent=1), encoding="utf-8")
            os.replace(tmp, out_path)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    outcome = await asyncio.gather(*(one(n) for n in todo), return_exceptions=True)
    for number, err in zip(todo, outcome):
        if isinstance(err, Exception):
            print(f"{number}: failed ({err}); rerun to retry")
    return results


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--md", type=Path, required=True)
    p.add_argument("--selection", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--keep-csv", type=Path, required=True)
    p.add_argument("--concurrency", type=int, default=10)
    args = p.parse_args()

    logging.basicConfig(level=logging.WARNING)
    load_dotenv(_root / ".env")
    with args.selection.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        header, rows = reader.fieldnames or [], list(reader)
    all_texts = parse_md(args.md)
    missing = [r["abstract"] for r in rows if r["abstract"] not in all_texts]
    if missing:
        raise SystemExit(f"ids not in {args.md}: {missing[:10]}")
    texts = {r["abstract"]: all_texts[r["abstract"]] for r in rows}

    costs = CostCalculator(ModelType.DEEPSEEK_V41_FLASH)
    llm = OpenRouterStructuredService(
        ModelType.DEEPSEEK_V41_FLASH.value,
        costs,
        call_log_path=args.out.parent / "triage_calls.jsonl",
    )
    start = time.monotonic()

    async def _run_and_close() -> dict[str, Any]:
        try:
            return await run(texts, args.out, llm, args.concurrency)
        finally:
            await llm.aclose()

    results = asyncio.run(_run_and_close())
    keep = kept_rows(rows, results)
    with args.keep_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header, lineterminator="\n")
        w.writeheader()
        w.writerows(keep)
    kinds: dict[str, int] = {}
    for n in texts:
        k = results.get(n, {}).get("kind", "failed")
        kinds[k] = kinds.get(k, 0) + 1
    summary = costs.get_summary()
    print(f"kept {len(keep)} of {len(rows)}: {dict(sorted(kinds.items()))}")
    print(
        f"spend ${summary.total_cost:.4f} over {summary.total_requests} calls, "
        f"wall {time.monotonic() - start:.0f}s"
    )


if __name__ == "__main__":
    main()
