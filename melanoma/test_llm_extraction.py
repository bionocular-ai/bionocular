"""Test LLM extraction for NCT number and number of patients."""

import asyncio
import logging

from src.domain.extraction_models import AttributeType
from src.infrastructure.arm_aware_rag_provider import ArmAwareRAGContextProvider
from src.infrastructure.attribute_extractor import LLMAttributeExtractor
from src.infrastructure.langchain.embeddings import LangChainEmbeddingService
from src.infrastructure.langchain.llm import LangChainLLMService
from src.infrastructure.langchain.vector_store import LangChainVectorStore
from src.infrastructure.prompt_templates import ExtractionPromptTemplateProvider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_llm_extraction():
    """Test LLM extraction for NCT number and number of patients."""

    # Initialize services
    embedding_service = LangChainEmbeddingService()
    vector_store = LangChainVectorStore(
        embedding_service=embedding_service,
        collection_name="enhanced_clinical_trials",
    )

    llm_service = LangChainLLMService()
    prompt_provider = ExtractionPromptTemplateProvider()
    attribute_extractor = LLMAttributeExtractor(llm_service, prompt_provider)

    rag_provider = ArmAwareRAGContextProvider(
        vector_store=vector_store,
        embedding_service=embedding_service,
    )

    abstract_id = "ESMO_2020_1076O"

    print("=" * 80)
    print("TESTING NCT NUMBER LLM EXTRACTION")
    print("=" * 80)

    # Get context for NCT number
    nct_context = await rag_provider.get_context_for_attribute(
        document_id=abstract_id,
        attribute_type=AttributeType.NCT_NUMBER,
        context_chunks=2,
        similarity_threshold=0.1,
    )

    print(f"\n📄 Context chunks retrieved: {len(nct_context)}")
    for i, chunk in enumerate(nct_context, 1):
        print(f"\n--- Context Chunk {i} ---")
        print(chunk)

    # Test LLM extraction
    print("\n🤖 Testing LLM extraction for NCT_NUMBER...")
    try:
        result = await attribute_extractor.extract_attribute(
            attribute_type=AttributeType.NCT_NUMBER,
            context=nct_context,
            document_id=abstract_id,
        )
        print("\n✅ LLM Result:")
        print(f"  Value: {result.value}")
        print(f"  Confidence: {result.confidence}")
        print(f"  Source chunks: {len(result.source_chunks)}")
    except Exception as e:
        print(f"\n❌ LLM extraction failed: {e}")
        import traceback

        traceback.print_exc()

    print("\n" + "=" * 80)
    print("TESTING NUMBER OF PATIENTS LLM EXTRACTION")
    print("=" * 80)

    # Get context for number of patients
    patients_context = await rag_provider.get_context_for_attribute(
        document_id=abstract_id,
        attribute_type=AttributeType.NUMBER_OF_PATIENTS,
        context_chunks=3,
        similarity_threshold=0.1,
    )

    print(f"\n📄 Context chunks retrieved: {len(patients_context)}")
    for i, chunk in enumerate(patients_context, 1):
        print(f"\n--- Context Chunk {i} ---")
        print(chunk[:300] + "..." if len(chunk) > 300 else chunk)

    # Test LLM extraction
    print("\n🤖 Testing LLM extraction for NUMBER_OF_PATIENTS...")
    try:
        result = await attribute_extractor.extract_attribute(
            attribute_type=AttributeType.NUMBER_OF_PATIENTS,
            context=patients_context,
            document_id=abstract_id,
        )
        print("\n✅ LLM Result:")
        print(f"  Value: {result.value}")
        print(f"  Confidence: {result.confidence}")
        print(f"  Source chunks: {len(result.source_chunks)}")
    except Exception as e:
        print(f"\n❌ LLM extraction failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_llm_extraction())
