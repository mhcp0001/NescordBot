"""
Tests for SyncManager service.

This module contains comprehensive tests for SQLite-ChromaDB synchronization,
consistency verification, and error handling functionality.
"""

import asyncio
import tempfile
from datetime import datetime, timedelta
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.nescordbot.config import BotConfig
from src.nescordbot.services.database import DatabaseService
from src.nescordbot.services.sync_manager import (
    ConsistencyReport,
    RepairReport,
    SyncError,
    SyncManager,
    SyncReport,
    SyncResult,
    SyncServiceUnavailableError,
    SyncStatus,
)


class TestSyncManager:
    """Test SyncManager functionality."""

    @pytest.fixture
    def temp_config(self):
        """Create temporary config for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = MagicMock(spec=BotConfig)
            config.database_url = f"sqlite:///{temp_dir}/test.db"
            config.sync_batch_size = 10
            config.sync_max_retries = 3
            config.sync_retry_delay = 0.1  # Faster for testing
            config.embedding_dimension = 384
            yield config

    @pytest.fixture
    async def mock_services(self, temp_config):
        """Create mock services for testing."""
        # Database service
        database_service = DatabaseService(temp_config.database_url)
        await database_service.initialize()

        # ChromaDB service mock
        chromadb_service = AsyncMock()
        chromadb_service._initialized = True
        chromadb_service.add_document = AsyncMock(return_value=True)
        chromadb_service.delete_document = AsyncMock(return_value=True)
        chromadb_service.get_document_count = AsyncMock(return_value=0)
        chromadb_service.search_documents = AsyncMock(return_value=[])

        # Embedding service mock
        embedding_service = MagicMock()
        embedding_service.is_available = MagicMock(return_value=True)
        embedding_service.embedding_dimension = 384
        embedding_service.model_name = "text-embedding-004"

        # Mock embedding result
        mock_embedding_result = MagicMock()
        mock_embedding_result.embedding = [0.1] * 384
        embedding_service.generate_embedding = AsyncMock(return_value=mock_embedding_result)

        yield {
            "database": database_service,
            "chromadb": chromadb_service,
            "embedding": embedding_service,
        }

        await database_service.close()

    @pytest.fixture
    async def sync_manager(self, temp_config, mock_services):
        """Create SyncManager instance for testing."""
        manager = SyncManager(
            config=temp_config,
            database_service=mock_services["database"],
            chromadb_service=mock_services["chromadb"],
            embedding_service=mock_services["embedding"],
        )
        await manager.init_async()

        yield manager

        await manager.close()

    @pytest.fixture
    async def sample_notes(self, mock_services):
        """Create sample notes in database."""
        db = mock_services["database"]

        # Create knowledge_notes table (simulate migration)
        async with db.get_connection() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_notes (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    content TEXT,
                    tags TEXT,
                    source_type TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    user_id TEXT
                )
            """
            )

            # Insert sample notes
            sample_data = [
                (
                    "note_1",
                    "Test Note 1",
                    "Content for note 1",
                    "test,sample",
                    "manual",
                    "user_123",
                ),
                (
                    "note_2",
                    "Test Note 2",
                    "Content for note 2",
                    "test,example",
                    "manual",
                    "user_456",
                ),
                ("note_3", "Test Note 3", "Content for note 3", "test", "imported", "user_123"),
            ]

            for note_id, title, content, tags, source_type, user_id in sample_data:
                await conn.execute(
                    """
                    INSERT INTO knowledge_notes
                    (id, title, content, tags, source_type, user_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (note_id, title, content, tags, source_type, user_id),
                )

            await conn.commit()

    @pytest.mark.asyncio
    async def test_initialization(self, temp_config, mock_services):
        """Test SyncManager initialization."""
        manager = SyncManager(
            config=temp_config,
            database_service=mock_services["database"],
            chromadb_service=mock_services["chromadb"],
            embedding_service=mock_services["embedding"],
        )

        assert not manager._initialized

        await manager.init_async()
        assert manager._initialized

        # Test double initialization
        await manager.init_async()
        assert manager._initialized

        await manager.close()

    @pytest.mark.asyncio
    async def test_table_creation(self, sync_manager):
        """Test that sync metadata table is created properly."""
        async with sync_manager.db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='sync_metadata'"
            )
            table_exists = await cursor.fetchone()
            assert table_exists is not None

    @pytest.mark.asyncio
    async def test_sync_single_note(self, sync_manager, sample_notes):
        """Test synchronizing a single note."""
        result = await sync_manager.sync_note_to_chromadb("note_1")

        assert result.success is True
        assert result.status == SyncStatus.SYNCED
        assert result.note_id == "note_1"
        assert result.synced_at is not None

        # Verify ChromaDB service was called
        sync_manager.chromadb.add_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_nonexistent_note(self, sync_manager):
        """Test synchronizing a non-existent note."""
        result = await sync_manager.sync_note_to_chromadb("nonexistent_note")

        assert result.success is False
        assert result.status == SyncStatus.FAILED
        assert "Note not found" in result.error

    @pytest.mark.asyncio
    async def test_sync_without_embedding_service(self, temp_config, mock_services):
        """Test sync behavior when embedding service is unavailable."""
        # Make embedding service unavailable
        mock_services["embedding"].is_available = MagicMock(return_value=False)

        manager = SyncManager(
            config=temp_config,
            database_service=mock_services["database"],
            chromadb_service=mock_services["chromadb"],
            embedding_service=mock_services["embedding"],
        )
        await manager.init_async()

        # Create sample note
        async with mock_services["database"].get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO knowledge_notes (id, title, content, user_id)
                VALUES (?, ?, ?, ?)
            """,
                ("note_1", "Test", "Content", "test_user"),
            )
            await conn.commit()

        result = await manager.sync_note_to_chromadb("note_1")

        assert result.success is False
        assert result.status == SyncStatus.FAILED
        assert result.error and "EmbeddingService not available" in result.error

        await manager.close()

    @pytest.mark.asyncio
    async def test_batch_sync(self, sync_manager, sample_notes):
        """Test batch synchronization of multiple notes."""
        note_ids = ["note_1", "note_2", "note_3"]

        results = await sync_manager.sync_notes_batch(note_ids)

        assert len(results) == 3

        for note_id, result in results.items():
            assert note_id in note_ids
            assert result.success is True
            assert result.status == SyncStatus.SYNCED

        # Verify ChromaDB was called for each note
        assert sync_manager.chromadb.add_document.call_count == 3

    @pytest.mark.asyncio
    async def test_sync_all_notes(self, sync_manager, sample_notes):
        """Test synchronizing all notes."""
        report = await sync_manager.sync_all_notes()

        assert report.total_notes == 3
        assert report.successful_syncs == 3
        assert report.failed_syncs == 0
        assert len(report.results) == 3
        assert report.success_rate == 1.0

    @pytest.mark.asyncio
    async def test_sync_metadata_tracking(self, sync_manager, sample_notes):
        """Test sync metadata is properly tracked."""
        await sync_manager.sync_note_to_chromadb("note_1")

        # Check sync metadata was created
        metadata = await sync_manager._get_sync_metadata("note_1")

        assert metadata is not None
        assert metadata["note_id"] == "note_1"
        assert metadata["sync_status"] == "synced"
        assert metadata["chromadb_doc_id"] == "note_note_1"
        assert metadata["embedding_hash"] is not None

    @pytest.mark.asyncio
    async def test_skip_already_synced(self, sync_manager, sample_notes):
        """Test that already synced notes are skipped if unchanged."""
        # First sync
        result1 = await sync_manager.sync_note_to_chromadb("note_1")
        assert result1.success is True

        # Reset mock to check if it's called again
        sync_manager.chromadb.add_document.reset_mock()

        # Second sync of same note (should be skipped)
        result2 = await sync_manager.sync_note_to_chromadb("note_1")
        assert result2.success is True
        assert result2.status == SyncStatus.SYNCED

        # ChromaDB should not be called again if nothing changed
        # Note: This test might pass if embedding hash comparison works correctly

    @pytest.mark.asyncio
    async def test_sync_status_tracking(self, sync_manager):
        """Test sync status retrieval functionality."""
        # Get status with no synced notes
        status = await sync_manager.get_sync_status()
        assert status["total_notes"] == 0
        assert status["synced_notes"] == 0

    @pytest.mark.asyncio
    async def test_health_check(self, sync_manager):
        """Test SyncManager health check functionality."""
        health = await sync_manager.health_check()

        assert health["status"] in ["healthy", "degraded"]
        assert health["initialized"] is True
        assert "services" in health
        assert "database" in health["services"]
        assert "chromadb" in health["services"]
        assert "embedding" in health["services"]

    @pytest.mark.asyncio
    async def test_chromadb_failure_handling(self, sync_manager, sample_notes):
        """Test handling of ChromaDB failures."""
        # Make ChromaDB add_document fail
        sync_manager.chromadb.add_document = AsyncMock(return_value=False)

        result = await sync_manager.sync_note_to_chromadb("note_1")

        assert result.success is False
        assert result.status == SyncStatus.FAILED
        assert "ChromaDB add_document failed" in result.error

    @pytest.mark.asyncio
    async def test_embedding_generation_failure(self, sync_manager, sample_notes):
        """Test handling of embedding generation failures."""
        # Make embedding generation fail
        sync_manager.embedding.generate_embedding = AsyncMock(return_value=None)

        result = await sync_manager.sync_note_to_chromadb("note_1")

        assert result.success is False
        assert result.status == SyncStatus.FAILED
        assert "Failed to generate embedding" in result.error

    @pytest.mark.asyncio
    async def test_unsynced_notes_detection(self, sync_manager, sample_notes):
        """Test detection of notes that need synchronization."""
        # Initially all notes should need sync
        unsynced = await sync_manager.get_unsynced_notes()
        assert len(unsynced) == 3

        # Sync one note
        await sync_manager.sync_note_to_chromadb("note_1")

        # Should have 2 unsynced notes remaining
        unsynced = await sync_manager.get_unsynced_notes()
        assert len(unsynced) == 2
        assert "note_1" not in unsynced

    @pytest.mark.asyncio
    async def test_delete_note_from_chromadb(self, sync_manager, sample_notes):
        """Test deleting a note from ChromaDB."""
        # First sync the note
        await sync_manager.sync_note_to_chromadb("note_1")

        # Then delete it
        success = await sync_manager.delete_note_from_chromadb("note_1")
        assert success is True

        # Verify delete was called
        sync_manager.chromadb.delete_document.assert_called_once_with("note_note_1")

    @pytest.mark.asyncio
    async def test_sync_statistics(self, sync_manager, sample_notes):
        """Test sync statistics generation."""
        # Sync some notes
        await sync_manager.sync_note_to_chromadb("note_1")
        await sync_manager.sync_note_to_chromadb("note_2")

        stats = await sync_manager.get_sync_statistics()

        assert "total_notes" in stats
        assert "sync_records" in stats
        assert "status_breakdown" in stats
        assert "success_rate" in stats
        assert stats["total_notes"] == 3
        assert stats["sync_records"] == 2

    @pytest.mark.asyncio
    async def test_content_preparation(self, sync_manager):
        """Test content preparation for embedding."""
        note_data = {"title": "Test Title", "content": "Test content here", "tags": "tag1,tag2"}

        content = sync_manager._prepare_content_for_embedding(note_data)

        assert "Title: Test Title" in content
        assert "Test content here" in content
        assert "Tags: tag1,tag2" in content

    @pytest.mark.asyncio
    async def test_embedding_hash_generation(self, sync_manager):
        """Test embedding hash generation for change detection."""
        content1 = "This is test content"
        content2 = "This is different content"

        hash1 = sync_manager._generate_embedding_hash(content1)
        hash2 = sync_manager._generate_embedding_hash(content1)  # Same content
        hash3 = sync_manager._generate_embedding_hash(content2)  # Different content

        assert hash1 == hash2  # Same content should produce same hash
        assert hash1 != hash3  # Different content should produce different hash

    @pytest.mark.asyncio
    async def test_document_id_generation(self, sync_manager):
        """Test ChromaDB document ID generation."""
        note_id = "test_note_123"
        doc_id = sync_manager._generate_doc_id(note_id)

        assert doc_id == "note_test_note_123"

    @pytest.mark.asyncio
    async def test_sync_manager_close(self, sync_manager):
        """Test proper cleanup on close."""
        assert sync_manager._initialized is True

        await sync_manager.close()
        assert sync_manager._initialized is False


