#!/usr/bin/env python3
"""Promote `cancer_type_derived` into `cancer_type` on Supabase `clinical_trials`.

This is the step users see. `cancer_type` is the filter behind every dashboard
query, `getDbCancerType()` in the web app, and the chat agent's trial retrieval,
so a bad run here is visible immediately - unlike the shadow-column backfill,
which nothing reads.

What it writes: one column, `cancer_type`, taken verbatim from the reviewed
`cancer_type_derived`. It never re-derives - the values promoted are exactly the
ones the backfill wrote and the adjudication reviewed.

Gate order, and none of it is optional:

    --backup            every row's current cancer_type, not just the changes
    --dry-run           the full before/after plan for a human to read
    --apply --nct X     one row, read back and verified
    --apply             the rest, refused without a matching backup
    --revert FILE       put every stored value back

Two guards refuse the run outright: any row whose `cancer_type_derived` is NULL
(promoting a partial backfill would blank real labels), and a missing or stale
backup.

Rows that derive to `[]` are promoted to `[]` deliberately. They stop matching
`.contains()` filters and disappear from dashboards, which is the intended
outcome for a trial that studies no skin cancer.

Usage:
    cd melanoma
    poetry run python3 scripts/promote_cancer_type.py --backup
    poetry run python3 scripts/promote_cancer_type.py --dry-run
    poetry run python3 scripts/promote_cancer_type.py --apply --nct NCT06581406
    poetry run python3 scripts/promote_cancer_type.py --apply
    poetry run python3 scripts/promote_cancer_type.py --revert data/backups/<file>.json
"""

import argparse
import csv
import json
import logging
import os
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from supabase import Client, create_client

logger = logging.getLogger(__name__)

_MELANOMA_ROOT = Path(__file__).resolve().parent.parent
_TABLE = "clinical_trials"
_PAGE_SIZE = 1000
_BACKUP_DIR = _MELANOMA_ROOT / "data" / "backups"
_DEFAULT_PLAN = (
    _MELANOMA_ROOT / "data" / "output" / "cancer_type_backfill" / "promote_plan.csv"
)


class IncompleteBackfillError(RuntimeError):
    """Raised when a row has no derived value to promote."""


# ---------------------------------------------------------------------------
# Row rules
# ---------------------------------------------------------------------------


def plan_promotions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The rows whose stored label differs from the reviewed derived one.

    Set comparison: the stored arrays are unordered, so a reordering is not a
    change and must not be written.
    """
    unbackfilled = [r["nct_id"] for r in rows if r.get("cancer_type_derived") is None]
    if unbackfilled:
        raise IncompleteBackfillError(
            f"{len(unbackfilled)} rows have no cancer_type_derived "
            f"(first: {unbackfilled[0]}). Run the backfill before promoting."
        )

    plan: list[dict[str, Any]] = []
    for row in rows:
        before = row.get("cancer_type") or []
        after = row["cancer_type_derived"]
        if set(before) == set(after):
            continue
        plan.append(
            {
                "nct_id": row["nct_id"],
                "before": before,
                "after": after,
                "empties": not after,
            }
        )
    return plan


def summarise_plan(plan: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    counts["changed"] = len(plan)
    for change in plan:
        counts["emptied" if change["empties"] else "relabelled"] += 1
    return counts


def backup_payload(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Every row's current label, not only the ones we mean to touch."""
    return {
        "table": _TABLE,
        "column": "cancer_type",
        "taken_at": datetime.now(UTC).isoformat(),
        "row_count": len(rows),
        "rows": [
            {"nct_id": r["nct_id"], "cancer_type": r.get("cancer_type")} for r in rows
        ],
    }


