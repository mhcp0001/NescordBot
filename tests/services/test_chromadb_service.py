"""
Tests for ChromaDBService.

This module contains comprehensive tests for ChromaDB vector database operations
including document storage, search, and metadata management.
"""

import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.nescordbot.config import BotConfig
from src.nescordbot.services.chromadb_service import (
    ChromaDBCollectionError,
    ChromaDBConnectionError,
    ChromaDBOperationError,
    ChromaDBService,
    ChromaDBServiceError,
    DocumentMetadata,
    SearchResult,
)


@pytest.fixture
def temp_chromadb_dir():
    """Create temporary directory for ChromaDB testing."""
    temp_dir = Path(tempfile.mkdtemp())
    yield str(temp_dir)
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def test_config(temp_chromadb_dir):
    """Create test configuration with temporary ChromaDB directory."""
    return BotConfig(
        discord_token="Bot TEST_TOKEN_FOR_TESTING",
        openai_api_key="sk-test-key",
        chromadb_persist_directory=temp_chromadb_dir,
        chromadb_collection_name="test_collection",
        chromadb_distance_metric="cosine",
        chromadb_max_batch_size=5,
        max_search_results=10,
    )


@pytest.fixture
def sample_embedding():
    """Sample embedding vector for testing."""
    return [0.1, 0.2, 0.3, 0.4, 0.5] * 154  # 770 dimensions to match typical embeddings


@pytest.fixture
def sample_metadata():
    """Sample document metadata for testing."""
    return DocumentMetadata(
        document_id="test-doc-1",
        title="Test Document",
        source="test",
        created_at="2025-08-25T10:00:00Z",
        updated_at="2025-08-25T10:00:00Z",
        tags=["test", "sample"],
        user_id="user123",
        content_type="text/plain",
    )


