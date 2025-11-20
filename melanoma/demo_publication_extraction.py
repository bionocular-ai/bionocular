"""Demo script for enhanced extraction from publications.

This script demonstrates the enhanced extraction service for publications with:
- Results section extraction for arm separation
- 60+ attributes from legacy system
- Clinical Trials API integration
- Backbone prompts for complex attributes
- RAG-enhanced extraction
"""

import asyncio
import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from src.app.enhanced_extraction_service import EnhancedExtractionService
from src.domain.constants import get_ordered_attributes, get_ordered_attribute_list
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


def convert_to_json_serializable(obj: Any) -> Any:
    """Recursively convert Pydantic models and other objects to JSON-serializable format.
    
    Args:
        obj: Object to convert (can be dict, list, Pydantic model, datetime, etc.)
        
    Returns:
        JSON-serializable version of the object
    """
    from pydantic import BaseModel
    
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, BaseModel):
        # Convert Pydantic model to dict, then recursively process
        return convert_to_json_serializable(obj.model_dump(mode="json"))
    elif isinstance(obj, dict):
        return {key: convert_to_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_to_json_serializable(item) for item in obj]
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    elif hasattr(obj, "__dict__"):
        # Fallback for other objects with __dict__
        return convert_to_json_serializable(obj.__dict__)
    else:
        # Last resort: convert to string
        return str(obj)


