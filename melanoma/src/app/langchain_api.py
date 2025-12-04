"""LangChain-powered API endpoints for the melanoma RAG system.

This module provides FastAPI endpoints that use LangChain services for
retrieval-augmented generation with clinical intelligence.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..domain.models import (
    RAGQuery,
)
from .clinical_extraction_service import ClinicalExtractionService
from .complete_rag_service import CompleteRAGService
from .langchain_factory_service import LangChainServiceFactory, ServiceConfiguration
from .pipeline_service import EndToEndPipelineService
from .rag_orchestration_service import LangChainRAGService

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/langchain", tags=["langchain-rag"])


# Request/Response models
class RAGQueryRequest(BaseModel):
    """Request model for RAG queries."""

    question: str
    context_chunks: int = 5
    similarity_threshold: float = 0.7
    metadata_filters: Optional[dict] = None


class RAGQueryResponse(BaseModel):
    """Response model for RAG queries."""

    answer: str
    confidence_score: float
    sources: list[dict]
    context_chunks_count: int
    processing_time_ms: Optional[int] = None


class ClinicalQueryRequest(BaseModel):
    """Request model for clinical queries."""

    question: str
    context_chunks: int = 5
    similarity_threshold: float = 0.7
    extract_clinical_data: bool = True
    metadata_filters: Optional[dict] = None


class ClinicalQueryResponse(BaseModel):
    """Response model for clinical queries."""

    answer: str
    confidence_score: float
    clinical_data: Optional[dict] = None
    sources: list[dict]
    context_chunks_count: int
    processing_time_ms: Optional[int] = None


# Service factory instance
_service_factory: Optional[LangChainServiceFactory] = None


def get_service_factory() -> LangChainServiceFactory:
    """Get service factory instance."""
    global _service_factory
    if _service_factory is None:
        # Configure service factory with default settings
        config = ServiceConfiguration(
            chunking_strategy="header_based",
            embedding_model="pritamdeka/S-BioBERT-snli-multinli-stsb",
            llm_provider="openai",
            llm_model="gpt-3.5-turbo",
            temperature=0.1,
            persist_directory="./langchain_chroma_db",
            collection_name="melanoma_chunks",
        )
        _service_factory = LangChainServiceFactory(config)
    return _service_factory


def get_rag_service() -> LangChainRAGService:
    """Get RAG service instance."""
    try:
        factory = get_service_factory()
        return factory.create_rag_service()
    except Exception as e:
        logger.error(f"Failed to create RAG service: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to initialize RAG service: {e}"
        ) from e


def get_clinical_service() -> ClinicalExtractionService:
    """Get clinical extraction service instance."""
    try:
        factory = get_service_factory()
        return factory.create_clinical_service()
    except Exception as e:
        logger.error(f"Failed to create clinical service: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to initialize clinical service: {e}"
        ) from e


def get_pipeline_service() -> EndToEndPipelineService:
    """Get end-to-end pipeline service instance."""
    try:
        factory = get_service_factory()
        return factory.create_pipeline_service()
    except Exception as e:
        logger.error(f"Failed to create pipeline service: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to initialize pipeline service: {e}"
        ) from e


# API Endpoints
@router.post("/query", response_model=RAGQueryResponse)
async def query_rag(
    request: RAGQueryRequest,
    rag_service: LangChainRAGService = Depends(get_rag_service),
) -> RAGQueryResponse:
    """Query the RAG system for general melanoma research questions.

    Args:
        request: RAG query request
        rag_service: Injected RAG service

    Returns:
        RAG response with answer and sources

    Raises:
        HTTPException: If query processing fails
    """
    try:
        # Create RAG query
        rag_query = RAGQuery(
            question=request.question,
            context_chunks=request.context_chunks,
            similarity_threshold=request.similarity_threshold,
            metadata_filters=request.metadata_filters or {},
        )

        # Process query
        response = await rag_service.process_query(rag_query)

        # Format response
        return RAGQueryResponse(
            answer=response.answer,
            confidence_score=response.confidence_score,
            sources=response.sources,
            context_chunks_count=len(response.context_chunks),
            processing_time_ms=response.processing_time_ms,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"RAG query failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"RAG query processing failed: {e}"
        ) from e


@router.post("/clinical", response_model=ClinicalQueryResponse)
async def query_clinical(
    request: ClinicalQueryRequest,
    rag_service: LangChainRAGService = Depends(get_rag_service),
    clinical_service: ClinicalExtractionService = Depends(get_clinical_service),
) -> ClinicalQueryResponse:
    """Query the RAG system for clinical trial data and analysis.

    Args:
        request: Clinical query request
        rag_service: Injected clinical RAG service

    Returns:
        Clinical response with structured data

    Raises:
        HTTPException: If query processing fails
    """
    try:
        # Create RAG query
        rag_query = RAGQuery(
            question=request.question,
            context_chunks=request.context_chunks,
            similarity_threshold=request.similarity_threshold,
            metadata_filters=request.metadata_filters or {},
        )

        # Process RAG query
        response = await rag_service.process_query(rag_query)

        # Extract clinical data if requested
        clinical_data = None
        if request.extract_clinical_data and response.context_chunks:
            try:
                # Convert SearchResult chunks to ChunkWithEmbedding
                chunks = [result.chunk for result in response.context_chunks]
                clinical_data_list = await clinical_service.extract_clinical_data(
                    chunks
                )
                if clinical_data_list:
                    clinical_data = clinical_data_list[0].model_dump()
            except Exception as e:
                logger.warning(f"Clinical data extraction failed: {e}")
                clinical_data = {"error": str(e)}

        # Format response
        return ClinicalQueryResponse(
            answer=response.answer,
            confidence_score=response.confidence_score,
            clinical_data=clinical_data,
            sources=response.sources,
            context_chunks_count=len(response.context_chunks),
            processing_time_ms=response.processing_time_ms,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Clinical query failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Clinical query processing failed: {e}"
        ) from e


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint for LangChain services.

    Returns:
        Health status
    """
    try:
        # Test service creation
        get_rag_service()

        return {
            "status": "healthy",
            "service": "langchain-rag",
            "components": {
                "vector_store": "ChromaDB",
                "embedding_model": "S-BioBERT",
                "llm_model": "GPT-3.5-turbo",
            },
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


@router.get("/info")
async def get_service_info(
    rag_service: CompleteRAGService = Depends(get_rag_service),
) -> dict:
    """Get information about the RAG service.

    Args:
        rag_service: Injected RAG service

    Returns:
        Service information
    """
    try:
        # Get vector store info
        store_info = await rag_service.vector_store.get_store_info()

        return {
            "service": "langchain-clinical-rag",
            "vector_store": store_info,
            "capabilities": [
                "semantic_search",
                "clinical_data_extraction",
                "treatment_comparison",
                "trial_analysis",
            ],
            "supported_queries": [
                "NCT number lookup",
                "Trial name search",
                "Treatment efficacy queries",
                "Safety profile analysis",
                "Biomarker analysis",
            ],
        }
    except Exception as e:
        logger.error(f"Failed to get service info: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get service info: {e}"
        ) from e
