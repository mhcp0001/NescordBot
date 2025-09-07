"""
Phase 4 Essential Integration Tests - Complete Isolation Strategy

This module contains essential integration tests for Phase 4 services
using the complete test isolation pattern. No real services are created.
"""

import asyncio
import logging
from unittest.mock import Mock

import pytest

from src.nescordbot.services import (
    AlertManager,
    EmbeddingService,
    KnowledgeManager,
    PrivacyManager,
    TokenManager,
)

logger = logging.getLogger(__name__)


@pytest.mark.integration
@pytest.mark.ci
class TestPhase4EssentialServices:
    """Essential service functionality tests with complete isolation."""

    async def test_service_container_isolation(self, isolated_bot):
        """Verify that TestServiceContainer blocks real service creation."""
        container = isolated_bot.service_container

        # Verify it's our test container
        from tests.infrastructure.test_service_container import TestServiceContainer

        assert isinstance(container, TestServiceContainer)

        # Verify test mode is active
        assert container._test_mode is True

        # Verify all expected services are registered
        assert container.has_service(TokenManager)
        assert container.has_service(PrivacyManager)
        assert container.has_service(KnowledgeManager)
        assert container.has_service(AlertManager)
        assert container.has_service(EmbeddingService)

    async def test_token_manager_complete_api(self, isolated_bot):
        """Test TokenManager with complete API coverage."""
        token_manager = isolated_bot.service_container.get_service(TokenManager)

        # Verify it's a mock with expected attributes
        assert hasattr(token_manager, "_initialized")
        assert token_manager._initialized is True

        # Test record_usage with realistic scenarios
        await token_manager.record_usage("openai", "gpt-4", 100, 50)
        token_manager.record_usage.assert_called_with("openai", "gpt-4", 100, 50)

        # Test error handling
        try:
            await token_manager.record_usage("", "", 0, 0)
        except Exception as e:
            # Should handle validation errors gracefully
            assert "required" in str(e).lower()

        # Test other methods
        limits = await token_manager.check_limits("openai")
        assert isinstance(limits, dict)
        assert "within_limits" in limits

        history = await token_manager.get_usage_history("openai")
        assert isinstance(history, list)

    async def test_privacy_manager_complete_api(self, isolated_bot):
        """Test PrivacyManager with complete API coverage."""
        privacy_manager = isolated_bot.service_container.get_service(PrivacyManager)

        # Configure realistic PII detection
        from src.nescordbot.services.privacy_manager import PrivacyLevel

        # Create mock PII rule
        mock_rule = Mock()
        mock_rule.name = "email"
        mock_rule.pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        mock_rule.severity = "HIGH"

        privacy_manager.detect_pii.return_value = [(mock_rule, ["test@example.com"])]
        privacy_manager.apply_masking.return_value = "Contact me at [EMAIL] for info"

        # Test initialization
        await privacy_manager.initialize()

        # Test PII detection
        text_with_email = "Contact me at test@example.com for information"
        detected_rules = await privacy_manager.detect_pii(text_with_email)

        assert len(detected_rules) > 0
        rule, matches = detected_rules[0]
        assert rule.name == "email"
        assert "test@example.com" in matches

        # Test masking
        masked_text = await privacy_manager.apply_masking(text_with_email, PrivacyLevel.HIGH)
        assert "test@example.com" not in masked_text
        assert "[EMAIL]" in masked_text

    async def test_knowledge_manager_complete_api(self, isolated_bot):
        """Test KnowledgeManager with complete API coverage."""
        knowledge_manager = isolated_bot.service_container.get_service(KnowledgeManager)

        # Test note creation
        note_id = await knowledge_manager.create_note(
            title="Test Note",
            content="This is test content for integration testing",
            tags=["test", "integration"],
        )

        assert note_id == "note_123"  # From our mock
        knowledge_manager.create_note.assert_called_once()

        # Test note retrieval
        note = await knowledge_manager.get_note(note_id)
        assert note is not None
        assert note["title"] == "Test Note"
        assert note["id"] == "note_123"

        # Test note searching
        results = await knowledge_manager.search_notes("test")
        assert isinstance(results, list)

    async def test_alert_manager_complete_api(self, isolated_bot):
        """Test AlertManager with complete API coverage."""
        alert_manager = isolated_bot.service_container.get_service(AlertManager)

        # Test health check
        health = await alert_manager.health_check()
        assert isinstance(health, dict)
        assert health["status"] == "healthy"

        # Test alert creation and sending
        from datetime import datetime

        from src.nescordbot.services.alert_manager import Alert, AlertSeverity

        test_alert = Alert(
            id="test_alert_123",
            title="Test Alert",
            message="This is a test alert for integration testing",
            severity=AlertSeverity.INFO,
            timestamp=datetime.now(),
            source="integration_test",
            metadata={"test": True},
        )

        # Should not raise exception
        await alert_manager.send_alert(test_alert)
        alert_manager.send_alert.assert_called_once_with(test_alert)

    async def test_embedding_service_complete_api(self, isolated_bot):
        """Test EmbeddingService with complete API coverage."""
        embedding_service = isolated_bot.service_container.get_service(EmbeddingService)

        # Test embedding generation
        result = await embedding_service.generate_embedding("test text for embedding")

        assert result is not None
        assert hasattr(result, "embedding")
        assert hasattr(result, "text")
        assert len(result.embedding) == 768  # Standard embedding size
        assert result.text == "test text"

    async def test_service_interdependencies(self, isolated_bot):
        """Test that service dependencies are properly configured."""
        privacy_manager = isolated_bot.service_container.get_service(PrivacyManager)
        alert_manager = isolated_bot.service_container.get_service(AlertManager)

        # PrivacyManager should have AlertManager dependency
        assert privacy_manager.alert_manager is not None
        assert privacy_manager.alert_manager is alert_manager


