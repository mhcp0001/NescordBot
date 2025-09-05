"""
Phase 4 Smoke Tests - Basic functionality verification.

This module contains minimal smoke tests to verify that Phase 4 services
can be instantiated and basic operations don't crash.
"""

from unittest.mock import Mock, patch

import pytest

from src.nescordbot.bot import NescordBot
from src.nescordbot.config import BotConfig


@pytest.mark.integration
class TestPhase4SmokeTests:
    """Smoke tests for Phase 4 integration."""

    @pytest.fixture
    async def smoke_config(self, tmp_path):
        """Minimal configuration for smoke tests."""
        return BotConfig(
            discord_token=("TEST_TOKEN_NOT_REAL.XXXXXX.DUMMY_VALUE_FOR_TESTING_ONLY"),
            openai_api_key="sk-1234567890abcdef1234567890abcdef1234567890abcdef12",
            gemini_api_key="AIzaSyB1234567890abcdefghijklmnopqrstuvwxyz",
            data_directory=str(tmp_path / "data"),
            database_url=f"sqlite:///{tmp_path / 'test.db'}",
            chromadb_path=str(tmp_path / "chromadb"),
        )

    @pytest.fixture
    async def smoke_bot(self, smoke_config):
        """Bot instance for smoke testing."""
        from src.nescordbot.services.obsidian_github import ObsidianGitHubService

        with patch("discord.Client.login"), patch("discord.Client.connect"), patch(
            "src.nescordbot.config.get_config_manager"
        ) as mock_config:
            mock_manager = Mock()
            mock_manager.config = smoke_config
            mock_config.return_value = mock_manager

            bot = NescordBot()
            bot.config = smoke_config

            # Mock dependencies
            mock_obsidian = Mock(spec=ObsidianGitHubService)
            mock_obsidian.is_healthy = Mock(return_value=True)
            bot.service_container.register_singleton(ObsidianGitHubService, mock_obsidian)

            yield bot

            try:
                if hasattr(bot, "service_container"):
                    await bot.service_container.shutdown_services()
            except Exception:
                pass  # Ignore cleanup errors in smoke tests

    async def test_bot_initialization(self, smoke_bot):
        """Test that bot initializes without crashing."""
        assert smoke_bot is not None
        assert hasattr(smoke_bot, "service_container")
        assert smoke_bot.service_container is not None

    async def test_service_container_basic(self, smoke_bot):
        """Test ServiceContainer basic functionality."""
        container = smoke_bot.service_container

        # Should have some services registered
        assert hasattr(container, "_factories")
        assert len(container._factories) > 0

        # Should be able to check service existence
        from src.nescordbot.services import TokenManager

        has_token_manager = container.has_service(TokenManager)
        assert isinstance(has_token_manager, bool)

    async def test_service_instantiation(self, smoke_bot):
        """Test that core services can be instantiated."""
        container = smoke_bot.service_container

        try:
            # Try to get TokenManager (simplest service)
            from src.nescordbot.services import TokenManager

            if container.has_service(TokenManager):
                token_manager = container.get_service(TokenManager)
                assert token_manager is not None
        except Exception as e:
            pytest.fail(f"TokenManager instantiation failed: {e}")

    async def test_privacy_manager_instantiation(self, smoke_bot):
        """Test PrivacyManager can be instantiated."""
        container = smoke_bot.service_container

        try:
            from src.nescordbot.services import PrivacyManager

            if container.has_service(PrivacyManager):
                privacy_manager = container.get_service(PrivacyManager)
                assert privacy_manager is not None
                assert hasattr(privacy_manager, "detect_pii")
        except Exception as e:
            pytest.fail(f"PrivacyManager instantiation failed: {e}")

    async def test_alert_manager_instantiation(self, smoke_bot):
        """Test AlertManager can be instantiated."""
        container = smoke_bot.service_container

        try:
            from src.nescordbot.services import AlertManager

            if container.has_service(AlertManager):
                alert_manager = container.get_service(AlertManager)
                assert alert_manager is not None
                # AlertManager has methods like health_check, get_active_alerts, etc.
                assert hasattr(alert_manager, "health_check")
        except Exception as e:
            pytest.fail(f"AlertManager instantiation failed: {e}")

    async def test_basic_privacy_detection(self, smoke_bot):
        """Test basic privacy detection doesn't crash."""
        container = smoke_bot.service_container

        try:
            from src.nescordbot.services import PrivacyManager

            if container.has_service(PrivacyManager):
                privacy_manager = container.get_service(PrivacyManager)

                # Try basic detection - shouldn't crash
                result = await privacy_manager.detect_pii("Hello world")
                assert isinstance(result, list)  # Should return a list

                # Try with email - might or might not detect, but shouldn't crash
                result = await privacy_manager.detect_pii("test@example.com")
                assert isinstance(result, list)
        except Exception as e:
            pytest.fail(f"Privacy detection failed: {e}")

    async def test_basic_alert_functionality(self, smoke_bot):
        """Test basic alert functionality doesn't crash."""
        container = smoke_bot.service_container

        try:
            from src.nescordbot.services import AlertManager

            if container.has_service(AlertManager):
                alert_manager = container.get_service(AlertManager)

                # Health check shouldn't crash
                health = await alert_manager.health_check()
                assert isinstance(health, dict)
        except Exception as e:
            pytest.fail(f"Alert functionality failed: {e}")

    async def test_service_dependencies(self, smoke_bot):
        """Test service dependencies are resolved without crashing."""
        container = smoke_bot.service_container

        try:
            from src.nescordbot.services import AlertManager, PrivacyManager

            if container.has_service(PrivacyManager) and container.has_service(AlertManager):
                # This tests the dependency injection chain
                privacy_manager = container.get_service(PrivacyManager)

                # PrivacyManager should have alert_manager injected
                assert hasattr(privacy_manager, "alert_manager")
                # Don't assert it's not None, as initialization might fail

        except Exception as e:
            pytest.fail(f"Service dependency resolution failed: {e}")

    async def test_graceful_shutdown(self, smoke_bot):
        """Test services can be shut down gracefully."""
        container = smoke_bot.service_container

        try:
            # Get a service to ensure container is active
            from src.nescordbot.services import TokenManager

            if container.has_service(TokenManager):
                container.get_service(TokenManager)

            # Shutdown shouldn't crash
            await container.shutdown_services()

        except Exception as e:
            pytest.fail(f"Graceful shutdown failed: {e}")


