"""
Tests for TokenManager service.

This module contains comprehensive tests for token usage tracking,
cost calculation, and limit management functionality.
"""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.nescordbot.config import BotConfig
from src.nescordbot.services.database import DatabaseService
from src.nescordbot.services.token_manager import (
    TokenLimitExceededError,
    TokenManager,
    TokenUsageError,
)


class TestTokenManager:
    """Test TokenManager functionality."""

    @pytest.fixture
    def temp_config(self):
        """Create temporary config for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = MagicMock(spec=BotConfig)
            config.database_url = f"sqlite:///{temp_dir}/test.db"
            config.gemini_monthly_limit = 100000
            config.openai_monthly_limit = 50000
            yield config

    @pytest.fixture
    async def token_manager(self, temp_config):
        """Create TokenManager instance for testing."""
        database_service = DatabaseService(temp_config.database_url)
        await database_service.initialize()

        manager = TokenManager(temp_config, database_service)
        await manager.init_async()

        yield manager

        await database_service.close()

    @pytest.mark.asyncio
    async def test_initialization(self, temp_config):
        """Test TokenManager initialization."""
        database_service = DatabaseService(temp_config.database_url)
        await database_service.initialize()

        manager = TokenManager(temp_config, database_service)
        assert not manager._initialized

        await manager.init_async()
        assert manager._initialized

        # Test double initialization
        await manager.init_async()
        assert manager._initialized

        await database_service.close()

    @pytest.mark.asyncio
    async def test_table_creation(self, token_manager):
        """Test that token usage table is created properly."""
        async with token_manager.db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='token_usage'"
            )
            table_exists = await cursor.fetchone()
            assert table_exists is not None

    @pytest.mark.asyncio
    async def test_record_usage_basic(self, token_manager):
        """Test basic token usage recording."""
        await token_manager.record_usage(
            provider="gemini",
            model="text-embedding-004",
            input_tokens=100,
            output_tokens=50,
            user_id="test_user_123",
            request_type="embedding",
        )

        # Verify record was created
        async with token_manager.db.get_connection() as conn:
            cursor = await conn.execute("SELECT * FROM token_usage WHERE provider = 'gemini'")
            record = await cursor.fetchone()

        assert record is not None
        assert record[1] == "gemini"  # provider
        assert record[2] == "text-embedding-004"  # model
        assert record[3] == 100  # input_tokens
        assert record[4] == 50  # output_tokens
        assert record[6] == "test_user_123"  # user_id
        assert record[7] == "embedding"  # request_type

    @pytest.mark.asyncio
    async def test_record_usage_with_metadata(self, token_manager):
        """Test recording usage with metadata."""
        metadata = {"request_id": "abc123", "duration_ms": 500}

        await token_manager.record_usage(
            provider="openai",
            model="gpt-3.5-turbo",
            input_tokens=200,
            output_tokens=100,
            metadata=metadata,
        )

        async with token_manager.db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT metadata FROM token_usage WHERE provider = 'openai'"
            )
            record = await cursor.fetchone()

        stored_metadata = json.loads(record[0])
        assert stored_metadata == metadata

    def test_cost_calculation(self, token_manager):
        """Test token cost calculation for different providers."""
        # Test Gemini costs
        gemini_cost = token_manager.calculate_cost("gemini", "text-embedding-004", 1000)
        assert gemini_cost == 0.000625  # $0.000625 per 1K tokens

        # Test OpenAI costs
        openai_cost = token_manager.calculate_cost("openai", "gpt-3.5-turbo", 1000)
        assert openai_cost == 0.0015  # $0.0015 per 1K tokens

        # Test unknown provider/model
        unknown_cost = token_manager.calculate_cost("unknown", "unknown-model", 1000)
        assert unknown_cost == 0.0

    @pytest.mark.asyncio
    async def test_monthly_usage_calculation(self, token_manager):
        """Test monthly usage statistics calculation."""
        # Record some usage data
        test_data = [
            ("gemini", "text-embedding-004", 500, 0),
            ("gemini", "text-embedding-004", 300, 0),
            ("openai", "gpt-3.5-turbo", 100, 200),
        ]

        for provider, model, input_tokens, output_tokens in test_data:
            await token_manager.record_usage(
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        # Get monthly usage
        usage = await token_manager.get_monthly_usage()

        assert usage["total_tokens"] == 1100  # Sum of all tokens
        assert len(usage["providers"]) == 2  # 2 different models
        assert usage["total_cost_usd"] > 0  # Should have calculated cost

        # Test provider-specific usage
        gemini_usage = await token_manager.get_monthly_usage("gemini")
        assert gemini_usage["total_tokens"] == 800  # Only Gemini tokens

    @pytest.mark.asyncio
    async def test_usage_limits_check(self, token_manager):
        """Test usage limit checking functionality."""
        # Record usage that approaches limit
        await token_manager.record_usage(
            provider="gemini",
            model="text-embedding-004",
            input_tokens=85000,  # 85% of 100k limit
            output_tokens=0,
        )

        # Check limits
        limits = await token_manager.check_limits("gemini")

        assert limits["provider"] == "gemini"
        assert limits["current_monthly_tokens"] == 85000
        assert limits["monthly_limit"] == 100000
        assert limits["approaching_limit"] is True  # > 80%
        assert limits["monthly_limit_exceeded"] is False

    @pytest.mark.asyncio
    async def test_usage_limits_exceeded(self, token_manager):
        """Test detection of exceeded usage limits."""
        # Record usage that exceeds limit
        await token_manager.record_usage(
            provider="gemini",
            model="text-embedding-004",
            input_tokens=150000,  # Exceeds 100k limit
            output_tokens=0,
        )

        limits = await token_manager.check_limits("gemini")

        assert limits["monthly_limit_exceeded"] is True
        assert limits["monthly_usage_percentage"] > 100

    @pytest.mark.asyncio
    async def test_usage_history(self, token_manager):
        """Test usage history retrieval."""
        # Record multiple usage entries
        test_entries = [
            ("gemini", "text-embedding-004", 100, 0, "user1"),
            ("openai", "gpt-3.5-turbo", 50, 100, "user2"),
            ("gemini", "text-embedding-004", 200, 0, "user1"),
        ]

        for provider, model, input_tokens, output_tokens, user_id in test_entries:
            await token_manager.record_usage(
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                user_id=user_id,
            )

        # Get all history
        history = await token_manager.get_usage_history(days=7)
        assert len(history) == 3

        # Get provider-specific history
        gemini_history = await token_manager.get_usage_history(provider="gemini", days=7)
        assert len(gemini_history) == 2

        # Get user-specific history
        user_history = await token_manager.get_usage_history(user_id="user1", days=7)
        assert len(user_history) == 2

    @pytest.mark.asyncio
    async def test_error_handling(self, temp_config):
        """Test error handling in various scenarios."""
        # Test with invalid database
        invalid_config = MagicMock(spec=BotConfig)
        invalid_config.database_url = "invalid://database"

        database_service = DatabaseService(temp_config.database_url)
        await database_service.initialize()

        manager = TokenManager(invalid_config, database_service)

        # Should handle initialization errors gracefully
        with patch.object(manager, "_create_tables", side_effect=Exception("DB Error")):
            with pytest.raises(TokenUsageError):
                await manager.init_async()

        await database_service.close()

    @pytest.mark.asyncio
    async def test_health_check(self, token_manager):
        """Test TokenManager health check functionality."""
        # Test healthy state
        health = await token_manager.health_check()
        assert health["status"] == "healthy"
        assert health["initialized"] is True
        assert "recent_records" in health
        assert "supported_providers" in health

    @pytest.mark.asyncio
    async def test_health_check_uninitialized(self, temp_config):
        """Test health check when not initialized."""
        database_service = DatabaseService(temp_config.database_url)
        await database_service.initialize()

        manager = TokenManager(temp_config, database_service)

        health = await manager.health_check()
        assert health["status"] == "unhealthy"
        assert "Not initialized" in health["error"]

        await database_service.close()

    @pytest.mark.asyncio
    async def test_close(self, token_manager):
        """Test proper cleanup on close."""
        assert token_manager._initialized is True

        await token_manager.close()
        assert token_manager._initialized is False


class TestTokenManagerIntegration:
    """Integration tests for TokenManager with real database operations."""

    @pytest.fixture
    async def integrated_manager(self):
        """Create fully integrated TokenManager for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = MagicMock(spec=BotConfig)
            config.database_url = f"sqlite:///{temp_dir}/integration.db"
            config.gemini_monthly_limit = 1000000
            config.openai_monthly_limit = 500000

            database_service = DatabaseService(config.database_url)
            await database_service.initialize()

            manager = TokenManager(config, database_service)
            await manager.init_async()

            yield manager

            await database_service.close()

    @pytest.mark.asyncio
    async def test_real_world_scenario(self, integrated_manager):
        """Test realistic usage scenario with multiple providers."""
        # Simulate a day of usage
        scenarios = [
            # Morning: Multiple embedding requests
            ("gemini", "text-embedding-004", 1000, 0, "user_123", "embedding"),
            ("gemini", "text-embedding-004", 800, 0, "user_456", "embedding"),
            ("gemini", "text-embedding-004", 1200, 0, "user_123", "embedding"),
            # Afternoon: Chat requests
            ("openai", "gpt-3.5-turbo", 500, 1000, "user_789", "chat"),
            ("openai", "gpt-3.5-turbo", 300, 800, "user_123", "chat"),
            # Evening: More embeddings
            ("gemini", "text-embedding-004", 600, 0, "user_456", "embedding"),
        ]

        for provider, model, input_tokens, output_tokens, user_id, request_type in scenarios:
            await integrated_manager.record_usage(
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                user_id=user_id,
                request_type=request_type,
            )

        # Analyze results
        monthly_usage = await integrated_manager.get_monthly_usage()
        assert monthly_usage["total_tokens"] == 6200

        gemini_usage = await integrated_manager.get_monthly_usage("gemini")
        assert gemini_usage["total_tokens"] == 3600

        openai_usage = await integrated_manager.get_monthly_usage("openai")
        assert openai_usage["total_tokens"] == 2600

        # Check limits
        gemini_limits = await integrated_manager.check_limits("gemini")
        assert not gemini_limits["monthly_limit_exceeded"]

        # Get history
        history = await integrated_manager.get_usage_history(days=1)
        assert len(history) == 6

        # User-specific analysis
        user_history = await integrated_manager.get_usage_history(user_id="user_123")
        assert len([h for h in user_history if h["user_id"] == "user_123"]) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
