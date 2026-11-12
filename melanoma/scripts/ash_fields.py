"""ASH test run: workbook fields, response schemas, prompts.

Fields are data (resources/ash/book1_sheet2.csv, a copy of the workbook's Sheet2).
Each row carries its family, scope (arm / comparison / trial), source, value type,
allowed values and evidence rule. Only rows whose source is the abstract are asked
here; registry rows are filled from ClinicalTrials.gov elsewhere.
One extraction call per family; the harness appends the abstract text.
"""

import csv
import re
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, create_model

sys.path.insert(0, str(Path(__file__).parent.parent))

RESOURCES = Path(__file__).parent.parent / "resources" / "ash"
ABSTRACT_SOURCES = ("abstract", "both")
FAMILY_TITLES = {
    "dose_events_special": "Dose changes, DLT and CRS/ICANS",
    "safety_overall": "Overall safety",
    "survival_other": "EFS, RFS, DFS and LFS",
    "duration_transplant": "Response duration, time-to-event and transplant outcomes",
    "survival_pfs_os": "PFS and OS",
    "response_rates": "Response and disease-specific rates",
    "population": "Population and study design",
    "regimen_drug": "Regimen and drug profile",
}
TYPE_TEXT = {
    "percent": "percent, bare number 0-100",
    "months": "months, bare number",
    "months_or_nr": "months, bare number, or NR if not reached",
    "count": "whole number",
    "number": "bare number",
    "range": "low-high, e.g. 0.41-0.74",
    "p_value": "<, = or > then the number, e.g. <0.001",
    "dose": "dose with its unit",
    "text": "short text",
}


@dataclass(frozen=True)
class SheetField:
    key: str
    name: str
    family: str
    scope: str  # arm | comparison | trial
    source: str
    value_type: str
    allowed: tuple[str, ...]
    detail: str
    evidence: str
    applies_to: str
    definition: str

    @property
    def trial_level(self) -> bool:
        return self.scope == "trial"


@dataclass(frozen=True)
class Family:
    key: str
    title: str
    fields: tuple[SheetField, ...]


@dataclass(frozen=True)
class Arm:
    arm_id: str
    arm_name: str
    role: str  # experimental | control | single arm


def _slug(name: str) -> str:
    s = name.lower().replace(">=", "ge").replace("%", "pct")
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s if s[0].isalpha() else "f_" + s


def load_families(csv_path: Path) -> tuple[Family, ...]:
    """Fields asked of the abstract, grouped by the workbook's family column."""
    buckets: dict[str, list[SheetField]] = {k: [] for k in FAMILY_TITLES}
    with csv_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["source"] not in ABSTRACT_SOURCES:
                continue
            if row["family"] not in buckets:
                raise ValueError(f"No family for workbook field: {row['field']}")
            allowed = (
                tuple(v.strip() for v in row["allowed_values"].split(" / ") if v)
                if row["value_type"] in ("enum", "yes_no")
                else ()
            )
            buckets[row["family"]].append(
                SheetField(
                    key=_slug(row["field"]),
                    name=row["field"],
                    family=row["family"],
                    scope=row["scope"],
                    source=row["source"],
                    value_type=row["value_type"],
                    allowed=allowed,
                    detail=row["detail"],
                    evidence=row["evidence"],
                    applies_to=row["applies_to"],
                    definition=row["definition"],
                )
            )
    return tuple(Family(k, t, tuple(buckets[k])) for k, t in FAMILY_TITLES.items())


def fields_for(family: Family, indication: str | None) -> Family:
    """The family narrowed to the fields that apply to this indication (all if unknown)."""
    if indication is None:
        return family
    return replace(
        family, fields=tuple(f for f in family.fields if applies(f, indication))
    )


def arm_fields(family: Family, arm: Arm) -> list[SheetField]:
    """Comparison fields (hazard ratio, CI, p-value) exist on the experimental arm only."""
    return [
        f
        for f in family.fields
        if f.scope == "arm" or (f.scope == "comparison" and arm.role == "experimental")
    ]


class Cell(BaseModel):
    value: str
    quote: str
    detail: str
    basis: Literal["", "arm", "pooled"]
    derived: bool


class ArmItem(BaseModel):
    arm_name: str
    role: Literal["experimental", "control", "single arm"]
    n: str
    source_text: str


