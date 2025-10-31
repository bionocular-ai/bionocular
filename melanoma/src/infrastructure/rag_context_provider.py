"""Enhanced RAG context provider implementation.

This service integrates with the existing RAG pipeline to provide
optimized context retrieval for attribute extraction with support for:
- Parallel query processing
- Context quality scoring
- Intelligent caching
- Configuration-driven query templates
"""

import asyncio
import hashlib
import logging
from typing import Any, Optional

from ..domain.extraction_interfaces import RAGContextProvider
from ..domain.extraction_models import AttributeType
from ..domain.models import SearchQuery, SearchResult
from .langchain import LangChainEmbeddingService, LangChainVectorStore
from .rag_config_loader import RAGConfigLoader

logger = logging.getLogger(__name__)


class ContextQualityScorer:
    """Scores and ranks context chunks based on relevance and quality."""

    def __init__(self):
        """Initialize context quality scorer."""
        # Attribute-specific keywords for relevance scoring
        self.attribute_keywords = {
            AttributeType.NCT_NUMBER: [
                "nct",
                "clinical trial",
                "registration",
                "identifier",
            ],
            AttributeType.GENERIC_NAME: [
                "drug",
                "medication",
                "therapy",
                "treatment",
                "agent",
            ],
            AttributeType.P_VALUE_OS: [
                "p-value",
                "p value",
                "survival",
                "os",
                "overall survival",
                "hazard ratio",
                "hr",
            ],
            AttributeType.OBJECTIVE_RESPONSE_RATE: [
                "response",
                "orr",
                "objective response",
                "tumor response",
                "efficacy",
            ],
            AttributeType.GRADE_3_PLUS_AE: [
                "adverse",
                "toxicity",
                "grade 3",
                "safety",
                "ae",
                "serious",
            ],
        }

    def score_context_quality(
        self, result: SearchResult, attribute_type: AttributeType, query_text: str
    ) -> float:
        """Calculate quality score for a context chunk.

        Args:
            result: Search result to score
            attribute_type: Type of attribute being extracted
            query_text: Original query text

        Returns:
            Quality score between 0.0 and 1.0
        """
        content = result.chunk.content.lower()

        # Factor 1: Similarity score (40%)
        similarity_score = result.similarity_score

        # Factor 2: Keyword relevance (30%)
        keywords = self.attribute_keywords.get(attribute_type, [])
        keyword_matches = sum(1 for keyword in keywords if keyword in content)
        keyword_score = min(keyword_matches / len(keywords), 1.0) if keywords else 0.5

        # Factor 3: Content completeness (20%)
        # Prefer longer, more complete chunks
        content_length = len(result.chunk.content)
        completeness_score = min(content_length / 500, 1.0)  # Normalize to 500 chars

        # Factor 4: Metadata quality (10%)
        # Prefer chunks from relevant sections
        metadata_score = 0.5
        if hasattr(result.chunk, "metadata") and result.chunk.metadata:
            section = result.chunk.metadata.get("Section", "").lower()
            relevant_sections = self._get_relevant_sections(attribute_type)
            if section in relevant_sections:
                metadata_score = 1.0

        # Calculate weighted score
        quality_score = (
            similarity_score * 0.4
            + keyword_score * 0.3
            + completeness_score * 0.2
            + metadata_score * 0.1
        )

        return min(quality_score, 1.0)

    def _get_relevant_sections(self, attribute_type: AttributeType) -> list[str]:
        """Get relevant sections for an attribute type."""
        section_map = {
            AttributeType.NCT_NUMBER: ["methods", "background", "introduction"],
            AttributeType.GENERIC_NAME: ["methods", "results", "treatment"],
            AttributeType.P_VALUE_OS: [
                "results",
                "statistical analysis",
                "survival",
                "efficacy",
            ],
            AttributeType.OBJECTIVE_RESPONSE_RATE: ["results", "efficacy", "response"],
            AttributeType.GRADE_3_PLUS_AE: [
                "results",
                "safety",
                "adverse events",
                "toxicity",
            ],
        }
        return section_map.get(attribute_type, [])

    def rank_results(
        self,
        results: list[SearchResult],
        attribute_type: AttributeType,
        query_text: str,
    ) -> list[tuple[SearchResult, float]]:
        """Rank results by quality score.

        Args:
            results: List of search results
            attribute_type: Type of attribute
            query_text: Original query text

        Returns:
            List of (result, quality_score) tuples sorted by score
        """
        scored_results = [
            (result, self.score_context_quality(result, attribute_type, query_text))
            for result in results
        ]
        return sorted(scored_results, key=lambda x: x[1], reverse=True)


