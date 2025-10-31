"""Arm-aware RAG context provider implementation.

This service provides RAG context retrieval that is aware of treatment arms,
providing targeted context for each arm and attribute combination.
"""

import logging
from typing import Any, Optional

from ..domain.extraction_interfaces import RAGContextProvider
from ..domain.extraction_models import AttributeType
from ..domain.models import SearchQuery, SearchResult
from ..domain.rag_optimization_config import RAGOptimizationConfig
from ..domain.treatment_arm_models import ArmSpecificContext, TreatmentArm
from .langchain import LangChainEmbeddingService, LangChainVectorStore
from .rag_config_loader import RAGConfigLoader

logger = logging.getLogger(__name__)


class ArmAwareRAGContextProvider(RAGContextProvider):
    """RAG context provider that is aware of treatment arms.

    This service provides targeted context retrieval for specific
    treatment arms and attributes, improving extraction precision.
    """

    def __init__(
        self,
        vector_store: LangChainVectorStore,
        embedding_service: LangChainEmbeddingService,
    ):
        """Initialize arm-aware RAG context provider.

        Args:
            vector_store: LangChain vector store for similarity search
            embedding_service: LangChain embedding service
        """
        self.vector_store = vector_store
        self.embedding_service = embedding_service

        # Load optimized query templates from YAML configuration
        # This provides better context for LLM extraction across all 114 attributes
        config_loader = RAGConfigLoader()
        self.arm_attribute_queries = config_loader.get_all_templates()

        logger.info(
            "Arm-aware RAG provider initialized with %d attribute query templates",
            len(self.arm_attribute_queries),
        )

        # Legacy hardcoded queries (kept for reference, but YAML is used)
        _legacy_queries = {
            AttributeType.NCT_NUMBER: [
                "NCT number clinical trial identifier",
                "ClinicalTrials.gov registration number",
                "trial registration NCT",
                "clinical trial number",
                "study registration",
            ],
            AttributeType.GENERIC_NAME: [
                "generic drug name treatment arm",
                "medication name therapy",
                "drug name treatment",
                "study drug medication",
                "therapeutic agent drug",
                "treatment regimen drug",
            ],
            AttributeType.P_VALUE_OS: [
                "overall survival p-value significance",
                "OS p-value statistical significance",
                "survival analysis p-value",
                "p value overall survival",
                "statistical significance survival",
                "hazard ratio survival",
                "median overall survival",
                "survival endpoint p-value",
            ],
            AttributeType.OBJECTIVE_RESPONSE_RATE: [
                "objective response rate ORR",
                "response rate efficacy",
                "tumor response rate",
                "response rate percentage",
                "overall response rate",
                "best overall response",
                "response evaluation",
                "tumor response evaluation",
            ],
            AttributeType.GRADE_3_PLUS_AE: [
                "grade 3 adverse events toxicity",
                "grade 3+ adverse events",
                "severe adverse events grade 3",
                "grade 3 higher adverse events",
                "treatment related adverse events",
                "serious adverse events",
                "toxicity grade 3",
                "adverse events grade 3 or higher",
            ],
        }

        logger.info("Arm-aware RAG context provider initialized")

    async def get_context_for_arm_attribute(
        self,
        arm: TreatmentArm,
        attribute_type: AttributeType,
        abstract_id: str,
        context_chunks: int = 5,
        similarity_threshold: float = 0.1,
        metadata_filters: Optional[dict[str, Any]] = None,
    ) -> ArmSpecificContext:
        """Get RAG context for a specific treatment arm and attribute.

        Args:
            arm: Treatment arm to get context for
            attribute_type: Type of attribute to extract
            abstract_id: Abstract identifier
            context_chunks: Number of context chunks to retrieve (will be overridden by optimization)
            similarity_threshold: Minimum similarity threshold
            metadata_filters: Optional metadata filters

        Returns:
            Arm-specific context with relevant chunks

        🎯 OPTIMIZATION: Uses dynamic chunk count and smart filtering
        """
        try:
            # 🎯 OPTIMIZATION 1: Use optimal chunk count based on attribute complexity
            optimal_chunks = RAGOptimizationConfig.get_optimal_chunk_count(
                attribute_type
            )
            target_chunks = optimal_chunks

            logger.info(
                f"Getting context for arm {arm.arm_id} and attribute {attribute_type} "
                f"(using {target_chunks} chunks, complexity: {RAGOptimizationConfig.get_complexity_level(attribute_type).value})"
            )

            # Create arm-specific queries
            queries = self._create_arm_specific_queries(arm, attribute_type)

            # Retrieve context using multiple queries
            all_search_results = []
            seen_chunk_ids = set()

            for query_text in queries:
                try:
                    # Create search query with abstract_id filter to get chunks only from this abstract
                    search_filters = {"abstract_id": abstract_id}

                    search_query = SearchQuery(
                        text=query_text,
                        top_k=target_chunks * 2,  # Retrieve more to allow filtering
                        similarity_threshold=similarity_threshold,
                        metadata_filters=search_filters,
                    )

                    # Search vector store
                    search_results = await self.vector_store.search(search_query)

                    # Add unique results with filtering
                    for result in search_results:
                        if result.chunk.id not in seen_chunk_ids:
                            # 🎯 OPTIMIZATION 2: Filter irrelevant chunks
                            if RAGOptimizationConfig.should_include_chunk(
                                result.chunk.content, attribute_type
                            ):
                                all_search_results.append(result)
                                seen_chunk_ids.add(result.chunk.id)
                            else:
                                logger.debug(
                                    f"Filtered out irrelevant chunk for {attribute_type.value}"
                                )

                    # Early exit if we have enough chunks
                    if len(all_search_results) >= target_chunks:
                        break

                except Exception as e:
                    logger.warning(f"Query '{query_text}' failed: {e}")
                    continue

            # If none found, retry without Section filter
            limited_results = all_search_results[:target_chunks]
            if not limited_results:
                try:
                    fallback_query = SearchQuery(
                        text=queries[0],
                        top_k=target_chunks,
                        similarity_threshold=similarity_threshold,
                        metadata_filters={"abstract_id": abstract_id},
                    )
                    limited_results = await self.vector_store.search(fallback_query)
                except Exception as _:
                    limited_results = []

            # Calculate context quality score
            quality_score = self._calculate_context_quality(
                limited_results, arm, attribute_type
            )

            # Create arm-specific context
            # Include full abstract as fallback context
            arm_meta = self._create_arm_metadata(arm)
            arm_meta["full_abstract"] = (
                arm.source_text
                if hasattr(arm, "source_text") and arm.source_text
                else ""
            )

            context = ArmSpecificContext(
                arm_id=arm.arm_id,
                abstract_id=abstract_id,
                context_chunks=self._format_context_chunks(limited_results),
                arm_metadata=arm_meta,
                context_quality_score=quality_score,
            )

            logger.info(
                f"Retrieved {len(limited_results)} optimized chunks for arm {arm.arm_id} "
                f"(target: {target_chunks}, complexity: {RAGOptimizationConfig.get_complexity_level(attribute_type).value})"
            )
            return context

        except Exception as e:
            logger.error(f"Failed to get context for arm {arm.arm_id}: {e}")
            return ArmSpecificContext(
                arm_id=arm.arm_id,
                abstract_id=abstract_id,
                context_chunks=[],
                arm_metadata={},
                context_quality_score=0.0,
            )

    async def get_context_for_attribute(
        self,
        document_id: Optional[str],
        attribute_type: AttributeType,
        context_chunks: int = 5,
        similarity_threshold: float = 0.1,
        metadata_filters: Optional[dict[str, Any]] = None,
    ) -> list[str]:
        """Get context for attribute extraction (legacy interface).

        This method provides backward compatibility with the existing
        RAG context provider interface.

        🎯 OPTIMIZATION: Uses dynamic chunk count and smart filtering
        """
        try:
            # 🎯 OPTIMIZATION 1: Use optimal chunk count based on attribute complexity
            optimal_chunks = RAGOptimizationConfig.get_optimal_chunk_count(
                attribute_type
            )
            target_chunks = optimal_chunks

            logger.debug(
                f"Using {target_chunks} chunks for {attribute_type.value} "
                f"(complexity: {RAGOptimizationConfig.get_complexity_level(attribute_type).value})"
            )

            # Create search query
            queries = self.arm_attribute_queries.get(
                attribute_type, [f"{attribute_type.value} data"]
            )

            all_search_results = []
            # Use (document_id, sequence_number) for deduplication since ChromaDB doesn't preserve chunk IDs
            seen_chunks = set()

            for query_text in queries:
                try:
                    search_filters = (metadata_filters or {}).copy()

                    # Only add document_id filter if provided (allows cross-document search)
                    if document_id:
                        search_filters[
                            "document_id"
                        ] = document_id  # Fixed: use correct key

                    search_query = SearchQuery(
                        text=query_text,
                        top_k=target_chunks * 2,  # Retrieve more to allow filtering
                        similarity_threshold=similarity_threshold,
                        metadata_filters=search_filters or {},  # Always pass dict
                    )

                    search_results = await self.vector_store.search(search_query)

                    for result in search_results:
                        # Deduplicate using (document_id, sequence_number) tuple
                        chunk_key = (
                            result.chunk.document_id,
                            result.chunk.sequence_number,
                        )
                        if chunk_key not in seen_chunks:
                            # 🎯 OPTIMIZATION 2: Filter irrelevant chunks
                            if RAGOptimizationConfig.should_include_chunk(
                                result.chunk.content, attribute_type
                            ):
                                all_search_results.append(result)
                                seen_chunks.add(chunk_key)
                            else:
                                logger.debug(
                                    f"Filtered out irrelevant chunk for {attribute_type.value}"
                                )

                    if len(all_search_results) >= target_chunks:
                        break

                except Exception as e:
                    logger.warning(f"Query '{query_text}' failed: {e}")
                    continue

            # Prioritize Results/Conclusions/Table chunks for numeric attributes
            prioritized_results = self._prioritize_results_sections(
                all_search_results, attribute_type
            )

            # Convert to string format for legacy interface
            context_strings = []
            for result in prioritized_results[:target_chunks]:
                context_strings.append(result.chunk.content)

            logger.info(
                f"Retrieved {len(context_strings)} optimized chunks for {attribute_type.value}"
            )
            return context_strings

        except Exception as e:
            logger.error(f"Failed to get context for attribute {attribute_type}: {e}")
            return []

    def _create_arm_specific_queries(
        self, arm: TreatmentArm, attribute_type: AttributeType
    ) -> list[str]:
        """Create arm-specific queries for context retrieval."""
        base_queries = self.arm_attribute_queries.get(
            attribute_type, [f"{attribute_type.value} data"]
        )

        # Enhance queries with arm-specific information
        arm_enhanced_queries = []

        for query in base_queries:
            # Add arm-specific context to query
            if arm.generic_name:
                arm_enhanced_queries.append(f"{query} {arm.generic_name}")

            if arm.dose:
                arm_enhanced_queries.append(f"{query} {arm.generic_name} {arm.dose}")

            if arm.arm_name:
                arm_enhanced_queries.append(f"{query} {arm.arm_name}")

            # Add original query
            arm_enhanced_queries.append(query)

        # Add treatment-specific queries
        if arm.is_combination:
            arm_enhanced_queries.append(f"{attribute_type.value} combination therapy")
            arm_enhanced_queries.append(
                f"{attribute_type.value} {arm.generic_name} combination"
            )

        if arm.arm_type.value == "dose_variation":
            arm_enhanced_queries.append(f"{attribute_type.value} dose escalation")
            arm_enhanced_queries.append(
                f"{attribute_type.value} {arm.generic_name} dose"
            )

        # Remove duplicates and limit
        unique_queries = list(dict.fromkeys(arm_enhanced_queries))
        return unique_queries[:10]  # Limit to 10 queries

    def _create_arm_search_filters(
        self,
        arm: TreatmentArm,
        abstract_id: str,
        base_filters: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Create search filters for arm-specific context retrieval."""
        filters = base_filters or {}

        # Add abstract ID filter
        filters["abstract_id"] = abstract_id

        # Note: Section filters removed for broader context retrieval

        # Note: We'll need to determine attribute type from context
        # For now, use general result sections
        # Build Chroma-compatible filter (no nested $eq around $in)
        filters["Section"] = {"$in": ["Results", "Methods", "Efficacy", "Safety"]}

        return filters

    def _calculate_context_quality(
        self,
        search_results: list[SearchResult],
        arm: TreatmentArm,
        attribute_type: AttributeType,
    ) -> float:
        """Calculate quality score for retrieved context."""
        if not search_results:
            return 0.0

        # Base quality from similarity scores
        avg_similarity = sum(
            result.similarity_score for result in search_results
        ) / len(search_results)

        # Quality factors
        quality_factors = [avg_similarity]

        # Factor 1: Arm-specific content relevance
        arm_relevance = 0.0
        for result in search_results:
            content = result.chunk.content.lower()
            if arm.generic_name and arm.generic_name.lower() in content:
                arm_relevance += 0.2
            if arm.dose and arm.dose.lower() in content:
                arm_relevance += 0.1
            if arm.arm_name and arm.arm_name.lower() in content:
                arm_relevance += 0.1

        arm_relevance = min(arm_relevance, 1.0)
        quality_factors.append(arm_relevance)

        # Factor 2: Attribute-specific content relevance
        attribute_relevance = 0.0
        attribute_keywords = {
            AttributeType.NCT_NUMBER: ["nct", "clinical trial", "registration"],
            AttributeType.GENERIC_NAME: ["drug", "medication", "therapy", "treatment"],
            AttributeType.P_VALUE_OS: [
                "p-value",
                "p value",
                "survival",
                "os",
                "overall survival",
            ],
            AttributeType.OBJECTIVE_RESPONSE_RATE: [
                "response",
                "orr",
                "objective response",
                "tumor response",
            ],
            AttributeType.GRADE_3_PLUS_AE: ["adverse", "toxicity", "grade 3", "safety"],
        }

        keywords = attribute_keywords.get(attribute_type, [])
        for result in search_results:
            content = result.chunk.content.lower()
            if keywords:  # Avoid division by zero
                keyword_matches = sum(1 for keyword in keywords if keyword in content)
                attribute_relevance += min(keyword_matches / len(keywords), 1.0)
            else:
                attribute_relevance += 0.0  # No keywords defined for this attribute

        attribute_relevance = min(attribute_relevance / len(search_results), 1.0)
        quality_factors.append(attribute_relevance)

        # Factor 3: Context diversity (avoid too similar chunks)
        diversity_score = 1.0
        if len(search_results) > 1:
            similarities = []
            for i in range(len(search_results)):
                for j in range(i + 1, len(search_results)):
                    # Simple similarity based on content overlap
                    content1 = set(search_results[i].chunk.content.lower().split())
                    content2 = set(search_results[j].chunk.content.lower().split())
                    overlap = len(content1.intersection(content2)) / len(
                        content1.union(content2)
                    )
                    similarities.append(overlap)

            if similarities:
                avg_similarity = sum(similarities) / len(similarities)
                diversity_score = 1.0 - avg_similarity

        quality_factors.append(diversity_score)

        # Calculate overall quality score
        return sum(quality_factors) / len(quality_factors)

    def _format_context_chunks(
        self, search_results: list[SearchResult]
    ) -> list[dict[str, Any]]:
        """Format context chunks for storage."""
        formatted_chunks = []

        for i, result in enumerate(search_results):
            chunk_data = {
                "chunk_id": str(result.chunk.id),
                "content": result.chunk.content,
                "similarity_score": result.similarity_score,
                "rank": i + 1,
                "metadata": result.chunk.metadata,
                "chunk_type": result.chunk.chunk_type.value
                if hasattr(result.chunk, "chunk_type")
                else "unknown",
            }
            formatted_chunks.append(chunk_data)

        return formatted_chunks

    def _create_arm_metadata(self, arm: TreatmentArm) -> dict[str, Any]:
        """Create metadata for treatment arm."""
        return {
            "arm_id": arm.arm_id,
            "arm_name": arm.arm_name,
            "generic_name": arm.generic_name,
            "dose": arm.dose,
            "arm_type": arm.arm_type.value,
            "line_of_treatment": arm.line_of_treatment.value,
            "patient_count": arm.patient_count,
            "is_combination": arm.is_combination,
            "is_dose_variation": arm.is_dose_variation,
        }

    def _prioritize_results_sections(
        self, search_results: list[Any], attribute_type: AttributeType
    ) -> list[Any]:
        """Prioritize Results/Conclusions/Table chunks for numeric attributes.

        For numeric attributes, we want to extract from Results, Conclusions, or Tables,
        NOT from Background (which often references other studies).

        Args:
            search_results: List of search results with chunks
            attribute_type: Type of attribute being extracted

        Returns:
            Reordered list with Results/Conclusions/Tables first
        """
        from src.domain.models import ChunkType

        # Non-numeric attributes (can use any section)
        non_numeric_attributes = {
            AttributeType.TRIAL_NAME,
            AttributeType.CANCER_TYPE,
            AttributeType.NCT_NUMBER,
            AttributeType.BRAND_NAME,
            AttributeType.GENERIC_NAME,
            AttributeType.TYPE_OF_THERAPY,
            AttributeType.SUB_THERAPY,
        }

        # If non-numeric, return as-is (no prioritization needed)
        if attribute_type in non_numeric_attributes:
            return search_results

        # For numeric attributes, prioritize Results/Conclusions/Tables
        priority_sections = {
            ChunkType.RESULTS,
            ChunkType.CONCLUSIONS,
            ChunkType.TABLE,
        }

        # Separate into priority and non-priority chunks
        priority_chunks = []
        non_priority_chunks = []

        for result in search_results:
            chunk_type = result.chunk.chunk_type
            if chunk_type in priority_sections:
                priority_chunks.append(result)
            else:
                non_priority_chunks.append(result)

        # Log prioritization for debugging
        if priority_chunks:
            logger.debug(
                f"Prioritized {len(priority_chunks)} Results/Conclusions/Table chunks "
                f"for numeric attribute {attribute_type.value}"
            )

        # Return priority chunks first, then others
        return priority_chunks + non_priority_chunks
