"""RAG orchestration service for clinical text processing.

This service orchestrates the complete RAG pipeline using LangChain infrastructure,
providing a clean application layer that coordinates chunking, embedding, vector storage,
and retrieval-augmented generation for clinical abstracts.
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from langchain.chains import RetrievalQA  # noqa: F401
    from langchain.prompts import PromptTemplate  # noqa: F401
    from langchain_core.language_models import BaseLLM  # noqa: F401

from ..domain.interfaces import RAGServiceInterface
from ..domain.models import (
    Chunk,
    ChunkingConfiguration,
    ChunkWithEmbedding,
    EmbeddingConfiguration,
    RAGQuery,
    RAGResponse,
    SearchQuery,
    SearchResult,
)

if TYPE_CHECKING:
    from ..infrastructure.langchain import (  # noqa: F401
        LangChainChunkingService,
        LangChainEmbeddingService,
        LangChainLLMService,
        LangChainVectorStore,
    )

logger = logging.getLogger(__name__)


class RAGPipelineOrchestrator:
    """Orchestrates the complete RAG pipeline.

    This class coordinates all components of the RAG pipeline including
    chunking, embedding, vector storage, and retrieval. It's separated
    to maintain single responsibility and make the orchestration logic
    testable.
    """

    def __init__(
        self,
        chunking_service: "LangChainChunkingService",
        embedding_service: "LangChainEmbeddingService",
        vector_store: "LangChainVectorStore",
        llm_service: "LangChainLLMService",
    ):
        """Initialize the RAG pipeline orchestrator.

        Args:
            chunking_service: LangChain chunking service
            embedding_service: LangChain embedding service
            vector_store: LangChain vector store
            llm_service: LangChain LLM service
        """
        # Lazy import to avoid import errors if langchain dependencies are not installed

        self.chunking_service = chunking_service
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.llm_service = llm_service

        logger.info("RAG pipeline orchestrator initialized")

    async def process_document(
        self,
        content: str,
        filename: str = "",
        document_id: Optional[str] = None,
        chunking_config: Optional[ChunkingConfiguration] = None,
        embedding_config: Optional[EmbeddingConfiguration] = None,
    ) -> list[ChunkWithEmbedding]:
        """Process a document through the complete RAG pipeline.

        Args:
            content: Document content to process
            filename: Filename for metadata extraction
            document_id: Document ID
            chunking_config: Chunking configuration
            embedding_config: Embedding configuration

        Returns:
            List of chunks with embeddings

        Raises:
            RuntimeError: If processing fails
        """
        try:
            logger.info(f"Starting document processing for: {filename}")

            # Use default configurations if not provided
            if chunking_config is None:
                chunking_config = ChunkingConfiguration()
            if embedding_config is None:
                embedding_config = EmbeddingConfiguration()

            # Step 1: Chunk the content
            logger.info("Step 1: Chunking content")
            chunks = await self.chunking_service.chunk_content(
                content=content,
                configuration=chunking_config,
                document_id=document_id,
                filename=filename,
            )

            # Step 2: Generate embeddings
            logger.info(f"Step 2: Generating embeddings for {len(chunks)} chunks")
            chunks_with_embeddings = await self._generate_embeddings_for_chunks(
                chunks, embedding_config
            )

            # Step 3: Store in vector database
            logger.info("Step 3: Storing chunks in vector database")
            await self.vector_store.store_chunks(chunks_with_embeddings)

            logger.info(
                f"Successfully processed document: {len(chunks_with_embeddings)} chunks stored"
            )
            return chunks_with_embeddings

        except Exception as e:
            logger.error(f"Document processing failed: {e}")
            raise RuntimeError(f"Document processing failed: {e}") from e

    async def _generate_embeddings_for_chunks(
        self,
        chunks: list[Chunk],
        embedding_config: EmbeddingConfiguration,
    ) -> list[ChunkWithEmbedding]:
        """Generate embeddings for chunks.

        Args:
            chunks: List of chunks to embed
            embedding_config: Embedding configuration

        Returns:
            List of chunks with embeddings
        """
        try:
            # Prepare texts for batch embedding
            texts = [chunk.content for chunk in chunks]

            # Generate embeddings in batch
            embeddings = await self.embedding_service.generate_embeddings_batch(
                texts, embedding_config
            )

            # Create chunks with embeddings
            chunks_with_embeddings = []
            for chunk, embedding in zip(chunks, embeddings):
                chunk_with_embedding = ChunkWithEmbedding(
                    id=chunk.id,
                    document_id=chunk.document_id,
                    content=chunk.content,
                    chunk_type=chunk.chunk_type,
                    metadata=chunk.metadata,
                    sequence_number=chunk.sequence_number,
                    token_count=chunk.token_count,
                    embedding=embedding,
                    embedding_model=embedding_config.model_name.value,
                    embedding_dimension=len(embedding),
                    embedding_generated_at=datetime.now(),
                )
                chunks_with_embeddings.append(chunk_with_embedding)

            return chunks_with_embeddings

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise RuntimeError(f"Embedding generation failed: {e}") from e

    async def search_similar_chunks(
        self,
        query_text: str,
        top_k: int = 10,
        similarity_threshold: float = 0.0,
        embedding_config: Optional[EmbeddingConfiguration] = None,
        **filters,
    ) -> list[SearchResult]:
        """Search for similar chunks.

        Args:
            query_text: Query text to search for
            top_k: Number of results to return
            similarity_threshold: Minimum similarity threshold
            embedding_config: Embedding configuration
            **filters: Additional search filters

        Returns:
            List of search results
        """
        try:
            # Use default embedding config if not provided
            if embedding_config is None:
                embedding_config = EmbeddingConfiguration()

            # Generate query embedding
            query_embedding = await self.embedding_service.generate_embedding(
                query_text, embedding_config
            )

            # Create search query
            search_query = SearchQuery(
                text=query_text,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                embedding=query_embedding,
                **filters,
            )

            # Search in vector store
            results = await self.vector_store.search_similar(search_query)

            logger.info(f"Found {len(results)} similar chunks for query")
            return results

        except Exception as e:
            logger.error(f"Similarity search failed: {e}")
            raise RuntimeError(f"Similarity search failed: {e}") from e


class LangChainRAGService(RAGServiceInterface):
    """LangChain-based RAG service for clinical text processing.

    This service provides sophisticated retrieval-augmented generation capabilities
    using LangChain infrastructure while maintaining clean architecture principles.
    """

    def __init__(
        self,
        pipeline_orchestrator: RAGPipelineOrchestrator,
        llm: "BaseLLM",
        temperature: float = 0.1,
    ):
        """Initialize the LangChain RAG service.

        Args:
            pipeline_orchestrator: RAG pipeline orchestrator
            llm: LLM instance for generation
            temperature: Temperature for generation
        """
        # Lazy import to avoid import errors if langchain dependencies are not installed
        from langchain_core.language_models import BaseLLM  # noqa: F401

        self.pipeline_orchestrator = pipeline_orchestrator
        self.llm = llm
        self.temperature = temperature

        # Create RAG chain
        self.rag_chain = self._create_rag_chain()

        logger.info("LangChain RAG service initialized")

    def _create_rag_chain(self) -> "RetrievalQA":
        """Create the LangChain RAG chain.

        Returns:
            Configured RetrievalQA chain
        """
        # Lazy import to avoid import errors if langchain dependencies are not installed
        from langchain.chains import RetrievalQA
        from langchain.prompts import PromptTemplate

        # Create custom prompt template for clinical queries
        prompt_template = """
