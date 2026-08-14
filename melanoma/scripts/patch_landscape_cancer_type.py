#!/usr/bin/env python3
"""Patch `cancer_type` on Supabase `trial_landscape` from `clinical_trials`.

`trial_landscape` keeps its own copy of the label, written by the landscape
uploaders from the same query-derived source `clinical_trials` used to carry.
`clinical_trials` has since been corrected and promoted, so the two disagree and
the landscape pages render trials under buckets the trial never studied -
NCT03340506 is a BRAF/MEK combo shown on the Uveal Melanoma page, and uveal
melanoma is GNAQ/GNA11-driven.

The source of truth is `clinical_trials.cancer_type` verbatim. This script never
re-derives: the values written are exactly the ones the backfill produced, the
adjudication reviewed and `promote_cancer_type.py` promoted.

Writes exactly one column, via `.update()` and never `upsert()` - a partial
payload upsert would null out every landscape parameter it omits.

Gate order, and none of it is optional:

    --backup            every row's current cancer_type, not just the changes
    --dry-run           the full before/after plan for a human to read
    --apply --nct X     one row, read back and verified
    --apply             the rest, refused without a matching backup
    --revert FILE       put every stored value back

One guard refuses the run outright: a landscape row with no `clinical_trials`
row behind it, since there is no reviewed value to write and guessing would
blank a real label.

Rows whose source is `[]` are patched to `[]` deliberately. They stop matching
`.contains()` and leave every landscape page, which is the intended outcome for
a trial that studies no skin cancer.

`--apply` also rewrites `cancer_type` in the cleaned extraction JSON that
`upload_nonindustry_landscape.py` upserts from. Left stale, the next manual run
of that script silently reverts the rows this patch touched.

Usage:
    cd melanoma
    poetry run python3 scripts/patch_landscape_cancer_type.py --backup
    poetry run python3 scripts/patch_landscape_cancer_type.py --dry-run
    poetry run python3 scripts/patch_landscape_cancer_type.py --apply --nct NCT03340506
    poetry run python3 scripts/patch_landscape_cancer_type.py --apply
    poetry run python3 scripts/patch_landscape_cancer_type.py --revert data/backups/<file>.json
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
_TABLE = "trial_landscape"
_SOURCE_TABLE = "clinical_trials"
_PAGE_SIZE = 1000
_BACKUP_DIR = _MELANOMA_ROOT / "data" / "backups"
# Deliberately underscore-separated: `backfill_modality.py` globs
# `trial_landscape-*.json` for its full-table dumps, and this thin one-column
# backup must never be mistaken for one.
_BACKUP_GLOB = "trial_landscape_cancer_type-*.json"
_DEFAULT_PLAN = (
    _MELANOMA_ROOT / "data" / "output" / "cancer_type_backfill" / "landscape_plan.csv"
)
_CLEANED_RESULTS = (
    _MELANOMA_ROOT
    / "data"
    / "output"
    / "trials_extraction_nonindustry"
    / "results.cleaned.json"
)


class MissingSourceRowError(RuntimeError):
    """Raised when a landscape row has no clinical_trials row behind it."""


# ---------------------------------------------------------------------------
# Row rules
# ---------------------------------------------------------------------------


def plan_patches(
    landscape_rows: list[dict[str, Any]], source_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """The landscape rows whose label differs from the corrected one.

    Set comparison: both columns are unordered `text[]`, so a reordering is not
    a change and must not be written.
    """
    source = {r["nct_id"]: r for r in source_rows}

    orphans = [r["nct_id"] for r in landscape_rows if r["nct_id"] not in source]
    if orphans:
        raise MissingSourceRowError(
            f"{len(orphans)} {_TABLE} rows have no {_SOURCE_TABLE} row "
            f"(first: {orphans[0]}). There is no reviewed value to patch them with."
        )

    plan: list[dict[str, Any]] = []
    for row in landscape_rows:
        before = row.get("cancer_type") or []
        after = source[row["nct_id"]].get("cancer_type") or []
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


def sync_cleaned_payload(payload: dict[str, Any], plan: list[dict[str, Any]]) -> int:
    """Move the cleaned extraction JSON to the values just written.

    `upload_nonindustry_landscape.py` upserts `cancer_type` for 1679 rows
    straight from this file. Left stale, its next run reverts them.
    """
    after_by_nct = {change["nct_id"]: change["after"] for change in plan}
    updated = 0
    for trial in payload["trials"]:
        after = after_by_nct.get(trial["nct_number"])
        if after is not None and trial["cancer_type"] != after:
            trial["cancer_type"] = after
            updated += 1
    return updated


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


def _fetch_all(sb: Client, table: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    page = 0
    while True:
        resp = (
            sb.table(table)
            .select("nct_id,cancer_type")
            .order("nct_id")
            .range(page * _PAGE_SIZE, page * _PAGE_SIZE + _PAGE_SIZE - 1)
            .execute()
        )
        rows.extend(resp.data)
        if len(resp.data) < _PAGE_SIZE:
            logger.info("Fetched %d rows from %s", len(rows), table)
            return rows
        page += 1


def preflight_update_permission(sb: Client) -> None:
    """Prove the key can UPDATE this table before a long run depends on it.

    The landscape uploader shows the key can *upsert*, which says nothing about
    UPDATE - a distinct RLS policy. Writes a row's current label back over
    itself and asserts the row comes back.
    """
    probe = sb.table(_TABLE).select("nct_id,cancer_type").limit(1).execute().data
    if not probe:
        logger.error("Pre-flight failed: %s returned no rows to probe.", _TABLE)
        sys.exit(1)
    row = probe[0]
    resp = (
        sb.table(_TABLE)
        .update({"cancer_type": row["cancer_type"]})
        .eq("nct_id", row["nct_id"])
        .execute()
    )
    if not resp.data:
        logger.error(
            "Pre-flight failed: UPDATE on %s returned no rows for %s. The key "
            "likely has no UPDATE policy; a SUPABASE_SECRET_KEY is needed.",
            _TABLE,
            row["nct_id"],
        )
        sys.exit(1)
    logger.info("Pre-flight OK: UPDATE permitted on %s (%s).", _TABLE, row["nct_id"])


def backup(sb: Client) -> Path:
    rows = _fetch_all(sb, _TABLE)
    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = _BACKUP_DIR / f"trial_landscape_cancer_type-{stamp}.json"
    path.write_text(json.dumps(backup_payload(rows), indent=2), encoding="utf-8")
    logger.info("Backup written to %s (%d rows)", path, len(rows))
    return path


def latest_backup() -> Optional[Path]:
    if not _BACKUP_DIR.is_dir():
        return None
    backups = sorted(_BACKUP_DIR.glob(_BACKUP_GLOB))
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
            logger.info("  patched %d/%d", i, len(plan))
    logger.info("Patched cancer_type on %d %s rows.", len(plan), _TABLE)


def sync_cleaned_results(plan: list[dict[str, Any]], path: Path) -> None:
    if not path.exists():
        logger.warning("Cleaned results not found at %s, skipping sync.", path)
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    updated = sync_cleaned_payload(payload, plan)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Synced %d rows in %s", updated, path)


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
        "--apply", action="store_true", help="Patch. Requires a matching backup."
    )
    parser.add_argument(
        "--revert", type=Path, metavar="BACKUP", help="Restore cancer_type."
    )
    parser.add_argument("--nct", help="Patch one named trial (canary).")
    parser.add_argument("--plan-out", type=Path, default=_DEFAULT_PLAN)
    parser.add_argument(
        "--cleaned-results",
        type=Path,
        default=_CLEANED_RESULTS,
        help="results.cleaned.json to keep in step on --apply.",
    )
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

    landscape_rows = _fetch_all(sb, _TABLE)
    source_rows = _fetch_all(sb, _SOURCE_TABLE)
    try:
        plan = plan_patches(landscape_rows, source_rows)
    except MissingSourceRowError as exc:
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

    preflight_update_permission(sb)
    assert_backup_matches(sb)
    apply(sb, plan, verify_first=True)
    if not args.nct:
        sync_cleaned_results(plan, args.cleaned_results)


if __name__ == "__main__":
    main()