class ArmList(BaseModel):
    results_reported: Literal["per_arm", "pooled_only", "mixed"]
    arms: list[ArmItem]


class JudgeItem(BaseModel):
    id: int
    value_ok: Literal["yes", "no", "unsure"]
    quote_ok: Literal["yes", "no"]
    error: Literal[
        "",
        "not_stated",
        "wrong_measure",
        "wrong_arm_or_group",
        "wrong_analysis",
        "wrong_number",
        "outside_knowledge",
    ]
    right_value: str
    right_quote: str


class JudgeVerdict(BaseModel):
    items: list[JudgeItem]


def _cell_type(family: Family, f: SheetField) -> Any:
    if not f.allowed:
        return Cell
    # Any: Literal built from workbook data
    values: Any = Literal[(*f.allowed, "")]  # type: ignore[valid-type]
    return create_model(
        f"{family.key}_{f.key}_cell", __base__=Cell, value=(values, ...)
    )


def _keys_literal(fields: list[SheetField]) -> Any:
    return Literal[tuple(f.key for f in fields)]  # type: ignore[valid-type]


def response_model(family: Family, arms: list[Arm]) -> type[BaseModel]:
    """{"trial"?: {key: Cell}, "arms"?: {arm_id: {key: Cell, "extra": [Extra]}}}."""
    top: dict[str, Any] = {}
    trial: dict[str, Any] = {
        f.key: (_cell_type(family, f), ...) for f in family.fields if f.trial_level
    }
    if trial:
        top["trial"] = (create_model(f"{family.key}_trial", **trial), ...)
    arm_models: dict[str, Any] = {}
    for arm in arms:
        fields = arm_fields(family, arm)
        if not fields:
            continue
        extra = create_model(
            f"{family.key}_{arm.arm_id}_extra",
            field=(_keys_literal(fields), ...),
            value=(str, ...),
            context=(str, ...),
            quote=(str, ...),
        )
        defs: dict[str, Any] = {f.key: (_cell_type(family, f), ...) for f in fields}
        defs["extra"] = (list[extra], ...)  # type: ignore[valid-type]
        arm_models[arm.arm_id] = (
            create_model(f"{family.key}_{arm.arm_id}", **defs),
            ...,
        )
    if arm_models:
        top["arms"] = (create_model(f"{family.key}_arms", **arm_models), ...)
    if not top:
        raise ValueError(f"family {family.key} has no fields to ask")
    return create_model(f"{family.key}_response", **top)


def missed_model(family: Family, arms: list[Arm]) -> type[BaseModel]:
    ids: Any = Literal[(*(a.arm_id for a in arms), "trial")]  # type: ignore[valid-type]
    item = create_model(
        f"{family.key}_missed_item",
        arm_id=(ids, ...),
        field=(_keys_literal(list(family.fields)), ...),
        value=(str, ...),
        quote=(str, ...),
    )
    return create_model(f"{family.key}_missed", items=(list[item], ...))  # type: ignore[valid-type]


def _fields_block(family: Family) -> str:
    lines = []
    for f in family.fields:
        kind = (
            "one of: " + " / ".join(f.allowed) if f.allowed else TYPE_TEXT[f.value_type]
        )
        line = f"- {f.key} ({f.name}); {kind}"
        if f.detail:
            line += f"; detail: {f.detail}"
        line += f"; {f.definition}" if f.definition else ""
        if f.evidence == "stated only":
            line += " Fill only if the abstract says it in words."
        lines.append(line)
    return "\n".join(lines)


def _arms_block(arms: list[Arm]) -> str:
    return "\n".join(f"{a.arm_id}: {a.arm_name} ({a.role})" for a in arms)


