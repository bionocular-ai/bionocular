"""Run RAG + LLM extraction for specific abstract-level attributes on ASCO abstracts.

This script extracts the following attributes that had extraction issues in previous runs:
- ABSTRACT_NUMBER
- COMMENTS
- NCT_NUMBER
- MECHANISM_OF_ACTION
- TARGET_PROTEIN
- NUMBER_OF_PATIENTS
"""

import asyncio
import json
import logging
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from src.app.enhanced_extraction_service import EnhancedExtractionService
from src.domain.extraction_models import AttributeType
from src.domain.models import (
    ChunkingConfiguration,
    ChunkWithEmbedding,
    EmbeddingConfiguration,
)
from src.infrastructure.arm_aware_rag_provider import ArmAwareRAGContextProvider
from src.infrastructure.attribute_extractor import LLMAttributeExtractor
from src.infrastructure.clinical_trials_api_service import ClinicalTrialsAPIService
from src.infrastructure.cost_calculator import CostCalculator
from src.infrastructure.cost_tracking_llm_service import CostTrackingLLMService
from src.infrastructure.database_setup import DatabaseSetup
from src.infrastructure.langchain.chunking import LangChainChunkingService
from src.infrastructure.langchain.embeddings import LangChainEmbeddingService
from src.infrastructure.langchain.llm import LangChainLLMService
from src.infrastructure.langchain.vector_store import LangChainVectorStore
from src.infrastructure.prompt_templates import ExtractionPromptTemplateProvider
from src.infrastructure.treatment_arm_separator import TreatmentArmSeparator

