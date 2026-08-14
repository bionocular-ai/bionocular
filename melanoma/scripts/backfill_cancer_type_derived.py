#!/usr/bin/env python3
"""Backfill the `cancer_type_derived` shadow columns on Supabase `clinical_trials`.

The daily sync writes these columns, but only on the ~140 rows inside its
`--days 2` window, so most of the table still has them NULL. This derives them
for every row from the trial's own stored `conditions` - no ClinicalTrials.gov
calls, one pass.

Writes four columns and nothing else:

    cancer_type_derived, cancer_type_evidence, is_basket, melanoma_unspecified

`cancer_type` is deliberately untouched. Nothing user-visible changes until the
later promote step. Writes use `.update()` on those four columns, never
`upsert()`, which would null out every column a partial payload omits.

Gate order, and none of it is optional:

    --dry-run           report only, writes nothing
    --apply --limit 1   one row, read back and verified in Supabase
    --apply             the rest

The canary matters because nothing has yet proven Supabase accepts
`cancer_type_evidence` as jsonb; `--apply --limit 1` reads the row back and
compares it against what was sent.

`--revert` sets the four columns back to NULL, which is where they started.

Usage:
    cd melanoma
    poetry run python3 scripts/backfill_cancer_type_derived.py --dry-run
    poetry run python3 scripts/backfill_cancer_type_derived.py --apply --limit 1
    poetry run python3 scripts/backfill_cancer_type_derived.py --apply
    poetry run python3 scripts/backfill_cancer_type_derived.py --revert
"""

import argparse
import csv
import logging
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from supabase import Client, create_client

_MELANOMA_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_MELANOMA_ROOT))

from src.infrastructure.clinical_trials.cancer_type_derivation import (  # noqa: E402
    derive_cancer_types,
)

logger = logging.getLogger(__name__)

_TABLE = "clinical_trials"
_PAGE_SIZE = 1000
_NO_BUCKET = "(no bucket)"
_SHADOW_COLUMNS = (
    "cancer_type_derived",
    "cancer_type_evidence",
    "is_basket",
    "melanoma_unspecified",
)
_DEFAULT_REPORT = (
    _MELANOMA_ROOT / "data" / "output" / "cancer_type_backfill" / "derived_diff.csv"
)
_REPORT_FIELDS = (
    "nct_id",
    "conditions",
    "stored",
    "derived",
    "added",
    "removed",
    "is_basket",
    "melanoma_unspecified",
)


# ---------------------------------------------------------------------------
# Row rules
# ---------------------------------------------------------------------------


def build_payload(conditions: Optional[list[str]]) -> dict[str, Any]:
    """The four shadow columns for one trial. Never includes `cancer_type`."""
    derived = derive_cancer_types(conditions or [])
    return {
        "cancer_type_derived": derived.buckets,
        "cancer_type_evidence": derived.evidence,
        "is_basket": derived.is_basket,
        "melanoma_unspecified": derived.melanoma_unspecified,
    }


def diff_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One record per row whose derived buckets disagree with the stored label.

    Set comparison: the stored arrays are unordered, so a reordering is not a
    disagreement and must not reach the reviewer as one.
    """
    diff: list[dict[str, Any]] = []
    for row in rows:
        payload = build_payload(row.get("conditions"))
        derived = payload["cancer_type_derived"]
        stored = row.get("cancer_type") or []
        if set(stored) == set(derived):
            continue
        diff.append(
            {
                "nct_id": row["nct_id"],
                "conditions": row.get("conditions") or [],
                "stored": sorted(stored),
                "derived": derived,
                "added": sorted(set(derived) - set(stored)),
                "removed": sorted(set(stored) - set(derived)),
                "is_basket": payload["is_basket"],
                "melanoma_unspecified": payload["melanoma_unspecified"],
            }
        )
    return diff


def summarise(rows: list[dict[str, Any]]) -> Counter[str]:
    """Bucket totals across the corpus, plus the two flags and the empty rows."""
    counts: Counter[str] = Counter()
    for row in rows:
        payload = build_payload(row.get("conditions"))
        buckets = payload["cancer_type_derived"]
        counts.update(buckets or [_NO_BUCKET])
        if payload["is_basket"]:
            counts["is_basket"] += 1
        if payload["melanoma_unspecified"]:
            counts["melanoma_unspecified"] += 1
    return counts


def write_report(diff: list[dict[str, Any]], path: Path) -> None:
    """CSV of the disagreements - the input to the later triage pass."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_REPORT_FIELDS)
        writer.writeheader()
        for row in diff:
            writer.writerow(
                {
                    field: (
                        " | ".join(row[field])
                        if isinstance(row[field], list)
                        else row[field]
                    )
                    for field in _REPORT_FIELDS
                }
            )


# ---------------------------------------------------------------------------
# Supabase access
# ---------------------------------------------------------------------------


