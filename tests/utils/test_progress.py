"""Tests for progress tracking utilities."""

import asyncio
import time
from unittest.mock import Mock

import pytest

from src.nescordbot.utils.progress import (
    BatchProgressTracker,
    ProgressStats,
    ProgressTracker,
    run_with_progress,
)


class TestProgressStats:
    """Test progress statistics container."""

    def test_progress_stats_init(self):
        """Test progress stats initialization."""
        stats = ProgressStats(total=100, description="Test Progress")

        assert stats.total == 100
        assert stats.current == 0
        assert stats.description == "Test Progress"
        assert stats.start_time > 0

    def test_progress_percent(self):
        """Test progress percentage calculation."""
        stats = ProgressStats(total=100)
        stats.current = 25

        assert stats.progress_percent == 25.0

        # Test edge case with zero total
        stats_zero = ProgressStats(total=0)
        assert stats_zero.progress_percent == 0.0

    def test_elapsed_time(self):
        """Test elapsed time calculation."""
        stats = ProgressStats(total=100)

        # Should be small but positive
        elapsed = stats.elapsed_time
        assert elapsed >= 0

        # Wait a bit and check again
        time.sleep(0.1)
        assert stats.elapsed_time > elapsed

    def test_eta_seconds(self):
        """Test ETA calculation."""
        stats = ProgressStats(total=100)
        stats.start_time = time.time() - 10  # 10 seconds ago
        stats.current = 50  # Half done

        eta = stats.eta_seconds
        # Should be approximately 10 seconds (same time to complete as elapsed)
        assert 8 <= eta <= 12

        # Test edge cases
        stats_zero = ProgressStats(total=100)
        stats_zero.current = 0
        assert stats_zero.eta_seconds == 0.0

        stats_complete = ProgressStats(total=100)
        stats_complete.current = 100
        assert stats_complete.eta_seconds == 0.0

    def test_rate_per_second(self):
        """Test processing rate calculation."""
        stats = ProgressStats(total=100)
        stats.start_time = time.time() - 10  # 10 seconds ago
        stats.current = 50  # 50 items processed

        rate = stats.rate_per_second
        # Should be approximately 5 items per second
        assert 4 <= rate <= 6

    def test_to_dict(self):
        """Test dictionary conversion."""
        stats = ProgressStats(total=100, current=25, description="Test")

        result = stats.to_dict()

        assert result["total"] == 100
        assert result["current"] == 25
        assert result["progress_percent"] == 25.0
        assert result["description"] == "Test"
        assert "elapsed_time" in result
        assert "eta_seconds" in result
        assert "rate_per_second" in result


class TestProgressTracker:
    """Test progress tracker functionality."""

    def test_tracker_init(self):
        """Test progress tracker initialization."""
        callback = Mock()
        tracker = ProgressTracker(
            total=100, description="Test Task", update_interval=0.5, callback=callback
        )

        assert tracker.stats.total == 100
        assert tracker.stats.description == "Test Task"
        assert tracker.update_interval == 0.5
        assert tracker.callback is callback
        assert not tracker.is_completed()

    def test_update_progress(self):
        """Test progress updates."""
        callback = Mock()
        tracker = ProgressTracker(total=10, callback=callback)

        # Update by 1 (default)
        tracker.update()
        assert tracker.stats.current == 1

        # Update by specific amount
        tracker.update(increment=3)
        assert tracker.stats.current == 4

        # Should not exceed total
        tracker.update(increment=10)
        assert tracker.stats.current == 10
        assert tracker.is_completed()

    def test_callback_interval(self):
        """Test callback timing."""
        callback = Mock()
        tracker = ProgressTracker(total=100, update_interval=0.1, callback=callback)

        # First update should trigger callback
        tracker.update()
        assert callback.call_count == 1

        # Immediate update should not trigger callback
        tracker.update()
        assert callback.call_count == 1

        # Wait for interval and update
        time.sleep(0.15)
        tracker.update()
        assert callback.call_count == 2

    def test_force_callback(self):
        """Test forcing callback updates."""
        callback = Mock()
        tracker = ProgressTracker(total=100, update_interval=1.0, callback=callback)

        tracker.update()  # Initial callback
        tracker.update(force_callback=True)  # Should force callback

        assert callback.call_count == 2

    def test_set_current(self):
        """Test setting current progress value."""
        callback = Mock()
        tracker = ProgressTracker(total=100, callback=callback)

        tracker.set_current(50)
        assert tracker.stats.current == 50

        # Should not exceed total
        tracker.set_current(150)
        assert tracker.stats.current == 100

        # Should not go below zero
        tracker.set_current(-10)
        assert tracker.stats.current == 0

    def test_format_progress(self):
        """Test progress formatting."""
        tracker = ProgressTracker(total=100, description="Test Task")
        tracker.set_current(25)

        formatted = tracker.format_progress()

        assert "Test Task" in formatted
        assert "25/100" in formatted
        assert "25.0%" in formatted
        assert "/s" in formatted
        assert "ETA:" in formatted


