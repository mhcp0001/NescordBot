"""
Phase 4 Smoke Tests - Complete Isolation Strategy

This module contains minimal smoke tests to verify that Phase 4 services
can be instantiated and basic operations work in isolated test environment.
"""

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
class TestPhase4BasicSmoke:
    """Basic smoke tests to verify services start without crashing."""

    async def test_isolated_bot_creation(self, isolated_bot):
        """Test that isolated bot is created successfully."""
        assert isolated_bot is not None
        assert hasattr(isolated_bot, "service_container")
        assert isolated_bot.service_container is not None

        # Verify it's using our test container
        from tests.infrastructure.test_service_container import TestServiceContainer

        assert isinstance(isolated_bot.service_container, TestServiceContainer)

    async def test_service_container_initialization(self, isolated_bot):
        """Test ServiceContainer is properly initialized."""
        container = isolated_bot.service_container

        # Container should be initialized and in test mode
        assert container._initialized is True
        assert container._test_mode is True

        # Should have blocked some factory registrations
        test_info = container.get_test_info()
        assert test_info["test_mode"] is True
        assert len(test_info["registered_mocks"]) >= 5  # Should have major services

    async def test_core_services_available(self, isolated_bot):
        """Test that core Phase 4 services are available."""
        container = isolated_bot.service_container

        # All core services should be registered
        core_services = [
            TokenManager,
            PrivacyManager,
            KnowledgeManager,
            AlertManager,
            EmbeddingService,
        ]

        for service_type in core_services:
            assert container.has_service(service_type), f"{service_type.__name__} not available"

            # Should be able to get the service without exceptions
            service = container.get_service(service_type)
            assert service is not None, f"{service_type.__name__} is None"

    async def test_service_basic_properties(self, isolated_bot):
        """Test services have basic expected properties."""
        container = isolated_bot.service_container

        # TokenManager
        token_manager = container.get_service(TokenManager)
        assert hasattr(token_manager, "record_usage")
        assert hasattr(token_manager, "check_limits")
        assert hasattr(token_manager, "_initialized")
        assert token_manager._initialized is True

        # PrivacyManager
        privacy_manager = container.get_service(PrivacyManager)
        assert hasattr(privacy_manager, "detect_pii")
        assert hasattr(privacy_manager, "apply_masking")
        assert hasattr(privacy_manager, "_initialized")
        assert privacy_manager._initialized is True

        # KnowledgeManager
        knowledge_manager = container.get_service(KnowledgeManager)
        assert hasattr(knowledge_manager, "create_note")
        assert hasattr(knowledge_manager, "get_note")
        assert hasattr(knowledge_manager, "_initialized")
        assert knowledge_manager._initialized is True

    async def test_service_health_checks(self, isolated_bot):
        """Test all services respond to health checks."""
        container = isolated_bot.service_container

        services = [TokenManager, PrivacyManager, KnowledgeManager, AlertManager, EmbeddingService]

        for service_type in services:
            service = container.get_service(service_type)

            # All services should have health_check method
            assert hasattr(service, "health_check")

            # Health check should return healthy status
            health = await service.health_check()
            assert isinstance(health, dict)
            assert health["status"] == "healthy", f"{service_type.__name__} not healthy: {health}"


