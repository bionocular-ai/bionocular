"""Publication extraction pipeline script.

Runs the enhanced extraction service against full journal publications
using Google Gemini as the LLM backend.

Only the attributes defined in the publication spec are extracted and emitted.
"""

import asyncio
import json
import logging
import os
import shutil
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
from src.domain.extraction_models import PUBLICATION_ATTRIBUTES
from src.domain.models import DocumentType
from src.infrastructure.cost_calculator import CostCalculator, ModelType
from src.infrastructure.family_extractor import FamilyExtractor
from src.infrastructure.gemini_service import GeminiLLMService
from src.infrastructure.treatment_arm_separator import TreatmentArmSeparator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ── Pipeline configuration ────────────────────────────────────────────────────
TEST_MODE = False          # Set False for full processing
MAX_PUBLICATIONS_TEST = 2  # Number of publications to process in test mode
TEST_FILE_OVERRIDE = ""    # Set to "" to use MAX_PUBLICATIONS_TEST instead

PUBLICATIONS_DIR = Path("data/postprocessed/Publications")

# Resume from a previous partial run. Set to the path of an existing
# extraction_results_Publications_*.json to skip already-processed pubs
# and append new results into that same file.
RESUME_FILE: str = "data/extraction_results_Publications_final_70.json"
# ─────────────────────────────────────────────────────────────────────────────


class PydanticJSONEncoder(json.JSONEncoder):
    def default(self, obj: object) -> object:
        if hasattr(obj, "model_dump"):
            return obj.model_dump()  # type: ignore[union-attr]
        elif hasattr(obj, "dict"):
            return obj.dict()  # type: ignore[union-attr]
        elif hasattr(obj, "__dict__"):
            return str(obj)
        return super().default(obj)


