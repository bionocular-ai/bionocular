#!/usr/bin/env python3
"""Merge per-trial text files into fewer, larger files for NotebookLM or Gemini.

NotebookLM allows 50–600 sources per notebook (by tier); Gemini allows ~10 files
per prompt. With ~4.5k trials, use this script to bundle N trials per file so you
stay under source limits while still giving the model full trial text.

Input: directory of NCT*.txt files (from export_clinical_trial_api_fields.py).
Output: trials_batch_001.txt, trials_batch_002.txt, ... each containing many trials
with clear "=== NCT01234567 ===" separators.

Usage:
  cd melanoma
  poetry run python merge_trial_exports_for_llm.py
  poetry run python merge_trial_exports_for_llm.py --trials-per-file 100 --out-dir data/trials_db/trial_api_merged
"""

import argparse
import re
import sys
from pathlib import Path

DEFAULT_EXPORT_DIR = (
    Path(__file__).resolve().parent.parent / "data" / "trials_db" / "trial_api_exports"
)
DEFAULT_MERGED_DIR = (
    Path(__file__).resolve().parent.parent / "data" / "trials_db" / "trial_api_merged"
)
NCT_PATTERN = re.compile(r"^NCT\d+$", re.IGNORECASE)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Merge per-trial export files into batched files for NotebookLM/Gemini."
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=DEFAULT_EXPORT_DIR,
        help=f"Directory containing NCT*.txt files (default: {DEFAULT_EXPORT_DIR})",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_MERGED_DIR,
        help=f"Directory to write merged files (default: {DEFAULT_MERGED_DIR})",
    )
    parser.add_argument(
        "--trials-per-file",
        type=int,
        default=100,
        help="Number of trials per merged file (default: 100). ~45 files for 4.5k trials fits NotebookLM free 50 sources.",
    )
    args = parser.parse_args()

    if not args.export_dir.exists():
        print(f"Export directory not found: {args.export_dir}", file=sys.stderr)
        return 1

    trial_files = sorted(
        f
        for f in args.export_dir.iterdir()
        if f.is_file() and f.suffix == ".txt" and NCT_PATTERN.match(f.stem)
    )
    if not trial_files:
        print(f"No NCT*.txt files in {args.export_dir}", file=sys.stderr)
        return 1

    args.out_dir.mkdir(parents=True, exist_ok=True)
    # Remove existing batch files so the merged dir only contains batches from this run
    for path in args.out_dir.iterdir():
        if (
            path.is_file()
            and path.name.startswith("trials_batch_")
            and path.suffix == ".txt"
        ):
            path.unlink()
    batch_size = max(1, args.trials_per_file)
    batch_num = 1
    current_batch: list[str] = []

    for i, path in enumerate(trial_files):
        nct_id = path.stem
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as e:
            print(f"Warning: could not read {path}: {e}", file=sys.stderr)
            continue

        block = f"\n\n=== {nct_id} ===\n\n{content}"
        current_batch.append(block)

        if len(current_batch) >= batch_size:
            out_path = args.out_dir / f"trials_batch_{batch_num:03d}.txt"
            out_path.write_text(
                f"# Batch {batch_num} – trials {i - len(current_batch) + 2}–{i + 1}\n"
                + "".join(current_batch),
                encoding="utf-8",
            )
            print(f"Wrote {out_path.name} ({len(current_batch)} trials)")
            batch_num += 1
            current_batch = []

    if current_batch:
        out_path = args.out_dir / f"trials_batch_{batch_num:03d}.txt"
        out_path.write_text(
            f"# Batch {batch_num}\n" + "".join(current_batch),
            encoding="utf-8",
        )
        print(f"Wrote {out_path.name} ({len(current_batch)} trials)")

    print(f"Total: {batch_num} merged files in {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
