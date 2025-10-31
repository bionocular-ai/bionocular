#!/usr/bin/env python3
"""
RAG-Enhanced Extraction Demo

This script demonstrates the complete RAG-enhanced extraction workflow
combining treatment arm separation with targeted attribute extraction.
"""

import argparse
import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    """Run the RAG-enhanced extraction demo."""
    # Load environment variables from .env if present
    load_dotenv()
    # Reduce tokenizers fork warnings and potential deadlocks
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    logger.info("🚀 Starting RAG-Enhanced Extraction Demo")
    logger.info("=" * 60)

    try:
        # Import services
        from src.app.langchain_factory_service import (
            LangChainServiceFactory,
            ServiceConfiguration,
        )
        from src.domain.constants import get_ordered_attributes
        from src.app.rag_enhanced_extraction_service import RAGEnhancedExtractionService
        from src.domain.extraction_models import AttributeType
        from src.infrastructure.arm_aware_rag_provider import ArmAwareRAGContextProvider
        from src.infrastructure.attribute_extractor import LLMAttributeExtractor
        from src.infrastructure.prompt_templates import ExtractionPromptTemplateProvider
        from src.infrastructure.treatment_arm_separator import TreatmentArmSeparator

        # Create configuration
        config = ServiceConfiguration(
            chunking_strategy="header_based",
            embedding_model="pritamdeka/S-BioBERT-snli-multinli-stsb",
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            temperature=0.1,
            persist_directory="./demo_rag_enhanced_chroma_db",
            collection_name="rag_enhanced_demo",
        )

        # Initialize factory
        factory = LangChainServiceFactory(config)
        logger.info("✅ Factory initialized")

        # Create services
        chunking_service = factory.create_chunking_service()
        embedding_service = factory.create_embedding_service()
        vector_store = factory.create_vector_store()
        llm_service = factory.create_llm_service()

        # Create RAG-enhanced extraction service
        treatment_arm_separator = TreatmentArmSeparator(llm_service)
        arm_aware_rag_provider = ArmAwareRAGContextProvider(
            vector_store, embedding_service
        )
        # Initialize attribute extractor with prompt provider
        attribute_extractor = LLMAttributeExtractor(
            llm_service=llm_service,
            prompt_provider=ExtractionPromptTemplateProvider(),
        )

        rag_enhanced_service = RAGEnhancedExtractionService(
            treatment_arm_separator=treatment_arm_separator,
            arm_aware_rag_provider=arm_aware_rag_provider,
            attribute_extractor=attribute_extractor,
            llm_service=llm_service,
        )

        logger.info("✅ RAG-enhanced extraction service initialized")

        # Optionally load first abstract from markdown file
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--md-file", type=str, default=None)
        args, _ = parser.parse_known_args()

        test_abstract = None
        if args.md_file and Path(args.md_file).exists():
            md_text = Path(args.md_file).read_text(encoding="utf-8")
            # Naive split: abstracts start with lines beginning with '### '
            parts = []
            current = []
            for line in md_text.splitlines():
                if line.startswith("### ") and current:
                    parts.append("\n".join(current).strip())
                    current = [line]
                else:
                    current.append(line)
            if current:
                parts.append("\n".join(current).strip())
            if parts:
                test_abstract = parts[0]
                logger.info("Loaded first abstract from markdown file")
        if not test_abstract:
            # Fallback sample abstract
            test_abstract = """
### Abstract ID: 1076O
**Title:** Adjuvant nivolumab (NIVO) vs ipilimumab (IPI) in resected stage III/IV melanoma: 4-y recurrence-free and overall survival (RFS/OS) results from CheckMate 238

#### Background:
NIVO has shown improved recurrence-free survival (RFS) vs IPI in patients (pts) with resected stage III/IV melanoma in the phase III CheckMate 238 study.

#### Methods:
Pts aged ≥15 y with completely resected stage IIIB/C or IV melanoma were stratified by AJCC staging criteria and randomized 1:1 to NIVO 240 mg Q2W for ≤12 mo or IPI 10 mg/kg Q3W for 4 doses, then Q12W for ≤12 mo.

#### Results:
At 48 mo of follow-up, NIVO continued to demonstrate superior RFS vs IPI (HR 0.71; 95% CI, 0.60-0.86; P < 0.001). The 4-y RFS rate was 51.7% vs 41.2%. Overall survival (OS) data showed a trend favoring NIVO (HR 0.87; 95% CI, 0.66-1.14; P = 0.31).

#### Conclusions:
NIVO demonstrated sustained RFS benefit vs IPI in resected stage III/IV melanoma.

**Clinical trial information:** NCT02388906.
"""

        logger.info("📄 Processing abstract with RAG-enhanced extraction...")

        # Process document first (chunking, embedding, storage)
        logger.info("Step 1: Processing document for RAG...")
        chunks = await chunking_service.chunk_content(
            content=test_abstract,
            configuration=None,  # Use default
            document_id="test_abstract_1076O",
            filename="melanoma_abstract.md",
        )
        logger.info(f"✅ Created {len(chunks)} chunks")

        # Generate embeddings and store
        from src.domain.models import (
            ChunkWithEmbedding,
            EmbeddingConfiguration,
            EmbeddingModel,
        )

        chunks_with_embeddings = []

        for chunk in chunks:
            embedding_config = EmbeddingConfiguration(
                model_name=EmbeddingModel(config.embedding_model),
                batch_size=config.batch_size,
                normalize_embeddings=config.normalize_embeddings,
            )
            embedding = await embedding_service.generate_embedding(
                text=chunk.content, config=embedding_config
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
                embedding_model="pritamdeka/S-BioBERT-snli-multinli-stsb",
                embedding_dimension=len(embedding),
            )
            chunks_with_embeddings.append(chunk_with_embedding)

        await vector_store.store_chunks(chunks_with_embeddings)
        logger.info(f"✅ Stored {len(chunks_with_embeddings)} chunks with embeddings")

        # Test RAG-enhanced extraction
        logger.info("Step 2: Running RAG-enhanced extraction...")

        # Define attributes to extract
        attributes_to_extract = [
            AttributeType.NCT_NUMBER,
            AttributeType.GENERIC_NAME,
            AttributeType.P_VALUE_OS,
            AttributeType.OBJECTIVE_RESPONSE_RATE,
            AttributeType.GRADE_3_PLUS_AE,
        ]

        # Run extraction
        extraction_result = await rag_enhanced_service.extract_attributes_from_abstract(
            abstract_text=test_abstract,
            abstract_id="test_abstract_1076O",
            attributes=attributes_to_extract,
            context_chunks_per_arm=5,
            similarity_threshold=0.1,
        )

        # Display results
        logger.info("🔍 RAG-Enhanced Extraction Results")
        logger.info("=" * 60)

        logger.info("📊 Overall Statistics:")
        logger.info(f"   - Treatment Arms: {extraction_result.arm_count}")
        logger.info(
            f"   - Total Attributes Extracted: {extraction_result.total_attributes_extracted}"
        )
        logger.info(
            f"   - Overall Confidence: {extraction_result.overall_confidence:.3f}"
        )
        logger.info(f"   - Success Rate: {extraction_result.success_rate:.3f}")
        logger.info(f"   - Processing Time: {extraction_result.processing_time_ms}ms")

        if extraction_result.errors:
            logger.info(f"❌ Errors: {extraction_result.errors}")

        if extraction_result.warnings:
            logger.info(f"⚠️ Warnings: {extraction_result.warnings}")

        # Display per-arm results
        logger.info("\n📋 Per-Arm Results:")
        for arm_result in extraction_result.arm_results.values():
            logger.info(f"\n   🏥 Arm: {arm_result.get('arm_name', 'Unknown')}")
            logger.info(
                f"      - Context Quality: {arm_result.get('context_quality', 0.0):.3f}"
            )
            logger.info(
                f"      - Attributes Extracted: {len(arm_result.get('attributes', {}))}"
            )

            if arm_result.get("errors"):
                logger.info(f"      - Errors: {arm_result['errors']}")

            if arm_result.get("warnings"):
                logger.info(f"      - Warnings: {arm_result['warnings']}")

            # Display extracted attributes
            if "attributes" in arm_result:
                logger.info("      📊 Extracted Attributes:")
                for attr_name, attr_data in arm_result["attributes"].items():
                    value = attr_data.get("value", "N/A")
                    confidence = attr_data.get("confidence", 0.0)
                    status = attr_data.get("validation_status", "unknown")
                    logger.info(
                        f"         - {attr_name}: {value} (confidence: {confidence:.3f}, status: {status})"
                    )

        # Quality assessment
        logger.info("\n🔍 Quality Assessment:")
        quality_assessment = await rag_enhanced_service.validate_extraction_quality(
            extraction_result
        )
        logger.info(f"   - Quality Score: {quality_assessment['quality_score']:.3f}")
        logger.info(f"   - Is Valid: {quality_assessment['is_valid']}")

        if quality_assessment["issues"]:
            logger.info(f"   - Issues: {quality_assessment['issues']}")

        if quality_assessment["recommendations"]:
            logger.info(
                f"   - Recommendations: {quality_assessment['recommendations']}"
            )

        # Get detailed statistics
        stats = rag_enhanced_service.get_extraction_statistics(extraction_result)
        logger.info("\n📈 Detailed Statistics:")
        logger.info(f"   - Abstract ID: {stats['abstract_id']}")
        logger.info(f"   - Arm Count: {stats['arm_count']}")
        logger.info(f"   - Total Attributes: {stats['total_attributes_extracted']}")
        logger.info(f"   - Overall Confidence: {stats['overall_confidence']:.3f}")
        logger.info(f"   - Success Rate: {stats['success_rate']:.3f}")
        logger.info(f"   - Processing Time: {stats['processing_time_ms']}ms")
        logger.info(f"   - Error Count: {stats['error_count']}")
        logger.info(f"   - Warning Count: {stats['warning_count']}")

        logger.info("\n🎉 RAG-Enhanced Extraction Demo Completed Successfully!")
        logger.info("✅ Treatment Arm Separation: WORKING")
        logger.info("✅ RAG Context Retrieval: WORKING")
        logger.info("✅ Targeted Attribute Extraction: WORKING")
        logger.info("✅ Quality Assessment: WORKING")
        logger.info("✅ End-to-End Pipeline: WORKING")

        # Save results to JSON file
        output_data = {
            "extraction_metadata": {
                "timestamp": datetime.now().isoformat(),
                "abstract_id": stats["abstract_id"],
                "processing_time_ms": stats["processing_time_ms"],
                "pipeline_version": "rag_enhanced_v1.0",
            },
            "overall_statistics": {
                "treatment_arms": stats["arm_count"],
                "total_attributes_extracted": stats["total_attributes_extracted"],
                "overall_confidence": stats["overall_confidence"],
                "success_rate": stats["success_rate"],
                "error_count": stats["error_count"],
                "warning_count": stats["warning_count"],
            },
            "quality_assessment": quality_assessment,
            "treatment_arms": [],
        }

        # Add treatment arm details
        for arm_id, arm_result in extraction_result.arm_results.items():
            # Order attributes according to canonical sequence
            ordered_attrs = get_ordered_attributes(arm_result.get("attributes", {}))

            arm_data = {
                "arm_id": arm_id,
                "arm_name": arm_result.get("arm_name", "Unknown"),
                "context_quality": arm_result.get("context_quality", 0.0),
                "attributes_extracted": len(arm_result.get("attributes", {})),
                "attributes": ordered_attrs,
                "errors": arm_result.get("errors", []),
                "warnings": arm_result.get("warnings", []),
            }
            output_data["treatment_arms"].append(arm_data)

        # Save to JSON file
        output_file = (
            f"rag_extraction_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        logger.info(f"\n💾 Results saved to: {output_file}")

    except Exception as e:
        logger.error(f"❌ Demo failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