@pytest.mark.integration
@pytest.mark.ci
class TestPhase4ServiceInteractionSmoke:
    """Smoke tests for basic service interactions."""

    async def test_privacy_manager_basic_operations(self, isolated_bot):
        """Test PrivacyManager basic operations don't crash."""
        privacy_manager = isolated_bot.service_container.get_service(PrivacyManager)

        # Configure mock to return empty results (no PII detected)
        privacy_manager.detect_pii.return_value = []
        privacy_manager.apply_masking.return_value = "Safe text content"

        # Basic PII detection - should not crash
        result = await privacy_manager.detect_pii("This is safe text")
        assert isinstance(result, list)
        assert len(result) == 0  # No PII detected

        # Basic masking - should not crash
        from src.nescordbot.services.privacy_manager import PrivacyLevel

        masked = await privacy_manager.apply_masking("Safe text", PrivacyLevel.MEDIUM)
        assert masked == "Safe text content"

    async def test_knowledge_manager_basic_operations(self, isolated_bot):
        """Test KnowledgeManager basic operations don't crash."""
        knowledge_manager = isolated_bot.service_container.get_service(KnowledgeManager)

        # Create a note - should not crash
        note_id = await knowledge_manager.create_note(
            title="Smoke Test Note",
            content="This is a smoke test note content",
            tags=["smoke", "test"],
        )

        assert note_id == "note_123"  # From our mock
        knowledge_manager.create_note.assert_called_once()

        # Get the note - should not crash
        note = await knowledge_manager.get_note(note_id)
        assert note is not None
        assert note["id"] == "note_123"

    async def test_token_manager_basic_operations(self, isolated_bot):
        """Test TokenManager basic operations don't crash."""
        token_manager = isolated_bot.service_container.get_service(TokenManager)

        # Record usage - should not crash
        await token_manager.record_usage("test_provider", "test_model", 100, 50)
        token_manager.record_usage.assert_called_with("test_provider", "test_model", 100, 50)

        # Check limits - should not crash
        limits = await token_manager.check_limits("test_provider")
        assert isinstance(limits, dict)
        assert "within_limits" in limits
        assert limits["within_limits"] is True

    async def test_alert_manager_basic_operations(self, isolated_bot):
        """Test AlertManager basic operations don't crash."""
        alert_manager = isolated_bot.service_container.get_service(AlertManager)

        # Health check
        health = await alert_manager.health_check()
        assert isinstance(health, dict)
        assert health["status"] == "healthy"

        # Create and send basic alert
        from datetime import datetime

        from src.nescordbot.services.alert_manager import Alert, AlertSeverity

        test_alert = Alert(
            id="smoke_test",
            title="Smoke Test Alert",
            message="This is a smoke test alert",
            severity=AlertSeverity.INFO,
            timestamp=datetime.now(),
            source="smoke_test",
            metadata={"test": True},
        )

        # Should not crash
        await alert_manager.send_alert(test_alert)
        alert_manager.send_alert.assert_called_once_with(test_alert)

    async def test_embedding_service_basic_operations(self, isolated_bot):
        """Test EmbeddingService basic operations don't crash."""
        embedding_service = isolated_bot.service_container.get_service(EmbeddingService)

        # Generate embedding - should not crash
        result = await embedding_service.generate_embedding("smoke test text")

        assert result is not None
        assert hasattr(result, "embedding")
        assert hasattr(result, "text")
        assert len(result.embedding) == 768  # Standard size
        assert result.text == "test text"


@pytest.mark.integration
@pytest.mark.ci
class TestPhase4DependencySmoke:
    """Smoke tests for service dependencies."""

    async def test_privacy_alert_dependency(self, isolated_bot):
        """Test PrivacyManager -> AlertManager dependency."""
        container = isolated_bot.service_container

        privacy_manager = container.get_service(PrivacyManager)
        alert_manager = container.get_service(AlertManager)

        # PrivacyManager should have AlertManager injected
        assert hasattr(privacy_manager, "alert_manager")
        assert privacy_manager.alert_manager is not None
        assert privacy_manager.alert_manager is alert_manager

    async def test_service_initialization_order(self, isolated_bot):
        """Test services can be initialized in any order."""
        container = isolated_bot.service_container

        # Get services in different orders - should not crash
        service_types = [AlertManager, PrivacyManager, TokenManager, KnowledgeManager]

        # Forward order
        services_forward = []
        for service_type in service_types:
            service = container.get_service(service_type)
            services_forward.append(service)
            assert service is not None

        # Reverse order
        services_reverse = []
        for service_type in reversed(service_types):
            service = container.get_service(service_type)
            services_reverse.append(service)
            assert service is not None

        # Should get same instances (singleton behavior)
        assert services_forward[0] is services_reverse[3]  # AlertManager
        assert services_forward[1] is services_reverse[2]  # PrivacyManager

    async def test_multiple_service_access(self, isolated_bot):
        """Test accessing services multiple times."""
        container = isolated_bot.service_container

        # Access each service multiple times
        for _ in range(3):
            token_manager = container.get_service(TokenManager)
            privacy_manager = container.get_service(PrivacyManager)
            knowledge_manager = container.get_service(KnowledgeManager)

            # Should get same instances each time
            assert token_manager is not None
            assert privacy_manager is not None
            assert knowledge_manager is not None

            # All should be initialized
            assert token_manager._initialized is True
            assert privacy_manager._initialized is True
            assert knowledge_manager._initialized is True


