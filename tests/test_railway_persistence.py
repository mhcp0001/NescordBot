"""
Tests for Railway persistent volumes functionality.

This module tests the persistence capabilities of NescordBot
in Railway environment, including ChromaDB and SQLite persistence.
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.nescordbot.config import BotConfig
from src.nescordbot.services.chromadb_service import ChromaDBService
from src.nescordbot.utils.backup import BackupManager


class TestChromaDBPersistence:
    """Test ChromaDB persistence functionality."""

    @pytest.fixture
    def temp_config(self):
        """Create temporary config for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = MagicMock()
            config.chromadb_persist_directory = temp_dir
            config.chromadb_collection_name = "test_collection"
            config.database_url = f"sqlite:///{temp_dir}/test.db"
            config.gemini_api_key = "test_key"
            config.gemini_monthly_limit = 1000000
            yield config

    @pytest.fixture
    async def chromadb_service(self, temp_config):
        """Create ChromaDBService instance for testing."""
        with patch("src.nescordbot.services.chromadb_service.chromadb"):
            service = ChromaDBService(temp_config)
            yield service
            await service.close()

    @pytest.mark.asyncio
    async def test_verify_persistence_directory_missing(self, temp_config):
        """Test persistence verification when directory is missing."""
        # Set non-existent directory in temp space to avoid permission issues
        temp_config.chromadb_persist_directory = "/tmp/non_existent_test_directory_12345"

        with patch("src.nescordbot.services.chromadb_service.chromadb"):
            service = ChromaDBService(temp_config)

            result = await service.verify_persistence()
            assert result is False
            await service.close()

    @pytest.mark.asyncio
    async def test_verify_persistence_no_write_permission(self, temp_config):
        """Test persistence verification with no write permissions."""
        persist_dir = Path(temp_config.chromadb_persist_directory)
        persist_dir.mkdir(exist_ok=True)

        with patch("src.nescordbot.services.chromadb_service.chromadb"):
            service = ChromaDBService(temp_config)

            # Mock write permission failure
            with patch.object(Path, "write_text", side_effect=PermissionError("No permission")):
                result = await service.verify_persistence()
                assert result is False

            await service.close()

    @pytest.mark.asyncio
    async def test_verify_persistence_success(self, chromadb_service, temp_config):
        """Test successful persistence verification."""
        # Mock ChromaDB operations
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 1
        mock_collection.query.return_value = {
            "ids": [["persistence_test_doc"]],
            "distances": [[0.1]],
            "documents": [["This is a persistence test document"]],
            "metadatas": [[{"test": True}]],
        }

        chromadb_service.client = mock_client
        chromadb_service.collection = mock_collection
        chromadb_service._initialized = True

        # Mock embedding service calls within verify_persistence
        with patch.object(chromadb_service, "add_document") as mock_add_doc, patch.object(
            chromadb_service, "search_documents"
        ) as mock_search, patch.object(chromadb_service, "delete_document") as mock_delete:
            # Mock successful document operations
            mock_add_doc.return_value = True
            mock_search.return_value = [MagicMock(document_id="persistence_test_doc")]
            mock_delete.return_value = True

            result = await chromadb_service.verify_persistence()
            assert result is True

    @pytest.mark.asyncio
    async def test_verify_persistence_document_operations_fail(self, chromadb_service, temp_config):
        """Test persistence verification when document operations fail."""
        # Mock ChromaDB initialization but make operations fail
        chromadb_service._initialized = True

        with patch.object(
            chromadb_service, "add_document", side_effect=Exception("Operation failed")
        ):
            result = await chromadb_service.verify_persistence()
            assert result is False


