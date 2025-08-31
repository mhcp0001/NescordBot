"""Test FallbackManager functionality."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest

from src.nescordbot.config import BotConfig
from src.nescordbot.services.fallback_manager import (
    FallbackLevel,
    FallbackManager,
    FallbackManagerError,
    ServicePriority,
)


@pytest.fixture
def mock_config():
    """Mock BotConfig for testing."""
    config = Mock(spec=BotConfig)
    return config


@pytest.fixture
async def fallback_manager(mock_config):
    """Create FallbackManager instance for testing."""
    manager = FallbackManager(mock_config)
    await manager.initialize()
    return manager


class TestFallbackManager:
    """Test FallbackManager functionality."""

    async def test_initialization(self, fallback_manager):
        """Test FallbackManager initialization."""
        assert fallback_manager._initialized is True
        assert fallback_manager._current_level == FallbackLevel.NORMAL
        assert fallback_manager._manual_override is False
        assert len(fallback_manager._service_states) > 0

        # Check all services are initially active
        for service, active in fallback_manager._service_states.items():
            assert active is True

    async def test_fallback_level_calculation(self, fallback_manager):
        """Test fallback level calculation based on usage percentage."""
        # Test normal level (< 90%)
        usage_data = {"monthly_usage_percentage": 85.0}
        level = await fallback_manager.check_and_update_fallback_level(usage_data)
        assert level == FallbackLevel.NORMAL

        # Test limited level (90-95%)
        usage_data = {"monthly_usage_percentage": 92.0}
        level = await fallback_manager.check_and_update_fallback_level(usage_data)
        assert level == FallbackLevel.LIMITED

        # Test critical level (95-100%)
        usage_data = {"monthly_usage_percentage": 97.0}
        level = await fallback_manager.check_and_update_fallback_level(usage_data)
        assert level == FallbackLevel.CRITICAL

        # Test emergency level (>= 100%)
        usage_data = {"monthly_usage_percentage": 102.0}
        level = await fallback_manager.check_and_update_fallback_level(usage_data)
        assert level == FallbackLevel.EMERGENCY

    async def test_service_state_updates(self, fallback_manager):
        """Test service state updates based on fallback level."""
        # Test LIMITED level - only essential and important services
        usage_data = {"monthly_usage_percentage": 92.0}
        await fallback_manager.check_and_update_fallback_level(usage_data)

        states = fallback_manager.get_service_states()
        assert states["embedding"] is True  # Essential
        assert states["knowledge_search"] is True  # Essential
        assert states["tag_suggestion"] is True  # Important
        assert states["content_expansion"] is False  # Optional

        # Test CRITICAL level - only essential services
        usage_data = {"monthly_usage_percentage": 97.0}
        await fallback_manager.check_and_update_fallback_level(usage_data)

        states = fallback_manager.get_service_states()
        assert states["embedding"] is True  # Essential
        assert states["knowledge_search"] is True  # Essential
        assert states["tag_suggestion"] is False  # Important -> disabled
        assert states["content_expansion"] is False  # Optional

        # Test EMERGENCY level - no services
        usage_data = {"monthly_usage_percentage": 105.0}
        await fallback_manager.check_and_update_fallback_level(usage_data)

        states = fallback_manager.get_service_states()
        for service, active in states.items():
            assert active is False

    async def test_cache_functionality(self, fallback_manager):
        """Test cache operations."""
        # Test cache storage
        test_data = {"key": "value", "number": 42}
        await fallback_manager.cache_data("test_type", "test_key", test_data)

        # Test cache retrieval
        cached_data = await fallback_manager.get_cached_data("test_type", "test_key")
        assert cached_data == test_data

        # Test cache miss
        missing_data = await fallback_manager.get_cached_data("test_type", "missing_key")
        assert missing_data is None

        # Test cache stats
        stats = fallback_manager.get_cache_stats()
        assert stats["total_entries"] >= 1
        assert "test_type" in stats["types"]

    async def test_cache_ttl(self, fallback_manager):
        """Test cache TTL functionality."""
        # Override TTL for testing
        fallback_manager._cache_ttl["test_cache"] = timedelta(milliseconds=100)

        # Cache some data
        await fallback_manager.cache_data("test_cache", "ttl_key", "test_data")

        # Should be available immediately
        cached_data = await fallback_manager.get_cached_data("test_cache", "ttl_key")
        assert cached_data == "test_data"

        # Wait for TTL to expire
        await asyncio.sleep(0.2)

        # Should be None after TTL expires
        expired_data = await fallback_manager.get_cached_data("test_cache", "ttl_key")
        assert expired_data is None

    async def test_cache_clear(self, fallback_manager):
        """Test cache clearing functionality."""
        # Add some test data
        await fallback_manager.cache_data("type1", "key1", "data1")
        await fallback_manager.cache_data("type2", "key2", "data2")

        # Verify data is cached
        assert await fallback_manager.get_cached_data("type1", "key1") == "data1"
        assert await fallback_manager.get_cached_data("type2", "key2") == "data2"

        # Clear specific cache type
        await fallback_manager.clear_cache("type1")

        # Verify type1 is cleared but type2 remains
        assert await fallback_manager.get_cached_data("type1", "key1") is None
        assert await fallback_manager.get_cached_data("type2", "key2") == "data2"

        # Clear all cache
        await fallback_manager.clear_cache()

        # Verify all cache is cleared
        assert await fallback_manager.get_cached_data("type2", "key2") is None

    async def test_manual_override(self, fallback_manager):
        """Test manual override functionality."""
        # Set manual override to EMERGENCY
        await fallback_manager.set_manual_override(True, FallbackLevel.EMERGENCY)

        assert fallback_manager._manual_override is True
        assert fallback_manager.get_current_level() == FallbackLevel.EMERGENCY

        # Try to update level normally - should be ignored
        usage_data = {"monthly_usage_percentage": 50.0}  # Should be NORMAL
        level = await fallback_manager.check_and_update_fallback_level(usage_data)
        assert level == FallbackLevel.EMERGENCY  # Should remain EMERGENCY

        # Disable manual override
        await fallback_manager.set_manual_override(False)
        assert fallback_manager._manual_override is False

    async def test_service_availability_check(self, fallback_manager):
        """Test service availability checking."""
        # Initially all services should be available (NORMAL level)
        assert fallback_manager.is_service_available("embedding") is True
        assert fallback_manager.is_service_available("tag_suggestion") is True
        assert fallback_manager.is_service_available("content_expansion") is True

        # Switch to CRITICAL level
        usage_data = {"monthly_usage_percentage": 97.0}
        await fallback_manager.check_and_update_fallback_level(usage_data)

        # Check availability after level change
        assert fallback_manager.is_service_available("embedding") is True  # Essential
        assert fallback_manager.is_service_available("tag_suggestion") is False  # Important
        assert fallback_manager.is_service_available("content_expansion") is False  # Optional

    async def test_health_check(self, fallback_manager):
        """Test health check functionality."""
        health = await fallback_manager.health_check()

        assert health["status"] == "healthy"
        assert "current_level" in health
        assert "manual_override" in health
        assert "active_services" in health
        assert "total_services" in health
        assert "cache_entries" in health

        assert isinstance(health["active_services"], int)
        assert isinstance(health["total_services"], int)
        assert health["active_services"] <= health["total_services"]

    async def test_alert_mechanism(self, fallback_manager):
        """Test alert sending mechanism."""
        # Reset alert state
        fallback_manager._alert_sent = False

        # Trigger CRITICAL level (should send alert)
        usage_data = {"monthly_usage_percentage": 97.0}
        await fallback_manager.check_and_update_fallback_level(usage_data)

        # Alert should be marked as sent
        assert fallback_manager._alert_sent is True

        # Reset and try EMERGENCY level
        fallback_manager._alert_sent = False
        usage_data = {"monthly_usage_percentage": 105.0}
        await fallback_manager.check_and_update_fallback_level(usage_data)

        # Alert should be marked as sent for EMERGENCY too
        assert fallback_manager._alert_sent is True

    async def test_service_priority_logic(self, fallback_manager):
        """Test service priority logic."""
        # Test priority determination
        assert (
            fallback_manager._should_service_be_active(
                ServicePriority.ESSENTIAL, FallbackLevel.EMERGENCY
            )
            is False
        )  # Even essential services are disabled in EMERGENCY

        assert (
            fallback_manager._should_service_be_active(
                ServicePriority.ESSENTIAL, FallbackLevel.CRITICAL
            )
            is True
        )

        assert (
            fallback_manager._should_service_be_active(
                ServicePriority.IMPORTANT, FallbackLevel.LIMITED
            )
            is True
        )

        assert (
            fallback_manager._should_service_be_active(
                ServicePriority.OPTIONAL, FallbackLevel.LIMITED
            )
            is False
        )

    async def test_close_cleanup(self, fallback_manager):
        """Test proper cleanup on close."""
        # Add some cache data
        await fallback_manager.cache_data("test", "key", "data")
        assert len(fallback_manager._cache_data) > 0

        # Close should clear cache and reset state
        await fallback_manager.close()

        assert fallback_manager._initialized is False
        assert len(fallback_manager._cache_data) == 0

    async def test_error_conditions(self, mock_config):
        """Test error handling conditions."""
        manager = FallbackManager(mock_config)

        # Test uninitialized usage
        usage_data = {"monthly_usage_percentage": 50.0}
        level = await manager.check_and_update_fallback_level(usage_data)
        # Should auto-initialize and work
        assert level == FallbackLevel.NORMAL
        assert manager._initialized is True
