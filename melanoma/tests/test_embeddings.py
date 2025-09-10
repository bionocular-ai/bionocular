#!/usr/bin/env python3
"""
Embedding Module Tests

Tests for the embedding generation service including:
- Model loading and initialization
- Embedding generation (single and batch)
- Model validation and cleanup
- Performance metrics
"""


import pytest

from src.domain.constants import EmbeddingDefaults
from src.domain.models import (
    EmbeddingConfiguration,
    EmbeddingModel,
)
from src.infrastructure.embedding_service import BioClinicalEmbeddingService


class TestEmbeddingService:
    """Test embedding service functionality."""

    @pytest.fixture
    def embedding_service(self):
        """Create embedding service instance."""
        return BioClinicalEmbeddingService()

    @pytest.fixture
    def embedding_config(self):
        """Create embedding configuration."""
        return EmbeddingConfiguration(
            model_name=EmbeddingModel.BIO_BERT_SNLI,
            batch_size=16,
            normalize_embeddings=True,
        )

    @pytest.mark.asyncio
    async def test_embedding_service_initialization(self, embedding_service):
        """Test embedding service initializes correctly."""
        assert embedding_service is not None
        assert hasattr(embedding_service, "_models")
        assert hasattr(embedding_service, "_model_dimensions")

    @pytest.mark.asyncio
    async def test_model_validation(self, embedding_service):
        """Test model validation works."""
        # Test valid model
        valid_model = "pritamdeka/S-BioBERT-snli-multinli-stsb"
        is_valid = await embedding_service.validate_model(valid_model)
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_embedding_generation_single(
        self, embedding_service, embedding_config
    ):
        """Test single embedding generation."""
        text = "Pembrolizumab shows efficacy in melanoma treatment"

        embedding = await embedding_service.generate_embedding(text, embedding_config)

        assert embedding is not None
        assert isinstance(embedding, list)
        assert len(embedding) > 0
        assert all(isinstance(x, float) for x in embedding)

    @pytest.mark.asyncio
    async def test_embedding_generation_batch(
        self, embedding_service, embedding_config
    ):
        """Test batch embedding generation."""
        texts = [
            "Pembrolizumab immunotherapy for melanoma",
            "BRAF mutation targeted therapy",
            "Clinical trial outcomes in oncology",
        ]

        embeddings = await embedding_service.generate_embeddings_batch(
            texts, embedding_config
        )

        assert embeddings is not None
        assert isinstance(embeddings, list)
        assert len(embeddings) == len(texts)
        assert all(isinstance(emb, list) for emb in embeddings)
        assert all(len(emb) > 0 for emb in embeddings)

    @pytest.mark.asyncio
    async def test_embedding_dimensions(self, embedding_service, embedding_config):
        """Test embedding dimensions are correct."""
        dimension = await embedding_service.get_embedding_dimension(embedding_config)

        assert dimension is not None
        assert isinstance(dimension, int)
        assert dimension > 0
        # Bio-BERT typically has 768 dimensions
        assert dimension == 768

    @pytest.mark.asyncio
    async def test_embedding_consistency(self, embedding_service, embedding_config):
        """Test same text produces same embedding."""
        text = "Consistent embedding test"

        embedding1 = await embedding_service.generate_embedding(text, embedding_config)
        embedding2 = await embedding_service.generate_embedding(text, embedding_config)

        assert embedding1 == embedding2

    @pytest.mark.asyncio
    async def test_embedding_normalization(self, embedding_service):
        """Test embedding normalization works."""
        text = "Normalization test"

        # Test with normalization
        config_normalized = EmbeddingConfiguration(
            model_name=EmbeddingModel.BIO_BERT_SNLI, normalize_embeddings=True
        )
        embedding_norm = await embedding_service.generate_embedding(
            text, config_normalized
        )

        # Test without normalization
        config_not_normalized = EmbeddingConfiguration(
            model_name=EmbeddingModel.BIO_BERT_SNLI, normalize_embeddings=False
        )
        embedding_not_norm = await embedding_service.generate_embedding(
            text, config_not_normalized
        )

        # Normalized embeddings should have different values
        assert embedding_norm != embedding_not_norm

    @pytest.mark.asyncio
    async def test_batch_size_handling(self, embedding_service):
        """Test different batch sizes work correctly."""
        texts = ["Text " + str(i) for i in range(10)]

        # Test small batch size
        config_small = EmbeddingConfiguration(
            model_name=EmbeddingModel.BIO_BERT_SNLI, batch_size=2
        )
        embeddings_small = await embedding_service.generate_embeddings_batch(
            texts, config_small
        )

        # Test large batch size
        config_large = EmbeddingConfiguration(
            model_name=EmbeddingModel.BIO_BERT_SNLI, batch_size=8
        )
        embeddings_large = await embedding_service.generate_embeddings_batch(
            texts, config_large
        )

        assert len(embeddings_small) == len(embeddings_large)
        assert len(embeddings_small) == len(texts)

    @pytest.mark.asyncio
    async def test_model_cleanup(self, embedding_service, embedding_config):
        """Test model cleanup works."""
        # Generate some embeddings to load models
        text = "Cleanup test"
        await embedding_service.generate_embedding(text, embedding_config)

        # Verify models are loaded
        assert len(embedding_service._models) > 0

        # Cleanup
        await embedding_service.cleanup_models()

        # Verify models are cleaned up
        assert len(embedding_service._models) == 0
        assert len(embedding_service._model_dimensions) == 0

    @pytest.mark.asyncio
    async def test_empty_text_handling(self, embedding_service, embedding_config):
        """Test handling of empty text."""
        empty_text = ""

        # Should raise ValueError for empty text
        with pytest.raises(ValueError, match="Text cannot be empty"):
            await embedding_service.generate_embedding(empty_text, embedding_config)

    @pytest.mark.asyncio
    async def test_very_long_text_handling(self, embedding_service, embedding_config):
        """Test handling of very long text."""
        long_text = "This is a very long text. " * 1000  # Very long text

        embedding = await embedding_service.generate_embedding(
            long_text, embedding_config
        )

        assert embedding is not None
        assert isinstance(embedding, list)
        assert len(embedding) > 0

    @pytest.mark.asyncio
    async def test_special_characters_handling(
        self, embedding_service, embedding_config
    ):
        """Test handling of special characters."""
        special_text = "Special chars: !@#$%^&*()_+-=[]{}|;':\",./<>?`~"

        embedding = await embedding_service.generate_embedding(
            special_text, embedding_config
        )

        assert embedding is not None
        assert isinstance(embedding, list)
        assert len(embedding) > 0


