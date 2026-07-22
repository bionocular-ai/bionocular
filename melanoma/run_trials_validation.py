#!/usr/bin/env python3
"""CLI runner for the LLM-as-a-Judge trial parameter validation pipeline.

Validates an extraction run's results.json against the source snapshot and writes
validation.json plus the routed cohort files (results.cleaned.json, its
dropped-ncts companion, validation_hitl.json, corrections.json).

Backend is Vertex AI / Gemini via ADC, same as run_trials_extraction.py.

Usage
-----
# Advisory (detect-only) sample run
poetry run python3 run_trials_validation.py --snapshot data/output/trials_extraction_nonindustry/<date>-clinical-trials.json --sample 30

# Higher throughput
poetry run python3 run_trials_validation.py --snapshot <snap> --concurrency 8

# Enable gated auto-fix (only after gold-set calibration)
poetry run python3 run_trials_validation.py --snapshot <snap> --apply-fixes --score-threshold 0.8
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

_MELANOMA_ROOT = Path(__file__).resolve().parent
load_dotenv(_MELANOMA_ROOT / ".env")

from src.app.trials_validation_service import (  # noqa: E402
    TrialValidationService,
    ValidationConfig,
)
from src.infrastructure.cost_calculator import CostCalculator  # noqa: E402
from src.infrastructure.gemini_service import GeminiLLMService  # noqa: E402

_DEFAULT_MODEL = "gemini-3.1-pro-preview"
_DEFAULT_RESULTS = (
    _MELANOMA_ROOT
    / "data"
    / "output"
    / "trials_extraction_nonindustry"
    / "results.json"
)
_DEFAULT_OUTPUT_DIR = (
    _MELANOMA_ROOT / "data" / "output" / "trials_extraction_nonindustry" / "validation"
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_trials_validation",
        description="Validate extracted trial parameters with an LLM judge.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        required=True,
        metavar="PATH",
        help="Snapshot JSON the extraction run used (source of truth for grading).",
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=_DEFAULT_RESULTS,
        metavar="PATH",
        help=f"Extraction results.json to validate (default: {_DEFAULT_RESULTS}).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_DEFAULT_OUTPUT_DIR,
        metavar="DIR",
        help=f"Output directory (default: {_DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument("--model", default=_DEFAULT_MODEL, metavar="MODEL_ID")
    parser.add_argument(
        "--mode",
        choices=["online", "batch"],
        default="online",
        help="online = bounded-concurrency interactive; batch = Vertex Batch "
        "Prediction (not yet implemented).",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        metavar="N",
        help="Max in-flight judge calls in online mode (default: 5).",
    )
    parser.add_argument(
        "--apply-fixes",
        action="store_true",
        help="Enable gated auto-fix + judge-driven drops (default: off / advisory).",
    )
    parser.add_argument(
        "--score-threshold",
        type=float,
        default=0.75,
        metavar="F",
        help="Minimum validation_score for a correction to be auto-applied.",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        metavar="N",
        help="Validate only the first N trials (after sorting/allowlist).",
    )
    parser.add_argument(
        "--nct",
        metavar="NCT_NUMBER",
        action="append",
        dest="nct_numbers",
        help="Validate only the given NCT number(s). Repeatable.",
    )
    parser.add_argument(
        "--no-resume",
        dest="resume",
        action="store_false",
        help="Re-validate all trials, ignoring the checkpoint.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs and report what would run; no LLM calls.",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    for noisy in ("httpx", "httpcore", "google_genai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _validate_env() -> tuple[str, str]:
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION")
    missing = [
        name
        for name, value in (
            ("GOOGLE_CLOUD_PROJECT", project),
            ("GOOGLE_CLOUD_LOCATION", location),
        )
        if not value
    ]
    if missing:
        print(
            f"ERROR: {', '.join(missing)} is not set. Add it to melanoma/.env.",
            file=sys.stderr,
        )
        sys.exit(1)
    assert project and location
    return project, location


def main() -> None:
    args = _build_parser().parse_args()
    _configure_logging(args.verbose)
    logger = logging.getLogger(__name__)

    project, location = _validate_env()
    for path in (args.results, args.snapshot):
        if not path.exists():
            print(f"ERROR: not found: {path}", file=sys.stderr)
            sys.exit(1)

    config = ValidationConfig(
        results_path=args.results,
        snapshot_path=args.snapshot,
        output_dir=args.output_dir,
        model=args.model,
        mode=args.mode,
        concurrency=args.concurrency,
        apply_fixes=args.apply_fixes,
        score_threshold=args.score_threshold,
        sample=args.sample,
        resume=args.resume,
        dry_run=args.dry_run,
        nct_allowlist=(
            [n.upper() for n in args.nct_numbers] if args.nct_numbers else None
        ),
    )

    logger.info("=" * 60)
    logger.info("Trial Parameter Validation Pipeline")
    logger.info("Model       : %s", config.model)
    logger.info("Mode        : %s", config.mode)
    logger.info("Apply fixes : %s", config.apply_fixes)
    logger.info("Output dir  : %s", config.output_dir)
    logger.info("=" * 60)

    cost_calculator = CostCalculator()
    llm = GeminiLLMService(
        model=config.model,
        cost_calculator=cost_calculator,
        project=project,
        location=location,
    )
    service = TrialValidationService.from_config(config, llm, cost_calculator)

    try:
        results = asyncio.run(service.run())
    except KeyboardInterrupt:
        logger.warning("Interrupted - partial results saved.")
        sys.exit(130)

    counts: dict[str, int] = {}
    for r in results:
        counts[r.decision.value] = counts.get(r.decision.value, 0) + 1

    print("\n" + "=" * 60)
    print("VALIDATION COMPLETE")
    print("=" * 60)
    for decision in ("kept", "fixed", "dropped", "hitl", "error"):
        print(f"  {decision.capitalize():9}: {counts.get(decision, 0)}")
    print(f"  Output   : {config.output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
