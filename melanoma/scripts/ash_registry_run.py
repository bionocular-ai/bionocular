"""ASH test run, registry side: fill the registry-sourced fields from ClinicalTrials.gov.

Usage (from melanoma/):
  poetry run python3 scripts/ash_registry_run.py \\
      --arms data/ash_test_run/v2/results.json --out data/ash_test_run/registry/results.json

Takes each abstract's NCT ids and arm list from an abstract run (--arms), fetches the
registry records (cached next to --out), and asks one call per abstract for the
workbook rows whose source is "registry", plus the trial setting (line of therapy).
Values are written per abstract arm so they line up with the abstract run. Nothing
goes to Supabase.
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(Path(__file__).parent))

from ash_checks import quote_found  # noqa: E402
from ash_fields import (  # noqa: E402
    Arm,
    Family,
    SheetField,
    _arms_block,
    _fields_block,
    load_families,
    response_model,
)
from ash_test_run import META  # noqa: E402

from src.infrastructure.clinical_trials.api_client import (  # noqa: E402
    ClinicalTrialsGovAPIClient,
)
from src.infrastructure.cost_calculator import CostCalculator, ModelType  # noqa: E402
from src.infrastructure.openrouter_structured_service import (  # noqa: E402
    OpenRouterStructuredService,
)

logger = logging.getLogger(__name__)

# Draft heme setting values: not yet signed off by an expert.
SETTING_VALUES = (
    "newly diagnosed",
    "relapsed/refractory",
    "maintenance",
    "consolidation",
    "precursor (smoldering / high-risk)",
    "post-transplant",
)
SETTING = SheetField(
    key="setting",
    name="Setting (line of therapy)",
    family="registry",
    scope="trial",
    source="registry",
    value_type="text",
    allowed=(),
    detail="the prior-lines requirement as stated, e.g. '>=3 prior lines', else ''",
    evidence="stated only",
    applies_to="All",
    definition=(
        "Disease setting the trial enrols, from the inclusion criteria first, then the "
        "title and summary. One or more of: "
        + " / ".join(SETTING_VALUES)
        + ", joined with ' + '. Transplant eligibility is its own field."
    ),
)
# The workbook definitions of these rows were written for the abstract.
REGISTRY_DEFS = {
    "Generic name (per component)": "Generic (INN) names of ALL the arm's drugs and cell therapies from its interventions, joined with ' + '. Not a brand name. A code name (ABC-123) only if the record gives no generic name. Drugs the record does not list stay out.",
    "Brand name": "Brand names from the interventions' other names, joined with ' + '. Empty if none is listed.",
    "Route": "Route of each drug, in the order of the generic names, joined with ' + ' (oral + IV). Use IV, SC, oral or other, only where the record states it (intravenous, infusion, subcutaneous, by mouth, orally, capsule or tablet); '?' for a drug whose route is not stated.",
    "Fixed-duration vs continuous": "fixed duration: the record states a cap on the whole treatment (N cycles or courses, N months, a single dose or infusion). continuous: it says until progression or unacceptable toxicity, or ends in open-ended maintenance. A day schedule within a cycle or course (days 1-7) is not a cap. 'Until death, withdrawal or study end' is neither. Otherwise empty.",
    "Therapy phase": "Every phase the arm's protocol covers, in order, joined with ' + ', only where the record names the phase in words (induction, consolidation, maintenance, salvage, bridging, conditioning). 'Part 1' or 'course 1-8' names no phase.",
    "Mechanism of action": "How the experimental drug works, only in the record's own words. Never from the drug's name or class.",
    "Target": "Molecular target as the record states it, e.g. BCMA, CD20xCD3, BTK, BCL2.",
    "Modality": "Only from the record's own words (antibody, bispecific, ADC, CAR-T, small molecule, chemotherapy). 'Inhibitor', 'tablet' or a drug name alone does not state a modality.",
    "Drug class / sub-type": "Drug class as the record states it, e.g. covalent BTK inhibitor, anti-CD38 antibody.",
    "Transplant eligibility / fitness": "From the eligibility criteria: transplant-eligible / transplant-ineligible / fit / unfit. 'Eligible for intensive chemotherapy' is 'fit', not transplant-eligible.",
    "Crossover allowed": "yes only if the record says patients may cross over to the other arm; no if it says crossover is not allowed; else empty.",
}
MULTI = {
    "Therapy phase",
    "Route",
}  # several values joined with ' + ': text, not an enum


def registry_family(csv_path: Path) -> Family:
    rows = [f for fam in load_families(csv_path, ("registry",)) for f in fam.fields]
    fields = [
        replace(
            f,
            definition=REGISTRY_DEFS[f.name],
            evidence="",  # the block's "stated only" hint names the abstract
            allowed=() if f.name in MULTI else f.allowed,
            value_type="text" if f.name in MULTI else f.value_type,
        )
        for f in rows
    ]
    return Family("registry", "Registry fields", (*fields, SETTING))


def record_text(study: dict[str, Any]) -> str:
    """The parts of a ClinicalTrials.gov v2 record the fields can come from."""
    p = study.get("protocolSection", {})
    ident, desc = p.get("identificationModule", {}), p.get("descriptionModule", {})
    design, arms = p.get("designModule", {}), p.get("armsInterventionsModule", {})
    elig = p.get("eligibilityModule", {})
    lines = [
        f"NCT: {ident.get('nctId', '')}",
        f"Title: {ident.get('officialTitle') or ident.get('briefTitle', '')}",
        f"Acronym: {ident.get('acronym', '')}",
        f"Conditions: {', '.join(p.get('conditionsModule', {}).get('conditions', []))}",
        f"Phases: {', '.join(design.get('phases', []))}",
        f"Design: {json.dumps(design.get('designInfo', {}))}",
        f"Brief summary: {desc.get('briefSummary', '')}",
        f"Detailed description: {desc.get('detailedDescription', '')[:4000]}",
        "Arm groups:",
        *(
            f"- {a.get('label', '')} [{a.get('type', '')}]: {a.get('description', '')} "
            f"(interventions: {', '.join(a.get('interventionNames', []))})"
            for a in arms.get("armGroups", [])
        ),
        "Interventions:",
        *(
            f"- {i.get('type', '')}: {i.get('name', '')}; other names: "
            f"{', '.join(i.get('otherNames', []))}; {i.get('description', '')}"
            for i in arms.get("interventions", [])
        ),
        f"Eligibility criteria:\n{elig.get('eligibilityCriteria', '')}",
    ]
    return "\n".join(lines)


_RULES = """RULES
1. Use only the registry record(s) below. If they do not state a field for an arm, return "" for value and quote. Never use what you know about the drug.
2. quote: copy the exact words from the record that state the value.
3. The ARMS are the abstract's arms. Match each to the record's arm groups and interventions by drug names. A registry arm group that matches no abstract arm is ignored. With several records, use the one whose arms match the abstract's arms; take a value from another record only for the same drug and the same use.
4. detail: what the field's detail asks for, else "".
5. A drug shared by several arms gets its values on each of those arms. derived is true only if you had to combine or convert.
6. extra: a second value for the same field and arm (another phase, another drug's route), with context."""


def prompt(family: Family, arms: list[Arm], records: list[str]) -> str:
    return "\n\n".join(
        [
            "TASK: Fill the fields below for each arm from the ClinicalTrials.gov "
            "record(s) of this trial. Trial-level fields go under 'trial' once.",
            _RULES,
            "FIELDS\n" + _fields_block(family),
            "ARMS\n" + _arms_block(arms),
            *(f"REGISTRY RECORD\n{r}" for r in records),
        ]
    )


def fetch(nct: str, cache: Path, client: ClinicalTrialsGovAPIClient) -> dict | None:
    path = cache / f"{nct}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    study = client.fetch_trial_data(nct)
    if study:
        path.write_text(json.dumps(study), encoding="utf-8")
    return study


def flags(extracted: dict[str, Any], text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    scopes = [("trial", extracted.get("trial", {})), *extracted["arms"].items()]
    for arm_id, cells in scopes:
        for key, cell in cells.items():
            if key == "extra" or not cell["value"]:
                continue
            got = []
            if not quote_found(cell["quote"], text):
                got.append("quote_not_in_record")
            if key == "setting" and any(
                v.strip() not in SETTING_VALUES for v in cell["value"].split(" + ")
            ):
                got.append("setting_not_in_list")
            if got:
                out[f"{arm_id}.{key}"] = got
    return out


async def run_one(
    number: str,
    run: dict[str, Any],
    family: Family,
    llm: OpenRouterStructuredService,
    cache: Path,
    client: ClinicalTrialsGovAPIClient,
) -> dict[str, Any]:
    out: dict[str, Any] = {"nct_ids": run["nct_ids"], "missing": [], "error": None}
    studies = []
    for nct in run["nct_ids"]:
        study = await asyncio.to_thread(fetch, nct, cache, client)
        (studies.append(study) if study else out["missing"].append(nct))
    arms = [Arm(a["arm_id"], a["arm_name"], a["role"]) for a in run["arms"]]
    if not studies or not arms:
        out["error"] = "no registry record" if not studies else "no arms"
        return out
    records = [record_text(s) for s in studies]
    try:
        got = await llm.generate_structured(
            prompt=prompt(family, arms, records),
            response_schema=response_model(family, arms, pooled_list=False),
            temperature=0.0,
            max_tokens=16384,
            operation="ash_registry",
        )
    except Exception as e:  # recorded so the other abstracts still finish
        logger.error("abstract %s failed: %s", number, e)
        out["error"] = f"{type(e).__name__}: {e}"
        return out
    out["extracted"] = got.model_dump()
    out["flags"] = flags(out["extracted"], "\n".join(records))
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--arms", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--ids", help="comma-separated abstract numbers (default: all)")
    args = p.parse_args()

    logging.basicConfig(level=logging.WARNING)
    load_dotenv(_root / ".env")
    runs = json.loads(args.arms.read_text(encoding="utf-8"))
    runs.pop(META, None)
    if args.ids:
        runs = {n: runs[n] for n in args.ids.split(",")}
    family = registry_family(_root / "resources" / "ash" / "book1_sheet2.csv")
    cache = args.out.parent / "records"
    cache.mkdir(parents=True, exist_ok=True)
    costs = CostCalculator(ModelType.DEEPSEEK_V41_FLASH)
    llm = OpenRouterStructuredService(
        ModelType.DEEPSEEK_V41_FLASH.value,
        costs,
        call_log_path=args.out.parent / "calls.jsonl",
    )
    client = ClinicalTrialsGovAPIClient()
    sem = asyncio.Semaphore(5)
    start = time.monotonic()

    async def go() -> dict[str, Any]:
        async def one(n: str) -> tuple[str, dict[str, Any]]:
            async with sem:
                r = await run_one(n, runs[n], family, llm, cache, client)
            print(
                f"{n}: {r['error'] or 'ok'}"
                + (f" missing {r['missing']}" if r["missing"] else "")
            )
            return n, r

        try:
            return dict(await asyncio.gather(*(one(n) for n in runs)))
        finally:
            await llm.aclose()

    results = asyncio.run(go())
    args.out.write_text(json.dumps(results, indent=1), encoding="utf-8")
    s = costs.get_summary()
    print(
        f"wrote {args.out}: spend ${s.total_cost:.4f} over {s.total_requests} calls, "
        f"wall {time.monotonic() - start:.0f}s"
    )


if __name__ == "__main__":
    main()