class TestChromaDBService:
    """Test cases for ChromaDBService."""

    @pytest.mark.asyncio
    async def test_service_initialization(self, test_config):
        """Test ChromaDBService initialization."""
        service = ChromaDBService(test_config)

        assert service.config == test_config
        assert service.persist_dir == Path(test_config.chromadb_persist_directory)
        assert not service._initialized
        assert service.client is None
        assert service.collection is None

    @pytest.mark.asyncio
    async def test_initialize_creates_client_and_collection(self, test_config):
        """Test that initialize creates client and collection."""
        service = ChromaDBService(test_config)

        await service.initialize()

        assert service._initialized
        assert service.client is not None
        assert service.collection is not None

        # Cleanup
        await service.close()

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, test_config):
        """Test that initialize can be called multiple times safely."""
        service = ChromaDBService(test_config)

        # First initialization
        await service.initialize()
        client1 = service.client
        collection1 = service.collection

        # Second initialization should not change anything
        await service.initialize()
        assert service.client is client1
        assert service.collection is collection1

        # Cleanup
        await service.close()

    @pytest.mark.asyncio
    async def test_add_document(self, test_config, sample_embedding, sample_metadata):
        """Test adding a single document."""
        service = ChromaDBService(test_config)
        await service.initialize()

        result = await service.add_document(
            document_id="test-doc-1",
            content="This is test content",
            embedding=sample_embedding,
            metadata=sample_metadata,
        )

        assert result is True

        # Verify document was added
        count = await service.get_document_count()
        assert count == 1

        # Cleanup
        await service.close()

    @pytest.mark.asyncio
    async def test_add_document_without_metadata(self, test_config, sample_embedding):
        """Test adding a document without metadata."""
        service = ChromaDBService(test_config)
        await service.initialize()

        result = await service.add_document(
            document_id="test-doc-1",
            content="This is test content",
            embedding=sample_embedding,
            metadata=None,
        )

        assert result is True

        # Verify document was added
        count = await service.get_document_count()
        assert count == 1

        # Cleanup
        await service.close()

    @pytest.mark.asyncio
    async def test_add_documents_batch(self, test_config, sample_embedding):
        """Test adding multiple documents in batch."""
        service = ChromaDBService(test_config)
        await service.initialize()

        # Prepare batch of documents
        documents = [
            ("doc-1", "Content 1", sample_embedding, None),
            ("doc-2", "Content 2", sample_embedding, None),
            ("doc-3", "Content 3", sample_embedding, None),
        ]

        result = await service.add_documents_batch(documents)

        assert result == 3

        # Verify all documents were added
        count = await service.get_document_count()
        assert count == 3

        # Cleanup
        await service.close()

    @pytest.mark.asyncio
    async def test_add_documents_batch_empty(self, test_config):
        """Test adding empty batch returns zero."""
        service = ChromaDBService(test_config)
        await service.initialize()

        result = await service.add_documents_batch([])

        assert result == 0

        # Cleanup
        await service.close()

    @pytest.mark.asyncio
    async def test_add_documents_batch_respects_max_batch_size(self, test_config, sample_embedding):
        """Test that large batches are split according to max_batch_size."""
        # Set small batch size for testing
        test_config.chromadb_max_batch_size = 2

        service = ChromaDBService(test_config)
        await service.initialize()

        # Prepare batch larger than max_batch_size
        documents = [(f"doc-{i}", f"Content {i}", sample_embedding, None) for i in range(5)]

        result = await service.add_documents_batch(documents)

        assert result == 5

        # Verify all documents were added
        count = await service.get_document_count()
        assert count == 5

        # Cleanup
        await service.close()

    @pytest.mark.asyncio
    async def test_search_documents(self, test_config, sample_embedding):
        """Test document search functionality."""
        service = ChromaDBService(test_config)
        await service.initialize()

        # Add test documents
        documents = [
            ("doc-1", "Python programming tutorial", sample_embedding, None),
            ("doc-2", "JavaScript web development", sample_embedding, None),
            ("doc-3", "Database design principles", sample_embedding, None),
        ]
        await service.add_documents_batch(documents)

        # Search for documents
        results = await service.search_documents(query_embedding=sample_embedding, n_results=2)

        assert len(results) <= 2
        assert all(isinstance(result, SearchResult) for result in results)
        assert all(result.score >= 0.0 for result in results)
        assert all(result.document_id in ["doc-1", "doc-2", "doc-3"] for result in results)

        # Cleanup
        await service.close()

    @pytest.mark.asyncio
    async def test_search_documents_with_metadata_filter(self, test_config, sample_embedding):
        """Test document search with metadata filtering."""
        service = ChromaDBService(test_config)
        await service.initialize()

        # Add test documents with metadata
        metadata1 = DocumentMetadata(
            document_id="doc-1", source="tutorial", content_type="text/plain"
        )
        metadata2 = DocumentMetadata(document_id="doc-2", source="blog", content_type="text/plain")

        documents = [
            ("doc-1", "Python tutorial", sample_embedding, metadata1),
            ("doc-2", "Python blog post", sample_embedding, metadata2),
        ]
        await service.add_documents_batch(documents)

        # Search with metadata filter
        results = await service.search_documents(
            query_embedding=sample_embedding, n_results=5, where={"source": "tutorial"}
        )

        # Should only return the tutorial document
        assert len(results) == 1
        assert results[0].document_id == "doc-1"

        # Cleanup
        await service.close()

    @pytest.mark.asyncio
    async def test_search_documents_respects_max_results(self, test_config, sample_embedding):
        """Test that search respects max_search_results configuration."""
        # Set small max_search_results for testing
        test_config.max_search_results = 2

        service = ChromaDBService(test_config)
        await service.initialize()

        # Add more documents than max_search_results
        documents = [(f"doc-{i}", f"Content {i}", sample_embedding, None) for i in range(5)]
        await service.add_documents_batch(documents)

        # Request more results than allowed
        results = await service.search_documents(query_embedding=sample_embedding, n_results=10)

        # Should be limited to max_search_results
        assert len(results) <= 2

        # Cleanup
        await service.close()

    @pytest.mark.asyncio
    async def test_update_document(self, test_config, sample_embedding, sample_metadata):
        """Test updating an existing document."""
        service = ChromaDBService(test_config)
        await service.initialize()

        # Add initial document
        await service.add_document(
            document_id="test-doc-1",
            content="Original content",
            embedding=sample_embedding,
            metadata=sample_metadata,
        )

        # Update document
        updated_metadata = DocumentMetadata(
            document_id="test-doc-1",
            title="Updated Title",
            source="updated",
        )

        result = await service.update_document(
            document_id="test-doc-1",
            content="Updated content",
            embedding=sample_embedding,  # Use same embedding dimension
            metadata=updated_metadata,
        )

        assert result is True

        # Cleanup
        await service.close()

    @pytest.mark.asyncio
    async def test_update_document_partial(self, test_config, sample_embedding, sample_metadata):
        """Test partial document update (only metadata)."""
        service = ChromaDBService(test_config)
        await service.initialize()

        # Add initial document
        await service.add_document(
            document_id="test-doc-1",
            content="Original content",
            embedding=sample_embedding,
            metadata=sample_metadata,
        )

        # Update only metadata
        updated_metadata = DocumentMetadata(
            document_id="test-doc-1",
            title="Updated Title Only",
        )

        result = await service.update_document(document_id="test-doc-1", metadata=updated_metadata)

        assert result is True

        # Cleanup
        await service.close()

    @pytest.mark.asyncio
    async def test_update_document_no_changes(self, test_config, sample_embedding, sample_metadata):
        """Test updating document with no changes."""
        service = ChromaDBService(test_config)
        await service.initialize()

        # Add initial document
        await service.add_document(
            document_id="test-doc-1",
            content="Original content",
            embedding=sample_embedding,
            metadata=sample_metadata,
        )

        # Update with no data - should return True anyway
        result = await service.update_document(document_id="test-doc-1")

        assert result is True

        # Cleanup
        await service.close()

    @pytest.mark.asyncio
    async def test_delete_document(self, test_config, sample_embedding, sample_metadata):
        """Test deleting a document."""
        service = ChromaDBService(test_config)
        await service.initialize()

        # Add document
        await service.add_document(
            document_id="test-doc-1",
            content="To be deleted",
            embedding=sample_embedding,
            metadata=sample_metadata,
        )

        # Verify document exists
        count_before = await service.get_document_count()
        assert count_before == 1

        # Delete document
        result = await service.delete_document("test-doc-1")

        assert result is True

        # Verify document was deleted
        count_after = await service.get_document_count()
        assert count_after == 0

        # Cleanup
        await service.close()

    @pytest.mark.asyncio
    async def test_get_document_count(self, test_config, sample_embedding):
        """Test getting document count."""
        service = ChromaDBService(test_config)
        await service.initialize()

        # Initially empty
        count = await service.get_document_count()
        assert count == 0

        # Add some documents
        documents = [
            ("doc-1", "Content 1", sample_embedding, None),
            ("doc-2", "Content 2", sample_embedding, None),
        ]
        await service.add_documents_batch(documents)

        # Check count again
        count = await service.get_document_count()
        assert count == 2

        # Cleanup
        await service.close()

    @pytest.mark.asyncio
    async def test_reset_collection(self, test_config, sample_embedding):
        """Test resetting collection (deleting all documents)."""
        service = ChromaDBService(test_config)
        await service.initialize()

        # Add some documents
        documents = [
            ("doc-1", "Content 1", sample_embedding, None),
            ("doc-2", "Content 2", sample_embedding, None),
        ]
        await service.add_documents_batch(documents)

        # Verify documents exist
        count_before = await service.get_document_count()
        assert count_before == 2

        # Reset collection
        result = await service.reset_collection()
        assert result is True

        # Verify collection is empty
        count_after = await service.get_document_count()
        assert count_after == 0

        # Cleanup
        await service.close()

    @pytest.mark.asyncio
    async def test_metadata_conversion(self, test_config):
        """Test metadata conversion between DocumentMetadata and ChromaDB format."""
        service = ChromaDBService(test_config)

        # Test prepare_metadata
        metadata = DocumentMetadata(
            document_id="test-doc",
            title="Test Document",
            source="test",
            tags=["tag1", "tag2"],
            user_id="user123",
        )

        chroma_metadata = service._prepare_metadata(metadata)

        assert chroma_metadata["title"] == "Test Document"
        assert chroma_metadata["source"] == "test"
        assert chroma_metadata["user_id"] == "user123"
        assert json.loads(chroma_metadata["tags"]) == ["tag1", "tag2"]

        # Test parse_metadata
        parsed_metadata = service._parse_metadata(chroma_metadata)

        assert parsed_metadata.title == "Test Document"
        assert parsed_metadata.source == "test"
        assert parsed_metadata.user_id == "user123"
        assert parsed_metadata.tags == ["tag1", "tag2"]

    @pytest.mark.asyncio
    async def test_metadata_conversion_none(self, test_config):
        """Test metadata conversion with None input."""
        service = ChromaDBService(test_config)

        # Test prepare_metadata with None
        result = service._prepare_metadata(None)
        assert result == {"_default": "true"}

        # Test parse_metadata with empty dict
        result = service._parse_metadata({})
        assert result.document_id == ""
        assert result.title is None
        assert result.tags is None

    @pytest.mark.asyncio
    async def test_metadata_tags_json_error(self, test_config):
        """Test metadata parsing with invalid JSON in tags."""
        service = ChromaDBService(test_config)

        # Test parse_metadata with invalid JSON tags
        invalid_metadata = {"tags": "invalid-json{"}
        result = service._parse_metadata(invalid_metadata)

        assert result.tags is None

    def test_service_close(self, test_config):
        """Test service cleanup."""
        service = ChromaDBService(test_config)

        # Test close before initialization
        asyncio.run(service.close())

        assert service.client is None
        assert service.collection is None
        assert not service._initialized

    @pytest.mark.asyncio
    async def test_operations_before_initialization_fail(self, test_config, sample_embedding):
        """Test that operations before initialization properly initialize the service."""
        service = ChromaDBService(test_config)

        # Should automatically initialize
        result = await service.add_document(
            document_id="test-doc",
            content="Test content",
            embedding=sample_embedding,
            metadata=None,
        )

        assert result is True
        assert service._initialized

        # Cleanup
        await service.close()


