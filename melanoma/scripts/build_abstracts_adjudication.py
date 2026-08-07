"""
Triage the abstracts validation FAILs and build adjudication batches.

The judge flagged 1785 cells. Most do not need a human-grade reader:

  suppress  - the judge's only complaint is a trailing '.0'. These columns are
              numeric, so '30' and '30.0' are the same stored value.
  auto      - a ci_hr_* cell holding a bare lower bound whose upper bound appears
              exactly once in the abstract. Unambiguous, so recover it offline.
  agent     - everything else, split into safety and efficacy batches, each with
              its abstract embedded inline.

Batches embed `source_text` rather than a path: abstract sources hold a whole
conference per file, and an agent handed the file would read neighbouring trials.

Usage:
    cd melanoma
    poetry run python3 scripts/build_abstracts_adjudication.py
    poetry run python3 scripts/build_abstracts_adjudication.py --batch-size 40
"""

import argparse
import collections
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from verify_validation_quotes import normalize, source_text  # noqa: E402

_root = pathlib.Path(__file__).parent.parent

DEFAULT_VALIDATION = (
    _root / "data/output/Abstracts_April_2026/validation/validation.json"
)
DEFAULT_OUT = _root / "data/validation/abstracts_adjudication"

CI_COLUMNS = {
    "ci_hr_os",
    "ci_hr_pfs",
    "ci_hr_rfs",
    "ci_hr_efs",
    "ci_hr_mfs",
    "ci_hr_ttp",
}
# Adverse-event columns go to the safety spec; everything else to efficacy.
SAFETY_PREFIXES = ("ae", "grade_3", "serious_", "trae", "teae", "irr", "immune_related")
RANGE = re.compile(r"^\s*\d*\.?\d+\s*-\s*\d*\.?\d+\s*$")


def is_safety(column: str) -> bool:
    return column.startswith(SAFETY_PREFIXES)


def is_decimal_only(extracted: str, corrected: object) -> bool:
    """True when the judge's whole complaint is a trailing '.0'.

    The test is that the judge proposes the identical number without the '.0'.
    Matching on the word "decimal" in the issue text is not enough: the judge
    mentions the decimal in passing while objecting to something substantive,
    e.g. a rate quoted for response-evaluable patients rather than ITT.
    """
    return extracted.endswith(".0") and str(corrected) == extracted[:-2]


def recover_ci(low: str, text: str) -> str | None:
    """Upper bound for `low`, only when the abstract offers exactly one candidate."""
    highs = {
        match.group(1)
        for match in re.finditer(rf"{re.escape(low)}\s*[-,]\s*(\d*\.?\d+)", text)
    }
    if len(highs) != 1:
        return None
    return f"{low}-{highs.pop()}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation", default=str(DEFAULT_VALIDATION))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument(
        "--batch-size", type=int, default=30, help="cells per agent batch"
    )
    args = parser.parse_args()

    data = json.load(open(args.validation))
    out_dir = pathlib.Path(args.out)
    (out_dir / "batches").mkdir(parents=True, exist_ok=True)

    counts: collections.Counter = collections.Counter()
    suppressed: list[dict] = []
    auto_fixed: list[dict] = []
    agent_docs: dict[str, list[dict]] = {"safety": [], "efficacy": []}

    for document in data["documents"]:
        doc_id = document["doc_id"]
        raw = source_text(pathlib.Path(document["source_path"]), doc_id)
        if raw is None:
            counts["source unavailable"] += 1
            continue
        normalized = normalize(raw)
        arms_in_doc = [
            {"arm_id": arm["arm_id"], "arm_name": arm["arm_name"]}
            for arm in document["arms"]
        ]
        pending: dict[str, list[dict]] = {"safety": [], "efficacy": []}

        for arm in document["arms"]:
            for evaluation in arm["field_evaluations"]:
                if evaluation.get("effective_status") != "FAIL":
                    continue
                column = evaluation["field_name"]
                extracted = str(evaluation.get("extracted_value"))
                corrected = evaluation.get("corrected_value")
                issue = evaluation.get("issue_description") or ""
                record = {
                    "doc_id": doc_id,
                    "arm_id": arm["arm_id"],
                    "arm_name": arm["arm_name"],
                    "db_column": column,
                    "value_in_db": extracted,
                    "judge_says": issue,
                    "judge_corrected_value": corrected,
                    "judge_quote": evaluation.get("source_evidence_quote"),
                }

                if is_decimal_only(extracted, corrected):
                    counts["suppress (trailing .0)"] += 1
                    suppressed.append(record)
                    continue

                if column in CI_COLUMNS and not RANGE.match(extracted):
                    recovered = recover_ci(extracted, normalized)
                    if recovered:
                        # Repairs the format only. Whether the HR belongs to this arm
                        # at all is a separate question, so the cell still goes to an
                        # agent - with the range already filled in.
                        counts["auto (ci_hr format repaired)"] += 1
                        auto_fixed.append({**record, "corrected_value": recovered})
                        record["value_in_db"] = recovered
                        record["auto_repaired"] = True
                    else:
                        counts["agent (ci_hr ambiguous)"] += 1

                group = "safety" if is_safety(column) else "efficacy"
                counts[f"agent ({group})"] += 1
                pending[group].append(record)

        for group, cells in pending.items():
            if cells:
                agent_docs[group].append(
                    {
                        "doc_id": doc_id,
                        "source_text": raw.strip(),
                        "arms_in_doc": arms_in_doc,
                        "cells": cells,
                    }
                )

    for group, documents in agent_docs.items():
        batch: list[dict] = []
        size = 0
        index = 0
        for document in documents:
            batch.append(document)
            size += len(document["cells"])
            if size >= args.batch_size:
                index += 1
                path = out_dir / "batches" / f"{group}_{index:02d}.json"
                path.write_text(json.dumps(batch, indent=1))
                batch, size = [], 0
        if batch:
            index += 1
            path = out_dir / "batches" / f"{group}_{index:02d}.json"
            path.write_text(json.dumps(batch, indent=1))
        counts[f"{group} batches"] = index

    (out_dir / "suppressed.json").write_text(json.dumps(suppressed, indent=1))
    (out_dir / "auto_ci_fixes.json").write_text(json.dumps(auto_fixed, indent=1))

    print("triage:")
    for key, value in counts.most_common():
        print(f"  {key}: {value}")
    print(f"\nwrote {out_dir}")


if __name__ == "__main__":
    main()