# Set tokenizer parallelism to avoid warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    """Main extraction function for ASCO abstract attributes."""
    logger.info("Starting ASCO Abstract Attribute Extraction")
    logger.info(
        "Attributes to extract: ABSTRACT_NUMBER, COMMENTS, NCT_NUMBER, MECHANISM_OF_ACTION, TARGET_PROTEIN"
    )

    try:
        # Clean vector database to avoid conflicts/duplicates
        chroma_db_path = Path("chroma_db")
        if chroma_db_path.exists():
            logger.info(f"🗑️  Cleaning existing vector database: {chroma_db_path}")
            shutil.rmtree(chroma_db_path)
            logger.info("✅ Vector database cleaned")

        # Initialize services
        logger.info("Initializing services...")

        # Database setup
        db_setup = DatabaseSetup()
        db_setup.setup_database()

        # LLM service with cost tracking
        base_llm_service = LangChainLLMService()

        # Get preferred model for cost tracking
        from src.infrastructure.cost_calculator import ModelType

        preferred_model_str = os.getenv("EXTRACTION_MODEL", "gpt-4o")
        preferred_model = (
            ModelType.GPT_4O
            if preferred_model_str == "gpt-4o"
            else ModelType.GPT_4O_MINI
        )

        cost_calculator = CostCalculator(default_model=preferred_model)
        llm_service = CostTrackingLLMService(base_llm_service, cost_calculator)

        # Embedding service
        embedding_service = LangChainEmbeddingService()

        # Vector store service
        vector_store_service = LangChainVectorStore(
            embedding_service=embedding_service,
            collection_name="asco_abstract_attributes",
        )

        # Chunking strategy
        chunking_config = ChunkingConfiguration(
            max_chunk_size=1000,
            chunk_overlap=200,
            preserve_tables=True,
            include_headers=True,
        )
        chunking_strategy = LangChainChunkingService(chunking_config)

        # RAG context provider
        rag_provider = ArmAwareRAGContextProvider(
            vector_store=vector_store_service,
            embedding_service=embedding_service,
        )

        # Treatment arm separator
        arm_separator = TreatmentArmSeparator(llm_service=llm_service)

        # Attribute extractor
        prompt_provider = ExtractionPromptTemplateProvider()
        attribute_extractor = LLMAttributeExtractor(
            llm_service=llm_service,
            prompt_provider=prompt_provider,
        )

        # Clinical Trials API service
        api_service = ClinicalTrialsAPIService("data/doctorci.db")

        # Test API connection
        if api_service.test_connection():
            logger.info("Clinical Trials API service connected successfully")
        else:
            logger.warning("Clinical Trials API service connection failed")
            api_service = None

        # Enhanced extraction service
        extraction_service = EnhancedExtractionService(
            treatment_arm_separator=arm_separator,
            arm_aware_rag_provider=rag_provider,
            attribute_extractor=attribute_extractor,
            llm_service=llm_service,
            clinical_trials_api_service=api_service,
        )

        logger.info("Services initialized successfully")

        # Define attributes to extract
        attributes_to_extract = [
            AttributeType.ABSTRACT_NUMBER,
            AttributeType.COMMENTS,
            AttributeType.NCT_NUMBER,
            AttributeType.MECHANISM_OF_ACTION,
            AttributeType.TARGET_PROTEIN,
            AttributeType.NUMBER_OF_PATIENTS,
        ]

        logger.info(
            f"Extracting {len(attributes_to_extract)} attributes: {[attr.value for attr in attributes_to_extract]}"
        )

        # TEST MODE: Set to True to only process test abstracts from 2024
        TEST_MODE = False
        TEST_ABSTRACT_IDS = [
            "9512"
        ]  # Abstract ID to test (LBA9512 from ASCO_2024) - has Full Text Reference for COMMENTS testing

        if TEST_MODE:
            logger.info("=" * 80)
            logger.info("🧪 TEST MODE ENABLED")
            logger.info(
                f"   Processing only {len(TEST_ABSTRACT_IDS)} test abstracts: {TEST_ABSTRACT_IDS}"
            )
            logger.info("   Set TEST_MODE = False to process all abstracts")
            logger.info("=" * 80)

        # Process all ASCO year files
        asco_years = [2024] if TEST_MODE else [2020, 2021, 2022, 2023, 2024, 2025]
        asco_abstracts_dir = Path("data/postprocessed/ASCO_Abstracts")

        # Collect all abstracts by year
        all_abstracts_by_year = {}
        for year in asco_years:
            abstract_file = asco_abstracts_dir / f"ASCO_{year}.md"
            if not abstract_file.exists():
                logger.warning(
                    f"Abstract file not found: {abstract_file}, skipping year {year}"
                )
                continue

            logger.info(f"Loading abstracts from {abstract_file.name}...")
            with open(abstract_file, encoding="utf-8") as f:
                abstract_content = f.read()

            # Split abstracts by "### Abstract ID:" marker
            abstracts = abstract_content.split("### Abstract ID:")[1:]  # Skip header
            if not abstracts:
                logger.warning(f"No abstracts found in {abstract_file.name}")
                continue

            # Filter to test abstracts if in TEST_MODE
            if TEST_MODE and year == 2024:
                filtered_abstracts = []
                for abstract_text in abstracts:
                    # Extract abstract ID from first line
                    first_line = abstract_text.strip().split("\n")[0].strip()
                    # Match the full abstract ID pattern (e.g., "9500", "LBA9501", "9504")
                    # The first line after split should be just the ID number or LBA/TPS prefix + number
                    abstract_id_match = re.match(
                        r"^(?:LBA|TPS)?(\d+)$", first_line.strip()
                    )
                    if abstract_id_match:
                        abstract_id_num = abstract_id_match.group(1)
                        if abstract_id_num in TEST_ABSTRACT_IDS:
                            filtered_abstracts.append(abstract_text)
                            logger.info(
                                f"  Selected test abstract: {first_line.strip()}"
                            )
                abstracts = filtered_abstracts
                logger.info(
                    f"TEST MODE: Filtered to {len(abstracts)} test abstracts from {len(abstract_content.split('### Abstract ID:')) - 1} total"
                )

            all_abstracts_by_year[year] = {
                "file": abstract_file,
                "abstracts": abstracts,
            }
            logger.info(f"Found {len(abstracts)} abstracts in {abstract_file.name}")

        if not all_abstracts_by_year:
            logger.error("No abstract files found to process")
            return

        # Load all abstracts into vector store (by year, sequentially)
        logger.info(
            "Loading abstract data into vector store (by year, sequentially)..."
        )

        all_chunks_with_embeddings = []
        embedding_config = EmbeddingConfiguration()
        all_abstracts_metadata = []  # Store metadata for processing later

        # Process each year sequentially
        for year in sorted(all_abstracts_by_year.keys()):
            year_data = all_abstracts_by_year[year]
            abstract_file = year_data["file"]
            abstracts = year_data["abstracts"]

            logger.info(f"\n{'='*60}")
            logger.info(f"Loading year {year}: {len(abstracts)} abstracts")
            logger.info(f"{'='*60}")

            for idx, abstract_text in enumerate(abstracts):
                # Extract ASCO abstract ID from the text
                # Format: "### Abstract ID: 10003" or "10003" (after split)
                first_line = abstract_text.strip().split("\n")[0].strip()
                # Extract number from first line (could be "10003" or "### Abstract ID: 10003")
                id_match = re.search(r"(\d+)", first_line)
                if id_match:
                    asco_abstract_id = id_match.group(1)
                else:
                    asco_abstract_id = f"{idx+1:03d}"
                abstract_id = f"ASCO_{year}_{asco_abstract_id}"

                logger.info(
                    f"  Loading abstract {idx+1}/{len(abstracts)}: {abstract_id}"
                )

                # Prepend "### Abstract ID:" back to the abstract text for proper chunking
                full_abstract_text = "### Abstract ID:" + abstract_text

                # Create chunks from the abstract text
                chunks = await chunking_strategy.chunk_content(
                    content=full_abstract_text,
                    configuration=chunking_config,
                    document_id=abstract_id,
                    filename=str(abstract_file),
                )

                # Generate embeddings for chunks
                for chunk in chunks:
                    embedding = await embedding_service.generate_embedding(
                        chunk.content, embedding_config
                    )
                    chunk_with_embedding = ChunkWithEmbedding(
                        id=chunk.id,
                        document_id=chunk.document_id,
                        content=chunk.content,
                        chunk_type=chunk.chunk_type,
                        metadata=chunk.metadata,
                        sequence_number=chunk.sequence_number,
                        token_count=chunk.token_count,
                        created_at=chunk.created_at,
                        embedding=embedding,
                    )
                    all_chunks_with_embeddings.append(chunk_with_embedding)

                # Store metadata for processing
                all_abstracts_metadata.append(
                    {
                        "year": year,
                        "file": abstract_file,
                        "abstract_text": abstract_text,
                        "abstract_id": abstract_id,
                        "asco_abstract_id": asco_abstract_id,
                        "index": idx,
                    }
                )

        # Store all chunks in vector store using upsert (prevents duplicates)
        # Batch chunks to avoid ChromaDB batch size limit (max ~5461)
        BATCH_SIZE = 5000
        total_chunks = len(all_chunks_with_embeddings)
        logger.info(f"Storing {total_chunks} chunks in batches of {BATCH_SIZE}...")

        for i in range(0, total_chunks, BATCH_SIZE):
            batch = all_chunks_with_embeddings[i : i + BATCH_SIZE]
            batch_num = (i // BATCH_SIZE) + 1
            total_batches = (total_chunks + BATCH_SIZE - 1) // BATCH_SIZE
            logger.info(
                f"Storing batch {batch_num}/{total_batches} ({len(batch)} chunks)..."
            )
            await vector_store_service.upsert_chunks(batch)

        logger.info(
            f"\n✅ Loaded {len(all_chunks_with_embeddings)} chunks for {len(all_abstracts_metadata)} abstracts into vector store"
        )

        logger.info(
            f"Extracting {len(attributes_to_extract)} attributes for {len(all_abstracts_metadata)} abstracts"
        )

        # Process each abstract sequentially (by year, then by abstract within year)
        all_results = []
        current_year = None

        for idx, abstract_meta in enumerate(all_abstracts_metadata):
            year = abstract_meta["year"]
            abstract_text = abstract_meta["abstract_text"]
            abstract_id = abstract_meta["abstract_id"]
            abstract_file = abstract_meta["file"]

            # Log year header when year changes
            if current_year != year:
                current_year = year
                logger.info(f"\n{'='*80}")
                logger.info(f"PROCESSING YEAR {year}")
                logger.info(f"{'='*80}")

            logger.info(f"\n{'='*60}")
            logger.info(
                f"PROCESSING ABSTRACT {idx+1}/{len(all_abstracts_metadata)}: {abstract_id} (Year {year})"
            )
            logger.info(f"{'='*60}")

            # Perform extraction using batch method
            result = await extraction_service.extract_attributes_from_abstract_batch(
                abstract_text=abstract_text,
                abstract_id=abstract_id,
                attributes=attributes_to_extract,
                context_chunks_per_arm=10,
                similarity_threshold=0.1,
                include_api_data=True,
                file_path=str(
                    abstract_file
                ),  # Pass file path for Conference/Year extraction
            )

            all_results.append(result)

            # Display results for this abstract
            logger.info(f"Abstract {abstract_id} completed!")
            logger.info(f"Total arms: {len(result.arm_results)}")
            logger.info(
                f"Total attributes extracted: {result.total_attributes_extracted}"
            )
            logger.info(f"Overall confidence: {result.overall_confidence:.2f}")
            logger.info(f"Processing time: {result.processing_time_ms}ms")

            # Display per-arm results
            for arm_id, arm_result in result.arm_results.items():
                logger.info(
                    f"\n--- Arm {arm_id}: {arm_result.get('arm_name', 'Unknown')} ---"
                )
                logger.info(
                    f"Total attributes: {arm_result.get('total_attributes', 0)}"
                )

                # Show extracted attribute values
                attributes = arm_result.get("attributes", {})
                for attr_type in attributes_to_extract:
                    attr_data = attributes.get(attr_type)
                    if attr_data:
                        if hasattr(attr_data, "value"):
                            value = attr_data.value
                        elif isinstance(attr_data, dict):
                            value = attr_data.get("value", "N/A")
                        else:
                            value = attr_data
                        logger.info(f"  {attr_type.value}: {value}")

                if arm_result.get("errors"):
                    logger.warning(f"Errors: {arm_result['errors']}")

                if arm_result.get("warnings"):
                    logger.warning(f"Warnings: {arm_result['warnings']}")

        # Display overall results
        logger.info(f"\n{'='*60}")
        logger.info("EXTRACTION COMPLETED!")
        logger.info(f"{'='*60}")
        logger.info(f"Processed {len(all_results)} abstracts")

        if all_results:
            total_arms = sum(len(result.arm_results) for result in all_results)
            total_attributes = sum(
                result.total_attributes_extracted for result in all_results
            )
            avg_confidence = sum(
                result.overall_confidence for result in all_results
            ) / len(all_results)
            total_time = sum(result.processing_time_ms for result in all_results)

            logger.info(f"Total arms across all abstracts: {total_arms}")
            logger.info(f"Total attributes extracted: {total_attributes}")
            logger.info(f"Average confidence: {avg_confidence:.2f}")
            logger.info(f"Total processing time: {total_time}ms")

        # Print cost summary
        print(f"\n{'='*60}")
        print("COST SUMMARY")
        print(f"{'='*60}")
        cost_calculator.print_summary()

        # Save results to JSON file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        test_suffix = "_TEST" if TEST_MODE else ""
        output_file = (
            f"asco_abstract_attributes_extraction{test_suffix}_{timestamp}.json"
        )
        cost_report_file = f"cost_report_asco_attributes{test_suffix}_{timestamp}.json"

        # Prepare results for JSON serialization
        json_results = {
            "extraction_type": "ASCO Abstract Attributes (RAG + LLM)",
            "attributes_extracted": [attr.value for attr in attributes_to_extract],
            "total_abstracts": len(all_results),
            "total_arms": sum(len(result.arm_results) for result in all_results)
            if all_results
            else 0,
            "total_attributes_extracted": sum(
                result.total_attributes_extracted for result in all_results
            )
            if all_results
            else 0,
            "average_confidence": sum(
                result.overall_confidence for result in all_results
            )
            / len(all_results)
            if all_results
            else 0,
            "total_processing_time_ms": sum(
                result.processing_time_ms for result in all_results
            )
            if all_results
            else 0,
            "abstracts": [],
        }

        # Convert all results to JSON-serializable format
        for idx, result in enumerate(all_results):
            # Get metadata for this abstract
            abstract_meta = (
                all_abstracts_metadata[idx]
                if idx < len(all_abstracts_metadata)
                else None
            )
            if not abstract_meta:
                continue

            abstract_id = abstract_meta["abstract_id"]
            year = abstract_meta["year"]
            abstract_data = {
                "abstract_id": abstract_id,
                "year": year,
                "total_arms": len(result.arm_results),
                "total_attributes_extracted": result.total_attributes_extracted,
                "overall_confidence": result.overall_confidence,
                "processing_time_ms": result.processing_time_ms,
                "errors": result.errors,
                "warnings": result.warnings,
                "arm_results": {},
            }

            # Convert arm results to JSON-serializable format
            for arm_id, arm_result in result.arm_results.items():
                # Convert attributes to JSON-serializable format
                serializable_attributes = {}
                for attr_type in attributes_to_extract:
                    attr_data = arm_result.get("attributes", {}).get(attr_type)
                    if attr_data:
                        # Handle different types of attribute data
                        if isinstance(attr_data, dict):
                            # Dictionary format - convert values to JSON-serializable
                            serializable_attr = {}
                            for key, value in attr_data.items():
                                if hasattr(value, "__dict__") and not isinstance(
                                    value, (str, int, float, bool, list, dict)
                                ):
                                    # Convert Pydantic models to their string representation
                                    serializable_attr[key] = str(value)
                                elif hasattr(value, "model_dump"):
                                    # Handle Pydantic v2 models
                                    serializable_attr[key] = value.model_dump()
                                elif hasattr(value, "dict"):
                                    # Handle Pydantic v1 models
                                    serializable_attr[key] = value.dict()
                                else:
                                    serializable_attr[key] = value
                            serializable_attributes[attr_type.value] = serializable_attr
                        elif hasattr(attr_data, "value"):
                            # Pydantic model format - extract clean value
                            clean_value = attr_data.value
                            if hasattr(clean_value, "__dict__") and not isinstance(
                                clean_value, (str, int, float, bool, list, dict)
                            ):
                                # Convert Pydantic models to their string representation
                                clean_value = str(clean_value)
                            elif hasattr(clean_value, "model_dump"):
                                # Handle Pydantic v2 models
                                clean_value = clean_value.model_dump()
                            elif hasattr(clean_value, "dict"):
                                # Handle Pydantic v1 models
                                clean_value = clean_value.dict()

                            # Handle datetime serialization
                            extracted_at = getattr(attr_data, "extracted_at", None)
                            if extracted_at and hasattr(extracted_at, "isoformat"):
                                extracted_at = extracted_at.isoformat()

                            serializable_attributes[attr_type.value] = {
                                "value": clean_value,
                                "confidence": getattr(attr_data, "confidence", 0.0),
                                "source": getattr(attr_data, "source", "unknown"),
                                "validation_status": str(
                                    getattr(attr_data, "validation_status", "unknown")
                                ),
                                "validation_errors": getattr(
                                    attr_data, "validation_errors", []
                                ),
                                "context_chunks": len(
                                    getattr(attr_data, "source_chunks", [])
                                ),
                                "extracted_at": extracted_at,
                            }
                        else:
                            # Direct value format
                            serializable_attributes[attr_type.value] = attr_data
                    else:
                        # Attribute not found
                        serializable_attributes[attr_type.value] = None

                abstract_data["arm_results"][arm_id] = {
                    "arm_id": arm_result.get("arm_id"),
                    "arm_name": arm_result.get("arm_name"),
                    "total_attributes": arm_result.get("total_attributes", 0),
                    "api_attributes": arm_result.get("api_attributes", 0),
                    "abstract_attributes": arm_result.get("abstract_attributes", 0),
                    "errors": arm_result.get("errors", []),
                    "warnings": arm_result.get("warnings", []),
                    "attributes": serializable_attributes,
                }

            json_results["abstracts"].append(abstract_data)

        with open(output_file, "w", encoding="utf-8") as f:
            # Custom JSON encoder to handle Pydantic models
            class PydanticJSONEncoder(json.JSONEncoder):
                def default(self, obj):
                    if hasattr(obj, "model_dump"):
                        return obj.model_dump()
                    elif hasattr(obj, "dict"):
                        return obj.dict()
                    elif hasattr(obj, "__dict__"):
                        return str(obj)
                    return super().default(obj)

            json.dump(
                json_results, f, indent=2, ensure_ascii=False, cls=PydanticJSONEncoder
            )

        logger.info(f"Results saved to: {output_file}")

        # Save cost report
        cost_calculator.save_detailed_report(cost_report_file)
        logger.info(f"Cost report saved to: {cost_report_file}")

        logger.info("\n✅ ASCO abstract attribute extraction completed successfully!")

    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
