"""
Git operations service for GitHub-Obsidian integration.

This module provides Git repository management, file operations,
and batch processing capabilities for synchronizing Obsidian files with GitHub.
"""

import asyncio
import logging
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

from ..config import get_config
from ..security import SecurityError, SecurityValidator

logger = logging.getLogger(__name__)


@dataclass
class GitOperationResult:
    """Result of a Git operation."""

    success: bool
    message: str
    files_affected: Optional[List[str]] = None
    commit_hash: Optional[str] = None
    error: Optional[Exception] = None

    def __post_init__(self):
        if self.files_affected is None:
            self.files_affected = []


@dataclass
class BatchOperation:
    """Represents a batch operation for Git processing."""

    operation_id: str
    operation_type: str  # 'add', 'update', 'delete'
    file_path: str
    content: Optional[str] = None
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class GitOperationError(Exception):
    """Git operation specific errors."""

    pass


class GitOperationService:
    """
    Service for handling Git operations for GitHub-Obsidian integration.

    This service provides:
    - Repository initialization and management
    - File operations (add, update, delete)
    - Batch processing with queuing
    - Conflict resolution
    - Error handling and recovery
    """

    def __init__(self, working_directory: Optional[str] = None):
        """
        Initialize Git operation service.

        Args:
            working_directory: Base directory for Git operations.
                              Defaults to data/git_repos/
        """
        self.config = get_config()
        self.instance_id = self._get_instance_id()

        # Set up working directory
        if working_directory:
            self.working_dir = Path(working_directory)
        else:
            self.working_dir = Path("data") / "git_repos" / self.instance_id

        self.working_dir.mkdir(parents=True, exist_ok=True)

        # Repository cache
        self._repo_cache: Dict[str, Repo] = {}

        # Batch operation queue
        self._batch_queue: List[BatchOperation] = []
        self._batch_lock = asyncio.Lock()

        # Security validator
        self.security = SecurityValidator()

        logger.info(f"GitOperationService initialized with working_dir: {self.working_dir}")

    def _get_instance_id(self) -> str:
        """Get unique instance identifier."""
        from ..config import get_config_manager

        manager = get_config_manager()
        if hasattr(manager, "get_instance_id"):
            return str(manager.get_instance_id())
        return "default"

    def _get_repo_path(self, repo_name: str) -> Path:
        """Get local repository path."""
        sanitized_name = str(self.security.sanitize_filename(repo_name))
        return self.working_dir / sanitized_name

    def _validate_repository_access(self, repo_name: str) -> None:
        """Validate repository access permissions."""
        github_enabled = getattr(self.config, "github_obsidian_enabled", False)
        if not github_enabled:
            raise GitOperationError("GitHub-Obsidian integration is not enabled")

        if not self.config.github_token:
            raise GitOperationError("GitHub token is required")

        if not self.config.github_repo_owner or not self.config.github_repo_name:
            raise GitOperationError("GitHub repository owner and name are required")

    async def initialize_repository(self, force_clean: bool = False) -> GitOperationResult:
        """
        Initialize local Git repository for GitHub integration.

        Args:
            force_clean: Whether to clean existing repository

        Returns:
            GitOperationResult with initialization status
        """
        try:
            repo_name = self.config.github_repo_name
            if not repo_name:
                return GitOperationResult(
                    success=False, message="GitHub repository name is not configured"
                )

            self._validate_repository_access(repo_name)
            repo_path = self._get_repo_path(repo_name)

            # Clean existing repository if requested
            if force_clean and repo_path.exists():
                shutil.rmtree(repo_path)
                logger.info(f"Cleaned existing repository: {repo_path}")

            # Check if repository already exists and is valid
            if repo_path.exists():
                try:
                    repo = Repo(repo_path)
                    if not repo.bare:
                        # Verify remote configuration
                        if self._verify_remote_config(repo):
                            self._repo_cache[repo_name] = repo
                            return GitOperationResult(
                                success=True, message=f"Repository already initialized: {repo_path}"
                            )
                        else:
                            logger.warning("Remote configuration mismatch, re-cloning repository")
                            shutil.rmtree(repo_path)
                except InvalidGitRepositoryError:
                    logger.warning(f"Invalid Git repository found, cleaning: {repo_path}")
                    shutil.rmtree(repo_path)

            # Clone repository
            return await self._clone_repository(repo_name, repo_path)

        except Exception as e:
            logger.error(f"Failed to initialize repository: {e}")
            return GitOperationResult(
                success=False, message=f"Repository initialization failed: {str(e)}", error=e
            )

    def _verify_remote_config(self, repo: Repo) -> bool:
        """Verify that remote configuration matches current settings."""
        try:
            origin = repo.remotes.origin
            expected_url = self._get_repository_url()

            # Check if any of the URLs match (Git can have multiple URLs)
            for url in origin.urls:
                if expected_url in url or url in expected_url:
                    return True

            return False
        except Exception:
            return False

    def _get_repository_url(self) -> str:
        """Get GitHub repository URL with authentication."""
        owner = self.config.github_repo_owner
        repo = self.config.github_repo_name
        token = self.config.github_token

        # Use token-based authentication
        return f"https://{token}@github.com/{owner}/{repo}.git"

    async def _clone_repository(self, repo_name: str, repo_path: Path) -> GitOperationResult:
        """Clone repository from GitHub."""
        try:
            repo_url = self._get_repository_url()
            branch = getattr(self.config, "github_obsidian_branch", "main")

            logger.info(f"Cloning repository: {self.config.github_repo_owner}/{repo_name}")

            # Clone with specific branch
            repo = Repo.clone_from(
                repo_url, repo_path, branch=branch, depth=1  # Shallow clone for efficiency
            )

            # Cache repository
            self._repo_cache[repo_name] = repo

            logger.info(f"Successfully cloned repository to: {repo_path}")

            return GitOperationResult(
                success=True, message=f"Repository cloned successfully: {repo_path}"
            )

        except GitCommandError as e:
            logger.error(f"Git command failed during clone: {e}")
            return GitOperationResult(
                success=False, message=f"Failed to clone repository: {str(e)}", error=e
            )

    def get_repository(self, repo_name: Optional[str] = None) -> Optional[Repo]:
        """
        Get cached repository instance.

        Args:
            repo_name: Repository name. Defaults to configured repo.

        Returns:
            Repo instance if available, None otherwise
        """
        if repo_name is None:
            repo_name = self.config.github_repo_name

        if repo_name:
            return self._repo_cache.get(repo_name)
        return None

    async def add_file(
        self, file_path: str, content: str, commit_message: Optional[str] = None
    ) -> GitOperationResult:
        """
        Add or update a file in the repository.

        Args:
            file_path: Relative path within repository
            content: File content
            commit_message: Optional commit message

        Returns:
            GitOperationResult with operation status
        """
        try:
            # Security validation
            safe_path = self.security.validate_file_path(file_path)
            safe_content = self.security.validate_discord_content(content)

            repo = self.get_repository()
            if not repo:
                return GitOperationResult(success=False, message="Repository not initialized")

            # Full file path
            full_path = Path(repo.working_dir) / safe_path
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file content
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(safe_content)

            # Stage file
            repo.index.add([safe_path])

            # Commit if message provided, otherwise add to batch
            if commit_message:
                commit = repo.index.commit(commit_message)
                return GitOperationResult(
                    success=True,
                    message=f"File added and committed: {safe_path}",
                    files_affected=[safe_path],
                    commit_hash=commit.hexsha,
                )
            else:
                return GitOperationResult(
                    success=True,
                    message=f"File staged for commit: {safe_path}",
                    files_affected=[safe_path],
                )

        except SecurityError as e:
            logger.warning(f"Security validation failed for file operation: {e}")
            return GitOperationResult(
                success=False, message=f"Security validation failed: {str(e)}", error=e
            )
        except Exception as e:
            logger.error(f"Failed to add file {file_path}: {e}")
            return GitOperationResult(
                success=False, message=f"Failed to add file: {str(e)}", error=e
            )

    async def remove_file(
        self, file_path: str, commit_message: Optional[str] = None
    ) -> GitOperationResult:
        """
        Remove a file from the repository.

        Args:
            file_path: Relative path within repository
            commit_message: Optional commit message

        Returns:
            GitOperationResult with operation status
        """
        try:
            # Security validation
            safe_path = self.security.validate_file_path(file_path)

            repo = self.get_repository()
            if not repo:
                return GitOperationResult(success=False, message="Repository not initialized")

            # Check if file exists
            full_path = Path(repo.working_dir) / safe_path
            if not full_path.exists():
                return GitOperationResult(
                    success=False, message=f"File does not exist: {safe_path}"
                )

            # Remove file from filesystem and index
            full_path.unlink()
            repo.index.remove([safe_path])

            # Commit if message provided
            if commit_message:
                commit = repo.index.commit(commit_message)
                return GitOperationResult(
                    success=True,
                    message=f"File removed and committed: {safe_path}",
                    files_affected=[safe_path],
                    commit_hash=commit.hexsha,
                )
            else:
                return GitOperationResult(
                    success=True,
                    message=f"File staged for removal: {safe_path}",
                    files_affected=[safe_path],
                )

        except SecurityError as e:
            logger.warning(f"Security validation failed for file removal: {e}")
            return GitOperationResult(
                success=False, message=f"Security validation failed: {str(e)}", error=e
            )
        except Exception as e:
            logger.error(f"Failed to remove file {file_path}: {e}")
            return GitOperationResult(
                success=False, message=f"Failed to remove file: {str(e)}", error=e
            )

    async def commit_changes(self, message: str) -> GitOperationResult:
        """
        Commit all staged changes.

        Args:
            message: Commit message

        Returns:
            GitOperationResult with commit status
        """
        try:
            repo = self.get_repository()
            if not repo:
                return GitOperationResult(success=False, message="Repository not initialized")

            # Check if there are staged changes
            if not repo.index.diff("HEAD"):
                return GitOperationResult(success=True, message="No changes to commit")

            # Get list of staged files
            staged_files = [item.a_path for item in repo.index.diff("HEAD") if item.a_path]

            # Commit changes
            commit = repo.index.commit(message)

            return GitOperationResult(
                success=True,
                message="Changes committed successfully",
                files_affected=staged_files,
                commit_hash=commit.hexsha,
            )

        except Exception as e:
            logger.error(f"Failed to commit changes: {e}")
            return GitOperationResult(
                success=False, message=f"Failed to commit changes: {str(e)}", error=e
            )

    async def push_changes(self) -> GitOperationResult:
        """
        Push committed changes to remote repository.

        Returns:
            GitOperationResult with push status
        """
        try:
            repo = self.get_repository()
            if not repo:
                return GitOperationResult(success=False, message="Repository not initialized")

            # Check if there are unpushed commits
            branch_name = getattr(self.config, "github_obsidian_branch", "main")
            local_commit = repo.head.commit

            try:
                remote_commit = repo.refs[f"origin/{branch_name}"].commit
                if local_commit == remote_commit:
                    return GitOperationResult(success=True, message="No changes to push")
            except Exception:
                # Remote branch might not exist, proceed with push
                pass

            # Push changes
            origin = repo.remotes.origin
            push_info = origin.push(branch_name)

            # Check push result
            if push_info and push_info[0].flags & push_info[0].ERROR:
                raise GitOperationError(f"Push failed: {push_info[0].summary}")

            return GitOperationResult(
                success=True,
                message="Changes pushed successfully to remote repository",
                commit_hash=local_commit.hexsha,
            )

        except Exception as e:
            logger.error(f"Failed to push changes: {e}")
            return GitOperationResult(
                success=False, message=f"Failed to push changes: {str(e)}", error=e
            )

    async def pull_changes(self) -> GitOperationResult:
        """
        Pull changes from remote repository.

        Returns:
            GitOperationResult with pull status
        """
        try:
            repo = self.get_repository()
            if not repo:
                return GitOperationResult(success=False, message="Repository not initialized")

            # Fetch latest changes
            origin = repo.remotes.origin
            origin.fetch()

            # Get current and remote commit
            branch_name = getattr(self.config, "github_obsidian_branch", "main")
            local_commit = repo.head.commit

            try:
                remote_commit = repo.refs[f"origin/{branch_name}"].commit
                if local_commit == remote_commit:
                    return GitOperationResult(success=True, message="Repository is up to date")
            except Exception:
                return GitOperationResult(success=False, message="Remote branch not found")

            # Pull changes
            pull_info = origin.pull(branch_name)

            # Get affected files
            affected_files: List[str] = []
            if pull_info and pull_info[0].commit:
                diff = local_commit.diff(pull_info[0].commit)
                for item in diff:
                    if item.a_path:
                        affected_files.append(item.a_path)
                    elif item.b_path:
                        affected_files.append(item.b_path)

            return GitOperationResult(
                success=True,
                message="Changes pulled successfully from remote repository",
                files_affected=affected_files,
                commit_hash=repo.head.commit.hexsha,
            )

        except Exception as e:
            logger.error(f"Failed to pull changes: {e}")
            return GitOperationResult(
                success=False, message=f"Failed to pull changes: {str(e)}", error=e
            )

    async def get_file_content(self, file_path: str) -> Tuple[bool, str]:
        """
        Get content of a file from the repository.

        Args:
            file_path: Relative path within repository

        Returns:
            Tuple of (success, content or error message)
        """
        try:
            # Security validation
            safe_path = self.security.validate_file_path(file_path)

            repo = self.get_repository()
            if not repo:
                return False, "Repository not initialized"

            # Full file path
            full_path = Path(repo.working_dir) / safe_path

            if not full_path.exists():
                return False, f"File does not exist: {safe_path}"

            # Read file content
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()

            return True, content

        except SecurityError as e:
            logger.warning(f"Security validation failed for file read: {e}")
            return False, f"Security validation failed: {str(e)}"
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return False, f"Failed to read file: {str(e)}"

    async def list_files(self, directory: str = "") -> Tuple[bool, List[str]]:
        """
        List files in repository directory.

        Args:
            directory: Relative directory path (empty for root)

        Returns:
            Tuple of (success, list of file paths or error message)
        """
        try:
            repo = self.get_repository()
            if not repo:
                return False, ["Repository not initialized"]

            # Validate directory path if provided
            if directory:
                safe_dir = self.security.validate_file_path(directory)
                search_path = Path(repo.working_dir) / safe_dir
            else:
                search_path = Path(repo.working_dir)

            if not search_path.exists():
                return False, [f"Directory does not exist: {directory}"]

            # Get all files recursively
            files = []
            for file_path in search_path.rglob("*"):
                if file_path.is_file() and not str(file_path).startswith(".git"):
                    # Get relative path from repository root
                    rel_path = file_path.relative_to(repo.working_dir)
                    files.append(str(rel_path).replace("\\", "/"))

            return True, sorted(files)

        except SecurityError as e:
            logger.warning(f"Security validation failed for directory listing: {e}")
            return False, [f"Security validation failed: {str(e)}"]
        except Exception as e:
            logger.error(f"Failed to list files in {directory}: {e}")
            return False, [f"Failed to list files: {str(e)}"]

    async def add_to_batch(
        self, operation_type: str, file_path: str, content: Optional[str] = None
    ) -> str:
        """
        Add operation to batch queue.

        Args:
            operation_type: Type of operation ('add', 'update', 'delete')
            file_path: Relative path within repository
            content: File content (for add/update operations)

        Returns:
            Operation ID for tracking
        """
        async with self._batch_lock:
            operation_id = f"{operation_type}_{len(self._batch_queue)}_{datetime.now().timestamp()}"

            operation = BatchOperation(
                operation_id=operation_id,
                operation_type=operation_type,
                file_path=file_path,
                content=content,
            )

            self._batch_queue.append(operation)
            logger.debug(f"Added operation to batch queue: {operation_id}")

            return operation_id

    async def process_batch(self, commit_message: Optional[str] = None) -> GitOperationResult:
        """
        Process all operations in the batch queue.

        Args:
            commit_message: Optional commit message for the batch

        Returns:
            GitOperationResult with batch processing status
        """
        async with self._batch_lock:
            if not self._batch_queue:
                return GitOperationResult(success=True, message="No operations in batch queue")

            try:
                repo = self.get_repository()
                if not repo:
                    return GitOperationResult(success=False, message="Repository not initialized")

                processed_files: List[str] = []
                failed_operations: List[str] = []

                # Process each operation
                for operation in self._batch_queue:
                    try:
                        if operation.operation_type in ["add", "update"]:
                            result = await self._process_add_operation(operation)
                        elif operation.operation_type == "delete":
                            result = await self._process_delete_operation(operation)
                        else:
                            logger.warning(f"Unknown operation type: {operation.operation_type}")
                            continue

                        if result.success and result.files_affected:
                            processed_files.extend(result.files_affected)
                        else:
                            failed_operations.append(operation.operation_id)

                    except Exception as e:
                        logger.error(f"Failed to process operation {operation.operation_id}: {e}")
                        failed_operations.append(operation.operation_id)

                # Commit all changes if any files were processed
                commit_result = None
                if processed_files:
                    if not commit_message:
                        commit_message = f"Batch operation: {len(processed_files)} files updated"

                    commit_result = await self.commit_changes(commit_message)

                # Clear processed operations
                self._batch_queue.clear()

                if failed_operations:
                    return GitOperationResult(
                        success=False,
                        message=(
                            f"Batch processing completed with " f"{len(failed_operations)} failures"
                        ),
                        files_affected=processed_files,
                        commit_hash=commit_result.commit_hash if commit_result else None,
                    )
                else:
                    return GitOperationResult(
                        success=True,
                        message=(
                            f"Batch processing completed successfully: "
                            f"{len(processed_files)} files"
                        ),
                        files_affected=processed_files,
                        commit_hash=commit_result.commit_hash if commit_result else None,
                    )

            except Exception as e:
                logger.error(f"Batch processing failed: {e}")
                return GitOperationResult(
                    success=False, message=f"Batch processing failed: {str(e)}", error=e
                )

    async def _process_add_operation(self, operation: BatchOperation) -> GitOperationResult:
        """Process add/update operation without committing."""
        try:
            # Security validation
            safe_path = self.security.validate_file_path(operation.file_path)
            safe_content = self.security.validate_discord_content(operation.content or "")

            repo = self.get_repository()
            if not repo:
                return GitOperationResult(success=False, message="Repository not initialized")

            # Full file path
            full_path = Path(repo.working_dir) / safe_path
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file content
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(safe_content)

            # Stage file
            repo.index.add([safe_path])

            return GitOperationResult(
                success=True, message=f"File staged: {safe_path}", files_affected=[safe_path]
            )

        except Exception as e:
            logger.error(f"Failed to process add operation for {operation.file_path}: {e}")
            return GitOperationResult(
                success=False, message=f"Failed to process add operation: {str(e)}", error=e
            )

    async def _process_delete_operation(self, operation: BatchOperation) -> GitOperationResult:
        """Process delete operation without committing."""
        try:
            # Security validation
            safe_path = self.security.validate_file_path(operation.file_path)

            repo = self.get_repository()
            if not repo:
                return GitOperationResult(success=False, message="Repository not initialized")

            # Full file path
            full_path = Path(repo.working_dir) / safe_path

            if not full_path.exists():
                return GitOperationResult(
                    success=True,  # File already doesn't exist
                    message=f"File already removed: {safe_path}",
                    files_affected=[],
                )

            # Remove file from filesystem and index
            full_path.unlink()
            repo.index.remove([safe_path])

            return GitOperationResult(
                success=True, message=f"File removed: {safe_path}", files_affected=[safe_path]
            )

        except Exception as e:
            logger.error(f"Failed to process delete operation for {operation.file_path}: {e}")
            return GitOperationResult(
                success=False, message=f"Failed to process delete operation: {str(e)}", error=e
            )

    async def get_batch_status(self) -> Dict[str, Any]:
        """
        Get current status of batch queue.

        Returns:
            Dictionary with queue status information
        """
        async with self._batch_lock:
            return {
                "queue_size": len(self._batch_queue),
                "operations": [
                    {
                        "id": op.operation_id,
                        "type": op.operation_type,
                        "file": op.file_path,
                        "timestamp": op.timestamp.isoformat() if op.timestamp else "",
                    }
                    for op in self._batch_queue
                ],
            }

    async def clear_batch_queue(self) -> GitOperationResult:
        """
        Clear all operations from batch queue without processing.

        Returns:
            GitOperationResult with clear status
        """
        async with self._batch_lock:
            queue_size = len(self._batch_queue)
            self._batch_queue.clear()

            return GitOperationResult(
                success=True, message=f"Batch queue cleared: {queue_size} operations removed"
            )

    async def sync_with_remote(self) -> GitOperationResult:
        """
        Synchronize local repository with remote (pull then push).

        Returns:
            GitOperationResult with sync status
        """
        try:
            # First pull changes from remote
            pull_result = await self.pull_changes()
            if not pull_result.success:
                return pull_result

            # Then push local changes
            push_result = await self.push_changes()
            if not push_result.success:
                return push_result

            return GitOperationResult(
                success=True,
                message="Repository synchronized with remote successfully",
                files_affected=pull_result.files_affected,
                commit_hash=push_result.commit_hash,
            )

        except Exception as e:
            logger.error(f"Failed to sync with remote: {e}")
            return GitOperationResult(
                success=False, message=f"Failed to sync with remote: {str(e)}", error=e
            )

    async def get_repository_status(self) -> Dict[str, Any]:
        """
        Get comprehensive repository status information.

        Returns:
            Dictionary with repository status
        """
        try:
            repo = self.get_repository()
            if not repo:
                return {"initialized": False, "error": "Repository not initialized"}

            # Get basic repository information
            status = {
                "initialized": True,
                "working_directory": str(repo.working_dir),
                "current_branch": repo.active_branch.name,
                "remote_url": repo.remotes.origin.url if repo.remotes else None,
                "last_commit": {
                    "hash": repo.head.commit.hexsha[:8],
                    "message": repo.head.commit.message.strip(),
                    "author": str(repo.head.commit.author),
                    "date": repo.head.commit.committed_datetime.isoformat(),
                },
                "files": {"total": 0, "staged": [], "modified": [], "untracked": []},
            }

            # Get file status
            staged_files = [item.a_path for item in repo.index.diff("HEAD")]
            modified_files = [item.a_path for item in repo.index.diff(None)]
            untracked_files = list(repo.untracked_files)

            files_dict = status["files"]
            if isinstance(files_dict, dict):
                files_dict.update(
                    {
                        "staged": staged_files,
                        "modified": modified_files,
                        "untracked": untracked_files,
                        "total": len(list(Path(repo.working_dir).rglob("*")))
                        - len(list(Path(repo.working_dir).glob(".git/**/*"))),
                    }
                )

            return status

        except Exception as e:
            logger.error(f"Failed to get repository status: {e}")
            return {"initialized": False, "error": str(e)}

    def cleanup(self) -> None:
        """Clean up resources and temporary files."""
        try:
            # Clear repository cache
            self._repo_cache.clear()

            # Clear batch queue
            self._batch_queue.clear()

            logger.info("GitOperationService cleanup completed")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
