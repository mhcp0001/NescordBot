"""
Test cases for GitOperationService.

Tests cover Git repository operations, file management, and authentication integration.
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.nescordbot.services.git_operations import (
    FileOperation,
    GitOperationError,
    GitOperationService,
)


class MockConfig:
    """Mock configuration for testing."""

    def __init__(self, **kwargs):
        self.github_repo_owner = kwargs.get("github_repo_owner", "test_owner")
        self.github_repo_name = kwargs.get("github_repo_name", "test_repo")
        self.github_obsidian_base_path = kwargs.get("github_obsidian_base_path", "data/repos")
        self.instance_id = kwargs.get("instance_id", "test_instance")


class MockAuthManager:
    """Mock authentication manager for testing."""

    def __init__(self):
        self._provider = MagicMock()
        self._provider.token = "test_token"

    async def get_client(self):
        return MagicMock()


@pytest.fixture
def mock_config():
    """Create mock configuration."""
    return MockConfig()


@pytest.fixture
def mock_auth_manager():
    """Create mock authentication manager."""
    return MockAuthManager()


@pytest.fixture
def temp_dir():
    """Create temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


class TestFileOperation:
    """Test FileOperation data class."""

    def test_file_operation_creation(self):
        """Test FileOperation creation."""
        op = FileOperation(
            filename="test.md",
            content="# Test Content",
            directory="notes",
            operation="create",
            commit_message="Add test file",
        )

        assert op.filename == "test.md"
        assert op.content == "# Test Content"
        assert op.directory == "notes"
        assert op.operation == "create"
        assert op.commit_message == "Add test file"
        # Handle both Windows and Unix path separators
        assert "notes" in str(op.file_path)
        assert "test.md" in str(op.file_path)

    def test_file_operation_no_directory(self):
        """Test FileOperation with no directory."""
        op = FileOperation(filename="test.md", content="# Test Content")

        assert str(op.file_path) == "test.md"

    def test_file_operation_repr(self):
        """Test FileOperation string representation."""
        op = FileOperation("test.md", "content", "notes", "create")
        # Handle both Windows and Unix path separators
        result = repr(op)
        assert "FileOperation(create: notes" in result
        assert "test.md)" in result


