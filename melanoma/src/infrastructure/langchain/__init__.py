"""LangChain infrastructure layer for clinical RAG system.

This module provides LangChain-based implementations of the core services
for the clinical RAG system, maintaining clean architecture principles
while leveraging LangChain's powerful framework capabilities.
"""


# Lazy imports to avoid import errors when processing dependencies are not installed
# This allows the module to be imported even if langchain dependencies are missing
def __getattr__(name: str):
    """Lazy import for LangChain services."""
    # Check if langchain is available before attempting imports
    try:
        import langchain  # noqa: F401
    except ImportError as e:
        raise ImportError(
            f"{name} requires langchain dependencies. "
            "Install with: poetry install --with processing"
        ) from e

    try:
        if name == "LangChainChunkingService":
            from .chunking import LangChainChunkingService

            return LangChainChunkingService
        elif name == "LangChainEmbeddingService":
            from .embeddings import LangChainEmbeddingService

            return LangChainEmbeddingService
        elif name == "LangChainVectorStore":
            from .vector_store import LangChainVectorStore

            return LangChainVectorStore
        elif name == "LangChainLLMService":
            from .llm import LangChainLLMService

            return LangChainLLMService
        elif name == "LangChainClinicalService":
            from .clinical import LangChainClinicalService

            return LangChainClinicalService
        elif name == "ClinicalTrialData":
            from .clinical import ClinicalTrialData

            return ClinicalTrialData
    except ImportError as e:
        raise ImportError(
            f"{name} requires langchain dependencies. "
            "Install with: poetry install --with processing"
        ) from e
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "LangChainChunkingService",
    "LangChainEmbeddingService",
    "LangChainVectorStore",
    "LangChainLLMService",
    "LangChainClinicalService",
    "ClinicalTrialData",
]
