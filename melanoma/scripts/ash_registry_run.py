"""ASH test run, registry side: fill the registry-sourced fields from ClinicalTrials.gov.

Usage (from melanoma/):
  poetry run python3 scripts/ash_registry_run.py \\
      --arms data/ash_test_run/v2/results.json --out data/ash_test_run/registry/results.json

Takes each abstract's NCT ids and arm list from an abstract run (--arms), fetches the
registry records (cached next to --out), keeps only the records of the study the
abstract reports (an abstract can cite another trial's NCT id as background), and
asks one call per abstract for the workbook rows whose source is "registry", plus
the trial setting (line of therapy).
Values are written per abstract arm so they line up with the abstract run. Nothing
goes to Supabase.
"""

import argparse
import asyncio
import difflib
import hashlib
import json
import logging
import os
import re
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from pydantic import BaseModel

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
from ash_test_run import META, parse_md  # noqa: E402

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
    "Generic name (per component)": "Generic (INN) names of ALL the arm's treatment drugs and cell therapies from its interventions, joined with ' + '. Leave out supportive care (tocilizumab, G-CSF, antiemetics), pre-medication and treatment given before the trial. Not a brand name. A code name (ABC-123) only if the record gives no generic name. Drugs the record does not list stay out.",
    "Brand name": "Brand names of the arm's study drugs (the investigational drug and a named comparator drug) from the interventions' other names, joined with ' + '. Leave out conventional chemotherapy and supportive care. A code name (HE071, MT-103) or a descriptive name (liposomal mitoxantrone injection) is not a brand. Empty if none is listed.",
    "Route": "Route of each drug, in the order of the generic names, joined with ' + ' (oral + IV). Use IV, SC, oral or other, only where the record states it (intravenous, infusion, subcutaneous, by mouth, orally, capsule or tablet); '?' for a drug whose route is not stated. A drug given by two stated routes gets both (IV or SC).",
    "Fixed-duration vs continuous": "fixed duration: the record states a cap on the whole treatment (N cycles or courses, N months, a single dose or infusion). continuous: it says until progression or unacceptable toxicity, or ends in open-ended maintenance. A day schedule within a cycle or course (days 1-7) is not a cap. 'Until death, withdrawal or study end' is neither. Otherwise empty.",
    "Therapy phase": "Every phase the arm's protocol covers, in order, joined with ' + ', only where the record names the phase in words (induction, consolidation, maintenance, salvage, bridging, conditioning). 'Part 1' or 'course 1-8' names no phase.",
    "Mechanism of action": "How the experimental drug works, only in the record's own words. Never from the drug's name or class.",
    "Target": "Molecular target of each of the arm's drugs that the record states one for, joined with ' + ' (BTK + CD19 x CD3). Never from the drug's name.",
    "Modality": "Only from the record's own words (antibody, bispecific, ADC, CAR-T, small molecule, chemotherapy). 'Inhibitor', 'tablet' or a drug name alone does not state a modality.",
    "Drug class / sub-type": "Drug class of each of the arm's drugs as the record states it, joined with ' + ' (BTK inhibitor + anti-CD19 x anti-CD3 bispecific antibody).",
    "Transplant eligibility / fitness": "From the eligibility criteria, only when it holds for every enrolled patient: transplant-eligible / transplant-ineligible / fit / unfit. Empty if the trial admits both transplant candidates and non-candidates, or the criterion covers only some patients (only those with one prior line). 'Eligible for intensive chemotherapy' is 'fit', not transplant-eligible.",
    "Crossover allowed": "yes only if the record says patients may cross over to the other arm; no if it says crossover is not allowed; else empty.",
}
MULTI = {
    "Therapy phase",
    "Route",
}  # several values joined with ' + ': text, not an enum