class TestGitOperationService:
    """Test Git operations service."""

    def test_init_missing_repo_config(self):
        """Test initialization with missing repository configuration."""
        config = MockConfig(github_repo_owner=None)
        auth_manager = MockAuthManager()

        with pytest.raises(GitOperationError, match="Repository owner and name must be configured"):
            GitOperationService(config, auth_manager)  # type: ignore

    def test_build_repo_url(self, mock_config, mock_auth_manager):
        """Test repository URL building."""
        service = GitOperationService(mock_config, mock_auth_manager)  # type: ignore
        expected = "https://github.com/test_owner/test_repo.git"
        assert service.repo_url == expected

    def test_generate_instance_id(self, mock_config, mock_auth_manager):
        """Test instance ID generation."""
        service = GitOperationService(mock_config, mock_auth_manager)  # type: ignore
        # Should generate consistent ID for same config
        instance_id1 = service._generate_instance_id()
        instance_id2 = service._generate_instance_id()
        assert instance_id1 == instance_id2
        assert len(instance_id1) == 8  # MD5 hash truncated to 8 chars

    @pytest.mark.asyncio
    async def test_get_auth_url_with_token(self, mock_config, mock_auth_manager, temp_dir):
        """Test authenticated URL generation with token."""
        # Override base path to use temp directory
        mock_config.github_obsidian_base_path = str(temp_dir)
        service = GitOperationService(mock_config, mock_auth_manager)  # type: ignore

        auth_url = await service._get_auth_url()
        expected = "https://test_token@github.com/test_owner/test_repo.git"
        assert auth_url == expected

    @pytest.mark.asyncio
    async def test_get_auth_url_fallback(self, mock_config, temp_dir):
        """Test authenticated URL fallback."""
        # Mock auth manager without token
        mock_auth_manager = AsyncMock()
        mock_auth_manager.get_client.side_effect = Exception("Auth error")

        mock_config.github_obsidian_base_path = str(temp_dir)
        service = GitOperationService(mock_config, mock_auth_manager)  # type: ignore

        auth_url = await service._get_auth_url()
        assert auth_url == service.repo_url

    @pytest.mark.asyncio
    async def test_initialize_clone_repository(self, mock_config, mock_auth_manager, temp_dir):
        """Test repository initialization with cloning."""
        mock_config.github_obsidian_base_path = str(temp_dir)
        service = GitOperationService(mock_config, mock_auth_manager)  # type: ignore

        # Mock Git operations
        mock_repo = MagicMock()
        mock_repo.bare = False
        mock_repo.heads = [MagicMock()]
        mock_repo.remotes.origin.pull = MagicMock()

        with patch("git.Repo.clone_from", return_value=mock_repo) as mock_clone, patch(
            "asyncio.to_thread", side_effect=lambda func, *args, **kwargs: func(*args, **kwargs)
        ):
            await service.initialize()

            assert service._initialized is True
            assert service._repo is mock_repo
            mock_clone.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_existing_repository(self, mock_config, mock_auth_manager, temp_dir):
        """Test repository initialization with existing repo."""
        mock_config.github_obsidian_base_path = str(temp_dir)
        service = GitOperationService(mock_config, mock_auth_manager)  # type: ignore

        # Create local path to simulate existing repository
        service.local_path.mkdir(parents=True)

        # Mock Git operations
        mock_repo = MagicMock()
        mock_repo.bare = False
        mock_repo.heads = [MagicMock()]
        mock_repo.remotes.origin.url = service.repo_url
        mock_repo.remotes.origin.pull = MagicMock()

        with patch("git.Repo", return_value=mock_repo) as mock_repo_init, patch(
            "asyncio.to_thread", side_effect=lambda func, *args, **kwargs: func(*args, **kwargs)
        ):
            await service.initialize()

            assert service._initialized is True
            assert service._repo is mock_repo
            mock_repo_init.assert_called_once_with(str(service.local_path))

    @pytest.mark.asyncio
    async def test_initialize_clone_failure(self, mock_config, mock_auth_manager, temp_dir):
        """Test repository initialization clone failure."""
        mock_config.github_obsidian_base_path = str(temp_dir)
        service = GitOperationService(mock_config, mock_auth_manager)  # type: ignore

        with patch("git.Repo.clone_from", side_effect=Exception("Clone failed")), patch(
            "asyncio.to_thread", side_effect=lambda func, *args, **kwargs: func(*args, **kwargs)
        ):
            with pytest.raises(GitOperationError, match="Repository initialization failed"):
                await service.initialize()

    @pytest.mark.asyncio
    async def test_create_files_single_operation(self, mock_config, mock_auth_manager, temp_dir):
        """Test creating a single file."""
        mock_config.github_obsidian_base_path = str(temp_dir)
        service = GitOperationService(mock_config, mock_auth_manager)  # type: ignore

        # Mock repository
        mock_repo = MagicMock()
        mock_repo.bare = False
        mock_repo.heads = [MagicMock()]
        mock_repo.remotes.origin.pull = MagicMock()
        mock_repo.remotes.origin.push = MagicMock()
        mock_repo.git.add = MagicMock()
        mock_repo.is_dirty.return_value = True

        # Mock commit
        mock_commit = MagicMock()
        mock_commit.hexsha = "abc123def456"
        mock_repo.index.commit.return_value = mock_commit

        service._repo = mock_repo
        service._initialized = True

        # Create file operation
        operation = FileOperation(
            filename="test.md", content="# Test Content", directory="notes", operation="create"
        )

        with patch(
            "asyncio.to_thread", side_effect=lambda func, *args, **kwargs: func(*args, **kwargs)
        ), patch.object(service.local_path, "exists", return_value=True):
            result = await service.create_files([operation])

            assert result["success"] is True
            assert result["files_created"] == 1
            assert result["commit_sha"] == "abc123def456"
            assert "test.md" in result["created_files"][0]

    @pytest.mark.asyncio
    async def test_create_files_no_changes(self, mock_config, mock_auth_manager, temp_dir):
        """Test creating files with no changes needed."""
        mock_config.github_obsidian_base_path = str(temp_dir)
        service = GitOperationService(mock_config, mock_auth_manager)  # type: ignore

        # Mock repository with no changes
        mock_repo = MagicMock()
        mock_repo.remotes.origin.pull = MagicMock()
        mock_repo.git.add = MagicMock()
        mock_repo.is_dirty.return_value = False  # No changes

        service._repo = mock_repo
        service._initialized = True

        operation = FileOperation("test.md", "content")

        with patch(
            "asyncio.to_thread", side_effect=lambda func, *args, **kwargs: func(*args, **kwargs)
        ):
            result = await service.create_files([operation])

            assert result["success"] is True
            assert result["files_created"] == 0
            assert result["commit_sha"] is None

    @pytest.mark.asyncio
    async def test_create_files_empty_list(self, mock_config, mock_auth_manager, temp_dir):
        """Test creating files with empty operation list."""
        mock_config.github_obsidian_base_path = str(temp_dir)
        service = GitOperationService(mock_config, mock_auth_manager)  # type: ignore
        service._initialized = True

        result = await service.create_files([])

        assert result["success"] is True
        assert result["files_created"] == 0
        assert result["commit_sha"] is None

    @pytest.mark.asyncio
    async def test_create_files_commit_failure(self, mock_config, mock_auth_manager, temp_dir):
        """Test file creation with commit failure."""
        mock_config.github_obsidian_base_path = str(temp_dir)
        service = GitOperationService(mock_config, mock_auth_manager)  # type: ignore

        # Mock repository that fails on commit
        mock_repo = MagicMock()
        mock_repo.remotes.origin.pull = MagicMock()
        mock_repo.git.add = MagicMock()
        mock_repo.is_dirty.return_value = True
        mock_repo.index.commit.side_effect = Exception("Commit failed")
        mock_repo.git.reset = MagicMock()  # For cleanup

        service._repo = mock_repo
        service._initialized = True

        operation = FileOperation("test.md", "content")

        with patch(
            "asyncio.to_thread", side_effect=lambda func, *args, **kwargs: func(*args, **kwargs)
        ):
            with pytest.raises(GitOperationError, match="File operation failed"):
                await service.create_files([operation])

    def test_generate_batch_commit_message_single(self, mock_config, mock_auth_manager, temp_dir):
        """Test commit message generation for single operation."""
        mock_config.github_obsidian_base_path = str(temp_dir)
        service = GitOperationService(mock_config, mock_auth_manager)  # type: ignore

        # Single operation with custom message
        op1 = FileOperation("test.md", "content", commit_message="Custom message")
        message = service._generate_batch_commit_message([op1])
        assert message == "Custom message"

        # Single operation without custom message
        op2 = FileOperation("test.md", "content", operation="create")
        message = service._generate_batch_commit_message([op2])
        assert message == "create: test.md"

    def test_generate_batch_commit_message_multiple(self, mock_config, mock_auth_manager, temp_dir):
        """Test commit message generation for multiple operations."""
        mock_config.github_obsidian_base_path = str(temp_dir)
        service = GitOperationService(mock_config, mock_auth_manager)  # type: ignore

        operations = [
            FileOperation("file1.md", "content1", operation="create"),
            FileOperation("file2.md", "content2", operation="create"),
            FileOperation("file3.md", "content3", operation="update"),
        ]

        message = service._generate_batch_commit_message(operations)
        assert "batch: create 2 files, update 1 file" in message
        assert "(file1.md, file2.md, file3.md)" in message

    @pytest.mark.asyncio
    async def test_get_file_content_exists(self, mock_config, mock_auth_manager, temp_dir):
        """Test getting content of existing file."""
        mock_config.github_obsidian_base_path = str(temp_dir)
        service = GitOperationService(mock_config, mock_auth_manager)  # type: ignore
        service._initialized = True

        # Create test file
        test_file = service.local_path / "test.md"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_content = "# Test Content"

        with patch("pathlib.Path.exists", return_value=True), patch(
            "asyncio.to_thread", return_value=test_content
        ):
            content = await service.get_file_content("test.md")
            assert content == test_content

    @pytest.mark.asyncio
    async def test_get_file_content_not_exists(self, mock_config, mock_auth_manager, temp_dir):
        """Test getting content of non-existent file."""
        mock_config.github_obsidian_base_path = str(temp_dir)
        service = GitOperationService(mock_config, mock_auth_manager)  # type: ignore
        service._initialized = True

        content = await service.get_file_content("nonexistent.md")
        assert content is None

    @pytest.mark.asyncio
    async def test_file_exists(self, mock_config, mock_auth_manager, temp_dir):
        """Test file existence check."""
        mock_config.github_obsidian_base_path = str(temp_dir)
        service = GitOperationService(mock_config, mock_auth_manager)  # type: ignore
        service._initialized = True

        with patch("pathlib.Path.exists", return_value=True):
            exists = await service.file_exists("test.md")
            assert exists is True

        with patch("pathlib.Path.exists", return_value=False):
            exists = await service.file_exists("test.md")
            assert exists is False

    @pytest.mark.asyncio
    async def test_get_repository_status_initialized(
        self, mock_config, mock_auth_manager, temp_dir
    ):
        """Test getting repository status when initialized."""
        mock_config.github_obsidian_base_path = str(temp_dir)
        service = GitOperationService(mock_config, mock_auth_manager)  # type: ignore

        # Mock repository
        mock_commit = MagicMock()
        mock_commit.hexsha = "abc123def456789"
        mock_commit.message = "Test commit\n"

        mock_repo = MagicMock()
        mock_repo.active_branch.name = "main"
        mock_repo.is_dirty.return_value = False
        mock_repo.untracked_files = []
        mock_repo.head.commit = mock_commit

        service._repo = mock_repo
        service._initialized = True

        status = await service.get_repository_status()

        assert status["initialized"] is True
        assert status["current_branch"] == "main"
        assert status["is_dirty"] is False
        assert status["head_commit"] == "abc123de"
        assert status["head_message"] == "Test commit"

    @pytest.mark.asyncio
    async def test_get_repository_status_not_initialized(
        self, mock_config, mock_auth_manager, temp_dir
    ):
        """Test getting repository status when not initialized."""
        mock_config.github_obsidian_base_path = str(temp_dir)
        service = GitOperationService(mock_config, mock_auth_manager)  # type: ignore

        status = await service.get_repository_status()
        assert status["initialized"] is False

    @pytest.mark.asyncio
    async def test_cleanup(self, mock_config, mock_auth_manager, temp_dir):
        """Test service cleanup."""
        mock_config.github_obsidian_base_path = str(temp_dir)
        service = GitOperationService(mock_config, mock_auth_manager)  # type: ignore

        # Mock repository
        mock_repo = MagicMock()
        service._repo = mock_repo
        service._initialized = True

        await service.cleanup()

        mock_repo.close.assert_called_once()
        assert service._repo is None
        assert service._initialized is False
