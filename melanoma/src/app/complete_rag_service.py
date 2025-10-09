"""Complete RAG Query Processing Service

This service provides complete RAG query processing that combines:
1. Query understanding and preprocessing
2. Vector similarity search (retrieval)
3. Context assembly and ranking
4. LLM-based response generation
5. Response validation and formatting

It orchestrates all components to provide end-to-end RAG functionality.
"""

import logging
from datetime import datetime
from typing import Any

from langchain.schema import HumanMessage, SystemMessage

from ..domain.models import (
    RAGQuery,
    RAGResponse,
    SearchQuery,
    SearchResult,
)
from ..infrastructure.langchain import (
    LangChainChunkingService,
    LangChainEmbeddingService,
    LangChainLLMService,
    LangChainVectorStore,
)

logger = logging.getLogger(__name__)


class CompleteRAGService:
    """Complete RAG query processing service.

    This service provides end-to-end RAG functionality by orchestrating
    all components: chunking, embedding, vector search, and LLM generation.
    """

    def __init__(
        self,
        chunking_service: LangChainChunkingService,
        embedding_service: LangChainEmbeddingService,
        vector_store: LangChainVectorStore,
        llm_service: LangChainLLMService,
    ):
        """Initialize the complete RAG service.

        Args:
            chunking_service: LangChain chunking service
            embedding_service: LangChain embedding service
            vector_store: LangChain vector store
            llm_service: LangChain LLM service
        """
        self.chunking_service = chunking_service
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.llm_service = llm_service

        # Initialize LLM for response generation
        self.llm = None
        self._initialize_llm()

        logger.info("Complete RAG service initialized")

    def _initialize_llm(self) -> None:
        """Initialize the LLM for response generation."""
        try:
            # Try to initialize with OpenAI (will fail gracefully if no API key)
            self.llm = self.llm_service.get_llm(
                model_name="gpt-3.5-turbo", temperature=0.1, max_tokens=1000
            )
            logger.info("LLM initialized successfully")
        except Exception as e:
            logger.warning(
                f"LLM initialization failed (will use retrieval-only mode): {e}"
            )
            self.llm = None

    async def process_query(self, query: RAGQuery) -> RAGResponse:
        """Process a complete RAG query.

        Args:
            query: RAG query to process

        Returns:
            RAG response with answer and sources

        Raises:
            RuntimeError: If query processing fails
        """
        try:
            start_time = datetime.now()
            logger.info(f"Processing RAG query: {query.question[:100]}...")

            # Step 1: Retrieve relevant chunks
            search_results = await self._retrieve_relevant_chunks(query)
            logger.info(f"Retrieved {len(search_results)} relevant chunks")

            # Step 2: Assemble context
            context = self._assemble_context(search_results)
            logger.info(f"Assembled context: {len(context)} characters")

            # Step 3: Generate response
            if self.llm and context:
                answer = await self._generate_response(query.question, context)
                confidence_score = self._calculate_confidence_score(
                    answer, search_results
                )
            else:
                # Fallback to retrieval-only mode
                answer = self._create_retrieval_only_response(search_results)
                confidence_score = 0.5  # Lower confidence for retrieval-only

            # Step 4: Format response
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

            response = RAGResponse(
                question=query.question,
                answer=answer,
                confidence_score=confidence_score,
                context_chunks=search_results,
                sources=self._extract_sources(search_results),
                processing_time_ms=processing_time,
                created_at=datetime.now(),
            )

            logger.info(f"RAG query processed successfully in {processing_time:.2f}ms")
            return response

        except Exception as e:
            logger.error(f"RAG query processing failed: {e}")
            raise RuntimeError(f"RAG query processing failed: {e}") from e

    async def _retrieve_relevant_chunks(self, query: RAGQuery) -> list[SearchResult]:
        """Retrieve relevant chunks using vector similarity search.

        Args:
            query: RAG query

        Returns:
            List of relevant search results
        """
        # Create search query
        search_query = SearchQuery(
            text=query.question,
            top_k=query.context_chunks or 5,
            similarity_threshold=query.similarity_threshold or 0.1,
            metadata_filters=query.metadata_filters or {},
        )

        # Search for relevant chunks
        search_results = await self.vector_store.search(search_query)

        # Sort by similarity score (highest first)
        search_results.sort(key=lambda x: x.similarity_score, reverse=True)

        return search_results

    def _assemble_context(self, search_results: list[SearchResult]) -> str:
        """Assemble context from search results.

        Args:
            search_results: List of search results

        Returns:
            Assembled context string
        """
        if not search_results:
            return ""

        context_parts = []
        for i, result in enumerate(search_results, 1):
            chunk = result.chunk

            # Add source information
            source_info = f"[Source {i}]"
            if chunk.metadata.get("abstract_id"):
                source_info += f" Abstract ID: {chunk.metadata['abstract_id']}"
            if chunk.metadata.get("year"):
                source_info += f" Year: {chunk.metadata['year']}"
            if chunk.metadata.get("Section"):
                source_info += f" Section: {chunk.metadata['Section']}"

            # Add content
            content = chunk.content.strip()
            context_parts.append(f"{source_info}\n{content}\n")

        return "\n".join(context_parts)

    async def _generate_response(self, question: str, context: str) -> str:
        """Generate response using LLM.

        Args:
            question: User question
            context: Retrieved context

        Returns:
            Generated response
        """
        if not self.llm:
            return "LLM not available for response generation."

        # Create prompt template
        prompt_template = """
You are a medical research assistant specializing in melanoma treatments and clinical trials.
Use the following context to answer the user's question about clinical trials, treatments, and research.

Context:
{context}

Question: {question}

Instructions:
1. Provide accurate, evidence-based answers based on the context
2. Include specific details like NCT numbers, trial names, and results when available
3. If the context doesn't contain enough information, say so clearly
4. Focus on clinical trial data, efficacy, safety, and treatment outcomes
5. Use medical terminology appropriately
6. Cite specific sources when possible

Answer:
"""

        try:
            # Generate response using LLM
            messages = [
                SystemMessage(
                    content="You are a medical research assistant specializing in melanoma treatments."
                ),
                HumanMessage(
                    content=prompt_template.format(context=context, question=question)
                ),
            ]

            response = await self.llm.ainvoke(messages)
            return response.content if hasattr(response, "content") else str(response)

        except Exception as e:
            logger.error(f"LLM response generation failed: {e}")
            return f"Response generation failed: {e}"

    def _create_retrieval_only_response(
        self, search_results: list[SearchResult]
    ) -> str:
        """Create a retrieval-only response when LLM is not available.

        Args:
            search_results: List of search results

        Returns:
            Retrieval-only response
        """
        if not search_results:
            return "No relevant information found for your query."

        response_parts = ["Based on the retrieved information:"]

        for i, result in enumerate(search_results, 1):
            chunk = result.chunk
            response_parts.append(f"\n{i}. {chunk.content[:200]}...")

            # Add source information
            if chunk.metadata.get("abstract_id"):
                response_parts.append(
                    f"   (Source: Abstract {chunk.metadata['abstract_id']})"
                )

        return "\n".join(response_parts)

    def _calculate_confidence_score(
        self, answer: str, search_results: list[SearchResult]
    ) -> float:
        """Calculate confidence score for the response.

        Args:
            answer: Generated answer
            search_results: Retrieved search results

        Returns:
            Confidence score between 0 and 1
        """
        if not search_results:
            return 0.0

        # Base confidence on similarity scores of retrieved chunks
        avg_similarity = sum(
            result.similarity_score for result in search_results
        ) / len(search_results)

        # Adjust based on answer quality indicators
        quality_indicators = 0
        if "NCT" in answer:  # Contains clinical trial ID
            quality_indicators += 0.2
        if any(
            word in answer.lower()
            for word in ["efficacy", "safety", "survival", "response"]
        ):
            quality_indicators += 0.2
        if len(answer) > 100:  # Substantial answer
            quality_indicators += 0.1

        # Combine similarity and quality
        confidence = min(0.9, avg_similarity + quality_indicators)
        return round(confidence, 3)

    def _extract_sources(
        self, search_results: list[SearchResult]
    ) -> list[dict[str, Any]]:
        """Extract source information from search results.

        Args:
            search_results: List of search results

        Returns:
            List of source dictionaries
        """
        sources = []
        for result in search_results:
            chunk = result.chunk
            source = {
                "abstract_id": chunk.metadata.get("abstract_id", ""),
                "year": chunk.metadata.get("year", ""),
                "section": chunk.metadata.get("Section", ""),
                "clinical_trial_id": chunk.metadata.get("clinical_trial_id", ""),
                "chunk_type": chunk.chunk_type.value,
                "similarity_score": result.similarity_score,
                "content_preview": chunk.content[:100] + "..."
                if len(chunk.content) > 100
                else chunk.content,
            }
            sources.append(source)

        return sources
