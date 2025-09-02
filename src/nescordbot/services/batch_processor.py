"""
Batch Processor Service.

Integrates PersistentQueue with GitOperationService to provide batch processing
of file operations with automatic retry and error handling.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

from ..config import BotConfig
from ..utils.memory import MemoryMonitor, optimize_memory
from ..utils.progress import BatchProgressTracker
from .database import DatabaseService
from .git_operations import FileOperation, GitOperationService
from .github_auth import GitHubAuthManager
from .persistent_queue import FileRequest, PersistentQueue

logger = logging.getLogger(__name__)


class BatchProcessorError(Exception):
    """Batch processor related errors."""

    pass


class BatchProcessor:
    """Batch processor that integrates PersistentQueue with Git operations."""

    def __init__(
        self,
        config: BotConfig,
        db_service: DatabaseService,
        auth_manager: GitHubAuthManager,
        git_operations: GitOperationService,
    ):
        self.config = config
        self.db_service = db_service
        self.auth_manager = auth_manager
        self.git_operations = git_operations

        # Create persistent queue
        self.queue = PersistentQueue(db_service, config)

        # Processing control
        self._processing_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        self._cancel_event = asyncio.Event()
        self._initialized = False

        # Memory monitoring
        self.memory_monitor = MemoryMonitor(
            threshold_mb=300.0, gc_threshold_mb=100.0  # Warning threshold  # GC trigger threshold
        )

        # Progress tracking
        self._progress_tracker: Optional[BatchProgressTracker] = None
        self._progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None

        # Statistics
        self._stats: Dict[str, Any] = {
            "batches_processed": 0,
            "files_processed": 0,
            "errors": 0,
            "last_batch_time": None,
            "last_error_time": None,
        }

    async def initialize(self) -> None:
        """Initialize batch processor and dependencies."""
        if self._initialized:
            return

        try:
            # Initialize dependencies
            await self.auth_manager.initialize()
            await self.git_operations.initialize()
            await self.queue.initialize()

            # Inject GitOperationService into PersistentQueue
            self.queue.set_git_service(self.git_operations)

            self._initialized = True
            logger.info("Batch processor initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize batch processor: {e}")
            raise BatchProcessorError(f"Initialization failed: {e}")

    async def enqueue_file_request(
        self,
        filename: str,
        content: str,
        directory: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        priority: int = 0,
        idempotency_key: Optional[str] = None,
    ) -> int:
        """Enqueue a file processing request."""
        if not self._initialized:
            await self.initialize()

        from datetime import datetime

        file_request = FileRequest(
            filename=filename,
            content=content,
            directory=directory,
            metadata=metadata or {},
            created_at=datetime.now(),
            priority=priority,
        )

        return await self.queue.enqueue(file_request, idempotency_key)

    async def start_processing(self) -> None:
        """Start background batch processing."""
        if not self._initialized:
            await self.initialize()

        if self._processing_task and not self._processing_task.done():
            logger.warning("Batch processing already running")
            return

        logger.info("Starting batch processor")
        self._shutdown_event.clear()
        self._processing_task = asyncio.create_task(self._processing_loop())
        await self.queue.start_processing()

    async def stop_processing(self, graceful: bool = True) -> None:
        """Stop background batch processing."""
        logger.info("Stopping batch processor")
        self._shutdown_event.set()

        # Stop queue processing
        await self.queue.stop_processing(graceful)

        # Stop our processing task
        if self._processing_task and not self._processing_task.done():
            if graceful:
                await self._processing_task
            else:
                self._processing_task.cancel()
                try:
                    await self._processing_task
                except asyncio.CancelledError:
                    pass

        self._processing_task = None
        logger.info("Batch processor stopped")

    async def _processing_loop(self) -> None:
        """Main processing loop for handling batches."""
        logger.info("Batch processing loop started")

        try:
            while not self._shutdown_event.is_set() and not self._cancel_event.is_set():
                try:
                    # Wait for batch processing interval
                    batch_timeout = getattr(self.config, "obsidian_batch_timeout", 30.0)

                    try:
                        # Check for both shutdown and cancel events
                        done, pending = await asyncio.wait(
                            [
                                asyncio.create_task(self._shutdown_event.wait()),
                                asyncio.create_task(self._cancel_event.wait()),
                            ],
                            timeout=batch_timeout,
                            return_when=asyncio.FIRST_COMPLETED,
                        )

                        # Cancel pending tasks
                        for task in pending:
                            task.cancel()

                        if done:
                            # Either shutdown or cancel was requested
                            break

                    except asyncio.TimeoutError:
                        # Timeout is normal, continue processing
                        pass

                    # Check memory usage periodically
                    gc_result = self.memory_monitor.check_and_optimize()
                    if gc_result and gc_result["memory_freed_mb"] > 10.0:
                        logger.info(
                            f"Memory optimization: freed {gc_result['memory_freed_mb']:.2f}MB"
                        )

                    # Check if there are any processed batches to handle
                    await self._check_completed_batches()

                except Exception as e:
                    logger.error(f"Error in batch processing loop: {e}")
                    self._stats["errors"] += 1
                    self._stats["last_error_time"] = asyncio.get_event_loop().time()

                    # Wait before retrying
                    await asyncio.sleep(5.0)

        except asyncio.CancelledError:
            logger.info("Batch processing loop cancelled")
            raise
        finally:
            logger.info("Batch processing loop stopped")

    async def _check_completed_batches(self) -> None:
        """Check for completed batches and process them."""
        # This is a placeholder for now since PersistentQueue handles its own processing
        # In a full implementation, this would coordinate with PersistentQueue
        # to get completed batches and handle any additional processing
        pass

    async def process_batch_manually(self, batch_size: Optional[int] = None) -> Dict[str, Any]:
        """Manually process a batch of pending requests."""
        if not self._initialized:
            await self.initialize()

        try:
            # Get queue status
            status = await self.queue.get_queue_status()
            pending_count = status.get("pending", 0)

            if pending_count == 0:
                return {
                    "success": True,
                    "message": "No pending requests to process",
                    "files_processed": 0,
                }

            # For manual processing, we would need to access queue internals
            # This is a simplified implementation
            logger.info(f"Manual batch processing requested (pending: {pending_count})")

            # Start queue processing temporarily if not running
            was_processing = self._processing_task and not self._processing_task.done()
            if not was_processing:
                await self.queue.start_processing()

                # Wait a short time for processing
                await asyncio.sleep(2.0)

                # Stop processing
                await self.queue.stop_processing()

            # Get updated status
            new_status = await self.queue.get_queue_status()
            processed = pending_count - new_status.get("pending", 0)

            return {
                "success": True,
                "files_processed": processed,
                "remaining_pending": new_status.get("pending", 0),
                "completed": new_status.get("completed", 0),
                "failed": new_status.get("failed", 0),
            }

        except Exception as e:
            logger.error(f"Manual batch processing failed: {e}")
            return {"success": False, "error": str(e), "files_processed": 0}

    async def get_processing_status(self) -> Dict[str, Any]:
        """Get current processing status."""
        queue_status = await self.queue.get_queue_status() if self._initialized else {}

        # Get memory statistics
        memory_stats = self.memory_monitor.get_memory_usage()

        # Get progress information
        progress_info = {}
        if self._progress_tracker:
            progress_info = self._progress_tracker.get_progress_info()

        return {
            "initialized": self._initialized,
            "processing_active": bool(self._processing_task and not self._processing_task.done()),
            "cancelled": self._cancel_event.is_set(),
            "queue_status": queue_status,
            "statistics": self._stats.copy(),
            "memory_stats": memory_stats,
            "progress": progress_info,
            "git_status": await self.git_operations.get_repository_status()
            if self._initialized
            else {},
        }

    async def get_queue_status(self) -> Dict[str, Any]:
        """Get queue status information."""
        if not self._initialized:
            return {"error": "Not initialized"}

        return await self.queue.get_queue_status()

    async def cleanup(self) -> None:
        """Clean up batch processor resources."""
        try:
            # Stop processing
            await self.stop_processing(graceful=True)

            # Cleanup components
            if self.queue:
                await self.queue.cleanup()

            if self.git_operations:
                await self.git_operations.cleanup()

            if self.auth_manager:
                await self.auth_manager.cleanup()

            logger.info("Batch processor cleanup completed")

        except Exception as e:
            logger.error(f"Error during batch processor cleanup: {e}")
        finally:
            # Always mark as not initialized
            self._initialized = False

    async def cancel_processing(self) -> bool:
        """
        Cancel ongoing batch processing.

        Returns:
            bool: True if cancellation was successful
        """
        if not self._processing_task or self._processing_task.done():
            return False

        logger.info("Cancelling batch processing...")
        self._cancel_event.set()

        try:
            # Wait for processing task to complete
            await asyncio.wait_for(self._processing_task, timeout=10.0)
            logger.info("Batch processing cancelled successfully")
            return True
        except asyncio.TimeoutError:
            logger.warning("Batch processing cancellation timed out, forcing termination")
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
            return True
        except Exception as e:
            logger.error(f"Error during batch processing cancellation: {e}")
            return False
        finally:
            self._cancel_event.clear()

    def set_progress_callback(self, callback: Optional[Callable[[Dict[str, Any]], None]]) -> None:
        """Set progress callback for batch operations."""
        self._progress_callback = callback

    async def process_with_progress(
        self,
        batch_size: Optional[int] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """
        Process batch with detailed progress tracking.

        Args:
            batch_size: Optional batch size override
            progress_callback: Optional progress callback

        Returns:
            Dict containing processing results and statistics
        """
        if not self._initialized:
            await self.initialize()

        # Set progress callback if provided
        if progress_callback:
            self.set_progress_callback(progress_callback)

        try:
            # Get queue status to setup progress tracking
            status = await self.queue.get_queue_status()
            pending_count = status.get("pending", 0)

            if pending_count == 0:
                return {
                    "success": True,
                    "message": "No pending requests to process",
                    "files_processed": 0,
                    "memory_stats": self.memory_monitor.get_memory_usage(),
                }

            # Setup progress tracker
            config_batch_size: int = getattr(self.config, "obsidian_batch_size", 5)
            effective_batch_size: int = batch_size if batch_size is not None else config_batch_size
            self._progress_tracker = BatchProgressTracker(
                total_items=pending_count,
                batch_size=effective_batch_size,
                description="Batch Processing",
                callback=self._progress_callback,
            )

            logger.info(
                f"Starting batch processing with progress tracking (items: {pending_count})"
            )

            # Start queue processing temporarily if not running
            was_processing = self._processing_task and not self._processing_task.done()
            if not was_processing:
                await self.queue.start_processing()

                # Monitor progress with memory optimization
                start_time = asyncio.get_event_loop().time()
                while True:
                    await asyncio.sleep(2.0)

                    # Check for cancellation
                    if self._cancel_event.is_set():
                        break

                    # Update progress
                    new_status = await self.queue.get_queue_status()
                    current_pending = new_status.get("pending", 0)
                    processed = pending_count - current_pending

                    if self._progress_tracker:
                        self._progress_tracker.update_item(
                            processed - self._progress_tracker.current_item
                        )

                    # Perform memory optimization
                    optimize_memory()

                    # Check if done
                    if current_pending == 0 or processed >= pending_count:
                        break

                    # Timeout check (max 5 minutes)
                    if asyncio.get_event_loop().time() - start_time > 300:
                        logger.warning("Batch processing timeout reached")
                        break

                # Stop processing
                await self.queue.stop_processing()

            # Get final statistics
            final_status = await self.queue.get_queue_status()
            final_processed = pending_count - final_status.get("pending", 0)
            memory_stats = self.memory_monitor.get_memory_usage()

            result = {
                "success": True,
                "files_processed": final_processed,
                "remaining_pending": final_status.get("pending", 0),
                "completed": final_status.get("completed", 0),
                "failed": final_status.get("failed", 0),
                "memory_stats": memory_stats,
                "cancelled": self._cancel_event.is_set(),
            }

            if self._progress_tracker:
                result["progress"] = self._progress_tracker.get_progress_info()

            return result

        except Exception as e:
            logger.error(f"Batch processing with progress failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "files_processed": 0,
                "memory_stats": self.memory_monitor.get_memory_usage(),
            }
        finally:
            self._progress_tracker = None

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get current memory usage statistics."""
        return self.memory_monitor.get_memory_usage()


