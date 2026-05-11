"""Abstract extraction pipeline script.

Runs the enhanced extraction service against ASCO and ESMO abstracts
using Google Gemini as the LLM backend.

Output: one JSON file per conference-year in melanoma/data/.
"""

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
from src.domain.constants import get_ordered_attribute_list, get_ordered_attributes
from src.domain.extraction_models import ABSTRACT_ATTRIBUTES
from src.domain.models import (
    ChunkingConfiguration,
    ChunkWithEmbedding,
    EmbeddingConfiguration,
)
from src.infrastructure.arm_aware_rag_provider import ArmAwareRAGContextProvider
from src.infrastructure.attribute_extractor import LLMAttributeExtractor
from src.infrastructure.cost_calculator import CostCalculator, ModelType
from src.infrastructure.family_extractor import FamilyExtractor
from src.infrastructure.gemini_service import GeminiLLMService
from src.infrastructure.langchain.chunking import LangChainChunkingService
from src.infrastructure.langchain.embeddings import LangChainEmbeddingService
from src.infrastructure.langchain.vector_store import LangChainVectorStore
from src.infrastructure.prompt_templates import ExtractionPromptTemplateProvider
from src.infrastructure.treatment_arm_separator import TreatmentArmSeparator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ── Pipeline configuration ────────────────────────────────────────────────────
TEST_MODE = False          # Set True for test mode (single abstract)
MAX_ABSTRACTS_TEST = 1     # Number of abstracts to process in test mode

CONFERENCES: dict[str, Path] = {
    "ASCO": Path("data/postprocessed/ASCO_Abstracts"),
    "ESMO": Path("data/postprocessed/ESMO_Abstracts"),
}
YEARS = [2020, 2021, 2022, 2023, 2024, 2025]
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


def _serialize_result(result: object, abstract_meta: dict, canonical_attributes: list) -> dict:
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
                    "validation_status": str(getattr(attr_data, "validation_status", "unknown")),
                    "validation_errors": getattr(attr_data, "validation_errors", []),
                    "context_chunks": len(getattr(attr_data, "source_chunks", [])),
                    "extracted_at": extracted_at,
                }
            else:
                serializable_attributes[str(attr_type)] = attr_data

        ordered_attributes = get_ordered_attributes(serializable_attributes)
        ordered_attributes = {k: v for k, v in ordered_attributes.items() if k in allowed_fields}

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
        "total_attributes_extracted": sum(a["total_attributes_extracted"] for a in abstracts_data),
        "average_confidence": (
            sum(a["overall_confidence"] for a in abstracts_data) / len(abstracts_data)
            if abstracts_data else 0
        ),
        "total_processing_time_ms": sum(a["processing_time_ms"] for a in abstracts_data),
        "abstracts": abstracts_data,
    }
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, cls=_PydanticJSONEncoder)