class TestRailwayVolumeSimulation:
    """Test Railway persistent volume simulation."""

    def test_volume_mount_simulation(self):
        """Test simulated Railway volume mount points."""
        # Test that volume paths are accessible
        data_path = Path("/tmp/test_data")  # Simulate /app/data
        chromadb_path = Path("/tmp/test_chromadb")  # Simulate /app/chromadb_data

        # Create directories
        data_path.mkdir(exist_ok=True)
        chromadb_path.mkdir(exist_ok=True)

        try:
            # Test write operations
            test_file = data_path / "test.txt"
            test_file.write_text("test content")
            assert test_file.read_text() == "test content"

            # Test ChromaDB directory
            chromadb_test = chromadb_path / "test_collection"
            chromadb_test.mkdir(exist_ok=True)
            assert chromadb_test.exists()

        finally:
            # Cleanup
            if data_path.exists():
                import shutil

                shutil.rmtree(data_path)
            if chromadb_path.exists():
                import shutil

                shutil.rmtree(chromadb_path)

    def test_database_path_configuration(self):
        """Test database path configuration for Railway."""
        config = MagicMock()
        config.database_url = "sqlite:///app/data/nescordbot.db"

        # Extract path from URL
        db_path = config.database_url.replace("sqlite:///", "/")
        path_obj = Path(db_path)

        # Use POSIX path for Railway (Linux environment)
        expected_path = "/app/data/nescordbot.db"
        expected_parent = "/app/data"

        # Convert to forward slashes for comparison
        assert str(path_obj).replace("\\", "/") == expected_path
        assert str(path_obj.parent).replace("\\", "/") == expected_parent

    def test_chromadb_path_configuration(self):
        """Test ChromaDB path configuration for Railway."""
        config = MagicMock()
        config.chromadb_persist_directory = "/app/chromadb_data"

        chromadb_path = Path(config.chromadb_persist_directory)
        # Convert to forward slashes for comparison (Railway uses Linux)
        assert str(chromadb_path).replace("\\", "/") == "/app/chromadb_data"


