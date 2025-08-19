"""
Test cases for PersistentQueue service.

Tests cover SQLite queue operations, recovery functionality,
and batch processing with proper cleanup.
"""

import asyncio
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import aiosqlite
import pytest

from src.nescordbot.services.database import DatabaseService
from src.nescordbot.services.persistent_queue import FileRequest, PersistentQueue


@pytest.fixture
async def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        db_service = DatabaseService(db_path)
        await db_service.initialize()
        yield db_service
    finally:
        await db_service.close()
        Path(db_path).unlink(missing_ok=True)


@pytest.fixture
async def queue_service(temp_db):
    """Create a PersistentQueue instance for testing."""
    # Mock config object
    config = type(
        "Config",
        (),
        {
            "obsidian_batch_size": 5,
            "obsidian_batch_timeout": 1.0,
            "obsidian_max_queue_size": 100,
            "obsidian_max_retry_count": 3,
        },
    )()

    queue = PersistentQueue(temp_db, config)
    await queue.initialize()

    try:
        yield queue
    finally:
        await queue.cleanup()


@pytest.fixture
def sample_file_request():
    """Create a sample FileRequest for testing."""
    return FileRequest(
        filename="test.md",
        content="# Test Content\n\nThis is a test file.",
        directory="notes",
        metadata={"tags": ["test"], "author": "pytest"},
        created_at=datetime.now(),
        priority=1,
    )


class TestFileRequest:
    """Test FileRequest data class."""

    def test_to_dict_conversion(self, sample_file_request):
        """Test converting FileRequest to dictionary."""
        data = sample_file_request.to_dict()

        assert data["filename"] == "test.md"
        assert data["content"] == "# Test Content\n\nThis is a test file."
        assert data["directory"] == "notes"
        assert data["metadata"] == {"tags": ["test"], "author": "pytest"}
        assert data["priority"] == 1
        assert isinstance(data["created_at"], str)

    def test_from_dict_conversion(self, sample_file_request):
        """Test creating FileRequest from dictionary."""
        data = sample_file_request.to_dict()
        restored = FileRequest.from_dict(data)

        assert restored.filename == sample_file_request.filename
        assert restored.content == sample_file_request.content
        assert restored.directory == sample_file_request.directory
        assert restored.metadata == sample_file_request.metadata
        assert restored.priority == sample_file_request.priority
        assert restored.created_at == sample_file_request.created_at


