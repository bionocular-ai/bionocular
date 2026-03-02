"""End-to-end pipeline service for clinical RAG processing.

This service provides a complete pipeline for processing clinical abstracts
from ingestion to RAG query processing, orchestrating all components while
maintaining clean architecture principles.
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from ..domain.models import (
    ChunkingConfiguration,
    EmbeddingConfiguration,
    RAGQuery,
    SearchResult,
)

if TYPE_CHECKING:
    from ..infrastructure.langchain import (  # noqa: F401
        LangChainChunkingService,
        LangChainEmbeddingService,
        LangChainLLMService,
        LangChainVectorStore,
    )

from .clinical_extraction_service import ClinicalExtractionService
from .rag_orchestration_service import LangChainRAGService, RAGPipelineOrchestrator

logger = logging.getLogger(__name__)


class PipelineConfiguration:
    """Configuration for the end-to-end pipeline.

    This class encapsulates all configuration options for the pipeline,
    providing a clean interface for pipeline setup and customization.
    """

    def __init__(
        self,
        chunking_config: Optional[ChunkingConfiguration] = None,
        embedding_config: Optional[EmbeddingConfiguration] = None,
        vector_store_config: Optional[dict[str, Any]] = None,
        llm_config: Optional[dict[str, Any]] = None,
        clinical_config: Optional[dict[str, Any]] = None,
    ):
        """Initialize pipeline configuration.

        Args:
            chunking_config: Chunking configuration
            embedding_config: Embedding configuration
            vector_store_config: Vector store configuration
            llm_config: LLM configuration
            clinical_config: Clinical extraction configuration
        """
        self.chunking_config = chunking_config or ChunkingConfiguration()
        self.embedding_config = embedding_config or EmbeddingConfiguration()
        self.vector_store_config = vector_store_config or {}
        self.llm_config = llm_config or {}
        self.clinical_config = clinical_config or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary.

        Returns:
            Configuration dictionary
        """
        return {
            "chunking": self.chunking_config.model_dump(),
            "embedding": self.embedding_config.model_dump(),
            "vector_store": self.vector_store_config,
            "llm": self.llm_config,
            "clinical": self.clinical_config,
        }


class PipelineMetrics:
    """Tracks metrics for the end-to-end pipeline.

    This class encapsulates all metrics tracking logic including
    performance monitoring, quality assessment, and usage statistics.
    """

    def __init__(self) -> None:
        """Initialize pipeline metrics."""
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.documents_processed: int = 0
        self.chunks_created: int = 0
        self.embeddings_generated: int = 0
        self.queries_processed: int = 0
        self.clinical_extractions: int = 0
        self.errors: list[str] = []
        self.performance_metrics: dict[str, float] = {}

    def start_pipeline(self) -> None:
        """Start pipeline execution tracking."""
        self.start_time = datetime.now()
        logger.info("Pipeline metrics tracking started")

    def end_pipeline(self) -> None:
        """End pipeline execution tracking."""
        self.end_time = datetime.now()
        if self.start_time:
            duration = (self.end_time - self.start_time).total_seconds()
            self.performance_metrics["total_duration_seconds"] = duration
        logger.info("Pipeline metrics tracking ended")

    def record_document_processing(self, chunks_count: int) -> None:
        """Record document processing metrics.

        Args:
            chunks_count: Number of chunks created
        """
        self.documents_processed += 1
        self.chunks_created += chunks_count
        logger.debug(f"Document processed: {chunks_count} chunks created")

    def record_embedding_generation(self, embeddings_count: int) -> None:
        """Record embedding generation metrics.

        Args:
            embeddings_count: Number of embeddings generated
        """
        self.embeddings_generated += embeddings_count
        logger.debug(f"Embeddings generated: {embeddings_count}")

    def record_query_processing(self) -> None:
        """Record query processing metrics."""
        self.queries_processed += 1
        logger.debug("Query processed")

    def record_clinical_extraction(self, extractions_count: int) -> None:
        """Record clinical extraction metrics.

        Args:
            extractions_count: Number of clinical extractions performed
        """
        self.clinical_extractions += extractions_count
        logger.debug(f"Clinical extractions performed: {extractions_count}")

    def record_error(self, error: str) -> None:
        """Record an error.

        Args:
            error: Error message
        """
        self.errors.append(f"{datetime.now()}: {error}")
        logger.error(f"Pipeline error recorded: {error}")

    def get_summary(self) -> dict[str, Any]:
        """Get metrics summary.

        Returns:
            Metrics summary dictionary
        """
        duration = None
        if self.start_time and self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()

        return {
            "execution_duration_seconds": duration,
            "documents_processed": self.documents_processed,
            "chunks_created": self.chunks_created,
            "embeddings_generated": self.embeddings_generated,
            "queries_processed": self.queries_processed,
            "clinical_extractions": self.clinical_extractions,
            "error_count": len(self.errors),
            "errors": self.errors,
            "performance_metrics": self.performance_metrics,
        }


