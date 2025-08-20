"""
Test cases for ObsidianGitHubService.

Tests cover integration service functionality, status management,
and error handling scenarios.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.nescordbot.services.obsidian_github import ObsidianGitHubService, ObsidianSyncStatus


@pytest.fixture
def mock_config():
    """Mock configuration object"""
    config = MagicMock()
    config.github_repo_owner = "test_owner"
    config.github_repo_name = "test_repo"
    config.github_obsidian_enabled = True
    config.github_obsidian_base_path = "obsidian_sync"
    config.github_obsidian_branch = "main"
    config.github_obsidian_batch_size = 5
    config.github_obsidian_batch_interval = 10
    return config


@pytest.fixture
def mock_components():
    """Mock all service components"""
    batch_processor = AsyncMock()
    security_validator = MagicMock()

    # Configure security validator
    def sanitize_filename_side_effect(filename):
        return filename if filename == "test.md" or "test" in filename else "sanitized.md"

    security_validator.sanitize_filename.side_effect = sanitize_filename_side_effect
    security_validator.validate_discord_content.return_value = "content"

    def validate_file_path_side_effect(path):
        return path if path in ["notes", "documents"] else "safe_path"

    security_validator.validate_file_path.side_effect = validate_file_path_side_effect

    return {
        "batch_processor": batch_processor,
        "security_validator": security_validator,
    }


@pytest.fixture
async def obsidian_service(mock_config, mock_components):
    """Create ObsidianGitHubService instance for testing"""
    service = ObsidianGitHubService(
        config=mock_config,
        batch_processor=mock_components["batch_processor"],
        security_validator=mock_components["security_validator"],
    )
    yield service
    await service.shutdown()


class TestObsidianGitHubServiceInitialization:
    """Test service initialization"""

    async def test_initialize_success(self, obsidian_service, mock_components):
        """Test successful initialization"""
        await obsidian_service.initialize()

        assert obsidian_service._initialized is True
        mock_components["batch_processor"].initialize.assert_called_once()

    async def test_initialize_idempotent(self, obsidian_service, mock_components):
        """Test that multiple initialize calls are safe"""
        await obsidian_service.initialize()
        await obsidian_service.initialize()

        # Should only be called once
        assert mock_components["batch_processor"].initialize.call_count == 1

    async def test_operation_without_initialization_fails(self, obsidian_service):
        """Test that operations fail without initialization"""
        with pytest.raises(RuntimeError, match="サービスが初期化されていません"):
            await obsidian_service.save_to_obsidian("test.md", "content")


class TestObsidianSaveToObsidian:
    """Test save_to_obsidian functionality"""

    async def test_save_to_obsidian_success(self, obsidian_service, mock_components):
        """Test successful file save request"""
        await obsidian_service.initialize()
        mock_components["batch_processor"].enqueue_file_request.return_value = 123

        request_id = await obsidian_service.save_to_obsidian(
            filename="test.md",
            content="# Test Content",
            directory="notes",
            metadata={"type": "test"},
        )

        assert request_id is not None
        assert len(request_id) == 36  # UUID length

        # Verify batch processor enqueue was called
        mock_components["batch_processor"].enqueue_file_request.assert_called_once()
        call_args = mock_components["batch_processor"].enqueue_file_request.call_args
        assert call_args[1]["filename"] == "test.md"
        assert call_args[1]["content"] == "# Test Content"
        assert call_args[1]["directory"] == "notes"
        assert call_args[1]["idempotency_key"] == request_id

        # Verify status cache
        status = await obsidian_service.get_status(request_id)
        assert status is not None
        assert status.status == "queued"
        assert status.file_path == "notes/test.md"

    async def test_save_to_obsidian_default_directory(self, obsidian_service, mock_components):
        """Test save with default directory"""
        await obsidian_service.initialize()
        mock_components["batch_processor"].enqueue_file_request.return_value = 123

        await obsidian_service.save_to_obsidian(
            filename="test.md",
            content="content",
        )

        call_args = mock_components["batch_processor"].enqueue_file_request.call_args
        assert call_args[1]["directory"] == "notes"  # default directory

    async def test_save_to_obsidian_security_validation_filename(
        self, obsidian_service, mock_components
    ):
        """Test security validation for filename"""
        await obsidian_service.initialize()
        mock_components["security_validator"].sanitize_filename.return_value = "sanitized.md"

        with pytest.raises(ValueError, match="無効なファイル名"):
            await obsidian_service.save_to_obsidian("../../../evil.md", "content")

    async def test_save_to_obsidian_security_validation_content(
        self, obsidian_service, mock_components
    ):
        """Test security validation for content"""
        await obsidian_service.initialize()
        mock_components["security_validator"].validate_discord_content.side_effect = Exception(
            "XSS detected"
        )

        with pytest.raises(ValueError, match="無効なコンテンツが検出されました"):
            await obsidian_service.save_to_obsidian("test.md", "<script>alert('xss')</script>")

    async def test_save_to_obsidian_security_validation_path(
        self, obsidian_service, mock_components
    ):
        """Test security validation for directory path"""
        await obsidian_service.initialize()
        mock_components["security_validator"].validate_file_path.return_value = "safe_path"

        with pytest.raises(ValueError, match="無効なディレクトリパス"):
            await obsidian_service.save_to_obsidian("test.md", "content", directory="../../../")


class TestObsidianStatusManagement:
    """Test status management functionality"""

    async def test_get_status_existing(self, obsidian_service, mock_components):
        """Test getting status for existing request"""
        await obsidian_service.initialize()
        mock_components["batch_processor"].enqueue_file_request.return_value = 123

        request_id = await obsidian_service.save_to_obsidian("test.md", "content")
        status = await obsidian_service.get_status(request_id)

        assert status is not None
        assert status.request_id == request_id
        assert status.status == "queued"

    async def test_get_status_nonexistent(self, obsidian_service):
        """Test getting status for non-existent request"""
        await obsidian_service.initialize()

        status = await obsidian_service.get_status("non-existent-id")
        assert status is None

    async def test_list_recent_requests(self, obsidian_service, mock_components):
        """Test listing recent requests"""
        await obsidian_service.initialize()
        mock_components["batch_processor"].enqueue_file_request.return_value = 123

        # Create multiple requests
        request_ids = []
        for i in range(3):
            request_id = await obsidian_service.save_to_obsidian(f"test{i}.md", f"content{i}")
            request_ids.append(request_id)

        recent = await obsidian_service.list_recent_requests(limit=2)

        assert len(recent) == 2
        # Should be sorted by creation time (newest first)
        assert recent[0].created_at >= recent[1].created_at

    async def test_cleanup_old_status(self, obsidian_service):
        """Test cleanup of old status entries"""
        await obsidian_service.initialize()

        # Create old status manually
        old_status = ObsidianSyncStatus(
            request_id="old-request",
            status="completed",
            created_at=datetime.now(timezone.utc) - timedelta(days=10),
            updated_at=datetime.now(timezone.utc) - timedelta(days=10),
            file_path="old/file.md",
        )
        obsidian_service._status_cache["old-request"] = old_status

        # Create recent status
        recent_status = ObsidianSyncStatus(
            request_id="recent-request",
            status="queued",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            file_path="recent/file.md",
        )
        obsidian_service._status_cache["recent-request"] = recent_status

        removed_count = await obsidian_service.cleanup_old_status(days=7)

        assert removed_count == 1
        assert "old-request" not in obsidian_service._status_cache
        assert "recent-request" in obsidian_service._status_cache


class TestObsidianProcessingStatistics:
    """Test processing statistics functionality"""

    async def test_get_processing_statistics_success(self, obsidian_service, mock_components):
        """Test getting processing statistics"""
        await obsidian_service.initialize()

        mock_components["batch_processor"].get_processing_status.return_value = {"running": True}

        # Add some status entries
        obsidian_service._status_cache["req1"] = ObsidianSyncStatus(
            request_id="req1",
            status="queued",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            file_path="test1.md",
        )
        obsidian_service._status_cache["req2"] = ObsidianSyncStatus(
            request_id="req2",
            status="completed",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            file_path="test2.md",
        )

        stats = await obsidian_service.get_processing_statistics()

        assert stats["batch_processor"]["running"] is True
        assert stats["status_counts"]["queued"] == 1
        assert stats["status_counts"]["completed"] == 1
        assert stats["total_requests"] == 2

    async def test_get_processing_statistics_not_initialized(self, obsidian_service):
        """Test getting statistics when not initialized"""
        stats = await obsidian_service.get_processing_statistics()

        assert "error" in stats
        assert "サービスが初期化されていません" in stats["error"]

    async def test_get_processing_statistics_exception(self, obsidian_service, mock_components):
        """Test getting statistics with exception"""
        await obsidian_service.initialize()
        mock_components["batch_processor"].get_processing_status.side_effect = Exception(
            "Processing error"
        )

        stats = await obsidian_service.get_processing_statistics()

        assert "error" in stats
        assert "Processing error" in stats["error"]


class TestObsidianProcessingControl:
    """Test processing control functionality"""

    async def test_start_processing(self, obsidian_service, mock_components):
        """Test starting batch processing"""
        await obsidian_service.start_processing()

        # Should initialize if not already done
        mock_components["batch_processor"].initialize.assert_called_once()
        mock_components["batch_processor"].start_processing.assert_called_once()

    async def test_stop_processing(self, obsidian_service, mock_components):
        """Test stopping batch processing"""
        await obsidian_service.stop_processing()

        mock_components["batch_processor"].stop_processing.assert_called_once()

    async def test_shutdown(self, obsidian_service, mock_components):
        """Test service shutdown"""
        await obsidian_service.initialize()

        await obsidian_service.shutdown()

        mock_components["batch_processor"].stop_processing.assert_called_once()
        assert obsidian_service._initialized is False