async def main(
    skip_publications: list[str] | None = None,
    only_publications: list[str] | None = None,
    previous_results_file: str | None = None,
):
    """Main demo function for publications.
    
    Args:
        skip_publications: List of publication IDs to skip (already processed)
        only_publications: List of publication IDs to process (if None, process all)
        previous_results_file: Path to previous results file to merge with
    """
    logger.info("Starting Publication Extraction Demo")
    logger.info("=" * 80)

    try:
        # Clean vector database to avoid conflicts/duplicates
        chroma_db_path = Path("chroma_db_publications")
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
        preferred_model_str = os.getenv("EXTRACTION_MODEL", "gpt-4o")
        from src.infrastructure.cost_calculator import ModelType

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
            collection_name="publications_clinical_trials",
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
            logger.info("✅ Clinical Trials API service connected successfully")
        else:
            logger.warning("⚠️  Clinical Trials API service connection failed")
            api_service = None

        # Enhanced extraction service
        extraction_service = EnhancedExtractionService(
            treatment_arm_separator=arm_separator,
            arm_aware_rag_provider=rag_provider,
            attribute_extractor=attribute_extractor,
            llm_service=llm_service,
            clinical_trials_api_service=api_service,
            enable_cost_tracking=True,
        )

        logger.info("✅ Services initialized successfully")

        # Find all publication files
        publications_dir = Path("data/postprocessed/Publications")
        
        if not publications_dir.exists():
            logger.error(f"Publications directory not found: {publications_dir}")
            return

        # Process all publication files
        all_publication_files = list(publications_dir.glob("*.md"))
        
        if not all_publication_files:
            logger.error(f"No publication files found in {publications_dir}")
            return

        # Filter publications based on skip/only lists
        publications_to_process = []
        skipped_count = 0
        
        for pub_file in sorted(all_publication_files):
            pub_id = pub_file.stem  # Get filename without extension
            
            # Check if we should skip this publication
            if skip_publications and pub_id in skip_publications:
                skipped_count += 1
                logger.debug(f"Skipping {pub_id} (already processed)")
                continue
            
            # Check if we should only process specific publications
            if only_publications and pub_id not in only_publications:
                skipped_count += 1
                logger.debug(f"Skipping {pub_id} (not in only_publications list)")
                continue
            
            publications_to_process.append(pub_file)
        
        if skipped_count > 0:
            logger.info(f"Skipping {skipped_count} already-processed publications")
        
        logger.info(f"Processing {len(publications_to_process)} publication files")
        
        if not publications_to_process:
            logger.warning("No publications to process after filtering!")
            return

        # Load previous results if provided
        previous_results = []
        if previous_results_file and Path(previous_results_file).exists():
            logger.info(f"Loading previous results from: {previous_results_file}")
            try:
                with open(previous_results_file, "r") as f:
                    prev_data = json.load(f)
                    previous_results = prev_data.get("publications", [])
                    logger.info(f"Loaded {len(previous_results)} previous publication results")
            except Exception as e:
                logger.warning(f"Failed to load previous results: {e}")

        # Load all publications into vector store
        logger.info("\n" + "=" * 80)
        logger.info("Loading publication data into vector store...")
        logger.info("=" * 80)

        all_chunks_with_embeddings = []
        embedding_config = EmbeddingConfiguration()
        all_publications_metadata = []

        for idx, pub_file in enumerate(publications_to_process):
            logger.info(f"\nLoading publication {idx+1}/{len(publications_to_process)}: {pub_file.name}")
            
            pub_content = pub_file.read_text(encoding="utf-8")
            publication_id = pub_file.stem  # e.g., "Batch-I_3"
            
            # Create chunks from the publication
            chunks = await chunking_strategy.chunk_content(
                content=pub_content,
                configuration=chunking_config,
                document_id=publication_id,
                filename=str(pub_file),
            )

            logger.info(f"  Created {len(chunks)} chunks")

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
            all_publications_metadata.append({
                "file": pub_file,
                "publication_id": publication_id,
                "content": pub_content,
                "index": idx,
            })

        # Store all chunks in vector store
        await vector_store_service.upsert_chunks(all_chunks_with_embeddings)
        logger.info(
            f"\n✅ Loaded {len(all_chunks_with_embeddings)} chunks for {len(all_publications_metadata)} publications into vector store"
        )

        # Use all configured attributes for comprehensive extraction
        from src.domain.extraction_models import AttributeConfigurationFactory, AttributeType

        all_configs = AttributeConfigurationFactory.get_all_configurations()
        all_attributes = list(all_configs.keys())

        # Filter out abstract-specific attributes for publications
        # Publications don't have CONFERENCE, ABSTRACT_NUMBER, or COMMENTS
        attributes_to_exclude = {
            AttributeType.CONFERENCE,
            AttributeType.ABSTRACT_NUMBER,
            AttributeType.COMMENTS,
        }
        filtered_attributes = [
            attr for attr in all_attributes if attr not in attributes_to_exclude
        ]

        # Order attributes according to canonical business sequence
        attributes_to_extract = get_ordered_attribute_list(filtered_attributes)
        
        logger.info(
            f"Filtered out {len(attributes_to_exclude)} abstract-specific attributes: {[attr.value for attr in attributes_to_exclude]}"
        )
        logger.info(
            f"\nExtracting {len(attributes_to_extract)} attributes (in canonical order) for {len(all_publications_metadata)} publications"
        )

        # Process each publication sequentially
        all_results = []
        
        # Pre-calculate previous results map for incremental saving (if provided)
        prev_results_map_for_incremental = {}
        if previous_results:
            prev_results_map_for_incremental = {p.get("publication_id"): p for p in previous_results}
        
        for idx, pub_meta in enumerate(all_publications_metadata):
            publication_id = pub_meta["publication_id"]
            pub_content = pub_meta["content"]
            pub_file = pub_meta["file"]
            
            logger.info(f"\n{'='*80}")
            logger.info(f"PROCESSING PUBLICATION {idx+1}/{len(all_publications_metadata)}: {publication_id}")
            logger.info(f"{'='*80}")

            # Perform extraction using batch method
            # Note: For publications, the service will automatically:
            # 1. Detect it's a publication
            # 2. Extract Results section
            # 3. Separate arms from Results section only
            result = await extraction_service.extract_attributes_from_abstract_batch(
                abstract_text=pub_content,
                abstract_id=publication_id,
                attributes=attributes_to_extract,
                context_chunks_per_arm=10,
                similarity_threshold=0.1,
                include_api_data=True,
                file_path=str(pub_file),  # Pass file path for publication detection
            )

            all_results.append(result)

            # Save results incrementally after each publication to avoid losing progress
            # This is especially important for long-running jobs that might hit rate limits
            try:
                # Use a fixed filename for incremental saves (overwrite each time)
                incremental_output_file = "publication_extraction_results_incremental_latest.json"
                
                # Prepare incremental results - include new results + previous results that weren't re-processed
                incremental_publications = []
                
                # Add new results
                for result_idx, result in enumerate(all_results):
                    pub_meta = all_publications_metadata[result_idx] if result_idx < len(all_publications_metadata) else None
                    if not pub_meta:
                        continue
                    
                    publication_id = pub_meta["publication_id"]
                    # Convert Pydantic models to JSON-serializable format
                    publication_data = {
                        "publication_id": publication_id,
                        "file": str(pub_meta["file"]),
                        "total_arms": len(result.arm_results),
                        "total_attributes_extracted": result.total_attributes_extracted,
                        "overall_confidence": result.overall_confidence,
                        "processing_time_ms": result.processing_time_ms,
                        "errors": result.errors,
                        "warnings": result.warnings,
                        "arm_results": convert_to_json_serializable(result.arm_results),
                    }
                    incremental_publications.append(publication_data)
                
                # Add previous results that weren't re-processed
                prev_count = 0
                if previous_results:
                    # Create a copy of the map and remove any that were re-processed so far
                    current_prev_map = prev_results_map_for_incremental.copy()
                    for i in range(idx + 1):  # Only check publications processed so far
                        if i < len(all_publications_metadata):
                            pub_meta_processed = all_publications_metadata[i]
                            pub_id = pub_meta_processed["publication_id"]
                            if pub_id in current_prev_map:
                                del current_prev_map[pub_id]
                    # Add remaining previous results
                    for prev_pub in current_prev_map.values():
                        incremental_publications.append(prev_pub)
                    prev_count = len(current_prev_map)
                
                json_results = {
                    "total_publications": len(incremental_publications),
                    "total_arms": sum(p.get("total_arms", len(p.get("arm_results", {}))) for p in incremental_publications),
                    "total_attributes_extracted": sum(p.get("total_attributes_extracted", 0) for p in incremental_publications),
                    "average_confidence": sum(p.get("overall_confidence", 0) for p in incremental_publications) / len(incremental_publications) if incremental_publications else 0.0,
                    "publications": incremental_publications,
                }
                
                # Save incremental results
                # Convert to JSON-serializable format (already done for new results, but ensure previous results are also converted)
                json_results_serialized = convert_to_json_serializable(json_results)
                with open(incremental_output_file, "w", encoding="utf-8") as f:
                    json.dump(json_results_serialized, f, indent=2, ensure_ascii=False)
                
                logger.info(f"💾 Incremental results saved to: {incremental_output_file} ({len(all_results)} new + {prev_count} previous = {len(incremental_publications)} total)")
            except Exception as e:
                logger.warning(f"Failed to save incremental results: {e}")

            # Display results for this publication
            logger.info(f"Publication {publication_id} completed!")
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

        # Display overall results
        logger.info(f"\n{'='*80}")
        logger.info("EXTRACTION COMPLETED!")
        logger.info(f"{'='*80}")
        logger.info(f"Processed {len(all_results)} new publications")
        
        # Calculate totals including previous results if provided
        if previous_results:
            prev_results_map = {p.get("publication_id"): p for p in previous_results}
            # Remove any that were re-processed
            for pub_meta in all_publications_metadata:
                pub_id = pub_meta["publication_id"]
                if pub_id in prev_results_map:
                    del prev_results_map[pub_id]
            logger.info(f"Total with previous results: {len(all_results)} new + {len(prev_results_map)} previous = {len(all_results) + len(prev_results_map)} total")

        if all_results:
            total_arms = sum(len(result.arm_results) for result in all_results)
            total_attributes = sum(
                result.total_attributes_extracted for result in all_results
            )
            avg_confidence = sum(
                result.overall_confidence for result in all_results
            ) / len(all_results)
            total_time = sum(result.processing_time_ms for result in all_results)

            logger.info(f"Total arms across all publications: {total_arms}")
            logger.info(f"Total attributes extracted: {total_attributes}")
            logger.info(f"Average confidence: {avg_confidence:.2f}")
            logger.info(f"Total processing time: {total_time}ms ({total_time/1000:.1f}s)")

            # Get extraction summary for the last result
            summary = extraction_service.get_extraction_summary(all_results[-1])
        else:
            summary = {}

        # Print cost summary
        print(f"\n{'='*80}")
        print("COST SUMMARY")
        print(f"{'='*80}")
        cost_calculator.print_summary()

        # Save results to JSON file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"publication_extraction_results_{timestamp}.json"
        cost_report_file = f"publication_cost_report_{timestamp}.json"

        # Prepare results for JSON serialization
        # Include previous results that weren't re-processed
        all_publications_for_json = []
        
        # Add new results
        for idx, result in enumerate(all_results):
            pub_meta = all_publications_metadata[idx] if idx < len(all_publications_metadata) else None
            if not pub_meta:
                continue
            
            publication_id = pub_meta["publication_id"]
            # Convert Pydantic models to JSON-serializable format
            publication_data = {
                "publication_id": publication_id,
                "file": str(pub_meta["file"]),
                "total_arms": len(result.arm_results),
                "total_attributes_extracted": result.total_attributes_extracted,
                "overall_confidence": result.overall_confidence,
                "processing_time_ms": result.processing_time_ms,
                "errors": result.errors,
                "warnings": result.warnings,
                "arm_results": convert_to_json_serializable(result.arm_results),
            }
            all_publications_for_json.append(publication_data)
        
        # Add previous results that weren't re-processed
        if previous_results:
            prev_results_map = {p.get("publication_id"): p for p in previous_results}
            # Remove any that were re-processed
            for pub_meta in all_publications_metadata:
                pub_id = pub_meta["publication_id"]
                if pub_id in prev_results_map:
                    del prev_results_map[pub_id]
            
            # Add remaining previous results
            for prev_pub in prev_results_map.values():
                all_publications_for_json.append(prev_pub)
        
        # Note: Previous results are already in JSON format, new results are already converted
        json_results = {
            "total_publications": len(all_publications_for_json),
            "total_arms": sum(p.get("total_arms", len(p.get("arm_results", {}))) for p in all_publications_for_json),
            "total_attributes_extracted": sum(p.get("total_attributes_extracted", 0) for p in all_publications_for_json),
            "average_confidence": sum(p.get("overall_confidence", 0) for p in all_publications_for_json) / len(all_publications_for_json) if all_publications_for_json else 0,
            "total_processing_time_ms": sum(p.get("processing_time_ms", 0) for p in all_publications_for_json),
            "publications": all_publications_for_json,
            "summary": summary,
        }

        # Convert to JSON-serializable format (already done for new results, but ensure previous results are also converted)
        json_results_serialized = convert_to_json_serializable(json_results)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(json_results_serialized, f, indent=2, ensure_ascii=False)

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

        logger.info("\n✅ Publication extraction demo completed successfully!")

    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Extract attributes from publications")
    parser.add_argument(
        "--skip",
        type=str,
        help="Comma-separated list of publication IDs to skip (or path to file with one ID per line)",
    )
    parser.add_argument(
        "--only",
        type=str,
        help="Comma-separated list of publication IDs to process (or path to file with one ID per line)",
    )
    parser.add_argument(
        "--previous-results",
        type=str,
        help="Path to previous results JSON file to merge with",
    )
    
    args = parser.parse_args()
    
    # Parse skip/only lists
    skip_publications = None
    if args.skip:
        if Path(args.skip).exists():
            # Read from file
            with open(args.skip, "r") as f:
                skip_publications = [line.strip() for line in f if line.strip()]
        else:
            # Parse from comma-separated string
            skip_publications = [p.strip() for p in args.skip.split(",") if p.strip()]
    
    only_publications = None
    if args.only:
        if Path(args.only).exists():
            # Read from file
            with open(args.only, "r") as f:
                only_publications = [line.strip() for line in f if line.strip()]
        else:
            # Parse from comma-separated string
            only_publications = [p.strip() for p in args.only.split(",") if p.strip()]
    
    asyncio.run(main(
        skip_publications=skip_publications,
        only_publications=only_publications,
        previous_results_file=args.previous_results,
    ))