ARM_PROMPT = """TASK: List the treatment arms in this hematology trial abstract.

An arm is a group of patients that receives a regimen different from the other groups.

ARE arms:
1. Each randomized group, including placebo, control, observation and standard of care.
2. Groups that get different drugs, even in one study: "DrugA + DrugB" and "DrugA + DrugC" are two arms, also when the abstract reports their results pooled.
3. Risk-stratified groups that get different regimens (standard-risk gets X, high-risk gets X + Y).
4. A single-arm study has exactly one arm.

Are NOT arms (never list them):
5. Dose levels or dose-escalation cohorts of the same drugs (DL1, DL2, 100 mg vs 200 mg).
6. Expansion cohorts, step-up cohorts, outpatient subsets of the same drugs.
7. Subgroups by age, risk, mutation, prior therapy, response.
8. Phases given to the same patients (induction, consolidation, maintenance).

If two groups get the same drugs, they are ONE arm.

For each arm:
- arm_name: the drugs or regimen as the abstract names them. No outside knowledge.
- role: experimental, control, or single arm.
- n: patients in this arm if stated, else "".
- source_text: the sentence that defines the arm, copied exactly.

results_reported: "pooled_only" if the abstract says results combine the arms and gives no per-arm outcomes; "per_arm" if outcomes are given per arm; "mixed" otherwise.

ABSTRACT:
{abstract_text}
"""

_RULES = """RULES
1. Use only what the abstract says. If it does not state a field for an arm, return "" for value and quote. Never use what you know about the drug or disease.
2. quote: copy the exact words from the abstract that state the value. The quote must name the measure (for a PFS field the quote contains "PFS" or "progression-free").
3. value: numbers only, no units, no "%". Durations in months ("NR" if not reached). If you had to calculate it (count to percent, days to months, "all patients" = 100, "none" = 0), set derived = true.
4. detail: the timepoint, method, threshold or grading system the field asks for, else "".
5. basis: "arm" if the value is for this arm only. "pooled" if the abstract gives it for all arms together. A pooled value goes on every arm with basis "pooled". Patient counts are the exception: a trial total never goes on an arm.
6. Extract the analysis this abstract reports. Ignore results from an earlier analysis that the abstract quotes as background ("in the primary analysis", "previously reported").
7. One measure, one field. Never put EFS in a PFS field, a CR rate in ORR, or an MRD rate in a response field. If no field fits, leave it out.
8. extra: further values of THESE fields that the field cannot hold: a subgroup, a dose level, a second population (evaluable vs ITT), another timepoint, a second analysis. Give field, value, context (who or when), and quote. Never drop a second value; never put a first value here."""

_EXAMPLES = """EXAMPLE 1 (invented)
Text: "In the primary analysis (median follow-up 18 months) PFS HR was 0.60 (P<0.001). Here we report the final analysis. At a median follow-up of 40 months, median PFS was 30.1 months with zorvamab vs 14.2 months with placebo (HR 0.55; 95% CI 0.41-0.74). In patients aged >=75, median PFS was 22.0 vs 11.0 months."
arm_1 zorvamab: median_pfs {value "30.1", quote "median PFS was 30.1 months with zorvamab", basis "arm"}; hr_pfs {value "0.55", quote "HR 0.55; 95% CI 0.41-0.74"}; p_value_pfs {value "", quote ""} because P<0.001 is from the earlier analysis; extra [{field "median_pfs", value "22.0", context "patients aged >=75", quote "In patients aged >=75, median PFS was 22.0 vs 11.0 months"}].
arm_2 placebo: median_pfs {value "14.2", ...}; no hazard ratio fields.

EXAMPLE 2 (invented)
Text: "Twelve patients received telnotug + drug A and nine received telnotug + drug B. Results combine both cohorts. CRS occurred in 8 of 21 patients. No ICANS was observed."
Both arms: crs_any_grade {value "38.1", quote "CRS occurred in 8 of 21 patients", basis "pooled", derived true}; icans_any_grade {value "0", quote "No ICANS was observed", basis "pooled", derived true}. patients_treated: arm_1 "12", arm_2 "9", basis "arm"."""


def family_prompt(family: Family, arms: list[Arm]) -> str:
    trial = [f.key for f in family.fields if f.trial_level]
    parts = [
        "TASK: Fill the fields below from the abstract, for each arm listed. "
        f"Fields: {family.title}.",
        _RULES,
    ]
    if trial:
        parts.append(
            "Trial-level fields ("
            + ", ".join(trial)
            + ") go under 'trial' once, not per arm."
        )
    parts += [
        "FIELDS\n" + _fields_block(family),
        "ARMS\n" + _arms_block(arms),
        _EXAMPLES,
    ]
    return "\n\n".join(parts)


