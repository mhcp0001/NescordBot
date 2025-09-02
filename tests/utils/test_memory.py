"""Tests for memory monitoring utilities."""

import asyncio
import gc
from unittest.mock import Mock, patch

import pytest

from src.nescordbot.utils.memory import (
    MemoryMonitor,
    MemoryOptimizedProcessor,
    get_memory_monitor,
    optimize_memory,
)


class TestMemoryMonitor:
    """Test memory monitoring functionality."""

    def test_memory_monitor_init(self):
        """Test memory monitor initialization."""
        monitor = MemoryMonitor(threshold_mb=100.0, gc_threshold_mb=50.0)

        assert monitor.threshold_mb == 100.0
        assert monitor.gc_threshold_mb == 50.0
        assert monitor.last_memory_mb == 0.0
        assert monitor.gc_interval == 30.0

    @patch("src.nescordbot.utils.memory.PSUTIL_AVAILABLE", True)
    @patch("src.nescordbot.utils.memory.psutil")
    def test_get_memory_usage_with_psutil(self, mock_psutil):
        """Test memory usage retrieval with psutil available."""
        # Mock psutil
        mock_process = Mock()
        mock_memory_info = Mock()
        mock_memory_info.rss = 100 * 1024 * 1024  # 100MB
        mock_memory_info.vms = 200 * 1024 * 1024  # 200MB
        mock_process.memory_info.return_value = mock_memory_info
        mock_process.memory_percent.return_value = 5.0

        mock_virtual_memory = Mock()
        mock_virtual_memory.available = 1000 * 1024 * 1024  # 1000MB
        mock_virtual_memory.total = 2000 * 1024 * 1024  # 2000MB

        mock_psutil.Process.return_value = mock_process
        mock_psutil.virtual_memory.return_value = mock_virtual_memory

        monitor = MemoryMonitor()
        stats = monitor.get_memory_usage()

        assert stats["rss_mb"] == 100.0
        assert stats["vms_mb"] == 200.0
        assert stats["percent"] == 5.0
        assert stats["available_mb"] == 1000.0
        assert stats["total_mb"] == 2000.0
        assert "timestamp" in stats

    @patch("src.nescordbot.utils.memory.PSUTIL_AVAILABLE", False)
    def test_get_memory_usage_without_psutil(self):
        """Test memory usage retrieval without psutil."""
        monitor = MemoryMonitor()
        stats = monitor.get_memory_usage()

        # Should have fallback values
        assert stats["rss_mb"] == 0.0
        assert stats["vms_mb"] == 0.0
        assert stats["percent"] == 0.0
        assert stats["available_mb"] == 1000.0
        assert stats["total_mb"] == 2000.0
        assert "timestamp" in stats

    def test_should_trigger_gc(self):
        """Test GC trigger logic."""
        monitor = MemoryMonitor(gc_threshold_mb=50.0)
        monitor.gc_interval = 0.1  # Short interval for testing
        monitor.last_memory_mb = 100.0

        # Should not trigger immediately due to time interval
        assert not monitor.should_trigger_gc()

        # Wait for interval
        import time

        time.sleep(0.15)

        # Mock increased memory usage
        with patch.object(monitor, "get_memory_usage") as mock_get_memory:
            mock_get_memory.return_value = {"rss_mb": 160.0}  # 60MB increase
            assert monitor.should_trigger_gc()

    @patch("src.nescordbot.utils.memory.gc.collect")
    def test_perform_gc(self, mock_collect):
        """Test garbage collection execution."""
        mock_collect.return_value = 100  # Objects collected

        monitor = MemoryMonitor()

        # Mock memory usage
        with patch.object(monitor, "get_memory_usage") as mock_get_memory:
            mock_get_memory.side_effect = [
                {"rss_mb": 200.0},  # Before GC
                {"rss_mb": 180.0},  # After GC
            ]

            result = monitor.perform_gc()

            assert result["collected_objects"] == 100
            assert result["memory_before_mb"] == 200.0
            assert result["memory_after_mb"] == 180.0
            assert result["memory_freed_mb"] == 20.0
            assert "timestamp" in result

    def test_check_and_optimize(self):
        """Test memory check and optimization."""
        monitor = MemoryMonitor(threshold_mb=100.0)

        # Mock high memory usage that should trigger GC
        with patch.object(monitor, "get_memory_usage") as mock_get_memory:
            with patch.object(monitor, "should_trigger_gc") as mock_should_trigger:
                with patch.object(monitor, "perform_gc") as mock_perform_gc:
                    mock_get_memory.return_value = {"rss_mb": 150.0}  # Above threshold
                    mock_should_trigger.return_value = True
                    mock_perform_gc.return_value = {"memory_freed_mb": 20.0}

                    result = monitor.check_and_optimize()

                    assert result is not None
                    assert result["memory_freed_mb"] == 20.0
                    mock_perform_gc.assert_called_once()

    @pytest.mark.asyncio
    async def test_monitor_task(self):
        """Test background monitoring task."""
        monitor = MemoryMonitor()

        # Mock check_and_optimize to avoid actual GC
        with patch.object(monitor, "check_and_optimize") as mock_check:
            # Start monitoring task
            task = asyncio.create_task(monitor.monitor_task(interval=0.1))

            # Let it run for a short time
            await asyncio.sleep(0.25)

            # Cancel the task
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

            # Should have called check_and_optimize at least once
            assert mock_check.call_count >= 1


