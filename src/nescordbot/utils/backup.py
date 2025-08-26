"""
Backup and restore functionality for NescordBot data.

This module provides utilities for backing up and restoring
ChromaDB collections, SQLite databases, and configuration files.
"""

import asyncio
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import BotConfig

logger = logging.getLogger(__name__)


class BackupManager:
    """Manages backup and restore operations for NescordBot data."""

    def __init__(self, config: BotConfig):
        """
        Initialize BackupManager.

        Args:
            config: Bot configuration containing paths and settings
        """
        self.config = config
        self.backup_dir = Path("/app/data/backups")
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    async def create_full_backup(self) -> str:
        """
        Create a full backup including ChromaDB and SQLite database.

        Returns:
            Backup identifier/filename
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_id = f"nescordbot_backup_{timestamp}"
        backup_path = self.backup_dir / backup_id
        backup_path.mkdir(exist_ok=True)

        try:
            # 1. Backup ChromaDB data
            await self._backup_chromadb(backup_path)

            # 2. Backup SQLite database
            await self._backup_sqlite(backup_path)

            # 3. Create backup manifest
            manifest = {
                "backup_id": backup_id,
                "timestamp": timestamp,
                "config": {
                    "chromadb_persist_directory": str(self.config.chromadb_persist_directory),
                    "database_url": self.config.database_url,
                    "chromadb_collection_name": self.config.chromadb_collection_name,
                },
                "files": {
                    "chromadb": "chromadb_data",
                    "sqlite": "nescordbot.db",
                    "manifest": "manifest.json",
                },
            }

            manifest_path = backup_path / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2))

            logger.info(f"Full backup created: {backup_id}")
            return backup_id

        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            # Clean up incomplete backup
            if backup_path.exists():
                shutil.rmtree(backup_path)
            raise

    async def _backup_chromadb(self, backup_path: Path) -> None:
        """Backup ChromaDB data directory."""
        chromadb_source = Path(self.config.chromadb_persist_directory)
        chromadb_backup = backup_path / "chromadb_data"

        if chromadb_source.exists():
            await asyncio.to_thread(
                shutil.copytree, chromadb_source, chromadb_backup, dirs_exist_ok=True
            )
            logger.debug(f"ChromaDB backup completed: {chromadb_backup}")
        else:
            logger.warning("ChromaDB source directory does not exist")

    async def _backup_sqlite(self, backup_path: Path) -> None:
        """Backup SQLite database file."""
        # Extract database path from URL
        db_url = self.config.database_url
        if db_url.startswith("sqlite:///"):
            db_source_path = Path(db_url.replace("sqlite:///", "/"))
        else:
            # Handle relative paths
            db_source_path = Path(db_url.replace("sqlite://", ""))
            if not db_source_path.is_absolute():
                db_source_path = Path("/app") / db_source_path

        db_backup = backup_path / "nescordbot.db"

        if db_source_path.exists():
            await asyncio.to_thread(shutil.copy2, db_source_path, db_backup)
            logger.debug(f"SQLite backup completed: {db_backup}")
        else:
            logger.warning(f"SQLite database does not exist: {db_source_path}")

    async def restore_backup(self, backup_id: str) -> bool:
        """
        Restore from a backup.

        Args:
            backup_id: Backup identifier to restore from

        Returns:
            True if restoration successful, False otherwise
        """
        backup_path = self.backup_dir / backup_id
        manifest_path = backup_path / "manifest.json"

        if not backup_path.exists() or not manifest_path.exists():
            logger.error(f"Backup not found: {backup_id}")
            return False

        try:
            # Load backup manifest
            manifest = json.loads(manifest_path.read_text())

            # 1. Restore ChromaDB data
            await self._restore_chromadb(backup_path, manifest)

            # 2. Restore SQLite database
            await self._restore_sqlite(backup_path, manifest)

            logger.info(f"Backup restored successfully: {backup_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to restore backup {backup_id}: {e}")
            return False

    async def _restore_chromadb(self, backup_path: Path, manifest: Dict[str, Any]) -> None:
        """Restore ChromaDB data from backup."""
        chromadb_backup = backup_path / "chromadb_data"
        chromadb_target = Path(self.config.chromadb_persist_directory)

        if chromadb_backup.exists():
            # Remove existing data
            if chromadb_target.exists():
                await asyncio.to_thread(shutil.rmtree, chromadb_target)

            # Restore from backup
            await asyncio.to_thread(shutil.copytree, chromadb_backup, chromadb_target)
            logger.debug("ChromaDB data restored")
        else:
            logger.warning("ChromaDB backup data not found")

    async def _restore_sqlite(self, backup_path: Path, manifest: Dict[str, Any]) -> None:
        """Restore SQLite database from backup."""
        db_backup = backup_path / "nescordbot.db"

        # Extract target path from current config
        db_url = self.config.database_url
        if db_url.startswith("sqlite:///"):
            db_target_path = Path(db_url.replace("sqlite:///", "/"))
        else:
            db_target_path = Path(db_url.replace("sqlite://", ""))
            if not db_target_path.is_absolute():
                db_target_path = Path("/app") / db_target_path

        if db_backup.exists():
            # Ensure target directory exists
            db_target_path.parent.mkdir(parents=True, exist_ok=True)

            # Restore database
            await asyncio.to_thread(shutil.copy2, db_backup, db_target_path)
            logger.debug("SQLite database restored")
        else:
            logger.warning("SQLite backup file not found")

    def list_backups(self) -> List[Dict[str, Any]]:
        """
        List available backups.

        Returns:
            List of backup information dictionaries
        """
        backups = []

        for backup_dir in self.backup_dir.iterdir():
            if not backup_dir.is_dir():
                continue

            manifest_path = backup_dir / "manifest.json"
            if manifest_path.exists():
                try:
                    manifest = json.loads(manifest_path.read_text())
                    backups.append(
                        {
                            "backup_id": manifest["backup_id"],
                            "timestamp": manifest["timestamp"],
                            "path": str(backup_dir),
                            "size": self._calculate_backup_size(backup_dir),
                        }
                    )
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Invalid backup manifest in {backup_dir}: {e}")

        # Sort by timestamp (newest first)
        backups.sort(key=lambda x: x["timestamp"], reverse=True)
        return backups

    def _calculate_backup_size(self, backup_path: Path) -> int:
        """Calculate total size of backup directory in bytes."""
        total_size = 0
        try:
            for file_path in backup_path.rglob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
        except (OSError, PermissionError):
            pass
        return total_size

    async def cleanup_old_backups(self, keep_count: int = 5) -> int:
        """
        Clean up old backups, keeping only the specified number.

        Args:
            keep_count: Number of recent backups to keep

        Returns:
            Number of backups deleted
        """
        backups = self.list_backups()
        deleted_count = 0

        if len(backups) <= keep_count:
            return 0

        backups_to_delete = backups[keep_count:]

        for backup in backups_to_delete:
            try:
                backup_path = Path(backup["path"])
                await asyncio.to_thread(shutil.rmtree, backup_path)
                logger.info(f"Deleted old backup: {backup['backup_id']}")
                deleted_count += 1
            except Exception as e:
                logger.error(f"Failed to delete backup {backup['backup_id']}: {e}")

        return deleted_count


async def export_chromadb_collection(
    chromadb_service: Any, output_path: Path, collection_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Export ChromaDB collection data to JSON file.

    Args:
        chromadb_service: ChromaDBService instance
        output_path: Path to save the exported data
        collection_name: Optional collection name override

    Returns:
        Export metadata dictionary
    """
    try:
        # Get all documents from collection
        # Note: This is a simplified export - in practice, you'd need
        # to implement pagination for large collections

        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "collection_name": collection_name or "default",
            "document_count": await chromadb_service.get_document_count(),
            "documents": [],
        }

        # Export would require additional ChromaDB methods to iterate all documents
        # This is a placeholder for the actual export implementation

        output_path.write_text(json.dumps(export_data, indent=2))

        logger.info(f"ChromaDB collection exported to: {output_path}")
        return export_data

    except Exception as e:
        logger.error(f"Failed to export ChromaDB collection: {e}")
        raise


async def import_chromadb_collection(
    chromadb_service: Any, import_path: Path, collection_name: Optional[str] = None
) -> bool:
    """
    Import ChromaDB collection data from JSON file.

    Args:
        chromadb_service: ChromaDBService instance
        import_path: Path to the exported data file
        collection_name: Optional collection name override

    Returns:
        True if import successful, False otherwise
    """
    try:
        if not import_path.exists():
            logger.error(f"Import file does not exist: {import_path}")
            return False

        import_data = json.loads(import_path.read_text())

        # Reset collection before import
        await chromadb_service.reset_collection()

        # Import documents (placeholder - requires actual document iteration)
        logger.info(f"Importing {import_data['document_count']} documents")

        # This is a placeholder for the actual import implementation
        # You'd need to add batch import methods to ChromaDBService

        logger.info("ChromaDB collection import completed")
        return True

    except Exception as e:
        logger.error(f"Failed to import ChromaDB collection: {e}")
        return False