class TestEmbeddingConfiguration:
    """Test embedding configuration validation."""

    def test_default_configuration(self):
        """Test default configuration values."""
        config = EmbeddingConfiguration()

        assert config.model_name == EmbeddingDefaults.DEFAULT_MODEL
        assert config.batch_size == EmbeddingDefaults.DEFAULT_BATCH_SIZE
        assert (
            config.normalize_embeddings
            == EmbeddingDefaults.DEFAULT_NORMALIZE_EMBEDDINGS
        )
        assert (
            config.max_sequence_length == EmbeddingDefaults.DEFAULT_MAX_SEQUENCE_LENGTH
        )

    def test_custom_configuration(self):
        """Test custom configuration values."""
        config = EmbeddingConfiguration(
            model_name=EmbeddingModel.SCI_BERT,
            batch_size=64,
            normalize_embeddings=False,
            max_sequence_length=256,
        )

        assert config.model_name == EmbeddingModel.SCI_BERT
        assert config.batch_size == 64
        assert config.normalize_embeddings is False
        assert config.max_sequence_length == 256

    def test_configuration_validation(self):
        """Test configuration validation."""
        # Test invalid batch size
        with pytest.raises(ValueError):
            EmbeddingConfiguration(batch_size=0)

        with pytest.raises(ValueError):
            EmbeddingConfiguration(batch_size=200)

        # Test invalid sequence length
        with pytest.raises(ValueError):
            EmbeddingConfiguration(max_sequence_length=50)

        with pytest.raises(ValueError):
            EmbeddingConfiguration(max_sequence_length=2000)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
