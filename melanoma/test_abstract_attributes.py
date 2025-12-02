#!/usr/bin/env python3
"""Quick test script for abstract-level attributes extraction.

Tests: CANCER_TYPE, CANCER_STAGE, SPONSORS, CLINICAL_TRIAL_PHASE, BIOSIMILAR
"""

import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from src.app.enhanced_extraction_service import EnhancedExtractionService
from src.domain.extraction_models import AttributeType
from src.domain.models import (
    ChunkingConfiguration,
    EmbeddingConfiguration,
)
from src.infrastructure.arm_aware_rag_provider import ArmAwareRAGContextProvider
from src.infrastructure.attribute_extractor import LLMAttributeExtractor
from src.infrastructure.cost_calculator import CostCalculator, ModelType
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


async def test_abstract_attributes():
    """Test extraction of abstract-level attributes."""

    logger.info("Initializing services...")

    # Database setup
    db_setup = DatabaseSetup()
    db_setup.setup_database()

    # LLM service with cost tracking
    base_llm_service = LangChainLLMService()
    preferred_model_str = os.getenv("EXTRACTION_MODEL", "gpt-4o")
    preferred_model = (
        ModelType.GPT_4O if preferred_model_str == "gpt-4o" else ModelType.GPT_4O_MINI
    )
    cost_calculator = CostCalculator(default_model=preferred_model)
    llm_service = CostTrackingLLMService(base_llm_service, cost_calculator)

    # Embedding service
    embedding_service = LangChainEmbeddingService()

    # Vector store service
    vector_store_service = LangChainVectorStore(
        embedding_service=embedding_service,
        collection_name="test_abstract_attributes",
    )

    # Chunking strategy
    chunking_config = ChunkingConfiguration(
        max_chunk_size=1000,
        chunk_overlap=200,
        preserve_tables=True,
        include_headers=True,
    )
    chunking_service = LangChainChunkingService(chunking_config)

    # Embedding configuration
    embedding_config = EmbeddingConfiguration()

    # Treatment arm separator
    treatment_arm_separator = TreatmentArmSeparator(llm_service)

    # Prompt template provider
    prompt_template_provider = ExtractionPromptTemplateProvider()

    # Attribute extractor
    attribute_extractor = LLMAttributeExtractor(
        llm_service=llm_service,
        prompt_provider=prompt_template_provider,
    )

    # RAG provider
    arm_aware_rag_provider = ArmAwareRAGContextProvider(
        vector_store=vector_store_service,
        embedding_service=embedding_service,
    )

    # Initialize the extraction service
    logger.info("Initializing extraction service...")
    service = EnhancedExtractionService(
        treatment_arm_separator=treatment_arm_separator,
        arm_aware_rag_provider=arm_aware_rag_provider,
        attribute_extractor=attribute_extractor,
        llm_service=llm_service,
    )

    # Read test abstracts (10003 and 10006 from ASCO_2020)
    abstract_path = Path("data/postprocessed/ASCO_Abstracts/ASCO_2020.md")
    if not abstract_path.exists():
        logger.error(f"Abstract file not found: {abstract_path}")
        return

    with open(abstract_path, encoding="utf-8") as f:
        content = f.read()

    # Extract abstracts 10003 and 10006
    test_abstracts = []
    for abstract_id in ["10003", "10006"]:
        abstract_start = content.find(f"### Abstract ID: {abstract_id}")
        if abstract_start == -1:
            logger.warning(f"Abstract {abstract_id} not found")
            continue
        abstract_end = content.find("---", abstract_start + 1)
        if abstract_end == -1:
            abstract_end = len(content)
        abstract_text = content[abstract_start:abstract_end].strip()
        test_abstracts.append((abstract_id, abstract_text))
        logger.info(
            f"Found abstract {abstract_id} (length: {len(abstract_text)} chars)"
        )

    if not test_abstracts:
        logger.error("No test abstracts found")
        return

    # Attributes to test
    test_attributes = [
        AttributeType.CANCER_TYPE,
        AttributeType.CANCER_STAGE,
        AttributeType.SPONSORS,
        AttributeType.CLINICAL_TRIAL_PHASE,
        AttributeType.BIOSIMILAR,
        AttributeType.OBJECTIVE_RESPONSE_RATE,
        AttributeType.MEDIAN_DOR,
    ]

    logger.info(f"Testing attributes: {[attr.value for attr in test_attributes]}")

    # Test each abstract
    for abstract_id, abstract_text in test_abstracts:
        print("\n" + "=" * 80)
        print(f"EXTRACTION RESULTS FOR ABSTRACT {abstract_id}")
        print("=" * 80)

        # First, index the abstract into the vector store
        logger.info(f"Indexing abstract {abstract_id} into vector store...")
        chunks = await chunking_service.chunk_content(
            content=abstract_text,
            configuration=chunking_config,
            document_id=abstract_id,
            filename=str(abstract_path),
        )

        # Generate embeddings and add to vector store
        from src.domain.models import ChunkWithEmbedding

        chunks_with_embeddings = []
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
                embedding=embedding,
            )
            chunks_with_embeddings.append(chunk_with_embedding)

        # Add chunks to vector store
        await vector_store_service.upsert_chunks(chunks_with_embeddings)
        logger.info(
            f"Indexed {len(chunks_with_embeddings)} chunks for abstract {abstract_id}"
        )

        # Extract attributes
        result = await service.extract_attributes_from_abstract_batch(
            abstract_text=abstract_text,
            abstract_id=abstract_id,
            attributes=test_attributes,
            include_api_data=False,  # Don't use API - test abstract extraction only
        )

        if result.arm_results:
            for arm_id, arm_result in result.arm_results.items():
                print(f"\nArm: {arm_id}")
                print("-" * 80)
                attributes = arm_result.get("attributes", {})

                for attr_type in test_attributes:
                    attr_data = attributes.get(attr_type)
                    if attr_data:
                        # Handle both dict and Pydantic object
                        if hasattr(attr_data, "value"):
                            value = attr_data.value
                            source = getattr(attr_data, "source", "N/A")
                            confidence = getattr(attr_data, "confidence", "N/A")
                        else:
                            value = attr_data.get("value", "N/A")
                            source = attr_data.get("source", "N/A")
                            confidence = attr_data.get("confidence", "N/A")
                        print(
                            f"  {attr_type.value:30s} = {str(value):40s} [Source: {source}, Confidence: {confidence}]"
                        )
                    else:
                        print(f"  {attr_type.value:30s} = {'Not found':40s}")
        else:
            print("No arm results found")

        # Print expected values for each abstract
        print("\n" + "-" * 80)
        print(f"EXPECTED VALUES FOR ABSTRACT {abstract_id}:")
        print("-" * 80)
        if abstract_id == "10003":
            print("  CANCER_TYPE           = Unresectable Cutaneous Melanoma")
            print("  CANCER_STAGE          = Stage III/Stage IV")
            print("  SPONSORS              = Bristol Myers-Squibb")
            print("  CLINICAL_TRIAL_PHASE  = PHASE2")
            print("  BIOSIMILAR            = false (or empty)")
            print("  OBJECTIVE_RESPONSE_RATE = 48% (or 53%)")
            print("  MEDIAN_DOR            = (not specified in abstract)")
        elif abstract_id == "10006":
            print("  CANCER_TYPE           = Unresectable Cutaneous Melanoma")
            print("  CANCER_STAGE          = Stage IV (metastatic)")
            print("  SPONSORS              = Iovance Biotherapeutics, Inc")
            print("  CLINICAL_TRIAL_PHASE  = PHASE2")
            print("  BIOSIMILAR            = false (or empty)")
            print("  OBJECTIVE_RESPONSE_RATE = 36.4%")
            print("  MEDIAN_DOR            = NR (not reached)")

        if result.errors:
            print(f"\nErrors: {result.errors}")
        if result.warnings:
            print(f"Warnings: {result.warnings}")


if __name__ == "__main__":
    asyncio.run(test_abstract_attributes())