# Enhanced PersistentQueue to work with GitOperationService
class GitHubIntegratedQueue(PersistentQueue):
    """Extended PersistentQueue that integrates with GitHub operations."""

    def __init__(
        self, db_service: DatabaseService, config: Any, git_operations: GitOperationService
    ):
        super().__init__(db_service, config)
        self.git_operations = git_operations

    async def _process_batch(self, file_requests: List[FileRequest], batch_id: int) -> bool:
        """Process a batch of file requests using GitOperationService."""
        try:
            # Convert FileRequests to FileOperations
            operations = []
            for request in file_requests:
                operation = FileOperation(
                    filename=request.filename,
                    content=request.content,
                    directory=request.directory,
                    operation="create",  # Default operation
                    commit_message=request.metadata.get("commit_message"),
                )
                operations.append(operation)

            # Process batch through Git operations
            result = await self.git_operations.create_files(operations)

            success: bool = result.get("success", False)
            files_created: int = result.get("files_created", 0)
            commit_sha = result.get("commit_sha")

            if success and files_created > 0:
                logger.info(
                    f"Batch {batch_id} processed successfully: "
                    f"{files_created} files, commit {commit_sha}"
                )
                return True
            else:
                logger.warning(f"Batch {batch_id} processed but no files created")
                return files_created == 0  # Success if no files needed to be created

        except Exception as e:
            logger.error(f"Batch {batch_id} processing failed: {e}")
            return False