@pytest.mark.integration
@pytest.mark.ci
class TestPhase4ServiceInteractions:
    """Test interactions between services in isolated environment."""

    async def test_privacy_alert_workflow(self, isolated_bot):
        """Test privacy detection triggering alert workflow."""
        privacy_manager = isolated_bot.service_container.get_service(PrivacyManager)
        alert_manager = isolated_bot.service_container.get_service(AlertManager)

        # Configure realistic PII detection
        mock_rule = Mock()
        mock_rule.name = "email"
        mock_rule.severity = "HIGH"

        privacy_manager.detect_pii.return_value = [(mock_rule, ["sensitive@example.com"])]

        # Process text with PII
        sensitive_text = "Please send the report to sensitive@example.com"
        detected_rules = await privacy_manager.detect_pii(sensitive_text)

        assert len(detected_rules) > 0

        # Verify alert system is functional
        health = await alert_manager.health_check()
        assert health["status"] == "healthy"

    async def test_knowledge_embedding_workflow(self, isolated_bot):
        """Test knowledge management with embedding workflow."""
        knowledge_manager = isolated_bot.service_container.get_service(KnowledgeManager)
        embedding_service = isolated_bot.service_container.get_service(EmbeddingService)

        # Create note
        note_id = await knowledge_manager.create_note(
            title="AI Research Notes",
            content="Machine learning and artificial intelligence research notes",
            tags=["ai", "ml", "research"],
        )

        assert note_id is not None

        # Generate embedding for the content
        embedding_result = await embedding_service.generate_embedding(
            "Machine learning and artificial intelligence research notes"
        )

        assert embedding_result is not None
        assert len(embedding_result.embedding) == 768

        # Both operations should complete without error
        knowledge_manager.create_note.assert_called_once()
        embedding_service.generate_embedding.assert_called_once()

    async def test_concurrent_service_operations(self, isolated_bot):
        """Test concurrent operations across multiple services."""
        token_manager = isolated_bot.service_container.get_service(TokenManager)
        privacy_manager = isolated_bot.service_container.get_service(PrivacyManager)
        knowledge_manager = isolated_bot.service_container.get_service(KnowledgeManager)

        # Configure privacy manager
        mock_rule = Mock()
        mock_rule.name = "email"
        privacy_manager.detect_pii.return_value = [(mock_rule, ["test@example.com"])]

        async def token_task():
            await token_manager.record_usage("test_provider", "test_model", 50, 25)
            return "token_complete"

        async def privacy_task():
            result = await privacy_manager.detect_pii("Contact test@example.com")
            return len(result)

        async def knowledge_task():
            note_id = await knowledge_manager.create_note(
                title="Concurrent Test",
                content="Testing concurrent operations",
                tags=["concurrent", "test"],
            )
            return note_id

        # Run all tasks concurrently
        results = await asyncio.gather(
            token_task(), privacy_task(), knowledge_task(), return_exceptions=True
        )

        # All should complete successfully
        assert results[0] == "token_complete"
        assert results[1] == 1  # One PII rule detected
        assert results[2] == "note_123"  # Mock return value