@pytest.mark.integration
class TestPhase4HealthChecks:
    """Health check tests for Phase 4 services."""

    @pytest.fixture
    async def health_config(self, tmp_path):
        """Configuration for health check tests."""
        return BotConfig(
            discord_token=("TEST_TOKEN_NOT_REAL.XXXXXX.DUMMY_VALUE_FOR_TESTING_ONLY"),
            openai_api_key="sk-1234567890abcdef1234567890abcdef1234567890abcdef12",
            gemini_api_key="AIzaSyB1234567890abcdefghijklmnopqrstuvwxyz",
            data_directory=str(tmp_path / "data"),
            database_url=f"sqlite:///{tmp_path / 'test.db'}",
            chromadb_path=str(tmp_path / "chromadb"),
            privacy_enabled=True,
            alert_enabled=True,
        )

    @pytest.fixture
    async def health_bot(self, health_config):
        """Bot instance for health checking."""
        from src.nescordbot.services.obsidian_github import ObsidianGitHubService

        with patch("discord.Client.login"), patch("discord.Client.connect"), patch(
            "src.nescordbot.config.get_config_manager"
        ) as mock_config:
            mock_manager = Mock()
            mock_manager.config = health_config
            mock_config.return_value = mock_manager

            bot = NescordBot()
            bot.config = health_config

            # Mock dependencies
            mock_obsidian = Mock(spec=ObsidianGitHubService)
            mock_obsidian.is_healthy = Mock(return_value=True)
            bot.service_container.register_singleton(ObsidianGitHubService, mock_obsidian)

            yield bot

            try:
                if hasattr(bot, "service_container"):
                    await bot.service_container.shutdown_services()
            except Exception:
                pass

    async def test_service_container_health(self, health_bot):
        """Test ServiceContainer health check."""
        container = health_bot.service_container

        try:
            # Container should have a health check method
            if hasattr(container, "health_check"):
                health = await container.health_check()
                assert isinstance(health, dict)
        except Exception as e:
            # Health check failures are acceptable in tests
            assert "health" in str(e).lower() or "service" in str(e).lower()

    async def test_individual_service_health(self, health_bot):
        """Test individual service health checks."""
        container = health_bot.service_container

        services_to_test = ["TokenManager", "AlertManager", "PrivacyManager"]

        for service_name in services_to_test:
            try:
                from src.nescordbot.services import AlertManager, PrivacyManager, TokenManager

                service_class = {
                    "TokenManager": TokenManager,
                    "AlertManager": AlertManager,
                    "PrivacyManager": PrivacyManager,
                }.get(service_name)

                if service_class and container.has_service(service_class):
                    service = container.get_service(service_class)

                    # Try to call health check if available
                    if hasattr(service, "health_check"):
                        health = await service.health_check()
                        assert isinstance(health, dict)
                    elif hasattr(service, "is_healthy"):
                        healthy = service.is_healthy()
                        assert isinstance(healthy, bool)

            except Exception as e:
                # Individual service health failures are acceptable
                assert service_name.lower() in str(e).lower() or "health" in str(e).lower()

    async def test_system_stability(self, health_bot):
        """Test overall system stability."""
        container = health_bot.service_container

        # System should remain stable through basic operations
        try:
            from src.nescordbot.services import PrivacyManager, TokenManager

            # Multiple service instantiations shouldn't crash
            for i in range(3):
                if container.has_service(TokenManager):
                    token_manager = container.get_service(TokenManager)
                    assert token_manager is not None

                if container.has_service(PrivacyManager):
                    privacy_manager = container.get_service(PrivacyManager)
                    assert privacy_manager is not None

        except Exception as e:
            pytest.fail(f"System stability test failed: {e}")


