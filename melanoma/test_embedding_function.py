#!/usr/bin/env python3
"""Test script to verify ChromaDB embedding function works."""

from src.infrastructure.langchain.vector_store import ChromaDBEmbeddingFunction


def test_embedding_function():
    """Test that ChromaDB embedding function works."""
    print("Testing ChromaDB embedding function...")

    try:
        # Create embedding function
        embedding_func = ChromaDBEmbeddingFunction()
        print("✅ ChromaDBEmbeddingFunction created successfully")

        # Test embedding generation
        test_texts = ["This is a test clinical trial abstract", "NCT123456789"]
        embeddings = embedding_func(test_texts)

        print("✅ Embeddings generated successfully")
        print(f"   Number of texts: {len(test_texts)}")
        print(f"   Number of embeddings: {len(embeddings)}")
        print(f"   Embedding dimension: {len(embeddings[0]) if embeddings else 'N/A'}")

        # Test single query embedding
        query_embedding = embedding_func.embed_query("NCT number clinical trial")
        print("✅ Query embedding generated successfully")
        print(f"   Query embedding dimension: {len(query_embedding)}")

        print("✅ All embedding function tests passed!")
        return True

    except Exception as e:
        print(f"❌ Embedding function test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_embedding_function()
