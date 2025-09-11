"""Implementation of vector storage using ChromaDB.

This service provides vector storage and retrieval capabilities for chunks
with embeddings, using ChromaDB as the underlying vector database.
"""

import logging
from typing import Optional

import chromadb
from chromadb.config import Settings

from ..domain.constants import LogMessages, VectorStoreDefaults
from ..domain.interfaces import VectorStoreInterface
from ..domain.models import ChunkWithEmbedding, SearchQuery, SearchResult

logger = logging.getLogger(__name__)


class ChromaVectorStore(VectorStoreInterface):
    """ChromaDB implementation of vector storage.

    This service provides vector storage and retrieval capabilities using
    ChromaDB as the underlying vector database. It supports metadata
    filtering and similarity search.
    """

    def __init__(
        self, persist_directory: str = VectorStoreDefaults.DEFAULT_PERSIST_DIRECTORY
    ):
        """Initialize the vector store.

        Args:
            persist_directory: Directory to persist the ChromaDB data
        """
        self.persist_directory = persist_directory
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize the ChromaDB client and collection."""
        try:
            self.client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(anonymized_telemetry=False),
            )
            self.collection = self.client.get_or_create_collection(
                name=VectorStoreDefaults.DEFAULT_COLLECTION_NAME,
                metadata={"description": "Melanoma research chunks with embeddings"},
            )
            logger.info(f"✅ ChromaDB initialized at {self.persist_directory}")

        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            raise RuntimeError(f"ChromaDB initialization failed: {e}") from e

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

        # Validate chunks have embeddings
        chunks_with_embeddings = [
            chunk for chunk in chunks if chunk.embedding is not None
        ]
        if not chunks_with_embeddings:
            raise ValueError("No chunks with embeddings provided")

        try:
            # Prepare data for ChromaDB
            ids = [str(chunk.id) for chunk in chunks_with_embeddings]
            embeddings = [
                chunk.embedding
                for chunk in chunks_with_embeddings
                if chunk.embedding is not None
            ]
            documents = [chunk.content for chunk in chunks_with_embeddings]
            metadatas = [
                self._prepare_metadata(chunk) for chunk in chunks_with_embeddings
            ]

            # Store in ChromaDB
            # Convert to ChromaDB-compatible types
            from typing import Any, cast

            chroma_embeddings = cast(Any, embeddings)
            chroma_metadatas = cast(
                Any,
                [
                    {
                        k: v
                        for k, v in meta.items()
                        if isinstance(v, (str, int, float, bool))
                    }
                    for meta in metadatas
                ],
            )

            self.collection.add(
                ids=ids,
                embeddings=chroma_embeddings,
                documents=documents,
                metadatas=chroma_metadatas,
            )

            logger.info(
                LogMessages.CHUNKS_STORED.format(count=len(chunks_with_embeddings))
            )

        except Exception as e:
            logger.error(f"Failed to store chunks: {e}")
            raise RuntimeError(f"Chunk storage failed: {e}") from e

    async def search_similar(self, query: SearchQuery) -> list[SearchResult]:
        """Search for similar chunks.

        Args:
            query: Search query with text and filters

        Returns:
            List of search results ordered by similarity

        Raises:
            ValueError: If query is invalid or embedding is missing
            RuntimeError: If search operation fails
        """
        if not query.embedding:
            raise ValueError("Query embedding is required for search")

        try:
            # Build where clause for metadata filtering
            where_clause = self._build_where_clause(query)

            # Search in ChromaDB
            # Convert to ChromaDB-compatible type
            from typing import Any, cast

            chroma_query_embeddings = cast(Any, [query.embedding])

            results = self.collection.query(
                query_embeddings=chroma_query_embeddings,
                n_results=query.top_k,
                where=where_clause if where_clause else None,
            )

            # Convert to SearchResult objects
            search_results = []
            if (
                results["ids"]
                and results["distances"]
                and results["metadatas"]
                and results["documents"]
            ):
                for i, (chunk_id, distance, metadata, document) in enumerate(
                    zip(
                        results["ids"][0],
                        results["distances"][0],
                        results["metadatas"][0],
                        results["documents"][0],
                    )
                ):
                    # Convert distance to similarity score (ChromaDB uses cosine distance)
                    similarity_score = 1 - distance

                    if similarity_score >= query.similarity_threshold:
                        # Convert ChromaDB metadata to our expected type
                        typed_metadata: dict[str, str | int | float | bool] = {
                            k: v
                            for k, v in metadata.items()
                            if isinstance(v, (str, int, float, bool))
                        }

                        chunk = self._reconstruct_chunk(
                            chunk_id, document, typed_metadata
                        )
                        search_results.append(
                            SearchResult(
                                chunk=chunk,
                                similarity_score=similarity_score,
                                rank=i + 1,
                            )
                        )

            return search_results

        except Exception as e:
            logger.error(f"Failed to search similar chunks: {e}")
            raise RuntimeError(f"Similarity search failed: {e}") from e

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
            results = self.collection.get(ids=[chunk_id])

            if not results["ids"]:
                return None

            # Reconstruct ChunkWithEmbedding from ChromaDB result
            if results["documents"] and results["metadatas"]:
                # Convert ChromaDB metadata to our expected type
                metadata = results["metadatas"][0]
                typed_metadata: dict[str, str | int | float | bool] = {
                    k: v
                    for k, v in metadata.items()
                    if isinstance(v, (str, int, float, bool))
                }

                return self._reconstruct_chunk(
                    chunk_id, results["documents"][0], typed_metadata
                )
            return None

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
            self.collection.delete(ids=chunk_ids)
            logger.info(LogMessages.CHUNKS_DELETED.format(count=len(chunk_ids)))

        except Exception as e:
            logger.error(f"Failed to delete chunks: {e}")
            raise RuntimeError(f"Chunk deletion failed: {e}") from e

    async def get_store_info(self) -> dict[str, any]:
        """Get information about the vector store.

        Returns:
            Dictionary with store information

        Raises:
            RuntimeError: If info retrieval fails
        """
        try:
            count = self.collection.count()
            return {
                "total_chunks": count,
                "collection_name": self.collection.name,
                "persist_directory": self.persist_directory,
                "collection_metadata": self.collection.metadata,
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
            self.client.delete_collection(self.collection.name)
            self.collection = self.client.create_collection(
                name=VectorStoreDefaults.DEFAULT_COLLECTION_NAME,
                metadata={"description": "Melanoma research chunks with embeddings"},
            )
            logger.info(LogMessages.STORE_CLEARED)

        except Exception as e:
            logger.error(f"Failed to clear store: {e}")
            raise RuntimeError(f"Store clear failed: {e}") from e

    def _prepare_metadata(self, chunk: ChunkWithEmbedding) -> dict[str, any]:
        """Prepare metadata for ChromaDB storage.

        Args:
            chunk: Chunk to prepare metadata for

        Returns:
            Metadata dictionary for ChromaDB
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

        return metadata

    def _build_where_clause(self, query: SearchQuery) -> dict[str, any]:
        """Build where clause for ChromaDB query.

        Args:
            query: Search query with filters

        Returns:
            Where clause dictionary for ChromaDB
        """
        conditions = []

        if query.metadata_filters:
            for key, value in query.metadata_filters.items():
                conditions.append({key: {"$eq": value}})

        if query.chunk_types:
            conditions.append(
                {"chunk_type": {"$in": [ct.value for ct in query.chunk_types]}}
            )

        if len(conditions) == 0:
            return {}
        elif len(conditions) == 1:
            return conditions[0]
        else:
            return {"$and": conditions}

    def _reconstruct_chunk(
        self,
        chunk_id: str,
        document: str,
        metadata: dict[str, str | int | float | bool] | dict[str, any],
    ) -> ChunkWithEmbedding:
        """Reconstruct ChunkWithEmbedding from ChromaDB result.

        Args:
            chunk_id: ID of the chunk
            document: Document content
            metadata: Metadata from ChromaDB

        Returns:
            Reconstructed ChunkWithEmbedding
        """
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

        from datetime import datetime
        from uuid import UUID

        from src.domain.models import ChunkType

        return ChunkWithEmbedding(
            id=UUID(str(chunk_id)),
            document_id=UUID(str(metadata["document_id"])),
            content=document,
            chunk_type=ChunkType(str(metadata["chunk_type"])),
            metadata=core_metadata,
            sequence_number=int(metadata["sequence_number"]),
            token_count=None,  # Not available from ChromaDB
            embedding=None,  # ChromaDB doesn't return embeddings in search results
            embedding_model=str(metadata.get("embedding_model"))
            if metadata.get("embedding_model")
            else None,
            created_at=datetime.fromisoformat(str(metadata["created_at"])),
            embedding_dimension=int(str(metadata.get("embedding_dimension")))
            if metadata.get("embedding_dimension")
            else None,
        )
