"""RAG context provider implementation.

This service integrates with the existing RAG pipeline to provide
context for attribute extraction.
"""

import logging
from typing import Any, Optional

from ..domain.extraction_interfaces import RAGContextProvider
from ..domain.extraction_models import AttributeType
from ..domain.models import SearchQuery, SearchResult
from .langchain import LangChainEmbeddingService, LangChainVectorStore

logger = logging.getLogger(__name__)


class RAGContextProviderImpl(RAGContextProvider):
    """Implementation of RAG context provider using existing RAG pipeline.

    This service follows the Open/Closed Principle by implementing
    the RAGContextProvider interface without modifying existing RAG code.
    """

    def __init__(
        self,
        vector_store: LangChainVectorStore,
        embedding_service: LangChainEmbeddingService,
    ):
        """Initialize RAG context provider.

        Args:
            vector_store: LangChain vector store for similarity search
            embedding_service: LangChain embedding service
        """
        self.vector_store = vector_store
        self.embedding_service = embedding_service

        # Enhanced attribute-specific query templates for better context retrieval
        self.attribute_queries = {
            AttributeType.NCT_NUMBER: [
                "NCT number clinical trial identifier",
                "ClinicalTrials.gov registration number",
                "trial registration NCT",
                "clinical trial number",
                "study registration",
            ],
            AttributeType.GENERIC_NAME: [
                "generic drug name treatment",
                "medication name therapy",
                "drug name treatment arm",
                "study drug medication",
                "therapeutic agent drug",
            ],
            AttributeType.P_VALUE_OS: [
                "overall survival p-value significance",
                "OS p-value statistical significance",
                "survival analysis p-value",
                "p value overall survival",
                "statistical significance survival",
                "hazard ratio survival",
                "median overall survival",
            ],
            AttributeType.OBJECTIVE_RESPONSE_RATE: [
                "objective response rate ORR",
                "response rate efficacy",
                "tumor response rate",
                "response rate percentage",
                "overall response rate",
                "best overall response",
                "response evaluation",
            ],
            AttributeType.GRADE_3_PLUS_AE: [
                "grade 3 adverse events toxicity",
                "grade 3+ adverse events",
                "severe adverse events grade 3",
                "grade 3 higher adverse events",
                "treatment related adverse events",
                "serious adverse events",
                "toxicity grade 3",
            ],
        }

        logger.info("RAG context provider initialized")

    async def get_context_for_attribute(
        self,
        document_id: str,
        attribute_type: AttributeType,
        context_chunks: int = 5,
        similarity_threshold: float = 0.1,
        metadata_filters: Optional[dict[str, Any]] = None,
    ) -> list[SearchResult]:
        """Get relevant context chunks for attribute extraction.

        Args:
            document_id: Document identifier
            attribute_type: Type of attribute to extract
            context_chunks: Number of context chunks to retrieve
            similarity_threshold: Minimum similarity threshold
            metadata_filters: Optional metadata filters

        Returns:
            List of SearchResult objects containing context chunks
        """
        try:
            logger.info("🔍 DEBUG: RAG Context Provider - Starting context retrieval")
            logger.info(f"🔍 DEBUG: Document ID: {document_id}")
            logger.info(f"🔍 DEBUG: Attribute Type: {attribute_type}")
            logger.info(f"🔍 DEBUG: Context chunks requested: {context_chunks}")
            logger.info(f"🔍 DEBUG: Similarity threshold: {similarity_threshold}")
            logger.info(f"🔍 DEBUG: Metadata filters: {metadata_filters}")

            # Get attribute-specific queries
            queries = self.attribute_queries.get(
                attribute_type, [f"{attribute_type.value} data"]
            )
            logger.info(f"🔍 DEBUG: Attribute queries: {queries}")

            all_search_results = []
            seen_chunk_ids = set()  # Track seen chunk IDs for efficient deduplication

            # Search for each query to get diverse context
            for i, query_text in enumerate(queries):
                try:
                    logger.info(
                        f"🔍 DEBUG: Processing query {i+1}/{len(queries)}: '{query_text}'"
                    )

                    # Create search query with abstract ID filter
                    document_filters = (metadata_filters or {}).copy()
                    document_filters["abstract_id"] = document_id

                    search_query = SearchQuery(
                        text=query_text,
                        top_k=context_chunks,
                        similarity_threshold=similarity_threshold,
                        metadata_filters=document_filters,
                    )
                    logger.info(f"🔍 DEBUG: Search query created: {search_query}")

                    # Search vector store
                    logger.info("🔍 DEBUG: Calling vector store search...")
                    search_results = await self.vector_store.search(search_query)
                    logger.info(
                        f"🔍 DEBUG: Vector store returned {len(search_results)} results"
                    )

                    # Add results to our collection (with deduplication)
                    added_count = 0
                    for j, result in enumerate(search_results):
                        logger.info(
                            f"🔍 DEBUG: Result {j+1}: similarity={result.similarity_score:.3f}, threshold={similarity_threshold}"
                        )
                        if result.similarity_score >= similarity_threshold:
                            # Check if we already have this chunk (by chunk ID)
                            chunk_id = result.chunk.id
                            if chunk_id not in seen_chunk_ids:
                                all_search_results.append(result)
                                seen_chunk_ids.add(chunk_id)
                                added_count += 1
                                logger.info(
                                    f"🔍 DEBUG: Added search result {len(all_search_results)}: {result.chunk.content[:50]}..."
                                )
                            else:
                                logger.info(
                                    f"🔍 DEBUG: Skipped duplicate chunk {chunk_id}"
                                )

                    logger.info(
                        f"🔍 DEBUG: Query '{query_text}' returned {len(search_results)} results, added {added_count} new results, total results: {len(all_search_results)}"
                    )

                    # Early exit if we have enough unique chunks
                    if len(all_search_results) >= context_chunks:
                        logger.info(
                            f"🔍 DEBUG: Reached target of {context_chunks} chunks, stopping search"
                        )
                        break

                except Exception as e:
                    logger.warning(f"Query '{query_text}' failed: {e}")
                    continue

            # Limit to requested number of chunks
            limited_results = all_search_results[:context_chunks]

            logger.info(
                f"Retrieved {len(limited_results)} context chunks for {attribute_type}"
            )
            return limited_results

        except Exception as e:
            logger.error(f"Failed to retrieve context for {attribute_type}: {e}")
            return []

    def _create_metadata_filters(
        self,
        document_id: str,
        attribute_type: AttributeType,
        base_filters: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Create metadata filters for context retrieval.

        Args:
            document_id: Document identifier
            attribute_type: Type of attribute
            base_filters: Base metadata filters

        Returns:
            Combined metadata filters
        """
        filters = base_filters or {}

        # Add document-specific filters
        if document_id:
            filters["document_id"] = document_id

        # Add attribute-specific section filters
        section_filters = {
            AttributeType.NCT_NUMBER: ["Methods", "Background", "Introduction"],
            AttributeType.GENERIC_NAME: ["Methods", "Results", "Treatment"],
            AttributeType.P_VALUE_OS: ["Results", "Statistical Analysis", "Survival"],
            AttributeType.OBJECTIVE_RESPONSE_RATE: ["Results", "Efficacy", "Response"],
            AttributeType.GRADE_3_PLUS_AE: ["Results", "Safety", "Adverse Events"],
        }

        if attribute_type in section_filters:
            filters["Section"] = {"$in": section_filters[attribute_type]}

        return filters
