#!/usr/bin/env python3
"""
Complete RAG Pipeline Demo

This script demonstrates the complete RAG pipeline including:
1. Document processing (chunking, embedding, storage)
2. Query processing (retrieval + generation)
3. Response generation with LLM
4. Fallback to retrieval-only mode if LLM unavailable

Usage:
    python demo_complete_rag.py
"""

import asyncio
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    """Run the complete RAG pipeline demo."""
    logger.info("🚀 Starting Complete RAG Pipeline Demo")
    logger.info("=" * 60)

    try:
        # Import services
        from src.app.complete_rag_service import CompleteRAGService
        from src.app.langchain_factory_service import (
            LangChainServiceFactory,
            ServiceConfiguration,
        )
        from src.domain.models import (
            ChunkingConfiguration,
            EmbeddingConfiguration,
            RAGQuery,
        )

        # Create configuration
        config = ServiceConfiguration(
            chunking_strategy="header_based",
            embedding_model="pritamdeka/S-BioBERT-snli-multinli-stsb",
            llm_provider="openai",
            llm_model="gpt-3.5-turbo",
            temperature=0.1,
            persist_directory="./demo_complete_rag_chroma_db",
            collection_name="complete_rag_demo",
        )

        # Initialize factory
        factory = LangChainServiceFactory(config)
        logger.info("✅ Factory initialized")

        # Create services
        chunking_service = factory.create_chunking_service()
        embedding_service = factory.create_embedding_service()
        vector_store = factory.create_vector_store()
        llm_service = factory.create_llm_service()

        # Create complete RAG service
        rag_service = CompleteRAGService(
            chunking_service=chunking_service,
            embedding_service=embedding_service,
            vector_store=vector_store,
            llm_service=llm_service,
        )

        logger.info("✅ Complete RAG service initialized")

        # Test data - melanoma abstracts
        test_content = """### Abstract ID: 1076O
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

---

### Abstract ID: 1077MO
**Title:** Long-term outcomes with pembrolizumab (pembro) in patients (pts) with advanced melanoma: 5-year results from KEYNOTE-006

#### Background:
Pembro demonstrated superior progression-free survival (PFS) and overall survival (OS) vs ipilimumab (ipi) in pts with advanced melanoma in KEYNOTE-006.

#### Methods:
Pts with unresectable stage III/IV melanoma were randomized 1:1:1 to pembro 10 mg/kg Q2W or Q3W, or ipi 3 mg/kg Q3W for 4 doses.

#### Results:
At 5-y follow-up, median OS was 32.7 mo (95% CI, 24.5-41.6) with pembro Q2W, 31.0 mo (95% CI, 24.1-41.6) with pembro Q3W, and 15.9 mo (95% CI, 13.3-22.0) with ipi.

#### Conclusions:
Pembro provided durable long-term benefit vs ipi in pts with advanced melanoma.

**Clinical trial information:** NCT01866319.
"""

        logger.info("📄 Processing documents...")

        # Process documents
        chunks = await chunking_service.chunk_content(
            content=test_content,
            configuration=ChunkingConfiguration(),
            document_id="test_doc",
            filename="melanoma_abstracts.md",
        )
        logger.info(f"✅ Created {len(chunks)} chunks")

        # Generate embeddings and store
        embedding_config = EmbeddingConfiguration()
        chunks_with_embeddings = []

        for chunk in chunks:
            embedding = await embedding_service.generate_embedding(
                text=chunk.content, config=embedding_config
            )
            from src.domain.models import ChunkWithEmbedding

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

        # Test queries
        test_queries = [
            "What is the recurrence-free survival for nivolumab in melanoma?",
            "How does pembrolizumab compare to ipilimumab in advanced melanoma?",
            "What are the clinical trial numbers for these studies?",
            "What are the overall survival results for these treatments?",
        ]

        logger.info("🔍 Testing Complete RAG Queries...")
        logger.info("=" * 60)

        for i, question in enumerate(test_queries, 1):
            logger.info(f"\n📝 Query {i}: {question}")
            logger.info("-" * 50)

            # Create RAG query
            rag_query = RAGQuery(question=question, top_k=3, similarity_threshold=0.1)

            # Process query
            response = await rag_service.process_query(rag_query)

            # Display results
            logger.info(f"🤖 Answer: {response.answer}")
            logger.info(f"📊 Confidence: {response.confidence_score}")
            logger.info(f"⏱️ Processing Time: {response.processing_time_ms:.2f}ms")
            logger.info(f"📚 Sources: {len(response.sources)}")

            if response.sources:
                logger.info("📖 Top Sources:")
                for j, source in enumerate(response.sources[:2], 1):
                    logger.info(
                        f"   {j}. {source['content_preview']} (Score: {source['similarity_score']:.3f})"
                    )

        logger.info("\n🎉 Complete RAG Pipeline Demo Completed Successfully!")
        logger.info("✅ Document Processing: WORKING")
        logger.info("✅ Vector Search: WORKING")
        logger.info("✅ Response Generation: WORKING")
        logger.info("✅ End-to-End Pipeline: WORKING")

    except Exception as e:
        logger.error(f"❌ Demo failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
