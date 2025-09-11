"""API endpoints for embedding and vector store operations."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..domain.constants import EmbeddingDefaults, VectorStoreDefaults
from ..domain.models import (
    EmbeddingConfiguration,
    EmbeddingModel,
    SearchQuery,
    SearchResult,
)
from ..infrastructure.embedding_service import BioClinicalEmbeddingService
from ..infrastructure.vector_store import ChromaVectorStore

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/embedding", tags=["embedding"])


# Request/Response models
class EmbeddingRequest(BaseModel):
    """Request model for embedding generation."""

    text: str
    model: Optional[str] = EmbeddingDefaults.DEFAULT_MODEL.value
    normalize: bool = EmbeddingDefaults.DEFAULT_NORMALIZE_EMBEDDINGS


class EmbeddingResponse(BaseModel):
    """Response model for embedding generation."""

    embedding: list[float]
    model: str
    dimension: int
    normalized: bool


class SearchRequest(BaseModel):
    """Request model for similarity search."""

    query: str
    top_k: int = 10
    similarity_threshold: float = 0.0
    chunk_types: Optional[list[str]] = None
    metadata_filters: Optional[dict] = None


class SearchResponse(BaseModel):
    """Response model for similarity search."""

    results: list[SearchResult]
    total_found: int
    query: str


# Dependency injection
def get_embedding_service() -> BioClinicalEmbeddingService:
    """Get embedding service instance."""
    return BioClinicalEmbeddingService()


def get_vector_store() -> ChromaVectorStore:
    """Get vector store instance."""
    return ChromaVectorStore(
        persist_directory=VectorStoreDefaults.DEFAULT_PERSIST_DIRECTORY
    )


# API Endpoints
@router.post("/generate", response_model=EmbeddingResponse)
async def generate_embedding(
    request: EmbeddingRequest,
    embedding_service: BioClinicalEmbeddingService = Depends(get_embedding_service),
):
    """Generate embedding for a single text.

    Args:
        request: Embedding request with text and options
        embedding_service: Injected embedding service

    Returns:
        Embedding response with vector and metadata

    Raises:
        HTTPException: If embedding generation fails
    """
    try:
        # Validate model
        if request.model not in [model.value for model in EmbeddingModel]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid model: {request.model}. Available models: {[model.value for model in EmbeddingModel]}",
            )

        # Create configuration
        config = EmbeddingConfiguration(
            model_name=EmbeddingModel(request.model),
            normalize_embeddings=request.normalize,
        )

        # Generate embedding
        embedding = await embedding_service.generate_embedding(request.text, config)
        dimension = await embedding_service.get_embedding_dimension(config)

        return EmbeddingResponse(
            embedding=embedding,
            model=request.model,
            dimension=dimension,
            normalized=request.normalize,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        raise HTTPException(
            status_code=500, detail="Embedding generation failed"
        ) from e


@router.post("/search", response_model=SearchResponse)
async def search_similar(
    request: SearchRequest,
    embedding_service: BioClinicalEmbeddingService = Depends(get_embedding_service),
    vector_store: ChromaVectorStore = Depends(get_vector_store),
):
    """Search for similar chunks using semantic similarity.

    Args:
        request: Search request with query and filters
        embedding_service: Injected embedding service
        vector_store: Injected vector store

    Returns:
        Search response with similar chunks

    Raises:
        HTTPException: If search fails
    """
    try:
        # Generate query embedding
        config = EmbeddingConfiguration(model_name=EmbeddingDefaults.DEFAULT_MODEL)
        query_embedding = await embedding_service.generate_embedding(
            request.query, config
        )

        # Create search query
        chunk_types = None
        if request.chunk_types:
            from src.domain.models import ChunkType

            chunk_types = [ChunkType(ct) for ct in request.chunk_types]

        search_query = SearchQuery(
            text=request.query,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold,
            chunk_types=chunk_types,
            metadata_filters=request.metadata_filters or {},
            embedding=query_embedding,
        )

        # Perform search
        results = await vector_store.search_similar(search_query)

        return SearchResponse(
            results=results, total_found=len(results), query=request.query
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Similarity search failed: {e}")
        raise HTTPException(status_code=500, detail="Similarity search failed") from e


@router.get("/models")
async def list_available_models():
    """List available embedding models.

    Returns:
        List of available models with descriptions
    """
    models = [
        {
            "name": model.value,
            "description": f"Bio-clinical embedding model: {model.value}",
            "type": "sentence-transformers",
        }
        for model in EmbeddingModel
    ]

    return {"models": models, "default": EmbeddingDefaults.DEFAULT_MODEL.value}


@router.get("/models/{model_name}/validate")
async def validate_model(
    model_name: str,
    embedding_service: BioClinicalEmbeddingService = Depends(get_embedding_service),
):
    """Validate that a model is available and working.

    Args:
        model_name: Name of the model to validate
        embedding_service: Injected embedding service

    Returns:
        Validation result

    Raises:
        HTTPException: If model name is invalid
    """
    if model_name not in [model.value for model in EmbeddingModel]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model: {model_name}. Available models: {[model.value for model in EmbeddingModel]}",
        )

    try:
        is_valid = await embedding_service.validate_model(model_name)

        return {
            "model": model_name,
            "valid": is_valid,
            "message": "Model is available and working"
            if is_valid
            else "Model validation failed",
        }

    except Exception as e:
        logger.error(f"Model validation failed for {model_name}: {e}")
        return {
            "model": model_name,
            "valid": False,
            "message": f"Validation error: {str(e)}",
        }


@router.get("/store/info")
async def get_vector_store_info(
    vector_store: ChromaVectorStore = Depends(get_vector_store),
):
    """Get information about the vector store.

    Args:
        vector_store: Injected vector store

    Returns:
        Vector store information

    Raises:
        HTTPException: If info retrieval fails
    """
    try:
        info = await vector_store.get_store_info()
        return info

    except Exception as e:
        logger.error(f"Failed to get store info: {e}")
        raise HTTPException(status_code=500, detail="Failed to get store info") from e


@router.delete("/store/clear")
async def clear_vector_store(
    vector_store: ChromaVectorStore = Depends(get_vector_store),
):
    """Clear all data from the vector store.

    Args:
        vector_store: Injected vector store

    Returns:
        Success message

    Raises:
        HTTPException: If clear operation fails
    """
    try:
        await vector_store.clear_store()
        return {"message": "Vector store cleared successfully"}

    except Exception as e:
        logger.error(f"Failed to clear store: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear store") from e


@router.get("/health")
async def health_check():
    """Health check endpoint for embedding services.

    Returns:
        Health status
    """
    return {"status": "healthy", "service": "embedding", "version": "1.0.0"}
