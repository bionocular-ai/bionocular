"""Demo script for the RAG-enhanced extractor system.

This script demonstrates the complete extraction pipeline
using the clean architecture implementation.
"""

import asyncio
import logging
import os
from datetime import datetime

from config import OPENAI_API_KEY
from src.app.extraction_service import ExtractionService
from src.app.langchain_factory_service import LangChainServiceFactory
from src.domain.extraction_models import AttributeType, ExtractionRequest
from src.infrastructure.attribute_extractor import LLMAttributeExtractor
from src.infrastructure.attribute_validator import AttributeValidatorImpl
from src.infrastructure.database_setup import DatabaseSetup
from src.infrastructure.extraction_llm_service import ExtractionLLMService
from src.infrastructure.extraction_repository import ExtractionRepositoryImpl
from src.infrastructure.prompt_templates import ExtractionPromptTemplateProvider
from src.infrastructure.rag_context_provider import RAGContextProviderImpl

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExtractorDemo:
    """Demo class for the extractor system."""

    def __init__(self):
        """Initialize demo with all required services."""
        self.extraction_service = None
        self.setup_complete = False

    async def setup(self):
        """Setup all services and dependencies."""
        try:
            logger.info("Setting up extractor demo...")

            # Check for API key
            if not OPENAI_API_KEY:
                raise ValueError(
                    "OPENAI_API_KEY not found. Please set it in .env file or environment variables."
                )

            # Set OpenAI API key
            os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

            # Initialize LangChain services
            factory = LangChainServiceFactory()

            # Create services
            embedding_service = factory.create_embedding_service()
            vector_store = factory.create_vector_store(embedding_service)

            # Initialize RAG context provider
            rag_context_provider = RAGContextProviderImpl(
                vector_store, embedding_service
            )

            # Initialize prompt templates
            prompt_provider = ExtractionPromptTemplateProvider()

            # Initialize LLM service for extraction with GPT-4o mini
            llm_extraction_service = ExtractionLLMService()

            # Initialize attribute extractor
            attribute_extractor = LLMAttributeExtractor(
                llm_extraction_service, prompt_provider
            )

            # Initialize validator
            attribute_validator = AttributeValidatorImpl()

            # Initialize database
            db_setup = DatabaseSetup()
            db_setup.setup_database()
            db_session = db_setup.get_session()

            # Initialize repository
            extraction_repository = ExtractionRepositoryImpl(db_session)

            # Initialize extraction service
            self.extraction_service = ExtractionService(
                rag_context_provider=rag_context_provider,
                attribute_extractor=attribute_extractor,
                attribute_validator=attribute_validator,
                extraction_repository=extraction_repository,
                prompt_template_provider=prompt_provider,
                llm_service=llm_extraction_service,
            )

            self.setup_complete = True
            logger.info("Extractor demo setup complete!")

        except Exception as e:
            logger.error(f"Setup failed: {e}")
            raise

    async def run_extraction_demo(self, document_id: str = "demo_document_001"):
        """Run extraction demo for the 5 priority attributes.

        Args:
            document_id: Document identifier for extraction
        """
        if not self.setup_complete:
            await self.setup()

        try:
            logger.info(f"Running extraction demo for document: {document_id}")

            # Define the 5 priority attributes
            attributes = [
                AttributeType.NCT_NUMBER,
                AttributeType.GENERIC_NAME,
                AttributeType.P_VALUE_OS,
                AttributeType.OBJECTIVE_RESPONSE_RATE,
                AttributeType.GRADE_3_PLUS_AE,
            ]

            # Create extraction request
            request = ExtractionRequest(
                document_id=document_id,
                attributes=attributes,
                context_chunks=5,
                similarity_threshold=0.1,
            )

            # Run extraction
            logger.info("Starting attribute extraction...")
            start_time = datetime.now()

            result = await self.extraction_service.extract_attributes(request)

            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()

            # Display results
            self._display_results(result, processing_time)

        except Exception as e:
            logger.error(f"Extraction demo failed: {e}")
            raise

    def _display_results(self, result, processing_time: float):
        """Display extraction results in a formatted way.

        Args:
            result: Extraction result
            processing_time: Total processing time in seconds
        """
        print("\n" + "=" * 80)
        print("🎯 EXTRACTION RESULTS")
        print("=" * 80)

        print(f"📄 Document ID: {result.document_id}")
        print(
            f"⏱️  Processing Time: {processing_time:.2f}s ({result.processing_time_ms}ms)"
        )
        print(f"📊 Total Chunks Processed: {result.total_chunks_processed}")
        print(f"🎯 Overall Confidence: {result.extraction_confidence:.3f}")
        print(f"✅ Success Rate: {result.success_rate:.1%}")
        print(f"📅 Created At: {result.created_at.strftime('%Y-%m-%d %H:%M:%S')}")

        print("\n" + "-" * 80)
        print("📋 EXTRACTED ATTRIBUTES")
        print("-" * 80)

        for attr_type, attribute in result.extracted_attributes.items():
            print(f"\n🔍 {attr_type.value.upper().replace('_', ' ')}")
            print(
                f"   Value: {attribute.value if attribute.value is not None else 'Not found'}"
            )
            print(
                f"   Confidence: {attribute.confidence:.3f} ({attribute.confidence_level.value})"
            )
            print(f"   Status: {attribute.validation_status.value}")

            if attribute.validation_errors:
                print(f"   Errors: {', '.join(attribute.validation_errors)}")

            if attribute.source_chunks:
                print(f"   Sources: {len(attribute.source_chunks)} chunks")

        print("\n" + "-" * 80)
        print("📈 HIGH CONFIDENCE ATTRIBUTES")
        print("-" * 80)

        high_confidence = result.high_confidence_attributes
        if high_confidence:
            for attr_type in high_confidence:
                attr = result.extracted_attributes[attr_type]
                print(
                    f"✅ {attr_type.value}: {attr.value} (confidence: {attr.confidence:.3f})"
                )
        else:
            print("No high confidence attributes found")

        print("\n" + "=" * 80)
        print("🎉 EXTRACTION COMPLETE!")
        print("=" * 80)


async def main():
    """Main demo function."""
    demo = ExtractorDemo()

    try:
        # Run extraction demo
        await demo.run_extraction_demo("demo_document_001")

    except Exception as e:
        logger.error(f"Demo failed: {e}")
        print(f"\n❌ Demo failed: {e}")
        print("Please check the logs for more details.")


if __name__ == "__main__":
    print("🚀 Starting RAG-Enhanced Extractor Demo")
    print("=" * 50)

    # Run the demo
    asyncio.run(main())
