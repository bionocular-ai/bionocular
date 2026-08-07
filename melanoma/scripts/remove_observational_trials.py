#!/usr/bin/env python3
"""Delete OBSERVATIONAL trials from the Supabase `trial_landscape` table.

trial_landscape describes treatment landscapes - what was given, at which line, to whom.
An observational study has no treatment arm, so those rows carry no landscape. The
snapshot pipeline has always excluded them (`_INCLUDED_STUDY_TYPES` in
download_clinical_trials_snapshot.py), but the table was populated before that filter
existed and still holds them.

The target set is resolved live from `clinical_trials.study_type`, never from a
hardcoded list, so this cannot delete a row whose type it did not just read.

Gate order, and none of it is optional:

    --dry-run           lists the rows and writes them to data/backups/ for review
    --apply --limit 1   one row, verified gone
    --apply             the rest
    --revert <file>     re-insert from the backup this script wrote

`--apply` refuses to run unless it just wrote a backup of every row it is about to
delete, and refuses if the live count of observational rows exceeds --max-delete.

Usage:
    cd melanoma
    poetry run python3 scripts/remove_observational_trials.py --dry-run
    poetry run python3 scripts/remove_observational_trials.py --apply --limit 1
    poetry run python3 scripts/remove_observational_trials.py --apply
    poetry run python3 scripts/remove_observational_trials.py --revert data/backups/<file>.json
"""

import argparse
import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from dotenv import load_dotenv
from supabase import Client, create_client

logger = logging.getLogger(__name__)

_MELANOMA_ROOT = Path(__file__).resolve().parent.parent
_BACKUP_DIR = _MELANOMA_ROOT / "data" / "backups"

_TABLE = "trial_landscape"
_TRIALS_TABLE = "clinical_trials"
_OBSERVATIONAL = "OBSERVATIONAL"

# A guard, not a target: if the live table ever reports more observational rows than
# this, something upstream changed and a human should look before anything is deleted.
_DEFAULT_MAX_DELETE = 200

_PAGE = 500


def _client() -> Client:
    load_dotenv(_MELANOMA_ROOT / ".env")
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        logger.error("SUPABASE_URL and SUPABASE_KEY must be set in melanoma/.env")
        sys.exit(1)
    return create_client(url, key)


def fetch_landscape(sb: Client) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        response = (
            sb.table(_TABLE).select("*").range(start, start + _PAGE - 1).execute()
        )
        batch = cast(list[dict[str, Any]], response.data)
        rows += batch
        if len(batch) < _PAGE:
            return rows
        start += _PAGE


def observational_ids(sb: Client, nct_ids: list[str]) -> set[str]:
    """Ask clinical_trials which of these are observational. Authoritative, live."""
    found: set[str] = set()
    for index in range(0, len(nct_ids), 200):
        chunk = nct_ids[index : index + 200]
        response = (
            sb.table(_TRIALS_TABLE)
            .select("nct_id,study_type")
            .in_("nct_id", chunk)
            .execute()
        )
        for row in cast(list[dict[str, Any]], response.data):
            if row.get("study_type") == _OBSERVATIONAL:
                found.add(row["nct_id"])
    return found


def write_backup(rows: list[dict[str, Any]], label: str) -> Path:
    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = _BACKUP_DIR / f"trial_landscape_observational_{label}_{stamp}.json"
    path.write_text(json.dumps(rows, indent=1, default=str))
    logger.info("Backed up %d rows to %s", len(rows), path)
    return path


def delete_rows(sb: Client, rows: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    for index, row in enumerate(rows, start=1):
        nct_id = row["nct_id"]
        try:
            sb.table(_TABLE).delete().eq("nct_id", nct_id).execute()
        except Exception as error:  # noqa: BLE001 - report the row, keep going
            failures.append(nct_id)
            logger.error("%s | delete failed: %s", nct_id, error)
        if index % 25 == 0:
            logger.info("  deleted %d/%d", index, len(rows))
    return failures


def still_present(sb: Client, nct_ids: list[str]) -> set[str]:
    """Which of these still have a trial_landscape row.

    Checks trial_landscape, not clinical_trials: the registry mirror keeps its row, and
    only the landscape entry is being removed.
    """
    found: set[str] = set()
    for index in range(0, len(nct_ids), 200):
        chunk = nct_ids[index : index + 200]
        response = sb.table(_TABLE).select("nct_id").in_("nct_id", chunk).execute()
        found |= {row["nct_id"] for row in cast(list[dict[str, Any]], response.data)}
    return found


def revert(sb: Client, path: Path) -> None:
    rows = json.loads(path.read_text())
    logger.info("Re-inserting %d rows from %s", len(rows), path)
    restored = 0
    for row in rows:
        sb.table(_TABLE).upsert(row, on_conflict="nct_id").execute()
        restored += 1
    logger.info("Restored %d rows", restored)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="List, write, delete none"
    )
    parser.add_argument(
        "--apply", action="store_true", help="Delete. Writes a backup first."
    )
    parser.add_argument("--revert", default=None, help="Re-insert from a backup file")
    parser.add_argument(
        "--limit", type=int, default=None, help="Delete at most N rows (smoke test)"
    )
    parser.add_argument(
        "--max-delete",
        type=int,
        default=_DEFAULT_MAX_DELETE,
        help=f"Refuse to run if more rows than this qualify (default {_DEFAULT_MAX_DELETE})",
    )
    args = parser.parse_args()

    if not (args.dry_run or args.apply or args.revert):
        parser.error("one of --dry-run, --apply or --revert is required")

    sb = _client()

    if args.revert:
        revert(sb, Path(args.revert))
        return

    landscape = fetch_landscape(sb)
    logger.info("Live %s rows: %d", _TABLE, len(landscape))

    targets = observational_ids(sb, [row["nct_id"] for row in landscape])
    rows = [row for row in landscape if row["nct_id"] in targets]
    logger.info("OBSERVATIONAL rows in %s: %d", _TABLE, len(rows))

    if not rows:
        logger.info("Nothing to do.")
        return
    if len(rows) > args.max_delete:
        logger.error(
            "%d rows qualify, above --max-delete=%d. Refusing to run.",
            len(rows),
            args.max_delete,
        )
        sys.exit(1)

    if args.limit is not None:
        rows = rows[: args.limit]
        logger.info("Restricted to %d row(s)", len(rows))

    if args.dry_run:
        write_backup(rows, "dryrun")
        logger.info("First 10 rows that would be deleted:")
        for row in rows[:10]:
            logger.info(
                "  %s | %s", row["nct_id"], (row.get("treatment_name") or "")[:60]
            )
        logger.info("[dry run] no deletes performed. Re-run with --apply.")
        return

    backup_path = write_backup(rows, "deleted")
    failures = delete_rows(sb, rows)
    logger.info("Deleted %d/%d rows", len(rows) - len(failures), len(rows))

    remaining = still_present(sb, [row["nct_id"] for row in rows])
    if remaining:
        logger.error(
            "VERIFY FAILED: %d rows still present in %s", len(remaining), _TABLE
        )
        sys.exit(1)
    logger.info("Verified: none of the deleted rows remain in %s", _TABLE)
    logger.info("Revert with: --revert %s", backup_path)
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
