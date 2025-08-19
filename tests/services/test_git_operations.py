"""
Tests for Git operations service.
"""

import asyncio
import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nescordbot.security import SecurityError
from nescordbot.services.git_operations import (
    BatchOperation,
    GitOperationError,
    GitOperationResult,
    GitOperationService,
)


class TestGitOperationService:
    """Test cases for GitOperationService."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def mock_config(self):
        """Mock configuration for tests."""
        config = MagicMock()
        config.github_obsidian_enabled = True
        config.github_token = "test_token"
        config.github_repo_owner = "test_owner"
        config.github_repo_name = "test_repo"
        config.github_obsidian_branch = "main"
        return config

    @pytest.fixture
    def git_service(self, temp_dir, mock_config):
        """Create GitOperationService instance for testing."""
        with patch("nescordbot.services.git_operations.get_config", return_value=mock_config):
            service = GitOperationService(working_directory=str(temp_dir))
            return service

    def test_init(self, git_service, temp_dir):
        """Test GitOperationService initialization."""
        assert git_service.working_dir == temp_dir
        assert len(git_service._repo_cache) == 0
        assert len(git_service._batch_queue) == 0

    def test_get_repo_path(self, git_service):
        """Test repository path generation."""
        repo_path = git_service._get_repo_path("test-repo")
        assert "test-repo" in str(repo_path)
        assert git_service.working_dir in repo_path.parents

    def test_validate_repository_access_disabled(self, git_service):
        """Test validation when integration is disabled."""
        git_service.config.github_obsidian_enabled = False

        with pytest.raises(GitOperationError, match="not enabled"):
            git_service._validate_repository_access("test_repo")

    def test_validate_repository_access_no_token(self, git_service):
        """Test validation when token is missing."""
        git_service.config.github_token = None

        with pytest.raises(GitOperationError, match="token is required"):
            git_service._validate_repository_access("test_repo")

    def test_validate_repository_access_no_repo_info(self, git_service):
        """Test validation when repository info is missing."""
        git_service.config.github_repo_owner = None

        with pytest.raises(GitOperationError, match="owner and name are required"):
            git_service._validate_repository_access("test_repo")

    def test_get_repository_url(self, git_service):
        """Test repository URL generation."""
        url = git_service._get_repository_url()
        expected = "https://test_token@github.com/test_owner/test_repo.git"
        assert url == expected

    @pytest.mark.asyncio
    async def test_add_to_batch(self, git_service):
        """Test adding operations to batch queue."""
        operation_id = await git_service.add_to_batch("add", "test.md", "test content")

        assert len(git_service._batch_queue) == 1
        assert operation_id.startswith("add_")

        operation = git_service._batch_queue[0]
        assert operation.operation_type == "add"
        assert operation.file_path == "test.md"
        assert operation.content == "test content"

    @pytest.mark.asyncio
    async def test_get_batch_status(self, git_service):
        """Test getting batch queue status."""
        await git_service.add_to_batch("add", "test1.md", "content1")
        await git_service.add_to_batch("update", "test2.md", "content2")

        status = await git_service.get_batch_status()

        assert status["queue_size"] == 2
        assert len(status["operations"]) == 2
        assert status["operations"][0]["type"] == "add"
        assert status["operations"][1]["type"] == "update"

    @pytest.mark.asyncio
    async def test_clear_batch_queue(self, git_service):
        """Test clearing batch queue."""
        await git_service.add_to_batch("add", "test.md", "content")
        assert len(git_service._batch_queue) == 1

        result = await git_service.clear_batch_queue()

        assert result.success
        assert len(git_service._batch_queue) == 0
        assert "1 operations removed" in result.message

    @patch("nescordbot.services.git_operations.Repo")
    @pytest.mark.asyncio
    async def test_initialize_repository_new_clone(self, mock_repo_class, git_service):
        """Test repository initialization with new clone."""
        mock_repo = MagicMock()
        mock_repo_class.clone_from.return_value = mock_repo

        result = await git_service.initialize_repository()

        assert result.success
        assert "cloned successfully" in result.message
        mock_repo_class.clone_from.assert_called_once()

    @patch("nescordbot.services.git_operations.Repo")
    @pytest.mark.asyncio
    async def test_initialize_repository_existing_valid(self, mock_repo_class, git_service):
        """Test repository initialization with existing valid repo."""
        # Create fake repository directory
        repo_path = git_service._get_repo_path("test_repo")
        repo_path.mkdir(parents=True)

        # Mock existing repository
        mock_repo = MagicMock()
        mock_repo.bare = False
        mock_repo.remotes.origin.urls = ["https://github.com/test_owner/test_repo.git"]
        mock_repo_class.return_value = mock_repo

        with patch.object(git_service, "_verify_remote_config", return_value=True):
            result = await git_service.initialize_repository()

        assert result.success
        assert "already initialized" in result.message

    @pytest.mark.asyncio
    async def test_add_file_security_validation_failure(self, git_service):
        """Test file addition with security validation failure."""
        # Mock repository
        mock_repo = MagicMock()
        git_service._repo_cache["test_repo"] = mock_repo

        # Mock security validation to raise error
        with patch.object(
            git_service.security, "validate_file_path", side_effect=SecurityError("Invalid path")
        ):
            result = await git_service.add_file("../dangerous/path", "content")

        assert not result.success
        assert "Security validation failed" in result.message

    @patch("builtins.open", create=True)
    @pytest.mark.asyncio
    async def test_add_file_success(self, mock_open, git_service):
        """Test successful file addition."""
        # Mock repository
        mock_repo = MagicMock()
        mock_repo.working_dir = str(git_service.working_dir)
        git_service._repo_cache["test_repo"] = mock_repo

        # Mock file operations
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        result = await git_service.add_file("test.md", "test content", "Add test file")

        assert result.success
        assert "test.md" in result.files_affected
        mock_repo.index.add.assert_called_once_with(["test.md"])
        mock_repo.index.commit.assert_called_once_with("Add test file")

    @pytest.mark.asyncio
    async def test_add_file_no_repository(self, git_service):
        """Test file addition when repository is not initialized."""
        result = await git_service.add_file("test.md", "content")

        assert not result.success
        assert "Repository not initialized" in result.message

    @pytest.mark.asyncio
    async def test_remove_file_success(self, git_service, temp_dir):
        """Test successful file removal."""
        # Mock repository
        mock_repo = MagicMock()
        mock_repo.working_dir = str(temp_dir)
        git_service._repo_cache["test_repo"] = mock_repo

        # Create test file
        test_file = temp_dir / "test.md"
        test_file.write_text("test content")

        result = await git_service.remove_file("test.md", "Remove test file")

        assert result.success
        assert "test.md" in result.files_affected
        assert not test_file.exists()
        mock_repo.index.remove.assert_called_once_with(["test.md"])

    @pytest.mark.asyncio
    async def test_remove_file_not_exists(self, git_service):
        """Test file removal when file doesn't exist."""
        # Mock repository
        mock_repo = MagicMock()
        mock_repo.working_dir = str(git_service.working_dir)
        git_service._repo_cache["test_repo"] = mock_repo

        result = await git_service.remove_file("nonexistent.md")

        assert not result.success
        assert "does not exist" in result.message

    @pytest.mark.asyncio
    async def test_commit_changes_success(self, git_service):
        """Test successful commit of changes."""
        # Mock repository with staged changes
        mock_repo = MagicMock()
        mock_diff_item = MagicMock()
        mock_diff_item.a_path = "test.md"
        mock_repo.index.diff.return_value = [mock_diff_item]

        mock_commit = MagicMock()
        mock_commit.hexsha = "abc123"
        mock_repo.index.commit.return_value = mock_commit

        git_service._repo_cache["test_repo"] = mock_repo

        result = await git_service.commit_changes("Test commit")

        assert result.success
        assert result.commit_hash == "abc123"
        assert "test.md" in result.files_affected
        mock_repo.index.commit.assert_called_once_with("Test commit")

    @pytest.mark.asyncio
    async def test_commit_changes_no_changes(self, git_service):
        """Test commit when there are no changes."""
        # Mock repository with no staged changes
        mock_repo = MagicMock()
        mock_repo.index.diff.return_value = []
        git_service._repo_cache["test_repo"] = mock_repo

        result = await git_service.commit_changes("Test commit")

        assert result.success
        assert "No changes to commit" in result.message
        mock_repo.index.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_file_content_success(self, git_service, temp_dir):
        """Test successful file content retrieval."""
        # Mock repository
        mock_repo = MagicMock()
        mock_repo.working_dir = str(temp_dir)
        git_service._repo_cache["test_repo"] = mock_repo

        # Create test file
        test_file = temp_dir / "test.md"
        test_file.write_text("test content")

        success, content = await git_service.get_file_content("test.md")

        assert success
        assert content == "test content"

    @pytest.mark.asyncio
    async def test_get_file_content_not_exists(self, git_service):
        """Test file content retrieval when file doesn't exist."""
        # Mock repository
        mock_repo = MagicMock()
        mock_repo.working_dir = str(git_service.working_dir)
        git_service._repo_cache["test_repo"] = mock_repo

        success, message = await git_service.get_file_content("nonexistent.md")

        assert not success
        assert "does not exist" in message

    @pytest.mark.asyncio
    async def test_list_files_success(self, git_service, temp_dir):
        """Test successful file listing."""
        # Mock repository
        mock_repo = MagicMock()
        mock_repo.working_dir = str(temp_dir)
        git_service._repo_cache["test_repo"] = mock_repo

        # Create test files
        (temp_dir / "file1.md").write_text("content1")
        (temp_dir / "subdir").mkdir()
        (temp_dir / "subdir" / "file2.md").write_text("content2")

        success, files = await git_service.list_files()

        assert success
        assert "file1.md" in files
        assert "subdir/file2.md" in files

    @pytest.mark.asyncio
    async def test_process_batch_no_operations(self, git_service):
        """Test batch processing with empty queue."""
        result = await git_service.process_batch()

        assert result.success
        assert "No operations in batch queue" in result.message

    @pytest.mark.asyncio
    async def test_process_batch_success(self, git_service, temp_dir):
        """Test successful batch processing."""
        # Mock repository
        mock_repo = MagicMock()
        mock_repo.working_dir = str(temp_dir)
        mock_repo.index.diff.return_value = []  # No staged changes initially

        mock_commit = MagicMock()
        mock_commit.hexsha = "abc123"
        mock_repo.index.commit.return_value = mock_commit

        git_service._repo_cache["test_repo"] = mock_repo

        # Add operations to batch
        await git_service.add_to_batch("add", "test1.md", "content1")
        await git_service.add_to_batch("add", "test2.md", "content2")

        # Mock file operations and commit_changes method
        with patch("builtins.open", create=True), patch.object(
            git_service, "commit_changes"
        ) as mock_commit:
            # Mock commit_changes return value
            mock_commit_result = GitOperationResult(
                success=True, message="Committed", commit_hash="abc123"
            )
            mock_commit.return_value = mock_commit_result

            result = await git_service.process_batch("Batch commit")

        assert result.success
        assert len(result.files_affected) == 2
        assert result.commit_hash == "abc123"
        assert len(git_service._batch_queue) == 0  # Queue should be cleared

    @pytest.mark.asyncio
    async def test_get_repository_status_not_initialized(self, git_service):
        """Test repository status when not initialized."""
        status = await git_service.get_repository_status()

        assert not status["initialized"]
        assert "not initialized" in status["error"]

    @pytest.mark.asyncio
    async def test_get_repository_status_success(self, git_service):
        """Test successful repository status retrieval."""
        # Mock repository
        mock_repo = MagicMock()
        mock_repo.working_dir = str(git_service.working_dir)
        mock_repo.active_branch.name = "main"
        mock_repo.remotes.origin.url = "https://github.com/test/repo.git"

        # Mock commit
        mock_commit = MagicMock()
        mock_commit.hexsha = "abcdef123456"
        mock_commit.message = "Test commit\n"
        mock_commit.author = "Test Author"
        mock_commit.committed_datetime.isoformat.return_value = "2023-01-01T00:00:00"
        mock_repo.head.commit = mock_commit

        # Mock file status
        mock_repo.index.diff.return_value = []
        mock_repo.untracked_files = []

        git_service._repo_cache["test_repo"] = mock_repo

        with patch("pathlib.Path.rglob", return_value=[]), patch(
            "pathlib.Path.glob", return_value=[]
        ):
            status = await git_service.get_repository_status()

        assert status["initialized"]
        assert status["current_branch"] == "main"
        assert status["last_commit"]["hash"] == "abcdef12"

    def test_cleanup(self, git_service):
        """Test service cleanup."""
        # Add some data to clean up
        git_service._repo_cache["test"] = MagicMock()
        git_service._batch_queue.append(BatchOperation("1", "add", "test.md"))

        git_service.cleanup()

        assert len(git_service._repo_cache) == 0
        assert len(git_service._batch_queue) == 0