class TestPersistentQueue:
    """Test PersistentQueue functionality."""

    @pytest.mark.asyncio
    async def test_queue_initialization(self, queue_service):
        """Test that queue tables are created properly."""
        async with queue_service.db_service.get_connection() as conn:
            # Check main queue table
            cursor = await conn.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='obsidian_file_queue'
            """
            )
            assert await cursor.fetchone() is not None

            # Check dead letter queue table
            cursor = await conn.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='obsidian_dead_letter_queue'
            """
            )
            assert await cursor.fetchone() is not None

            # Check index
            cursor = await conn.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='index' AND name='idx_queue_processing'
            """
            )
            assert await cursor.fetchone() is not None

    @pytest.mark.asyncio
    async def test_enqueue_file_request(self, queue_service, sample_file_request):
        """Test adding file request to queue."""
        queue_id = await queue_service.enqueue(sample_file_request)

        assert isinstance(queue_id, int)
        assert queue_id > 0

        # Verify in database
        async with queue_service.db_service.get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT id, status, priority FROM obsidian_file_queue WHERE id = ?
            """,
                (queue_id,),
            )

            result = await cursor.fetchone()
            assert result is not None
            assert result[0] == queue_id
            assert result[1] == "pending"
            assert result[2] == 1

    @pytest.mark.asyncio
    async def test_idempotency_key_duplicate_prevention(self, queue_service, sample_file_request):
        """Test that duplicate requests are handled properly."""
        idempotency_key = "test-unique-key"

        # First request
        queue_id1 = await queue_service.enqueue(sample_file_request, idempotency_key)

        # Duplicate request
        queue_id2 = await queue_service.enqueue(sample_file_request, idempotency_key)

        # Should return the same ID
        assert queue_id1 == queue_id2

        # Verify only one record exists
        async with queue_service.db_service.get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT COUNT(*) FROM obsidian_file_queue WHERE idempotency_key = ?
            """,
                (idempotency_key,),
            )

            count = (await cursor.fetchone())[0]
            assert count == 1

    @pytest.mark.asyncio
    async def test_queue_status_reporting(self, queue_service, sample_file_request):
        """Test queue status reporting functionality."""
        # Initially empty
        status = await queue_service.get_queue_status()
        assert status["pending"] == 0
        assert status["processing"] == 0
        assert status["completed"] == 0
        assert status["failed"] == 0
        assert status["dead_letter"] == 0

        # Add a few items
        for i in range(3):
            request = FileRequest(
                filename=f"test{i}.md",
                content=f"Content {i}",
                directory="notes",
                metadata={},
                created_at=datetime.now(),
                priority=0,
            )
            await queue_service.enqueue(request)

        status = await queue_service.get_queue_status()
        assert status["pending"] == 3

    @pytest.mark.asyncio
    async def test_recovery_pending_tasks(self, temp_db):
        """Test recovery of pending tasks after restart."""
        # Create initial queue with some items
        config = type(
            "Config",
            (),
            {
                "obsidian_batch_size": 5,
                "obsidian_batch_timeout": 1.0,
                "obsidian_max_queue_size": 100,
                "obsidian_max_retry_count": 3,
            },
        )()

        queue1 = PersistentQueue(temp_db, config)
        await queue1.initialize()

        # Add some items
        for i in range(3):
            request = FileRequest(
                filename=f"test{i}.md",
                content=f"Content {i}",
                directory="notes",
                metadata={},
                created_at=datetime.now(),
                priority=i,
            )
            await queue1.enqueue(request)

        await queue1.cleanup()

        # Create new queue instance (simulates restart)
        queue2 = PersistentQueue(temp_db, config)
        await queue2.initialize()

        # Check that items were recovered to memory queue
        assert queue2._memory_queue.qsize() == 3

        await queue2.cleanup()

    @pytest.mark.asyncio
    async def test_processing_task_recovery(self, temp_db):
        """Test recovery of stuck processing tasks."""
        config = type("Config", (), {"obsidian_max_queue_size": 100})()

        # Initialize queue first to create tables
        queue = PersistentQueue(temp_db, config)
        await queue.initialize()

        # Manually insert a processing task that's old
        async with temp_db.get_connection() as conn:
            # Use SQLite datetime format that's compatible with datetime('now') comparison
            await conn.execute(
                """
                INSERT INTO obsidian_file_queue
                (status, updated_at, file_request_json, priority)
                VALUES ('processing', datetime('now', '-10 minutes'),
                        '{"filename": "test.md", "content": "test", "directory": "notes", '
                        '"metadata": {}, "created_at": "2024-01-01T00:00:00", "priority": 0}',
                        0)
            """
            )
            await conn.commit()

        await queue.cleanup()

        # Create new queue instance (simulates restart)
        queue2 = PersistentQueue(temp_db, config)
        await queue2.initialize()

        # Verify task was moved back to pending
        async with temp_db.get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT status, COUNT(*) FROM obsidian_file_queue WHERE status = 'pending'
            """
            )
            result = await cursor.fetchone()
            assert result is not None
            assert result[1] > 0  # Count should be greater than 0

        await queue2.cleanup()

    @pytest.mark.asyncio
    async def test_batch_processing_simulation(self, queue_service, sample_file_request):
        """Test the batch processing mechanism."""
        # Override _process_batch to track calls
        processed_batches = []

        async def mock_process_batch(file_requests, batch_id):
            processed_batches.append((len(file_requests), batch_id))
            return True

        queue_service._process_batch = mock_process_batch

        # Add multiple items
        for i in range(7):  # More than batch_size (5)
            request = FileRequest(
                filename=f"test{i}.md",
                content=f"Content {i}",
                directory="notes",
                metadata={},
                created_at=datetime.now(),
                priority=0,
            )
            await queue_service.enqueue(request)

        # Start processing
        await queue_service.start_processing()

        # Wait for processing to complete
        await asyncio.sleep(0.5)

        # Stop processing
        await queue_service.stop_processing()

        # Verify batches were processed
        assert len(processed_batches) >= 1
        total_processed = sum(batch[0] for batch in processed_batches)
        assert total_processed == 7

    @pytest.mark.asyncio
    async def test_dead_letter_queue_movement(self, queue_service, sample_file_request):
        """Test movement of failed items to dead letter queue."""
        queue_id = await queue_service.enqueue(sample_file_request)

        # Simulate multiple failures
        for _ in range(4):  # Exceeds max_retry_count (3)
            await queue_service._handle_batch_failure([str(queue_id)], "Test error")

        # Check that item was moved to DLQ
        status = await queue_service.get_queue_status()
        assert status["dead_letter"] == 1
        assert status["pending"] == 0  # Should be removed from main queue

    @pytest.mark.asyncio
    async def test_queue_cleanup(self, queue_service, sample_file_request):
        """Test proper cleanup of queue resources."""
        # Add some items and start processing
        await queue_service.enqueue(sample_file_request)
        await queue_service.start_processing()

        # Cleanup should stop processing gracefully
        await queue_service.cleanup()

        # Verify processing stopped
        assert queue_service._processing_task is None

    @pytest.mark.asyncio
    async def test_memory_queue_full_handling(self, temp_db, sample_file_request):
        """Test handling when memory queue is full."""
        config = type(
            "Config",
            (),
            {
                "obsidian_batch_size": 5,
                "obsidian_batch_timeout": 1.0,
                "obsidian_max_queue_size": 2,  # Very small queue
                "obsidian_max_retry_count": 3,
            },
        )()

        queue = PersistentQueue(temp_db, config)
        await queue.initialize()

        try:
            # Add more items than memory queue can hold
            queue_ids = []
            for i in range(5):
                request = FileRequest(
                    filename=f"test{i}.md",
                    content=f"Content {i}",
                    directory="notes",
                    metadata={},
                    created_at=datetime.now(),
                    priority=0,
                )
                queue_id = await queue.enqueue(request)
                queue_ids.append(queue_id)

            # All should be stored in database
            async with temp_db.get_connection() as conn:
                cursor = await conn.execute(
                    """
                    SELECT COUNT(*) FROM obsidian_file_queue WHERE status = 'pending'
                """
                )
                count = (await cursor.fetchone())[0]
                assert count == 5

            # But memory queue should be limited
            assert queue._memory_queue.qsize() <= 2

        finally:
            await queue.cleanup()


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_malformed_json_recovery(self, temp_db):
        """Test handling of malformed JSON in queue items."""
        config = type("Config", (), {"obsidian_max_queue_size": 100})()

        # Initialize queue first to create tables
        queue = PersistentQueue(temp_db, config)
        await queue.initialize()

        # Manually insert malformed JSON
        async with temp_db.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO obsidian_file_queue
                (status, file_request_json, priority)
                VALUES ('pending', 'invalid json', 0)
            """
            )
            await conn.commit()

        try:
            # Load file requests should handle the error gracefully
            file_requests = await queue._load_file_requests(["1"])
            assert len(file_requests) == 0  # Malformed item should be skipped

            # Item should be marked as failed
            async with temp_db.get_connection() as conn:
                cursor = await conn.execute(
                    """
                    SELECT status FROM obsidian_file_queue WHERE id = 1
                """
                )
                result = await cursor.fetchone()
                assert result[0] == "failed"

        finally:
            await queue.cleanup()

    @pytest.mark.asyncio
    async def test_database_connection_error_handling(self, queue_service):
        """Test handling of database connection errors."""
        # Mock a database error
        with patch.object(queue_service.db_service, "get_connection") as mock_conn:
            mock_conn.side_effect = Exception("Database connection failed")

            # Should handle the error gracefully
            with pytest.raises(Exception, match="Database connection failed"):
                sample_request = FileRequest(
                    filename="test.md",
                    content="test",
                    directory="notes",
                    metadata={},
                    created_at=datetime.now(),
                    priority=0,
                )
                await queue_service.enqueue(sample_request)
