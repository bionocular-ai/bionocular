"""Resolve a reviewed ASH run into resolved.json: one record per final value, no quotes.

Usage (from melanoma/):
  poetry run python3 scripts/ash_resolve.py --run data/ash_test_run/full_v2 \\
      [--check-xlsx data/ash_test_run/full_v2/ash_full_v2_results_resolved.xlsx] \\
      [--no-registry-criteria]

Port of the two .lavish/ash-integration/tools scripts of 2026-11-24
(adjudication_merge, then resolve_judge_expert), with the resolution order unchanged:
results.json, expert verdicts, the context rerun, Opus adjudication, then the policy
overrides. --check-xlsx compares every arm, pooled and extra value with the resolved
sheet those scripts wrote and exits non-zero on any mismatch.

Every input is read from the run dir. The ones that lived elsewhere were copied into
run/resolution_inputs/ once (2026-11-26, from melanoma/):
  R=data/ash_test_run/full_v2/resolution_inputs; mkdir -p $R
  cp data/ash_test_run/full_v1/registry.json $R/registry_v1.json
  cp data/postprocessed/ASH_Abstracts/ASH_2025_all.md $R/
  poetry run python3 -c "import json, pathlib as p; \\
    d = json.loads(p.Path('../.lavish/ash-verify/data.js').read_text().split('=', 1)[1].rstrip().rstrip(';')); \\
    ks = ('a', 'arm', 'field', 'kind', 'context', 'value'); \\
    p.Path('$R/values.json').write_text(json.dumps({i: {k: v.get(k, '') for k in ks} for i, v in enumerate(d['values'])}))"
"""

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(Path(__file__).parent))

from ash_checks import quote_found  # noqa: E402
from ash_fields import Arm, full_names, load_families  # noqa: E402
from ash_registry_criteria import fill_criteria, spot_check_rows  # noqa: E402
from ash_registry_run import (  # noqa: E402
    ClinicalTrialsGovAPIClient,
    fetch,
    registry_family,
)
from ash_results_sheet import OTHER, _arm_id, _shown, registry_cells  # noqa: E402
from ash_review_sheet import build_rows, load_selection  # noqa: E402
from ash_test_run import META, parse_md  # noqa: E402

CSV = _root / "resources" / "ash" / "book1_sheet2.csv"
MISPRINT = "source misprint, corrected by arithmetic"
POOLED_SHEET = "Pooled (all arms together)"
_CHECK_SUFFIX = " - CHECK: judge and expert disagree"  # the sheet's context marker


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def nv(x: object) -> str:
    return re.sub(r"[\s%]+", "", str(x or "")).lower()


def _key(a: str, arm: str, f: str, k: str, ctx: str | None, v: str) -> tuple:
    return (a, arm, f, k, ctx or "", v)


def cited_order(nct_ids: list[str], text: str) -> list[str]:
    """The ids by first appearance in the text, so the first is the primary trial;
    ids the text does not name keep their order, after the rest."""
    return sorted(nct_ids, key=lambda n: (n not in text, text.find(n)))


def adjudications(run: Path, values: dict[str, dict]) -> list[dict]:
    """The Opus verdicts (context rerun and post-rerun batches win over the first pass),
    with the product-owner policy overrides on top."""
    adj = run / "adjudication"

    def by_id(pattern: str) -> dict[int, dict]:
        return {x["id"]: x for p in sorted(adj.glob(pattern)) for x in _load(p)}

    def ids(pattern: str) -> list[int]:
        return [i for p in sorted(adj.glob(pattern)) for i in _load(p)]

    ver = {x["id"]: x for x in _load(run / "expert_review/verdicts.json")}
    want, base = ids("batch_*_ids.json"), by_id("verdicts_*.json")
    ctx, newv = by_id("ctx_verdicts_*.json"), by_id("new_verdicts_*.json")
    assert set(base) == set(want), set(want) ^ set(base)
    new_want = ids("new_batch_*_ids.json")
    assert set(newv) == set(new_want), set(new_want) ^ set(newv)
    # new_*: disagreements that appeared after the expert rerun; their expert side is the rerun
    rerun = _load(run / "expert_review/ctx_rerun/verdicts.json")
    ver.update({x["id"]: x for x in rerun if x["id"] in newv})
    out = []
    for i in want + new_want:
        x = ver[i]
        out.append(
            {
                **(newv.get(i) or ctx.get(i) or base[i]),
                "context": values[str(i)]["context"],
            }
            | {k: x[k] for k in ("abstract", "arm", "field", "kind", "value")}
        )
    policy = {o["id"]: o for o in _load(adj / "policy_overrides.json")}
    keys = ("policy_call", "final", "right_value", "right_quote", "error", "reason")
    for rec in out:
        if rec["id"] in policy:
            rec |= {k: policy[rec["id"]][k] for k in keys}
    assert sum("policy_call" in r for r in out) == len(policy)
    return out