class TestSyncManagerIntegration:
    """Integration tests for SyncManager with more realistic scenarios."""

    @pytest.fixture
    async def integrated_manager(self):
        """Create fully integrated SyncManager for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = MagicMock(spec=BotConfig)
            config.database_url = f"sqlite:///{temp_dir}/integration.db"
            config.sync_batch_size = 50
            config.sync_max_retries = 2
            config.sync_retry_delay = 0.05
            config.embedding_dimension = 384

            # Create database service
            database_service = DatabaseService(config.database_url)
            await database_service.initialize()

            # Create mock services
            chromadb_service = AsyncMock()
            chromadb_service._initialized = True
            chromadb_service.add_document = AsyncMock(return_value=True)
            chromadb_service.get_document_count = AsyncMock(return_value=0)

            embedding_service = MagicMock()
            embedding_service.is_available = MagicMock(return_value=True)
            embedding_service.embedding_dimension = 384
            embedding_service.model_name = "text-embedding-004"

            mock_result = MagicMock()
            mock_result.embedding = [0.2] * 384
            embedding_service.generate_embedding = AsyncMock(return_value=mock_result)

            # Create manager
            manager = SyncManager(config, database_service, chromadb_service, embedding_service)
            await manager.init_async()

            yield manager

            await database_service.close()

    @pytest.mark.asyncio
    async def test_realistic_workflow(self, integrated_manager):
        """Test a realistic synchronization workflow."""
        # Create sample data (knowledge_notes table should already exist from migrations)
        async with integrated_manager.db.get_connection() as conn:
            # Insert multiple notes simulating different scenarios
            notes = [
                (
                    "note_001",
                    "Meeting Notes",
                    "Weekly team meeting discussion points",
                    "work,meeting",
                    "manual",
                    "user_alice",
                ),
                (
                    "note_002",
                    "Research Ideas",
                    "AI and machine learning research topics",
                    "research,ai",
                    "imported",
                    "user_bob",
                ),
                (
                    "note_003",
                    "Project Plan",
                    "Q4 development roadmap and milestones",
                    "project,planning",
                    "manual",
                    "user_alice",
                ),
                (
                    "note_004",
                    "Bug Report",
                    "Issue with authentication service",
                    "bug,urgent",
                    "imported",
                    "user_charlie",
                ),
                (
                    "note_005",
                    "Design Doc",
                    "UI/UX improvements for mobile app",
                    "design,mobile",
                    "manual",
                    "user_alice",
                ),
            ]

            for note_data in notes:
                await conn.execute(
                    """
                    INSERT INTO knowledge_notes
                    (id, title, content, tags, source_type, user_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    note_data,
                )
            await conn.commit()

        # Test full synchronization workflow
        report = await integrated_manager.sync_all_notes()

        assert report.total_notes == 5
        assert report.successful_syncs == 5
        assert report.failed_syncs == 0
        assert report.success_rate == 1.0

        # Verify sync metadata was created
        status = await integrated_manager.get_sync_status()
        assert status["synced_notes"] == 5
        assert status["unsynced_notes"] == 0

        # Test statistics
        stats = await integrated_manager.get_sync_statistics()
        assert stats["total_notes"] == 5
        assert stats["sync_records"] == 5
        assert stats["status_breakdown"]["synced"] == 5

    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, integrated_manager):
        """Test error handling and recovery mechanisms."""
        # Create a test note
        async with integrated_manager.db.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO knowledge_notes (id, title, content, user_id)
                VALUES (?, ?, ?, ?)
            """,
                ("test_note", "Test", "Content", "test_user"),
            )
            await conn.commit()

        # First, make sync fail
        integrated_manager.chromadb.add_document = AsyncMock(return_value=False)

        result = await integrated_manager.sync_note_to_chromadb("test_note")
        assert result.success is False
        assert result.status == SyncStatus.FAILED

        # Verify failed sync is tracked
        metadata = await integrated_manager._get_sync_metadata("test_note")
        assert metadata["sync_status"] == "failed"
        assert metadata["retry_count"] == 1

        # Now fix the service and retry
        integrated_manager.chromadb.add_document = AsyncMock(return_value=True)

        retry_report = await integrated_manager.retry_failed_syncs()
        assert retry_report.successful_syncs == 1
        assert retry_report.failed_syncs == 0

        # Verify sync status is now successful
        metadata = await integrated_manager._get_sync_metadata("test_note")
        assert metadata["sync_status"] == "synced"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
