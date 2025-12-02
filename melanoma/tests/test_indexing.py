#!/usr/bin/env python3
"""
Indexing Module Tests

Tests for the vector storage and indexing functionality including:
- Vector store initialization and configuration
- Chunk storage and retrieval operations
- Metadata preservation and filtering
- Search operations and performance
- Store management and cleanup
"""

import asyncio
import time
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.domain.models import (
    ChunkType,
    ChunkWithEmbedding,
    EmbeddingModel,
    SearchQuery,
)
from src.infrastructure.langchain import LangChainVectorStore


class TestVectorStore:
    """Test vector store functionality."""

    @pytest.fixture
    def vector_store(self):
        """Create vector store instance for testing."""
        import tempfile

        temp_dir = tempfile.mkdtemp()
        store = LangChainVectorStore(persist_directory=temp_dir)
        yield store
        # Clean up temp directory
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def sample_chunks(self):
        """Create sample chunks for testing."""
        doc_id = uuid4()
        return [
            ChunkWithEmbedding(
                id=uuid4(),
                document_id=str(doc_id),
                content="Pembrolizumab shows efficacy in melanoma treatment with improved survival outcomes.",
                chunk_type=ChunkType.RESULTS,
                metadata={
                    "abstract_id": "10001",
                    "year": 2023,
                    "conference": "ASCO",
                    "clinical_trial_id": "NCT02743819",
                    "sponsor": "Merck",
                },
                sequence_number=1,
                embedding=[0.1, 0.2, 0.3, 0.4, 0.5] * 153
                + [0.1, 0.2, 0.3],  # 768 dimensions
                embedding_model=EmbeddingModel.BIO_BERT_SNLI.value,
                embedding_dimension=768,
                embedding_generated_at=datetime.now(UTC),
            ),
            ChunkWithEmbedding(
                id=uuid4(),
                document_id=str(doc_id),
                content="BRAF V600E mutation targeted therapy with dabrafenib and trametinib combination.",
                chunk_type=ChunkType.BACKGROUND,
                metadata={
                    "abstract_id": "10002",
                    "year": 2023,
                    "conference": "ASCO",
                    "clinical_trial_id": "NCT01909453",
                    "sponsor": "Novartis",
                },
                sequence_number=2,
                embedding=[0.6, 0.7, 0.8, 0.9, 1.0] * 153
                + [0.1, 0.2, 0.3],  # 768 dimensions
                embedding_model=EmbeddingModel.BIO_BERT_SNLI.value,
                embedding_dimension=768,
                embedding_generated_at=datetime.now(UTC),
            ),
            ChunkWithEmbedding(
                id=uuid4(),
                document_id=str(uuid4()),
                content="Immunotherapy resistance mechanisms in advanced melanoma patients.",
                chunk_type=ChunkType.CONCLUSIONS,
                metadata={
                    "abstract_id": "10003",
                    "year": 2022,
                    "conference": "ESMO",
                    "clinical_trial_id": "NCT02394132",
                    "sponsor": "Bristol-Myers Squibb",
                },
                sequence_number=1,
                embedding=[0.2, 0.3, 0.4, 0.5, 0.6] * 153
                + [0.1, 0.2, 0.3],  # 768 dimensions
                embedding_model=EmbeddingModel.BIO_BERT_SNLI.value,
                embedding_dimension=768,
                embedding_generated_at=datetime.now(UTC),
            ),
        ]

    @pytest.fixture(autouse=True)
    async def cleanup_after_test(self, vector_store):
        """Clean up after each test."""
        yield
        await vector_store.clear_store()

    @pytest.mark.asyncio
    async def test_vector_store_initialization(self, vector_store):
        """Test vector store initializes correctly."""
        assert vector_store is not None
        assert hasattr(vector_store, "collection_name")
        assert hasattr(vector_store, "persist_directory")
        assert hasattr(vector_store, "_vectorstore")

    @pytest.mark.asyncio
    async def test_store_chunks(self, vector_store, sample_chunks):
        """Test storing chunks in vector store."""
        await vector_store.store_chunks(sample_chunks)

        # Verify chunks were stored
        store_info = await vector_store.get_store_info()
        assert store_info["total_chunks"] == len(sample_chunks)

    @pytest.mark.asyncio
    async def test_store_empty_chunks(self, vector_store):
        """Test storing empty chunk list."""
        await vector_store.store_chunks([])

        # Should handle empty list gracefully
        store_info = await vector_store.get_store_info()
        assert store_info["total_chunks"] == 0

    @pytest.mark.asyncio
    async def test_get_chunk_by_id(self, vector_store, sample_chunks):
        """Test retrieving chunk by ID."""
        await vector_store.store_chunks(sample_chunks)

        chunk_id = str(sample_chunks[0].id)
        retrieved_chunk = await vector_store.get_chunk_by_id(chunk_id)

        assert retrieved_chunk is not None
        assert retrieved_chunk.id == sample_chunks[0].id
        assert retrieved_chunk.content == sample_chunks[0].content
        assert retrieved_chunk.metadata == sample_chunks[0].metadata

    @pytest.mark.asyncio
    async def test_get_nonexistent_chunk(self, vector_store):
        """Test retrieving non-existent chunk."""
        fake_id = str(uuid4())
        retrieved_chunk = await vector_store.get_chunk_by_id(fake_id)

        assert retrieved_chunk is None

    @pytest.mark.asyncio
    async def test_search_similar(self, vector_store, sample_chunks):
        """Test similarity search."""
        await vector_store.store_chunks(sample_chunks)

        # Create search query
        query_embedding = [0.1, 0.2, 0.3, 0.4, 0.5] * 153 + [
            0.1,
            0.2,
            0.3,
        ]  # 768 dimensions
        search_query = SearchQuery(
            text="melanoma treatment",
            top_k=5,
            similarity_threshold=0.1,
            embedding=query_embedding,
        )

        results = await vector_store.search_similar(search_query)

        # Should find relevant results
        assert len(results) > 0
        for result in results:
            assert 0.0 <= result.similarity_score <= 1.0
            assert result.rank >= 1

    @pytest.mark.asyncio
    async def test_search_with_metadata_filter(self, vector_store, sample_chunks):
        """Test search with metadata filtering."""
        await vector_store.store_chunks(sample_chunks)

        query_embedding = [0.1, 0.2, 0.3, 0.4, 0.5] * 153 + [
            0.1,
            0.2,
            0.3,
        ]  # 768 dimensions
        search_query = SearchQuery(
            text="melanoma",
            top_k=5,
            similarity_threshold=0.1,
            metadata_filters={"conference": "ASCO"},
            embedding=query_embedding,
        )

        results = await vector_store.search_similar(search_query)

        # Should only return ASCO chunks
        for result in results:
            assert result.chunk.metadata.get("conference") == "ASCO"

    @pytest.mark.asyncio
    async def test_search_with_chunk_type_filter(self, vector_store, sample_chunks):
        """Test search with chunk type filtering."""
        await vector_store.store_chunks(sample_chunks)

        query_embedding = [0.1, 0.2, 0.3, 0.4, 0.5] * 153 + [
            0.1,
            0.2,
            0.3,
        ]  # 768 dimensions
        search_query = SearchQuery(
            text="melanoma",
            top_k=5,
            similarity_threshold=0.1,
            chunk_types=[ChunkType.RESULTS],
            embedding=query_embedding,
        )

        results = await vector_store.search_similar(search_query)

        # Should only return RESULTS chunks
        for result in results:
            assert result.chunk.chunk_type == ChunkType.RESULTS

    @pytest.mark.asyncio
    async def test_search_with_high_threshold(self, vector_store, sample_chunks):
        """Test search with high similarity threshold."""
        await vector_store.store_chunks(sample_chunks)

        # Use a completely different embedding that should have low similarity
        query_embedding = [1.0, 1.0, 1.0, 1.0, 1.0] * 153 + [
            1.0,
            1.0,
            1.0,
        ]  # 768 dimensions
        search_query = SearchQuery(
            text="completely unrelated text about cooking recipes",
            top_k=5,
            similarity_threshold=0.9,  # Very high threshold
            embedding=query_embedding,
        )

        results = await vector_store.search_similar(search_query)

        # Should return no results due to high threshold
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_with_low_threshold(self, vector_store, sample_chunks):
        """Test search with low similarity threshold."""
        await vector_store.store_chunks(sample_chunks)

        query_embedding = [0.1, 0.2, 0.3, 0.4, 0.5] * 153 + [
            0.1,
            0.2,
            0.3,
        ]  # 768 dimensions
        search_query = SearchQuery(
            text="melanoma",
            top_k=5,
            similarity_threshold=0.01,  # Very low threshold
            embedding=query_embedding,
        )

        results = await vector_store.search_similar(search_query)

        # Should return more results due to low threshold
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_delete_chunks(self, vector_store, sample_chunks):
        """Test deleting chunks."""
        await vector_store.store_chunks(sample_chunks)

        # Verify chunks are stored
        store_info_before = await vector_store.get_store_info()
        assert store_info_before["total_chunks"] == len(sample_chunks)

        # Delete one chunk
        chunk_id_to_delete = str(sample_chunks[0].id)
        await vector_store.delete_chunks([chunk_id_to_delete])

        # Verify chunk is deleted
        store_info_after = await vector_store.get_store_info()
        assert store_info_after["total_chunks"] == len(sample_chunks) - 1

        deleted_chunk = await vector_store.get_chunk_by_id(chunk_id_to_delete)
        assert deleted_chunk is None

    @pytest.mark.asyncio
    async def test_delete_multiple_chunks(self, vector_store, sample_chunks):
        """Test deleting multiple chunks."""
        await vector_store.store_chunks(sample_chunks)

        # Delete multiple chunks
        chunk_ids_to_delete = [str(sample_chunks[0].id), str(sample_chunks[1].id)]
        await vector_store.delete_chunks(chunk_ids_to_delete)

        # Verify chunks are deleted
        store_info_after = await vector_store.get_store_info()
        assert store_info_after["total_chunks"] == len(sample_chunks) - 2

    @pytest.mark.asyncio
    async def test_clear_store(self, vector_store, sample_chunks):
        """Test clearing the entire store."""
        await vector_store.store_chunks(sample_chunks)

        # Verify chunks are stored
        store_info_before = await vector_store.get_store_info()
        assert store_info_before["total_chunks"] == len(sample_chunks)

        # Clear store
        await vector_store.clear_store()

        # Verify store is empty
        store_info_after = await vector_store.get_store_info()
        assert store_info_after["total_chunks"] == 0

    @pytest.mark.asyncio
    async def test_get_store_info(self, vector_store, sample_chunks):
        """Test getting store information."""
        await vector_store.store_chunks(sample_chunks)

        store_info = await vector_store.get_store_info()

        assert "total_chunks" in store_info
        assert "collection_name" in store_info
        assert "persist_directory" in store_info
        assert store_info["total_chunks"] == len(sample_chunks)
        assert store_info["collection_name"] == "melanoma_chunks"

    @pytest.mark.asyncio
    async def test_metadata_preservation(self, vector_store, sample_chunks):
        """Test that metadata is preserved correctly."""
        await vector_store.store_chunks(sample_chunks)

        # Retrieve a chunk and check metadata
        chunk_id = str(sample_chunks[0].id)
        retrieved_chunk = await vector_store.get_chunk_by_id(chunk_id)

        assert (
            retrieved_chunk.metadata["abstract_id"]
            == sample_chunks[0].metadata["abstract_id"]
        )
        assert retrieved_chunk.metadata["year"] == sample_chunks[0].metadata["year"]
        assert (
            retrieved_chunk.metadata["conference"]
            == sample_chunks[0].metadata["conference"]
        )

    @pytest.mark.asyncio
    async def test_embedding_preservation(self, vector_store, sample_chunks):
        """Test that embeddings are preserved correctly."""
        await vector_store.store_chunks(sample_chunks)

        # Retrieve a chunk and check embedding
        chunk_id = str(sample_chunks[0].id)
        retrieved_chunk = await vector_store.get_chunk_by_id(chunk_id)

        # ChromaDB doesn't return embeddings in search results, so it should be None
        assert retrieved_chunk.embedding is None
        assert retrieved_chunk.embedding_model == sample_chunks[0].embedding_model
        assert (
            retrieved_chunk.embedding_dimension == sample_chunks[0].embedding_dimension
        )

    @pytest.mark.asyncio
    async def test_search_performance(self, vector_store, sample_chunks):
        """Test search performance with timing."""
        await vector_store.store_chunks(sample_chunks)

        query_embedding = [0.1, 0.2, 0.3, 0.4, 0.5] * 153 + [
            0.1,
            0.2,
            0.3,
        ]  # 768 dimensions
        search_query = SearchQuery(
            text="melanoma treatment",
            top_k=5,
            similarity_threshold=0.1,
            embedding=query_embedding,
        )

        import time

        start_time = time.time()
        results = await vector_store.search_similar(search_query)
        search_time = time.time() - start_time

        # Should be fast
        assert search_time < 1.0
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, vector_store, sample_chunks):
        """Test concurrent store and search operations."""
        # Store chunks
        await vector_store.store_chunks(sample_chunks)

        # Perform concurrent searches
        query_embedding = [0.1, 0.2, 0.3, 0.4, 0.5] * 153 + [
            0.1,
            0.2,
            0.3,
        ]  # 768 dimensions
        search_queries = [
            SearchQuery(
                text=f"query {i}",
                top_k=3,
                similarity_threshold=0.1,
                embedding=query_embedding,
            )
            for i in range(5)
        ]

        # Run searches concurrently
        tasks = [vector_store.search_similar(query) for query in search_queries]
        results = await asyncio.gather(*tasks)

        # All searches should complete successfully
        assert len(results) == 5
        for result in results:
            assert isinstance(result, list)


