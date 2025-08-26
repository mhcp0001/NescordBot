"""
Services package for NescordBot.

This package contains service classes that provide business logic
and infrastructure operations for the bot.
"""

from ..security import SecurityValidator
from .batch_processor import BatchProcessor, GitHubIntegratedQueue
from .chromadb_service import ChromaDBService, DocumentMetadata, SearchResult
from .database import DatabaseService, IDataStore
from .embedding import EmbeddingResult, EmbeddingService, EmbeddingServiceError
from .git_operations import FileOperation, GitOperationService
from .github import GitHubService
from .github_auth import GitHubAuthManager
from .note_processing import NoteProcessingService
from .obsidian_github import ObsidianGitHubService, ObsidianSyncStatus
from .persistent_queue import FileRequest, PersistentQueue
from .service_container import (
    ServiceContainer,
    ServiceInitializationError,
    ServiceNotFoundError,
    create_service_container,
    get_service_container,
    reset_service_container,
)
from .token_manager import TokenLimitExceededError, TokenManager, TokenUsageError

__all__ = [
    "DatabaseService",
    "IDataStore",
    "ChromaDBService",
    "DocumentMetadata",
    "SearchResult",
    "EmbeddingService",
    "EmbeddingResult",
    "EmbeddingServiceError",
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
    "ServiceContainer",
    "ServiceNotFoundError",
    "ServiceInitializationError",
    "get_service_container",
    "create_service_container",
    "reset_service_container",
    "TokenManager",
    "TokenUsageError",
    "TokenLimitExceededError",
]