def _resolve(
    rows: list[dict],
    expert: dict[tuple, dict],
    adj: dict[tuple, dict],
    texts: dict[str, str],
    tally: Counter,
) -> None:
    """Write each row's final value and its caveat (the sheet note a reader must see)."""
    for r in rows:
        if not r["value"] or r["kind"] == "missed":
            continue
        k = _key(
            r["abstract"], r["arm"], r["field"], r["kind"], r["context"], r["value"]
        )
        old, judge_wrong = r["value"], r.get("value_ok") == "no"
        jv = r.get("right_value", "") if judge_wrong else ""
        usable = (
            bool(jv)
            and nv(jv) != nv(old)
            and quote_found(r.get("right_quote", ""), texts[r["abstract"]])
        )
        jv = jv if usable else ""
        x = expert.get(k)
        ev = (x or {}).get("expert_right_value", "")
        new, state, note = old, "ok", ""
        if x is None:
            if usable:
                new, state = jv, "patched"
        elif x["expert"] == "unclear":
            state, note = "disagree", "expert unclear"
        elif x["expert"] == "correct":
            if judge_wrong:
                state, note = "disagree", "judge wrong, expert correct"
        elif not judge_wrong:
            new, state, note = (ev or old), "disagree", "judge correct, expert wrong"
        elif not ev and not jv:
            new, state = "", "cleared"
        elif not jv or nv(jv) == nv(ev):
            new, state = ev, "patched"
        else:
            new, state = (ev or old), "disagree"
            note = f"judge says {jv}, expert says {ev or 'not stated'}"
        a = adj.get(k)
        if state == "disagree" or a:
            assert a, (r["abstract"], r["field"], old)
            av, aq = a.get("right_value", ""), a.get("right_quote", "")
            contradiction = a.get("policy_call") == "contradiction"
            if a["final"] == "correct":
                new, state, note = old, "ok", ""
            elif a["final"] == "wrong" and av and quote_found(aq, texts[r["abstract"]]):
                new, state, note = av, "patched", MISPRINT if contradiction else ""
            elif a["final"] == "wrong" and not av:
                new, state, note = "", "cleared", ""
            elif a["final"] == "wrong":
                new, state = old, "disagree"
                note = f"adjudicated wrong, says {av} (quote not found)"
            else:
                new, state = old, "disagree"
                note = (
                    "possible source error, literal value kept: needs a person"
                    if contradiction
                    else "adjudicated unclear"
                )
        tally[("expert" if x else "no expert", state)] += 1
        r["value"], r["caveat"] = new, note or None


def resolve_run(run_dir: Path, tally: Counter | None = None) -> list[dict]:
    """One record per final value the resolved sheet shows; cleared values are absent."""
    tally = Counter() if tally is None else tally
    inputs = run_dir / "resolution_inputs"
    values = _load(inputs / "values.json")
    expert: dict[tuple, dict] = {}
    for path in (
        "expert_review/verdicts.json",
        "expert_review/ctx_rerun/verdicts.json",
    ):
        for x in _load(run_dir / path):  # the context rerun replaces the first pass
            v = values[str(x["id"])]
            k = _key(v["a"], v["arm"], v["field"], v["kind"], v["context"], v["value"])
            expert[k] = x
    adj = {
        _key(
            x["abstract"], x["arm"], x["field"], x["kind"], x["context"], x["value"]
        ): x
        for x in adjudications(run_dir, values)
    }
    results = _load(run_dir / "results.json")
    results.pop(META, None)
    registry: dict[str, Any] = {}
    for path in (inputs / "registry_v1.json", run_dir / "registry.json"):
        registry.update(_load(path))  # the full_v2 entry replaces the full_v1 one
    registry.pop(META, None)
    texts = parse_md(inputs / "ASH_2025_all.md")
    selection = load_selection(run_dir / "selection_union.csv")
    families = load_families(CSV)
    reg_family = registry_family(CSV)
    keys = {f.name: f.key for fam in (*families, reg_family) for f in fam.fields}
    rows = build_rows(results, texts, families, selection)
    _resolve(rows, expert, adj, texts, tally)
    by_abstract: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r["value"] and r["kind"] != "missed":
            by_abstract[r["abstract"]].append(r)
    full, reg_names = full_names(), {f.key: f.name for f in reg_family.fields}

    out = []
    for number in [n for n in selection if n in results]:
        res, sel = results[number], selection[number]
        arms = {a["arm_id"]: a for a in res["arms"]}
        base = {
            "abstract": number,
            "doi": sel["doi"],
            "indication": full[sel["indication"]],
            "nct_ids": cited_order(res["nct_ids"], texts[number]),
        }
        mine = by_abstract[number]
        # as the sheet does: abstract values first, a registry value fills an empty field
        wide: dict[tuple[str, str], tuple[dict, str]] = {}
        for r in mine:
            if r["kind"] == "field":
                wide[(_arm_id(r["arm"]), r["field"])] = (r, "abstract")
        for c in registry_cells(registry.get(number, {}), reg_names):
            wide.setdefault((c["arm"], c["field"]), (c, "registry"))
        cells = list(wide.values()) + [
            (r, "abstract") for r in mine if r["kind"] in ("extra", "pooled")
        ]
        for c, origin in cells:
            scope = _arm_id(c["arm"])
            assert scope in arms or scope in ("trial", "pooled (all arms)"), scope
            arm = arms.get(scope)  # None for trial-scope and pooled values
            n = str(c.get("n") or "")
            out.append(
                {
                    **base,
                    "arm_id": arm and arm["arm_id"],
                    "arm_name": arm and Arm(**arm).label,  # with any dose level
                    "arm_role": arm and arm["role"],
                    "field_key": keys[c["field"]],
                    "context": c.get("context") or "",
                    "value_text": c["value"],
                    "n": int(n) if n.isdigit() else None,
                    "detail": c.get("detail") or "",
                    "derived": c.get("derived") == "yes",
                    "origin": origin,
                    "caveat": c.get("caveat"),
                }
            )
    return out


