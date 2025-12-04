"""LangChain-based embedding service for clinical text.

This module provides a sophisticated embedding service that leverages LangChain's
HuggingFaceEmbeddings while adding model management, caching, and performance
optimizations for clinical text processing.
"""

import logging
from typing import Optional

from langchain_huggingface import HuggingFaceEmbeddings

from ...domain.constants import EmbeddingDefaults
from ...domain.interfaces import EmbeddingServiceInterface
from ...domain.models import EmbeddingConfiguration, EmbeddingModel

logger = logging.getLogger(__name__)


class ModelManager:
    """Manages embedding model lifecycle and caching.

    This class encapsulates all model management logic including loading,
    caching, and cleanup. It's separated to maintain single responsibility
    and make the model management logic testable.
    """

    def __init__(self):
        """Initialize the model manager."""
        self._models: dict[str, HuggingFaceEmbeddings] = {}
        self._model_dimensions: dict[str, int] = {}
        self._model_metadata: dict[str, dict[str, any]] = {}

    async def get_model(
        self, model_name: str, config: EmbeddingConfiguration
    ) -> HuggingFaceEmbeddings:
        """Get or load the specified model.

        Args:
            model_name: Name of the model to load
            config: Embedding configuration

        Returns:
            Loaded HuggingFaceEmbeddings model

        Raises:
            RuntimeError: If model fails to load
        """
        if model_name not in self._models:
            await self._load_model(model_name, config)

        return self._models[model_name]

    async def _load_model(
        self, model_name: str, config: EmbeddingConfiguration
    ) -> None:
        """Load a new model.

        Args:
            model_name: Name of the model to load
            config: Embedding configuration

        Raises:
            RuntimeError: If model fails to load
        """
        try:
            logger.info(f"Loading LangChain HuggingFaceEmbeddings: {model_name}")

            # Create HuggingFaceEmbeddings instance
            embeddings = HuggingFaceEmbeddings(
                model_name=model_name,
                model_kwargs={
                    "device": "cpu",  # Use CPU for now, can be configured
                    "trust_remote_code": True,  # Allow custom models
                },
                encode_kwargs={
                    "normalize_embeddings": config.normalize_embeddings,
                    "batch_size": config.batch_size,
                },
            )

            # Store the model
            self._models[model_name] = embeddings

            # Get and cache model dimension
            dimension = await self._get_model_dimension(embeddings)
            self._model_dimensions[model_name] = dimension

            # Store model metadata
            self._model_metadata[model_name] = {
                "model_name": model_name,
                "dimension": dimension,
                "normalize_embeddings": config.normalize_embeddings,
                "batch_size": config.batch_size,
            }

            logger.info(
                f"Successfully loaded model {model_name} with dimension {dimension}"
            )

        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            raise RuntimeError(f"Model loading failed: {e}") from e

    async def _get_model_dimension(self, embeddings: HuggingFaceEmbeddings) -> int:
        """Get the dimension of the embedding model.

        Args:
            embeddings: HuggingFaceEmbeddings instance

        Returns:
            Dimension of the embedding vector
        """
        try:
            # Get dimension by embedding a dummy text
            dummy_embedding = embeddings.embed_query("dummy")
            return len(dummy_embedding)
        except Exception as e:
            logger.error(f"Failed to determine model dimension: {e}")
            raise RuntimeError(f"Cannot determine model dimension: {e}") from e

    def get_model_dimension(self, model_name: str) -> Optional[int]:
        """Get cached model dimension.

        Args:
            model_name: Name of the model

        Returns:
            Model dimension if available, None otherwise
        """
        return self._model_dimensions.get(model_name)

    def get_loaded_models(self) -> list[str]:
        """Get list of currently loaded models.

        Returns:
            List of loaded model names
        """
        return list(self._models.keys())

    def is_model_loaded(self, model_name: str) -> bool:
        """Check if a model is loaded.

        Args:
            model_name: Name of the model to check

        Returns:
            True if model is loaded, False otherwise
        """
        return model_name in self._models

    def get_model_metadata(self, model_name: str) -> Optional[dict[str, any]]:
        """Get model metadata.

        Args:
            model_name: Name of the model

        Returns:
            Model metadata if available, None otherwise
        """
        return self._model_metadata.get(model_name)

    async def cleanup_models(self) -> None:
        """Clean up loaded models to free memory.

        This method should be called when the service is no longer needed
        to free up memory used by loaded models.
        """
        try:
            for model_name in list(self._models.keys()):
                logger.info(f"Cleaning up model: {model_name}")
                del self._models[model_name]

            self._models.clear()
            self._model_dimensions.clear()
            self._model_metadata.clear()

            logger.info("Model cleanup completed successfully")

        except Exception as e:
            logger.error(f"Model cleanup failed: {e}")
            raise RuntimeError(f"Model cleanup failed: {e}") from e


