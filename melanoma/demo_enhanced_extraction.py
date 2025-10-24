"""Demo script for enhanced extraction with comprehensive attribute support.

This script demonstrates the enhanced extraction service with:
- 60+ attributes from legacy system
- Clinical Trials API integration
- Backbone prompts for complex attributes
- RAG-enhanced extraction
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from src.app.enhanced_extraction_service import EnhancedExtractionService
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
    """Main demo function."""
    logger.info("Starting Enhanced Extraction Demo")

    try:
        # Initialize services
        logger.info("Initializing services...")

        # Database setup
        db_setup = DatabaseSetup()
        db_setup.setup_database()

        # LLM service with cost tracking
        base_llm_service = LangChainLLMService()
        cost_calculator = CostCalculator()
        llm_service = CostTrackingLLMService(base_llm_service, cost_calculator)

        # Embedding service
        embedding_service = LangChainEmbeddingService()

        # Vector store service
        vector_store_service = LangChainVectorStore(
            embedding_service=embedding_service,
            collection_name="enhanced_clinical_trials",
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

        # Load sample abstract
        abstract_file = Path("data/postprocessed/ASCO_Abstracts/ASCO_2020.md")
        if not abstract_file.exists():
            logger.error(f"Abstract file not found: {abstract_file}")
            return

        with open(abstract_file, encoding="utf-8") as f:
            abstract_content = f.read()

        # Get first 5 abstracts
        abstracts = abstract_content.split("### Abstract ID:")[1:]  # Skip header
        if not abstracts:
            logger.error("No abstracts found in file")
            return

        # Process first 1 abstract for testing
        abstracts_to_process = abstracts[:1]
        logger.info(
            f"Found {len(abstracts)} total abstracts, processing first {len(abstracts_to_process)}"
        )

        # Load all abstracts into vector store
        logger.info("Loading abstract data into vector store...")

        all_chunks_with_embeddings = []
        embedding_config = EmbeddingConfiguration()

        for i, abstract_text in enumerate(abstracts_to_process):
            abstract_id = f"ASCO_2020_{i+1:03d}"
            logger.info(f"Processing abstract {i+1}/5: {abstract_id}")
            logger.info(f"Abstract length: {len(abstract_text)} characters")
            logger.info(f"Abstract preview: {abstract_text[:200]}...")

            # Create chunks from the abstract text
            chunks = await chunking_strategy.chunk_content(
                content=abstract_text,
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

        # Store all chunks in vector store
        await vector_store_service.store_chunks(all_chunks_with_embeddings)
        logger.info(
            f"Loaded {len(all_chunks_with_embeddings)} chunks for {len(abstracts_to_process)} abstracts into vector store"
        )

        # Use all configured attributes for comprehensive extraction
        from src.domain.extraction_models import AttributeConfigurationFactory

        all_configs = AttributeConfigurationFactory.get_all_configurations()
        attributes_to_extract = list(all_configs.keys())

        logger.info(
            f"Extracting {len(attributes_to_extract)} attributes for {len(abstracts_to_process)} abstracts"
        )

        # Process each abstract
        all_results = []
        for i, abstract_text in enumerate(abstracts_to_process):
            abstract_id = f"ASCO_2020_{i+1:03d}"
            logger.info(f"\n{'='*60}")
            logger.info(f"PROCESSING ABSTRACT {i+1}/5: {abstract_id}")
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
            logger.info(f"Abstract {i+1} completed!")
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
                logger.info(f"API attributes: {arm_result.get('api_attributes', 0)}")
                logger.info(
                    f"Abstract attributes: {arm_result.get('abstract_attributes', 0)}"
                )

                if arm_result.get("errors"):
                    logger.warning(f"Errors: {arm_result['errors']}")

                if arm_result.get("warnings"):
                    logger.warning(f"Warnings: {arm_result['warnings']}")

        # Use the last result for the summary (they should all be similar)
        result = all_results[-1] if all_results else None

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

            # Get extraction summary for the last result
            summary = extraction_service.get_extraction_summary(all_results[-1])
        else:
            summary = {}

        # Print cost summary
        print(f"\n{'='*60}")
        print("COST SUMMARY")
        print(f"{'='*60}")
        cost_calculator.print_summary()

        # Save results to JSON file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"enhanced_extraction_results_{timestamp}.json"
        cost_report_file = f"cost_report_{timestamp}.json"

        # Prepare results for JSON serialization
        json_results = {
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
            "summary": summary,
        }

        # Convert all results to JSON-serializable format
        for i, result in enumerate(all_results):
            abstract_id = f"ASCO_2020_{i+1:03d}"
            abstract_data = {
                "abstract_id": abstract_id,
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
                for attr_type, attr_data in arm_result.get("attributes", {}).items():
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
                        serializable_attributes[str(attr_type)] = serializable_attr
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

                        serializable_attributes[str(attr_type)] = {
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
                        serializable_attributes[str(attr_type)] = attr_data

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

        # Display attribute configuration summary
        logger.info("\n--- Attribute Configuration Summary ---")
        configs = AttributeConfigurationFactory.get_all_configurations()

        abstract_level = AttributeConfigurationFactory.get_abstract_level_attributes()
        arm_level = AttributeConfigurationFactory.get_arm_level_attributes()
        api_sourced = AttributeConfigurationFactory.get_api_sourced_attributes()

        logger.info(f"Total attributes configured: {len(configs)}")
        logger.info(f"Abstract-level attributes: {len(abstract_level)}")
        logger.info(f"Arm-level attributes: {len(arm_level)}")
        logger.info(f"API-sourced attributes: {len(api_sourced)}")

        logger.info("\nEnhanced extraction demo completed successfully!")

    except Exception as e:
        logger.error(f"Demo failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