def _entries(text: str | None, labels: list[str]) -> list[str]:
    """A sheet list cell ('Label: value (context); ...') split into its entries, with the
    sheet-only context marker removed and cleared entries (empty value) left out."""
    if not text:
        return []
    split = "; (?=(?:" + "|".join(map(re.escape, labels)) + "): )"
    parts = re.split(split, text.replace(_CHECK_SUFFIX, ""))
    return [
        e
        for e in parts
        if not any(e.startswith(f"{lb}:  ") or e == f"{lb}: " for lb in labels)
    ]


def _match(entry: str, rec: dict, label: str) -> bool:
    """The sheet entry is the record's value, allowing the ' [was old]' a patch adds."""
    head = f"{label}: {_shown(_cell(rec))}"
    tail = f" ({rec['context']})" if rec["context"] else ""
    if not (entry.startswith(head) and entry.endswith(tail)):
        return False
    middle = entry[len(head) : len(entry) - len(tail)]
    return middle == "" or middle.startswith(" [was ")


def _cell(rec: dict) -> dict:
    return {"value": rec["value_text"], "n": rec["n"] or "", "detail": rec["detail"]}


def _compare_list(
    where: str, text: Any, recs: list[dict], labels: dict[str, str]
) -> list[str]:
    left = _entries(text, sorted(set(labels.values()), key=len, reverse=True))
    bad = []
    for r in recs:
        label = labels[r["field_key"]]
        hit = next((e for e in left if _match(e, r, label)), None)
        if hit is None:
            bad.append(
                f"{where} | {label} | context {r['context']!r} | resolved {r['value_text']!r}, not in sheet"
            )
        else:
            left.remove(hit)
    return bad + [f"{where} | sheet entry not in resolved.json: {e!r}" for e in left]