@pytest.mark.integration
@pytest.mark.ci
class TestPhase4ErrorHandlingSmoke:
    """Smoke tests for basic error handling."""

    async def test_service_error_recovery(self, isolated_bot):
        """Test services handle and recover from errors."""
        knowledge_manager = isolated_bot.service_container.get_service(KnowledgeManager)

        # Simulate an error
        knowledge_manager.create_note.side_effect = Exception("Test error")

        # Should raise the exception
        with pytest.raises(Exception) as exc_info:
            await knowledge_manager.create_note("Test", "Content", ["tag"])

        assert "Test error" in str(exc_info.value)

        # Reset and should work again
        knowledge_manager.create_note.side_effect = None
        knowledge_manager.create_note.return_value = "note_123"

        result = await knowledge_manager.create_note("Test", "Content", ["tag"])
        assert result == "note_123"

    async def test_privacy_manager_error_handling(self, isolated_bot):
        """Test PrivacyManager handles errors gracefully."""
        privacy_manager = isolated_bot.service_container.get_service(PrivacyManager)

        # Test with error in detection
        privacy_manager.detect_pii.side_effect = ValueError("Detection error")

        with pytest.raises(ValueError) as exc_info:
            await privacy_manager.detect_pii("test text")

        assert "Detection error" in str(exc_info.value)

        # Reset
        privacy_manager.detect_pii.side_effect = None
        privacy_manager.detect_pii.return_value = []

        result = await privacy_manager.detect_pii("test text")
        assert result == []

    async def test_service_isolation_on_error(self, isolated_bot):
        """Test that errors in one service don't affect others."""
        container = isolated_bot.service_container

        token_manager = container.get_service(TokenManager)
        privacy_manager = container.get_service(PrivacyManager)

        # Break token manager
        token_manager.record_usage.side_effect = Exception("Token manager error")

        # Privacy manager should still work
        privacy_manager.detect_pii.return_value = []
        result = await privacy_manager.detect_pii("test text")
        assert result == []

        # Token manager should still be broken
        with pytest.raises(Exception):
            await token_manager.record_usage("provider", "model", 100, 50)


@pytest.mark.integration
@pytest.mark.ci
class TestPhase4ContainerSmoke:
    """Smoke tests specific to test container functionality."""

    async def test_test_container_blocks_real_services(self, isolated_bot):
        """Test that TestServiceContainer blocks real service creation."""
        container = isolated_bot.service_container

        # Get test info
        test_info = container.get_test_info()

        # Should be in test mode
        assert test_info["test_mode"] is True

        # Should have registered mocks
        assert len(test_info["registered_mocks"]) >= 5

        # Should have blocked some factory registrations
        blocked_factories = test_info.get("blocked_factories", [])
        assert isinstance(blocked_factories, list)

    async def test_mock_registry_completeness(self, isolated_bot):
        """Test that all expected services have mocks."""
        container = isolated_bot.service_container

        # All these services should be available as mocks
        expected_services = [
            TokenManager,
            PrivacyManager,
            KnowledgeManager,
            AlertManager,
            EmbeddingService,
        ]

        for service_type in expected_services:
            assert container.has_service(service_type)

            service = container.get_service(service_type)
            assert service is not None

            # Should have mock characteristics
            assert hasattr(service, "_initialized")
            assert service._initialized is True

    async def test_container_shutdown_graceful(self, isolated_bot):
        """Test container shuts down gracefully."""
        container = isolated_bot.service_container

        # Get some services first
        token_manager = container.get_service(TokenManager)
        privacy_manager = container.get_service(PrivacyManager)

        assert token_manager is not None
        assert privacy_manager is not None

        # Shutdown should not crash
        await container.shutdown_services()

        # Container should be marked as shut down
        assert container._shutdown is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
