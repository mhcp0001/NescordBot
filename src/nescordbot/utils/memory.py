"""Memory monitoring and optimization utilities."""

import asyncio
import gc
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not available - memory monitoring will be limited")


class MemoryMonitor:
    """Memory usage monitor with automatic optimization."""

    def __init__(self, threshold_mb: float = 500.0, gc_threshold_mb: float = 200.0):
        """
        Initialize memory monitor.

        Args:
            threshold_mb: Memory threshold in MB to trigger warnings
            gc_threshold_mb: Memory increase threshold in MB to trigger garbage collection
        """
        self.threshold_mb = threshold_mb
        self.gc_threshold_mb = gc_threshold_mb
        self.last_memory_mb = 0.0
        self.last_gc_time = time.time()
        self.gc_interval = 30.0  # Minimum 30 seconds between GC calls

    def get_memory_usage(self) -> Dict[str, Any]:
        """Get current memory usage statistics."""
        stats = {
            "timestamp": time.time(),
            "gc_collections": sum(gc.get_stats()[0].values()) if gc.get_stats() else 0,
        }

        if PSUTIL_AVAILABLE:
            process = psutil.Process()
            memory_info = process.memory_info()
            stats.update(
                {
                    "rss_mb": memory_info.rss / 1024 / 1024,  # Resident Set Size
                    "vms_mb": memory_info.vms / 1024 / 1024,  # Virtual Memory Size
                    "percent": process.memory_percent(),
                    "available_mb": psutil.virtual_memory().available / 1024 / 1024,
                    "total_mb": psutil.virtual_memory().total / 1024 / 1024,
                }
            )
        else:
            # Fallback: estimate using gc
            stats.update(
                {
                    "rss_mb": 0.0,
                    "vms_mb": 0.0,
                    "percent": 0.0,
                    "available_mb": 1000.0,  # Assume 1GB available
                    "total_mb": 2000.0,  # Assume 2GB total
                }
            )

        return stats

    def should_trigger_gc(self) -> bool:
        """Check if garbage collection should be triggered."""
        current_time = time.time()
        if current_time - self.last_gc_time < self.gc_interval:
            return False

        stats = self.get_memory_usage()
        current_memory = stats["rss_mb"] if PSUTIL_AVAILABLE else 0.0

        # Trigger GC if memory increased significantly
        memory_increase = current_memory - self.last_memory_mb
        if memory_increase > self.gc_threshold_mb:
            self.last_memory_mb = current_memory
            return True

        return False

    def perform_gc(self) -> Dict[str, Any]:
        """Perform garbage collection and return statistics."""
        before_stats = self.get_memory_usage()

        # Force garbage collection
        collected = gc.collect()

        after_stats = self.get_memory_usage()
        self.last_gc_time = time.time()

        result = {
            "collected_objects": collected,
            "memory_before_mb": before_stats["rss_mb"],
            "memory_after_mb": after_stats["rss_mb"],
            "memory_freed_mb": before_stats["rss_mb"] - after_stats["rss_mb"],
            "timestamp": self.last_gc_time,
        }

        logger.info(
            f"GC performed: {collected} objects collected, "
            f"{result['memory_freed_mb']:.2f}MB freed"
        )

        return result

    def check_and_optimize(self) -> Optional[Dict[str, Any]]:
        """Check memory usage and optimize if needed."""
        stats = self.get_memory_usage()

        # Check if memory usage is too high
        if stats["rss_mb"] > self.threshold_mb:
            logger.warning(
                f"High memory usage: {stats['rss_mb']:.2f}MB " f"(threshold: {self.threshold_mb}MB)"
            )

        # Trigger GC if needed
        if self.should_trigger_gc():
            return self.perform_gc()

        return None

    async def monitor_task(self, interval: float = 60.0) -> None:
        """Background task to monitor memory usage."""
        while True:
            try:
                self.check_and_optimize()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                logger.info("Memory monitoring task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in memory monitoring: {e}")
                await asyncio.sleep(interval)


class MemoryOptimizedProcessor:
    """Base class for memory-optimized batch processing."""

    def __init__(self, memory_threshold_mb: float = 300.0):
        """Initialize with memory monitoring."""
        self.memory_monitor = MemoryMonitor(threshold_mb=memory_threshold_mb)
        self._processed_count = 0
        self._gc_frequency = 50  # Perform GC check every N items

    def process_item(self, item: Any) -> Any:
        """Process a single item (to be overridden)."""
        raise NotImplementedError

    async def process_batch(self, items: list, batch_size: int = 10) -> list:
        """Process items in batches with memory optimization."""
        results = []

        for i in range(0, len(items), batch_size):
            batch = items[i : i + batch_size]

            # Process batch
            for item in batch:
                result = self.process_item(item)
                results.append(result)
                self._processed_count += 1

                # Check memory periodically
                if self._processed_count % self._gc_frequency == 0:
                    gc_result = self.memory_monitor.check_and_optimize()
                    if gc_result and gc_result["memory_freed_mb"] > 0:
                        logger.debug(f"GC freed {gc_result['memory_freed_mb']:.2f}MB")

            # Small delay between batches to prevent overwhelming
            await asyncio.sleep(0.1)

        return results

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get current memory statistics."""
        return self.memory_monitor.get_memory_usage()


# Global memory monitor instance
_global_monitor: Optional[MemoryMonitor] = None


def get_memory_monitor() -> MemoryMonitor:
    """Get the global memory monitor instance."""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = MemoryMonitor()
    return _global_monitor


def optimize_memory() -> Optional[Dict[str, Any]]:
    """Convenient function to check and optimize memory."""
    return get_memory_monitor().check_and_optimize()