You are a medical research assistant specializing in melanoma treatments.
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

Answer:
"""

        prompt = PromptTemplate(
            template=prompt_template, input_variables=["context", "question"]
        )

        # Create RetrievalQA chain
        # Initialize vectorstore synchronously (lazy initialization will happen on first use)
        # The vectorstore will be initialized when first accessed
        vectorstore = self.pipeline_orchestrator.vector_store._vectorstore
        if vectorstore is None:
            # If not initialized, we'll initialize it lazily on first use
            # For now, we'll create a wrapper that initializes on access
            import asyncio

            try:
                # Try to get existing event loop
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Can't use await in sync context, will initialize lazily
                    vectorstore = None
                else:
                    vectorstore = loop.run_until_complete(
                        self.pipeline_orchestrator.vector_store._ensure_vectorstore_initialized()
                    )
            except RuntimeError:
                # No event loop, create one
                vectorstore = asyncio.run(
                    self.pipeline_orchestrator.vector_store._ensure_vectorstore_initialized()
                )

        if vectorstore is None:
            raise RuntimeError(
                "Vectorstore not initialized and cannot be initialized synchronously"
            )
        return RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=vectorstore.as_retriever(
                search_kwargs={"k": 5}  # Retrieve top 5 most relevant chunks
            ),
            chain_type_kwargs={"prompt": prompt},
            return_source_documents=True,
        )

    async def process_query(self, query: RAGQuery) -> RAGResponse:
        """Process a RAG query.

        Args:
            query: RAG query

        Returns:
            RAG response with answer and sources

        Raises:
            RuntimeError: If query processing fails
        """
        try:
            logger.info(f"Processing RAG query: {query.question[:100]}...")

            # Use LangChain RAG chain
            result = self.rag_chain({"query": query.question})

            # Extract answer and sources
            answer = result["result"]
            source_docs = result["source_documents"]

            # Convert source documents to SearchResult objects
            context_chunks = []
            sources = []

            for i, doc in enumerate(source_docs):
                # Create SearchResult from Document
                search_result = SearchResult(
                    chunk=self._convert_doc_to_chunk(doc),
                    similarity_score=1.0,  # LangChain doesn't provide scores in this context
                    rank=i + 1,
                )
                context_chunks.append(search_result)

                # Extract source information
                source_info = {
                    "abstract_id": doc.metadata.get("abstract_id", ""),
                    "year": doc.metadata.get("year", ""),
                    "section": doc.metadata.get("Section", ""),
                    "clinical_trial_id": doc.metadata.get("clinical_trial_id", ""),
                    "chunk_type": doc.metadata.get("chunk_type", ""),
                }
                sources.append(source_info)

            # Calculate confidence score
            confidence_score = self._calculate_confidence_score(answer, context_chunks)

            # Create RAG response
            response = RAGResponse(
                answer=answer,
                context_chunks=context_chunks,
                confidence_score=confidence_score,
                sources=sources,
                processing_time_ms=None,  # Could be added if needed
            )

            logger.info(
                f"RAG query processed successfully. Confidence: {confidence_score:.2f}"
            )
            return response

        except Exception as e:
            logger.error(f"RAG query processing failed: {e}")
            raise RuntimeError(f"RAG query processing failed: {e}") from e

    def _convert_doc_to_chunk(self, doc) -> ChunkWithEmbedding:
        """Convert LangChain Document to ChunkWithEmbedding.

        Args:
            doc: LangChain Document

        Returns:
            ChunkWithEmbedding object
        """
        from datetime import datetime
        from uuid import UUID, uuid4

        metadata = doc.metadata

        # Extract core metadata
        core_metadata = {
            k: v
            for k, v in metadata.items()
            if k
            not in [
                "chunk_type",
                "document_id",
                "sequence_number",
                "embedding_model",
                "created_at",
                "embedding_dimension",
            ]
        }

        return ChunkWithEmbedding(
            id=UUID(metadata.get("id", str(uuid4()))),
            document_id=str(UUID(metadata["document_id"])),
            content=doc.page_content,
            chunk_type=type(metadata["chunk_type"])(metadata["chunk_type"]),
            metadata=core_metadata,
            sequence_number=int(metadata["sequence_number"]),
            token_count=None,
            embedding=None,
            embedding_model=metadata.get("embedding_model"),
            created_at=datetime.fromisoformat(metadata["created_at"]),
            embedding_dimension=None,
        )

    def _calculate_confidence_score(
        self, answer: str, context_chunks: list[SearchResult]
    ) -> float:
        """Calculate confidence score for the answer.

        Args:
            answer: Generated answer
            context_chunks: Context chunks used

        Returns:
            Confidence score between 0.0 and 1.0
        """
        if not answer or not context_chunks:
            return 0.0

        # Base confidence on number of sources and answer quality
        source_confidence = min(len(context_chunks) / 5.0, 1.0)  # Max at 5 sources

        # Check if answer contains specific clinical data
        clinical_indicators = [
            "NCT",
            "trial",
            "study",
            "patients",
            "response",
            "survival",
            "efficacy",
            "safety",
            "adverse",
            "dose",
            "treatment",
        ]

        answer_lower = answer.lower()
        clinical_score = sum(
            1 for indicator in clinical_indicators if indicator in answer_lower
        )
        clinical_confidence = min(clinical_score / len(clinical_indicators), 1.0)

        # Combine scores
        confidence = (source_confidence * 0.6) + (clinical_confidence * 0.4)

        return min(confidence, 1.0)

    async def generate_context(self, question: str, chunks: list[SearchResult]) -> str:
        """Generate context from retrieved chunks.

        Args:
            question: User question
            chunks: Retrieved chunks

        Returns:
            Formatted context string
        """
        if not chunks:
            return "No relevant context found."

        context_parts = []
        for i, chunk_result in enumerate(chunks, 1):
            chunk = chunk_result.chunk
            context_parts.append(
                f"Source {i} ({chunk.chunk_type.value}):\n{chunk.content}\n"
            )

        return "\n".join(context_parts)

    async def format_response(
        self, answer: str, sources: list[SearchResult]
    ) -> RAGResponse:
        """Format the final RAG response.

        Args:
            answer: Generated answer
            sources: Source chunks

        Returns:
            Formatted RAG response
        """
        # Extract source information
        source_info = []
        for source in sources:
            chunk = source.chunk
            source_info.append(
                {
                    "abstract_id": chunk.metadata.get("abstract_id", ""),
                    "year": chunk.metadata.get("year", ""),
                    "section": chunk.metadata.get("Section", ""),
                    "clinical_trial_id": chunk.metadata.get("clinical_trial_id", ""),
                    "chunk_type": chunk.chunk_type.value,
                }
            )

        # Calculate confidence
        confidence = self._calculate_confidence_score(answer, sources)

        return RAGResponse(
            answer=answer,
            context_chunks=sources,
            confidence_score=confidence,
            sources=source_info,
        )

    def get_service_statistics(self) -> dict[str, Any]:
        """Get statistics about the RAG service.

        Returns:
            Dictionary containing service statistics
        """
        return {
            "llm_provider": type(self.llm).__name__,
            "temperature": self.temperature,
            "pipeline_components": {
                "chunking": type(self.pipeline_orchestrator.chunking_service).__name__,
                "embedding": type(
                    self.pipeline_orchestrator.embedding_service
                ).__name__,
                "vector_store": type(self.pipeline_orchestrator.vector_store).__name__,
            },
        }
