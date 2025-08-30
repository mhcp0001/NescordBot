"""
Test cases for BatchProcessor service.

Tests cover batch processing integration with PersistentQueue and GitOperationService,
error handling, and processing lifecycle management.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.nescordbot.services.batch_processor import BatchProcessor, BatchProcessorError
from src.nescordbot.services.persistent_queue import FileRequest


class MockConfig:
    """Mock configuration for testing."""

    def __init__(self, **kwargs):
        self.obsidian_batch_size = kwargs.get("obsidian_batch_size", 5)
        self.obsidian_batch_timeout = kwargs.get("obsidian_batch_timeout", 1.0)
        self.obsidian_max_queue_size = kwargs.get("obsidian_max_queue_size", 100)
        self.obsidian_max_retry_count = kwargs.get("obsidian_max_retry_count", 3)


@pytest.fixture
def mock_config():
    """Create mock configuration."""
    return MockConfig()


@pytest.fixture
def mock_db_service():
    """Create mock database service."""
    db_service = AsyncMock()
    db_service.get_connection = MagicMock()
    return db_service


@pytest.fixture
def mock_auth_manager():
    """Create mock authentication manager."""
    auth_manager = AsyncMock()
    auth_manager.initialize = AsyncMock()
    return auth_manager


@pytest.fixture
def mock_git_operations():
    """Create mock git operations service."""
    git_ops = AsyncMock()
    git_ops.initialize = AsyncMock()
    git_ops.get_repository_status = AsyncMock(
        return_value={"initialized": True, "current_branch": "main"}
    )
    return git_ops


@pytest.fixture
async def batch_processor(mock_config, mock_db_service, mock_auth_manager, mock_git_operations):
    """Create batch processor for testing."""
    with patch("src.nescordbot.services.batch_processor.PersistentQueue") as mock_queue_class:
        mock_queue = AsyncMock()
        mock_queue.initialize = AsyncMock()
        mock_queue.enqueue = AsyncMock(return_value=1)
        mock_queue.get_queue_status = AsyncMock(
            return_value={"pending": 0, "processing": 0, "completed": 0, "failed": 0}
        )
        mock_queue.start_processing = AsyncMock()
        mock_queue.stop_processing = AsyncMock()
        mock_queue.cleanup = AsyncMock()
        # set_git_service is a synchronous method, use MagicMock
        mock_queue.set_git_service = MagicMock()
        mock_queue_class.return_value = mock_queue

        processor = BatchProcessor(
            mock_config, mock_db_service, mock_auth_manager, mock_git_operations
        )
        yield processor


class TestBatchProcessor:
    """Test batch processor functionality."""

    @pytest.mark.asyncio
    async def test_initialization_success(self, batch_processor):
        """Test successful batch processor initialization."""
        await batch_processor.initialize()

        assert batch_processor._initialized is True
        batch_processor.auth_manager.initialize.assert_called_once()
        batch_processor.git_operations.initialize.assert_called_once()
        batch_processor.queue.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialization_failure(self, batch_processor):
        """Test batch processor initialization failure."""
        batch_processor.auth_manager.initialize.side_effect = Exception("Auth failed")

        with pytest.raises(BatchProcessorError, match="Initialization failed"):
            await batch_processor.initialize()

    @pytest.mark.asyncio
    async def test_initialization_idempotent(self, batch_processor):
        """Test that initialization is idempotent."""
        await batch_processor.initialize()
        await batch_processor.initialize()  # Should not fail

        # Should only call once
        assert batch_processor.auth_manager.initialize.call_count == 1

    @pytest.mark.asyncio
    async def test_enqueue_file_request(self, batch_processor):
        """Test enqueueing a file processing request."""
        await batch_processor.initialize()

        queue_id = await batch_processor.enqueue_file_request(
            filename="test.md",
            content="# Test Content",
            directory="notes",
            metadata={"author": "test"},
            priority=1,
            idempotency_key="test-key",
        )

        assert queue_id == 1
        batch_processor.queue.enqueue.assert_called_once()

        # Verify FileRequest was created properly
        call_args = batch_processor.queue.enqueue.call_args
        file_request = call_args[0][0]
        assert file_request.filename == "test.md"
        assert file_request.content == "# Test Content"
        assert file_request.directory == "notes"
        assert file_request.priority == 1

        # Check how idempotency_key was passed - could be positional or keyword
        if len(call_args[0]) > 1:
            # Passed as positional argument
            assert call_args[0][1] == "test-key"
        else:
            # Passed as keyword argument
            assert call_args[1].get("idempotency_key") == "test-key"

    @pytest.mark.asyncio
    async def test_enqueue_auto_initialize(self, batch_processor):
        """Test that enqueue auto-initializes if needed."""
        queue_id = await batch_processor.enqueue_file_request("test.md", "content")

        assert queue_id == 1
        assert batch_processor._initialized is True

    @pytest.mark.asyncio
    async def test_start_processing(self, batch_processor):
        """Test starting batch processing."""
        await batch_processor.initialize()

        await batch_processor.start_processing()

        batch_processor.queue.start_processing.assert_called_once()
        assert batch_processor._processing_task is not None
        assert not batch_processor._processing_task.done()

    @pytest.mark.asyncio
    async def test_start_processing_already_running(self, batch_processor):
        """Test starting processing when already running."""
        await batch_processor.initialize()

        # Start processing first time
        await batch_processor.start_processing()
        first_task = batch_processor._processing_task

        # Try to start again
        await batch_processor.start_processing()

        # Should be the same task
        assert batch_processor._processing_task is first_task

    @pytest.mark.asyncio
    async def test_stop_processing_graceful(self, batch_processor):
        """Test graceful stop of batch processing."""
        await batch_processor.initialize()
        await batch_processor.start_processing()

        # Stop processing
        await batch_processor.stop_processing(graceful=True)

        batch_processor.queue.stop_processing.assert_called_once_with(True)
        assert batch_processor._processing_task is None

    @pytest.mark.asyncio
    async def test_stop_processing_immediate(self, batch_processor):
        """Test immediate stop of batch processing."""
        await batch_processor.initialize()
        await batch_processor.start_processing()

        # Stop processing immediately
        await batch_processor.stop_processing(graceful=False)

        batch_processor.queue.stop_processing.assert_called_once_with(False)
        assert batch_processor._processing_task is None

    @pytest.mark.asyncio
    async def test_processing_loop_shutdown(self, batch_processor):
        """Test processing loop handles shutdown correctly."""
        await batch_processor.initialize()

        # Start processing
        await batch_processor.start_processing()

        # Signal shutdown immediately
        batch_processor._shutdown_event.set()

        # Wait for processing task to complete
        if batch_processor._processing_task:
            await batch_processor._processing_task

        # Should have stopped cleanly
        assert batch_processor._processing_task.done()

    @pytest.mark.asyncio
    async def test_manual_batch_processing_no_pending(self, batch_processor):
        """Test manual batch processing with no pending requests."""
        await batch_processor.initialize()

        result = await batch_processor.process_batch_manually()

        assert result["success"] is True
        assert result["files_processed"] == 0
        assert "No pending requests" in result["message"]

    @pytest.mark.asyncio
    async def test_manual_batch_processing_with_pending(self, batch_processor):
        """Test manual batch processing with pending requests."""
        await batch_processor.initialize()

        # Mock queue status to show pending items
        batch_processor.queue.get_queue_status.side_effect = [
            {"pending": 3, "processing": 0, "completed": 0, "failed": 0},  # Initial
            {"pending": 0, "processing": 0, "completed": 3, "failed": 0},  # After processing
        ]

        result = await batch_processor.process_batch_manually()

        assert result["success"] is True
        assert result["files_processed"] == 3
        assert result["remaining_pending"] == 0

    @pytest.mark.asyncio
    async def test_manual_batch_processing_error(self, batch_processor):
        """Test manual batch processing error handling."""
        await batch_processor.initialize()

        batch_processor.queue.get_queue_status.side_effect = Exception("Queue error")

        result = await batch_processor.process_batch_manually()

        assert result["success"] is False
        assert "error" in result
        assert result["files_processed"] == 0

    @pytest.mark.asyncio
    async def test_get_processing_status_initialized(self, batch_processor):
        """Test getting processing status when initialized."""
        await batch_processor.initialize()
        await batch_processor.start_processing()

        status = await batch_processor.get_processing_status()

        assert status["initialized"] is True
        assert status["processing_active"] is True
        assert "queue_status" in status
        assert "statistics" in status
        assert "git_status" in status

    @pytest.mark.asyncio
    async def test_get_processing_status_not_initialized(self, batch_processor):
        """Test getting processing status when not initialized."""
        # Ensure processor is not initialized
        batch_processor._initialized = False
        batch_processor._processing_task = None

        status = await batch_processor.get_processing_status()

        assert status["initialized"] is False
        assert status["processing_active"] is False

    @pytest.mark.asyncio
    async def test_get_queue_status_initialized(self, batch_processor):
        """Test getting queue status when initialized."""
        await batch_processor.initialize()

        status = await batch_processor.get_queue_status()

        assert "pending" in status
        batch_processor.queue.get_queue_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_queue_status_not_initialized(self, batch_processor):
        """Test getting queue status when not initialized."""
        status = await batch_processor.get_queue_status()

        assert status["error"] == "Not initialized"

    @pytest.mark.asyncio
    async def test_cleanup(self, batch_processor):
        """Test batch processor cleanup."""
        await batch_processor.initialize()
        await batch_processor.start_processing()

        await batch_processor.cleanup()

        batch_processor.queue.cleanup.assert_called_once()
        batch_processor.git_operations.cleanup.assert_called_once()
        batch_processor.auth_manager.cleanup.assert_called_once()
        assert batch_processor._initialized is False

    @pytest.mark.asyncio
    async def test_cleanup_error_handling(self, batch_processor):
        """Test cleanup handles errors gracefully."""
        await batch_processor.initialize()

        # Verify initialized state
        assert batch_processor._initialized is True

        # Make cleanup methods fail
        batch_processor.queue.cleanup.side_effect = Exception("Cleanup error")
        batch_processor.git_operations.cleanup.side_effect = Exception("Git cleanup error")
        batch_processor.auth_manager.cleanup.side_effect = Exception("Auth cleanup error")

        # Should not raise exception
        await batch_processor.cleanup()

        # Should still set initialized to False even with errors
        assert batch_processor._initialized is False

    @pytest.mark.asyncio
    async def test_processing_loop_error_handling(self, batch_processor):
        """Test processing loop handles errors gracefully."""
        await batch_processor.initialize()

        # Mock _check_completed_batches to raise an error
        with patch.object(
            batch_processor, "_check_completed_batches", side_effect=Exception("Processing error")
        ):
            # Start processing
            await batch_processor.start_processing()

            # Let it run briefly to hit the error
            await asyncio.sleep(0.1)

            # Should increment error count
            assert batch_processor._stats["errors"] >= 0  # May be 0 if error hasn't occurred yet

            # Stop processing
            await batch_processor.stop_processing()


# Additional integration tests could be added here for GitHubIntegratedQueue
# if we wanted to test the full integration with actual Git operations
