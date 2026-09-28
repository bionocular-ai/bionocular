#!/usr/bin/env python3
"""Record a pharmacology expert's verdict on trial_outcomes sources.

The expert reviews a source (a conference abstract or a publication) against its
document, so the verdict is written to every arm row that source produced. Only
`expert_review` and `expert_reviewed_at` are touched, with `.update()` - never
`upsert()`, which would null the columns a partial payload omits.

Dry run by default: prints the rows each source id matches and their current
verdict. `--apply` refuses if any id matches no row (a typo must not pass
silently), writes, then re-reads and checks every row.

Usage:
    cd melanoma
    poetry run python3 scripts/record_expert_review.py --verdict good ASCO_2025_9551 ASCO_2023_9511
    poetry run python3 scripts/record_expert_review.py --verdict good ASCO_2025_9551 --apply

Undo is a write of the previous values the dry run printed, or for a source
never reviewed before, `update trial_outcomes set expert_review = null,
expert_reviewed_at = null where abstract_id = '...'` in the SQL editor.
"""

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from supabase import Client, create_client

_MELANOMA_ROOT = Path(__file__).resolve().parent.parent
_TABLE = "trial_outcomes"
_VERDICTS = ("good", "issues")
# A source id is an abstract id (ASCO_2025_9551) or a publication id; both are
# checked, so the caller does not have to say which.
_SOURCE_COLUMNS = ("abstract_id", "publication_id")
_SHOWN = "id, abstract_id, publication_id, arm_name, expert_review, expert_reviewed_at"


def _client() -> Client:
    load_dotenv(_MELANOMA_ROOT / ".env")
    url = os.environ.get("SUPABASE_URL")
    # trial_outcomes RLS blocks the anon key; writes need the secret key.
    key = os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("SUPABASE_KEY")
    if not url or not key:
        sys.exit("SUPABASE_URL and SUPABASE_SECRET_KEY must be set in melanoma/.env")
    return create_client(url, key)


def _rows_for(sb: Client, source_id: str) -> tuple[str, list[dict[str, Any]]]:
    """The column the id lives in, and the rows it matches there."""
    for column in _SOURCE_COLUMNS:
        rows = sb.table(_TABLE).select(_SHOWN).eq(column, source_id).execute().data
        if rows:
            return column, rows
    return "", []


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("sources", nargs="+", help="abstract or publication ids")
    parser.add_argument("--verdict", required=True, choices=_VERDICTS)
    parser.add_argument(
        "--apply", action="store_true", help="write (default is a dry run)"
    )
    args = parser.parse_args()

    sb = _client()
    matched: dict[str, tuple[str, list[dict[str, Any]]]] = {}
    for source_id in args.sources:
        column, rows = _rows_for(sb, source_id)
        matched[source_id] = (column, rows)
        print(f"{source_id}: {len(rows)} row(s)" + (f" by {column}" if column else ""))
        for row in rows:
            print(
                f"  {row['id']}  {row['arm_name']!r}  now: {row['expert_review']} {row['expert_reviewed_at']}"
            )

    missing = [source_id for source_id, (_, rows) in matched.items() if not rows]
    if missing:
        sys.exit(f"No rows for {', '.join(missing)}; nothing written.")
    if not args.apply:
        print(f"\nDry run. Re-run with --apply to mark these {args.verdict!r}.")
        return

    reviewed_at = datetime.now(UTC).isoformat()
    for source_id, (column, _) in matched.items():
        sb.table(_TABLE).update(
            {"expert_review": args.verdict, "expert_reviewed_at": reviewed_at}
        ).eq(column, source_id).execute()

    wrong = [
        row["id"]
        for source_id, (column, _) in matched.items()
        for row in _rows_for(sb, source_id)[1]
        if row["expert_review"] != args.verdict
    ]
    if wrong:
        sys.exit(f"Verification failed for {wrong}")
    total = sum(len(rows) for _, rows in matched.values())
    print(f"\nMarked {total} row(s) {args.verdict!r} at {reviewed_at}; verified.")


if __name__ == "__main__":
    main()