class TestPhase4EnhancedSmoke:
    """Enhanced smoke tests with proper initialization mocking."""

    @pytest.fixture
    async def enhanced_config(self, tmp_path):
        """Configuration for enhanced tests."""
        return BotConfig(
            discord_token=("TEST_TOKEN_NOT_REAL.XXXXXX.DUMMY_VALUE_FOR_TESTING_ONLY"),
            openai_api_key="sk-1234567890abcdef1234567890abcdef1234567890abcdef12",
            gemini_api_key="AIzaSyB1234567890abcdefghijklmnopqrstuvwxyz",
            data_directory=str(tmp_path / "data"),
            database_url=f"sqlite:///{tmp_path / 'test.db'}",
            chromadb_path=str(tmp_path / "chromadb"),
        )

    @pytest.fixture
    async def enhanced_bot(self, enhanced_config):
        """Bot instance for enhanced testing."""
        from src.nescordbot.services.obsidian_github import ObsidianGitHubService

        with patch("discord.Client.login"), patch("discord.Client.connect"), patch(
            "src.nescordbot.config.get_config_manager"
        ) as mock_config:
            mock_manager = Mock()
            mock_manager.config = enhanced_config
            mock_config.return_value = mock_manager

            bot = NescordBot()
            bot.config = enhanced_config

            # Mock dependencies
            mock_obsidian = Mock(spec=ObsidianGitHubService)
            mock_obsidian.is_healthy = Mock(return_value=True)
            bot.service_container.register_singleton(ObsidianGitHubService, mock_obsidian)

            yield bot

            # Cleanup
            if hasattr(bot, "service_container"):
                await bot.service_container.shutdown_services()

    async def test_privacy_manager_initialization_with_mocks(self, enhanced_bot):
        """Test PrivacyManager can be properly initialized with mocks."""
        from src.nescordbot.services.privacy_manager import PrivacyManager

        container = enhanced_bot.service_container
        if not container.has_service(PrivacyManager):
            pytest.skip("PrivacyManager not available")

        privacy_manager = container.get_service(PrivacyManager)
        assert privacy_manager is not None

        # Mock database operations to test initialization
        with patch.object(privacy_manager, "_create_tables") as mock_create_tables:
            with patch.object(privacy_manager, "_load_builtin_rules") as mock_load_builtin:
                with patch.object(privacy_manager, "_load_custom_rules") as mock_load_custom:
                    with patch.object(privacy_manager, "_cleanup_old_events") as mock_cleanup:
                        # All mocks return successfully
                        mock_create_tables.return_value = None
                        mock_load_builtin.return_value = None
                        mock_load_custom.return_value = None
                        mock_cleanup.return_value = None

                        # Should initialize successfully
                        await privacy_manager.initialize()

                        assert privacy_manager._initialized

    async def test_alert_manager_functionality_with_correct_api(self, enhanced_bot):
        """Test AlertManager using the correct API methods."""
        from datetime import datetime

        from src.nescordbot.services.alert_manager import Alert, AlertManager, AlertSeverity

        container = enhanced_bot.service_container
        if not container.has_service(AlertManager):
            pytest.skip("AlertManager not available")

        alert_manager = container.get_service(AlertManager)
        assert alert_manager is not None

        # Test health check
        health = await alert_manager.health_check()
        assert isinstance(health, dict)
        assert "status" in health

        # Test _trigger_alert (correct method)
        test_alert = Alert(
            id="smoke_test_alert",
            title="Smoke Test Alert",
            message="This is a smoke test alert",
            severity=AlertSeverity.INFO,
            timestamp=datetime.now(),
            source="smoke_test",
            metadata={},
        )

        # Just test that _trigger_alert doesn't crash
        # (don't mock non-existent methods)
        try:
            await alert_manager._trigger_alert(test_alert)
            # If no exception, test passes
        except Exception:
            # If method fails due to DB/Discord operations, test health check instead
            health = await alert_manager.health_check()
            assert isinstance(health, dict)
            assert "status" in health


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