def check_xlsx(records: list[dict], path: Path) -> tuple[list[str], Counter]:
    """Mismatches between resolved.json and the resolved sheet, one line each, and counts."""
    fields = [
        f for fam in (*load_families(CSV), registry_family(CSV)) for f in fam.fields
    ]
    scope, labels = {f.key: f.scope for f in fields}, {f.key: f.name for f in fields}
    main: dict[tuple, dict] = {}
    arm_names: dict[tuple, set[str]] = defaultdict(set)
    extras: dict[tuple, list[dict]] = defaultdict(list)
    pooled: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        k = (r["abstract"], r["arm_id"], r["field_key"])
        if r["arm_id"]:
            arm_names[(r["abstract"], r["arm_id"])].add(r["arm_name"])
        if r["arm_id"] is None and scope[r["field_key"]] != "trial":
            pooled[r["abstract"]].append(r)
        elif r["context"] == "" and k not in main:
            main[k] = r
        else:
            extras[(r["abstract"], r["arm_id"])].append(r)
    wb = load_workbook(path, read_only=True)
    bad: list[str] = []
    seen: set[tuple] = set()
    it = wb["Arms"].iter_rows(values_only=True)
    head = list(next(it))
    cols = {h: i for i, h in enumerate(head)}
    keys = {labels[k]: k for k in labels}
    count = Counter()
    for row in it:
        a, arm = str(row[cols["abstract"]]), row[cols["arm_id"]]
        count["arm rows"] += 1
        dose = row[cols["dose_level"]]
        label = f"{row[cols['arm']]} [{dose}]" if dose else row[cols["arm"]]
        bad += [
            f"{a} | {arm} | arm_name {n!r}, sheet {label!r}"
            for n in arm_names.pop((a, arm), set()) - {label}
        ]
        for label, i in cols.items():
            if label not in keys:
                continue
            k = keys[label]
            rec = main.get((a, arm, k)) or main.get((a, None, k))
            seen.update(
                x for x in ((a, arm, k), (a, None, k)) if x in main and main[x] is rec
            )
            want = _shown(_cell(rec)) if rec else None
            if rec and row[i] is None and rec["arm_id"] == arm:
                # an extra without a context looks like a main value: the sheet lists it
                extras[(a, arm)].append(rec)
            elif want != row[i]:
                bad.append(
                    f"{a} | {arm} | {label} | context '' | resolved {want!r}, sheet {row[i]!r}"
                )
        bad += _compare_list(
            f"{a} | {arm}", row[cols[OTHER]], extras.pop((a, arm), []), labels
        )
    for row in wb[POOLED_SHEET].iter_rows(min_row=2, values_only=True):
        a = str(row[0])
        bad += _compare_list(f"{a} | pooled", row[2], pooled.pop(a, []), labels)
    for k in main.keys() - seen:
        bad.append(
            f"{k[0]} | {k[1]} | {labels[k[2]]} | context '' | resolved {main[k]['value_text']!r}, no sheet cell"
        )
    for (a, arm), recs in extras.items():
        bad += _compare_list(f"{a} | {arm}", None, recs, labels)
    for a, recs in pooled.items():
        bad += _compare_list(f"{a} | pooled", None, recs, labels)
    count.update(
        "registry"
        if r["origin"] == "registry"
        else "pooled"
        if r["arm_id"] is None and scope[r["field_key"]] != "trial"
        else "trial"
        if r["arm_id"] is None
        else "arm main"
        if r["context"] == ""
        else "extra"
        for r in records
    )
    return bad, count


def _registry_criteria(run: Path, records: list[dict]) -> list[dict]:
    """The records with the registry criteria filled (the sheet has no such cells, so
    this runs after the xlsx check)."""
    cache = run / "records"
    cache.mkdir(exist_ok=True)
    client = None
    studies: dict[str, dict] = {}
    for nct in sorted({n for r in records for n in r["nct_ids"]}):
        if client is None and not (cache / f"{nct}.json").exists():
            client = ClinicalTrialsGovAPIClient()
        studies[nct] = fetch(nct, cache, client) or {}
    keys = {
        f.key
        for fam in load_families(CSV)
        if fam.key == "response_rates"
        for f in fam.fields
    }
    filled = fill_criteria(records, studies, keys)
    added = filled[len(records) :]
    rows = spot_check_rows(added, studies)
    with (run / "spot_check.csv").open("w", newline="", encoding="utf-8") as f:
        cols = ["abstract", "nct", "set", "indication", "sentence", "ok", "why"]
        w = csv.DictWriter(f, cols)
        w.writeheader()
        w.writerows(rows)
    print(
        f"registry criteria: {len(added)} filled",
        dict(Counter(r["value_text"] for r in added)),
        "" if rows else "(spot_check.csv has its header only)",
    )
    return filled


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--run",
        type=Path,
        required=True,
        help="run dir, e.g. data/ash_test_run/full_v2",
    )
    p.add_argument(
        "--check-xlsx", type=Path, help="resolved sheet to compare every value with"
    )
    p.add_argument(
        "--no-registry-criteria",
        action="store_true",
        help="do not fill a missing response criteria from the trial registry",
    )
    args = p.parse_args()
    tally: Counter = Counter()
    records = resolve_run(args.run, tally)
    for k in sorted(tally):
        print(k, tally[k])
    if args.check_xlsx:
        bad, count = check_xlsx(records, args.check_xlsx)
        print("\n".join(bad[:50]))
        print(
            f"{len(bad)} mismatches; "
            + ", ".join(f"{k} {v}" for k, v in sorted(count.items()))
        )
        if bad:  # the previous resolved.json stays
            sys.exit(1)
    if not args.no_registry_criteria:
        records = _registry_criteria(args.run, records)
    out = args.run / "resolved.json"
    out.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
    print(
        f"wrote {out}: {len(records)} records, {len({r['abstract'] for r in records})} abstracts"
    )


if __name__ == "__main__":
    main()
