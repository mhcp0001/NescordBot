"""
Batch Processor Service.

Integrates PersistentQueue with GitOperationService to provide batch processing
of file operations with automatic retry and error handling.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from ..config import BotConfig
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
        self._initialized = False

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
            while not self._shutdown_event.is_set():
                try:
                    # Wait for batch processing interval
                    batch_timeout = getattr(self.config, "obsidian_batch_timeout", 30.0)

                    try:
                        await asyncio.wait_for(self._shutdown_event.wait(), timeout=batch_timeout)
                        # If we get here, shutdown was requested
                        break
                    except asyncio.TimeoutError:
                        # Timeout is normal, continue processing
                        pass

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

        return {
            "initialized": self._initialized,
            "processing_active": bool(self._processing_task and not self._processing_task.done()),
            "queue_status": queue_status,
            "statistics": self._stats.copy(),
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