class TestBatchProgressTracker:
    """Test batch progress tracker functionality."""

    def test_batch_tracker_init(self):
        """Test batch progress tracker initialization."""
        callback = Mock()
        tracker = BatchProgressTracker(
            total_items=100, batch_size=10, description="Batch Task", callback=callback
        )

        assert tracker.total_items == 100
        assert tracker.batch_size == 10
        assert tracker.total_batches == 10
        assert tracker.description == "Batch Task"
        assert tracker.callback is callback
        assert tracker.current_batch == 0
        assert tracker.current_item == 0

    def test_batch_operations(self):
        """Test batch operations."""
        callback = Mock()
        tracker = BatchProgressTracker(total_items=25, batch_size=10, callback=callback)

        # Start first batch
        tracker.start_batch(0)
        assert tracker.current_batch == 0

        # Update items in batch
        tracker.update_item(5)
        assert tracker.current_item == 5

        # Complete batch
        tracker.complete_batch()
        assert tracker.current_batch == 1

    def test_callback_timing(self):
        """Test callback timing in batch processing."""
        callback = Mock()
        tracker = BatchProgressTracker(
            total_items=100, batch_size=10, update_interval=0.1, callback=callback
        )

        # Update items
        tracker.update_item(5)

        # Wait for interval
        time.sleep(0.15)
        tracker.update_item(3)

        # Should have triggered callback
        assert callback.call_count >= 1

    def test_progress_info(self):
        """Test progress information retrieval."""
        tracker = BatchProgressTracker(total_items=100, batch_size=10, description="Test Batches")

        tracker.current_item = 25
        tracker.current_batch = 2

        info = tracker.get_progress_info()

        assert info["total_items"] == 100
        assert info["current_item"] == 25
        assert info["item_percent"] == 25.0
        assert info["total_batches"] == 10
        assert info["current_batch"] == 2
        assert info["batch_percent"] == 20.0
        assert info["batch_size"] == 10
        assert info["description"] == "Test Batches"
        assert "elapsed_seconds" in info
        assert "rate_per_second" in info
        assert "eta_seconds" in info

    def test_format_progress_batch(self):
        """Test batch progress formatting."""
        tracker = BatchProgressTracker(total_items=100, batch_size=10, description="Batch Test")

        tracker.current_item = 25
        tracker.current_batch = 2

        formatted = tracker.format_progress()

        assert "Batch Test" in formatted
        assert "25/100" in formatted
        assert "2/10" in formatted
        assert "25.0%" in formatted

    def test_completion_check(self):
        """Test completion checking."""
        tracker = BatchProgressTracker(total_items=10, batch_size=5)

        assert not tracker.is_completed()

        tracker.current_item = 10
        assert tracker.is_completed()


class TestRunWithProgress:
    """Test run_with_progress utility function."""

    @pytest.mark.asyncio
    async def test_run_with_progress_sync_function(self):
        """Test running with progress using sync function."""
        callback = Mock()

        def process_item(item):
            return item * 2

        items = [1, 2, 3, 4, 5]
        results = await run_with_progress(
            items=items,
            process_func=process_item,
            batch_size=2,
            description="Test Processing",
            progress_callback=callback,
        )

        assert results == [2, 4, 6, 8, 10]
        assert callback.call_count >= 1

    @pytest.mark.asyncio
    async def test_run_with_progress_async_function(self):
        """Test running with progress using async function."""
        callback = Mock()

        async def process_item(item):
            await asyncio.sleep(0.01)  # Simulate async work
            return item * 3

        items = [1, 2, 3]
        results = await run_with_progress(
            items=items,
            process_func=process_item,
            batch_size=2,
            description="Async Processing",
            progress_callback=callback,
        )

        assert results == [3, 6, 9]
        assert callback.call_count >= 1

    @pytest.mark.asyncio
    async def test_run_with_progress_empty_items(self):
        """Test running with progress with empty items list."""
        callback = Mock()

        def process_item(item):
            return item

        results = await run_with_progress(
            items=[], process_func=process_item, progress_callback=callback
        )

        assert results == []
        # Should still call callback at least once for initialization
        assert callback.call_count >= 1
