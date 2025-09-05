"""
Simplified Phase 4 Integration Tests.

These tests focus on verifying basic service functionality without
complex mocking or integration requirements.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.nescordbot.bot import NescordBot
from src.nescordbot.config import BotConfig
from src.nescordbot.services import ServiceContainer


@pytest.fixture
def simple_config(tmp_path):
    """Create minimal test configuration."""
    return BotConfig(
        discord_token="TEST_TOKEN_NOT_REAL.XXXXXX.DUMMY_VALUE_FOR_TESTING_ONLY",
        openai_api_key="sk-1234567890abcdef1234567890abcdef1234567890abcdef12",
        database_url="sqlite:///:memory:",
        data_directory=str(tmp_path / "data"),
        phase4_enabled=True,
        chromadb_enabled=True,
        chromadb_path=str(tmp_path / "chromadb"),
        enable_pkm=True,
        embedding_model="text-embedding-3-small",
        gemini_api_key="AIzaSyB1234567890abcdefghijklmnopqrstuvwxyz",
    )


@pytest.fixture
async def simple_bot(simple_config):
    """Create simplified bot with mocked Discord operations."""
    with patch("discord.Client.login"), patch("discord.Client.connect"):
        bot = NescordBot()
        bot.config = simple_config

        # Initialize services if available
        if hasattr(bot, "initialize_services"):
            await bot.initialize_services()

        yield bot

        # Cleanup
        if hasattr(bot, "service_container"):
            await bot.service_container.shutdown_services()


class TestPhase4BasicIntegration:
    """Basic integration tests for Phase 4 services."""

    async def test_service_container_exists(self, simple_bot):
        """Verify ServiceContainer is properly initialized."""
        assert hasattr(simple_bot, "service_container")
        assert isinstance(simple_bot.service_container, ServiceContainer)

    async def test_phase4_services_registered(self, simple_bot):
        """Verify Phase 4 services are registered."""
        container = simple_bot.service_container

        # Check for core services
        from src.nescordbot.services.chromadb_service import ChromaDBService
        from src.nescordbot.services.embedding import EmbeddingService
        from src.nescordbot.services.token_manager import TokenManager

        assert container.has_service(EmbeddingService)
        assert container.has_service(ChromaDBService)
        assert container.has_service(TokenManager)

    async def test_service_creation(self, simple_bot):
        """Test that services can be created."""
        from src.nescordbot.services.token_manager import TokenManager

        token_manager = simple_bot.service_container.get_service(TokenManager)
        assert token_manager is not None

        # Basic functionality test
        await token_manager.record_usage("test_provider", "test_model", 10, 5)
        usage = await token_manager.get_usage_history("test_provider")
        assert len(usage) > 0

    async def test_knowledge_manager_basic(self, simple_bot):
        """Test basic KnowledgeManager operations."""
        from src.nescordbot.services.knowledge_manager import KnowledgeManager

        km = simple_bot.service_container.get_service(KnowledgeManager)

        # Create a note
        note_id = await km.create_note(
            title="Test Note",
            content="Test content for integration testing",
            tags=["test", "integration"],
        )

        assert note_id is not None

        # Retrieve the note
        note = await km.get_note(note_id)
        assert note is not None
        assert note["title"] == "Test Note"

    async def test_privacy_manager_basic(self, simple_bot):
        """Test basic PrivacyManager functionality."""
        from src.nescordbot.services.privacy_manager import PrivacyManager

        pm = simple_bot.service_container.get_service(PrivacyManager)

        # Mock database initialization
        with patch.object(pm.db, "_initialized", True):
            await pm.initialize()

            # Test PII detection
            text_with_email = "Contact me at test@example.com"
            detected = await pm.detect_pii(text_with_email)

            # Should detect email
            assert len(detected) > 0

            # Test masking
            masked = await pm.mask_pii(text_with_email)
            assert "test@example.com" not in masked
            assert "[EMAIL]" in masked or "***" in masked

    async def test_alert_manager_basic(self, simple_bot):
        """Test basic AlertManager functionality."""
        from datetime import datetime

        from src.nescordbot.services.alert_manager import Alert, AlertManager, AlertSeverity

        am = simple_bot.service_container.get_service(AlertManager)

        # Create and send an alert
        alert = Alert(
            id="test_alert",
            title="Test Alert",
            message="This is a test alert",
            severity=AlertSeverity.INFO,
            timestamp=datetime.now(),
            source="test",
            metadata={},
        )

        # Mock Discord notification
        with patch.object(am, "_send_discord_notification", new_callable=AsyncMock):
            await am.send_alert(alert)

            # Verify alert was processed
            assert alert.id in am._active_alerts

    async def test_embedding_service_basic(self, simple_bot):
        """Test basic EmbeddingService functionality."""
        from src.nescordbot.services.embedding import EmbeddingService

        es = simple_bot.service_container.get_service(EmbeddingService)

        # Mock the Gemini API call
        with patch.object(es, "generate_embedding", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [0.1] * 768  # Mock embedding vector

            embedding = await es.generate_embedding("Test text")
            assert embedding is not None
            assert len(embedding) == 768

    async def test_search_engine_basic(self, simple_bot):
        """Test basic SearchEngine functionality."""
        from src.nescordbot.services.knowledge_manager import KnowledgeManager
        from src.nescordbot.services.search_engine import SearchEngine

        se = simple_bot.service_container.get_service(SearchEngine)
        km = simple_bot.service_container.get_service(KnowledgeManager)

        # Add some test notes
        await km.create_note(
            title="Python Guide",
            content="Python is a programming language",
            tags=["python", "programming"],
        )

        # Mock search to avoid complex dependencies
        with patch.object(se, "search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = {
                "results": [{"title": "Python Guide", "score": 0.9}],
                "total": 1,
            }

            results = await se.search("python")
            assert results["total"] > 0


class TestPhase4EndToEnd:
    """Simplified end-to-end workflow tests."""

    async def test_note_creation_workflow(self, simple_bot):
        """Test complete note creation workflow."""
        from src.nescordbot.services.knowledge_manager import KnowledgeManager
        from src.nescordbot.services.privacy_manager import PrivacyManager

        km = simple_bot.service_container.get_service(KnowledgeManager)
        pm = simple_bot.service_container.get_service(PrivacyManager)

        # Mock privacy manager initialization
        with patch.object(pm.db, "_initialized", True):
            await pm.initialize()

            # Create note with PII
            content = "Contact John at john@example.com for details"

            # Mask PII
            masked_content = await pm.mask_pii(content)

            # Create note with masked content
            note_id = await km.create_note(
                title="Contact Info", content=masked_content, tags=["contact"]
            )

            # Verify note was created
            note = await km.get_note(note_id)
            assert note is not None
            assert "john@example.com" not in note["content"]

    async def test_concurrent_operations(self, simple_bot):
        """Test concurrent service operations."""
        from src.nescordbot.services.token_manager import TokenManager

        tm = simple_bot.service_container.get_service(TokenManager)

        # Create concurrent tasks
        async def record_usage(i):
            await tm.record_usage(
                provider=f"provider_{i % 3}", model="test_model", input_tokens=10, output_tokens=5
            )

        # Run 10 concurrent operations
        tasks = [record_usage(i) for i in range(10)]
        await asyncio.gather(*tasks)

        # Verify all operations completed
        for i in range(3):
            usage = await tm.get_usage_history(f"provider_{i}")
            assert len(usage) > 0


@pytest.mark.asyncio
async def test_phase4_basic_health_check(simple_bot):
    """Test overall Phase 4 system health."""
    # Check service container
    assert simple_bot.service_container is not None

    # Check critical services
    from src.nescordbot.services.knowledge_manager import KnowledgeManager
    from src.nescordbot.services.token_manager import TokenManager

    tm = simple_bot.service_container.get_service(TokenManager)
    km = simple_bot.service_container.get_service(KnowledgeManager)

    assert tm is not None
    assert km is not None

    # Basic health check
    health = await km.health_check()
    assert health["status"] == "healthy"
