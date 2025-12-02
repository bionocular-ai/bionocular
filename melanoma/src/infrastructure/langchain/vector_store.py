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
from langchain_core.embeddings import Embeddings

from ...domain.constants import VectorStoreDefaults
from ...domain.interfaces import VectorStoreInterface
from ...domain.models import (
    ChunkWithEmbedding,
    EmbeddingConfiguration,
    SearchQuery,
    SearchResult,
)

logger = logging.getLogger(__name__)


class ChromaDBEmbeddingFunction(Embeddings):
    """ChromaDB-compatible embedding function wrapper.

    This class provides a ChromaDB-compatible embedding function interface
    using LangChain's HuggingFaceEmbeddings directly.
    Implements the Embeddings interface for type compatibility.
    """

    def __init__(self, embedding_service=None):
        """Initialize the embedding function wrapper.

        Args:
            embedding_service: Optional embedding service (not used, kept for compatibility)
        """
        super().__init__()
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
                # Allow direct operators like $in in value, otherwise wrap in $eq or $in
                if isinstance(value, dict) and any(
                    k.startswith("$") for k in value.keys()
                ):
                    conditions.append({key: value})
                elif isinstance(value, list):
                    # 🎯 TIER 1: For lists (like chunk_type filter), use $in operator
                    conditions.append({key: {"$in": value}})
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

    async def _ensure_vectorstore_initialized(self) -> Chroma:
        """Ensure the vector store is initialized.

        Returns:
            Initialized Chroma vectorstore instance

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

        # Type assertion: after initialization, _vectorstore is guaranteed to be non-None
        assert self._vectorstore is not None, "Vectorstore should be initialized"
        return self._vectorstore

    async def store_chunks(self, chunks: list[ChunkWithEmbedding]) -> None:
        """Store chunks with their embeddings.

        Args:
            chunks: List of chunks with embeddings to store

        Raises:
            ValueError: If chunks list is empty or contains invalid data
            RuntimeError: If storage operation fails
        """
        # ChromaDB has a max batch size limit (typically ~5000)
        # Batch chunks into smaller groups to avoid exceeding the limit
        MAX_BATCH_SIZE = 5000

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
                    from ...domain.constants import EmbeddingModel

                    embedding_config = EmbeddingConfiguration(
                        model_name=EmbeddingModel.BIO_BERT_SNLI,
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

                    # Ensure embedding is not None before using len()
                    if embedding is None:
                        raise ValueError("Failed to generate embedding for chunk")

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

            # Batch chunks into smaller groups to avoid ChromaDB batch size limit
            total_chunks = len(chunks_with_embeddings)
            total_stored = 0

            for i in range(0, total_chunks, MAX_BATCH_SIZE):
                batch = chunks_with_embeddings[i : i + MAX_BATCH_SIZE]

                # Convert chunks to LangChain documents
                documents = []
                ids = []

                for chunk in batch:
                    document = self.document_converter.chunk_to_langchain_document(
                        chunk
                    )
                    documents.append(document)
                    ids.append(str(chunk.id))

                # Store batch in ChromaDB
                vectorstore = await self._ensure_vectorstore_initialized()
                vectorstore.add_documents(documents, ids=ids)
                total_stored += len(batch)

                logger.debug(
                    f"Stored batch {i//MAX_BATCH_SIZE + 1}: {len(batch)} chunks "
                    f"({total_stored}/{total_chunks} total)"
                )

            logger.info(
                f"Successfully stored {total_stored} chunks using LangChain Chroma "
                f"(in {(total_chunks + MAX_BATCH_SIZE - 1) // MAX_BATCH_SIZE} batches)"
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

            # Note: ChromaDB's similarity_search_with_score will automatically generate
            # embeddings using the embedding_function, so we don't need to generate them manually.
            # The embedding_service is only used if we need embeddings for other purposes.

            # Build filter conditions
            filter_conditions = self.metadata_processor.build_filter_conditions(query)

            # Search in ChromaDB using query text (ChromaDB will use the same embedding function)
            logger.info(
                f"Searching for query: '{query.text}' with top_k={query.top_k}, threshold={query.similarity_threshold}"
            )
            logger.info(f"Filter conditions: {filter_conditions}")

            vectorstore = await self._ensure_vectorstore_initialized()
            docs_with_scores = vectorstore.similarity_search_with_score(
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
            vectorstore = await self._ensure_vectorstore_initialized()
            docs = vectorstore.get(ids=[chunk_id])

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

            vectorstore = await self._ensure_vectorstore_initialized()
            vectorstore.delete(ids=chunk_ids)
            logger.info(f"Successfully deleted {len(chunk_ids)} chunks using LangChain")

        except Exception as e:
            logger.error(f"Failed to delete chunks: {e}")
            raise RuntimeError(f"Chunk deletion failed: {e}") from e

    async def delete_chunks_by_document_id(self, document_id: str) -> int:
        """Delete all chunks for a specific document.

        This is useful for re-ingesting documents without creating duplicates.

        Args:
            document_id: Document ID to delete chunks for

        Returns:
            Number of chunks deleted

        Raises:
            RuntimeError: If deletion operation fails
        """
        try:
            vectorstore = await self._ensure_vectorstore_initialized()

            # Get all chunks for this document
            collection = vectorstore._collection
            existing_data = collection.get(where={"document_id": document_id})

            if not existing_data["ids"]:
                logger.info(f"No existing chunks found for document {document_id}")
                return 0

            # Delete them
            chunk_ids = existing_data["ids"]
            collection.delete(ids=chunk_ids)

            logger.info(
                f"Deleted {len(chunk_ids)} existing chunks for document {document_id}"
            )
            return len(chunk_ids)

        except Exception as e:
            logger.error(f"Failed to delete chunks for document {document_id}: {e}")
            raise RuntimeError(f"Chunk deletion by document_id failed: {e}") from e

    async def upsert_chunks(self, chunks: list[ChunkWithEmbedding]) -> None:
        """Store chunks with automatic deduplication (upsert).

        This method will:
        1. Delete all existing chunks for each document_id in the batch
        2. Store the new chunks

        This prevents duplicate chunks from multiple ingestion runs.

        Args:
            chunks: List of chunks with embeddings to store

        Raises:
            ValueError: If chunks list is empty or contains invalid data
            RuntimeError: If storage operation fails
        """
        if not chunks:
            logger.warning("No chunks provided for upsert")
            return

        try:
            # Get unique document IDs
            document_ids = {chunk.document_id for chunk in chunks}

            logger.info(f"Upserting chunks for {len(document_ids)} document(s)")

            # Delete existing chunks for these documents
            total_deleted = 0
            for doc_id in document_ids:
                deleted_count = await self.delete_chunks_by_document_id(doc_id)
                total_deleted += deleted_count

            if total_deleted > 0:
                logger.info(
                    f"Removed {total_deleted} existing chunks before storing new ones"
                )

            # Store new chunks
            await self.store_chunks(chunks)
            logger.info(
                f"Upserted {len(chunks)} chunks (deleted {total_deleted}, stored {len(chunks)})"
            )

        except Exception as e:
            logger.error(f"Failed to upsert chunks: {e}")
            raise RuntimeError(f"Chunk upsert failed: {e}") from e

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
            vectorstore = await self._ensure_vectorstore_initialized()
            collection = vectorstore._collection
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
            vectorstore = await self._ensure_vectorstore_initialized()
            collection_name = vectorstore._collection.name
            vectorstore.delete_collection()
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
