"""Abstract extraction pipeline script.

Runs the enhanced extraction service against ASCO and ESMO abstracts
using Google Gemini as the LLM backend.

Output: one JSON file per conference-year in melanoma/data/.
"""

# ruff: noqa: E402 - env vars must be set before the service imports below,
# so the imports deliberately sit after that setup.

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Set env vars before any service imports
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ.setdefault("EXTRACTION_MODEL", "gemini-3.1-pro-preview")

# Load environment variables
load_dotenv()

from src.app.enhanced_extraction_service import EnhancedExtractionService
from src.domain.constants import get_ordered_attributes
from src.domain.extraction_models import ABSTRACT_ATTRIBUTES
from src.domain.models import DocumentType
from src.infrastructure.cost_calculator import CostCalculator, ModelType
from src.infrastructure.family_extractor import FamilyExtractor
from src.infrastructure.gemini_service import GeminiLLMService, vertex_env
from src.infrastructure.treatment_arm_separator import TreatmentArmSeparator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ── Pipeline configuration ────────────────────────────────────────────────────
TEST_MODE = False  # Set True for test mode (single abstract)
MAX_ABSTRACTS_TEST = 1  # Number of abstracts to process in test mode

CONFERENCES: dict[str, Path] = {
    "ASCO": Path("data/postprocessed/ASCO_Abstracts"),
    "ESMO": Path("data/postprocessed/ESMO_Abstracts"),
}
YEARS = [2020, 2021, 2022, 2023, 2024, 2025, 2026]
CONCURRENCY = 1  # Abstracts in parallel; each already fans out to the
# family extractor, and Vertex refuses the overlap (see FamilyExtractor).
# ─────────────────────────────────────────────────────────────────────────────


class _PydanticJSONEncoder(json.JSONEncoder):
    def default(self, obj: object) -> object:
        if hasattr(obj, "model_dump"):
            return obj.model_dump()  # type: ignore[union-attr]
        elif hasattr(obj, "dict"):
            return obj.dict()  # type: ignore[union-attr]
        elif hasattr(obj, "__dict__"):
            return str(obj)
        return super().default(obj)


def _serialize_result(
    result: object, abstract_meta: dict, canonical_attributes: list
) -> dict:
    """Serialize a single abstract extraction result to a JSON-safe dict."""
    allowed_fields = {attr.value for attr in canonical_attributes}

    abstract_data: dict = {
        "abstract_id": abstract_meta["abstract_id"],
        "total_arms": len(result.arm_results),  # type: ignore[union-attr]
        "total_attributes_extracted": result.total_attributes_extracted,  # type: ignore[union-attr]
        "overall_confidence": result.overall_confidence,  # type: ignore[union-attr]
        "processing_time_ms": result.processing_time_ms,  # type: ignore[union-attr]
        "errors": result.errors,  # type: ignore[union-attr]
        "warnings": result.warnings,  # type: ignore[union-attr]
        "arm_results": {},
    }

    for arm_id, arm_result in result.arm_results.items():  # type: ignore[union-attr]
        serializable_attributes: dict = {}
        for attr_type, attr_data in arm_result.get("attributes", {}).items():
            if isinstance(attr_data, dict):
                serializable_attr = {}
                for key, value in attr_data.items():
                    if hasattr(value, "model_dump"):
                        serializable_attr[key] = value.model_dump()
                    elif hasattr(value, "dict"):
                        serializable_attr[key] = value.dict()
                    elif hasattr(value, "__dict__") and not isinstance(
                        value, (str, int, float, bool, list, dict)
                    ):
                        serializable_attr[key] = str(value)
                    else:
                        serializable_attr[key] = value
                serializable_attributes[str(attr_type)] = serializable_attr
            elif hasattr(attr_data, "value"):
                clean_value = attr_data.value
                if hasattr(clean_value, "model_dump"):
                    clean_value = clean_value.model_dump()
                elif hasattr(clean_value, "dict"):
                    clean_value = clean_value.dict()
                elif hasattr(clean_value, "__dict__") and not isinstance(
                    clean_value, (str, int, float, bool, list, dict)
                ):
                    clean_value = str(clean_value)

                extracted_at = getattr(attr_data, "extracted_at", None)
                if extracted_at and hasattr(extracted_at, "isoformat"):
                    extracted_at = extracted_at.isoformat()

                serializable_attributes[str(attr_type)] = {
                    "value": clean_value,
                    "confidence": getattr(attr_data, "confidence", 0.0),
                    "source": getattr(attr_data, "source", "unknown"),
                    "validation_status": str(
                        getattr(attr_data, "validation_status", "unknown")
                    ),
                    "validation_errors": getattr(attr_data, "validation_errors", []),
                    "context_chunks": len(getattr(attr_data, "source_chunks", [])),
                    "extracted_at": extracted_at,
                }
            else:
                serializable_attributes[str(attr_type)] = attr_data

        ordered_attributes = get_ordered_attributes(serializable_attributes)
        ordered_attributes = {
            k: v for k, v in ordered_attributes.items() if k in allowed_fields
        }

        abstract_data["arm_results"][arm_id] = {
            "arm_id": arm_result.get("arm_id"),
            "arm_name": arm_result.get("arm_name"),
            "generic_name": arm_result.get("generic_name"),
            "dose": arm_result.get("dose"),
            "dosing_schedule": arm_result.get("dosing_schedule"),
            "patient_count": arm_result.get("patient_count"),
            "arm_type": arm_result.get("arm_type"),
            "combination_drugs": arm_result.get("combination_drugs", []),
            "confidence_score": arm_result.get("confidence_score", 0.0),
            "source_text": arm_result.get("source_text"),
            "total_attributes": arm_result.get("total_attributes", 0),
            "api_attributes": arm_result.get("api_attributes", 0),
            "abstract_attributes": arm_result.get("abstract_attributes", 0),
            "errors": arm_result.get("errors", []),
            "warnings": arm_result.get("warnings", []),
            "attributes": ordered_attributes,
        }

    return abstract_data


