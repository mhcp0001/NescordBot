"""
Test cases for ObsidianGitHub service injection bug fix.

Tests that the ObsidianGitHubService is properly initialized and injected
into the Voice cog during bot setup.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.nescordbot.bot import NescordBot
from src.nescordbot.cogs.voice import Voice
from src.nescordbot.services import ObsidianGitHubService


@pytest.fixture
def mock_config():
    """Mock configuration with ObsidianGitHub enabled."""
    config = MagicMock()
    config.discord_token = "test_token"
    config.openai_api_key = "test_openai_key"
    config.database_url = ":memory:"
    config.log_level = "INFO"
    config.max_audio_size_mb = 25
    config.speech_language = "ja"

    # GitHub configuration
    config.github_token = "test_github_token"
    config.github_repo_owner = "test_owner"
    config.github_repo_name = "test_repo"
    config.github_obsidian_enabled = True

    return config


@pytest.fixture
def mock_config_manager():
    """Mock configuration manager."""
    config_manager = MagicMock()
    return config_manager


class TestObsidianServiceInjection:
    """Test ObsidianGitHub service initialization and injection."""

    @patch("src.nescordbot.bot.get_config_manager")
    @patch("src.nescordbot.bot.get_logger")
    def test_bot_initialization_with_obsidian_enabled(
        self, mock_logger, mock_get_config_manager, mock_config, mock_config_manager
    ):
        """Test that bot initializes ObsidianGitHub services when enabled."""
        mock_get_config_manager.return_value = mock_config_manager
        mock_config_manager.config = mock_config
        mock_logger.return_value = MagicMock()

        with patch("src.nescordbot.bot.DatabaseService"), patch(
            "src.nescordbot.bot.SecurityValidator"
        ), patch("src.nescordbot.bot.GitHubAuthManager"), patch(
            "src.nescordbot.bot.GitOperationService"
        ), patch(
            "src.nescordbot.bot.BatchProcessor"
        ), patch(
            "src.nescordbot.bot.ObsidianGitHubService"
        ) as mock_obsidian_service:
            bot = NescordBot()

            # Verify ObsidianGitHubService was initialized
            mock_obsidian_service.assert_called_once()
            assert hasattr(bot, "obsidian_service")
            assert bot.obsidian_service is not None

    @patch("src.nescordbot.bot.get_config_manager")
    @patch("src.nescordbot.bot.get_logger")
    def test_bot_initialization_with_obsidian_disabled(
        self, mock_logger, mock_get_config_manager, mock_config, mock_config_manager
    ):
        """Test that bot doesn't initialize ObsidianGitHub services when disabled."""
        mock_config.github_obsidian_enabled = False
        mock_get_config_manager.return_value = mock_config_manager
        mock_config_manager.config = mock_config
        mock_logger.return_value = MagicMock()

        with patch("src.nescordbot.bot.DatabaseService"):
            bot = NescordBot()

            # Verify ObsidianGitHubService was not initialized
            assert bot.obsidian_service is None

    @patch("src.nescordbot.bot.get_config_manager")
    @patch("src.nescordbot.bot.get_logger")
    def test_bot_initialization_with_missing_config(
        self, mock_logger, mock_get_config_manager, mock_config, mock_config_manager
    ):
        """Test that bot doesn't initialize ObsidianGitHub services with missing config."""
        mock_config.github_token = None  # Missing required config
        mock_get_config_manager.return_value = mock_config_manager
        mock_config_manager.config = mock_config
        mock_logger.return_value = MagicMock()

        with patch("src.nescordbot.bot.DatabaseService"):
            bot = NescordBot()

            # Verify ObsidianGitHubService was not initialized
            assert bot.obsidian_service is None

    @pytest.mark.asyncio
    async def test_voice_cog_receives_obsidian_service(self):
        """Test that Voice cog receives the ObsidianGitHub service."""
        # Mock bot with obsidian_service
        mock_bot = MagicMock()
        mock_obsidian_service = MagicMock(spec=ObsidianGitHubService)
        mock_bot.obsidian_service = mock_obsidian_service

        # Test voice cog setup
        from src.nescordbot.cogs.voice import setup

        with patch.object(mock_bot, "add_cog", new_callable=AsyncMock) as mock_add_cog:
            await setup(mock_bot)

            # Verify add_cog was called with Voice instance that has obsidian_service
            mock_add_cog.assert_called_once()
            voice_cog = mock_add_cog.call_args[0][0]
            assert isinstance(voice_cog, Voice)
            assert voice_cog.obsidian_service == mock_obsidian_service

    @pytest.mark.asyncio
    async def test_voice_cog_without_obsidian_service(self):
        """Test that Voice cog works without ObsidianGitHub service."""
        # Mock bot without obsidian_service
        mock_bot = MagicMock()
        # Remove obsidian_service attribute to simulate getattr returning None
        del mock_bot.obsidian_service

        from src.nescordbot.cogs.voice import setup

        with patch.object(mock_bot, "add_cog", new_callable=AsyncMock) as mock_add_cog:
            await setup(mock_bot)

            # Verify add_cog was called with Voice instance that has None obsidian_service
            mock_add_cog.assert_called_once()
            voice_cog = mock_add_cog.call_args[0][0]
            assert isinstance(voice_cog, Voice)
            assert voice_cog.obsidian_service is None
