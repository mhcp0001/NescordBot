"""
Service Mock Registry - Central Mock Management

This module provides centralized creation and management of all service mocks.
"""

import logging
from typing import Any, Dict, Type
from unittest.mock import AsyncMock

from src.nescordbot.config import BotConfig
from src.nescordbot.services import (
    AlertManager,
    APIMonitor,
    ChromaDBService,
    EmbeddingService,
    FallbackManager,
    KnowledgeManager,
    Phase4Monitor,
    PrivacyManager,
    SearchEngine,
    SyncManager,
    TokenManager,
)

from .base_mock import BaseMockService, DatabaseAwareMock, RealisticResponseMixin

logger = logging.getLogger(__name__)


class ServiceMockRegistry:
    """Central registry for all service mocks."""

    @classmethod
    def create_complete_mock_set(  # type: ignore
        cls, config: BotConfig, db_service=None
    ) -> Dict[Any, Any]:
        """
        Create a complete set of all service mocks.

        Args:
            config: Bot configuration
            db_service: Mock database service

        Returns:
            Dictionary mapping service types to mock instances
        """
        logger.info("Creating complete mock set...")

        registry: Dict[Any, Any] = {}

        # Create all service mocks
        registry[TokenManager] = cls._create_token_manager_mock(config, db_service)
        registry[PrivacyManager] = cls._create_privacy_manager_mock(config, db_service)
        registry[KnowledgeManager] = cls._create_knowledge_manager_mock(config, db_service)
        registry[AlertManager] = cls._create_alert_manager_mock(config, db_service)
        registry[EmbeddingService] = cls._create_embedding_service_mock(config)
        registry[ChromaDBService] = cls._create_chromadb_service_mock(config)
        registry[SearchEngine] = cls._create_search_engine_mock(config, db_service)
        registry[SyncManager] = cls._create_sync_manager_mock(config, db_service)
        registry[FallbackManager] = cls._create_fallback_manager_mock(config)
        registry[APIMonitor] = cls._create_api_monitor_mock(config)
        registry[Phase4Monitor] = cls._create_phase4_monitor_mock(config)

        # Set up inter-service dependencies
        cls._setup_service_dependencies(registry)

        logger.info(f"Complete mock set created with {len(registry)} services")
        return registry

    @classmethod
    def create_performance_mock_set(cls, config: BotConfig, db_service=None) -> Dict[Type, Any]:
        """Create performance-optimized mock set."""
        # For performance tests, use the same mocks but with optimized responses
        mock_set = cls.create_complete_mock_set(config, db_service)

        # Optimize for concurrent access
        for service_mock in mock_set.values():
            if hasattr(service_mock, "record_usage"):
                # Make record_usage extremely fast
                service_mock.record_usage.return_value = None

        logger.info("Performance-optimized mock set created")
        return mock_set

    @staticmethod
    def _create_token_manager_mock(config, db_service) -> AsyncMock:
        """Create fully functional TokenManager mock."""
        mock = DatabaseAwareMock.create_db_mock(TokenManager, config, db_service)

        # Set up all TokenManager methods with realistic behavior
        async def mock_record_usage(
            provider: str, model: str, input_tokens: int = 0, output_tokens: int = 0, **kwargs
        ):
            if not provider or not model:
                # Create a mock TokenUsageError for testing
                class TokenUsageError(Exception):
                    pass

                raise TokenUsageError("Provider and model are required")
            return None

        mock.record_usage.side_effect = mock_record_usage
        mock.check_limits.return_value = {
            "within_limits": True,
            "usage": {"total_tokens": 100, "total_cost": 0.01},
        }
        mock.get_usage_history.return_value = []
        mock.get_monthly_usage.return_value = {}
        mock.calculate_cost.return_value = 0.001

        logger.debug("Created TokenManager mock")
        return mock

    @staticmethod
    def _create_privacy_manager_mock(config, db_service) -> AsyncMock:
        """Create fully functional PrivacyManager mock."""
        mock = DatabaseAwareMock.create_db_mock(PrivacyManager, config, db_service)

        # Set up PII detection with realistic responses
        mock.detect_pii.return_value = RealisticResponseMixin.create_realistic_pii_rules()
        mock.apply_masking.return_value = "Contact me at [EMAIL] for more info"

        # Set up alert manager dependency (will be set later)
        mock.alert_manager = None

        logger.debug("Created PrivacyManager mock")
        return mock

    @staticmethod
    def _create_knowledge_manager_mock(config, db_service) -> AsyncMock:
        """Create fully functional KnowledgeManager mock."""
        mock = DatabaseAwareMock.create_db_mock(KnowledgeManager, config, db_service)

        # Set up knowledge management methods
        mock.create_note.return_value = "note_123"
        mock.get_note.return_value = RealisticResponseMixin.create_realistic_note_data()
        mock.search_notes.return_value = []
        mock.update_note.return_value = True
        mock.delete_note.return_value = True
        mock.list_notes.return_value = []

        logger.debug("Created KnowledgeManager mock")
        return mock

    @staticmethod
    def _create_alert_manager_mock(config, db_service) -> AsyncMock:
        """Create fully functional AlertManager mock."""
        mock = BaseMockService.create_mock(AlertManager, config)
        mock.database_service = db_service
        mock._active_alerts = {}

        # Set up alert methods
        mock.send_alert.return_value = None
        mock._send_discord_notification.return_value = None
        mock.get_active_alerts.return_value = []
        mock.resolve_alert.return_value = True

        logger.debug("Created AlertManager mock")
        return mock

    @staticmethod
    def _create_embedding_service_mock(config) -> AsyncMock:
        """Create fully functional EmbeddingService mock."""
        mock = BaseMockService.create_mock(EmbeddingService, config)

        # Set up embedding methods
        mock_result = AsyncMock()
        mock_result.embedding = [0.1] * 768  # Realistic embedding vector
        mock_result.text = "test text"

        mock.generate_embedding.return_value = mock_result
        mock._generate_embedding_api.return_value = [0.1] * 768

        logger.debug("Created EmbeddingService mock")
        return mock

    @staticmethod
    def _create_chromadb_service_mock(config) -> AsyncMock:
        """Create fully functional ChromaDBService mock."""
        mock = BaseMockService.create_mock(ChromaDBService, config)

        # Set up ChromaDB methods
        mock.client = AsyncMock()
        mock.collection = AsyncMock()
        mock.add_document.return_value = None
        mock.search_documents.return_value = []
        mock.get_document_count.return_value = 0
        mock.reset_collection.return_value = None

        # Add compatibility methods using setattr to avoid AttributeError
        setattr(
            mock,
            "get_collection_info",
            AsyncMock(return_value={"count": 0, "name": "test_collection"}),
        )
        setattr(
            mock, "clear_collection", AsyncMock(return_value=None)
        )  # Alias for reset_collection

        logger.debug("Created ChromaDBService mock")
        return mock

    @staticmethod
    def _create_search_engine_mock(config, db_service) -> AsyncMock:
        """Create fully functional SearchEngine mock."""
        mock = DatabaseAwareMock.create_db_mock(SearchEngine, config, db_service)

        # Set up search methods
        mock.hybrid_search.return_value = []
        mock.vector_search.return_value = []
        mock.keyword_search.return_value = []

        # Add compatibility methods
        setattr(mock, "search", AsyncMock(return_value={"results": [], "total": 0}))
        setattr(mock, "semantic_search", AsyncMock(return_value=[]))  # Alias for vector_search

        logger.debug("Created SearchEngine mock")
        return mock

    @staticmethod
    def _create_sync_manager_mock(config, db_service) -> AsyncMock:
        """Create fully functional SyncManager mock."""
        mock = DatabaseAwareMock.create_db_mock(SyncManager, config, db_service)

        # Set up sync methods using setattr
        setattr(mock, "sync_note", AsyncMock(return_value=True))
        setattr(mock, "sync_all_notes", AsyncMock(return_value={"synced": 0, "failed": 0}))
        setattr(mock, "get_sync_status", AsyncMock(return_value={"last_sync": None, "pending": 0}))

        logger.debug("Created SyncManager mock")
        return mock

    @staticmethod
    def _create_fallback_manager_mock(config) -> AsyncMock:
        """Create fully functional FallbackManager mock."""
        mock = BaseMockService.create_mock(FallbackManager, config)

        # Set up fallback methods using setattr
        setattr(mock, "get_fallback_service", AsyncMock(return_value="backup_service"))
        setattr(mock, "is_service_available", AsyncMock(return_value=True))
        setattr(mock, "record_failure", AsyncMock(return_value=None))

        logger.debug("Created FallbackManager mock")
        return mock

    @staticmethod
    def _create_api_monitor_mock(config) -> AsyncMock:
        """Create fully functional APIMonitor mock."""
        mock = BaseMockService.create_mock(APIMonitor, config)

        # Set up monitoring methods using setattr
        setattr(mock, "record_api_call", AsyncMock(return_value=None))
        setattr(mock, "get_api_stats", AsyncMock(return_value={"calls": 0, "errors": 0}))
        setattr(mock, "check_rate_limits", AsyncMock(return_value={"within_limits": True}))

        logger.debug("Created APIMonitor mock")
        return mock

    @staticmethod
    def _create_phase4_monitor_mock(config) -> AsyncMock:
        """Create fully functional Phase4Monitor mock."""
        mock = BaseMockService.create_mock(Phase4Monitor, config)

        # Set up monitoring methods using setattr
        setattr(mock, "get_system_metrics", AsyncMock(return_value={"cpu": 0.1, "memory": 0.2}))
        setattr(mock, "get_service_metrics", AsyncMock(return_value={}))
        setattr(mock, "record_metric", AsyncMock(return_value=None))

        logger.debug("Created Phase4Monitor mock")
        return mock

    @staticmethod
    def _setup_service_dependencies(registry: Dict[Type, Any]) -> None:
        """Set up inter-service dependencies."""
        # PrivacyManager needs AlertManager
        if PrivacyManager in registry and AlertManager in registry:
            registry[PrivacyManager].alert_manager = registry[AlertManager]

        # SearchEngine needs ChromaDBService and EmbeddingService
        if SearchEngine in registry:
            if ChromaDBService in registry:
                registry[SearchEngine].chroma_service = registry[ChromaDBService]
            if EmbeddingService in registry:
                registry[SearchEngine].embedding_service = registry[EmbeddingService]

        # APIMonitor needs TokenManager and FallbackManager
        if APIMonitor in registry:
            if TokenManager in registry:
                registry[APIMonitor].token_manager = registry[TokenManager]
            if FallbackManager in registry:
                registry[APIMonitor].fallback_manager = registry[FallbackManager]

        logger.debug("Service dependencies configured")
