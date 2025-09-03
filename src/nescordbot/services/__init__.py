"""
Services package for NescordBot.

This package contains service classes that provide business logic
and infrastructure operations for the bot.
"""

from ..security import SecurityValidator
from .alert_manager import Alert, AlertManager, AlertManagerError, AlertRule, AlertSeverity
from .api_monitor import APIMonitor, APIMonitorError
from .batch_processor import BatchProcessor, GitHubIntegratedQueue
from .chromadb_service import ChromaDBService, DocumentMetadata, SearchResult
from .database import DatabaseService, IDataStore
from .embedding import EmbeddingResult, EmbeddingService, EmbeddingServiceError
from .fallback_manager import FallbackLevel, FallbackManager, FallbackManagerError
from .git_operations import FileOperation, GitOperationService
from .github import GitHubService
from .github_auth import GitHubAuthManager
from .knowledge_manager import KnowledgeManager, KnowledgeManagerError
from .note_processing import NoteProcessingService
from .obsidian_github import ObsidianGitHubService, ObsidianSyncStatus
from .persistent_queue import FileRequest, PersistentQueue
from .phase4_monitor import Phase4Monitor, Phase4MonitorError
from .search_engine import (
    SearchEngine,
    SearchEngineError,
    SearchFilters,
    SearchHistory,
    SearchQueryError,
)
from .search_engine import SearchResult as SearchEngineResult
from .search_engine import SearchTimeoutError
from .service_container import (
    ServiceContainer,
    ServiceInitializationError,
    ServiceNotFoundError,
    create_service_container,
    get_service_container,
    reset_service_container,
)
from .sync_manager import (
    ConsistencyReport,
    RepairReport,
    SyncConsistencyError,
    SyncError,
    SyncManager,
    SyncReport,
    SyncResult,
    SyncServiceUnavailableError,
    SyncStatus,
)
from .token_manager import TokenLimitExceededError, TokenManager, TokenUsageError

__all__ = [
    "Alert",
    "AlertManager",
    "AlertManagerError",
    "AlertRule",
    "AlertSeverity",
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
    "KnowledgeManager",
    "KnowledgeManagerError",
    "SearchEngine",
    "SearchEngineError",
    "SearchEngineResult",
    "SearchFilters",
    "SearchHistory",
    "SearchQueryError",
    "SearchTimeoutError",
    "ServiceContainer",
    "ServiceNotFoundError",
    "ServiceInitializationError",
    "get_service_container",
    "create_service_container",
    "reset_service_container",
    "TokenManager",
    "TokenUsageError",
    "TokenLimitExceededError",
    "SyncManager",
    "SyncStatus",
    "SyncResult",
    "SyncReport",
    "ConsistencyReport",
    "RepairReport",
    "SyncError",
    "SyncServiceUnavailableError",
    "SyncConsistencyError",
    "FallbackManager",
    "FallbackManagerError",
    "FallbackLevel",
    "APIMonitor",
    "APIMonitorError",
    "Phase4Monitor",
    "Phase4MonitorError",
]
