"""
Test helpers for Phase 4 integration tests.

This module provides utilities for mocking Phase 4 services to avoid
database initialization issues in integration tests.
"""

from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock

from src.nescordbot.bot import NescordBot
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


def create_mock_database_connection():
    """Create a mock database connection context manager."""
    mock_connection = AsyncMock()
    mock_connection.execute = AsyncMock()
    mock_connection.fetchall = AsyncMock(return_value=[])
    mock_connection.fetchone = AsyncMock(return_value=None)
    mock_connection.commit = AsyncMock()

    mock_context = AsyncMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_connection)
    mock_context.__aexit__ = AsyncMock()

    return mock_context


def create_mock_token_manager(config=None, database_service=None):
    """Create a properly mocked TokenManager."""
    mock_token_manager = AsyncMock(spec=TokenManager)
    mock_token_manager._initialized = True
    mock_token_manager.config = config
    mock_token_manager.db = database_service or AsyncMock()
    mock_token_manager.db._initialized = True
    mock_token_manager.db.get_connection = MagicMock(return_value=create_mock_database_connection())

    # Mock methods
    mock_token_manager.record_usage = AsyncMock()
    mock_token_manager.check_limits = AsyncMock(
        return_value={"within_limits": True, "usage": {"total_tokens": 100, "total_cost": 0.01}}
    )
    mock_token_manager.get_usage_history = AsyncMock(return_value=[])
    mock_token_manager.get_monthly_usage = AsyncMock(return_value={})
    mock_token_manager.health_check = AsyncMock(return_value={"status": "healthy"})

    return mock_token_manager


def create_mock_privacy_manager(config=None, bot=None, database_service=None, alert_manager=None):
    """Create a properly mocked PrivacyManager."""
    mock_privacy_manager = AsyncMock(spec=PrivacyManager)
    mock_privacy_manager._initialized = True
    mock_privacy_manager.config = config
    mock_privacy_manager.bot = bot
    mock_privacy_manager.db = database_service or AsyncMock()
    mock_privacy_manager.db._initialized = True
    mock_privacy_manager.db.get_connection = MagicMock(
        return_value=create_mock_database_connection()
    )
    mock_privacy_manager.alert_manager = alert_manager

    # Mock methods
    mock_privacy_manager.initialize = AsyncMock()
    mock_privacy_manager.detect_pii = AsyncMock(return_value=[])
    mock_privacy_manager.mask_pii = AsyncMock(return_value="[REDACTED]")
    mock_privacy_manager.apply_masking = AsyncMock(return_value="[REDACTED]")
    mock_privacy_manager.health_check = AsyncMock(return_value={"status": "healthy"})

    return mock_privacy_manager


def create_mock_knowledge_manager(
    config=None,
    database_service=None,
    chromadb_service=None,
    embedding_service=None,
    sync_manager=None,
    obsidian_github_service=None,
):
    """Create a properly mocked KnowledgeManager."""
    mock_km = AsyncMock(spec=KnowledgeManager)
    mock_km._initialized = True
    mock_km.config = config
    mock_km.db = database_service or AsyncMock()
    mock_km.db._initialized = True
    mock_km.db.get_connection = MagicMock(return_value=create_mock_database_connection())
    mock_km.chromadb_service = chromadb_service
    mock_km.embedding_service = embedding_service
    mock_km.sync_manager = sync_manager
    mock_km.obsidian_github_service = obsidian_github_service

    # Mock methods
    mock_km.create_note = AsyncMock(return_value="note_123")
    mock_km.get_note = AsyncMock(
        return_value={
            "id": "note_123",
            "title": "Test Note",
            "content": "Test content",
            "tags": ["test"],
        }
    )
    mock_km.search_notes = AsyncMock(return_value=[])
    mock_km.health_check = AsyncMock(return_value={"status": "healthy"})

    return mock_km


def create_mock_alert_manager(
    config=None, bot=None, database_service=None, phase4_monitor=None, token_manager=None
):
    """Create a properly mocked AlertManager."""
    mock_am = AsyncMock(spec=AlertManager)
    mock_am._initialized = True
    mock_am.config = config
    mock_am.bot = bot
    mock_am.database_service = database_service
    mock_am.phase4_monitor = phase4_monitor
    mock_am.token_manager = token_manager
    mock_am._active_alerts = {}

    # Mock methods
    mock_am.send_alert = AsyncMock()
    mock_am._send_discord_notification = AsyncMock()
    mock_am.health_check = AsyncMock(return_value={"status": "healthy"})

    return mock_am


def create_mock_embedding_service(config=None):
    """Create a properly mocked EmbeddingService."""
    mock_es = AsyncMock(spec=EmbeddingService)
    mock_es.config = config
    mock_es._initialized = True

    # Mock methods
    mock_es.generate_embedding = AsyncMock(
        return_value=AsyncMock(embedding=[0.1] * 768, text="test text")
    )
    mock_es._generate_embedding_api = AsyncMock(return_value=[0.1] * 768)
    mock_es.health_check = AsyncMock(return_value={"status": "healthy"})

    return mock_es