class LangChainEmbeddingService(EmbeddingServiceInterface):
    """LangChain-based embedding service for clinical text.

    This service provides sophisticated embedding generation using LangChain's
    HuggingFaceEmbeddings while adding model management, caching, and performance
    optimizations specifically designed for clinical text processing.
    """

    def __init__(self):
        """Initialize the LangChain embedding service."""
        self.model_manager = ModelManager()
        logger.info("LangChain embedding service initialized")

    async def generate_embedding(
        self, text: str, config: EmbeddingConfiguration
    ) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: The text to embed
            config: Embedding configuration

        Returns:
            List of float values representing the embedding vector

        Raises:
            ValueError: If text is empty or invalid
            RuntimeError: If embedding generation fails
        """
        if not text.strip():
            raise ValueError("Text cannot be empty")

        try:
            model = await self.model_manager.get_model(config.model_name.value, config)
            embedding = model.embed_query(text)
            return embedding

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise RuntimeError(f"Embedding generation failed: {e}") from e

    async def generate_embeddings_batch(
        self, texts: list[str], config: EmbeddingConfiguration
    ) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed
            config: Embedding configuration

        Returns:
            List of embedding vectors, one for each input text

        Raises:
            ValueError: If texts list is empty or contains empty strings
            RuntimeError: If batch embedding generation fails
        """
        if not texts:
            raise ValueError("Texts list cannot be empty")

        # Filter out empty texts
        valid_texts = [text for text in texts if text.strip()]
        if not valid_texts:
            raise ValueError("All texts are empty")

        try:
            model = await self.model_manager.get_model(config.model_name.value, config)
            embeddings = model.embed_documents(valid_texts)
            return embeddings

        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            raise RuntimeError(f"Batch embedding generation failed: {e}") from e

    async def get_embedding_dimension(self, config: EmbeddingConfiguration) -> int:
        """Get the dimension of embeddings for the given model.

        Args:
            config: Embedding configuration

        Returns:
            Dimension of the embedding vector

        Raises:
            RuntimeError: If model fails to load or dimension cannot be determined
        """
        model_name = config.model_name.value

        # Check if we already have the dimension cached
        cached_dimension = self.model_manager.get_model_dimension(model_name)
        if cached_dimension is not None:
            return cached_dimension

        # Load the model to get the dimension
        try:
            await self.model_manager.get_model(model_name, config)
            return self.model_manager.get_model_dimension(model_name)

        except Exception as e:
            logger.error(f"Failed to determine embedding dimension: {e}")
            raise RuntimeError(f"Cannot determine embedding dimension: {e}") from e

    async def validate_model(self, model_name: str) -> bool:
        """Validate that the model is available and working.

        Args:
            model_name: Name of the model to validate

        Returns:
            True if model is valid and working, False otherwise
        """
        try:
            # Check if model name is valid
            if model_name not in [model.value for model in EmbeddingModel]:
                logger.warning(f"Invalid model name: {model_name}")
                return False

            # Try to load the model
            config = EmbeddingConfiguration(model_name=EmbeddingModel(model_name))
            await self.model_manager.get_model(model_name, config)
            return True

        except Exception as e:
            logger.error(f"Model validation failed for {model_name}: {e}")
            return False

    async def cleanup_models(self) -> None:
        """Clean up loaded models to free memory.

        This method should be called when the service is no longer needed
        to free up memory used by loaded models.
        """
        await self.model_manager.cleanup_models()

    def get_loaded_models(self) -> list[str]:
        """Get list of currently loaded models.

        Returns:
            List of model names that are currently loaded
        """
        return self.model_manager.get_loaded_models()

    def is_model_loaded(self, model_name: str) -> bool:
        """Check if a specific model is loaded.

        Args:
            model_name: Name of the model to check

        Returns:
            True if model is loaded, False otherwise
        """
        return self.model_manager.is_model_loaded(model_name)

    def get_model_metadata(self, model_name: str) -> Optional[dict[str, any]]:
        """Get metadata for a specific model.

        Args:
            model_name: Name of the model

        Returns:
            Model metadata if available, None otherwise
        """
        return self.model_manager.get_model_metadata(model_name)

    def _get_embeddings(self, config: EmbeddingConfiguration) -> HuggingFaceEmbeddings:
        """Get HuggingFaceEmbeddings instance for vector store.

        Args:
            config: Embedding configuration

        Returns:
            HuggingFaceEmbeddings instance
        """
        # Create a synchronous version for vector store compatibility
        import asyncio
        import threading

        # Use a thread to run the async method to avoid event loop conflicts
        result = None
        exception = None

        def run_async():
            nonlocal result, exception
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    self.model_manager.get_model(config.model_name, config)
                )
            except Exception as e:
                exception = e
            finally:
                loop.close()

        thread = threading.Thread(target=run_async)
        thread.start()
        thread.join()

        if exception:
            raise exception

        if result is None:
            raise RuntimeError("Failed to get embedding model")

        return result

    def get_service_statistics(self) -> dict[str, any]:
        """Get statistics about the embedding service.

        Returns:
            Dictionary containing service statistics
        """
        loaded_models = self.model_manager.get_loaded_models()
        return {
            "loaded_models": loaded_models,
            "total_loaded_models": len(loaded_models),
            "available_models": [model.value for model in EmbeddingModel],
            "default_model": EmbeddingDefaults.DEFAULT_MODEL.value,
        }
