"""LangChain-based vector store service for clinical embeddings.

This module provides a sophisticated vector store service that leverages LangChain's
Chroma integration while adding advanced filtering, metadata handling, and performance
optimizations for clinical text storage and retrieval.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

try:
    from langchain_chroma import Chroma
except ImportError:
    from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

from ...domain.constants import VectorStoreDefaults
from ...domain.interfaces import VectorStoreInterface
from ...domain.models import (
    ChunkWithEmbedding,
    EmbeddingConfiguration,
    SearchQuery,
    SearchResult,
)

logger = logging.getLogger(__name__)


class ChromaDBEmbeddingFunction:
    """ChromaDB-compatible embedding function wrapper.

    This class provides a ChromaDB-compatible embedding function interface
    using LangChain's HuggingFaceEmbeddings directly.
    """

    def __init__(self, embedding_service=None):
        """Initialize the embedding function wrapper.

        Args:
            embedding_service: Optional embedding service (not used, kept for compatibility)
        """
        self._model = None
        logger.info("ChromaDB embedding function wrapper initialized")

    def _ensure_model_loaded(self):
        """Ensure the embedding model is loaded."""
        if self._model is None:
            try:
                # Set tokenizer parallelism to avoid warnings
                import os

                os.environ["TOKENIZERS_PARALLELISM"] = "false"

                # Try new package first, fallback to community
                try:
                    from langchain_huggingface import HuggingFaceEmbeddings
                except ImportError:
                    from langchain_community.embeddings import HuggingFaceEmbeddings

                self._model = HuggingFaceEmbeddings(
                    model_name="pritamdeka/S-BioBERT-snli-multinli-stsb",
                    model_kwargs={"device": "cpu"},
                    encode_kwargs={"normalize_embeddings": True},
                )
                logger.info("Embedding model loaded for ChromaDB")
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                raise

    def __call__(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        self._ensure_model_loaded()
        try:
            embeddings = self._model.embed_documents(texts)
            return embeddings
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise

    def embed_query(self, text: str) -> list[float]:
        """Generate embedding for a single query text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        self._ensure_model_loaded()
        try:
            embedding = self._model.embed_query(text)
            return embedding
        except Exception as e:
            logger.error(f"Failed to generate query embedding: {e}")
            raise

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple documents.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        self._ensure_model_loaded()
        try:
            embeddings = self._model.embed_documents(texts)
            return embeddings
        except Exception as e:
            logger.error(f"Failed to generate document embeddings: {e}")
            raise