def create_mock_search_engine(
    chroma_service=None, db_service=None, embedding_service=None, config=None
):
    """Create a properly mocked SearchEngine."""
    mock_se = AsyncMock(spec=SearchEngine)
    mock_se.chroma_service = chroma_service
    mock_se.db_service = db_service
    mock_se.embedding_service = embedding_service
    mock_se.config = config
    mock_se._initialized = True

    # Mock methods
    mock_se.search = AsyncMock(return_value={"results": [], "total": 0})
    mock_se.health_check = AsyncMock(return_value={"status": "healthy"})

    return mock_se


def create_mock_chromadb_service(config=None):
    """Create a properly mocked ChromaDBService."""
    mock_cdb = AsyncMock(spec=ChromaDBService)
    mock_cdb.config = config
    mock_cdb._initialized = True
    mock_cdb.client = AsyncMock()
    mock_cdb.collection = AsyncMock()

    # Mock methods
    mock_cdb.add_document = AsyncMock()
    mock_cdb.search = AsyncMock(return_value=[])
    mock_cdb.health_check = AsyncMock(return_value={"status": "healthy"})

    return mock_cdb


async def setup_phase4_service_mocks(bot: NescordBot) -> Dict[str, Any]:
    """
    Set up all Phase 4 service mocks for integration testing.

    Args:
        bot: The NescordBot instance to configure

    Returns:
        Dictionary of all mocked services for verification
    """
    mocks = {}

    # Create mock database service if needed
    if hasattr(bot, "database_service"):
        bot.database_service._initialized = True
        setattr(
            bot.database_service,
            "get_connection",
            MagicMock(return_value=create_mock_database_connection()),
        )

    # Register TokenManager mock
    mock_token_manager = create_mock_token_manager(bot.config, bot.database_service)
    bot.service_container.register_singleton(TokenManager, mock_token_manager)
    mocks["token_manager"] = mock_token_manager

    # Register EmbeddingService mock
    mock_embedding_service = create_mock_embedding_service(bot.config)
    bot.service_container.register_singleton(EmbeddingService, mock_embedding_service)
    mocks["embedding_service"] = mock_embedding_service

    # Register ChromaDBService mock
    mock_chromadb_service = create_mock_chromadb_service(bot.config)
    bot.service_container.register_singleton(ChromaDBService, mock_chromadb_service)
    mocks["chromadb_service"] = mock_chromadb_service

    # Register FallbackManager mock
    mock_fallback_manager = AsyncMock(spec=FallbackManager)
    mock_fallback_manager.config = bot.config
    mock_fallback_manager.health_check = AsyncMock(return_value={"status": "healthy"})
    bot.service_container.register_singleton(FallbackManager, mock_fallback_manager)
    mocks["fallback_manager"] = mock_fallback_manager

    # Register APIMonitor mock
    mock_api_monitor = AsyncMock(spec=APIMonitor)
    mock_api_monitor.config = bot.config
    mock_api_monitor.token_manager = mock_token_manager
    mock_api_monitor.fallback_manager = mock_fallback_manager
    mock_api_monitor.health_check = AsyncMock(return_value={"status": "healthy"})
    bot.service_container.register_singleton(APIMonitor, mock_api_monitor)
    mocks["api_monitor"] = mock_api_monitor

    # Register SyncManager mock
    mock_sync_manager = AsyncMock(spec=SyncManager)
    mock_sync_manager.config = bot.config
    mock_sync_manager.health_check = AsyncMock(return_value={"status": "healthy"})
    bot.service_container.register_singleton(SyncManager, mock_sync_manager)
    mocks["sync_manager"] = mock_sync_manager

    # Register SearchEngine mock
    mock_search_engine = create_mock_search_engine(
        mock_chromadb_service, bot.database_service, mock_embedding_service, bot.config
    )
    bot.service_container.register_singleton(SearchEngine, mock_search_engine)
    mocks["search_engine"] = mock_search_engine

    # Register KnowledgeManager mock
    mock_knowledge_manager = create_mock_knowledge_manager(
        bot.config,
        bot.database_service,
        mock_chromadb_service,
        mock_embedding_service,
        mock_sync_manager,
        None,
    )
    bot.service_container.register_singleton(KnowledgeManager, mock_knowledge_manager)
    mocks["knowledge_manager"] = mock_knowledge_manager

    # Register Phase4Monitor mock
    mock_phase4_monitor = AsyncMock(spec=Phase4Monitor)
    mock_phase4_monitor.config = bot.config
    mock_phase4_monitor.health_check = AsyncMock(return_value={"status": "healthy"})
    bot.service_container.register_singleton(Phase4Monitor, mock_phase4_monitor)
    mocks["phase4_monitor"] = mock_phase4_monitor

    # Register AlertManager mock
    mock_alert_manager = create_mock_alert_manager(
        bot.config, bot, bot.database_service, mock_phase4_monitor, mock_token_manager
    )
    bot.service_container.register_singleton(AlertManager, mock_alert_manager)
    mocks["alert_manager"] = mock_alert_manager

    # Register PrivacyManager mock
    mock_privacy_manager = create_mock_privacy_manager(
        bot.config, bot, bot.database_service, mock_alert_manager
    )
    bot.service_container.register_singleton(PrivacyManager, mock_privacy_manager)
    mocks["privacy_manager"] = mock_privacy_manager

    return mocks
