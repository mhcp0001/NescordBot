"""
Services package for NescordBot.

This package contains service classes that provide business logic
and infrastructure operations for the bot.
"""

from ..security import SecurityValidator
from .backup_manager import (
    BackupInfo,
    BackupIntegrityError,
    BackupManager,
    BackupManagerError,
    RestoreError,
)
from .batch_processor import BatchProcessor, GitHubIntegratedQueue
from .database import DatabaseService, IDataStore
from .git_operations import FileOperation, GitOperationService
from .github import GitHubService
from .github_auth import GitHubAuthManager
from .note_processing import NoteProcessingService
from .obsidian_github import ObsidianGitHubService, ObsidianSyncStatus
from .persistent_queue import FileRequest, PersistentQueue

__all__ = [
    "BackupInfo",
    "BackupIntegrityError",
    "BackupManager",
    "BackupManagerError",
    "RestoreError",
    "DatabaseService",
    "IDataStore",
    "GitHubService",
    "PersistentQueue",
    "FileRequest",
    "GitHubAuthManager",
    "GitOperationService",
    "FileOperation",
    "BatchProcessor",
    "GitHubIntegratedQueue",
    "NoteProcessingService",
    "ObsidianGitHubService",
    "ObsidianSyncStatus",
    "SecurityValidator",
]