class EndToEndPipelineService:
    """End-to-end pipeline service for clinical RAG processing.

    This service provides a complete pipeline for processing clinical abstracts
    from ingestion to RAG query processing, orchestrating all components while
    maintaining clean architecture principles.
    """

    def __init__(
        self,
        configuration: Optional[PipelineConfiguration] = None,
    ):
        """Initialize the end-to-end pipeline service.

        Args:
            configuration: Pipeline configuration
        """
        self.configuration = configuration or PipelineConfiguration()
        self.metrics = PipelineMetrics()

        # Initialize services
        self._initialize_services()

        logger.info("End-to-end pipeline service initialized")

    def _initialize_services(self) -> None:
        """Initialize all pipeline services."""
        try:
            # Lazy import to avoid import errors if langchain dependencies are not installed
            from ..infrastructure.langchain import (
                LangChainChunkingService,
                LangChainEmbeddingService,
                LangChainLLMService,
                LangChainVectorStore,
            )

            # Initialize chunking service
            self.chunking_service = LangChainChunkingService(
                self.configuration.chunking_config
            )

            # Initialize embedding service
            self.embedding_service = LangChainEmbeddingService()

            # Initialize vector store
            self.vector_store = LangChainVectorStore(
                **self.configuration.vector_store_config
            )

            # Initialize LLM service
            self.llm_service = LangChainLLMService(**self.configuration.llm_config)

            # Initialize RAG pipeline orchestrator
            self.rag_orchestrator = RAGPipelineOrchestrator(
                chunking_service=self.chunking_service,
                embedding_service=self.embedding_service,
                vector_store=self.vector_store,
                llm_service=self.llm_service,
            )

            # Initialize RAG service
            self.rag_service = LangChainRAGService(
                pipeline_orchestrator=self.rag_orchestrator,
                llm=self.llm_service.get_llm(**self.configuration.llm_config),
                **self.configuration.llm_config,
            )

            # Initialize clinical extraction service
            self.clinical_service = ClinicalExtractionService(
                llm=self.llm_service.get_llm(**self.configuration.llm_config),
                **self.configuration.clinical_config,
            )

            logger.info("All pipeline services initialized successfully")

        except Exception as e:
            logger.error(f"Service initialization failed: {e}")
            raise RuntimeError(f"Service initialization failed: {e}") from e

    async def process_document(
        self,
        content: str,
        filename: str = "",
        document_id: Optional[str] = None,
        extract_clinical_data: bool = False,
    ) -> dict[str, Any]:
        """Process a document through the complete pipeline.

        Args:
            content: Document content to process
            filename: Filename for metadata extraction
            document_id: Document ID
            extract_clinical_data: Whether to extract clinical data

        Returns:
            Processing results dictionary

        Raises:
            RuntimeError: If processing fails
        """
        try:
            self.metrics.start_pipeline()
            logger.info(f"Starting document processing: {filename}")

            # Process document through RAG pipeline
            chunks_with_embeddings = await self.rag_orchestrator.process_document(
                content=content,
                filename=filename,
                document_id=document_id,
                chunking_config=self.configuration.chunking_config,
                embedding_config=self.configuration.embedding_config,
            )

            # Record metrics
            self.metrics.record_document_processing(len(chunks_with_embeddings))
            self.metrics.record_embedding_generation(len(chunks_with_embeddings))

            # Extract clinical data if requested
            clinical_data = None
            if extract_clinical_data:
                clinical_data = await self.clinical_service.extract_clinical_data(
                    chunks_with_embeddings
                )
                self.metrics.record_clinical_extraction(len(clinical_data))

            self.metrics.end_pipeline()

            # Prepare results
            results = {
                "document_id": document_id,
                "filename": filename,
                "chunks_created": len(chunks_with_embeddings),
                "clinical_data_extracted": clinical_data is not None,
                "clinical_trials_found": len(clinical_data) if clinical_data else 0,
                "processing_metrics": self.metrics.get_summary(),
            }

            if clinical_data:
                results["clinical_data"] = clinical_data

            logger.info(f"Document processing completed: {filename}")
            return results

        except Exception as e:
            self.metrics.record_error(str(e))
            logger.error(f"Document processing failed: {e}")
            raise RuntimeError(f"Document processing failed: {e}") from e

    async def process_query(
        self,
        query: RAGQuery,
        extract_clinical_data: bool = False,
    ) -> dict[str, Any]:
        """Process a RAG query.

        Args:
            query: RAG query to process
            extract_clinical_data: Whether to extract clinical data from results

        Returns:
            Query processing results dictionary

        Raises:
            RuntimeError: If query processing fails
        """
        try:
            self.metrics.start_pipeline()
            logger.info(f"Processing RAG query: {query.question[:100]}...")

            # Process query through RAG service
            rag_response = await self.rag_service.process_query(query)

            # Record metrics
            self.metrics.record_query_processing()

            # Extract clinical data from context if requested
            clinical_data = None
            if extract_clinical_data and rag_response.context_chunks:
                # Convert SearchResult chunks to ChunkWithEmbedding
                chunks = [result.chunk for result in rag_response.context_chunks]
                clinical_data = await self.clinical_service.extract_clinical_data(
                    chunks
                )
                self.metrics.record_clinical_extraction(len(clinical_data))

            self.metrics.end_pipeline()

            # Prepare results
            results = {
                "question": query.question,
                "answer": rag_response.answer,
                "confidence_score": rag_response.confidence_score,
                "sources_count": len(rag_response.sources),
                "clinical_data_extracted": clinical_data is not None,
                "clinical_trials_found": len(clinical_data) if clinical_data else 0,
                "processing_metrics": self.metrics.get_summary(),
            }

            if clinical_data:
                results["clinical_data"] = clinical_data

            logger.info(
                f"Query processing completed with confidence: {rag_response.confidence_score:.2f}"
            )
            return results

        except Exception as e:
            self.metrics.record_error(str(e))
            logger.error(f"Query processing failed: {e}")
            raise RuntimeError(f"Query processing failed: {e}") from e

    async def search_similar_chunks(
        self,
        query_text: str,
        top_k: int = 10,
        similarity_threshold: float = 0.0,
        **filters,
    ) -> list[SearchResult]:
        """Search for similar chunks.

        Args:
            query_text: Query text to search for
            top_k: Number of results to return
            similarity_threshold: Minimum similarity threshold
            **filters: Additional search filters

        Returns:
            List of search results
        """
        try:
            return await self.rag_orchestrator.search_similar_chunks(
                query_text=query_text,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                embedding_config=self.configuration.embedding_config,
                **filters,
            )
        except Exception as e:
            self.metrics.record_error(str(e))
            logger.error(f"Similarity search failed: {e}")
            raise RuntimeError(f"Similarity search failed: {e}") from e

    def get_pipeline_statistics(self) -> dict[str, Any]:
        """Get comprehensive pipeline statistics.

        Returns:
            Dictionary containing pipeline statistics
        """
        return {
            "configuration": self.configuration.to_dict(),
            "metrics": self.metrics.get_summary(),
            "services": {
                "chunking": self.chunking_service.get_chunking_statistics([]),
                "embedding": self.embedding_service.get_service_statistics(),
                "vector_store": self.vector_store.get_vectorstore_statistics(),
                "llm": self.llm_service.get_service_statistics(),
                "rag": self.rag_service.get_service_statistics(),
                "clinical": self.clinical_service.get_service_statistics(),
            },
        }

    def reset_metrics(self) -> None:
        """Reset pipeline metrics."""
        self.metrics = PipelineMetrics()
        logger.info("Pipeline metrics reset")

    def update_configuration(self, new_config: PipelineConfiguration) -> None:
        """Update pipeline configuration.

        Args:
            new_config: New configuration
        """
        self.configuration = new_config
        self._initialize_services()
        logger.info("Pipeline configuration updated and services reinitialized")
