"""Progress tracking utilities for batch operations."""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ProgressStats:
    """Progress statistics container."""

    total: int
    current: int = 0
    start_time: float = field(default_factory=time.time)
    description: str = ""

    @property
    def progress_percent(self) -> float:
        """Get progress as percentage."""
        if self.total == 0:
            return 0.0
        return (self.current / self.total) * 100.0

    @property
    def elapsed_time(self) -> float:
        """Get elapsed time in seconds."""
        return time.time() - self.start_time

    @property
    def eta_seconds(self) -> float:
        """Estimate time remaining in seconds."""
        if self.current == 0 or self.current >= self.total:
            return 0.0

        rate = self.current / self.elapsed_time
        remaining = self.total - self.current
        return remaining / rate if rate > 0 else 0.0

    @property
    def rate_per_second(self) -> float:
        """Get processing rate per second."""
        elapsed = self.elapsed_time
        return self.current / elapsed if elapsed > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total": self.total,
            "current": self.current,
            "progress_percent": self.progress_percent,
            "elapsed_time": self.elapsed_time,
            "eta_seconds": self.eta_seconds,
            "rate_per_second": self.rate_per_second,
            "description": self.description,
        }


class ProgressTracker:
    """Progress tracker with callback support."""

    def __init__(
        self,
        total: int,
        description: str = "",
        update_interval: float = 1.0,
        callback: Optional[Callable[[ProgressStats], None]] = None,
    ):
        """
        Initialize progress tracker.

        Args:
            total: Total number of items to process
            description: Description of the operation
            update_interval: Minimum seconds between callback updates
            callback: Optional callback function called on updates
        """
        self.stats = ProgressStats(total=total, description=description)
        self.update_interval = update_interval
        self.callback = callback
        self.last_update_time = 0.0
        self._completed = False

    def update(self, increment: int = 1, force_callback: bool = False) -> None:
        """
        Update progress.

        Args:
            increment: Number of items completed
            force_callback: Force callback even if interval not reached
        """
        self.stats.current = min(self.stats.current + increment, self.stats.total)

        # Check if we should trigger callback
        current_time = time.time()
        should_callback = (
            force_callback
            or (current_time - self.last_update_time >= self.update_interval)
            or self.stats.current >= self.stats.total
        )

        if should_callback and self.callback:
            try:
                self.callback(self.stats)
                self.last_update_time = current_time
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")

        # Mark as completed
        if self.stats.current >= self.stats.total and not self._completed:
            self._completed = True
            logger.info(
                f"Progress completed: {self.stats.description} "
                f"({self.stats.total} items in {self.stats.elapsed_time:.2f}s)"
            )

    def set_current(self, value: int, force_callback: bool = False) -> None:
        """Set current progress value."""
        self.stats.current = min(max(0, value), self.stats.total)

        if force_callback and self.callback:
            try:
                self.callback(self.stats)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")

    def is_completed(self) -> bool:
        """Check if progress is completed."""
        return self.stats.current >= self.stats.total

    def get_stats(self) -> ProgressStats:
        """Get current progress statistics."""
        return self.stats

    def format_progress(self) -> str:
        """Format progress as a string."""
        percent = self.stats.progress_percent
        eta = self.stats.eta_seconds
        rate = self.stats.rate_per_second

        eta_str = f"{eta:.1f}s" if eta > 0 else "N/A"

        return (
            f"{self.stats.description}: {self.stats.current}/{self.stats.total} "
            f"({percent:.1f}%) - {rate:.1f}/s - ETA: {eta_str}"
        )


class BatchProgressTracker:
    """Progress tracker for batch operations with sub-progress tracking."""

    def __init__(
        self,
        total_items: int,
        batch_size: int,
        description: str = "",
        callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        update_interval: float = 1.0,
    ):
        """
        Initialize batch progress tracker.

        Args:
            total_items: Total number of items to process
            batch_size: Size of each batch
            description: Description of the operation
            callback: Optional callback for progress updates
        """
        self.total_items = total_items
        self.batch_size = batch_size
        self.description = description
        self.callback = callback
        self.update_interval = update_interval

        self.total_batches = (total_items + batch_size - 1) // batch_size
        self.current_batch = 0
        self.current_item = 0
        self.start_time = time.time()

        self._batch_start_time = time.time()
        self._last_update_time = 0.0
        self.update_interval = 1.0

    def start_batch(self, batch_index: int) -> None:
        """Start processing a new batch."""
        self.current_batch = batch_index
        self._batch_start_time = time.time()

    def update_item(self, items_completed: int = 1) -> None:
        """Update item progress within current batch."""
        self.current_item = min(self.current_item + items_completed, self.total_items)

        # Trigger callback if enough time has passed
        current_time = time.time()
        if current_time - self._last_update_time >= self.update_interval and self.callback:
            try:
                self.callback(self.get_progress_info())
                self._last_update_time = current_time
            except Exception as e:
                logger.error(f"Error in batch progress callback: {e}")

    def complete_batch(self) -> None:
        """Mark current batch as completed."""
        self.current_batch += 1
        batch_time = time.time() - self._batch_start_time
        logger.debug(
            f"Batch {self.current_batch}/{self.total_batches} completed " f"in {batch_time:.2f}s"
        )

    def get_progress_info(self) -> Dict[str, Any]:
        """Get comprehensive progress information."""
        elapsed = time.time() - self.start_time
        item_percent = (self.current_item / self.total_items * 100) if self.total_items > 0 else 0
        batch_percent = (
            (self.current_batch / self.total_batches * 100) if self.total_batches > 0 else 0
        )

        rate = self.current_item / elapsed if elapsed > 0 else 0
        eta = (self.total_items - self.current_item) / rate if rate > 0 else 0

        return {
            "description": self.description,
            "total_items": self.total_items,
            "current_item": self.current_item,
            "item_percent": item_percent,
            "total_batches": self.total_batches,
            "current_batch": self.current_batch,
            "batch_percent": batch_percent,
            "elapsed_seconds": elapsed,
            "rate_per_second": rate,
            "eta_seconds": eta,
            "batch_size": self.batch_size,
        }

    def format_progress(self) -> str:
        """Format progress as a readable string."""
        info = self.get_progress_info()
        return (
            f"{info['description']}: "
            f"Items {info['current_item']}/{info['total_items']} "
            f"({info['item_percent']:.1f}%) - "
            f"Batch {info['current_batch']}/{info['total_batches']} - "
            f"{info['rate_per_second']:.1f}/s - "
            f"ETA: {info['eta_seconds']:.1f}s"
        )

    def is_completed(self) -> bool:
        """Check if all processing is completed."""
        return self.current_item >= self.total_items


async def run_with_progress(
    items: list,
    process_func: Callable,
    batch_size: int = 10,
    description: str = "Processing",
    progress_callback: Optional[Callable[[ProgressStats], None]] = None,
) -> list:
    """
    Run processing function with progress tracking.

    Args:
        items: List of items to process
        process_func: Function to process each item
        batch_size: Size of batches
        description: Description for progress tracking
        progress_callback: Optional progress callback

    Returns:
        List of results
    """
    tracker = ProgressTracker(total=len(items), description=description, callback=progress_callback)

    results = []

    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]

        for item in batch:
            if asyncio.iscoroutinefunction(process_func):
                result = await process_func(item)
            else:
                result = process_func(item)
            results.append(result)
            tracker.update()

        # Small delay between batches
        await asyncio.sleep(0.01)

    return results
