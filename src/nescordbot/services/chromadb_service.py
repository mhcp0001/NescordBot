"""
ChromaDB Service for vector database operations.

This module provides ChromaDBService for managing document embeddings
and performing semantic search using ChromaDB in-process database.
"""

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import chromadb  # type: ignore[import-untyped]
from chromadb.config import Settings  # type: ignore[import-untyped]
from chromadb.errors import NotFoundError  # type: ignore[import-untyped]

from ..config import BotConfig

# Logging configuration
logger = logging.getLogger(__name__)


@dataclass
class DocumentMetadata:
    """Metadata for a document stored in ChromaDB."""

    document_id: str
    title: Optional[str] = None
    source: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    tags: Optional[List[str]] = None
    user_id: Optional[str] = None
    content_type: Optional[str] = None


@dataclass
class SearchResult:
    """Result from ChromaDB vector search."""

    document_id: str
    content: str
    score: float
    metadata: DocumentMetadata


class ChromaDBServiceError(Exception):
    """Base exception for ChromaDB service errors."""

    pass


class ChromaDBConnectionError(ChromaDBServiceError):
    """Raised when ChromaDB connection fails."""

    pass


class ChromaDBCollectionError(ChromaDBServiceError):
    """Raised when collection operations fail."""

    pass


class ChromaDBOperationError(ChromaDBServiceError):
    """Raised when ChromaDB operations fail."""

    pass