class MetadataProcessor:
    """Processes metadata for ChromaDB storage and retrieval.

    This class encapsulates all metadata processing logic including preparation,
    filtering, and reconstruction. It's separated to maintain single responsibility
    and make the metadata processing logic testable.
    """

    # Metadata keys that are stored in ChromaDB
    CHROMA_METADATA_KEYS = {
        "chunk_type",
        "document_id",
        "sequence_number",
        "embedding_model",
        "created_at",
        "embedding_dimension",
    }

    def prepare_metadata_for_storage(self, chunk: ChunkWithEmbedding) -> dict[str, Any]:
        """Prepare metadata for ChromaDB storage.

        Args:
            chunk: Chunk to prepare metadata for

        Returns:
            Metadata dictionary for ChromaDB storage
        """
        metadata = {
            **chunk.metadata,
            "chunk_type": chunk.chunk_type.value,
            "document_id": str(chunk.document_id),
            "sequence_number": chunk.sequence_number,
            "embedding_model": chunk.embedding_model or "",
            "created_at": chunk.created_at.isoformat(),
        }

        # Add embedding dimension if available
        if chunk.embedding_dimension:
            metadata["embedding_dimension"] = chunk.embedding_dimension

        # Ensure all values are ChromaDB-compatible
        return self._ensure_chroma_compatibility(metadata)

    def _ensure_chroma_compatibility(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """Ensure metadata values are compatible with ChromaDB.

        Args:
            metadata: Metadata dictionary

        Returns:
            ChromaDB-compatible metadata dictionary
        """
        compatible_metadata = {}
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool)):
                compatible_metadata[key] = value
            elif isinstance(value, (list, tuple)):
                # Convert lists to strings for ChromaDB compatibility
                compatible_metadata[key] = str(value)
            else:
                # Convert other types to strings
                compatible_metadata[key] = str(value)

        return compatible_metadata

    def extract_core_metadata(self, chroma_metadata: dict[str, Any]) -> dict[str, Any]:
        """Extract core metadata from ChromaDB metadata.

        Args:
            chroma_metadata: Metadata from ChromaDB

        Returns:
            Core metadata dictionary
        """
        return {
            key: value
            for key, value in chroma_metadata.items()
            if key not in self.CHROMA_METADATA_KEYS
        }

    def build_filter_conditions(self, query: SearchQuery) -> Optional[dict[str, Any]]:
        """Build filter conditions for ChromaDB query.

        Args:
            query: Search query with filters

        Returns:
            Filter conditions for ChromaDB, or None if no filters
        """
        conditions = []

        # Metadata filters
        if query.metadata_filters:
            for key, value in query.metadata_filters.items():
                # Allow direct operators like $in in value, otherwise wrap in $eq
                if isinstance(value, dict) and any(
                    k.startswith("$") for k in value.keys()
                ):
                    conditions.append({key: value})
                else:
                    conditions.append({key: {"$eq": value}})

        # Chunk type filters
        if query.chunk_types:
            conditions.append(
                {"chunk_type": {"$in": [ct.value for ct in query.chunk_types]}}
            )

        if not conditions:
            return None
        elif len(conditions) == 1:
            return conditions[0]
        else:
            return {"$and": conditions}


class DocumentConverter:
    """Converts between domain models and LangChain documents.

    This class encapsulates all document conversion logic including
    chunk reconstruction and document creation. It's separated to maintain
    single responsibility and make the conversion logic testable.
    """

    def __init__(self, metadata_processor: MetadataProcessor):
        """Initialize the document converter.

        Args:
            metadata_processor: Metadata processor instance
        """
        self.metadata_processor = metadata_processor

    def chunk_to_langchain_document(self, chunk: ChunkWithEmbedding) -> Document:
        """Convert ChunkWithEmbedding to LangChain Document.

        Args:
            chunk: Chunk to convert

        Returns:
            LangChain Document
        """
        metadata = self.metadata_processor.prepare_metadata_for_storage(chunk)

        return Document(page_content=chunk.content, metadata=metadata)

    def langchain_document_to_chunk(
        self, document: Document, chunk_id: str
    ) -> ChunkWithEmbedding:
        """Convert LangChain Document to ChunkWithEmbedding.

        Args:
            document: LangChain Document
            chunk_id: ID of the chunk

        Returns:
            ChunkWithEmbedding
        """
        from datetime import datetime

        metadata = document.metadata
        core_metadata = self.metadata_processor.extract_core_metadata(metadata)

        return ChunkWithEmbedding(
            id=UUID(chunk_id),
            document_id=metadata["document_id"],  # Keep as string
            content=document.page_content,
            chunk_type=type(metadata["chunk_type"])(metadata["chunk_type"]),
            metadata=core_metadata,
            sequence_number=int(metadata["sequence_number"]),
            token_count=None,  # Not available from ChromaDB
            embedding=None,  # ChromaDB doesn't return embeddings in search
            embedding_model=metadata.get("embedding_model") or None,
            created_at=datetime.fromisoformat(metadata["created_at"]),
            embedding_dimension=int(metadata["embedding_dimension"])
            if metadata.get("embedding_dimension")
            else None,
        )


