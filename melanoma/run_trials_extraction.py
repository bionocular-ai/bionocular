#!/usr/bin/env python3
"""CLI runner for the clinical trial parameter extraction pipeline.

Processes clinical trial export files through a single-pass LLM extraction
using the Gemini API (Gemini 3.1 Pro by default) and writes structured JSON
output to data/output/trials_extraction/.

Usage
-----
# Test run — 50 trials (default)
poetry run python run_trials_extraction.py

# Custom limit
poetry run python run_trials_extraction.py --limit 100

# Full run (all trials)
poetry run python run_trials_extraction.py --no-limit

# Last 50 trials (instead of first 50)
poetry run python run_trials_extraction.py --limit 50 --last

# Next 50 latest trials (positions 51-100 from end)
poetry run python run_trials_extraction.py --limit 50 --last --offset 50

# Use a different model
poetry run python run_trials_extraction.py --model gemini-2.5-flash

# Resume a previous run (skip already completed trials)
poetry run python run_trials_extraction.py --resume

# Dry run — validate inputs, no LLM calls
poetry run python run_trials_extraction.py --dry-run

# Filter to a specific cancer type
poetry run python run_trials_extraction.py --cancer-type "Uveal Melanoma"
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Path setup — allow running from the melanoma/ root
# ---------------------------------------------------------------------------

_MELANOMA_ROOT = Path(__file__).resolve().parent

# Load .env from melanoma/
load_dotenv(_MELANOMA_ROOT / ".env")

from src.app.trials_parameter_extraction_service import (  # noqa: E402
    ExtractionConfig,
    TrialParameterExtractionService,
)
from src.infrastructure.gemini_service import GeminiLLMService  # noqa: E402
from src.infrastructure.cost_calculator import CostCalculator  # noqa: E402

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_DEFAULT_MODEL = "gemini-3.1-pro-preview"
_DEFAULT_LIMIT = 50
_TRIALS_DB = _MELANOMA_ROOT / "data" / "trials_db" / "trials.db"
_EXPORTS_DIR = _MELANOMA_ROOT / "data" / "trials_db" / "trial_api_exports"
_OUTPUT_DIR = _MELANOMA_ROOT / "data" / "output" / "trials_extraction"

_SUPPORTED_MODELS = [
    "gemini-3.1-pro-preview",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    # Silence noisy third-party loggers
    for noisy in ("httpx", "httpcore", "openai", "langchain", "google_genai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_trials_extraction",
        description="Extract parameters from clinical trial export files via LLM.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=_DEFAULT_LIMIT,
        metavar="N",
        help=f"Maximum number of trials to process (default: {_DEFAULT_LIMIT}). "
        "Ignored when --no-limit is set.",
    )
    parser.add_argument(
        "--no-limit",
        action="store_true",
        help="Process all available trials (overrides --limit).",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        metavar="N",
        help="Skip N trials before applying --limit. With --last, skips from "
        "the end (e.g. --last --limit 50 --offset 50 yields positions 51-100 "
        "from the end). Default: 0.",
    )
    parser.add_argument(
        "--last",
        action="store_true",
        help="Apply --limit to the last N trials instead of the first N.",
    )
    parser.add_argument(
        "--model",
        default=_DEFAULT_MODEL,
        metavar="MODEL_ID",
        help=f"Gemini model identifier (default: {_DEFAULT_MODEL}). "
        f"Supported: {', '.join(_SUPPORTED_MODELS)}",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        default=True,
        help="Skip trials already recorded as done in checkpoint.json (default: on).",
    )
    parser.add_argument(
        "--no-resume",
        dest="resume",
        action="store_false",
        help="Re-process all trials, ignoring checkpoint.json.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs and log what would be processed — no LLM calls made.",
    )
    parser.add_argument(
        "--nct",
        metavar="NCT_NUMBER",
        action="append",
        dest="nct_numbers",
        help="Run only the specified NCT number(s). Can be repeated. "
        "Overrides --limit and --cancer-type.",
    )
    parser.add_argument(
        "--cancer-type",
        metavar="CANCER_TYPE",
        action="append",
        dest="cancer_types",
        help="Restrict to trials tagged with this cancer type. "
        "Can be specified multiple times. Default: all cancer types.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_OUTPUT_DIR,
        metavar="DIR",
        help=f"Output directory for results (default: {_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--exports-dir",
        type=Path,
        default=_EXPORTS_DIR,
        metavar="DIR",
        help=f"Directory containing trial .txt export files (default: {_EXPORTS_DIR}).",
    )
    parser.add_argument(
        "--trials-db",
        type=Path,
        default=_TRIALS_DB,
        metavar="PATH",
        help=f"Path to trials.db with api_discovery table (default: {_TRIALS_DB}).",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable DEBUG-level logging.",
    )

    return parser


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_env(api_key: str | None) -> str:
    if not api_key:
        print(
            "ERROR: GOOGLE_API_KEY is not set. "
            "Add it to melanoma/.env or export it as an environment variable.",
            file=sys.stderr,
        )
        sys.exit(1)
    # sys.exit raises SystemExit (NoReturn), but not all static analysers model
    # it as such.  The assert is a zero-cost hint that narrows str | None → str.
    assert api_key
    return api_key


def _validate_paths(
    trials_db: Path, exports_dir: Path
) -> None:
    errors = []
    if not trials_db.exists():
        errors.append(f"trials.db not found: {trials_db}")
    if not exports_dir.is_dir():
        errors.append(f"Exports directory not found: {exports_dir}")
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    _configure_logging(args.verbose)
    logger = logging.getLogger(__name__)

    # Vertex AI via google-genai SDK — authenticated with GOOGLE_API_KEY.
    api_key = _validate_env(os.getenv("GOOGLE_API_KEY"))

    # Validate required paths
    _validate_paths(args.trials_db, args.exports_dir)

    # Build config
    nct_numbers = [n.upper() for n in args.nct_numbers] if args.nct_numbers else None
    config = ExtractionConfig(
        trials_db_path=args.trials_db,
        exports_dir=args.exports_dir,
        output_dir=args.output_dir,
        model=args.model,
        limit=None if (args.no_limit or nct_numbers) else args.limit,
        offset=args.offset,
        last=args.last,
        resume=args.resume,
        dry_run=args.dry_run,
        cancer_type_filter=args.cancer_types or None,
        nct_allowlist=nct_numbers,
    )

    logger.info("=" * 60)
    logger.info("Clinical Trial Parameter Extraction Pipeline")
    logger.info("=" * 60)
    logger.info("Model      : %s", config.model)
    logger.info("Limit      : %s", config.limit if config.limit else "all")
    logger.info("Last       : %s", config.last)
    logger.info("Resume     : %s", config.resume)
    logger.info("Dry run    : %s", config.dry_run)
    logger.info(
        "Cancer types: %s",
        ", ".join(config.cancer_type_filter) if config.cancer_type_filter else "all",
    )
    logger.info("Output dir : %s", config.output_dir)
    logger.info("=" * 60)

    # Build and run service.
    # cost_calculator is created here and passed to both GeminiLLMService
    # and from_config so that token usage recorded during LLM calls is
    # visible to the service when it writes cost_report.json.
    cost_calculator = CostCalculator()
    llm = GeminiLLMService(
        api_key=api_key,
        model=config.model,
        cost_calculator=cost_calculator,
    )
    service = TrialParameterExtractionService.from_config(
        config,
        api_key="",
        llm_service=llm,
        cost_calculator=cost_calculator,
    )

    try:
        results = asyncio.run(service.run())
    except KeyboardInterrupt:
        logger.warning("Interrupted by user — partial results may have been saved.")
        sys.exit(130)

    # Print a quick summary table to stdout
    done = sum(1 for r in results if r.extraction_status.value == "done")
    partial = sum(1 for r in results if r.extraction_status.value == "partial")
    failed = sum(1 for r in results if r.extraction_status.value == "failed")

    print("\n" + "=" * 60)
    print("EXTRACTION COMPLETE")
    print("=" * 60)
    print(f"  Successful : {done}")
    print(f"  Partial    : {partial}")
    print(f"  Failed     : {failed}")
    print(f"  Output     : {config.output_dir / 'results.json'}")
    print(f"  Cost report: {config.output_dir / 'cost_report.json'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
