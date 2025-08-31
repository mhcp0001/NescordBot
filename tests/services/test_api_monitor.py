"""Test APIMonitor functionality."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.nescordbot.config import BotConfig
from src.nescordbot.services.api_monitor import APIMonitor, APIMonitorError
from src.nescordbot.services.fallback_manager import FallbackLevel, FallbackManager
from src.nescordbot.services.token_manager import TokenManager, TokenUsageError


@pytest.fixture
def mock_config():
    """Mock BotConfig for testing."""
    return Mock(spec=BotConfig)


@pytest.fixture
async def mock_token_manager():
    """Mock TokenManager for testing."""
    manager = Mock(spec=TokenManager)
    manager.check_limits = AsyncMock()
    manager.health_check = AsyncMock()
    return manager


@pytest.fixture
async def mock_fallback_manager():
    """Mock FallbackManager for testing."""
    manager = Mock(spec=FallbackManager)
    manager.check_and_update_fallback_level = AsyncMock()
    manager.get_current_level = Mock(return_value=FallbackLevel.NORMAL)
    manager.get_service_states = Mock(return_value={})
    manager.get_cache_stats = Mock(return_value={})
    manager.health_check = AsyncMock()
    manager.set_manual_override = AsyncMock()
    manager.clear_cache = AsyncMock()
    return manager


@pytest.fixture
async def api_monitor(mock_config, mock_token_manager, mock_fallback_manager):
    """Create APIMonitor instance for testing."""
    monitor = APIMonitor(mock_config, mock_token_manager, mock_fallback_manager)
    return monitor


class TestAPIMonitor:
    """Test APIMonitor functionality."""

    async def test_initialization(self, api_monitor):
        """Test APIMonitor initialization."""
        assert api_monitor._monitoring_task is None
        assert api_monitor._monitoring_interval == 300
        assert api_monitor._shutdown is False

    async def test_monitoring_lifecycle(
        self, api_monitor, mock_token_manager, mock_fallback_manager
    ):
        """Test monitoring start/stop lifecycle."""
        # Mock check_limits to return test data
        mock_token_manager.check_limits.return_value = {
            "monthly_usage_percentage": 50.0,
            "current_monthly_tokens": 500000,
            "monthly_limit": 1000000,
        }
        mock_fallback_manager.check_and_update_fallback_level.return_value = FallbackLevel.NORMAL

        # Start monitoring
        await api_monitor.start_monitoring()
        assert api_monitor._monitoring_task is not None
        assert not api_monitor._monitoring_task.done()
        assert api_monitor._shutdown is False

        # Wait a bit to ensure monitoring loop starts
        await asyncio.sleep(0.1)

        # Stop monitoring
        await api_monitor.stop_monitoring()
        assert api_monitor._shutdown is True
        assert api_monitor._monitoring_task.done()

    async def test_force_check(self, api_monitor, mock_token_manager, mock_fallback_manager):
        """Test force check functionality."""
        # Setup mock returns
        usage_data = {
            "monthly_usage_percentage": 75.0,
            "current_monthly_tokens": 750000,
            "monthly_limit": 1000000,
        }
        mock_token_manager.check_limits.return_value = usage_data
        mock_fallback_manager.check_and_update_fallback_level.return_value = FallbackLevel.NORMAL
        mock_fallback_manager.get_service_states.return_value = {
            "embedding": True,
            "tag_suggestion": True,
        }
        mock_fallback_manager.get_cache_stats.return_value = {
            "total_entries": 5,
            "types": {"test": 2},
        }

        # Execute force check
        result = await api_monitor.force_check()

        # Verify results
        assert "timestamp" in result
        assert result["usage_data"] == usage_data
        assert result["fallback_level"] == "normal"
        assert "service_states" in result
        assert "cache_stats" in result

        # Verify mocks were called
        mock_token_manager.check_limits.assert_called_once_with("gemini")
        mock_fallback_manager.check_and_update_fallback_level.assert_called_once_with(usage_data)

    async def test_force_check_error_handling(
        self, api_monitor, mock_token_manager, mock_fallback_manager
    ):
        """Test force check error handling."""
        # Setup mock to raise error
        mock_token_manager.check_limits.side_effect = TokenUsageError("Test error")

        # Should raise APIMonitorError
        with pytest.raises(APIMonitorError):
            await api_monitor.force_check()

    async def test_monitoring_interval_setting(self, api_monitor):
        """Test monitoring interval setting."""
        # Test valid interval
        await api_monitor.set_monitoring_interval(120)
        assert api_monitor._monitoring_interval == 120

        # Test invalid interval (too small)
        with pytest.raises(APIMonitorError):
            await api_monitor.set_monitoring_interval(30)

    async def test_emergency_override(self, api_monitor, mock_fallback_manager):
        """Test emergency override functionality."""
        await api_monitor.emergency_override(FallbackLevel.CRITICAL)

        mock_fallback_manager.set_manual_override.assert_called_once_with(
            True, FallbackLevel.CRITICAL
        )

    async def test_clear_emergency_override(self, api_monitor, mock_fallback_manager):
        """Test clearing emergency override."""
        await api_monitor.clear_emergency_override()

        mock_fallback_manager.set_manual_override.assert_called_once_with(False)

    async def test_cache_management(self, api_monitor, mock_fallback_manager):
        """Test cache management operations."""
        # Test clear all cache
        await api_monitor.clear_cache()
        mock_fallback_manager.clear_cache.assert_called_once_with(None)

        # Test clear specific cache type
        mock_fallback_manager.clear_cache.reset_mock()
        await api_monitor.clear_cache("embeddings")
        mock_fallback_manager.clear_cache.assert_called_once_with("embeddings")

    async def test_monitoring_status(self, api_monitor, mock_fallback_manager):
        """Test monitoring status retrieval."""
        status = await api_monitor.get_monitoring_status()

        assert "monitoring_active" in status
        assert "monitoring_interval" in status
        assert "shutdown" in status
        assert "fallback_level" in status
        assert "service_states" in status

        assert status["monitoring_interval"] == 300
        assert status["shutdown"] is False

    async def test_health_check(self, api_monitor, mock_token_manager, mock_fallback_manager):
        """Test health check functionality."""
        # Setup mock returns
        mock_token_manager.health_check.return_value = {"status": "healthy"}
        mock_fallback_manager.health_check.return_value = {"status": "healthy"}

        health = await api_monitor.health_check()

        assert health["status"] == "healthy"
        assert "components" in health
        assert "token_manager" in health["components"]
        assert "fallback_manager" in health["components"]
        assert "monitoring" in health["components"]

    async def test_health_check_error_handling(
        self, api_monitor, mock_token_manager, mock_fallback_manager
    ):
        """Test health check error handling."""
        # Setup mock to raise error
        mock_token_manager.health_check.side_effect = Exception("Test error")

        health = await api_monitor.health_check()

        assert health["status"] == "error"
        assert "error" in health

    async def test_monitoring_loop_error_handling(
        self, api_monitor, mock_token_manager, mock_fallback_manager
    ):
        """Test monitoring loop error handling."""
        # Setup mock to raise error
        mock_token_manager.check_limits.side_effect = TokenUsageError("Test error")
        mock_fallback_manager.check_and_update_fallback_level.return_value = FallbackLevel.NORMAL

        # Start monitoring (should handle errors gracefully)
        await api_monitor.start_monitoring()

        # Wait a bit to let monitoring loop run and handle error
        await asyncio.sleep(0.1)

        # Stop monitoring
        await api_monitor.stop_monitoring()

        # Should complete without raising unhandled exceptions
        assert api_monitor._shutdown is True

    async def test_close_cleanup(self, api_monitor):
        """Test proper cleanup on close."""
        # Start monitoring first
        await api_monitor.start_monitoring()
        assert api_monitor._monitoring_task is not None

        # Close should stop monitoring
        await api_monitor.close()
        assert api_monitor._shutdown is True
        assert api_monitor._monitoring_task.done()

    async def test_api_limit_check_logic(
        self, api_monitor, mock_token_manager, mock_fallback_manager
    ):
        """Test the core API limit checking logic."""
        usage_data = {
            "monthly_usage_percentage": 95.5,
            "current_monthly_tokens": 955000,
            "monthly_limit": 1000000,
        }
        mock_token_manager.check_limits.return_value = usage_data
        mock_fallback_manager.check_and_update_fallback_level.return_value = FallbackLevel.CRITICAL

        # Test the internal check method
        await api_monitor._check_api_limits()

        # Verify the correct sequence of calls
        mock_token_manager.check_limits.assert_called_once_with("gemini")
        mock_fallback_manager.check_and_update_fallback_level.assert_called_once_with(usage_data)
