"""
TestBotFactory - Complete Bot Isolation for Testing

This module provides factory methods to create completely isolated
test bots with no real service dependencies.
"""

import logging
from typing import Any, Dict
from unittest.mock import Mock, patch

from src.nescordbot.bot import NescordBot
from src.nescordbot.config import BotConfig
from src.nescordbot.services import DatabaseService

from .test_service_container import TestServiceContainer

logger = logging.getLogger(__name__)


class TestBotFactory:
    """
    Factory for creating completely isolated test bots.

    Ensures that:
    1. No real Discord connections are made
    2. No real services are created
    3. All database operations are mocked
    4. Complete service isolation
    """

    @staticmethod
    async def create_isolated_bot(config: BotConfig) -> NescordBot:
        """
        Create a completely isolated test bot.

        Args:
            config: Test configuration

        Returns:
            Fully isolated NescordBot instance
        """
        logger.info("Creating isolated test bot...")

        with patch("discord.Client.login"), patch("discord.Client.connect"), patch(
            "src.nescordbot.config.get_config_manager"
        ) as mock_config_manager:
            # Mock config manager
            mock_manager = Mock()
            mock_manager.config = config
            mock_config_manager.return_value = mock_manager

            # Create bot instance
            bot = NescordBot()
            bot.config = config

            # Replace with test-only ServiceContainer
            bot.service_container = TestServiceContainer(config)

            # Mock database service completely
            bot.database_service = TestBotFactory._create_mock_database_service()

            logger.info("Isolated test bot created successfully")
            return bot

    @staticmethod
    async def create_bot_with_mocks(
        config: BotConfig, mock_registry: Dict[type, Any]
    ) -> NescordBot:
        """
        Create isolated bot with pre-configured mock registry.

        Args:
            config: Test configuration
            mock_registry: Pre-configured service mocks

        Returns:
            NescordBot with all services mocked
        """
        bot = await TestBotFactory.create_isolated_bot(config)

        # Register all provided mocks
        for service_type, mock_service in mock_registry.items():
            bot.service_container.register_test_mock(service_type, mock_service)  # type: ignore
            logger.debug(f"Registered mock for {service_type.__name__}")

        logger.info(f"Bot created with {len(mock_registry)} pre-configured mocks")
        return bot

    @staticmethod
    def _create_mock_database_service() -> Mock:
        """
        Create a completely mocked DatabaseService.

        Returns:
            Mock DatabaseService that never attempts real operations
        """
        from unittest.mock import AsyncMock, MagicMock

        mock_db = Mock(spec=DatabaseService)
        mock_db._initialized = True

        # Mock connection context manager
        mock_connection = AsyncMock()
        mock_connection.execute = AsyncMock()
        mock_connection.fetchall = AsyncMock(return_value=[])
        mock_connection.fetchone = AsyncMock(return_value=None)
        mock_connection.commit = AsyncMock()

        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_connection)
        mock_context.__aexit__ = AsyncMock()

        # Use MagicMock for method assignment compatibility
        mock_db.get_connection = MagicMock(return_value=mock_context)

        # Mock other essential methods
        mock_db.initialize = AsyncMock()
        mock_db.close = AsyncMock()
        mock_db.health_check = AsyncMock(return_value={"status": "healthy"})

        logger.debug("Created mock database service")
        return mock_db

    @staticmethod
    async def create_performance_test_bot(config: BotConfig) -> NescordBot:
        """
        Create bot optimized for performance testing.

        Uses minimal mocks and optimized for concurrent access.
        """
        bot = await TestBotFactory.create_isolated_bot(config)

        # Import here to avoid circular dependencies
        from tests.mocks.service_mock_registry import ServiceMockRegistry

        # Get performance-optimized mock set
        performance_mocks = ServiceMockRegistry.create_performance_mock_set(
            config, bot.database_service
        )

        # Register all performance mocks
        for service_type, mock_service in performance_mocks.items():
            bot.service_container.register_test_mock(service_type, mock_service)  # type: ignore

        logger.info("Performance test bot created")
        return bot

    @staticmethod
    async def cleanup_bot(bot: NescordBot) -> None:
        """
        Properly cleanup a test bot.

        Args:
            bot: Bot instance to cleanup
        """
        try:
            if hasattr(bot, "service_container") and bot.service_container:
                await bot.service_container.shutdown_services()

            if hasattr(bot, "database_service") and bot.database_service:
                if hasattr(bot.database_service, "close"):
                    await bot.database_service.close()

            logger.debug("Test bot cleaned up successfully")

        except Exception as e:
            logger.error(f"Error during bot cleanup: {e}")
            # Don't raise - cleanup should be fault-tolerant