def _client() -> Client:
    load_dotenv(_MELANOMA_ROOT / ".env")
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        logger.error("SUPABASE_URL and SUPABASE_KEY must be set in melanoma/.env")
        sys.exit(1)
    return create_client(url, key)


def fetch_all(sb: Client) -> list[dict[str, Any]]:
    """Page through the table - PostgREST caps a single response."""
    rows: list[dict[str, Any]] = []
    page = 0
    while True:
        resp = (
            sb.table(_TABLE)
            .select("nct_id,conditions,cancer_type")
            .order("nct_id")
            .range(page * _PAGE_SIZE, page * _PAGE_SIZE + _PAGE_SIZE - 1)
            .execute()
        )
        rows.extend(resp.data)
        if len(resp.data) < _PAGE_SIZE:
            logger.info("Fetched %d rows from %s", len(rows), _TABLE)
            return rows
        page += 1


def _verify_canary(sb: Client, nct_id: str, payload: dict[str, Any]) -> None:
    """Read the written row back and prove Supabase kept what was sent.

    jsonb and text[] round-trips are the open question: no run has written
    `cancer_type_evidence` before this one.
    """
    stored = (
        sb.table(_TABLE)
        .select("nct_id," + ",".join(_SHADOW_COLUMNS))
        .eq("nct_id", nct_id)
        .execute()
        .data
    )
    if not stored:
        logger.error("Canary %s could not be read back.", nct_id)
        sys.exit(1)
    row = stored[0]
    for column, sent in payload.items():
        if row[column] != sent:
            logger.error(
                "Canary %s | %s round-tripped as %r, sent %r",
                nct_id,
                column,
                row[column],
                sent,
            )
            sys.exit(1)
    logger.info("Canary %s verified: %s", nct_id, {c: row[c] for c in _SHADOW_COLUMNS})


def apply(sb: Client, rows: list[dict[str, Any]], verify_first: bool) -> None:
    """Write the shadow columns row by row.

    Deliberately not batched: batching means `upsert`, and a partial-column
    upsert nulls out every column the payload omits.
    """
    for i, row in enumerate(rows, start=1):
        payload = build_payload(row.get("conditions"))
        resp = sb.table(_TABLE).update(payload).eq("nct_id", row["nct_id"]).execute()
        if not resp.data:
            logger.error(
                "%s | update returned no row - stopping. The key likely has no "
                "UPDATE policy on %s; a SUPABASE_SECRET_KEY may be needed.",
                row["nct_id"],
                _TABLE,
            )
            sys.exit(1)
        if i == 1 and verify_first:
            _verify_canary(sb, row["nct_id"], payload)
        if i % 250 == 0 or i == len(rows):
            logger.info("  updated %d/%d", i, len(rows))
    logger.info("Applied shadow columns to %d rows.", len(rows))


def revert(sb: Client, rows: list[dict[str, Any]]) -> None:
    """Put the four columns back to NULL, where they started."""
    payload: dict[str, Any] = dict.fromkeys(_SHADOW_COLUMNS)
    for i, row in enumerate(rows, start=1):
        sb.table(_TABLE).update(payload).eq("nct_id", row["nct_id"]).execute()
        if i % 250 == 0 or i == len(rows):
            logger.info("  reverted %d/%d", i, len(rows))
    logger.info("Reverted %d rows.", len(rows))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report the corpus totals and write the diff CSV. Writes nothing.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the four shadow columns. With --limit 1, verifies the row.",
    )
    parser.add_argument(
        "--revert", action="store_true", help="Set the four columns back to NULL."
    )
    parser.add_argument("--limit", type=int, help="Process only the first N rows.")
    parser.add_argument(
        "--nct",
        help="Process one named trial. Use for a canary that carries real "
        "evidence - the first row by id may derive to empty.",
    )
    parser.add_argument("--report", type=Path, default=_DEFAULT_REPORT)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(message)s"
    )

    if not any((args.dry_run, args.apply, args.revert)):
        parser.error("one of --dry-run, --apply or --revert is required")

    sb = _client()
    rows = fetch_all(sb)
    if args.nct:
        rows = [row for row in rows if row["nct_id"] == args.nct]
        if not rows:
            logger.error("%s is not in %s.", args.nct, _TABLE)
            sys.exit(1)
    if args.limit:
        rows = rows[: args.limit]

    if args.revert:
        revert(sb, rows)
        return

    diff = diff_rows(rows)
    counts = summarise(rows)
    for label, count in counts.most_common():
        logger.info("  %-46s %5d", label, count)
    logger.info("Rows disagreeing with the stored cancer_type: %d", len(diff))

    if args.limit or args.nct:
        # A partial run's report would replace a whole-corpus one with a slice.
        logger.info("Partial run: leaving %s alone.", args.report)
    else:
        write_report(diff, args.report)
        logger.info("Diff report: %s", args.report)

    if args.dry_run:
        logger.info("Dry run: nothing was written to %s.", _TABLE)
        return

    apply(sb, rows, verify_first=True)


if __name__ == "__main__":
    main()