class TestGitOperationResult:
    """Test cases for GitOperationResult."""

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        result = GitOperationResult(success=True, message="Test")

        assert result.success
        assert result.message == "Test"
        assert result.files_affected == []
        assert result.commit_hash is None
        assert result.error is None

    def test_init_with_all_values(self):
        """Test initialization with all values."""
        error = Exception("Test error")
        result = GitOperationResult(
            success=False,
            message="Failed",
            files_affected=["file1.md", "file2.md"],
            commit_hash="abc123",
            error=error,
        )

        assert not result.success
        assert result.message == "Failed"
        assert result.files_affected == ["file1.md", "file2.md"]
        assert result.commit_hash == "abc123"
        assert result.error == error


class TestBatchOperation:
    """Test cases for BatchOperation."""

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        operation = BatchOperation("1", "add", "test.md")

        assert operation.operation_id == "1"
        assert operation.operation_type == "add"
        assert operation.file_path == "test.md"
        assert operation.content is None
        assert operation.timestamp is not None

    def test_init_with_all_values(self):
        """Test initialization with all values."""
        from datetime import datetime

        timestamp = datetime(2023, 1, 1)
        operation = BatchOperation("1", "update", "test.md", "content", timestamp)

        assert operation.operation_id == "1"
        assert operation.operation_type == "update"
        assert operation.file_path == "test.md"
        assert operation.content == "content"
        assert operation.timestamp == timestamp