def write_plan(plan: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("nct_id", "before", "after", "empties"))
        for change in plan:
            writer.writerow(
                (
                    change["nct_id"],
                    " | ".join(change["before"]),
                    " | ".join(change["after"]),
                    change["empties"],
                )
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
    rows: list[dict[str, Any]] = []
    page = 0
    while True:
        resp = (
            sb.table(_TABLE)
            .select("nct_id,cancer_type,cancer_type_derived")
            .order("nct_id")
            .range(page * _PAGE_SIZE, page * _PAGE_SIZE + _PAGE_SIZE - 1)
            .execute()
        )
        rows.extend(resp.data)
        if len(resp.data) < _PAGE_SIZE:
            logger.info("Fetched %d rows from %s", len(rows), _TABLE)
            return rows
        page += 1


def backup(sb: Client) -> Path:
    rows = fetch_all(sb)
    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = _BACKUP_DIR / f"clinical_trials-cancer_type-{stamp}.json"
    path.write_text(json.dumps(backup_payload(rows), indent=2), encoding="utf-8")
    logger.info("Backup written to %s (%d rows)", path, len(rows))
    return path


def latest_backup() -> Optional[Path]:
    if not _BACKUP_DIR.is_dir():
        return None
    backups = sorted(_BACKUP_DIR.glob("clinical_trials-cancer_type-*.json"))
    return backups[-1] if backups else None


def assert_backup_matches(sb: Client) -> Path:
    path = latest_backup()
    if path is None:
        logger.error("No cancer_type backup in %s. Run --backup first.", _BACKUP_DIR)
        sys.exit(1)
    payload = json.loads(path.read_text(encoding="utf-8"))
    live = sb.table(_TABLE).select("nct_id", count="exact").limit(1).execute().count
    if payload["row_count"] != live:
        logger.error(
            "Backup %s holds %d rows but %s has %d. Take a fresh backup.",
            path,
            payload["row_count"],
            _TABLE,
            live,
        )
        sys.exit(1)
    logger.info("Backup %s matches the live table (%d rows).", path, live)
    return path


def _verify(sb: Client, nct_id: str, expected: list[str]) -> None:
    stored = (
        sb.table(_TABLE)
        .select("nct_id,cancer_type")
        .eq("nct_id", nct_id)
        .execute()
        .data
    )
    if not stored or stored[0]["cancer_type"] != expected:
        logger.error(
            "Canary %s | cancer_type read back as %r, wrote %r",
            nct_id,
            stored[0]["cancer_type"] if stored else None,
            expected,
        )
        sys.exit(1)
    logger.info("Canary %s verified: cancer_type = %r", nct_id, expected)


def apply(sb: Client, plan: list[dict[str, Any]], verify_first: bool) -> None:
    for i, change in enumerate(plan, start=1):
        resp = (
            sb.table(_TABLE)
            .update({"cancer_type": change["after"]})
            .eq("nct_id", change["nct_id"])
            .execute()
        )
        if not resp.data:
            logger.error("%s | update returned no row - stopping.", change["nct_id"])
            sys.exit(1)
        if i == 1 and verify_first:
            _verify(sb, change["nct_id"], change["after"])
        if i % 100 == 0 or i == len(plan):
            logger.info("  promoted %d/%d", i, len(plan))
    logger.info("Promoted cancer_type on %d rows.", len(plan))


def revert(sb: Client, path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload["rows"]
    logger.info("Reverting cancer_type on %d rows from %s", len(rows), path)
    for i, row in enumerate(rows, start=1):
        sb.table(_TABLE).update({"cancer_type": row["cancer_type"]}).eq(
            "nct_id", row["nct_id"]
        ).execute()
        if i % 250 == 0 or i == len(rows):
            logger.info("  reverted %d/%d", i, len(rows))
    logger.info("Revert complete: %d rows", len(rows))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backup", action="store_true", help="Dump cancer_type and exit."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Write the plan CSV. Writes no rows."
    )
    parser.add_argument(
        "--apply", action="store_true", help="Promote. Requires a matching backup."
    )
    parser.add_argument(
        "--revert", type=Path, metavar="BACKUP", help="Restore cancer_type."
    )
    parser.add_argument("--nct", help="Promote one named trial (canary).")
    parser.add_argument("--plan-out", type=Path, default=_DEFAULT_PLAN)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(message)s"
    )

    if not any((args.backup, args.dry_run, args.apply, args.revert)):
        parser.error("one of --backup, --dry-run, --apply or --revert is required")

    sb = _client()

    if args.revert:
        revert(sb, args.revert)
        return

    if args.backup:
        backup(sb)
        return

    rows = fetch_all(sb)
    try:
        plan = plan_promotions(rows)
    except IncompleteBackfillError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    if args.nct:
        plan = [c for c in plan if c["nct_id"] == args.nct]
        if not plan:
            logger.error("%s is not in the plan (already agrees, or absent).", args.nct)
            sys.exit(1)

    counts = summarise_plan(plan)
    logger.info(
        "Plan: %d changes | %d relabelled | %d emptied",
        counts["changed"],
        counts["relabelled"],
        counts["emptied"],
    )

    if args.nct:
        logger.info("Partial run: leaving %s alone.", args.plan_out)
    else:
        write_plan(plan, args.plan_out)
        logger.info("Plan written to %s", args.plan_out)

    if args.dry_run:
        logger.info("Dry run: nothing was written to %s.", _TABLE)
        return

    assert_backup_matches(sb)
    apply(sb, plan, verify_first=True)


if __name__ == "__main__":
    main()
