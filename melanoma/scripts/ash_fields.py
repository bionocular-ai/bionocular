"""ASH test run: workbook fields, family split, response schemas and prompts.

Fields are data (resources/ash/book1_sheet2.csv), not AttributeType members.
One extraction call per family; the harness appends the abstract text to the
prompts built here.
"""

import csv
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, create_model

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.domain.prompt_templates import SHARED_EXTRACTION_RULES  # noqa: E402
from src.domain.treatment_arm_models import TreatmentArm  # noqa: E402

RESOURCES = Path(__file__).parent.parent / "resources" / "ash"
DROPPED = {"Cytokine Release Syndrome or CRS"}  # duplicate of "CRS any grade"
TEXT_ONLY_NAMES = (
    "mechanism of action",
    "target",
    "modality",
    "drug class",
    "generic name",
    "brand name",
    "disease subtype",
)
TRIAL_LEVEL_NAMES = ("trial name", "nct", "disease subtype")


@dataclass(frozen=True)
class SheetField:
    key: str
    name: str
    type: str
    applies_to: str
    definition: str
    text_only: bool
    trial_level: bool


@dataclass(frozen=True)
class Family:
    key: str
    title: str
    fields: tuple[SheetField, ...]


# Ordered: the first pattern matching the lowercased field name wins.
_FAMILY_RULES: tuple[tuple[str, str, str], ...] = (
    (
        "dose_events_special",
        "Dose changes, DLT and CRS/ICANS",
        r"dose reduction|dose interruption|hospitali|^crs|^icans|^dlt|^mtd|^rp2d",
    ),
    (
        "safety_overall",
        "Overall safety",
        r"^grade >=3|^serious|^discontinuation|^deaths|mortality|immune related|infusion-related",
    ),
    (
        "survival_other",
        "EFS, RFS, DFS and LFS",
        r"\b(efs|rfs|dfs|lfs)\b",
    ),
    (
        "duration_transplant",
        "Response duration, time-to-event and transplant outcomes",
        r"^median (dor|time to|ttp|ttnt)|^dor rate|duration of complete|^pfs2"
        r"|gvhd|non-relapse|cumulative incidence",
    ),
    ("survival_pfs_os", "PFS and OS", r"\b(pfs|os)\b"),
    (
        "response_rates",
        "Response and disease-specific rates",
        r"\borr\b|cr rate|^cbr|pod24|vgpr|^scr|cr/crh|composite cr|mlfs|mrd|bridge to"
        r"|transfusion independence|hematologic improvement|^mmr|^mr4|svr35|tss50"
        r"|major response|hematologic cr",
    ),
    (
        "population",
        "Population and study design",
        r"response criteria|assessment by|disease subtype|line of therapy|transplant elig"
        r"|median age|^patients |crossover|biomarker",
    ),
    (
        "regimen_drug",
        "Regimen and drug profile",
        r"arm label|regimen name|component|generic|brand|^dose$|route|dosing schedule"
        r"|step-up|fixed-duration|therapy phase|mechanism|^target|modality|drug class"
        r"|cell therapy|lymphodepletion|bridging therapy",
    ),
)


def _slug(name: str) -> str:
    s = name.lower().replace(">=", "ge").replace("%", "pct")
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s if s[0].isalpha() else "f_" + s


def load_families(csv_path: Path) -> tuple[Family, ...]:
    buckets: dict[str, list[SheetField]] = {k: [] for k, _, _ in _FAMILY_RULES}
    with csv_path.open(newline="") as f:
        for row in csv.DictReader(f):
            name = row["field"]
            if name in DROPPED:
                continue
            low = name.lower()
            sheet_field = SheetField(
                key=_slug(name),
                name=name,
                type=row["type"],
                applies_to=row["applies_to"],
                definition=row["definition"],
                text_only=low.startswith(TEXT_ONLY_NAMES),
                trial_level=low.startswith(TRIAL_LEVEL_NAMES),
            )
            for key, _, pattern in _FAMILY_RULES:
                if re.search(pattern, low):
                    buckets[key].append(sheet_field)
                    break
            else:
                raise ValueError(f"No family for workbook field: {name}")
    return tuple(
        Family(key, title, tuple(buckets[key])) for key, title, _ in _FAMILY_RULES
    )


class Cell(BaseModel):
    value: str
    quote: str


class JudgeItem(BaseModel):
    arm_id: str
    key: str
    verdict: Literal["pass", "fail", "uncertain"]
    note: str
    corrected_value: str