# A 'fixed duration' quote must show a cap; a 'continuous' one an until-progression stop.
_CAP = re.compile(
    r"\d+\s*(?:or|-|to)?\s*\d*\s*(?:\w+\s){0,2}?(?:cycles?|courses?|months?|weeks?|years?|doses?|infusions?)\b"
    r"|\bcycles?\s+\d+\s*-\s*\d+|\b(?:single|one)\s+(?:\w+\s)?(?:dose|infusion|course)|\binfusion\b"
    r"|\bup to week\s+\d+"
    r"|\bday\s+-\d",  # pre-transplant conditioning days (day -5 to day -2) are one course
    re.I,
)
_UNTIL_PD = re.compile(r"progress|toxicit|\bPD\b|ongoing|indefinite", re.I)


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
    aliases = ", ".join(ident.get("nctIdAliases", []))  # merged duplicate registrations
    lines = [
        f"NCT: {ident.get('nctId', '')}"
        + (f" (also registered as {aliases})" if aliases else ""),
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


class RecordMatch(BaseModel):
    relation: Literal["this study", "another trial"]
    reason: str


MATCH_PROMPT = """TASK: Does this abstract report results (outcomes, safety or patient characteristics) of patients enrolled in the trial registered in the record below?

- "this study": yes. This includes a part, cohort or subgroup of the trial, a longer follow-up, a post hoc analysis, and a pooled or comparative analysis that includes this trial's patients, even alongside patients from elsewhere.
- "another trial": no. The abstract only mentions the trial, e.g. as background, as an earlier trial, or as the basis for its own, different study.

Compare the abstract's phase, design, drugs and population with the record's, and read how the abstract mentions the NCT id. reason: one sentence.

ABSTRACT:
{abstract}

REGISTRY RECORD:
{record}"""


async def own_studies(
    text: str, studies: list[dict[str, Any]], llm: OpenRouterStructuredService
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The records of the study the abstract reports, and every record's verdict."""
    verdicts = await asyncio.gather(
        *(
            llm.generate_structured(
                prompt=MATCH_PROMPT.format(abstract=text, record=record_text(s)),
                response_schema=RecordMatch,
                temperature=0.0,
                max_tokens=1024,
                operation="ash_registry_match",
            )
            for s in studies
        )
    )
    matches = [
        {
            "nct_id": s["protocolSection"]["identificationModule"]["nctId"],
            **v.model_dump(),
        }
        for s, v in zip(studies, verdicts, strict=True)
    ]
    own = [
        s for s, v in zip(studies, verdicts, strict=True) if v.relation == "this study"
    ]
    return own, matches


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


def _in_record(drug: str, words: set[str]) -> bool:
    """Every word of the drug name is in the record, allowing a near spelling (rituxumab)."""
    return all(
        w in words or difflib.get_close_matches(w, words, n=1, cutoff=0.85)
        for w in re.findall(r"[a-z0-9-]{4,}", drug.lower())
    )


def drop_unsupported(
    extracted: dict[str, Any], studies: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Remove what the record cannot back; return it. A generic name must appear in the
    record (its route goes with it); a duration needs its wording in the quote."""
    text = " ".join(record_text(s) for s in studies).lower()
    words = set(re.findall(r"[a-z0-9-]{4,}", text))
    dropped: list[dict[str, Any]] = []
    for arm_id, cells in extracted.get("arms", {}).items():
        dur = cells.get("fixed_duration_vs_continuous")
        if dur and dur["value"]:
            pattern = _CAP if dur["value"].startswith("fixed") else _UNTIL_PD
            if not pattern.search(dur["quote"]):
                dropped.append(
                    {"arm_id": arm_id, "key": "fixed_duration_vs_continuous", **dur}
                )
                cells["fixed_duration_vs_continuous"] = {
                    **dur,
                    "value": "",
                    "quote": "",
                }
        gen, route = cells.get("generic_name_per_component"), cells.get("route")
        if not gen or not gen["value"]:
            continue
        drugs = [d.strip() for d in gen["value"].split(" + ")]
        keep = [_in_record(d, words) for d in drugs]
        if all(keep):
            continue
        dropped.append({"arm_id": arm_id, "key": "generic_name_per_component", **gen})
        gen["value"] = " + ".join(d for d, k in zip(drugs, keep, strict=True) if k)
        if not gen["value"]:
            gen["quote"] = ""
        if route and route["value"]:
            routes = [r.strip() for r in route["value"].split(" + ")]
            dropped.append({"arm_id": arm_id, "key": "route", **route})
            if len(routes) == len(drugs):
                route["value"] = " + ".join(
                    r for r, k in zip(routes, keep, strict=True) if k
                )
            else:  # cannot tell which route belongs to which drug
                route["value"] = ""
            if not route["value"]:
                route["quote"] = ""
    return dropped


async def run_one(
    number: str,
    text: str,
    run: dict[str, Any],
    family: Family,
    llm: OpenRouterStructuredService,
    cache: Path,
    client: ClinicalTrialsGovAPIClient,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "nct_ids": run["nct_ids"],
        "arms": run["arms"],
        "missing": [],
        "error": None,
    }
    studies = []
    for nct in run["nct_ids"]:
        study = await asyncio.to_thread(fetch, nct, cache, client)
        (studies.append(study) if study else out["missing"].append(nct))
    arms = [Arm(**a) for a in run["arms"]]
    if not studies or not arms:
        out["error"] = "no registry record" if not studies else "no arms"
        return out
    try:
        studies, out["record_matches"] = await own_studies(text, studies, llm)
        if not studies:
            out["error"] = "no record of this study"
            return out
        records = [record_text(s) for s in studies]
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
    out["dropped"] = drop_unsupported(out["extracted"], studies)
    out["flags"] = flags(out["extracted"], "\n".join(records))
    return out


def fingerprint(family: Family) -> str:
    """Changes whenever this script's prompts or the registry fields do."""
    h = hashlib.sha256(repr(family).encode())
    h.update(Path(__file__).read_bytes())
    return h.hexdigest()[:16]


def done(prev: dict[str, Any] | None, run: dict[str, Any]) -> bool:
    """A finished abstract whose arms still match the abstract run is not redone."""
    return (
        prev is not None
        and prev.get("arms") == run["arms"]
        and prev["error"] in (None, "no arms")
    )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--arms", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--ids", help="comma-separated abstract numbers (default: all)")
    p.add_argument(
        "--md", type=Path, default=Path("data/postprocessed/ASH_Abstracts/ASH_2025.md")
    )
    args = p.parse_args()

    logging.basicConfig(level=logging.WARNING)
    load_dotenv(_root / ".env")
    runs = json.loads(args.arms.read_text(encoding="utf-8"))
    runs.pop(META, None)
    if args.ids:
        runs = {n: runs[n] for n in args.ids.split(",")}
    texts = parse_md(args.md)
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
    lock = asyncio.Lock()
    start = time.monotonic()
    results: dict[str, Any] = (
        json.loads(args.out.read_text(encoding="utf-8")) if args.out.exists() else {}
    )
    mark = fingerprint(family)
    if results and results.get(META, {}).get("fingerprint") != mark:
        raise SystemExit(
            f"{args.out} was written with different prompts or fields; "
            "use a new --out or delete it"
        )
    results[META] = {"fingerprint": mark}
    todo = [n for n in runs if not done(results.get(n), runs[n])]
    print(f"{len(runs) - len(todo)} already done, {len(todo)} to run")

    async def go() -> None:
        async def one(n: str) -> None:
            async with sem:
                r = await run_one(n, texts[n], runs[n], family, llm, cache, client)
            async with lock:
                results[n] = r
                tmp = args.out.with_suffix(".tmp")
                tmp.write_text(json.dumps(results, indent=1), encoding="utf-8")
                os.replace(tmp, args.out)
            print(
                f"{n}: {r['error'] or 'ok'}"
                + (f" missing {r['missing']}" if r["missing"] else "")
                + f" (spend ${costs.get_summary().total_cost:.2f})"
            )

        try:
            await asyncio.gather(*(one(n) for n in todo))
        finally:
            await llm.aclose()

    asyncio.run(go())
    s = costs.get_summary()
    print(
        f"wrote {args.out}: spend ${s.total_cost:.4f} over {s.total_requests} calls, "
        f"wall {time.monotonic() - start:.0f}s"
    )


if __name__ == "__main__":
    main()
