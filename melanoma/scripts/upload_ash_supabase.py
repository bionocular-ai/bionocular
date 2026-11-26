"""Load a resolved ASH run into Supabase: outcome_fields, trial_outcomes arms, outcome_values.

Reads <run>/resolved.json (scripts/ash_resolve.py). Dry run by default: prints
arms, values and "All arms" view rows per cancer type, and the drift check
(each wide trial_outcomes column against its long value). --write seeds
outcome_fields, replaces each abstract in one transaction
(replace_ash_abstract) and then deletes ASH abstracts no longer in the run
(delete_ash_abstracts_except). Before any write it refuses NCT ids missing from
clinical_trials, and, without --prune, removing an expert-reviewed abstract or
more than 5 abstracts. Needs SUPABASE_SECRET_KEY.

Usage (from melanoma/):
  poetry run python3 scripts/upload_ash_supabase.py --run data/ash_test_run/full_v2 [--write [--prune]]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from functools import cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from supabase import Client, create_client

_MELANOMA_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_MELANOMA_ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from ash_fields import load_families  # noqa: E402
from ash_registry_run import registry_family  # noqa: E402

CSV = _MELANOMA_ROOT / "resources" / "ash" / "book1_sheet2.csv"
SOURCE_NAME = "extraction_results_ASH_2025"
NUMERIC_TYPES = {"percent", "months", "months_or_nr", "count", "number", "p_value"}

# Field key -> the trial_outcomes column it also fills (spec 5.2). Only fields
# whose meaning is the same in every cancer: no response or MRD rate (they
# depend on the response criteria), no per-term heme AE (no AE class), and no
# AE deaths (the source holds counts, the columns hold percents).
WIDE_COLUMNS: dict[str, str] = {
    # regimen and counts
    "generic_name_per_component": "generic_name",
    "brand_name": "brand_name",
    "dose": "dosage",
    "mechanism_of_action": "mechanism_of_action",
    "target": "target_protein",
    "modality": "modality",
    "setting": "line_of_treatment",
    "patients_enrolled": "num_patients",  # enrolled, never treated: policy
    "median_age": "median_age",
    # survival
    "median_pfs": "median_pfs",
    "median_follow_up_pfs": "pfs_followup_months",
    "p_value_pfs": "p_value_pfs",
    "hr_pfs": "hr_pfs",
    "f_95pct_ci_of_hr_pfs": "ci_hr_pfs",
    "pfs_rate_6_mo": "pfs_rate_6m",
    "pfs_rate_12_mo": "pfs_rate_12m",
    "pfs_rate_18_mo": "pfs_rate_18m",
    "pfs_rate_24_mo": "pfs_rate_24m",
    "pfs_rate_36_mo": "pfs_rate_36m",
    "pfs_rate_48_mo": "pfs_rate_48m",
    "median_os": "median_os",
    "median_follow_up_os": "os_followup_months",
    "p_value_os": "p_value_os",
    "hr_os": "hr_os",
    "f_95pct_ci_of_hr_os": "ci_hr_os",
    "os_rate_6_mo": "os_rate_6m",
    "os_rate_12_mo": "os_rate_12m",
    "os_rate_18_mo": "os_rate_18m",
    "os_rate_24_mo": "os_rate_24m",
    "os_rate_36_mo": "os_rate_36m",
    "os_rate_48_mo": "os_rate_48m",
    "median_efs": "efs",
    "hr_efs": "hr_efs",
    "p_value_efs": "p_value_efs",
    "f_95pct_ci_of_hr_efs": "ci_hr_efs",
    "median_rfs": "rfs",
    "hr_rfs": "hr_rfs",
    "p_value_rfs": "p_value_rfs",
    "f_95pct_ci_of_hr_rfs": "ci_hr_rfs",
    # safety aggregates that carry an AE class
    "grade_ge3_aes": "grade_3_plus_ae_pct",
    "grade_ge3_teaes": "grade_3_plus_teae_pct",
    "grade_ge3_traes": "grade_3_plus_trae_pct",
    "serious_aes": "serious_ae_pct",
    "serious_teaes": "serious_teae_pct",
    "serious_traes": "serious_trae_pct",
    "discontinuation_due_to_aes": "ae_leading_to_discontinuation_pct",
    "discontinuation_due_to_teaes": "teae_discontinuation_pct",
    "discontinuation_due_to_traes": "trae_discontinuation_pct",
    "aes_leading_to_dose_reduction": "ae_dose_reduction_pct",
    "teaes_leading_to_dose_reduction": "teae_dose_reduction_pct",
    "traes_leading_to_dose_reduction": "trae_dose_reduction_pct",
    "aes_leading_to_dose_interruption": "ae_dose_interruption_pct",
    "teaes_leading_to_dose_interruption": "teae_dose_interruption_pct",
    "traes_leading_to_dose_interruption": "trae_dose_interruption_pct",
    "aes_requiring_hospitalization": "ae_hospitalization_pct",
    "teaes_requiring_hospitalization": "teae_hospitalization_pct",
    "traes_requiring_hospitalization": "trae_hospitalization_pct",
    "infusion_related_reaction_irr": "irr_pct",
    "crs_any_grade": "crs_pct",
}
_NUMBER = re.compile(r"(<=|>=|≤|≥|<|>|=)?\s*(\d*\.?\d+)\s*%?")
_QUALIFIER = {"≤": "<=", "≥": ">=", "=": None, None: None}


def parse_value(value_text: str, value_type: str) -> tuple[float | None, str | None]:
    """(value_num, qualifier). Only numeric types parse; NR, ranges and text get no number."""
    if value_type not in NUMERIC_TYPES:
        return None, None
    text = value_text.strip()
    if text.upper() == "NR":
        return None, "NR"
    m = _NUMBER.fullmatch(text)
    if not m:
        return None, None
    return float(m[2]), _QUALIFIER.get(m[1], m[1])


@cache
def _fields() -> tuple[dict[str, Any], ...]:
    families = (*load_families(CSV), registry_family(CSV))
    return tuple(
        {
            "key": f.key,
            "label": f.name,
            "family": fam.key,
            "scope": f.scope,
            "value_type": f.value_type,
            "allowed_values": list(f.allowed) or None,
            "definition": f.definition
            + (f" Applies to: {f.applies_to}." if f.applies_to else ""),
            "wide_column": WIDE_COLUMNS.get(f.key),
            "sort_order": i,
        }
        for fam in families
        for i, f in enumerate(fam.fields)
    )


def field_rows() -> list[dict]:
    """The outcome_fields payload: every abstract and registry field."""
    return [dict(r) for r in _fields()]


@cache
def _field(key: str) -> dict[str, Any]:
    return next(r for r in _fields() if r["key"] == key)


def _wide(val: dict) -> tuple[Any, str | None]:
    """The wide column value a long value gives, and 'is_nr' / 'is_lt' when flagged."""
    if _field(val["field_key"])["value_type"] not in NUMERIC_TYPES:
        return val["value_text"], None
    num, q = val["value_num"], val["qualifier"]
    if q == "NR":
        return None, "is_nr"
    if q == "<":
        return num, "is_lt"
    if q is not None:  # >, >=, <=: no column flag says so, the long row keeps it
        return None, None
    if num is not None and WIDE_COLUMNS[val["field_key"]] == "num_patients":
        return (int(num) if num.is_integer() else None), None
    return num, None


def _wide_sources(arm: dict, vals: list[dict]) -> dict[str, list[dict]]:
    """Main values per wide field for one arm: its own, plus trial-scope values
    (they hold for every arm). Pooled values never fill an arm."""
    out: dict[str, list[dict]] = defaultdict(list)
    for v in vals:
        if v["context"] or v["field_key"] not in WIDE_COLUMNS:
            continue
        own = v["trial_outcome_id"] == arm["id"]
        trial = (
            v["trial_outcome_id"] is None and _field(v["field_key"])["scope"] == "trial"
        )
        if own or trial:
            out[v["field_key"]].append(v)
    return out


def abstract_payload(records: list[dict]) -> tuple[list[dict], list[dict]]:
    """(arms, vals) for one abstract, in the shape replace_ash_abstract takes."""
    first = records[0]
    abstract_id = f"ASH_2025_{first['abstract']}"
    nct_id = first["nct_ids"][0] if first["nct_ids"] else None
    cancer_type = [first["indication"]]
    source_url = f"https://doi.org/{first['doi']}"

    arms: dict[str, dict] = {}
    for r in records:
        if r["arm_id"] and r["arm_id"] not in arms:
            arms[r["arm_id"]] = {
                "id": f"abstract_{abstract_id}_{r['arm_id']}",
                "source_type": "abstract",
                "source_name": SOURCE_NAME,
                "abstract_id": abstract_id,
                "source_url": source_url,
                "nct_id": nct_id,
                "arm_id": r["arm_id"],
                "arm_name": r["arm_name"],
                "cancer_type": cancer_type,
                # every arm carries every wide column, so a cleared value is nulled
                **dict.fromkeys(WIDE_COLUMNS.values()),
                "is_nr": None,
                "is_lt": None,
            }

    vals: list[dict] = []
    for r in records:
        num, q = parse_value(r["value_text"], _field(r["field_key"])["value_type"])
        val = {
            "trial_outcome_id": arms[r["arm_id"]]["id"] if r["arm_id"] else None,
            "source_type": "abstract",
            "source_id": abstract_id,
            "source_url": source_url,
            "nct_id": nct_id,
            "cancer_type": cancer_type,
            "field_key": r["field_key"],
            "context": r["context"],
            "value_text": r["value_text"],
            "value_num": num,
            "qualifier": q,
            "n": r["n"],
            "detail": r["detail"],
            "derived": r["derived"],
            "origin": r["origin"],
            "caveat": r["caveat"],
        }
        if val not in vals:  # exact duplicates only
            vals.append(val)

    for arm in arms.values():
        flags: dict[str, list[str]] = {"is_nr": [], "is_lt": []}
        for key, [v, *rest] in _wide_sources(arm, vals).items():
            if rest:  # two main values: no single wide value; drift reports it
                continue
            col = WIDE_COLUMNS[key]
            arm[col], flag = _wide(v)
            if flag:
                flags[flag].append(col)
        arm.update({k: sorted(cols) or None for k, cols in flags.items()})
    return list(arms.values()), vals


def drift(arms: list[dict], vals: list[dict]) -> list[str]:
    """Wide columns that disagree with their long main value, one line each."""
    out = []
    for arm in arms:
        sources = _wide_sources(arm, vals)
        for key, col in WIDE_COLUMNS.items():
            found = sources.get(key, [])
            if len(found) > 1:
                out.append(f"{arm['id']} {col}: {len(found)} main values")
                continue
            want, flag = _wide(found[0]) if found else (None, None)
            flagged = {f for f in ("is_nr", "is_lt") if col in (arm[f] or [])}
            if arm[col] != want or flagged != ({flag} if flag else set()):
                out.append(
                    f"{arm['id']} {col}: wide {arm[col]!r} {sorted(flagged)}, "
                    f"long {want!r} {flag or ''}".rstrip()
                )
    return out


def _paged(query: Any) -> list[dict]:
    """Every row of query(), a page at a time (PostgREST caps a response at 1000)."""
    rows: list[dict] = []
    while True:
        page = query().range(len(rows), len(rows) + 999).execute().data
        rows += page
        if len(page) < 1000:
            return rows


def missing_ncts(sb: Client, payloads: dict[str, tuple[list, list]]) -> list[str]:
    """The payloads' NCT ids that clinical_trials lacks (the foreign key would fail
    mid-load)."""
    ncts = sorted(
        {r["nct_id"] for arms, vals in payloads.values() for r in arms + vals} - {None}
    )
    found = sb.table("clinical_trials").select("nct_id").in_("nct_id", ncts).execute()
    return sorted(set(ncts) - {r["nct_id"] for r in found.data})


def prune_refusal(
    sb: Client, payloads: dict[str, tuple[list, list]], prune: bool
) -> str | None:
    """Prints the live ASH abstracts the load would remove and each reviewed arm whose
    name would change; the reason to refuse, unless prune: a removed abstract carries
    an expert review, or more than 5 would go."""
    live_arms = _paged(
        lambda: sb.table("trial_outcomes")
        .select("id, abstract_id, arm_name, expert_review")
        .eq("source_name", SOURCE_NAME)
        .order("id")
    )
    live_vals = _paged(
        lambda: sb.table("outcome_values")
        .select("source_id")
        .like("source_id", "ASH\\_2025\\_%")
        .order("id")
    )
    keep = {f"ASH_2025_{a}" for a in payloads}
    live = {r["abstract_id"] for r in live_arms} | {r["source_id"] for r in live_vals}
    gone = sorted(live - keep)
    names = {
        arm["id"]: arm["arm_name"] for arms, _ in payloads.values() for arm in arms
    }
    reviewed = [r for r in live_arms if r["expert_review"] is not None]
    print(f"would remove {len(gone)} ASH abstracts no longer in the run: {gone}")
    for r in reviewed:
        if names.get(r["id"]) != r["arm_name"]:
            new = repr(names[r["id"]]) if r["id"] in names else "removed"
            print(
                f"reviewed arm {r['id']} ({r['expert_review']}): {r['arm_name']!r} -> {new}"
            )
    if prune:
        return None
    lost = sorted({r["abstract_id"] for r in reviewed} & set(gone))
    if lost:
        return f"refusing to remove reviewed abstracts {lost} (pass --prune to allow)"
    if len(gone) > 5:
        return f"refusing to remove {len(gone)} abstracts (pass --prune to allow)"
    return None


def _client() -> Client:
    load_dotenv(_MELANOMA_ROOT / ".env")
    url = os.environ.get("SUPABASE_URL")
    # trial_outcomes RLS and the replace_ash_abstract grant need the secret key.
    key = os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("SUPABASE_KEY")
    if not url or not key:
        sys.exit("SUPABASE_URL and SUPABASE_SECRET_KEY must be set in melanoma/.env")
    return create_client(url, key)


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--run", type=Path, required=True, help="run dir with resolved.json")
    p.add_argument("--write", action="store_true", help="write to Supabase")
    p.add_argument(
        "--prune",
        action="store_true",
        help="allow removing reviewed abstracts, or more than 5, no longer in the run",
    )
    args = p.parse_args()

    records = json.loads((args.run / "resolved.json").read_text(encoding="utf-8"))
    if not records:  # an empty keep list would delete every ASH abstract
        sys.exit("refusing to load: no abstracts in the run")
    unknown = {r["field_key"] for r in records} - {f["key"] for f in _fields()}
    if unknown:
        sys.exit(
            f"refusing to load: field keys not in outcome_fields: {sorted(unknown)}"
        )
    by_abstract: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_abstract[r["abstract"]].append(r)
    payloads = {a: abstract_payload(rs) for a, rs in by_abstract.items()}

    per_cancer: dict[str, Counter] = defaultdict(Counter)
    problems: list[str] = []
    for a, (arms, vals) in payloads.items():
        c = per_cancer[by_abstract[a][0]["indication"]]
        c["abstracts"] += 1
        c["arms"] += len(arms)
        c["values"] += len(vals)
        # the view's "All arms" row: any arm-less value, pooled or trial scope
        c["all_arms_rows"] += any(v["trial_outcome_id"] is None for v in vals)
        problems += drift(arms, vals)

    width = max(map(len, per_cancer))
    print(f"{'cancer type':<{width}}  abstracts  arms  values  all_arms_rows")
    for name, c in sorted(per_cancer.items(), key=lambda kv: -kv[1]["values"]):
        print(
            f"{name:<{width}}  {c['abstracts']:>9}  {c['arms']:>4}  {c['values']:>6}"
            f"  {c['all_arms_rows']:>13}"
        )
    total = sum(per_cancer.values(), Counter())
    print(
        f"{len(per_cancer)} cancer types, {total['abstracts']} abstracts, "
        f"{total['arms']} arms, {total['values']} values, "
        f"{total['all_arms_rows']} All arms rows, {len(field_rows())} fields"
    )
    print("\n".join(problems[:50]))
    print(f"drift: {len(problems)} mismatches")
    if problems:
        sys.exit(1)
    if not args.write:
        print("dry run: nothing written (pass --write to load)")
        return

    sb = _client()
    missing = missing_ncts(sb, payloads)
    if missing:
        sys.exit(f"refusing to load: NCT ids not in clinical_trials: {missing}")
    refusal = prune_refusal(sb, payloads, args.prune)
    if refusal:
        sys.exit(refusal)
    sb.table("outcome_fields").upsert(field_rows()).execute()
    for a, (arms, vals) in payloads.items():
        sb.rpc(
            "replace_ash_abstract",
            {"abstract_id": f"ASH_2025_{a}", "arms": arms, "vals": vals},
        ).execute()
    keep = [f"ASH_2025_{a}" for a in payloads]
    removed = sb.rpc("delete_ash_abstracts_except", {"keep": keep}).execute().data
    print(f"loaded {len(payloads)} abstracts; removed {removed} no longer in the run")


if __name__ == "__main__":
    main()