def _save_results(output_file: Path, abstracts_data: list, header: dict) -> None:
    """Write accumulated results to the output file (overwrites each time)."""
    payload = {
        **header,
        "total_abstracts": len(abstracts_data),
        "total_arms": sum(a["total_arms"] for a in abstracts_data),
        "total_attributes_extracted": sum(
            a["total_attributes_extracted"] for a in abstracts_data
        ),
        "average_confidence": (
            sum(a["overall_confidence"] for a in abstracts_data) / len(abstracts_data)
            if abstracts_data
            else 0
        ),
        "total_processing_time_ms": sum(
            a["processing_time_ms"] for a in abstracts_data
        ),
        "abstracts": abstracts_data,
    }
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, cls=_PydanticJSONEncoder)


async def _process_conference_year(
    conference: str,
    year: int,
    abstracts_dir: Path,
    extraction_service: EnhancedExtractionService,
    canonical_attributes: list,
    output_file: Path,
    concurrency: int,
) -> int:
    """Process all abstracts for a single conference-year.

    Up to `concurrency` abstracts are extracted in parallel. Results are
    accumulated in a single list guarded by a lock and flushed after every
    abstract, so an interrupted run resumes from the output file.

    Returns the number of abstracts processed.
    """
    abstract_file = abstracts_dir / f"{conference}_{year}.md"
    if not abstract_file.exists():
        logger.warning(f"Abstract file not found, skipping: {abstract_file}")
        return 0

    logger.info(f"\n{'='*80}")
    logger.info(f"STARTING {conference} {year}")
    logger.info(f"{'='*80}")

    # --- Load abstracts ---
    with open(abstract_file, encoding="utf-8") as f:
        abstract_content = f.read()

    abstracts = abstract_content.split("### Abstract ID:")[1:]
    if not abstracts:
        logger.warning(f"No abstracts found in {abstract_file.name}, skipping")
        return 0

    if TEST_MODE and len(abstracts) > MAX_ABSTRACTS_TEST:
        import random

        abstracts = random.sample(abstracts, MAX_ABSTRACTS_TEST)
        logger.info(f"  (TEST MODE: randomly sampled {MAX_ABSTRACTS_TEST} abstracts)")

    logger.info(f"Found {len(abstracts)} abstracts to process in {abstract_file.name}")

    # --- Collect per-abstract metadata ---
    abstracts_metadata = []
    for idx, abstract_text in enumerate(abstracts):
        first_line = abstract_text.strip().split("\n")[0].strip()
        raw_abstract_id = first_line if first_line else f"{idx+1:03d}"
        abstracts_metadata.append(
            {
                "year": year,
                "file": abstract_file,
                "abstract_text": "### Abstract ID:" + abstract_text,
                "abstract_id": f"{conference}_{year}_{raw_abstract_id}",
                "index": idx,
            }
        )

    # --- Resume: keep abstracts already written to the output file ---
    output_header = {"conference": conference, "year": year, "test_mode": TEST_MODE}
    serialized_abstracts: list[dict] = []
    if output_file.exists():
        with open(output_file, encoding="utf-8") as f:
            serialized_abstracts = json.load(f).get("abstracts", [])
    # Abstracts left partial by a failed family (e.g. a 429) are reprocessed, but
    # stay on disk until their replacement exists - a retry that fails must not
    # delete the partial content we already had.
    retry_ids = {
        a["abstract_id"]
        for a in serialized_abstracts
        if any(
            str(e).startswith(
                ("family_extraction_failed", "verifier_failed", "Separation failed")
            )
            for e in a.get("errors", [])
        )
    }
    done_ids = {a["abstract_id"] for a in serialized_abstracts} - retry_ids
    if serialized_abstracts:
        logger.info(
            f"Resuming {conference} {year}: {len(done_ids)} abstracts already complete, "
            f"{len(retry_ids)} partial to retry in {output_file}"
        )

    # --- Extract attributes in parallel, saving after each abstract ---
    pending = [
        meta for meta in abstracts_metadata if str(meta["abstract_id"]) not in done_ids
    ]
    logger.info(f"Extracting {len(pending)} abstracts with concurrency={concurrency}")

    processed = 0
    write_lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def _worker(abstract_meta: dict) -> None:
        nonlocal processed
        abstract_id = str(abstract_meta["abstract_id"])
        abstract_text = str(abstract_meta["abstract_text"])

        async with semaphore:
            logger.info(f"Processing abstract {abstract_id}")
            try:
                result = await extraction_service.extract(
                    abstract_text, abstract_id, DocumentType.ABSTRACT
                )
            except (
                Exception
            ) as exc:  # noqa: BLE001 - one bad abstract must not end the run
                logger.error(
                    f"Abstract {abstract_id} failed and was not saved "
                    f"(re-run to retry it): {exc}"
                )
                return

        # The result list and the output file are shared, so mutate and flush
        # under the lock - concurrent writers would interleave otherwise.
        async with write_lock:
            logger.info(f"Abstract {abstract_id} completed!")
            logger.info(f"  Arms: {len(result.arm_results)}")
            logger.info(f"  Attributes extracted: {result.total_attributes_extracted}")
            logger.info(f"  Confidence: {result.overall_confidence:.2f}")
            logger.info(f"  Processing time: {result.processing_time_ms}ms")

            for arm_id, arm_result in result.arm_results.items():
                logger.info(
                    f"  Arm {arm_id}: {arm_result.get('arm_name', 'Unknown')} - "
                    f"{arm_result.get('total_attributes', 0)} attributes"
                )
                if arm_result.get("errors"):
                    logger.warning(f"    Errors: {arm_result['errors']}")

            record = _serialize_result(result, abstract_meta, canonical_attributes)
            replaced = next(
                (
                    i
                    for i, a in enumerate(serialized_abstracts)
                    if a["abstract_id"] == abstract_id
                ),
                None,
            )
            if replaced is None:
                serialized_abstracts.append(record)
            else:
                serialized_abstracts[replaced] = record
            _save_results(output_file, serialized_abstracts, output_header)
            processed += 1
            logger.info(
                f"  Progress saved ({processed}/{len(pending)}) → {output_file}"
            )

    await asyncio.gather(*(_worker(meta) for meta in pending))

    return processed