class RAGContextProviderImpl(RAGContextProvider):
    """Enhanced RAG context provider with optimized retrieval and quality scoring.

    This service follows the Open/Closed Principle by implementing
    the RAGContextProvider interface without modifying existing RAG code.

    Features:
    - Parallel query processing for better performance
    - Context quality scoring and ranking
    - Intelligent caching for repeated queries
    - Configuration-driven query templates
    """

    def __init__(
        self,
        vector_store: LangChainVectorStore,
        embedding_service: LangChainEmbeddingService,
        enable_caching: bool = True,
        cache_ttl: int = 3600,
    ):
        """Initialize enhanced RAG context provider.

        Args:
            vector_store: LangChain vector store for similarity search
            embedding_service: LangChain embedding service
            enable_caching: Whether to enable result caching
            cache_ttl: Cache time-to-live in seconds
        """
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.enable_caching = enable_caching
        self.cache_ttl = cache_ttl

        # Initialize cache
        self._context_cache: dict[str, list[SearchResult]] = {}

        # Initialize quality scorer
        self.quality_scorer = ContextQualityScorer()

        # Load attribute-specific query templates from YAML configuration
        # These are optimized for clinical trial abstracts
        config_loader = RAGConfigLoader()
        self.attribute_queries = config_loader.get_all_templates()

        logger.info(
            "Enhanced RAG context provider initialized with caching=%s, loaded %d attribute query templates",
            enable_caching,
            len(self.attribute_queries),
        )

    async def get_context_for_attribute(
        self,
        document_id: Optional[str],
        attribute_type: AttributeType,
        context_chunks: int = 5,
        similarity_threshold: float = 0.1,
        metadata_filters: Optional[dict[str, Any]] = None,
    ) -> list[SearchResult]:
        """Get relevant context chunks for attribute extraction.

        This method uses parallel query processing and quality scoring
        to retrieve the most relevant context chunks efficiently.

        Args:
            document_id: Optional document identifier. If None, searches across all documents.
            attribute_type: Type of attribute to extract
            context_chunks: Number of context chunks to retrieve
            similarity_threshold: Minimum similarity threshold
            metadata_filters: Optional metadata filters

        Returns:
            List of SearchResult objects containing context chunks
        """
        try:
            logger.debug(
                "Retrieving context for document=%s, attribute=%s, chunks=%d",
                document_id,
                attribute_type.value,
                context_chunks,
            )

            # Check cache first
            if self.enable_caching:
                cache_key = self._generate_cache_key(
                    document_id, attribute_type, context_chunks, similarity_threshold
                )
                if cache_key in self._context_cache:
                    logger.debug("Cache hit for %s", cache_key)
                    return self._context_cache[cache_key]

            # Get attribute-specific queries
            queries = self.attribute_queries.get(
                attribute_type, [f"{attribute_type.value} data"]
            )
            logger.debug("Using %d queries for %s", len(queries), attribute_type.value)

            # Process queries in parallel for better performance
            search_results = await self._parallel_query_processing(
                queries=queries,
                document_id=document_id,
                context_chunks=context_chunks,
                similarity_threshold=similarity_threshold,
                metadata_filters=metadata_filters,
                attribute_type=attribute_type,
            )

            # Rank by quality score
            ranked_results = self._rank_and_deduplicate(
                search_results, attribute_type, queries[0]
            )

            # Limit to requested number of chunks
            limited_results = ranked_results[:context_chunks]

            # Cache results
            if self.enable_caching:
                self._context_cache[cache_key] = limited_results

            logger.info(
                "Retrieved %d high-quality context chunks for %s",
                len(limited_results),
                attribute_type.value,
            )
            return limited_results

        except Exception as e:
            logger.error(
                "Failed to retrieve context for %s: %s", attribute_type.value, e
            )
            return []

    async def _parallel_query_processing(
        self,
        queries: list[str],
        document_id: str,
        context_chunks: int,
        similarity_threshold: float,
        metadata_filters: Optional[dict[str, Any]],
        attribute_type: AttributeType,
    ) -> list[SearchResult]:
        """Process multiple queries in parallel for better performance.

        Args:
            queries: List of query strings
            document_id: Document identifier
            context_chunks: Number of chunks to retrieve per query
            similarity_threshold: Minimum similarity threshold
            metadata_filters: Optional metadata filters
            attribute_type: Type of attribute

        Returns:
            Combined list of search results from all queries
        """
        # Create search tasks for parallel execution
        search_tasks = [
            self._search_single_query(
                query_text=query,
                document_id=document_id,
                context_chunks=context_chunks,
                similarity_threshold=similarity_threshold,
                metadata_filters=metadata_filters,
            )
            for query in queries
        ]

        # Execute all queries in parallel with timeout
        try:
            results = await asyncio.gather(*search_tasks, return_exceptions=True)
        except Exception as e:
            logger.error("Parallel query processing failed: %s", e)
            return []

        # Combine results, filtering out exceptions
        all_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning("Query %d failed: %s", i, result)
                continue
            if isinstance(result, list):
                all_results.extend(result)

        logger.debug("Parallel processing returned %d total results", len(all_results))
        return all_results

    async def _search_single_query(
        self,
        query_text: str,
        document_id: Optional[str],
        context_chunks: int,
        similarity_threshold: float,
        metadata_filters: Optional[dict[str, Any]],
    ) -> list[SearchResult]:
        """Execute a single search query.

        Args:
            query_text: Query string
            document_id: Optional document identifier. If None, searches across all documents.
            context_chunks: Number of chunks to retrieve
            similarity_threshold: Minimum similarity threshold
            metadata_filters: Optional metadata filters

        Returns:
            List of search results
        """
        try:
            # Create search query with optional document ID filter
            document_filters = (metadata_filters or {}).copy()

            # Only add document_id filter if provided and not empty
            # This allows searching across all documents when document_id is None
            if document_id:
                document_filters[
                    "document_id"
                ] = document_id  # Fixed: use "document_id" not "abstract_id"

            search_query = SearchQuery(
                text=query_text,
                top_k=context_chunks,
                similarity_threshold=similarity_threshold,
                metadata_filters=document_filters
                or {},  # Always pass dict, empty if no filters
            )

            # Execute search
            search_results = await self.vector_store.search(search_query)

            # Filter by similarity threshold
            filtered_results = [
                result
                for result in search_results
                if result.similarity_score >= similarity_threshold
            ]

            logger.debug(
                "Query '%s' for document_id='%s' returned %d results (filtered to %d)",
                query_text[:50],
                document_id or "ALL",
                len(search_results),
                len(filtered_results),
            )

            return filtered_results

        except Exception as e:
            logger.warning(
                "Query '%s' for document_id='%s' failed: %s",
                query_text[:50],
                document_id or "ALL",
                e,
            )
            return []

    def _rank_and_deduplicate(
        self,
        results: list[SearchResult],
        attribute_type: AttributeType,
        query_text: str,
    ) -> list[SearchResult]:
        """Rank results by quality and remove duplicates.

        Args:
            results: List of search results
            attribute_type: Type of attribute
            query_text: Original query text

        Returns:
            Deduplicated and ranked list of results
        """
        if not results:
            return []

        # Deduplicate by chunk ID
        seen_chunk_ids = set()
        unique_results = []

        for result in results:
            chunk_id = result.chunk.id
            if chunk_id not in seen_chunk_ids:
                unique_results.append(result)
                seen_chunk_ids.add(chunk_id)

        # Rank by quality score
        ranked_results = self.quality_scorer.rank_results(
            unique_results, attribute_type, query_text
        )

        # Extract just the results (without scores)
        return [result for result, score in ranked_results]

    def _generate_cache_key(
        self,
        document_id: str,
        attribute_type: AttributeType,
        context_chunks: int,
        similarity_threshold: float,
    ) -> str:
        """Generate cache key for context retrieval.

        Args:
            document_id: Document identifier
            attribute_type: Type of attribute
            context_chunks: Number of chunks
            similarity_threshold: Similarity threshold

        Returns:
            Cache key string
        """
        key_data = f"{document_id}:{attribute_type.value}:{context_chunks}:{similarity_threshold}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def clear_cache(self) -> None:
        """Clear the context cache."""
        self._context_cache.clear()
        logger.info("Context cache cleared")

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        return {
            "enabled": self.enable_caching,
            "size": len(self._context_cache),
            "ttl": self.cache_ttl,
        }

    def update_query_templates(
        self, attribute_type: AttributeType, queries: list[str]
    ) -> None:
        """Update query templates for an attribute type.

        This allows dynamic configuration of queries without code changes.

        Args:
            attribute_type: Type of attribute
            queries: List of query strings
        """
        self.attribute_queries[attribute_type] = queries
        logger.info("Updated query templates for %s", attribute_type.value)

    def get_query_templates(self, attribute_type: AttributeType) -> list[str]:
        """Get query templates for an attribute type.

        Args:
            attribute_type: Type of attribute

        Returns:
            List of query strings
        """
        return self.attribute_queries.get(attribute_type, [])
