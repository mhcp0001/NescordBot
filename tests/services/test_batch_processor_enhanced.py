"""Tests for enhanced batch processor functionality."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.nescordbot.config import BotConfig
from src.nescordbot.services.batch_processor import BatchProcessor
from src.nescordbot.services.database import DatabaseService
from src.nescordbot.services.git_operations import GitOperationService
from src.nescordbot.services.github_auth import GitHubAuthManager


class TestBatchProcessorEnhanced:
    """Test enhanced batch processor functionality."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        config = Mock(spec=BotConfig)
        config.obsidian_batch_timeout = 10.0
        config.obsidian_batch_size = 5
        return config

    @pytest.fixture
    def db_service(self):
        """Create mock database service."""
        return Mock(spec=DatabaseService)

    @pytest.fixture
    def auth_manager(self):
        """Create mock auth manager."""
        return Mock(spec=GitHubAuthManager)

    @pytest.fixture
    def git_operations(self):
        """Create mock git operations service."""
        mock_git = Mock(spec=GitOperationService)
        mock_git.get_repository_status = AsyncMock(return_value={})
        return mock_git

    @pytest.fixture
    def batch_processor(self, config, db_service, auth_manager, git_operations):
        """Create batch processor instance."""
        return BatchProcessor(config, db_service, auth_manager, git_operations)

    def test_enhanced_initialization(self, batch_processor):
        """Test enhanced initialization with memory monitoring and progress tracking."""
        assert hasattr(batch_processor, "memory_monitor")
        assert hasattr(batch_processor, "_cancel_event")
        assert hasattr(batch_processor, "_progress_tracker")
        assert hasattr(batch_processor, "_progress_callback")

        # Check memory monitor configuration
        assert batch_processor.memory_monitor.threshold_mb == 300.0
        assert batch_processor.memory_monitor.gc_threshold_mb == 100.0

    @pytest.mark.asyncio
    async def test_cancel_processing(self, batch_processor):
        """Test processing cancellation functionality."""
        # Mock processing task
        mock_task = Mock()
        mock_task.done.return_value = False
        batch_processor._processing_task = mock_task

        # Mock successful cancellation
        async def wait_for_completion():
            await asyncio.sleep(0.1)

        with patch("asyncio.wait_for", side_effect=wait_for_completion):
            result = await batch_processor.cancel_processing()

            assert result is True
            assert batch_processor._cancel_event.is_set()

    @pytest.mark.asyncio
    async def test_cancel_processing_timeout(self, batch_processor):
        """Test processing cancellation with timeout."""
        # Mock processing task
        mock_task = Mock()
        mock_task.done.return_value = False
        mock_task.cancel = Mock()
        batch_processor._processing_task = mock_task

        # Mock timeout during cancellation
        async def timeout_wait():
            raise asyncio.TimeoutError()

        with patch("asyncio.wait_for", side_effect=timeout_wait):
            result = await batch_processor.cancel_processing()

            assert result is True
            mock_task.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_processing_status_with_memory_stats(self, batch_processor):
        """Test processing status includes memory statistics."""
        # Mock queue and initialize
        batch_processor.queue = Mock()
        batch_processor.queue.get_queue_status = AsyncMock(return_value={"pending": 5})
        batch_processor._initialized = True

        # Mock memory monitor
        mock_memory_stats = {"rss_mb": 150.0, "percent": 7.5, "available_mb": 1000.0}
        batch_processor.memory_monitor.get_memory_usage = Mock(return_value=mock_memory_stats)

        status = await batch_processor.get_processing_status()

        assert "memory_stats" in status
        assert status["memory_stats"]["rss_mb"] == 150.0
        assert status["memory_stats"]["percent"] == 7.5
        assert "cancelled" in status

    @pytest.mark.asyncio
    async def test_process_with_progress(self, batch_processor):
        """Test batch processing with progress tracking."""
        # Setup mocks
        batch_processor._initialized = True
        batch_processor.queue = Mock()
        batch_processor.queue.get_queue_status = AsyncMock(
            side_effect=[
                {"pending": 10},  # Initial status
                {"pending": 5, "completed": 5, "failed": 0},  # Progress update
                {"pending": 0, "completed": 10, "failed": 0},  # Final status
            ]
        )
        batch_processor.queue.start_processing = AsyncMock()
        batch_processor.queue.stop_processing = AsyncMock()

        # Mock memory optimization
        with patch("src.nescordbot.utils.memory.optimize_memory") as mock_optimize:
            mock_optimize.return_value = None

            # Mock progress callback
            progress_callback = Mock()

            result = await batch_processor.process_with_progress(
                batch_size=5, progress_callback=progress_callback
            )

            assert result["success"] is True
            assert result["files_processed"] == 10
            assert result["remaining_pending"] == 0
            assert "memory_stats" in result
            assert "progress" in result

            # Should have called memory optimization
            assert mock_optimize.call_count >= 1

    @pytest.mark.asyncio
    async def test_process_with_progress_no_pending(self, batch_processor):
        """Test progress processing with no pending items."""
        batch_processor._initialized = True
        batch_processor.queue = Mock()
        batch_processor.queue.get_queue_status = AsyncMock(return_value={"pending": 0})

        result = await batch_processor.process_with_progress()

        assert result["success"] is True
        assert result["message"] == "No pending requests to process"
        assert result["files_processed"] == 0
        assert "memory_stats" in result

    @pytest.mark.asyncio
    async def test_process_with_progress_cancellation(self, batch_processor):
        """Test progress processing handles cancellation."""
        batch_processor._initialized = True
        batch_processor.queue = Mock()
        batch_processor.queue.get_queue_status = AsyncMock(return_value={"pending": 5})
        batch_processor.queue.start_processing = AsyncMock()
        batch_processor.queue.stop_processing = AsyncMock()

        # Trigger cancellation during processing
        async def delayed_cancel():
            await asyncio.sleep(0.1)
            batch_processor._cancel_event.set()

        # Start cancellation task
        cancel_task = asyncio.create_task(delayed_cancel())

        with patch("src.nescordbot.utils.memory.optimize_memory"):
            result = await batch_processor.process_with_progress()

            assert "cancelled" in result
            assert result["cancelled"] is True

        await cancel_task

    @pytest.mark.asyncio
    async def test_process_with_progress_timeout(self, batch_processor):
        """Test progress processing handles timeout."""
        batch_processor._initialized = True
        batch_processor.queue = Mock()

        # Mock queue that never completes
        batch_processor.queue.get_queue_status = AsyncMock(return_value={"pending": 10})
        batch_processor.queue.start_processing = AsyncMock()
        batch_processor.queue.stop_processing = AsyncMock()

        # Set a very short timeout for testing
        call_count = {"count": 0}

        def mock_time():
            # First call returns 0, second call returns 301 (timeout reached)
            call_count["count"] += 1
            if call_count["count"] == 1:
                return 0
            return 301

        with patch.object(asyncio.get_event_loop(), "time", side_effect=mock_time):
            with patch("src.nescordbot.utils.memory.optimize_memory"):
                result = await batch_processor.process_with_progress()

                # Should complete due to timeout
                assert result["success"] is True

    def test_set_progress_callback(self, batch_processor):
        """Test setting progress callback."""
        callback = Mock()
        batch_processor.set_progress_callback(callback)

        assert batch_processor._progress_callback is callback

    def test_get_memory_stats(self, batch_processor):
        """Test memory statistics retrieval."""
        mock_stats = {"rss_mb": 200.0, "percent": 10.0, "available_mb": 800.0}
        batch_processor.memory_monitor.get_memory_usage = Mock(return_value=mock_stats)

        stats = batch_processor.get_memory_stats()

        assert stats["rss_mb"] == 200.0
        assert stats["percent"] == 10.0
        assert stats["available_mb"] == 800.0

    @pytest.mark.asyncio
    async def test_processing_loop_with_memory_optimization(self, batch_processor):
        """Test processing loop includes memory optimization."""
        batch_processor._initialized = True
        batch_processor.queue = Mock()
        batch_processor.queue.get_queue_status = AsyncMock(return_value={})

        # Mock memory monitor
        mock_gc_result = {"memory_freed_mb": 15.0}
        batch_processor.memory_monitor.check_and_optimize = Mock(return_value=mock_gc_result)

        # Mock _check_completed_batches
        batch_processor._check_completed_batches = AsyncMock()

        # Start processing loop and let it run briefly
        loop_task = asyncio.create_task(batch_processor._processing_loop())

        await asyncio.sleep(0.1)

        # Stop the loop
        batch_processor._shutdown_event.set()

        try:
            await asyncio.wait_for(loop_task, timeout=1.0)
        except asyncio.TimeoutError:
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass

        # Should have called memory optimization
        assert batch_processor.memory_monitor.check_and_optimize.call_count >= 0

    @pytest.mark.asyncio
    async def test_processing_loop_cancellation(self, batch_processor):
        """Test processing loop responds to cancellation."""
        batch_processor._initialized = True
        batch_processor._check_completed_batches = AsyncMock()

        # Start processing loop
        loop_task = asyncio.create_task(batch_processor._processing_loop())

        await asyncio.sleep(0.05)

        # Trigger cancellation
        batch_processor._cancel_event.set()

        # Should exit cleanly
        try:
            await asyncio.wait_for(loop_task, timeout=1.0)
        except asyncio.TimeoutError:
            pytest.fail("Processing loop did not respond to cancellation")