class JudgeVerdict(BaseModel):
    items: list[JudgeItem]


def response_model(family: Family, arm_ids: list[str]) -> type[BaseModel]:
    """{"trial"?: {key: Cell}, "arms": {arm_id: {key: Cell, "other_values": str}}}."""
    arm_fields = {f.key: (Cell, ...) for f in family.fields if not f.trial_level}
    arm_fields["other_values"] = (str, ...)
    arm_model = create_model(f"{family.key}_arm", **arm_fields)
    arms_model = create_model(
        f"{family.key}_arms", **{a: (arm_model, ...) for a in arm_ids}
    )
    top = {"arms": (arms_model, ...)}
    trial_fields = {f.key: (Cell, ...) for f in family.fields if f.trial_level}
    if trial_fields:
        top = {
            "trial": (create_model(f"{family.key}_trial", **trial_fields), ...),
            **top,
        }
    return create_model(f"{family.key}_response", **top)


def _fields_block(family: Family) -> str:
    return "\n".join(
        f"- {f.key} ({f.name}); type: {f.type}; definition: {f.definition or 'none given'}"
        for f in family.fields
    )


def family_prompt(family: Family, arms: list[TreatmentArm]) -> str:
    trial = [f.key for f in family.fields if f.trial_level]
    text_only = [f.key for f in family.fields if f.text_only]
    parts = [
        f"TASK: Extract the following fields ({family.title}) from the abstract, "
        "once for each treatment arm listed below.",
        SHARED_EXTRACTION_RULES,
        "Fields:\n" + _fields_block(family),
        "Arms:\n" + "\n".join(f"{a.arm_id}: {a.arm_name}" for a in arms),
        "Each field returns {value, quote}. quote is the exact verbatim substring of the "
        "abstract that supports the value; copy it character for character. If the "
        "abstract does not state the field for that arm, return empty strings for both.",
        "other_values (one per arm): a short text naming each further value the abstract "
        "reports for this family's fields that one value per field cannot hold, such as "
        "another population, criterion, threshold, dose level or timepoint. Name the field "
        "and the context. Empty string if there is none.",
        "If the abstract gives a second value for the same field in one arm (for example "
        "ORR in the ITT population and in evaluable patients), keep the primary value in "
        "the field and put the second value in other_values; never drop it.",
    ]
    if trial:
        parts.append(
            "Trial-level fields ("
            + ", ".join(trial)
            + ") go under 'trial' once, not per arm."
        )
    if text_only:
        parts.append(
            "Text-only fields (" + ", ".join(text_only) + ") are filled only when the "
            "abstract text states them. Never fill them from your own knowledge of the drug "
            "or disease; if the abstract does not say it, return empty strings."
        )
    return "\n\n".join(parts)


def judge_prompt(family: Family, extracted: dict) -> str:
    return "\n\n".join(
        [
            f"TASK: You are auditing an extraction ({family.title}) against the abstract "
            "text. For every arm and field in the extraction, return a verdict: pass if "
            "value and quote are supported by the abstract and the quote is verbatim; fail "
            "if wrong, unsupported or attributed to the wrong arm; uncertain if the "
            "abstract is ambiguous. Give a short note, and corrected_value when you fail "
            "a field (empty string otherwise). Also check other_values: a value that "
            "belongs to a field but was dropped, or one wrongly placed there, is a fail "
            "for that field. Text-only fields must be stated in the abstract text, never "
            "supplied from model knowledge; fail any that are not. Use arm_id 'trial' for "
            "trial-level fields.",
            "Fields:\n" + _fields_block(family),
            "Extraction:\n" + json.dumps(extracted, indent=2),
        ]
    )