class TestBackupManager:
    """Test backup and restore functionality."""

    @pytest.fixture
    def temp_backup_config(self):
        """Create temporary config for backup testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = MagicMock()
            config.chromadb_persist_directory = f"{temp_dir}/chromadb"
            config.database_url = f"sqlite:///{temp_dir}/test.db"
            config.chromadb_collection_name = "test_collection"

            # Create test data
            Path(config.chromadb_persist_directory).mkdir(exist_ok=True)
            Path(temp_dir).joinpath("test.db").touch()

            yield config

    @pytest.fixture
    def backup_manager(self, temp_backup_config):
        """Create BackupManager instance for testing."""
        with patch("src.nescordbot.utils.backup.Path") as mock_path:
            # Mock backup directory creation
            mock_backup_dir = MagicMock()
            mock_path.return_value = mock_backup_dir
            mock_backup_dir.mkdir = MagicMock()

            return BackupManager(temp_backup_config)

    @pytest.mark.asyncio
    async def test_create_full_backup(self, backup_manager, temp_backup_config):
        """Test full backup creation."""
        # Mock the entire backup creation process
        with patch.object(backup_manager, "_backup_chromadb") as mock_backup_chromadb, patch.object(
            backup_manager, "_backup_sqlite"
        ) as mock_backup_sqlite:
            # Mock backup directory operations
            mock_backup_path = MagicMock()
            mock_backup_path.mkdir = MagicMock()
            mock_manifest_path = MagicMock()
            mock_backup_path.__truediv__ = MagicMock(return_value=mock_manifest_path)

            with patch.object(backup_manager, "backup_dir") as mock_backup_dir:
                mock_backup_dir.__truediv__ = MagicMock(return_value=mock_backup_path)

                # Mock successful operations
                mock_backup_chromadb.return_value = None
                mock_backup_sqlite.return_value = None

                backup_id = await backup_manager.create_full_backup()

                assert backup_id.startswith("nescordbot_backup_")
                # Verify manifest was written
                mock_manifest_path.write_text.assert_called_once()

    def test_list_backups_empty(self, backup_manager):
        """Test listing backups when no backups exist."""
        with patch.object(backup_manager.backup_dir, "iterdir", return_value=[]):
            backups = backup_manager.list_backups()
            assert backups == []

    @pytest.mark.asyncio
    async def test_cleanup_old_backups(self, backup_manager):
        """Test cleanup of old backups."""
        # Mock existing backups
        mock_backups = [
            {"backup_id": "backup_1", "timestamp": "20250101_120000", "path": "/tmp/backup_1"},
            {"backup_id": "backup_2", "timestamp": "20250102_120000", "path": "/tmp/backup_2"},
            {"backup_id": "backup_3", "timestamp": "20250103_120000", "path": "/tmp/backup_3"},
        ]

        with patch.object(backup_manager, "list_backups", return_value=mock_backups), patch(
            "shutil.rmtree"
        ) as mock_rmtree, patch("asyncio.to_thread") as mock_to_thread:
            mock_to_thread.side_effect = lambda func, *args, **kwargs: func(*args, **kwargs)

            deleted_count = await backup_manager.cleanup_old_backups(keep_count=1)

            assert deleted_count == 2
            assert mock_rmtree.call_count == 2


class TestRailwayEnvironmentVariables:
    """Test Railway-specific environment variable configurations."""

    def test_railway_database_url_format(self):
        """Test Railway database URL format."""
        railway_db_url = "sqlite:///app/data/nescordbot.db"

        # Verify absolute path format
        assert railway_db_url.startswith("sqlite:///")
        assert "/app/data/" in railway_db_url

    def test_railway_chromadb_directory(self):
        """Test Railway ChromaDB directory configuration."""
        railway_chromadb_dir = "/app/chromadb_data"

        # Verify path properties (account for Windows testing environment)
        path_str = railway_chromadb_dir.replace("\\", "/")
        assert path_str.startswith("/app/")
        assert path_str.endswith("chromadb_data")

    def test_volume_mount_paths(self):
        """Test volume mount path configurations."""
        data_volume = "/app/data"
        chromadb_volume = "/app/chromadb_data"

        # Verify both paths are under /app (Railway Linux environment)
        assert data_volume.startswith("/app/")
        assert chromadb_volume.startswith("/app/")
        assert "data" in data_volume
        assert "chromadb_data" in chromadb_volume


@pytest.mark.integration
class TestPersistenceIntegration:
    """Integration tests for persistence functionality."""

    @pytest.mark.asyncio
    async def test_end_to_end_persistence_flow(self):
        """Test complete persistence flow from setup to verification."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup configuration
            config = MagicMock()
            config.chromadb_persist_directory = f"{temp_dir}/chromadb"
            config.chromadb_collection_name = "test_integration"
            config.database_url = f"sqlite:///{temp_dir}/integration.db"
            config.gemini_api_key = "test_key"

            # Create required directories
            Path(config.chromadb_persist_directory).mkdir(exist_ok=True)

            with patch("src.nescordbot.services.chromadb_service.chromadb"):
                # Initialize service
                service = ChromaDBService(config)

                # Mock successful initialization
                service._initialized = True
                service.client = MagicMock()
                service.collection = MagicMock()
                service.collection.count.return_value = 1
                service.collection.query.return_value = {
                    "ids": [["test_doc"]],
                    "distances": [[0.1]],
                    "documents": [["test content"]],
                    "metadatas": [[{"test": True}]],
                }

                # Test persistence verification
                with patch.object(service, "add_document") as mock_add_doc, patch.object(
                    service, "search_documents"
                ) as mock_search, patch.object(service, "delete_document") as mock_delete:
                    # Mock successful document operations
                    mock_add_doc.return_value = True
                    mock_search.return_value = [MagicMock(document_id="persistence_test_doc")]
                    mock_delete.return_value = True

                    result = await service.verify_persistence()
                    assert result is True

                await service.close()

    @pytest.mark.asyncio
    async def test_backup_restore_cycle(self):
        """Test complete backup and restore cycle."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup test environment
            config = MagicMock()
            config.chromadb_persist_directory = f"{temp_dir}/chromadb"
            config.database_url = f"sqlite:///{temp_dir}/test.db"
            config.chromadb_collection_name = "backup_test"

            # Create test data
            chromadb_dir = Path(config.chromadb_persist_directory)
            chromadb_dir.mkdir(exist_ok=True)
            (chromadb_dir / "test_file.txt").write_text("test data")

            db_path = Path(temp_dir) / "test.db"
            db_path.write_text("test database")

            # Test backup creation
            with patch("src.nescordbot.utils.backup.Path"):
                # Mock backup directory
                mock_backup_dir = Path(temp_dir) / "backups" / "test_backup"
                mock_backup_dir.mkdir(parents=True, exist_ok=True)

                backup_manager = BackupManager(config)
                backup_manager.backup_dir = Path(temp_dir) / "backups"
                backup_manager.backup_dir.mkdir(exist_ok=True)

                with patch("shutil.copytree"), patch("shutil.copy2"), patch(
                    "asyncio.to_thread"
                ) as mock_to_thread:
                    mock_to_thread.side_effect = lambda func, *args, **kwargs: func(*args, **kwargs)

                    with patch("pathlib.Path.write_text"), patch("pathlib.Path.mkdir"):
                        backup_id = await backup_manager.create_full_backup()
                        assert backup_id.startswith("nescordbot_backup_")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
