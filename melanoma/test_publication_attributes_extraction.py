"""Test script to verify NCT number, publication name, and year extraction for publications.

This script tests the full extraction pipeline including RAG retrieval and LLM extraction.
"""

import asyncio
import logging
from pathlib import Path

from dotenv import load_dotenv

from src.domain.extraction_models import AttributeType
from src.infrastructure.arm_aware_rag_provider import ArmAwareRAGContextProvider
from src.infrastructure.attribute_extractor import LLMAttributeExtractor
from src.infrastructure.cost_calculator import CostCalculator
from src.infrastructure.cost_tracking_llm_service import CostTrackingLLMService
from src.infrastructure.langchain.embeddings import LangChainEmbeddingService
from src.infrastructure.langchain.llm import LangChainLLMService
from src.infrastructure.langchain.vector_store import LangChainVectorStore
from src.infrastructure.prompt_templates import ExtractionPromptTemplateProvider

# Load environment variables
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def test_publication_attributes(publication_file: str):
    """Test extraction of NCT number, publication name, and year for a publication."""
    logger.info("=" * 80)
    logger.info(f"Testing Publication Attributes Extraction: {publication_file}")
    logger.info("=" * 80)

    # Initialize services
    logger.info("Initializing services...")

    # Load publication first to get publication_id
    pub_path = Path(publication_file)
    if not pub_path.exists():
        logger.error(f"Publication file not found: {publication_file}")
        return

    pub_content = pub_path.read_text(encoding="utf-8")
    publication_id = pub_path.stem

    logger.info(f"Loaded publication: {publication_id}")
    logger.info(f"Content length: {len(pub_content)} characters")

    base_llm_service = LangChainLLMService()
    cost_calculator = CostCalculator()
    llm_service = CostTrackingLLMService(base_llm_service, cost_calculator)

    embedding_service = LangChainEmbeddingService()
    # Use the same collection name as the demo script
    vector_store = LangChainVectorStore(
        embedding_service=embedding_service,
        collection_name="publications_clinical_trials",
    )

    # Check if publication is in vector store
    logger.info(f"Checking if {publication_id} is in vector store...")
    # Try a simple search to see if document exists
    from src.infrastructure.langchain.vector_store import SearchQuery

    test_query = SearchQuery(
        text="pembrolizumab",
        top_k=1,
        similarity_threshold=0.0,
        metadata_filters={"document_id": publication_id},
    )
    test_results = await vector_store.search(test_query)
    if test_results:
        logger.info(
            f"✅ Found {len(test_results)} chunks for {publication_id} in vector store"
        )
    else:
        logger.warning(
            f"⚠️  No chunks found for {publication_id}. Publication may not be loaded in vector store."
        )
        logger.info(
            "   Note: You may need to run demo_publication_extraction.py first to load publications"
        )

    rag_provider = ArmAwareRAGContextProvider(
        vector_store=vector_store,
        embedding_service=embedding_service,
    )

    prompt_provider = ExtractionPromptTemplateProvider()
    attribute_extractor = LLMAttributeExtractor(
        llm_service=llm_service,
        prompt_provider=prompt_provider,
    )

    logger.info(f"Loaded publication: {publication_id}")
    logger.info(f"Content length: {len(pub_content)} characters")

    # Test attributes
    test_attributes = [
        AttributeType.NCT_NUMBER,
        AttributeType.PUBLICATION_NAME,
        AttributeType.PUBLICATION_YEAR,
    ]

    logger.info("\n" + "=" * 80)
    logger.info("STEP 1: Testing RAG Retrieval")
    logger.info("=" * 80)

    # Test RAG retrieval for each attribute
    for attr_type in test_attributes:
        logger.info(f"\n--- Testing {attr_type.value} ---")

        metadata_filters = {"filename": str(pub_path)}
        context_chunks = await rag_provider.get_context_for_attribute(
            document_id=publication_id,
            attribute_type=attr_type,
            context_chunks=5,
            similarity_threshold=0.1,
            metadata_filters=metadata_filters,
        )

        logger.info(f"Retrieved {len(context_chunks)} chunks")
        for idx, chunk in enumerate(context_chunks[:3], 1):
            preview = chunk[:200] + "..." if len(chunk) > 200 else chunk
            logger.info(f"  Chunk {idx}: {preview}")

    logger.info("\n" + "=" * 80)
    logger.info("STEP 2: Testing LLM Extraction")
    logger.info("=" * 80)

    # Test LLM extraction for each attribute
    extraction_results = {}

    for attr_type in test_attributes:
        logger.info(f"\n--- Extracting {attr_type.value} ---")

        # Get context
        metadata_filters = {"filename": str(pub_path)}
        # Use higher threshold for NCT number to filter out irrelevant chunks
        threshold = 0.3 if attr_type == AttributeType.NCT_NUMBER else 0.1
        context_chunks = await rag_provider.get_context_for_attribute(
            document_id=publication_id,
            attribute_type=attr_type,
            context_chunks=5,
            similarity_threshold=threshold,
            metadata_filters=metadata_filters,
        )

        if not context_chunks:
            logger.warning(f"No chunks retrieved for {attr_type.value}")
            extraction_results[attr_type] = {
                "value": "Not found",
                "confidence": 0.0,
                "reason": "No chunks retrieved",
            }
            continue

        # Extract with LLM
        try:
            extracted_attr = await attribute_extractor.extract_attribute(
                attribute_type=attr_type,
                context=context_chunks,
                document_id=publication_id,
                arm_info=None,
            )

            extraction_results[attr_type] = {
                "value": extracted_attr.value
                if hasattr(extracted_attr, "value")
                else str(extracted_attr),
                "confidence": extracted_attr.confidence
                if hasattr(extracted_attr, "confidence")
                else 0.0,
                "source": extracted_attr.source
                if hasattr(extracted_attr, "source")
                else "unknown",
            }

            logger.info(f"✅ Extracted: {extraction_results[attr_type]['value']}")
            logger.info(
                f"   Confidence: {extraction_results[attr_type]['confidence']:.2f}"
            )
            logger.info(f"   Source: {extraction_results[attr_type]['source']}")

        except Exception as e:
            logger.error(f"❌ Extraction failed: {e}", exc_info=True)
            extraction_results[attr_type] = {
                "value": "Error",
                "confidence": 0.0,
                "error": str(e),
            }

    logger.info("\n" + "=" * 80)
    logger.info("EXTRACTION RESULTS SUMMARY")
    logger.info("=" * 80)

    for attr_type in test_attributes:
        result = extraction_results.get(attr_type, {})
        logger.info(f"\n{attr_type.value}:")
        logger.info(f"  Value: {result.get('value', 'N/A')}")
        logger.info(f"  Confidence: {result.get('confidence', 0.0):.2f}")
        logger.info(f"  Source: {result.get('source', 'N/A')}")
        if "error" in result:
            logger.error(f"  Error: {result['error']}")

    # Expected values for Batch-III_11
    expected = {
        AttributeType.NCT_NUMBER: "NCT02267603",
        AttributeType.PUBLICATION_NAME: "Journal of Clinical Oncology",  # or similar
        AttributeType.PUBLICATION_YEAR: "2019",  # Published February 6, 2019
    }

    logger.info("\n" + "=" * 80)
    logger.info("VALIDATION")
    logger.info("=" * 80)

    for attr_type in test_attributes:
        expected_value = expected.get(attr_type, "Unknown")
        actual_value = extraction_results.get(attr_type, {}).get("value", "")

        # Check if extracted value contains expected value (flexible matching)
        if (
            expected_value.lower() in str(actual_value).lower()
            or str(actual_value).lower() in expected_value.lower()
        ):
            logger.info(
                f"✅ {attr_type.value}: PASS (Expected: {expected_value}, Got: {actual_value})"
            )
        else:
            logger.warning(
                f"⚠️  {attr_type.value}: MISMATCH (Expected: {expected_value}, Got: {actual_value})"
            )

    # Print cost summary
    print(f"\n{'='*80}")
    print("COST SUMMARY")
    print(f"{'='*80}")
    cost_calculator.print_summary()

    logger.info("\n" + "=" * 80)
    logger.info("TEST COMPLETE")
    logger.info("=" * 80)


async def main():
    """Main function."""
    # Default publication
    default_pub = "data/postprocessed/Publications/Batch-III_11.md"

    import sys

    if len(sys.argv) > 1:
        publication_file = sys.argv[1]
    else:
        publication_file = default_pub

    try:
        await test_publication_attributes(publication_file)
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
