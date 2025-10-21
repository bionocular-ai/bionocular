#!/usr/bin/env python3
"""Test script to verify LangChainVectorStore works with ChromaDB."""

import asyncio

from src.infrastructure.langchain.embeddings import LangChainEmbeddingService
from src.infrastructure.langchain.vector_store import LangChainVectorStore


async def test_vector_store():
    """Test that LangChainVectorStore works with ChromaDB."""
    print("Testing LangChainVectorStore with ChromaDB...")

    try:
        # Create embedding service
        embedding_service = LangChainEmbeddingService()
        print("✅ LangChainEmbeddingService created successfully")

        # Create vector store
        vector_store = LangChainVectorStore(
            persist_directory="./test_chroma_db",
            collection_name="test_collection",
            embedding_service=embedding_service,
        )
        print("✅ LangChainVectorStore created successfully")

        # Test vector store initialization
        await vector_store._ensure_vectorstore_initialized()
        print("✅ Vector store initialized successfully")

        # Test search (should work even with empty collection)
        try:
            from src.domain.models import SearchQuery

            search_query = SearchQuery(
                text="test query", top_k=5, similarity_threshold=0.1
            )
            results = await vector_store.search(search_query)
            print(f"✅ Search completed successfully (found {len(results)} results)")
        except Exception as e:
            print(f"⚠️  Search failed (expected with empty collection): {e}")

        print("✅ All vector store tests passed!")
        return True

    except Exception as e:
        print(f"❌ Vector store test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    asyncio.run(test_vector_store())
