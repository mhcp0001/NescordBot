"""
Git Operations Service.

Provides safe Git operations for file creation, staging, committing, and pushing
with support for multiple repository instances.
"""

import asyncio
import hashlib
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

import git
from git import Repo

from ..config import BotConfig
from .github_auth import GitHubAuthManager

logger = logging.getLogger(__name__)


class GitOperationError(Exception):
    """Git operation related errors."""

    pass


class FileOperation:
    """Represents a file operation for batch processing."""

    def __init__(
        self,
        filename: str,
        content: str,
        directory: str = "",
        operation: str = "create",
        commit_message: Optional[str] = None,
    ):
        self.filename = filename
        self.content = content
        self.directory = directory
        self.operation = operation  # create, update, delete
        self.commit_message = commit_message
        self.file_path = Path(directory) / filename if directory else Path(filename)

    def __repr__(self) -> str:
        return f"FileOperation({self.operation}: {self.file_path})"


class GitOperationService:
    """Git operations service with authentication integration."""

    def __init__(self, config: BotConfig, auth_manager: GitHubAuthManager):
        self.config = config
        self.auth_manager = auth_manager
        self.repo_url = self._build_repo_url()

        # Directory management
        self.base_path = Path(getattr(config, "github_obsidian_base_path", "data/repos"))
        self.instance_id = self._generate_instance_id()
        self.local_path = self.base_path / f"instance_{self.instance_id}"

        self._repo: Optional[Repo] = None
        self._lock = asyncio.Lock()
        self._initialized = False

    def _build_repo_url(self) -> str:
        """Build repository URL from config."""
        repo_owner = getattr(self.config, "github_repo_owner", "")
        repo_name = getattr(self.config, "github_repo_name", "")

        if not repo_owner or not repo_name:
            raise GitOperationError("Repository owner and name must be configured")

        return f"https://github.com/{repo_owner}/{repo_name}.git"

    def _generate_instance_id(self) -> str:
        """Generate unique instance ID."""
        # Use config-based unique identifier
        config_str = f"{self.repo_url}_{getattr(self.config, 'instance_id', 'default')}"
        return hashlib.md5(config_str.encode()).hexdigest()[:8]

    async def initialize(self) -> None:
        """Initialize Git repository."""
        async with self._lock:
            if self._initialized:
                return

            try:
                # Ensure base directory exists
                self.base_path.mkdir(parents=True, exist_ok=True)

                if self.local_path.exists():
                    # Repository exists, try to open it
                    self._repo = await asyncio.to_thread(Repo, str(self.local_path))
                    logger.info(f"Opened existing repository: {self.local_path}")

                    # Ensure we're on the correct remote
                    await self._update_remote()
                else:
                    # Clone repository
                    await self._clone_repository()

                # Verify repository state
                await self._verify_repository()
                self._initialized = True

                logger.info(f"Git repository initialized: {self.local_path}")

            except Exception as e:
                logger.error(f"Failed to initialize Git repository: {e}")
                raise GitOperationError(f"Repository initialization failed: {e}")

    async def _clone_repository(self) -> None:
        """Clone repository with authentication."""
        try:
            # Get authenticated URL
            auth_url = await self._get_auth_url()

            # Clone repository
            logger.info(f"Cloning repository from {self.repo_url}")
            self._repo = await asyncio.to_thread(
                Repo.clone_from,
                auth_url,
                str(self.local_path),
                depth=1,  # Shallow clone for efficiency
            )

        except git.GitCommandError as e:
            logger.error(f"Git clone failed: {e}")
            # Cleanup on failure
            if self.local_path.exists():
                shutil.rmtree(self.local_path)
            raise GitOperationError(f"Repository clone failed: {e}")

    async def _get_auth_url(self) -> str:
        """Get repository URL with authentication."""
        try:
            await self.auth_manager.get_client()

            # For PAT authentication, use token in URL
            if hasattr(self.auth_manager, "_provider") and self.auth_manager._provider:
                # Extract token from PAT provider
                if hasattr(self.auth_manager._provider, "token"):
                    token = self.auth_manager._provider.token
                    # Build authenticated URL
                    return self.repo_url.replace(
                        "https://github.com/", f"https://{token}@github.com/"
                    )

            # Fallback to regular URL
            return self.repo_url

        except Exception as e:
            logger.warning(f"Failed to get authenticated URL: {e}")
            return self.repo_url

    async def _update_remote(self) -> None:
        """Update remote URL with authentication."""
        if not self._repo:
            return

        try:
            auth_url = await self._get_auth_url()
            origin = self._repo.remotes.origin

            # Update remote URL if different
            if origin.url != auth_url:
                await asyncio.to_thread(origin.set_url, auth_url)
                logger.debug("Updated remote URL with authentication")

        except Exception as e:
            logger.warning(f"Failed to update remote URL: {e}")

    async def _verify_repository(self) -> None:
        """Verify repository is in good state."""
        if not self._repo:
            raise GitOperationError("Repository not initialized")

        try:
            # Check if repository is valid
            if self._repo.bare:
                raise GitOperationError("Repository is bare")

            # Try to access HEAD
            if not self._repo.heads:
                raise GitOperationError("Repository has no branches")

            # Pull latest changes
            await self._pull_changes()

        except git.GitCommandError as e:
            logger.error(f"Repository verification failed: {e}")
            raise GitOperationError(f"Repository verification failed: {e}")

    async def _pull_changes(self) -> None:
        """Pull latest changes from remote."""
        if not self._repo:
            return

        try:
            origin = self._repo.remotes.origin
            current_branch = self._repo.active_branch.name

            logger.debug(f"Pulling changes from origin/{current_branch}")
            await asyncio.to_thread(origin.pull, current_branch)

        except Exception as e:
            logger.warning(f"Failed to pull changes: {e}")
            # Don't raise error, just log warning

    async def create_files(self, operations: List[FileOperation]) -> Dict[str, Any]:
        """Create multiple files in a batch operation."""
        if not self._initialized:
            await self.initialize()

        if not operations:
            return {"success": True, "files_created": 0, "commit_sha": None}

        async with self._lock:
            try:
                # Pull latest changes first
                await self._pull_changes()

                # Process file operations
                created_files = []
                for operation in operations:
                    file_path = await self._process_operation(operation)
                    created_files.append(str(file_path))

                if not created_files:
                    return {"success": True, "files_created": 0, "commit_sha": None}

                # Ensure repository is available
                if not self._repo:
                    raise GitOperationError("Repository not initialized")

                # Stage all changes
                await asyncio.to_thread(self._repo.git.add, "--all")

                # Check if there are changes to commit
                if not self._repo.is_dirty():
                    logger.info("No changes to commit")
                    return {"success": True, "files_created": 0, "commit_sha": None}

                # Create commit message
                commit_message = self._generate_batch_commit_message(operations)

                # Commit changes
                commit = await asyncio.to_thread(self._repo.index.commit, commit_message)

                # Push changes
                await self._push_changes()

                result = {
                    "success": True,
                    "files_created": len(created_files),
                    "created_files": created_files,
                    "commit_sha": commit.hexsha,
                    "commit_message": commit_message,
                }

                logger.info(f"Successfully processed {len(created_files)} file operations")
                return result

            except Exception as e:
                logger.error(f"Batch file operation failed: {e}")
                # Try to reset to clean state
                try:
                    if self._repo:
                        await asyncio.to_thread(self._repo.git.reset, "--hard", "HEAD")
                except Exception as reset_error:
                    logger.error(f"Failed to reset repository: {reset_error}")

                raise GitOperationError(f"File operation failed: {e}")

    async def _process_operation(self, operation: FileOperation) -> Path:
        """Process a single file operation."""
        if not self._repo:
            raise GitOperationError("Repository not initialized")

        target_path = self.local_path / operation.file_path

        # Ensure directory exists
        target_path.parent.mkdir(parents=True, exist_ok=True)

        if operation.operation == "create" or operation.operation == "update":
            # Write file content
            await asyncio.to_thread(target_path.write_text, operation.content, encoding="utf-8")
            logger.debug(f"Created/updated file: {target_path}")

        elif operation.operation == "delete":
            # Delete file if exists
            if target_path.exists():
                await asyncio.to_thread(target_path.unlink)
                logger.debug(f"Deleted file: {target_path}")
        else:
            raise GitOperationError(f"Unsupported operation: {operation.operation}")

        return target_path

    def _generate_batch_commit_message(self, operations: List[FileOperation]) -> str:
        """Generate commit message for batch operations."""
        if len(operations) == 1:
            op = operations[0]
            custom_msg = op.commit_message
            if custom_msg:
                return custom_msg
            return f"{op.operation}: {op.file_path}"

        # Multiple operations
        create_count = sum(1 for op in operations if op.operation == "create")
        update_count = sum(1 for op in operations if op.operation == "update")
        delete_count = sum(1 for op in operations if op.operation == "delete")

        parts = []
        if create_count > 0:
            parts.append(f"create {create_count} file{'s' if create_count > 1 else ''}")
        if update_count > 0:
            parts.append(f"update {update_count} file{'s' if update_count > 1 else ''}")
        if delete_count > 0:
            parts.append(f"delete {delete_count} file{'s' if delete_count > 1 else ''}")

        message = f"batch: {', '.join(parts)}"

        # Add file list if reasonable number
        if len(operations) <= 5:
            file_list = ", ".join(str(op.file_path) for op in operations)
            message += f" ({file_list})"

        return message

    async def _push_changes(self) -> None:
        """Push changes to remote repository."""
        if not self._repo:
            raise GitOperationError("Repository not initialized")

        try:
            origin = self._repo.remotes.origin
            current_branch = self._repo.active_branch.name

            logger.debug(f"Pushing changes to origin/{current_branch}")
            await asyncio.to_thread(origin.push, current_branch)

        except git.GitCommandError as e:
            logger.error(f"Push failed: {e}")
            raise GitOperationError(f"Push failed: {e}")

    async def get_file_content(self, file_path: str) -> Optional[str]:
        """Get content of a file from the repository."""
        if not self._initialized:
            await self.initialize()

        target_path = self.local_path / file_path

        try:
            if target_path.exists():
                return await asyncio.to_thread(target_path.read_text, encoding="utf-8")
            return None
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return None

    async def file_exists(self, file_path: str) -> bool:
        """Check if a file exists in the repository."""
        if not self._initialized:
            await self.initialize()

        target_path = self.local_path / file_path
        return target_path.exists()

    async def list_files(self, directory: str = "", pattern: str = "*") -> List[str]:
        """List files in repository directory."""
        if not self._initialized:
            await self.initialize()

        target_dir = self.local_path / directory if directory else self.local_path

        try:
            if not target_dir.exists():
                return []

            # Use glob to find matching files
            files = list(target_dir.glob(pattern))
            # Return relative paths
            return [str(f.relative_to(self.local_path)) for f in files if f.is_file()]

        except Exception as e:
            logger.error(f"Failed to list files in {directory}: {e}")
            return []

    async def get_repository_status(self) -> Dict[str, Any]:
        """Get repository status information."""
        if not self._repo or not self._initialized:
            return {"initialized": False}

        try:
            status = {
                "initialized": True,
                "local_path": str(self.local_path),
                "remote_url": self.repo_url,
                "current_branch": self._repo.active_branch.name,
                "is_dirty": self._repo.is_dirty(),
                "untracked_files": self._repo.untracked_files,
                "head_commit": self._repo.head.commit.hexsha[:8],
                "head_message": self._repo.head.commit.message.strip(),
            }

            return status

        except Exception as e:
            logger.error(f"Failed to get repository status: {e}")
            return {"initialized": True, "error": str(e)}

    async def cleanup(self) -> None:
        """Clean up Git resources."""
        async with self._lock:
            if self._repo:
                # Close repository
                self._repo.close()
                self._repo = None

            self._initialized = False
            logger.info("Git operations cleanup completed")
