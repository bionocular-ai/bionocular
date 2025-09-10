"""Implementation of embedding generation service for bio-clinical text.

This service provides bio-clinical embedding generation using sentence-transformers
with specialized models trained on medical and scientific literature.
"""

import logging

from sentence_transformers import SentenceTransformer

from ..domain.constants import LogMessages
from ..domain.interfaces import EmbeddingServiceInterface
from ..domain.models import EmbeddingConfiguration

logger = logging.getLogger(__name__)


class BioClinicalEmbeddingService(EmbeddingServiceInterface):
    """Bio-clinical embedding service using sentence-transformers.

    This service provides specialized embedding generation for medical and
    scientific text using models trained on biomedical literature.
    """

    def __init__(self):
        """Initialize the embedding service."""
        self._models: dict[str, SentenceTransformer] = {}
        self._model_dimensions: dict[str, int] = {}

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
            ValueError: If text is empty or model fails to load
            RuntimeError: If embedding generation fails
        """
        if not text.strip():
            raise ValueError("Text cannot be empty")

        try:
            model = await self._get_model(config.model_name.value)
            embedding = model.encode(
                text,
                normalize_embeddings=config.normalize_embeddings,
                show_progress_bar=False,
            )
            return embedding.tolist()

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
            model = await self._get_model(config.model_name.value)
            embeddings = model.encode(
                valid_texts,
                batch_size=config.batch_size,
                normalize_embeddings=config.normalize_embeddings,
                show_progress_bar=True,
            )
            return [embedding.tolist() for embedding in embeddings]

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

        if model_name not in self._model_dimensions:
            try:
                model = await self._get_model(model_name)
                # Get dimension by encoding a dummy text
                dummy_embedding = model.encode(["dummy"], normalize_embeddings=False)
                self._model_dimensions[model_name] = len(dummy_embedding[0])

            except Exception as e:
                logger.error(f"Failed to determine embedding dimension: {e}")
                raise RuntimeError(f"Cannot determine embedding dimension: {e}") from e

        return self._model_dimensions[model_name]

    async def validate_model(self, model_name: str) -> bool:
        """Validate that the model is available and working.

        Args:
            model_name: Name of the model to validate

        Returns:
            True if model is valid and working, False otherwise
        """
        try:
            await self._get_model(model_name)
            return True

        except Exception as e:
            logger.error(f"Model validation failed for {model_name}: {e}")
            return False

    async def cleanup_models(self) -> None:
        """Clean up loaded models to free memory.

        This method should be called when the service is no longer needed
        to free up GPU/CPU memory used by loaded models.
        """
        for model_name, model in self._models.items():
            logger.info(LogMessages.MODEL_CLEANUP.format(model_name=model_name))
            del model

        self._models.clear()
        self._model_dimensions.clear()
        logger.info(LogMessages.MODEL_CLEANUP_COMPLETE)

    async def _get_model(self, model_name: str) -> SentenceTransformer:
        """Get or load the specified model.

        Args:
            model_name: Name of the model to load

        Returns:
            Loaded SentenceTransformer model

        Raises:
            RuntimeError: If model fails to load
        """
        if model_name not in self._models:
            logger.info(LogMessages.MODEL_LOADING.format(model_name=model_name))

            try:
                self._models[model_name] = SentenceTransformer(model_name)
                logger.info(LogMessages.MODEL_LOADED.format(model_name=model_name))

            except Exception as e:
                logger.error(f"Failed to load model {model_name}: {e}")
                raise RuntimeError(f"Model loading failed: {e}") from e

        return self._models[model_name]

    def get_loaded_models(self) -> list[str]:
        """Get list of currently loaded models.

        Returns:
            List of model names that are currently loaded
        """
        return list(self._models.keys())

    def is_model_loaded(self, model_name: str) -> bool:
        """Check if a specific model is loaded.

        Args:
            model_name: Name of the model to check

        Returns:
            True if model is loaded, False otherwise
        """
        return model_name in self._models