class LangChainVectorStore(VectorStoreInterface):
    """LangChain-based vector store service for clinical embeddings.

    This service provides sophisticated vector storage and retrieval using LangChain's
    Chroma integration while adding advanced filtering, metadata handling, and performance
    optimizations specifically designed for clinical text processing.
    """

    def __init__(
        self,
        persist_directory: str = VectorStoreDefaults.DEFAULT_PERSIST_DIRECTORY,
        collection_name: str = VectorStoreDefaults.DEFAULT_COLLECTION_NAME,
        embedding_function: Optional[Any] = None,
        embedding_service: Optional[Any] = None,
    ):
        """Initialize the LangChain vector store.

        Args:
            persist_directory: Directory to persist the vector store
            collection_name: Name of the collection
            embedding_function: Optional embedding function for ChromaDB
            embedding_service: Optional embedding service for generating embeddings
        """
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.embedding_service = embedding_service

        # Create ChromaDB-compatible embedding function
        if embedding_function is None:
            self.embedding_function = ChromaDBEmbeddingFunction()
        else:
            self.embedding_function = embedding_function

        self._vectorstore: Optional[Chroma] = None

        # Initialize helper services
        self.metadata_processor = MetadataProcessor()
        self.document_converter = DocumentConverter(self.metadata_processor)

        logger.info(
            f"LangChain vector store initialized for collection: {collection_name}"
        )

    async def _ensure_vectorstore_initialized(self) -> None:
        """Ensure the vector store is initialized.

        Raises:
            RuntimeError: If vector store initialization fails
        """
        if self._vectorstore is None:
            try:
                self._vectorstore = Chroma(
                    persist_directory=self.persist_directory,
                    collection_name=self.collection_name,
                    embedding_function=self.embedding_function,
                )
                logger.info(
                    f"LangChain Chroma vector store initialized at {self.persist_directory}"
                )

            except Exception as e:
                logger.error(f"Failed to initialize LangChain vector store: {e}")
                raise RuntimeError(f"Vector store initialization failed: {e}") from e

    async def store_chunks(self, chunks: list[ChunkWithEmbedding]) -> None:
        """Store chunks with their embeddings.

        Args:
            chunks: List of chunks with embeddings to store

        Raises:
            ValueError: If chunks list is empty or contains invalid data
            RuntimeError: If storage operation fails
        """
        if not chunks:
            logger.warning("No chunks provided for storage")
            return

        # Convert Chunk objects to ChunkWithEmbedding if needed
        chunks_with_embeddings = []
        for chunk in chunks:
            if hasattr(chunk, "embedding") and chunk.embedding is not None:
                # Already has embedding
                chunks_with_embeddings.append(chunk)
            else:
                # Need to generate embedding
                try:
                    # Generate embedding for the chunk
                    embedding_config = EmbeddingConfiguration(
                        model_name="pritamdeka/S-BioBERT-snli-multinli-stsb",
                        batch_size=32,
                        normalize_embeddings=True,
                    )

                    # Generate embedding synchronously using threading to avoid event loop conflicts
                    import asyncio
                    import threading

                    def run_async_embedding(chunk_content, config):
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            return new_loop.run_until_complete(
                                self.embedding_service.generate_embedding(
                                    text=chunk_content, config=config
                                )
                            )
                        finally:
                            new_loop.close()

                    # Run in a separate thread to avoid event loop conflicts
                    result_container = [None]
                    exception_container = [None]

                    def thread_target(
                        chunk_content, config, result_container, exception_container
                    ):
                        try:
                            result_container[0] = run_async_embedding(
                                chunk_content, config
                            )
                        except Exception as e:
                            exception_container[0] = e

                    thread = threading.Thread(
                        target=thread_target,
                        args=(
                            chunk.content,
                            embedding_config,
                            result_container,
                            exception_container,
                        ),
                    )
                    thread.start()
                    thread.join()

                    if exception_container[0]:
                        raise exception_container[0]

                    embedding = result_container[0]

                    # Create ChunkWithEmbedding
                    from ...domain.models import ChunkWithEmbedding

                    chunk_with_embedding = ChunkWithEmbedding(
                        id=chunk.id,
                        document_id=chunk.document_id,
                        content=chunk.content,
                        chunk_type=chunk.chunk_type,
                        metadata=chunk.metadata,
                        sequence_number=chunk.sequence_number,
                        token_count=chunk.token_count,
                        created_at=chunk.created_at,
                        embedding=embedding,
                        embedding_model="pritamdeka/S-BioBERT-snli-multinli-stsb",
                        embedding_dimension=len(embedding),
                        embedding_generated_at=datetime.now(timezone.utc),
                    )
                    chunks_with_embeddings.append(chunk_with_embedding)

                except Exception as e:
                    logger.warning(
                        f"Failed to generate embedding for chunk {chunk.id}: {e}"
                    )
                    continue

        if not chunks_with_embeddings:
            raise ValueError("No chunks with embeddings could be processed")

        try:
            await self._ensure_vectorstore_initialized()

            # Convert chunks to LangChain documents
            documents = []
            ids = []

            for chunk in chunks_with_embeddings:
                document = self.document_converter.chunk_to_langchain_document(chunk)
                documents.append(document)
                ids.append(str(chunk.id))

            # Store in ChromaDB
            self._vectorstore.add_documents(documents, ids=ids)

            logger.info(
                f"Successfully stored {len(chunks_with_embeddings)} chunks using LangChain Chroma"
            )

        except Exception as e:
            logger.error(f"Failed to store chunks: {e}")
            raise RuntimeError(f"Chunk storage failed: {e}") from e

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        """Search for similar chunks.

        Args:
            query: Search query with text and filters

        Returns:
            List of search results ordered by similarity

        Raises:
            ValueError: If query is invalid or embedding is missing
            RuntimeError: If search operation fails
        """
        if not query.text:
            raise ValueError("Query text is required for search")

        try:
            await self._ensure_vectorstore_initialized()

            # Generate embedding for the query text
            from ...domain.models import EmbeddingConfiguration

            embedding_config = EmbeddingConfiguration(
                model_name="pritamdeka/S-BioBERT-snli-multinli-stsb"
            )

            # Generate embedding synchronously using threading to avoid event loop conflicts
            import asyncio
            import threading

            def run_async_embedding():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(
                        self.embedding_service.generate_embedding(
                            text=query.text, config=embedding_config
                        )
                    )
                finally:
                    new_loop.close()

            # Run embedding generation in a separate thread and get the result
            result_container = [None]
            exception_container = [None]

            def thread_target():
                try:
                    result_container[0] = run_async_embedding()
                except Exception as e:
                    exception_container[0] = e

            embedding_thread = threading.Thread(target=thread_target)
            embedding_thread.start()
            embedding_thread.join()

            if exception_container[0]:
                raise exception_container[0]

            # Build filter conditions
            filter_conditions = self.metadata_processor.build_filter_conditions(query)

            # Search in ChromaDB using query text (ChromaDB will use the same embedding function)
            logger.info(
                f"Searching for query: '{query.text}' with top_k={query.top_k}, threshold={query.similarity_threshold}"
            )
            logger.info(f"Filter conditions: {filter_conditions}")

            docs_with_scores = self._vectorstore.similarity_search_with_score(
                query.text,
                k=query.top_k,
                filter=filter_conditions,
            )

            logger.info(
                f"ChromaDB returned {len(docs_with_scores)} documents with scores"
            )

            # Convert to search results
            search_results = []
            for rank, (document, score) in enumerate(docs_with_scores, 1):
                # ChromaDB returns distance scores (lower = more similar)
                # Convert to similarity score: similarity = 1 / (1 + distance)
                similarity_score = 1 / (1 + score)

                logger.info(
                    f"Document {rank}: distance={score:.4f}, similarity={similarity_score:.4f}, threshold={query.similarity_threshold}"
                )

                if similarity_score >= query.similarity_threshold:
                    # Reconstruct chunk from document
                    chunk = self.document_converter.langchain_document_to_chunk(
                        document, str(uuid4())  # Generate new ID for search result
                    )

                    search_results.append(
                        SearchResult(
                            chunk=chunk,
                            similarity_score=similarity_score,
                            rank=rank,
                        )
                    )

            logger.info(f"Found {len(search_results)} similar chunks for query")
            return search_results

        except Exception as e:
            logger.error(f"Failed to search similar chunks: {e}")
            raise RuntimeError(f"Similarity search failed: {e}") from e

    async def search_similar(self, query: SearchQuery) -> list[SearchResult]:
        """Search for similar chunks (alias for search method).

        Args:
            query: Search query with text and filters

        Returns:
            List of search results ordered by similarity
        """
        return await self.search(query)

    async def get_chunk_by_id(self, chunk_id: str) -> Optional[ChunkWithEmbedding]:
        """Get a specific chunk by ID.

        Args:
            chunk_id: ID of the chunk to retrieve

        Returns:
            ChunkWithEmbedding if found, None otherwise

        Raises:
            RuntimeError: If retrieval operation fails
        """
        try:
            await self._ensure_vectorstore_initialized()

            # Get document by ID
            docs = self._vectorstore.get(ids=[chunk_id])

            if not docs["ids"]:
                return None

            # Reconstruct chunk from document
            document = Document(
                page_content=docs["documents"][0], metadata=docs["metadatas"][0]
            )

            return self.document_converter.langchain_document_to_chunk(
                document, chunk_id
            )

        except Exception as e:
            logger.error(f"Failed to get chunk by ID {chunk_id}: {e}")
            raise RuntimeError(f"Chunk retrieval failed: {e}") from e

    async def delete_chunks(self, chunk_ids: list[str]) -> None:
        """Delete chunks by their IDs.

        Args:
            chunk_ids: List of chunk IDs to delete

        Raises:
            RuntimeError: If deletion operation fails
        """
        if not chunk_ids:
            logger.warning("No chunk IDs provided for deletion")
            return

        try:
            await self._ensure_vectorstore_initialized()

            self._vectorstore.delete(ids=chunk_ids)
            logger.info(f"Successfully deleted {len(chunk_ids)} chunks using LangChain")

        except Exception as e:
            logger.error(f"Failed to delete chunks: {e}")
            raise RuntimeError(f"Chunk deletion failed: {e}") from e

    async def get_store_info(self) -> dict[str, Any]:
        """Get information about the vector store.

        Returns:
            Dictionary with store information

        Raises:
            RuntimeError: If info retrieval fails
        """
        try:
            await self._ensure_vectorstore_initialized()

            # Get collection info
            collection = self._vectorstore._collection
            count = collection.count()

            return {
                "total_chunks": count,
                "collection_name": collection.name,
                "persist_directory": self.persist_directory,
                "collection_metadata": collection.metadata,
            }

        except Exception as e:
            logger.error(f"Failed to get store info: {e}")
            raise RuntimeError(f"Store info retrieval failed: {e}") from e

    async def clear_store(self) -> None:
        """Clear all data from the vector store.

        Raises:
            RuntimeError: If clear operation fails
        """
        try:
            await self._ensure_vectorstore_initialized()

            # Delete and recreate collection
            collection_name = self._vectorstore._collection.name
            self._vectorstore.delete_collection()
            self._vectorstore = Chroma(
                persist_directory=self.persist_directory,
                collection_name=collection_name,
                embedding_function=self.embedding_function,
            )

            logger.info("LangChain vector store cleared successfully")

        except Exception as e:
            logger.error(f"Failed to clear store: {e}")
            raise RuntimeError(f"Store clear failed: {e}") from e

    def get_vectorstore_statistics(self) -> dict[str, Any]:
        """Get statistics about the vector store.

        Returns:
            Dictionary containing vector store statistics
        """
        return {
            "persist_directory": self.persist_directory,
            "collection_name": self.collection_name,
            "has_embedding_function": self.embedding_function is not None,
            "is_initialized": self._vectorstore is not None,
        }