def _save_results(
    all_results: list,
    all_publications_metadata: list,
    output_file: Path,
    test_mode: bool,
    allowed_fields: set,
) -> None:
    """Write all results collected so far to the output JSON file."""
    json_results: dict = {
        "source": "publications",
        "test_mode": test_mode,
        "total_publications": len(all_results),
        "total_arms": sum(len(r.arm_results) for r in all_results) if all_results else 0,
        "total_attributes_extracted": sum(r.total_attributes_extracted for r in all_results) if all_results else 0,
        "average_confidence": sum(r.overall_confidence for r in all_results) / len(all_results) if all_results else 0,
        "total_processing_time_ms": sum(r.processing_time_ms for r in all_results) if all_results else 0,
        "publications": [],
    }

    for idx, result in enumerate(all_results):
        pub_meta = all_publications_metadata[idx] if idx < len(all_publications_metadata) else None
        if not pub_meta:
            continue

        pub_data: dict = {
            "pub_id": pub_meta["pub_id"],
            "total_arms": len(result.arm_results),
            "total_attributes_extracted": result.total_attributes_extracted,
            "overall_confidence": result.overall_confidence,
            "processing_time_ms": result.processing_time_ms,
            "errors": result.errors,
            "warnings": result.warnings,
            "arm_results": {},
        }

        for arm_id, arm_result in result.arm_results.items():
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

            # Strip to spec-only fields — prevent internal service attributes
            # from leaking into the output.
            ordered_attributes = {
                k: v for k, v in ordered_attributes.items()
                if k in allowed_fields
            }

            pub_data["arm_results"][arm_id] = {
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

        json_results["publications"].append(pub_data)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(json_results, f, indent=2, ensure_ascii=False, cls=PydanticJSONEncoder)


async def main():
    """Run the publication extraction pipeline."""
    logger.info("Starting Publication Extraction Pipeline")

    try:
        # Clean any stale vector database from previous runs
        chroma_db_path = Path("chroma_db")
        if chroma_db_path.exists():
            logger.info(f"Cleaning existing vector database: {chroma_db_path}")
            shutil.rmtree(chroma_db_path)
            logger.info("Vector database cleaned")

        # ── LLM service (Gemini) ──────────────────────────────────────────────
        logger.info("Initializing services...")

        google_api_key = os.getenv("GOOGLE_API_KEY", "")
        if not google_api_key:
            raise RuntimeError("GOOGLE_API_KEY is not set in the environment")

        cost_calculator = CostCalculator(
            default_model=ModelType.GEMINI_31_PRO_PREVIEW_DIRECT
        )
        llm_service = GeminiLLMService(
            api_key=google_api_key,
            model=ModelType.GEMINI_31_PRO_PREVIEW_DIRECT.value,
            cost_calculator=cost_calculator,
        )

        # ── Extraction components ─────────────────────────────────────────────
        arm_separator = TreatmentArmSeparator(llm_service=llm_service)
        family_extractor = FamilyExtractor(gemini=llm_service)
        extraction_service = EnhancedExtractionService(
            treatment_arm_separator=arm_separator,
            clinical_trials_api_service=None,
            enable_cost_tracking=False,  # GeminiLLMService tracks costs internally
            family_extractor=family_extractor,
            gemini=llm_service,
        )

        logger.info("Services initialized successfully")

        # ── Load publications ─────────────────────────────────────────────────
        if not PUBLICATIONS_DIR.exists():
            logger.error(f"Publications directory not found: {PUBLICATIONS_DIR}")
            return

        publication_files = sorted(PUBLICATIONS_DIR.glob("*.md"))
        if not publication_files:
            logger.error(f"No .md files found in {PUBLICATIONS_DIR}")
            return

        if TEST_MODE and TEST_FILE_OVERRIDE:
            publication_files = [f for f in publication_files if f.name == TEST_FILE_OVERRIDE]
            if not publication_files:
                logger.error(f"TEST_FILE_OVERRIDE '{TEST_FILE_OVERRIDE}' not found in {PUBLICATIONS_DIR}")
                return
            logger.info(f"(TEST MODE: targeting single file '{TEST_FILE_OVERRIDE}')")
        elif TEST_MODE and len(publication_files) > MAX_PUBLICATIONS_TEST:
            publication_files = publication_files[:MAX_PUBLICATIONS_TEST]
            logger.info(f"(TEST MODE: limiting to {MAX_PUBLICATIONS_TEST} publications)")

        # ── Load publication content ───────────────────────────────────────────
        all_publications_metadata = []
        for pub_file in publication_files:
            pub_id = pub_file.stem  # e.g. "NEJM_2024_checkmate"
            with open(pub_file, encoding="utf-8") as f:
                content = f.read()
            all_publications_metadata.append({"file": pub_file, "pub_id": pub_id, "content": content})

        logger.info(f"Loaded content for {len(all_publications_metadata)} publication(s)")

        allowed_fields = {attr.value for attr in PUBLICATION_ATTRIBUTES}

        logger.info(f"Processing {len(all_publications_metadata)} publication(s)")

        # ── Resume from prior partial run ──────────────────────────────────────
        already_done: set[str] = set()
        resume_path = Path(RESUME_FILE) if RESUME_FILE else None
        if resume_path and resume_path.exists():
            with open(resume_path, encoding="utf-8") as f:
                prior = json.load(f)
            already_done = {p["pub_id"] for p in prior.get("publications", [])}
            logger.info(f"Resuming — skipping {len(already_done)} pub(s) already in {resume_path.name}")

        # ── Extract attributes ─────────────────────────────────────────────────
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        output_file = data_dir / f"extraction_results_Publications_{timestamp}.json"
        cost_report_file = data_dir / f"cost_report_Publications_{timestamp}.json"

        all_results: list = []
        processed_metadata: list = []  # parallel to all_results — only actually-processed pubs

        for idx, pub_meta in enumerate(all_publications_metadata):
            pub_id = pub_meta["pub_id"]
            content = pub_meta["content"]

            if pub_id in already_done:
                logger.info(f"Skipping {pub_id} (already processed)")
                continue

            logger.info(f"\n{'=' * 60}")
            logger.info(f"PROCESSING PUBLICATION {idx + 1}/{len(all_publications_metadata)}: {pub_id}")
            logger.info(f"{'=' * 60}")

            try:
                result = await extraction_service.extract(content, pub_id, DocumentType.PUBLICATION)
            except Exception as exc:
                logger.error(f"Publication {pub_id} failed — skipping: {exc}")
                continue

            all_results.append(result)
            processed_metadata.append(pub_meta)

            # Save incrementally so progress is not lost on crash/kill
            _save_results(all_results, processed_metadata, output_file, TEST_MODE, allowed_fields)
            cost_calculator.save_detailed_report(str(cost_report_file))
            remaining = len(all_publications_metadata) - len(already_done)
            logger.info(f"  [incremental] Saved {len(all_results)}/{remaining} pub(s) → {output_file.name}")

            logger.info(f"Publication {pub_id} completed!")
            logger.info(f"  Arms: {len(result.arm_results)}")
            logger.info(f"  Attributes extracted: {result.total_attributes_extracted}")
            logger.info(f"  Confidence: {result.overall_confidence:.2f}")
            logger.info(f"  Processing time: {result.processing_time_ms}ms")

            for arm_id, arm_result in result.arm_results.items():
                logger.info(
                    f"  Arm {arm_id}: {arm_result.get('arm_name', 'Unknown')} — "
                    f"{arm_result.get('total_attributes', 0)} attributes"
                )
                if arm_result.get("errors"):
                    logger.warning(f"    Errors: {arm_result['errors']}")

        # ── Summary ────────────────────────────────────────────────────────────
        logger.info(f"\n{'=' * 60}")
        logger.info("EXTRACTION COMPLETED!")
        logger.info(f"{'=' * 60}")
        logger.info(f"Processed {len(all_results)} publication(s)")

        if all_results:
            total_arms = sum(len(r.arm_results) for r in all_results)
            total_attrs = sum(r.total_attributes_extracted for r in all_results)
            avg_conf = sum(r.overall_confidence for r in all_results) / len(all_results)
            total_ms = sum(r.processing_time_ms for r in all_results)

            logger.info(f"Total arms: {total_arms}")
            logger.info(f"Total attributes extracted: {total_attrs}")
            logger.info(f"Average confidence: {avg_conf:.2f}")
            logger.info(f"Total processing time: {total_ms}ms")

        # ── Final output ───────────────────────────────────────────────────────
        logger.info(f"Results saved to: {output_file}")
        logger.info(f"Cost report saved to: {cost_report_file}")

        # Print Gemini cost summary
        print(f"\n{'=' * 60}")
        print("COST SUMMARY")
        print(f"{'=' * 60}")
        cost_calculator.print_summary()

        logger.info("Publication pipeline completed successfully!")

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
