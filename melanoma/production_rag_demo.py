#!/usr/bin/env python3
"""
Production RAG Demo - Full RAG pipeline with extraction on real ASCO abstracts.

This demo uses the working RAG pipeline to extract attributes from clinical abstracts
with proper context retrieval, deduplication, and error handling.
"""

import asyncio
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from src.app.langchain_factory_service import (
    LangChainServiceFactory,
    ServiceConfiguration,
)
from src.domain.extraction_models import AttributeType
from src.domain.models import (
    ChunkingConfiguration,
    ChunkWithEmbedding,
    EmbeddingConfiguration,
)
from src.infrastructure.attribute_extractor import LLMAttributeExtractor
from src.infrastructure.attribute_validator import AttributeValidatorImpl
from src.infrastructure.extraction_llm_service import ExtractionLLMService
from src.infrastructure.prompt_templates import ExtractionPromptTemplateProvider
from src.infrastructure.rag_context_provider import RAGContextProviderImpl

# Fix HuggingFace tokenizers warning
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Load environment variables
load_dotenv()

# Configure logging (reduced verbosity for production)
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class ProductionRAGDemo:
    """Production-ready RAG extraction demo."""

    def __init__(
        self, data_file: str = "data/postprocessed/ASCO_Abstracts/enhanced_ASCO_2020.md"
    ):
        self.data_file = Path(data_file)
        self.abstracts = []
        self.vector_store = None
        self.embedding_service = None
        self.rag_context_provider = None
        self.extraction_service = None
        self.setup_complete = False

    def parse_abstracts(self, max_abstracts: int = 10) -> list[dict[str, Any]]:
        """Parse abstracts from the ASCO 2020 markdown file."""
        if not self.data_file.exists():
            raise FileNotFoundError(f"Data file not found: {self.data_file}")

        with open(self.data_file, encoding="utf-8") as f:
            content = f.read()

        # Split by abstract separators
        abstract_sections = re.split(r"\n---\n", content)
        abstracts = []

        for i, section in enumerate(abstract_sections[:max_abstracts]):
            if not section.strip():
                continue

            # Extract abstract ID
            id_match = re.search(r"### Abstract ID: (\d+)", section)
            abstract_id = id_match.group(1) if id_match else f"abstract_{i+1}"

            # Extract title
            title_match = re.search(r"\*\*Title:\*\* (.+)", section)
            title = title_match.group(1).strip() if title_match else "No title found"

            # Extract NCT number
            nct_match = re.search(r"NCT(\d{8})", section)
            nct_number = f"NCT{nct_match.group(1)}" if nct_match else None

            # Clean up the content for processing
            clean_content = re.sub(r"#{1,6}\s+", "", section)  # Remove markdown headers
            clean_content = re.sub(
                r"\*\*([^*]+)\*\*", r"\1", clean_content
            )  # Remove bold formatting
            clean_content = re.sub(
                r"\n+", " ", clean_content
            )  # Replace multiple newlines with spaces
            clean_content = re.sub(
                r"\s+", " ", clean_content
            ).strip()  # Clean up whitespace

            abstracts.append(
                {
                    "id": abstract_id,
                    "title": title,
                    "content": clean_content,
                    "nct_number": nct_number,
                    "raw_section": section,
                }
            )

        logger.info(f"Parsed {len(abstracts)} abstracts from {self.data_file}")
        return abstracts

    async def setup_rag_pipeline(self):
        """Setup RAG pipeline components."""
        try:
            print("🔧 Setting up RAG pipeline...")

            # Check for API key
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError(
                    "OPENAI_API_KEY not found. Please set it in .env file."
                )

            # Set OpenAI API key
            os.environ["OPENAI_API_KEY"] = api_key

            # Parse abstracts
            self.abstracts = self.parse_abstracts(max_abstracts=10)

            # Create LangChain services - store config for reuse
            self.config = ServiceConfiguration(
                chunking_strategy="header_based",
                embedding_model="pritamdeka/S-BioBERT-snli-multinli-stsb",
                llm_provider="openai",
                llm_model="gpt-4o-mini",
                temperature=0.1,
                persist_directory="./production_rag_chroma_db",
                collection_name="production_rag_extraction",
            )

            self.factory = LangChainServiceFactory(self.config)

            # Create services once and reuse
            self.embedding_service = self.factory.create_embedding_service()
            self.vector_store = self.factory.create_vector_store()

            print("✅ RAG pipeline setup complete!")

        except Exception as e:
            logger.error(f"RAG setup failed: {e}")
            raise

    async def process_abstracts(self):
        """Process abstracts and store in vector database."""
        try:
            print("📚 Processing abstracts and storing in vector database...")

            # Reuse the same factory and services from setup
            chunking_service = self.factory.create_chunking_service()

            # Reuse the same embedding service to avoid reloading the model
            embedding_config = EmbeddingConfiguration(
                model_name="pritamdeka/S-BioBERT-snli-multinli-stsb"
            )

            total_chunks = 0
            for i, abstract in enumerate(self.abstracts):
                print(
                    f"  Processing abstract {i+1}/{len(self.abstracts)}: {abstract['id']}"
                )

                # Chunk the abstract
                chunking_config = ChunkingConfiguration(
                    strategy="header_based", chunk_size=1000, chunk_overlap=200
                )

                chunks = await chunking_service.chunk_content(
                    content=abstract["content"],
                    configuration=chunking_config,
                    document_id=str(abstract["id"]),  # Ensure string document ID
                    filename=f"abstract_{abstract['id']}.md",
                )

                # Use the pre-configured embedding config

                chunks_with_embeddings = []
                for chunk in chunks:
                    embedding = await self.embedding_service.generate_embedding(
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
                        embedding_model=embedding_config.model_name,
                        embedding_dimension=len(embedding),
                        embedding_generated_at=datetime.now(),
                    )

                    chunks_with_embeddings.append(chunk_with_embedding)

                # Store in vector database
                await self.vector_store.store_chunks(chunks_with_embeddings)
                total_chunks += len(chunks_with_embeddings)

            print(
                f"✅ Processed {len(self.abstracts)} abstracts, stored {total_chunks} chunks"
            )

        except Exception as e:
            logger.error(f"Abstract processing failed: {e}")
            raise

    async def setup_extraction_services(self):
        """Setup extraction services."""
        try:
            print("🔧 Setting up extraction services...")

            # Create RAG context provider
            self.rag_context_provider = RAGContextProviderImpl(
                self.vector_store, self.embedding_service
            )

            # Create extraction services
            prompt_provider = ExtractionPromptTemplateProvider()
            llm_service = ExtractionLLMService()
            attribute_extractor = LLMAttributeExtractor(llm_service, prompt_provider)
            attribute_validator = AttributeValidatorImpl()

            self.extraction_service = {
                "extractor": attribute_extractor,
                "validator": attribute_validator,
                "rag_provider": self.rag_context_provider,
            }

            self.setup_complete = True
            print("✅ Extraction services setup complete!")

        except Exception as e:
            logger.error(f"Extraction services setup failed: {e}")
            raise

    async def extract_attributes_with_rag(
        self, abstract: dict[str, Any]
    ) -> dict[AttributeType, Any]:
        """Extract attributes using RAG context."""
        try:
            # Priority attributes to extract
            priority_attributes = [
                AttributeType.NCT_NUMBER,
                AttributeType.GENERIC_NAME,
                AttributeType.P_VALUE_OS,
                AttributeType.OBJECTIVE_RESPONSE_RATE,
                AttributeType.GRADE_3_PLUS_AE,
            ]

            extracted_attributes = {}

            for attribute_type in priority_attributes:
                try:
                    # Get RAG context with more chunks for better coverage
                    context_results = await self.rag_context_provider.get_context_for_attribute(
                        document_id=abstract["id"],
                        attribute_type=attribute_type,
                        context_chunks=8,  # Increased from 5 to 8 for better context
                        similarity_threshold=0.05,  # Lowered threshold to catch more relevant content
                        metadata_filters={},
                    )

                    # Extract context chunks from SearchResult objects
                    context_chunks = [result.chunk for result in context_results]

                    # Extract attribute using LLM
                    extracted_attribute = await self.extraction_service[
                        "extractor"
                    ].extract_attribute(attribute_type, context_chunks, abstract["id"])

                    # Validate attribute
                    validated_attribute = self.extraction_service["validator"].validate(
                        extracted_attribute, attribute_type
                    )

                    extracted_attributes[attribute_type] = validated_attribute

                except Exception as e:
                    logger.warning(
                        f"Failed to extract {attribute_type} for {abstract['id']}: {e}"
                    )
                    # Create empty attribute for failed extractions
                    from src.domain.extraction_models import ExtractedAttribute

                    extracted_attributes[attribute_type] = ExtractedAttribute(
                        attribute_type=attribute_type,
                        value=None,
                        confidence=0.0,
                        source_chunks=[],
                        extracted_at=datetime.now(),
                    )

            return extracted_attributes

        except Exception as e:
            logger.error(f"Attribute extraction failed for {abstract['id']}: {e}")
            raise

    async def run_demo(self):
        """Run the complete production demo."""
        try:
            print("🚀 Starting Production RAG Extraction Demo")
            print("=" * 80)
            print("⚠️  Note: This demo uses RAG pipeline for context retrieval")
            print("=" * 80)

            # Setup RAG pipeline
            await self.setup_rag_pipeline()

            # Process abstracts
            await self.process_abstracts()

            # Setup extraction services
            await self.setup_extraction_services()

            print("\n" + "=" * 80)
            print("🎯 PRODUCTION RAG EXTRACTION RESULTS")
            print("=" * 80)

            total_processing_time = 0
            successful_extractions = 0
            attribute_success_counts = {
                attr: 0
                for attr in [
                    AttributeType.NCT_NUMBER,
                    AttributeType.GENERIC_NAME,
                    AttributeType.P_VALUE_OS,
                    AttributeType.OBJECTIVE_RESPONSE_RATE,
                    AttributeType.GRADE_3_PLUS_AE,
                ]
            }

            for i, abstract in enumerate(self.abstracts):
                print(f"\n📄 Abstract {i+1}/{len(self.abstracts)}: {abstract['id']}")
                print(f"Title: {abstract['title'][:80]}...")
                print(f"Known NCT: {abstract['nct_number'] or 'Not found'}")
                print("-" * 60)

                try:
                    start_time = datetime.now()

                    # Extract attributes using RAG
                    extracted_attributes = await self.extract_attributes_with_rag(
                        abstract
                    )

                    processing_time = int(
                        (datetime.now() - start_time).total_seconds() * 1000
                    )
                    total_processing_time += processing_time

                    # Display results
                    for attr_type, attr in extracted_attributes.items():
                        status_emoji = (
                            "✅" if attr.value and attr.value != "N/A" else "❌"
                        )
                        print(
                            f"  {status_emoji} {attr_type.value.replace('_', ' ').title()}: {attr.value}"
                        )
                        print(
                            f"     Confidence: {attr.confidence:.3f} | Status: {attr.validation_status.value}"
                        )

                        # Count successful extractions
                        if attr.value and attr.value != "N/A":
                            attribute_success_counts[attr_type] += 1

                    # Check if we found the known NCT number
                    if abstract["nct_number"] and extracted_attributes.get(
                        AttributeType.NCT_NUMBER
                    ):
                        found_nct = extracted_attributes[AttributeType.NCT_NUMBER].value
                        if found_nct and abstract["nct_number"] in str(found_nct):
                            print(
                                f"  🎯 NCT Match: Found known NCT {abstract['nct_number']}"
                            )
                        else:
                            print(
                                f"  ⚠️  NCT Mismatch: Expected {abstract['nct_number']}, got {found_nct}"
                            )

                    print(f"  ⏱️  Processing Time: {processing_time}ms")
                    successful_extractions += 1

                except Exception as e:
                    print(f"  ❌ Extraction failed: {e}")
                    logger.error(
                        f"Extraction failed for abstract {abstract['id']}: {e}"
                    )

            # Summary
            print("\n" + "=" * 80)
            print("📊 EXTRACTION SUMMARY")
            print("=" * 80)
            print(f"Total Abstracts Processed: {len(self.abstracts)}")
            print(f"Successful Extractions: {successful_extractions}")
            print(
                f"Success Rate: {(successful_extractions/len(self.abstracts))*100:.1f}%"
            )
            print(
                f"Average Processing Time: {total_processing_time/len(self.abstracts):.0f}ms per abstract"
            )
            print(f"Total Processing Time: {total_processing_time/1000:.1f}s")

            # Performance improvements summary
            print("\n🚀 OPTIMIZATIONS APPLIED:")
            print("  ✅ Fixed HuggingFace tokenizers warning")
            print("  ✅ Optimized model loading (no repeated reloading)")
            print("  ✅ Enhanced context queries (5→7 queries per attribute)")
            print("  ✅ Increased context chunks (5→8 chunks)")
            print("  ✅ Lowered similarity threshold (0.1→0.05)")

            print("\n📈 Attribute Success Rates:")
            for attr_type, count in attribute_success_counts.items():
                success_rate = (count / len(self.abstracts)) * 100
                print(
                    f"  {attr_type.value.replace('_', ' ').title()}: {count}/{len(self.abstracts)} ({success_rate:.1f}%)"
                )

            print("\n🎉 Production RAG Demo completed successfully!")

        except Exception as e:
            logger.error(f"Demo failed: {e}")
            raise


async def main():
    """Main function to run the demo."""
    demo = ProductionRAGDemo()

    try:
        await demo.run_demo()
        print("\n✅ Demo completed successfully!")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        print("Please check the logs for more details.")
        logger.error(f"Demo failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