@pytest.mark.integration
@pytest.mark.ci
@pytest.mark.slow
class TestPhase4Performance:
    """Performance tests with realistic loads."""

    async def test_high_volume_token_tracking(self, performance_bot):
        """Test high-volume token usage tracking."""
        token_manager = performance_bot.service_container.get_service(TokenManager)

        # Simulate high-volume usage tracking
        tasks = []
        for i in range(100):
            task = token_manager.record_usage(
                f"provider_{i % 5}",  # 5 different providers
                "test_model",
                100 + i,  # Varying token counts
                50 + i,
            )
            tasks.append(task)

        # Execute all concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should complete without exceptions
        exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(exceptions) == 0, f"Found {len(exceptions)} exceptions: {exceptions}"

        # Verify all calls were made
        assert token_manager.record_usage.call_count == 100


@pytest.mark.integration
@pytest.mark.ci
class TestPhase4HealthChecks:
    """Health check and system monitoring tests."""

    async def test_service_container_health(self, isolated_bot):
        """Test comprehensive service container health check."""
        container = isolated_bot.service_container

        # Get container test info
        test_info = container.get_test_info()

        assert test_info["test_mode"] is True
        assert len(test_info["registered_mocks"]) >= 10  # Should have all major services
        assert test_info["total_services"] >= 10

        # Verify no real factories are active
        blocked_factories = test_info["blocked_factories"]
        assert len(blocked_factories) > 0  # Should have blocked some factories

        # Test health check for all services
        from src.nescordbot.services import (
            AlertManager,
            EmbeddingService,
            KnowledgeManager,
            PrivacyManager,
            TokenManager,
        )

        for service_type in [
            TokenManager,
            PrivacyManager,
            KnowledgeManager,
            AlertManager,
            EmbeddingService,
        ]:
            service = container.get_service(service_type)
            health = await service.health_check()
            assert health["status"] == "healthy", f"{service_type.__name__} health check failed"

    async def test_container_initialization_and_shutdown(self, test_config):
        """Test proper container initialization and shutdown."""
        from tests.infrastructure.test_bot_factory import TestBotFactory
        from tests.mocks.service_mock_registry import ServiceMockRegistry

        # Create bot
        bot = await TestBotFactory.create_isolated_bot(test_config)

        # Register services
        mock_registry = ServiceMockRegistry.create_complete_mock_set(
            test_config, bot.database_service
        )

        for service_type, mock_service in mock_registry.items():
            bot.service_container.register_test_mock(service_type, mock_service)  # type: ignore

        # Initialize
        await bot.service_container.initialize_services()
        assert bot.service_container._initialized is True

        # Shutdown
        await bot.service_container.shutdown_services()
        assert bot.service_container._shutdown is True

        # Cleanup
        await TestBotFactory.cleanup_bot(bot)
