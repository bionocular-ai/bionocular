"""Fill a missing response criteria from the trial's ClinicalTrials.gov outcome measures.

Only when exactly one criteria set is named across the abstract's NCT ids. The record
is stored with origin "registry" so the agent can say "criteria per the trial registry".
"""

import re
from collections import defaultdict

PATTERNS = {
    "IMWG": r"IMWG|International Myeloma",
    "Lugano/Cheson": r"Lugano|Cheson|Deauville",
    "ELN": r"\bELN\b|LeukemiaNet",
    "iwCLL": r"iwCLL|Workshop on (Chronic Lymphocytic|CLL)|Hallek",
    "IWG": r"\bIWG\b|International Working Group",
    "Owen/IWWM": r"Owen|IWWM",
    "NIH/MAGIC": r"NIH consensus|MAGIC",
}
# a set counts only when the outcome names a response within this many characters
RESPONSE = re.compile(r"respon|remission|\bCRR?\b|\bORR\b", re.I)
WINDOW = 80
DETAIL = "criteria per the trial registry"


def outcome_texts(study: dict) -> list[str]:
    """Measure and description of every protocol and posted-result outcome measure."""
    out = []
    om = study.get("protocolSection", {}).get("outcomesModule", {})
    for kind in ("primaryOutcomes", "secondaryOutcomes", "otherOutcomes"):
        for o in om.get(kind, []):
            out += [o.get("measure", ""), o.get("description", "")]
    res = study.get("resultsSection", {}).get("outcomeMeasuresModule", {})
    for o in res.get("outcomeMeasures", []):
        out += [o.get("title", ""), o.get("description", "")]
    return [t for t in out if t]


def criteria_matches(study: dict) -> list[tuple[str, str]]:
    """(set, sentence) for each place an outcome measure names a criteria set next to a
    response word (a PFS, GVHD or treatment-failure outcome does not define response)."""
    found = []
    for text in outcome_texts(study):
        for sentence in re.split(r"(?<=[.;])\s+|\n+", text):
            for name, pat in PATTERNS.items():
                for m in re.finditer(pat, sentence, re.I):
                    near = sentence[max(0, m.start() - WINDOW) : m.end() + WINDOW]
                    if RESPONSE.search(near):
                        found.append((name, sentence.strip()))
                        break
    return found


def criteria_sets(study: dict) -> set[str]:
    return {name for name, _ in criteria_matches(study)}


def fill_criteria(
    records: list[dict], studies: dict[str, dict], response_keys: set[str]
) -> list[dict]:
    """The records plus one registry response_criteria record per qualifying abstract."""
    by_abstract: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_abstract[r["abstract"]].append(r)
    added = []
    for recs in by_abstract.values():
        keys = {r["field_key"] for r in recs}
        if "response_criteria" in keys or not keys & response_keys:
            continue
        sets: set[str] = set()
        for nct in recs[0]["nct_ids"]:
            sets |= criteria_sets(studies.get(nct) or {})
        if len(sets) == 1:
            first = recs[0]
            added.append(
                {
                    **{
                        k: first[k]
                        for k in ("abstract", "doi", "indication", "nct_ids")
                    },
                    "arm_id": None,
                    "arm_name": None,
                    "arm_role": None,
                    "field_key": "response_criteria",
                    "context": "",
                    "value_text": next(iter(sets)),
                    "n": None,
                    "detail": DETAIL,
                    "derived": False,
                    "origin": "registry",
                    "caveat": None,
                }
            )
    return records + added


def spot_check_rows(
    added: list[dict], studies: dict[str, dict], size: int = 20
) -> list[dict]:
    """size rows (abstract, NCT, set, matched sentence): every AML ELN match up to 5 first,
    then round-robin over the sets so each is represented."""
    pool: dict[str, list[dict]] = defaultdict(list)
    for r in sorted(added, key=lambda r: int(r["abstract"])):
        for nct in r["nct_ids"]:
            hit = next(
                (
                    s
                    for n, s in criteria_matches(studies.get(nct) or {})
                    if n == r["value_text"]
                ),
                None,
            )
            if hit:
                pool[r["value_text"]].append(
                    {"abstract": r["abstract"], "nct": nct, "set": r["value_text"],
                     "indication": r["indication"], "sentence": hit}
                )  # fmt: skip
                break
    rows = [x for x in pool["ELN"] if x["indication"] == "Acute Myeloid Leukemia"][:5]
    left = {k: [x for x in v if x not in rows] for k, v in pool.items()}
    while len(rows) < size and any(left.values()):
        for v in left.values():
            if v and len(rows) < size:
                rows.append(v.pop(0))
    return rows