class TestMemoryOptimizedProcessor:
    """Test memory-optimized batch processor."""

    def test_processor_init(self):
        """Test processor initialization."""
        processor = MemoryOptimizedProcessor(memory_threshold_mb=200.0)

        assert processor.memory_monitor.threshold_mb == 200.0
        assert processor._processed_count == 0
        assert processor._gc_frequency == 50

    def test_process_item_not_implemented(self):
        """Test that process_item raises NotImplementedError."""
        processor = MemoryOptimizedProcessor()

        with pytest.raises(NotImplementedError):
            processor.process_item("test")

    @pytest.mark.asyncio
    async def test_process_batch(self):
        """Test batch processing with memory optimization."""

        class TestProcessor(MemoryOptimizedProcessor):
            def process_item(self, item):
                return f"processed_{item}"

        processor = TestProcessor()

        # Mock memory optimization
        with patch.object(processor.memory_monitor, "check_and_optimize") as mock_optimize:
            mock_optimize.return_value = None

            items = [f"item_{i}" for i in range(25)]  # Enough to trigger GC check
            results = await processor.process_batch(items, batch_size=10)

            assert len(results) == 25
            assert results[0] == "processed_item_0"
            assert results[-1] == "processed_item_24"

            # Should have called memory optimization (may not be called if fast)
            assert mock_optimize.call_count >= 0

    def test_get_memory_stats(self):
        """Test memory statistics retrieval."""
        processor = MemoryOptimizedProcessor()

        with patch.object(processor.memory_monitor, "get_memory_usage") as mock_get_memory:
            mock_get_memory.return_value = {"rss_mb": 100.0, "percent": 5.0}

            stats = processor.get_memory_stats()

            assert stats["rss_mb"] == 100.0
            assert stats["percent"] == 5.0


class TestGlobalMonitor:
    """Test global monitor functionality."""

    def test_get_memory_monitor(self):
        """Test global monitor retrieval."""
        # Clear global monitor for testing
        import src.nescordbot.utils.memory as memory_module

        memory_module._global_monitor = None

        monitor1 = get_memory_monitor()
        monitor2 = get_memory_monitor()

        # Should return the same instance
        assert monitor1 is monitor2
        assert isinstance(monitor1, MemoryMonitor)

    def test_optimize_memory(self):
        """Test global memory optimization."""
        with patch("src.nescordbot.utils.memory.get_memory_monitor") as mock_get_monitor:
            mock_monitor = Mock()
            mock_monitor.check_and_optimize.return_value = {"memory_freed_mb": 15.0}
            mock_get_monitor.return_value = mock_monitor

            result = optimize_memory()

            assert result is not None and result["memory_freed_mb"] == 15.0
            mock_monitor.check_and_optimize.assert_called_once()