async def _process_conference_year(
    conference: str,
    year: int,
    abstracts_dir: Path,
    embedding_service: LangChainEmbeddingService,
    chunking_strategy: LangChainChunkingService,
    chunking_config: ChunkingConfiguration,
    arm_separator: TreatmentArmSeparator,
    attribute_extractor: LLMAttributeExtractor,
    llm_service: GeminiLLMService,
    canonical_attributes: list,
    attributes_to_extract: list,
    output_file: Path,
) -> int:
    """Process all abstracts for a single conference-year. Returns number of abstracts processed."""
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

    # --- Reset vector store for this conference-year ---
    # Use in-memory store (no persist_directory) to avoid SQLite file handle
    # conflicts between conference-years when running back-to-back.
    vector_store_service = LangChainVectorStore(
        embedding_service=embedding_service,
        collection_name="abstract_pipeline_trials",
        persist_directory=None,
    )
    rag_provider = ArmAwareRAGContextProvider(
        vector_store=vector_store_service,
        embedding_service=embedding_service,
    )
    family_extractor = FamilyExtractor(gemini=llm_service)
    extraction_service = EnhancedExtractionService(
        treatment_arm_separator=arm_separator,
        arm_aware_rag_provider=rag_provider,
        attribute_extractor=attribute_extractor,
        llm_service=llm_service,
        clinical_trials_api_service=None,
        enable_cost_tracking=False,
        family_extractor=family_extractor,
        gemini=llm_service,
    )

    # --- Chunk all abstracts for this year ---
    logger.info(f"Chunking {len(abstracts)} abstracts...")
    embedding_config = EmbeddingConfiguration()
    all_raw_chunks = []  # (abstract_idx, chunk) pairs preserving order
    abstracts_metadata = []

    for idx, abstract_text in enumerate(abstracts):
        first_line = abstract_text.strip().split("\n")[0].strip()
        raw_abstract_id = first_line if first_line else f"{idx+1:03d}"
        abstract_id = f"{conference}_{year}_{raw_abstract_id}"

        full_abstract_text = "### Abstract ID:" + abstract_text
        chunks = await chunking_strategy.chunk_content(
            content=full_abstract_text,
            configuration=chunking_config,
            document_id=abstract_id,
            filename=str(abstract_file),
        )
        for chunk in chunks:
            all_raw_chunks.append((idx, chunk))

        abstracts_metadata.append(
            {
                "year": year,
                "file": abstract_file,
                "abstract_text": abstract_text,
                "abstract_id": abstract_id,
                "index": idx,
            }
        )

    # --- Batch-embed all chunks in one vectorized pass ---
    logger.info(f"Embedding {len(all_raw_chunks)} chunks in one batch...")
    all_texts = [chunk.content for _, chunk in all_raw_chunks]
    batch_embeddings = await embedding_service.generate_embeddings_batch(all_texts, embedding_config)

    all_chunks_with_embeddings = [
        ChunkWithEmbedding(
            id=chunk.id,
            document_id=chunk.document_id,
            content=chunk.content,
            chunk_type=chunk.chunk_type,
            metadata=chunk.metadata,
            sequence_number=chunk.sequence_number,
            token_count=chunk.token_count,
            created_at=chunk.created_at,
            embedding=emb,
        )
        for (_, chunk), emb in zip(all_raw_chunks, batch_embeddings)
    ]
    logger.info(f"Embedded {len(all_chunks_with_embeddings)} chunks for {len(abstracts_metadata)} abstracts")

    await vector_store_service.upsert_chunks(all_chunks_with_embeddings)
    logger.info(
        f"Loaded {len(all_chunks_with_embeddings)} chunks for "
        f"{len(abstracts_metadata)} abstracts into vector store"
    )

    # --- Extract attributes, saving incrementally after each abstract ---
    output_header = {"conference": conference, "year": year, "test_mode": TEST_MODE}
    serialized_abstracts: list[dict] = []

    for idx, abstract_meta in enumerate(abstracts_metadata):
        abstract_id = abstract_meta["abstract_id"]
        abstract_text = abstract_meta["abstract_text"]

        logger.info(f"\n{'='*60}")
        logger.info(f"PROCESSING ABSTRACT {idx+1}/{len(abstracts_metadata)}: {abstract_id}")
        logger.info(f"{'='*60}")

        result = await extraction_service.extract_attributes_from_abstract_batch(
            abstract_text=abstract_text,
            abstract_id=abstract_id,
            attributes=attributes_to_extract,
            context_chunks_per_arm=10,
            similarity_threshold=0.1,
            include_api_data=False,
            file_path=str(abstract_meta["file"]),
        )

        logger.info(f"Abstract {abstract_id} completed!")
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

        serialized_abstracts.append(
            _serialize_result(result, abstract_meta, canonical_attributes)
        )
        _save_results(output_file, serialized_abstracts, output_header)
        logger.info(
            f"  Progress saved ({idx+1}/{len(abstracts_metadata)}) → {output_file}"
        )

    return len(abstracts_metadata)


async def main():
    """Run the abstract extraction pipeline across all conferences and years."""
    logger.info("Starting Abstract Extraction Pipeline")

    try:
        google_api_key = os.getenv("GOOGLE_API_KEY", "")
        if not google_api_key:
            raise RuntimeError("GOOGLE_API_KEY is not set in the environment")

        # ── Services initialized once for the entire run ──────────────────────
        logger.info("Initializing services...")

        cost_calculator = CostCalculator(
            default_model=ModelType.GEMINI_31_PRO_PREVIEW_DIRECT
        )
        llm_service = GeminiLLMService(
            api_key=google_api_key,
            model=ModelType.GEMINI_31_PRO_PREVIEW_DIRECT.value,
            cost_calculator=cost_calculator,
        )
        embedding_service = LangChainEmbeddingService()
        chunking_config = ChunkingConfiguration(
            max_chunk_size=1000,
            chunk_overlap=200,
            preserve_tables=True,
            include_headers=True,
        )
        chunking_strategy = LangChainChunkingService(chunking_config)
        arm_separator = TreatmentArmSeparator(llm_service=llm_service)
        prompt_provider = ExtractionPromptTemplateProvider()
        attribute_extractor = LLMAttributeExtractor(
            llm_service=llm_service,
            prompt_provider=prompt_provider,
        )

        logger.info("Services initialized successfully")

        # ── Canonical attribute list ───────────────────────────────────────────
        canonical_attributes = ABSTRACT_ATTRIBUTES

        attributes_to_extract = get_ordered_attribute_list(canonical_attributes)

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
                if output_file.exists():
                    logger.info(f"Skipping {conference} {year} — output already exists: {output_file}")
                    continue
                processed = await _process_conference_year(
                    conference=conference,
                    year=year,
                    abstracts_dir=abstracts_dir,
                    embedding_service=embedding_service,
                    chunking_strategy=chunking_strategy,
                    chunking_config=chunking_config,
                    arm_separator=arm_separator,
                    attribute_extractor=attribute_extractor,
                    llm_service=llm_service,
                    canonical_attributes=canonical_attributes,
                    attributes_to_extract=attributes_to_extract,
                    output_file=output_file,
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
