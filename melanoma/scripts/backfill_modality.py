#!/usr/bin/env python3
"""Backfill `modality` on Supabase `trial_landscape` from a modality-only run.

Writes exactly one column. Every other parameter on these rows was extracted by
earlier runs and is already correct, so this script must never touch them - it
uses `.update()` on `modality` alone and never `upsert()`, which would null out
the columns a partial payload omits.

Gate order, and none of it is optional:

    --backup            full-table dump, all rows, every column
    --dry-run           writes modality_backfill.json for a human to read
    --apply --limit 1   one row, verified in Supabase
    --apply             the rest

`--apply` refuses to run unless a backup exists whose row count matches the live
table, and `--revert <backup.json>` puts `modality` back, so rollback is tested
code rather than an improvised query under pressure.

Rows whose extraction came back PARTIAL (the model returned no modality) are
skipped: "could not tell" must not overwrite a stored value.

Usage:
    cd melanoma
    poetry run python3 scripts/backfill_modality.py --backup
    poetry run python3 scripts/backfill_modality.py --dry-run
    poetry run python3 scripts/backfill_modality.py --apply --limit 1
    poetry run python3 scripts/backfill_modality.py --apply
    poetry run python3 scripts/backfill_modality.py --revert data/backups/<file>.json
"""

import argparse
import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from supabase import Client, create_client

logger = logging.getLogger(__name__)

_MELANOMA_ROOT = Path(__file__).resolve().parent.parent
_RUN_DIR = _MELANOMA_ROOT / "data" / "output" / "trials_modality_backfill"
_DEFAULT_RESULTS = _RUN_DIR / "run" / "results.json"
_DEFAULT_SNAPSHOT = _RUN_DIR / "2026-07-28-clinical-trials-merged.json"
_DEFAULT_DIFF = _RUN_DIR / "modality_backfill.json"
_BACKUP_DIR = _MELANOMA_ROOT / "data" / "backups"
_CLEANED_RESULTS = (
    _MELANOMA_ROOT
    / "data"
    / "output"
    / "trials_extraction_nonindustry"
    / "results.cleaned.json"
)

_TABLE = "trial_landscape"
_PAGE_SIZE = 1000
_STATUS_DONE = "done"


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


def _fetch_all(sb: Client, columns: str) -> list[dict[str, Any]]:
    """Page through the whole table - PostgREST caps a single response."""
    rows: list[dict[str, Any]] = []
    page = 0
    while True:
        resp = (
            sb.table(_TABLE)
            .select(columns)
            .range(page * _PAGE_SIZE, page * _PAGE_SIZE + _PAGE_SIZE - 1)
            .execute()
        )
        rows.extend(resp.data)
        if len(resp.data) < _PAGE_SIZE:
            return rows
        page += 1