class TestChromaDBServiceErrors:
    """Test error conditions for ChromaDBService."""

    @pytest.mark.asyncio
    async def test_initialization_error_handling(self, test_config):
        """Test error handling during initialization."""
        # Mock the ChromaDB client creation to fail
        service = ChromaDBService(test_config)

        with patch.object(service, "_init_client", side_effect=Exception("Mock ChromaDB error")):
            with pytest.raises(ChromaDBConnectionError):
                await service.initialize()

    @pytest.mark.asyncio
    async def test_search_results_processing_empty(self, test_config):
        """Test processing empty search results."""
        service = ChromaDBService(test_config)

        # Test with empty results
        results = service._process_search_results({})
        assert results == []

        # Test with None results
        results = service._process_search_results(None)
        assert results == []

    @pytest.mark.asyncio
    async def test_search_results_processing_partial_data(self, test_config):
        """Test processing search results with missing data."""
        service = ChromaDBService(test_config)

        # Simulate partial results from ChromaDB
        partial_results = {
            "ids": [["doc-1", "doc-2"]],
            "documents": [["Content 1"]],  # Missing second document
            "metadatas": [[]],  # Empty metadata
            "distances": [[0.1]],  # Missing second distance
        }

        results = service._process_search_results(partial_results)

        assert len(results) == 2
        assert results[0].content == "Content 1"
        assert results[1].content == ""  # Missing content should be empty string
        assert results[0].score > 0  # Distance converted to score
        assert results[1].score == 0.0  # Missing distance should default to 0 score