def build_services(
    project: str, location: str
) -> tuple[EnhancedExtractionService, CostCalculator]:
    """Build the extraction service and its cost calculator."""
    cost_calculator = CostCalculator(
        default_model=ModelType.GEMINI_31_PRO_PREVIEW_DIRECT
    )
    llm_service = GeminiLLMService(
        project=project,
        location=location,
        model=ModelType.GEMINI_31_PRO_PREVIEW_DIRECT.value,
        cost_calculator=cost_calculator,
    )
    extraction_service = EnhancedExtractionService(
        treatment_arm_separator=TreatmentArmSeparator(llm_service=llm_service),
        clinical_trials_api_service=None,
        enable_cost_tracking=False,  # GeminiLLMService tracks costs internally
        family_extractor=FamilyExtractor(gemini=llm_service),
        gemini=llm_service,
    )
    return extraction_service, cost_calculator


async def main():
    """Run the abstract extraction pipeline across all conferences and years."""
    logger.info("Starting Abstract Extraction Pipeline")

    try:
        project, location = vertex_env()

        # ── Services initialized once for the entire run ──────────────────────
        logger.info("Initializing services...")
        extraction_service, cost_calculator = build_services(project, location)
        logger.info("Services initialized successfully")

        # ── Canonical attribute list ───────────────────────────────────────────
        canonical_attributes = ABSTRACT_ATTRIBUTES

        # ── Output directory ───────────────────────────────────────────────────
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        cost_report_file = data_dir / f"cost_report_{timestamp}.json"

        # ── Outer loop: conference × year ──────────────────────────────────────
        total_processed = 0
        for conference, abstracts_dir in CONFERENCES.items():
            for year in YEARS:
                output_file = data_dir / f"extraction_results_{conference}_{year}.json"
                processed = await _process_conference_year(
                    conference=conference,
                    year=year,
                    abstracts_dir=abstracts_dir,
                    extraction_service=extraction_service,
                    canonical_attributes=canonical_attributes,
                    output_file=output_file,
                    concurrency=CONCURRENCY,
                )
                total_processed += processed
                if processed:
                    logger.info(
                        f"Finished {conference} {year}: {processed} abstracts → {output_file}"
                    )
                    cost_calculator.save_detailed_report(str(cost_report_file))

        # ── Final summary ──────────────────────────────────────────────────────
        logger.info(f"\n{'='*60}")
        logger.info("EXTRACTION COMPLETED!")
        logger.info(f"{'='*60}")
        logger.info(f"Total abstracts processed: {total_processed}")

        print(f"\n{'=' * 60}")
        print("COST SUMMARY")
        print(f"{'=' * 60}")
        cost_calculator.print_summary()

        logger.info(f"Cost report saved to: {cost_report_file}")

        logger.info("Pipeline completed successfully!")

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
