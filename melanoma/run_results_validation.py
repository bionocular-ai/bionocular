#!/usr/bin/env python3
"""CLI runner for the abstract / publication results validation pipeline.

Validates an extraction run's ``extraction_results_*.json`` against the source
markdown each document was extracted from, and writes validation.json plus the
routed cohort files (results.cleaned.json, validation_hitl.json,
missed_values.json, dropped-arms.json).

Backend is Vertex AI / Gemini via ADC, same as run_trials_validation.py.

Usage
-----
# Dry run - resolve every document to a source file, spend nothing
poetry run python3 run_results_validation.py \
    --results data/output/Publications_May_2026/extraction_results_Publications_final_70.json \
    --dry-run

# Advisory (detect-only) sample run
poetry run python3 run_results_validation.py --results <results.json> --sample 3

# Gold-set spot check
poetry run python3 run_results_validation.py --results <results.json> \
    --doc-id Batch-II_1 --doc-id Batch-I_22

# Abstracts (12 conference-year files in one run)
poetry run python3 run_results_validation.py --source-type abstract \
    --results data/output/Abstracts_April_2026/extraction_results_ASCO_2023.json \
    --results data/output/Abstracts_April_2026/extraction_results_ESMO_2023.json

# Enable gated auto-fix (only after gold-set calibration)
poetry run python3 run_results_validation.py --results <results.json> \
    --apply-fixes --score-threshold 0.8
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

from src.app.results_validation_service import (  # noqa: E402
    ResultsValidationConfig,
    ResultsValidationService,
)
from src.domain.models import DocumentType  # noqa: E402
from src.infrastructure.cost_calculator import CostCalculator  # noqa: E402
from src.infrastructure.document_source_loader import (  # noqa: E402
    AbstractSourceLoader,
    DocumentSourceLoader,
    PublicationSourceLoader,
)
from src.infrastructure.gemini_service import GeminiLLMService  # noqa: E402

_DEFAULT_MODEL = "gemini-3.1-pro-preview"
_DEFAULT_SOURCE_ROOT = _MELANOMA_ROOT / "data" / "postprocessed"
_PUBLICATIONS_SUBDIR = "Publications"
_ABSTRACT_SUBDIRS = {"ASCO": "ASCO_Abstracts", "ESMO": "ESMO_Abstracts"}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_results_validation",
        description="Validate extracted abstract / publication results with an "
        "LLM judge.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--results",
        type=Path,
        action="append",
        dest="results_paths",
        required=True,
        metavar="PATH",
        help="Extraction results JSON to validate. Repeatable - abstracts are "
        "split across one file per conference-year.",
    )
    parser.add_argument(
        "--source-type",
        choices=[DocumentType.PUBLICATION.value, DocumentType.ABSTRACT.value],
        default=DocumentType.PUBLICATION.value,
        help="Which extraction pipeline produced the results (default: publication).",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=_DEFAULT_SOURCE_ROOT,
        metavar="DIR",
        help=f"Postprocessed markdown root (default: {_DEFAULT_SOURCE_ROOT}).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        metavar="DIR",
        help="Output directory (default: <results dir>/validation).",
    )
    parser.add_argument("--model", default=_DEFAULT_MODEL, metavar="MODEL_ID")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=3,
        metavar="N",
        help="Max documents judged in parallel. Each document issues 3 group "
        "calls at once, so in-flight requests are 3x this (default: 3).",
    )
    parser.add_argument(
        "--apply-fixes",
        action="store_true",
        help="Enable gated auto-fix (default: off / advisory).",
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
        help="Validate only the first N documents (after sorting/allowlist).",
    )
    parser.add_argument(
        "--doc-id",
        metavar="DOC_ID",
        action="append",
        dest="doc_ids",
        help="Validate only the given document id(s). Repeatable.",
    )
    parser.add_argument(
        "--no-resume",
        dest="resume",
        action="store_false",
        help="Re-validate all documents, ignoring the checkpoint.",
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


def _build_source_loader(source_type: str, source_dir: Path) -> DocumentSourceLoader:
    if source_type == DocumentType.PUBLICATION.value:
        return PublicationSourceLoader(source_dir / _PUBLICATIONS_SUBDIR)
    return AbstractSourceLoader(
        {
            conference: source_dir / subdir
            for conference, subdir in _ABSTRACT_SUBDIRS.items()
        }
    )


def main() -> None:
    args = _build_parser().parse_args()
    _configure_logging(args.verbose)
    logger = logging.getLogger(__name__)

    for path in args.results_paths:
        if not path.exists():
            print(f"ERROR: not found: {path}", file=sys.stderr)
            sys.exit(1)
    if not args.source_dir.exists():
        print(f"ERROR: source directory not found: {args.source_dir}", file=sys.stderr)
        sys.exit(1)

    output_dir = args.output_dir or args.results_paths[0].parent / "validation"
    config = ResultsValidationConfig(
        results_paths=args.results_paths,
        doc_type=args.source_type,
        output_dir=output_dir,
        model=args.model,
        concurrency=args.concurrency,
        apply_fixes=args.apply_fixes,
        score_threshold=args.score_threshold,
        sample=args.sample,
        resume=args.resume,
        dry_run=args.dry_run,
        doc_allowlist=args.doc_ids,
    )
    source_loader = _build_source_loader(args.source_type, args.source_dir)

    logger.info("=" * 60)
    logger.info("Results Validation Pipeline")
    logger.info("Source type : %s", config.doc_type)
    logger.info("Model       : %s", config.model)
    logger.info("Apply fixes : %s", config.apply_fixes)
    logger.info("Output dir  : %s", config.output_dir)
    logger.info("=" * 60)

    cost_calculator = CostCalculator()
    if config.dry_run:
        # No credentials needed to resolve sources and count the work.
        service = ResultsValidationService.from_config(
            config, _NullLLM(), source_loader, cost_calculator
        )
        asyncio.run(service.run())
        return

    project, location = _validate_env()
    llm = GeminiLLMService(
        model=config.model,
        cost_calculator=cost_calculator,
        project=project,
        location=location,
    )
    service = ResultsValidationService.from_config(
        config, llm, source_loader, cost_calculator
    )

    try:
        results = asyncio.run(service.run())
    except KeyboardInterrupt:
        logger.warning("Interrupted - partial results saved.")
        sys.exit(130)

    counts: dict[str, int] = {}
    for document in results:
        for arm in document.arms:
            counts[arm.decision.value] = counts.get(arm.decision.value, 0) + 1
    missed = sum(len(arm.missed_values) for d in results for arm in d.arms)

    print("\n" + "=" * 60)
    print("VALIDATION COMPLETE")
    print("=" * 60)
    print(f"  Documents: {len(results)}")
    for decision in ("kept", "fixed", "dropped", "hitl"):
        print(f"  {decision.capitalize():9} arms: {counts.get(decision, 0)}")
    print(f"  Missed values flagged: {missed}")
    cost = cost_calculator.get_summary()
    print(f"  Cost     : ${cost.total_cost:.4f} ({cost.total_tokens:,} tokens)")
    print(f"  Output   : {config.output_dir}")
    print("=" * 60)


class _NullLLM:
    """Stands in for the judge during --dry-run, which makes no LLM calls."""

    async def generate_structured(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("dry run must not call the judge")


if __name__ == "__main__":
    main()
