"""
Essential Phase 4 integration tests for NescordBot.

This module contains simplified but comprehensive integration tests that verify
the core functionality of Phase 4 services in their current implementation state.
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.nescordbot.bot import NescordBot
from src.nescordbot.config import BotConfig
from src.nescordbot.services import (
    AlertManager,
    APIMonitor,
    ChromaDBService,
    EmbeddingService,
    FallbackManager,
    KnowledgeManager,
    PrivacyManager,
    SearchEngine,
    TokenManager,
)


class TestPhase4EssentialIntegration:
    """Essential integration tests for Phase 4 services."""

    @pytest.fixture
    async def essential_config(self, tmp_path):
        """Create minimal test configuration."""
        config = BotConfig(
            # Valid formats for validation
            discord_token=("TEST_TOKEN_NOT_REAL.XXXXXX.DUMMY_VALUE_FOR_TESTING_ONLY"),
            openai_api_key="sk-1234567890abcdef1234567890abcdef1234567890abcdef12",
            gemini_api_key="AIzaSyB1234567890abcdefghijklmnopqrstuvwxyz",
            # Basic settings
            data_directory=str(tmp_path / "data"),
            database_url=f"sqlite:///{tmp_path / 'test.db'}",
            chromadb_path=str(tmp_path / "chromadb"),
            # Phase 4 minimal settings
            enable_pkm=True,
            privacy_enabled=True,
            alert_enabled=True,
        )
        return config

    @pytest.fixture
    async def essential_bot(self, essential_config):
        """Create bot with essential services only."""
        from src.nescordbot.services.obsidian_github import ObsidianGitHubService

        with patch("discord.Client.login"), patch("discord.Client.connect"), patch(
            "src.nescordbot.config.get_config_manager"
        ) as mock_config:
            # Mock config manager
            mock_manager = Mock()
            mock_manager.config = essential_config
            mock_config.return_value = mock_manager

            bot = NescordBot()
            bot.config = essential_config

            # Mock ObsidianGitHubService
            mock_obsidian = Mock(spec=ObsidianGitHubService)
            mock_obsidian.is_healthy = Mock(return_value=True)
            bot.service_container.register_singleton(ObsidianGitHubService, mock_obsidian)

            yield bot

            # Cleanup
            if hasattr(bot, "service_container"):
                await bot.service_container.shutdown_services()

    async def test_service_container_health(self, essential_bot):
        """Test that ServiceContainer and core services are healthy."""
        container = essential_bot.service_container

        # Verify core services are registered
        assert container.has_service(EmbeddingService)
        assert container.has_service(TokenManager)
        assert container.has_service(AlertManager)
        assert container.has_service(PrivacyManager)

        # Test service instantiation
        token_manager = container.get_service(TokenManager)
        assert token_manager is not None

        # Test dependency injection
        privacy_manager = container.get_service(PrivacyManager)
        assert privacy_manager is not None
        assert hasattr(privacy_manager, "alert_manager")

    async def test_privacy_manager_basic_functionality(self, essential_bot):
        """Test PrivacyManager basic PII detection."""
        privacy_manager = essential_bot.service_container.get_service(PrivacyManager)

        # Test PII detection
        text_with_email = "Contact me at john.doe@example.com for more info"
        detected_rules = await privacy_manager.detect_pii(text_with_email)

        assert len(detected_rules) > 0
        # Should detect email pattern
        assert any("email" in rule.name.lower() for rule in detected_rules)

        # Test masking
        from src.nescordbot.services.privacy_manager import PrivacyLevel

        masked_text = await privacy_manager.apply_masking(text_with_email, PrivacyLevel.HIGH)
        assert "john.doe@example.com" not in masked_text
        assert "***" in masked_text or "REDACTED" in masked_text

    async def test_alert_manager_basic_functionality(self, essential_bot):
        """Test AlertManager basic functionality."""
        alert_manager = essential_bot.service_container.get_service(AlertManager)

        # Test health check
        health = await alert_manager.health_check()
        assert isinstance(health, dict)
        assert "status" in health

        # Test alert creation
        from datetime import datetime

        from src.nescordbot.services.alert_manager import Alert, AlertSeverity

        test_alert = Alert(
            id="test_alert_1",
            title="Test Alert",
            message="This is a test alert",
            severity=AlertSeverity.WARNING,
            timestamp=datetime.now(),
            source="integration_test",
            metadata={},
        )

        # Should not raise exception
        await alert_manager.send_alert(test_alert)

    async def test_embedding_service_basic_functionality(self, essential_bot):
        """Test EmbeddingService basic functionality."""
        # Mock the actual API call for testing
        embedding_service = essential_bot.service_container.get_service(EmbeddingService)

        with patch.object(
            embedding_service,
            "_generate_embedding_batch",
            return_value=[{"embedding": [0.1, 0.2, 0.3], "text": "test"}],
        ):
            result = await embedding_service.create_embedding("test text")
            assert result is not None
            assert hasattr(result, "embedding")
            assert hasattr(result, "text")

    async def test_token_manager_basic_functionality(self, essential_bot):
        """Test TokenManager basic functionality."""
        token_manager = essential_bot.service_container.get_service(TokenManager)

        # Test usage tracking
        await token_manager.track_usage("test_service", 100, "test")

        # Test rate limiting
        is_allowed = await token_manager.check_rate_limit("test_user", "test_operation")
        assert isinstance(is_allowed, bool)

        # Test statistics
        stats = await token_manager.get_usage_stats("test_service")
        assert isinstance(stats, dict)

    async def test_service_interaction_basic(self, essential_bot):
        """Test basic interaction between services."""
        # Get services
        privacy_manager = essential_bot.service_container.get_service(PrivacyManager)
        alert_manager = essential_bot.service_container.get_service(AlertManager)

        # Test that privacy manager can access alert manager
        assert privacy_manager.alert_manager is not None
        assert isinstance(privacy_manager.alert_manager, AlertManager)

        # Test cross-service functionality
        text_with_pii = "API key: sk-1234567890abcdefghijklmnopqrstuvwxyz"

        # This should trigger PII detection and potentially an alert
        detected = await privacy_manager.detect_pii(text_with_pii)
        assert len(detected) > 0

        # Verify system remains stable after detection
        health = await alert_manager.health_check()
        assert health["status"] in ["healthy", "warning"]

    async def test_concurrent_service_access(self, essential_bot):
        """Test concurrent access to services."""
        privacy_manager = essential_bot.service_container.get_service(PrivacyManager)
        token_manager = essential_bot.service_container.get_service(TokenManager)

        async def privacy_task():
            return await privacy_manager.detect_pii("test@example.com")

        async def token_task():
            await token_manager.track_usage("concurrent_test", 50, "test")
            return await token_manager.get_usage_stats("concurrent_test")

        # Run concurrently
        privacy_result, token_result = await asyncio.gather(privacy_task(), token_task())

        assert len(privacy_result) > 0  # Should detect email
        assert isinstance(token_result, dict)  # Should return stats

    async def test_service_error_handling(self, essential_bot):
        """Test error handling in services."""
        privacy_manager = essential_bot.service_container.get_service(PrivacyManager)

        # Test with invalid regex pattern (if such functionality exists)
        # This should handle errors gracefully
        try:
            # Test with extremely long text
            very_long_text = "test " * 10000
            result = await privacy_manager.detect_pii(very_long_text)
            assert isinstance(result, list)  # Should handle gracefully
        except Exception as e:
            # If it raises an exception, it should be a known exception type
            assert "PrivacyManager" in str(type(e)) or "timeout" in str(e).lower()

    async def test_system_resource_usage(self, essential_bot):
        """Test system resource usage under normal load."""
        import os

        import psutil

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Perform various operations
        privacy_manager = essential_bot.service_container.get_service(PrivacyManager)
        token_manager = essential_bot.service_container.get_service(TokenManager)

        for i in range(10):
            await privacy_manager.detect_pii(f"Test email {i}: test{i}@example.com")
            await token_manager.track_usage(f"test_service_{i}", 10, "test")

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Memory should not increase dramatically during normal operations
        assert memory_increase < 100, f"Memory increased by {memory_increase:.1f}MB"

    async def test_service_container_shutdown(self, essential_bot):
        """Test graceful shutdown of ServiceContainer."""
        container = essential_bot.service_container

        # Get a service to ensure container is active
        privacy_manager = container.get_service(PrivacyManager)
        assert privacy_manager is not None

        # Shutdown should complete without errors
        await container.shutdown_services()

        # Container should indicate shutdown state
        assert hasattr(container, "_shutdown")


@pytest.mark.integration
class TestPhase4RealWorldScenarios:
    """Real-world integration scenarios for Phase 4."""

    @pytest.fixture
    async def integration_config(self, tmp_path):
        """Configuration for real-world testing."""
        return BotConfig(
            discord_token=("TEST_TOKEN_NOT_REAL.XXXXXX.DUMMY_VALUE_FOR_TESTING_ONLY"),
            openai_api_key="sk-1234567890abcdef1234567890abcdef1234567890abcdef12",
            gemini_api_key="AIzaSyB1234567890abcdefghijklmnopqrstuvwxyz",
            data_directory=str(tmp_path / "data"),
            database_url=f"sqlite:///{tmp_path / 'test.db'}",
            chromadb_path=str(tmp_path / "chromadb"),
            enable_pkm=True,
            privacy_enabled=True,
            privacy_default_level="medium",
            alert_enabled=True,
            max_backups=3,
        )

    @pytest.fixture
    async def integration_bot(self, integration_config):
        """Bot instance for real-world testing."""
        from src.nescordbot.services.obsidian_github import ObsidianGitHubService

        with patch("discord.Client.login"), patch("discord.Client.connect"), patch(
            "src.nescordbot.config.get_config_manager"
        ) as mock_config:
            mock_manager = Mock()
            mock_manager.config = integration_config
            mock_config.return_value = mock_manager

            bot = NescordBot()
            bot.config = integration_config

            # Mock dependencies
            mock_obsidian = Mock(spec=ObsidianGitHubService)
            mock_obsidian.is_healthy = Mock(return_value=True)
            bot.service_container.register_singleton(ObsidianGitHubService, mock_obsidian)

            yield bot

            if hasattr(bot, "service_container"):
                await bot.service_container.shutdown_services()

    async def test_privacy_workflow_realistic(self, integration_bot):
        """Test realistic privacy protection workflow."""
        privacy_manager = integration_bot.service_container.get_service(PrivacyManager)

        # Realistic text samples
        samples = [
            "Please contact me at john.smith@company.com for the proposal.",
            "The API key is sk-abc123def456ghi789 for production access.",
            "Call me at 555-123-4567 or email admin@domain.org",
            "Credit card: 4111-1111-1111-1111 expires 12/25",
            "SSN: 123-45-6789 for verification purposes",
        ]

        for sample in samples:
            # Detect PII
            detected = await privacy_manager.detect_pii(sample)

            if detected:  # If PII is detected
                # Apply appropriate masking
                from src.nescordbot.services.privacy_manager import PrivacyLevel

                # Test different privacy levels
                low_mask = await privacy_manager.apply_masking(sample, PrivacyLevel.LOW)
                medium_mask = await privacy_manager.apply_masking(sample, PrivacyLevel.MEDIUM)
                high_mask = await privacy_manager.apply_masking(sample, PrivacyLevel.HIGH)

                # Verify masking effectiveness increases with privacy level
                assert len(high_mask) <= len(medium_mask) <= len(low_mask)

                # High level should mask most/all sensitive info
                sensitive_patterns = ["@", "sk-", "555-", "4111", "123-45"]
                for pattern in sensitive_patterns:
                    if pattern in sample:
                        assert (
                            pattern not in high_mask
                        ), f"Pattern {pattern} not masked in: {high_mask}"

    async def test_alert_privacy_integration_realistic(self, integration_bot):
        """Test realistic alert-privacy integration."""
        privacy_manager = integration_bot.service_container.get_service(PrivacyManager)
        alert_manager = integration_bot.service_container.get_service(AlertManager)

        # Mock alert sending to avoid actual webhook calls
        with patch.object(alert_manager, "send_alert", new_callable=AsyncMock):
            # Process high-risk PII
            high_risk_text = (
                "Database password: secretpassword123 and API key: sk-live-abc123def456"
            )

            detected = await privacy_manager.detect_pii(high_risk_text)
            assert len(detected) > 0

            # System should remain stable regardless of whether alerts are sent
            health = await alert_manager.health_check()
            assert isinstance(health, dict)

    async def test_performance_under_load(self, integration_bot):
        """Test system performance under realistic load."""
        privacy_manager = integration_bot.service_container.get_service(PrivacyManager)
        token_manager = integration_bot.service_container.get_service(TokenManager)

        import time

        start_time = time.time()

        # Simulate realistic concurrent load
        async def process_message(msg_id):
            text = f"Message {msg_id}: Contact support at help{msg_id}@company.com"

            # Track token usage
            await token_manager.track_usage("message_processing", 25, f"msg_{msg_id}")

            # Process for PII
            detected = await privacy_manager.detect_pii(text)

            if detected:
                from src.nescordbot.services.privacy_manager import PrivacyLevel

                await privacy_manager.apply_masking(text, PrivacyLevel.MEDIUM)

            return len(detected)

        # Process 20 messages concurrently
        tasks = [process_message(i) for i in range(20)]
        results = await asyncio.gather(*tasks)

        elapsed = time.time() - start_time

        # Should process 20 messages within reasonable time
        assert elapsed < 5.0, f"Processing took {elapsed:.2f}s, expected <5s"

        # All messages should be processed
        assert len(results) == 20
        assert all(isinstance(r, int) for r in results)

        # System should remain healthy
        stats = await token_manager.get_usage_stats("message_processing")
        assert stats["total_tokens"] >= 500  # 20 messages * 25 tokens each