HEME_SEPARATION_PROMPT = """
TASK: Identify the treatment arms in this hematology clinical trial abstract.

Treatment arms are usually defined in the Title and in Methods / Patients and Methods / Study Design. Look there first; confirm against Results.

RULES:
1. An arm is a distinct regimen or comparison group. Most trials have 1-3; multi-regimen trials may have more.
2. Treatment and control groups are arms. Different regimens are different arms: "LINVO + DARA" and "LINVO + ISA" are two arms even in one phase 1/2 study.
3. Combination = single arm with "+" notation (e.g., "Venetoclax + Azacitidine").
4. Placebo / control / observation / best available therapy / transplant-only groups ARE arms. Use arm_type="placebo" or "control".
5. A single-arm study has one arm.
6. NOT arms - do NOT emit these as separate arms (their results go in the arm they belong to):
   - Dose levels or dose-escalation cohorts of one regimen (e.g., 5 mg vs 10 mg of the same combination)
   - Cohorts within one regimen (expansion cohorts, step-up dosing cohorts)
   - Subgroups (cytogenetic risk, age, line of therapy, prior treatment, response status, biomarker status)
   - Phases of one regimen (induction, consolidation, maintenance given to the same patients)
7. If the abstract uses cohort labels (e.g., "Cohort A"), append the regimen: "Cohort A (Teclistamab + Daratumumab)".
8. Prefer drug names over generic labels like "Arm 1", "Treatment arm".
9. Do not use outside knowledge to name a regimen; use only what the abstract states.

FIELDS:
- arm_id: "arm_1", "arm_2", ... (sequential)
- arm_name: drug or regimen name(s) as referred to in the text
- generic_name: generic names of the DEFINING drugs of this arm, "+" joined; "Placebo" / "Control" for non-drug arms
- combination_drugs: list of individual drugs for combination arms; [] for monotherapy/placebo/non-drug
- arm_type: one of [monotherapy, combination, placebo, control, dose_variation, unknown]
- line_of_treatment: one of [first_line, second_line, third_line_plus, adjuvant, neoadjuvant, maintenance, unknown]
- dose: dose with units as stated, "Drug dose + Drug dose" for combinations; null if not stated
- dosing_schedule: schedule using standard abbreviations (QD, BID, QW, Q2W, Q3W, Q4W; "Q3W x4"); null if not stated
- patient_count: integer N for this arm if explicitly stated, else 0
- nct_number: NCT identifier if found, else ""
- source_text: the verbatim sentence from the abstract that defines this arm
- confidence_score: 1.0 arm explicitly named in the design; 0.7 clearly inferable from Methods + Results; 0.4 uncertain

OUTPUT FORMAT (JSON ONLY - no markdown, no explanations):
{
  "treatment_arms": [
    {
      "arm_id": "arm_1",
      "arm_name": "Linvoseltamab + Daratumumab",
      "generic_name": "Linvoseltamab + Daratumumab",
      "combination_drugs": ["Linvoseltamab", "Daratumumab"],
      "arm_type": "combination",
      "line_of_treatment": "second_line",
      "dose": "Linvoseltamab 200 mg + Daratumumab 1800 mg",
      "dosing_schedule": "Q4W",
      "patient_count": 42,
      "nct_number": "NCT00000000",
      "source_text": "...patients received linvoseltamab plus daratumumab...",
      "confidence_score": 1.0
    }
  ]
}

ABSTRACT:
{abstract_text}
"""

INDICATIONS: tuple[str, ...]
_INCLUDES: dict[str, str]
with (RESOURCES / "indications.csv").open(newline="") as _f:
    _rows = list(csv.DictReader(_f))
INDICATIONS = tuple(r["indication"] for r in _rows)
_INCLUDES = {r["indication"]: r["includes"] for r in _rows}

_LYMPHOMAS = {
    "DLBCL",
    "Follicular lymphoma",
    "Mantle cell lymphoma",
    "Marginal zone lymphoma",
    "Hodgkin lymphoma",
    "T-cell lymphoma",
}
# Workbook abbreviations and groups that are not a word in any indication name.
_ALIASES = {
    "mm": {"Multiple myeloma"},
    "wm": {"Waldenström"},
    "lymphoma": _LYMPHOMAS,
    "allo-hct": {"Allo-HCT / GVHD"},
}
# Design or phase scopes, not diseases: they apply to every indication.
_SCOPES = ("bispecific", "car-t", "cell therapy", "randomized", "phase 1", "relapsed")


def applies(field: SheetField, indication: str) -> bool:
    scope = re.sub(r"\([^)]*\)", "", field.applies_to).strip()
    if not scope or scope.lower() == "all":
        return True
    for raw in (i.strip() for i in scope.split(",")):
        item = raw.lower()
        if item in _ALIASES:
            if indication in _ALIASES[item]:
                return True
        elif any(s in item for s in _SCOPES):
            return True
        else:
            hay = f"{indication} {re.sub(r'[(][^)]*[)]', '', _INCLUDES.get(indication, ''))}"
            # Acronyms (ALL) match case-sensitively so prose "all" cannot hit them.
            pat = rf"(?<![\w-]){re.escape(raw)}(?![\w-])"
            if re.search(pat, hay) if raw.isupper() else re.search(pat, hay, re.I):
                return True
    return False