def preflight_update_permission(sb: Client) -> None:
    """Prove the anon key can UPDATE this table before a long run depends on it.

    `upload_nonindustry_landscape.py` shows the key can *upsert*, which says
    nothing about UPDATE - a distinct RLS policy. Writes a row's current modality
    back over itself and asserts the row comes back.
    """
    probe = sb.table(_TABLE).select("nct_id,modality").limit(1).execute().data
    if not probe:
        logger.error("Pre-flight failed: %s returned no rows to probe.", _TABLE)
        sys.exit(1)
    row = probe[0]
    resp = (
        sb.table(_TABLE)
        .update({"modality": row["modality"]})
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


# ---------------------------------------------------------------------------
# Backup / revert
# ---------------------------------------------------------------------------


def backup(sb: Client) -> Path:
    """Dump every row and every column, not just the rows we mean to touch.

    A diff only covers intended rows, so it cannot recover from a script that
    touches others.
    """
    rows = _fetch_all(sb, "*")
    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = _BACKUP_DIR / f"trial_landscape-{stamp}.json"
    path.write_text(
        json.dumps({"table": _TABLE, "row_count": len(rows), "rows": rows}, indent=2),
        encoding="utf-8",
    )
    logger.info("Backup written to %s (%d rows)", path, len(rows))
    return path


def latest_backup() -> Optional[Path]:
    if not _BACKUP_DIR.is_dir():
        return None
    backups = sorted(_BACKUP_DIR.glob("trial_landscape-*.json"))
    return backups[-1] if backups else None


def revert(sb: Client, path: Path) -> None:
    """Restore `modality` for every row in a backup file."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload["rows"]
    logger.info("Reverting modality on %d rows from %s", len(rows), path)
    for i, row in enumerate(rows, start=1):
        sb.table(_TABLE).update({"modality": row["modality"]}).eq(
            "nct_id", row["nct_id"]
        ).execute()
        if i % 200 == 0:
            logger.info("  reverted %d/%d", i, len(rows))
    logger.info("Revert complete: %d rows", len(rows))


# ---------------------------------------------------------------------------
# Diff construction
# ---------------------------------------------------------------------------


def build_diff(
    sb: Client, results_path: Path, snapshot_path: Path
) -> list[dict[str, Any]]:
    """Load the run output and pair it against the live table."""
    results = json.loads(results_path.read_text(encoding="utf-8"))["trials"]
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))["trials"]
    live = _fetch_all(sb, "nct_id,modality,treatment_name,cancer_type")
    return pair_rows(results, snapshot, live)


def pair_rows(
    results: list[dict[str, Any]],
    snapshot_rows: list[dict[str, Any]],
    live_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Pair each extracted modality with the value currently stored.

    Only DONE results with a non-empty modality are candidates; PARTIAL means
    the model could not tell, and an unchanged value is not a write.
    """
    context = {r["nct_id"]: r for r in snapshot_rows}
    live = {r["nct_id"]: r for r in live_rows}

    diff: list[dict[str, Any]] = []
    skipped_partial = 0
    skipped_unchanged = 0
    skipped_downgrade = 0
    missing = 0

    for trial in results:
        nct = trial["nct_number"]
        if trial["extraction_status"] != _STATUS_DONE or not trial["modality"]:
            skipped_partial += 1
            continue
        current = live.get(nct)
        if current is None:
            logger.warning("%s | extracted but absent from %s, skipping", nct, _TABLE)
            missing += 1
            continue

        after = "; ".join(trial["modality"])
        before = current["modality"]
        if before == after:
            skipped_unchanged += 1
            continue

        # An Other-only answer is strictly less informative than a stored value
        # that already names a class, so it is never allowed to replace one.
        # Observed on trials whose regimen mixes an unclassifiable agent with a
        # checkpoint inhibitor: the model answered for the odd agent and dropped
        # the antibody.
        if trial["modality"] == ["Other"] and _has_real_class(before):
            logger.info(
                "%s | Other-only result would replace %r, skipping", nct, before
            )
            skipped_downgrade += 1
            continue

        row = context.get(nct, {})
        diff.append(
            {
                "nct_id": nct,
                "before": before,
                "after": after,
                "study_type": row.get("study_type"),
                "treatment_name": current["treatment_name"],
                "intervention_types": sorted(
                    {
                        (i or {}).get("type")
                        for i in (row.get("interventions") or [])
                        if (i or {}).get("type")
                    }
                ),
            }
        )

    logger.info(
        "Diff: %d rows to update | skipped: %d no-modality, %d unchanged, "
        "%d Other-only downgrade, %d absent",
        len(diff),
        skipped_partial,
        skipped_unchanged,
        skipped_downgrade,
        missing,
    )
    return diff


def _has_real_class(modality: Optional[str]) -> bool:
    """True when a stored modality names something more specific than Other."""
    if not modality:
        return False
    return bool({v.strip() for v in modality.split(";")} - {"Other", ""})


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


def assert_backup_matches(sb: Client) -> Path:
    """Refuse to write without a backup that covers the current table."""
    path = latest_backup()
    if path is None:
        logger.error("No backup in %s. Run --backup first.", _BACKUP_DIR)
        sys.exit(1)
    payload = json.loads(path.read_text(encoding="utf-8"))
    live_count = (
        sb.table(_TABLE).select("nct_id", count="exact").limit(1).execute().count
    )
    if payload["row_count"] != live_count:
        logger.error(
            "Backup %s holds %d rows but %s has %d. Take a fresh backup.",
            path,
            payload["row_count"],
            _TABLE,
            live_count,
        )
        sys.exit(1)
    logger.info("Backup %s matches the live table (%d rows).", path, live_count)
    return path


def apply(sb: Client, diff: list[dict[str, Any]]) -> None:
    """Write `modality` row by row.

    692 sequential requests take a minute or two. They are deliberately not
    batched: batching this means `upsert`, and a partial-column upsert nulls out
    every column the payload omits.
    """
    for i, row in enumerate(diff, start=1):
        resp = (
            sb.table(_TABLE)
            .update({"modality": row["after"]})
            .eq("nct_id", row["nct_id"])
            .execute()
        )
        if not resp.data:
            logger.error("%s | update returned no row - stopping.", row["nct_id"])
            sys.exit(1)
        if i % 100 == 0 or i == len(diff):
            logger.info("  updated %d/%d", i, len(diff))
    logger.info("Applied %d modality updates.", len(diff))


def sync_cleaned_results(diff: list[dict[str, Any]], path: Path) -> None:
    """Rewrite `modality` in results.cleaned.json to match what we just wrote.

    `upload_nonindustry_landscape.py` upserts modality for 1679 rows straight
    from this file. Left stale, the next manual re-run of that script silently
    reverts every non-industry row this backfill touched.
    """
    if not path.exists():
        logger.warning("Cleaned results not found at %s, skipping sync.", path)
        return

    payload = json.loads(path.read_text(encoding="utf-8"))
    after_by_nct = {row["nct_id"]: row["after"].split("; ") for row in diff}
    updated = 0
    for trial in payload["trials"]:
        new_modality = after_by_nct.get(trial["nct_number"])
        if new_modality is not None and trial["modality"] != new_modality:
            trial["modality"] = new_modality
            updated += 1
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Synced %d rows in %s", updated, path)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backup", action="store_true", help="Dump the whole table and exit."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write the before/after diff for review and exit. Writes nothing.",
    )
    parser.add_argument(
        "--apply", action="store_true", help="Write modality. Requires a backup."
    )
    parser.add_argument(
        "--revert",
        type=Path,
        metavar="BACKUP",
        help="Restore modality from a backup file.",
    )
    parser.add_argument("--limit", type=int, help="Process only the first N rows.")
    parser.add_argument("--results", type=Path, default=_DEFAULT_RESULTS)
    parser.add_argument("--snapshot", type=Path, default=_DEFAULT_SNAPSHOT)
    parser.add_argument("--diff-out", type=Path, default=_DEFAULT_DIFF)
    parser.add_argument(
        "--cleaned-results",
        type=Path,
        default=_CLEANED_RESULTS,
        help="results.cleaned.json to keep in sync on --apply.",
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

    preflight_update_permission(sb)
    diff = build_diff(sb, args.results, args.snapshot)
    if args.limit:
        diff = diff[: args.limit]

    if args.dry_run:
        args.diff_out.write_text(
            json.dumps({"total": len(diff), "rows": diff}, indent=2), encoding="utf-8"
        )
        logger.info("Dry run: %d rows written to %s", len(diff), args.diff_out)
        logger.info("Nothing was written to %s.", _TABLE)
        return

    assert_backup_matches(sb)
    apply(sb, diff)
    sync_cleaned_results(diff, args.cleaned_results)


if __name__ == "__main__":
    main()