class ChromaDBService:
    """
    ChromaDB service for vector database operations.

    Provides document storage, embedding management, and semantic search
    functionality using ChromaDB in-process database.
    """

    def __init__(self, config: BotConfig):
        """
        Initialize ChromaDB service.

        Args:
            config: Bot configuration containing ChromaDB settings
        """
        self.config = config
        self.client: Optional[Any] = None
        self.collection: Optional[Any] = None
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._initialized = False

        # Ensure persist directory exists
        self.persist_dir = Path(config.chromadb_persist_directory)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"ChromaDB service initialized with persist directory: {self.persist_dir}")

    async def initialize(self) -> None:
        """Initialize ChromaDB client and collection."""
        if self._initialized:
            return

        try:
            # Initialize client in thread pool to avoid blocking
            self.client = await asyncio.get_event_loop().run_in_executor(
                self.executor, self._init_client
            )

            # Get or create collection
            self.collection = await asyncio.get_event_loop().run_in_executor(
                self.executor, self._get_or_create_collection
            )

            self._initialized = True
            logger.info("ChromaDB service successfully initialized")

        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB service: {e}")
            raise ChromaDBConnectionError(f"ChromaDB initialization failed: {e}")

    def _init_client(self) -> Any:
        """Initialize ChromaDB client (runs in thread pool)."""
        try:
            # Create persistent client with custom settings
            settings = Settings(
                persist_directory=str(self.persist_dir),
                anonymized_telemetry=False,  # Disable telemetry
            )

            client = chromadb.PersistentClient(  # type: ignore[call-arg]
                path=str(self.persist_dir), settings=settings
            )

            logger.info("ChromaDB client created successfully")
            return client

        except Exception as e:
            logger.error(f"Failed to create ChromaDB client: {e}")
            raise ChromaDBConnectionError(f"Client creation failed: {e}")

    def _get_or_create_collection(self) -> Any:
        """Get or create ChromaDB collection (runs in thread pool)."""
        try:
            if not self.client:
                raise ChromaDBConnectionError("Client not initialized")

            # Try to get existing collection first
            try:
                collection = self.client.get_collection(name=self.config.chromadb_collection_name)
                logger.info(
                    f"Retrieved existing collection: {self.config.chromadb_collection_name}"
                )
                return collection

            except NotFoundError:
                # Collection doesn't exist, create it
                collection = self.client.create_collection(
                    name=self.config.chromadb_collection_name,
                    metadata={"hnsw:space": self.config.chromadb_distance_metric},
                )
                logger.info(f"Created new collection: {self.config.chromadb_collection_name}")
                return collection

        except Exception as e:
            logger.error(f"Failed to get or create collection: {e}")
            raise ChromaDBCollectionError(f"Collection setup failed: {e}")

    async def add_document(
        self,
        document_id: str,
        content: str,
        embedding: List[float],
        metadata: Optional[DocumentMetadata] = None,
    ) -> bool:
        """
        Add a document to ChromaDB.

        Args:
            document_id: Unique document identifier
            content: Document text content
            embedding: Pre-computed embedding vector
            metadata: Optional document metadata

        Returns:
            True if document was added successfully

        Raises:
            ChromaDBOperationError: If document addition fails
        """
        await self._ensure_initialized()

        try:
            # Prepare metadata for ChromaDB
            chroma_metadata = self._prepare_metadata(metadata)

            # Add document in thread pool
            await asyncio.get_event_loop().run_in_executor(
                self.executor,
                self._add_document_sync,
                document_id,
                content,
                embedding,
                chroma_metadata,
            )

            logger.debug(f"Document added successfully: {document_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to add document {document_id}: {e}")
            raise ChromaDBOperationError(f"Document addition failed: {e}")

    def _add_document_sync(
        self, document_id: str, content: str, embedding: List[float], metadata: Dict[str, Any]
    ) -> None:
        """Add document synchronously (runs in thread pool)."""
        if not self.collection:
            raise ChromaDBCollectionError("Collection not initialized")

        self.collection.add(
            ids=[document_id], documents=[content], embeddings=[embedding], metadatas=[metadata]
        )

    async def add_documents_batch(
        self, documents: List[Tuple[str, str, List[float], Optional[DocumentMetadata]]]
    ) -> int:
        """
        Add multiple documents in batch.

        Args:
            documents: List of tuples (document_id, content, embedding, metadata)

        Returns:
            Number of documents successfully added

        Raises:
            ChromaDBOperationError: If batch addition fails
        """
        await self._ensure_initialized()

        if not documents:
            return 0

        # Split into batches to respect batch size limits
        batch_size = min(self.config.chromadb_max_batch_size, len(documents))
        total_added = 0

        try:
            for i in range(0, len(documents), batch_size):
                batch = documents[i : i + batch_size]

                # Prepare batch data
                ids = [doc[0] for doc in batch]
                contents = [doc[1] for doc in batch]
                embeddings = [doc[2] for doc in batch]
                metadatas = [self._prepare_metadata(doc[3]) for doc in batch]

                # Add batch in thread pool
                await asyncio.get_event_loop().run_in_executor(
                    self.executor, self._add_batch_sync, ids, contents, embeddings, metadatas
                )

                total_added += len(batch)
                logger.debug(f"Added batch of {len(batch)} documents")

            logger.info(f"Successfully added {total_added} documents in batch")
            return total_added

        except Exception as e:
            logger.error(f"Batch document addition failed: {e}")
            raise ChromaDBOperationError(f"Batch addition failed: {e}")

    def _add_batch_sync(
        self,
        ids: List[str],
        contents: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
    ) -> None:
        """Add batch synchronously (runs in thread pool)."""
        if not self.collection:
            raise ChromaDBCollectionError("Collection not initialized")

        self.collection.add(ids=ids, documents=contents, embeddings=embeddings, metadatas=metadatas)

    async def search_documents(
        self,
        query_embedding: List[float],
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """
        Search documents by embedding similarity.

        Args:
            query_embedding: Query vector for similarity search
            n_results: Maximum number of results to return
            where: Optional metadata filters

        Returns:
            List of search results ordered by similarity

        Raises:
            ChromaDBOperationError: If search fails
        """
        await self._ensure_initialized()

        try:
            # Ensure n_results doesn't exceed configured maximum
            n_results = min(n_results, self.config.max_search_results)

            # Perform search in thread pool
            results = await asyncio.get_event_loop().run_in_executor(
                self.executor, self._search_sync, query_embedding, n_results, where
            )

            # Convert to SearchResult objects
            search_results = self._process_search_results(results)

            logger.debug(f"Found {len(search_results)} search results")
            return search_results

        except Exception as e:
            logger.error(f"Document search failed: {e}")
            raise ChromaDBOperationError(f"Search failed: {e}")

    def _search_sync(
        self, query_embedding: List[float], n_results: int, where: Optional[Dict[str, Any]]
    ) -> Any:
        """Perform search synchronously (runs in thread pool)."""
        if not self.collection:
            raise ChromaDBCollectionError("Collection not initialized")

        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

    def _process_search_results(self, results: Any) -> List[SearchResult]:
        """Process ChromaDB search results into SearchResult objects."""
        search_results: List[SearchResult] = []

        if not results or not results.get("ids"):
            return search_results

        # ChromaDB returns nested lists for batch queries, take first query results
        ids = results["ids"][0] if results["ids"] else []
        documents = results["documents"][0] if results["documents"] else []
        metadatas = results["metadatas"][0] if results["metadatas"] else []
        distances = results["distances"][0] if results["distances"] else []

        for i, doc_id in enumerate(ids):
            # Convert distance to similarity score (lower distance = higher similarity)
            # For cosine distance, convert to similarity score between 0 and 1
            distance = distances[i] if i < len(distances) else 1.0
            score = max(0.0, 1.0 - distance)  # Convert distance to similarity

            content = documents[i] if i < len(documents) else ""
            metadata_dict = metadatas[i] if i < len(metadatas) else {}

            # Convert metadata dict back to DocumentMetadata
            metadata = self._parse_metadata(metadata_dict)

            search_results.append(
                SearchResult(document_id=doc_id, content=content, score=score, metadata=metadata)
            )

        return search_results

    async def update_document(
        self,
        document_id: str,
        content: Optional[str] = None,
        embedding: Optional[List[float]] = None,
        metadata: Optional[DocumentMetadata] = None,
    ) -> bool:
        """
        Update an existing document.

        Args:
            document_id: Document identifier
            content: New content (optional)
            embedding: New embedding (optional)
            metadata: New metadata (optional)

        Returns:
            True if document was updated successfully

        Raises:
            ChromaDBOperationError: If document update fails
        """
        await self._ensure_initialized()

        try:
            # Prepare update data
            update_data: Dict[str, Any] = {}
            if content is not None:
                update_data["documents"] = [content]
            if embedding is not None:
                update_data["embeddings"] = [embedding]
            if metadata is not None:
                update_data["metadatas"] = [self._prepare_metadata(metadata)]

            if not update_data:
                logger.warning(f"No update data provided for document {document_id}")
                return True

            # Update document in thread pool
            await asyncio.get_event_loop().run_in_executor(
                self.executor, self._update_document_sync, document_id, update_data
            )

            logger.debug(f"Document updated successfully: {document_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update document {document_id}: {e}")
            raise ChromaDBOperationError(f"Document update failed: {e}")

    def _update_document_sync(self, document_id: str, update_data: Dict[str, Any]) -> None:
        """Update document synchronously (runs in thread pool)."""
        if not self.collection:
            raise ChromaDBCollectionError("Collection not initialized")

        self.collection.update(ids=[document_id], **update_data)

    async def delete_document(self, document_id: str) -> bool:
        """
        Delete a document from ChromaDB.

        Args:
            document_id: Document identifier

        Returns:
            True if document was deleted successfully

        Raises:
            ChromaDBOperationError: If document deletion fails
        """
        await self._ensure_initialized()

        try:
            await asyncio.get_event_loop().run_in_executor(
                self.executor, self._delete_document_sync, document_id
            )

            logger.debug(f"Document deleted successfully: {document_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            raise ChromaDBOperationError(f"Document deletion failed: {e}")

    def _delete_document_sync(self, document_id: str) -> None:
        """Delete document synchronously (runs in thread pool)."""
        if not self.collection:
            raise ChromaDBCollectionError("Collection not initialized")

        self.collection.delete(ids=[document_id])

    async def get_document_count(self) -> int:
        """
        Get total number of documents in collection.

        Returns:
            Number of documents in collection
        """
        await self._ensure_initialized()

        try:
            count = await asyncio.get_event_loop().run_in_executor(
                self.executor, self._get_count_sync
            )
            return count

        except Exception as e:
            logger.error(f"Failed to get document count: {e}")
            raise ChromaDBOperationError(f"Count retrieval failed: {e}")

    def _get_count_sync(self) -> int:
        """Get document count synchronously (runs in thread pool)."""
        if not self.collection:
            raise ChromaDBCollectionError("Collection not initialized")

        return int(self.collection.count())

    async def reset_collection(self) -> bool:
        """
        Reset (delete all documents from) the collection.

        Returns:
            True if collection was reset successfully

        Raises:
            ChromaDBOperationError: If collection reset fails
        """
        await self._ensure_initialized()

        try:
            await asyncio.get_event_loop().run_in_executor(
                self.executor, self._reset_collection_sync
            )

            logger.info("ChromaDB collection reset successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to reset collection: {e}")
            raise ChromaDBOperationError(f"Collection reset failed: {e}")

    def _reset_collection_sync(self) -> None:
        """Reset collection synchronously (runs in thread pool)."""
        if not self.collection or not self.client:
            raise ChromaDBCollectionError("Collection not initialized")

        # Delete and recreate collection
        self.client.delete_collection(name=self.config.chromadb_collection_name)
        self.collection = self.client.create_collection(
            name=self.config.chromadb_collection_name,
            metadata={"hnsw:space": self.config.chromadb_distance_metric},
        )

    def _prepare_metadata(self, metadata: Optional[DocumentMetadata]) -> Dict[str, Any]:
        """Convert DocumentMetadata to ChromaDB metadata format."""
        chroma_metadata = {}

        if metadata:
            # ChromaDB metadata values must be strings, numbers, or booleans
            if metadata.title:
                chroma_metadata["title"] = metadata.title
            if metadata.source:
                chroma_metadata["source"] = metadata.source
            if metadata.created_at:
                chroma_metadata["created_at"] = metadata.created_at
            if metadata.updated_at:
                chroma_metadata["updated_at"] = metadata.updated_at
            if metadata.user_id:
                chroma_metadata["user_id"] = metadata.user_id
            if metadata.content_type:
                chroma_metadata["content_type"] = metadata.content_type
            if metadata.tags:
                # Convert list to JSON string for storage
                chroma_metadata["tags"] = json.dumps(metadata.tags)

        # ChromaDB requires non-empty metadata, add default if empty
        if not chroma_metadata:
            chroma_metadata["_default"] = "true"

        return chroma_metadata

    def _parse_metadata(self, metadata_dict: Dict[str, Any]) -> DocumentMetadata:
        """Convert ChromaDB metadata to DocumentMetadata object."""
        tags = None
        if "tags" in metadata_dict:
            try:
                tags = json.loads(metadata_dict["tags"])
            except (json.JSONDecodeError, TypeError):
                tags = None

        return DocumentMetadata(
            document_id=metadata_dict.get("document_id", ""),
            title=metadata_dict.get("title"),
            source=metadata_dict.get("source"),
            created_at=metadata_dict.get("created_at"),
            updated_at=metadata_dict.get("updated_at"),
            user_id=metadata_dict.get("user_id"),
            content_type=metadata_dict.get("content_type"),
            tags=tags,
        )

    async def _ensure_initialized(self) -> None:
        """Ensure service is initialized before operations."""
        if not self._initialized:
            await self.initialize()

    async def close(self) -> None:
        """Clean up resources."""
        if self.executor:
            self.executor.shutdown(wait=True)
        self.client = None
        self.collection = None
        self._initialized = False
        logger.info("ChromaDB service closed")
