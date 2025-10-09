"""LangChain factory service for service instantiation and configuration.

This service provides a factory pattern for creating and configuring LangChain
services, ensuring proper dependency injection and configuration management
while maintaining clean architecture principles.
"""

import logging
from typing import Any, Optional

from langchain_core.language_models import BaseLLM

from ..domain.models import (
    ChunkingConfiguration,
    EmbeddingConfiguration,
    EmbeddingModel,
)
from ..infrastructure.langchain import (
    LangChainChunkingService,
    LangChainEmbeddingService,
    LangChainLLMService,
    LangChainVectorStore,
)
from .clinical_extraction_service import ClinicalExtractionService
from .pipeline_service import EndToEndPipelineService, PipelineConfiguration
from .rag_orchestration_service import LangChainRAGService, RAGPipelineOrchestrator

logger = logging.getLogger(__name__)


class ServiceConfiguration:
    """Configuration for LangChain services.

    This class encapsulates all configuration options for LangChain services,
    providing a clean interface for service setup and customization.
    """

    def __init__(
        self,
        # Chunking configuration
        chunking_strategy: str = "header_based",
        max_chunk_size: int = 1000,
        chunk_overlap: int = 200,
        # Embedding configuration
        embedding_model: str = "pritamdeka/S-BioBERT-snli-multinli-stsb",
        batch_size: int = 32,
        normalize_embeddings: bool = True,
        # Vector store configuration
        persist_directory: str = "./chroma_db",
        collection_name: str = "melanoma_chunks",
        # LLM configuration
        llm_provider: str = "openai",
        llm_model: str = "gpt-3.5-turbo",
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        # Clinical configuration
        clinical_prompts_path: Optional[str] = None,
        # Additional configuration
        custom_config: Optional[dict[str, Any]] = None,
    ):
        """Initialize service configuration.

        Args:
            chunking_strategy: Chunking strategy to use
            max_chunk_size: Maximum chunk size in characters
            chunk_overlap: Overlap between chunks
            embedding_model: Embedding model to use
            batch_size: Batch size for embedding generation
            normalize_embeddings: Whether to normalize embeddings
            persist_directory: Directory to persist vector store
            collection_name: Name of the collection
            llm_provider: LLM provider to use
            llm_model: LLM model to use
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate
            clinical_prompts_path: Path to clinical prompts file
            custom_config: Additional custom configuration
        """
        self.chunking_strategy = chunking_strategy
        self.max_chunk_size = max_chunk_size
        self.chunk_overlap = chunk_overlap
        self.embedding_model = embedding_model
        self.batch_size = batch_size
        self.normalize_embeddings = normalize_embeddings
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.clinical_prompts_path = clinical_prompts_path
        self.custom_config = custom_config or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary.

        Returns:
            Configuration dictionary
        """
        return {
            "chunking_strategy": self.chunking_strategy,
            "max_chunk_size": self.max_chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "embedding_model": self.embedding_model,
            "batch_size": self.batch_size,
            "normalize_embeddings": self.normalize_embeddings,
            "persist_directory": self.persist_directory,
            "collection_name": self.collection_name,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "clinical_prompts_path": self.clinical_prompts_path,
            "custom_config": self.custom_config,
        }


class LangChainServiceFactory:
    """Factory for creating and configuring LangChain services.

    This factory provides methods for creating and configuring all LangChain
    services with proper dependency injection and configuration management.
    """

    def __init__(self, configuration: Optional[ServiceConfiguration] = None):
        """Initialize the LangChain service factory.

        Args:
            configuration: Service configuration
        """
        self.configuration = configuration or ServiceConfiguration()
        self._created_services: dict[str, Any] = {}

        logger.info("LangChain service factory initialized")

    def create_chunking_service(
        self, custom_config: Optional[ChunkingConfiguration] = None
    ) -> LangChainChunkingService:
        """Create a LangChain chunking service.

        Args:
            custom_config: Custom chunking configuration

        Returns:
            Configured chunking service
        """
        try:
            if custom_config is None:
                from ..domain.models import ChunkingStrategy

                custom_config = ChunkingConfiguration(
                    strategy=ChunkingStrategy(self.configuration.chunking_strategy),
                    max_chunk_size=self.configuration.max_chunk_size,
                    chunk_overlap=self.configuration.chunk_overlap,
                )

            service = LangChainChunkingService(custom_config)
            self._created_services["chunking"] = service

            logger.info(
                f"Chunking service created with strategy: {custom_config.strategy}"
            )
            return service

        except Exception as e:
            logger.error(f"Failed to create chunking service: {e}")
            raise RuntimeError(f"Chunking service creation failed: {e}") from e

    def create_embedding_service(self) -> LangChainEmbeddingService:
        """Create a LangChain embedding service.

        Returns:
            Configured embedding service
        """
        try:
            service = LangChainEmbeddingService()
            self._created_services["embedding"] = service

            logger.info("Embedding service created")
            return service

        except Exception as e:
            logger.error(f"Failed to create embedding service: {e}")
            raise RuntimeError(f"Embedding service creation failed: {e}") from e

    def create_vector_store(
        self, embedding_service: Optional[LangChainEmbeddingService] = None
    ) -> LangChainVectorStore:
        """Create a LangChain vector store.

        Args:
            embedding_service: Optional embedding service for initialization

        Returns:
            Configured vector store
        """
        try:
            if embedding_service is None:
                embedding_service = self.create_embedding_service()

            # Get embedding function
            embedding_config = EmbeddingConfiguration(
                model_name=EmbeddingModel(self.configuration.embedding_model),
                batch_size=self.configuration.batch_size,
                normalize_embeddings=self.configuration.normalize_embeddings,
            )

            # Create vector store
            service = LangChainVectorStore(
                persist_directory=self.configuration.persist_directory,
                collection_name=self.configuration.collection_name,
                embedding_function=embedding_service._get_embeddings(embedding_config),
                embedding_service=embedding_service,
            )

            self._created_services["vector_store"] = service

            logger.info(
                f"Vector store created at: {self.configuration.persist_directory}"
            )
            return service

        except Exception as e:
            logger.error(f"Failed to create vector store: {e}")
            raise RuntimeError(f"Vector store creation failed: {e}") from e

    def create_llm_service(self) -> LangChainLLMService:
        """Create a LangChain LLM service.

        Returns:
            Configured LLM service
        """
        try:
            service = LangChainLLMService(provider=self.configuration.llm_provider)
            self._created_services["llm"] = service

            logger.info(
                f"LLM service created with provider: {self.configuration.llm_provider}"
            )
            return service

        except Exception as e:
            logger.error(f"Failed to create LLM service: {e}")
            raise RuntimeError(f"LLM service creation failed: {e}") from e

    def create_clinical_service(
        self, llm: Optional[BaseLLM] = None
    ) -> ClinicalExtractionService:
        """Create a clinical extraction service.

        Args:
            llm: Optional LLM instance

        Returns:
            Configured clinical service
        """
        try:
            if llm is None:
                llm_service = self.create_llm_service()
                llm = llm_service.get_llm(
                    model_name=self.configuration.llm_model,
                    temperature=self.configuration.temperature,
                    max_tokens=self.configuration.max_tokens,
                )

            service = ClinicalExtractionService(
                llm=llm,
                prompts_path=self.configuration.clinical_prompts_path,
            )

            self._created_services["clinical"] = service

            logger.info("Clinical extraction service created")
            return service

        except Exception as e:
            logger.error(f"Failed to create clinical service: {e}")
            raise RuntimeError(f"Clinical service creation failed: {e}") from e

    def create_rag_service(
        self,
        chunking_service: Optional[LangChainChunkingService] = None,
        embedding_service: Optional[LangChainEmbeddingService] = None,
        vector_store: Optional[LangChainVectorStore] = None,
        llm_service: Optional[LangChainLLMService] = None,
    ) -> LangChainRAGService:
        """Create a complete RAG service.

        Args:
            chunking_service: Optional chunking service
            embedding_service: Optional embedding service
            vector_store: Optional vector store
            llm_service: Optional LLM service

        Returns:
            Configured RAG service
        """
        try:
            # Create services if not provided
            if chunking_service is None:
                chunking_service = self.create_chunking_service()
            if embedding_service is None:
                embedding_service = self.create_embedding_service()
            if vector_store is None:
                vector_store = self.create_vector_store(embedding_service)
            if llm_service is None:
                llm_service = self.create_llm_service()

            # Create RAG pipeline orchestrator
            orchestrator = RAGPipelineOrchestrator(
                chunking_service=chunking_service,
                embedding_service=embedding_service,
                vector_store=vector_store,
                llm_service=llm_service,
            )

            # Create LLM instance
            llm = llm_service.get_llm(
                model_name=self.configuration.llm_model,
                temperature=self.configuration.temperature,
                max_tokens=self.configuration.max_tokens,
            )

            # Create RAG service
            service = LangChainRAGService(
                pipeline_orchestrator=orchestrator,
                llm=llm,
                temperature=self.configuration.temperature,
            )

            self._created_services["rag"] = service

            logger.info("RAG service created successfully")
            return service

        except Exception as e:
            logger.error(f"Failed to create RAG service: {e}")
            raise RuntimeError(f"RAG service creation failed: {e}") from e

    def create_pipeline_service(
        self, custom_config: Optional[PipelineConfiguration] = None
    ) -> EndToEndPipelineService:
        """Create a complete end-to-end pipeline service.

        Args:
            custom_config: Custom pipeline configuration

        Returns:
            Configured pipeline service
        """
        try:
            if custom_config is None:
                # Create pipeline configuration from service configuration
                from ..domain.models import ChunkingStrategy

                chunking_config = ChunkingConfiguration(
                    strategy=ChunkingStrategy(self.configuration.chunking_strategy),
                    max_chunk_size=self.configuration.max_chunk_size,
                    chunk_overlap=self.configuration.chunk_overlap,
                )

                embedding_config = EmbeddingConfiguration(
                    model_name=EmbeddingModel(self.configuration.embedding_model),
                    batch_size=self.configuration.batch_size,
                    normalize_embeddings=self.configuration.normalize_embeddings,
                )

                vector_store_config = {
                    "persist_directory": self.configuration.persist_directory,
                    "collection_name": self.configuration.collection_name,
                }

                llm_config = {
                    "provider": self.configuration.llm_provider,
                    "model_name": self.configuration.llm_model,
                    "temperature": self.configuration.temperature,
                    "max_tokens": self.configuration.max_tokens,
                }

                clinical_config = {
                    "prompts_path": self.configuration.clinical_prompts_path,
                }

                custom_config = PipelineConfiguration(
                    chunking_config=chunking_config,
                    embedding_config=embedding_config,
                    vector_store_config=vector_store_config,
                    llm_config=llm_config,
                    clinical_config=clinical_config,
                )

            service = EndToEndPipelineService(configuration=custom_config)
            self._created_services["pipeline"] = service

            logger.info("End-to-end pipeline service created successfully")
            return service

        except Exception as e:
            logger.error(f"Failed to create pipeline service: {e}")
            raise RuntimeError(f"Pipeline service creation failed: {e}") from e

    def get_created_services(self) -> dict[str, Any]:
        """Get all created services.

        Returns:
            Dictionary of created services
        """
        return self._created_services.copy()

    def cleanup_services(self) -> None:
        """Clean up all created services."""
        try:
            for service_name, service in self._created_services.items():
                if hasattr(service, "cleanup_models"):
                    service.cleanup_models()
                logger.info(f"Cleaned up service: {service_name}")

            self._created_services.clear()
            logger.info("All services cleaned up successfully")

        except Exception as e:
            logger.error(f"Service cleanup failed: {e}")
            raise RuntimeError(f"Service cleanup failed: {e}") from e

    def update_configuration(self, new_config: ServiceConfiguration) -> None:
        """Update factory configuration.

        Args:
            new_config: New configuration
        """
        self.configuration = new_config
        logger.info("Factory configuration updated")

    def get_factory_statistics(self) -> dict[str, Any]:
        """Get factory statistics.

        Returns:
            Dictionary containing factory statistics
        """
        return {
            "configuration": self.configuration.to_dict(),
            "created_services": list(self._created_services.keys()),
            "total_services": len(self._created_services),
        }