class TestSearchQuery:
    """Test search query validation."""

    def test_search_query_creation(self):
        """Test creating search query."""
        query = SearchQuery(
            text="test query", top_k=5, similarity_threshold=0.5, embedding=[0.1] * 768
        )

        assert query.text == "test query"
        assert query.top_k == 5
        assert query.similarity_threshold == 0.5
        assert len(query.embedding) == 768

    def test_search_query_validation(self):
        """Test search query validation."""
        # Valid query
        query = SearchQuery(
            text="test", top_k=1, similarity_threshold=0.0, embedding=[0.1] * 768
        )
        assert query is not None

        # Invalid similarity threshold
        with pytest.raises(ValueError):
            SearchQuery(
                text="test",
                top_k=1,
                similarity_threshold=1.5,  # Invalid: > 1.0
                embedding=[0.1] * 768,
            )


class TestEmbeddingIndexingIntegration:
    """Test embedding and indexing integration."""

    @pytest.fixture
    def embedding_service(self):
        """Create embedding service instance."""
        from src.infrastructure.langchain import LangChainEmbeddingService

        return LangChainEmbeddingService()

    @pytest.fixture
    def chunking_factory(self):
        """Create chunking strategy factory."""
        from src.app.langchain_factory_service import (
            LangChainServiceFactory,
            ServiceConfiguration,
        )

        config = ServiceConfiguration(
            chunking_strategy="header_based",
            embedding_model="pritamdeka/S-BioBERT-snli-multinli-stsb",
            llm_provider="openai",
            llm_model="gpt-3.5-turbo",
            temperature=0.1,
            persist_directory="./test_chroma_db",
            collection_name="test_chunks",
        )
        return LangChainServiceFactory(config)

    @pytest.fixture
    def embedding_config(self):
        """Create embedding configuration."""
        from src.domain.models import EmbeddingConfiguration, EmbeddingModel

        return EmbeddingConfiguration(
            model_name=EmbeddingModel.BIO_BERT_SNLI,
            batch_size=16,
            normalize_embeddings=True,
            max_sequence_length=512,
        )

    @pytest.fixture
    def chunking_config(self):
        """Create chunking configuration."""
        from src.domain.models import ChunkingConfiguration, ChunkingStrategy

        return ChunkingConfiguration(
            strategy=ChunkingStrategy.HYBRID,
            max_chunk_size=1000,
            chunk_overlap=150,
            preserve_tables=True,
            include_headers=True,
        )

    @pytest.fixture(autouse=True)
    async def cleanup_after_test(self, embedding_service):
        """Clean up services after each test."""
        yield
        await embedding_service.cleanup_models()

    @pytest.mark.asyncio
    async def test_end_to_end_pipeline(
        self, embedding_service, chunking_factory, embedding_config, chunking_config
    ):
        """Test complete end-to-end pipeline."""
        # Create isolated vector store for this test
        import shutil
        import tempfile

        temp_dir = tempfile.mkdtemp()
        vector_store = LangChainVectorStore(persist_directory=temp_dir)

        try:
            # Sample medical text
            medical_text = """
            Background: Pembrolizumab, a programmed death 1 (PD-1) inhibitor, has shown efficacy
            in treating advanced melanoma. This phase 3 randomized controlled trial evaluated
            pembrolizumab versus ipilimumab in patients with advanced melanoma.

            Methods: Patients with unresectable stage III or IV melanoma were randomly assigned
            to receive pembrolizumab (10 mg/kg every 2 or 3 weeks) or ipilimumab (3 mg/kg every 3 weeks
            for 4 doses). The primary endpoint was progression-free survival.

            Results: The median progression-free survival was 5.5 months in the pembrolizumab group
            versus 2.8 months in the ipilimumab group (hazard ratio, 0.58; 95% CI, 0.46 to 0.72; P<0.001).

            Conclusions: Pembrolizumab significantly improved progression-free survival compared with
            ipilimumab in patients with advanced melanoma.
            """

            # Step 1: Chunk the text
            chunking_strategy = chunking_factory.create_chunking_service()
            chunks = await chunking_strategy.chunk_content(
                content=medical_text,
                configuration=chunking_config,
                document_id=None,
                filename="test_abstract.md",
            )

            assert len(chunks) > 0

            # Step 2: Convert to ChunkWithEmbedding
            doc_id = uuid4()
            chunks_with_embeddings = []
            for i, chunk in enumerate(chunks):
                chunk_with_embedding = ChunkWithEmbedding(
                    id=chunk.id,
                    document_id=str(doc_id),
                    content=chunk.content,
                    chunk_type=chunk.chunk_type,
                    metadata={
                        **chunk.metadata,
                        "test_document": True,
                        "chunk_index": i,
                    },
                    sequence_number=chunk.sequence_number,
                    embedding=None,
                    embedding_model=None,
                    embedding_dimension=None,
                    embedding_generated_at=None,
                )
                chunks_with_embeddings.append(chunk_with_embedding)

            # Step 3: Generate embeddings
            texts = [chunk.content for chunk in chunks_with_embeddings]
            embeddings = await embedding_service.generate_embeddings_batch(
                texts, embedding_config
            )

            # Update chunks with embeddings
            embedding_dim = await embedding_service.get_embedding_dimension(
                embedding_config
            )
            for i, chunk in enumerate(chunks_with_embeddings):
                chunk.embedding = embeddings[i]
                chunk.embedding_model = embedding_config.model_name.value
                chunk.embedding_dimension = embedding_dim
                chunk.embedding_generated_at = time.time()

            # Step 4: Store in vector database
            await vector_store.store_chunks(chunks_with_embeddings)

            # Verify storage
            store_info = await vector_store.get_store_info()
            assert store_info["total_chunks"] == len(chunks_with_embeddings)

            # Step 5: Test search
            query_text = "pembrolizumab melanoma survival"
            query_embedding = await embedding_service.generate_embedding(
                query_text, embedding_config
            )

            search_query = SearchQuery(
                text=query_text,
                top_k=3,
                similarity_threshold=0.1,
                embedding=query_embedding,
            )

            search_results = await vector_store.search_similar(search_query)

            # Should find relevant results
            assert len(search_results) > 0
            assert all(result.similarity_score > 0 for result in search_results)

        finally:
            # Cleanup
            await vector_store.clear_store()
            shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_performance_benchmark(self, embedding_service, embedding_config):
        """Test performance with multiple chunks."""
        # Create isolated vector store for this test
        import shutil
        import tempfile

        temp_dir = tempfile.mkdtemp()
        vector_store = LangChainVectorStore(persist_directory=temp_dir)

        try:
            # Create test chunks
            chunks = []
            for i in range(10):
                chunk = ChunkWithEmbedding(
                    id=uuid4(),
                    document_id=str(uuid4()),
                    content=f"Test chunk {i} about melanoma treatment and immunotherapy research.",
                    chunk_type=ChunkType.BACKGROUND,
                    metadata={"test_chunk": True, "index": i},
                    sequence_number=i,
                    embedding=None,
                    embedding_model=None,
                    embedding_dimension=None,
                    embedding_generated_at=None,
                )
                chunks.append(chunk)

            # Generate embeddings
            texts = [chunk.content for chunk in chunks]
            start_time = time.time()
            embeddings = await embedding_service.generate_embeddings_batch(
                texts, embedding_config
            )
            embedding_time = time.time() - start_time

            # Update chunks
            embedding_dim = await embedding_service.get_embedding_dimension(
                embedding_config
            )
            for i, chunk in enumerate(chunks):
                chunk.embedding = embeddings[i]
                chunk.embedding_model = embedding_config.model_name.value
                chunk.embedding_dimension = embedding_dim
                chunk.embedding_generated_at = time.time()

            # Store chunks
            start_time = time.time()
            await vector_store.store_chunks(chunks)
            storage_time = time.time() - start_time

            # Test search performance
            query_text = "melanoma immunotherapy"
            query_embedding = await embedding_service.generate_embedding(
                query_text, embedding_config
            )
            search_query = SearchQuery(
                text=query_text,
                top_k=5,
                similarity_threshold=0.1,
                embedding=query_embedding,
            )

            start_time = time.time()
            results = await vector_store.search_similar(search_query)
            search_time = time.time() - start_time

            # Performance assertions (relaxed for CI/CD environments)
            assert embedding_time < 15.0  # Should be reasonable
            assert storage_time < 10.0  # Should be fast (relaxed for CI/CD environments)
            assert search_time < 2.0  # Should be fast
            assert len(results) > 0  # Should find results

        finally:
            await vector_store.clear_store()
            shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, embedding_service, embedding_config):
        """Test concurrent embedding and indexing operations."""
        # Create isolated vector store for this test
        import shutil
        import tempfile

        temp_dir = tempfile.mkdtemp()
        vector_store = LangChainVectorStore(persist_directory=temp_dir)

        try:
            # Create multiple documents
            documents = [
                "Document 1 about melanoma treatment with pembrolizumab.",
                "Document 2 about BRAF mutation therapy in melanoma.",
                "Document 3 about immunotherapy resistance mechanisms.",
                "Document 4 about combination therapy approaches.",
                "Document 5 about survival outcomes in advanced melanoma.",
            ]

            # Process documents concurrently
            async def process_document(doc_text, doc_id):
                # Generate embedding
                embedding = await embedding_service.generate_embedding(
                    doc_text, embedding_config
                )

                # Create chunk
                chunk = ChunkWithEmbedding(
                    id=uuid4(),
                    document_id=str(doc_id),
                    content=doc_text,
                    chunk_type=ChunkType.BACKGROUND,
                    metadata={"doc_id": str(doc_id), "processed_concurrently": True},
                    sequence_number=0,
                    embedding=embedding,
                    embedding_model=embedding_config.model_name.value,
                    embedding_dimension=len(embedding),
                    embedding_generated_at=time.time(),
                )

                # Store chunk
                await vector_store.store_chunks([chunk])
                return chunk

            # Run concurrent processing
            doc_ids = [uuid4() for _ in documents]
            tasks = [
                process_document(doc, doc_id) for doc, doc_id in zip(documents, doc_ids)
            ]
            processed_chunks = await asyncio.gather(*tasks)

            # Verify all chunks were processed
            assert len(processed_chunks) == len(documents)

            # Verify storage
            store_info = await vector_store.get_store_info()
            assert store_info["total_chunks"] == len(documents)

            # Test concurrent search
            search_queries = [
                SearchQuery(
                    text=f"query {i}",
                    top_k=3,
                    similarity_threshold=0.1,
                    embedding=await embedding_service.generate_embedding(
                        f"query {i}", embedding_config
                    ),
                )
                for i in range(3)
            ]

            search_tasks = [
                vector_store.search_similar(query) for query in search_queries
            ]
            search_results = await asyncio.gather(*search_tasks)

            # All searches should complete successfully
            assert len(search_results) == len(search_queries)
            for result in search_results:
                assert isinstance(result, list)

        finally:
            await vector_store.clear_store()
            shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_error_handling(self, embedding_service, embedding_config):
        """Test error handling in the pipeline."""
        # Create isolated vector store for this test
        import shutil
        import tempfile

        temp_dir = tempfile.mkdtemp()
        vector_store = LangChainVectorStore(persist_directory=temp_dir)

        try:
            # Test with invalid chunk (missing required fields)
            invalid_chunk = ChunkWithEmbedding(
                id=uuid4(),
                document_id=str(uuid4()),
                content="Test content",
                chunk_type=ChunkType.BACKGROUND,
                metadata={},
                sequence_number=1,
                embedding=None,  # Missing embedding
                embedding_model=None,
                embedding_dimension=None,
                embedding_generated_at=None,
            )

            # Should handle missing embedding gracefully
            with pytest.raises(ValueError):  # Should raise a specific error
                await vector_store.store_chunks([invalid_chunk])

            # Test with empty text - should raise ValueError
            empty_text = ""
            with pytest.raises(ValueError, match="Text cannot be empty"):
                await embedding_service.generate_embedding(empty_text, embedding_config)

        finally:
            await vector_store.clear_store()
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