def judge_items(
    family: Family, extracted: dict[str, Any], arms: list[Arm]
) -> list[dict[str, Any]]:
    """Every filled value (fields and extras) as a flat, numbered list for the judge."""
    names = {a.arm_id: a.arm_name for a in arms} | {"trial": "whole trial"}
    by_key = {f.key: f for f in family.fields}
    scopes: list[tuple[str, dict[str, Any]]] = []
    if "trial" in extracted:
        scopes.append(("trial", extracted["trial"]))
    scopes += list(extracted.get("arms", {}).items())
    items: list[dict[str, Any]] = []
    for arm_id, cells in scopes:
        for key, cell in cells.items():
            if key != "extra" and cell["value"]:
                items.append({"kind": "field", "arm_id": arm_id, "key": key, **cell})
        for ex in cells.get("extra", []):
            if ex["value"]:
                items.append(
                    {"kind": "extra", "arm_id": arm_id, "key": ex["field"], **ex}
                )
    for i, item in enumerate(items, 1):
        item["id"] = i
        item["arm_name"] = names[item["arm_id"]]
        item["field_name"] = by_key[item["key"]].name
    return items


def _item_line(item: dict[str, Any]) -> str:
    if item["kind"] == "extra":
        tail = f"extra value for: {item['context']}"
    else:
        tail = f"basis: {item['basis'] or 'none'} | derived: {str(item['derived']).lower()}"
    return (
        f"{item['id']} | {item['arm_name']} | {item['field_name']} | "
        f"value: {item['value']} | {tail} | quote: \"{item['quote']}\""
    )


_JUDGE_RULES = """TASK: Check each extracted value below against the abstract. Answer two separate questions for every item.

A. value_ok: is this the right value for this field and this arm, according to the abstract?
- "yes": the abstract states it (or it is simple arithmetic from stated numbers and marked derived).
- "no": pick the error:
  not_stated - the abstract does not say this; it could only come from knowledge of the drug or disease.
  wrong_measure - the number belongs to a different measure (EFS not PFS, CR not ORR, MRD not response).
  wrong_arm_or_group - the number belongs to another arm, a subgroup or a dose level. A value marked "pooled" on several arms is correct if the abstract reports only pooled results.
  wrong_analysis - the number is from an earlier analysis quoted as background.
  wrong_number - the abstract gives a different number.
- "unsure": the abstract is ambiguous. Say what is ambiguous in right_value.

B. quote_ok: does the quote, on its own, state the whole value? "no" if it covers only part of it. A correct value with a short quote is value_ok "yes", quote_ok "no".

Rules:
1. Judge only against the abstract text. Do not use what you know about the drug.
2. Unit conversion and count-to-percent are not errors.
3. right_value: only when value_ok is "no" and the abstract states the right value. Then right_quote must be the exact words that state it. Otherwise both are "".
4. Return one item for every id. Do not add items."""


def judge_prompt(family: Family, items: list[dict[str, Any]], arms: list[Arm]) -> str:
    return "\n\n".join(
        [
            _JUDGE_RULES,
            "FIELD DEFINITIONS\n" + _fields_block(family),
            "ARMS\n" + _arms_block(arms),
            "ITEMS\n" + "\n".join(_item_line(i) for i in items),
        ]
    )


def missed_prompt(family: Family, extracted: dict[str, Any], arms: list[Arm]) -> str:
    """Ask only for values the abstract states and the extraction left empty."""
    empty = []
    if "trial" in extracted:
        keys = [k for k, c in extracted["trial"].items() if not c["value"]]
        empty.append("trial: " + (", ".join(keys) or "none"))
    for arm_id, cells in extracted.get("arms", {}).items():
        keys = [k for k, c in cells.items() if k != "extra" and not c["value"]]
        empty.append(f"{arm_id}: " + (", ".join(keys) or "none"))
    return "\n\n".join(
        [
            "TASK: The fields listed under EMPTY were left empty for this abstract. "
            "Find any of them that the abstract does state. Return one item per value "
            "found: arm_id, field, value (numbers only, no units), and quote (the exact "
            "words that state it). Return an empty list if the abstract states none of "
            "them. Use only the abstract, never what you know about the drug. A value "
            "for a subgroup, a dose level or an earlier analysis does not count.",
            "FIELDS\n" + _fields_block(family),
            "ARMS\n" + _arms_block(arms),
            "EMPTY\n" + "\n".join(empty),
        ]
    )


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
