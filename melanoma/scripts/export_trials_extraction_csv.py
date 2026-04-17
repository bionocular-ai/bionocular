#!/usr/bin/env python3
"""Convert trials_extraction results.json to results.csv.

Per-trial columns: model, prompt_tokens, completion_tokens, total_tokens, cost_usd
are joined from the sibling cost_report.json (matched by position — one API call
per trial). List fields are joined with "; ".

Usage:
  cd melanoma
  poetry run python export_trials_extraction_csv.py
  poetry run python export_trials_extraction_csv.py --input data/output/trials_extraction/results.json --output data/output/trials_extraction/results.csv
"""

import argparse
import csv
import json
import sys
from pathlib import Path


def _list_to_cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "; ".join(str(v) for v in value if v is not None)
    return str(value) if value else ""


def convert_to_csv(input_path: Path, output_path: Path) -> None:
    data = json.loads(input_path.read_text(encoding="utf-8"))
    meta = data.get("metadata", {})
    trials = data.get("trials", [])

    # Load per-trial cost data from sibling cost_report.json (matched by index)
    cost_report_path = input_path.with_name("cost_report.json")
    api_calls: list[dict] = []
    if cost_report_path.exists():
        cost_data = json.loads(cost_report_path.read_text(encoding="utf-8"))
        api_calls = cost_data.get("api_calls", [])

    run_model = meta.get("model") or ""

    fieldnames = [
        "nct_number",
        "cancer_type",
        "treatment_name",
        "modality",
        "biomarker",
        "stage",
        "line_of_therapy",
        "previous_treatment_criteria",
        "extraction_status",
        "error_message",
        "extracted_at",
        "model",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "cost_usd",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i, t in enumerate(trials):
            call = api_calls[i] if i < len(api_calls) else {}
            prompt_tokens = call.get("prompt_tokens", "")
            completion_tokens = call.get("completion_tokens", "")
            total_tokens = (
                prompt_tokens + completion_tokens
                if isinstance(prompt_tokens, int) and isinstance(completion_tokens, int)
                else ""
            )
            row = {
                "nct_number": t.get("nct_number") or "",
                "cancer_type": _list_to_cell(t.get("cancer_type")),
                "treatment_name": t.get("treatment_name") or "",
                "modality": _list_to_cell(t.get("modality")),
                "biomarker": _list_to_cell(t.get("biomarker")),
                "stage": _list_to_cell(t.get("stage")),
                "line_of_therapy": _list_to_cell(t.get("line_of_therapy")),
                "previous_treatment_criteria": _list_to_cell(
                    t.get("previous_treatment_criteria")
                ),
                "extraction_status": t.get("extraction_status") or "",
                "error_message": t.get("error_message") or "",
                "extracted_at": t.get("extracted_at") or "",
                "model": call.get("model") or run_model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "cost_usd": call.get("cost", ""),
            }
            writer.writerow(row)


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    default_input = root / "data" / "output" / "trials_extraction" / "results.json"
    default_output = root / "data" / "output" / "trials_extraction" / "results.csv"

    parser = argparse.ArgumentParser(description="Convert results.json to results.csv")
    parser.add_argument(
        "--input",
        type=Path,
        default=default_input,
        help=f"Input results.json (default: {default_input})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=default_output,
        help=f"Output results.csv (default: {default_output})",
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"ERROR: Input file not found: {args.input}", file=sys.stderr)
        return 1

    convert_to_csv(args.input, args.output)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
