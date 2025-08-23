"""
Test debug command functionality.
Tests for Issue #89 debug command implementation.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from nescordbot.cogs.admin import AdminCog


class TestDebugCommand:
    """Test debug command functionality."""

    @pytest.fixture
    def mock_bot(self):
        """Create a mock bot with required services."""
        bot = MagicMock()
        bot.user = MagicMock()
        bot.user.id = 123456789
        bot.guilds = []
        bot.data_dir = Path("data")
        bot.database_service = AsyncMock()
        bot.config = MagicMock()
        return bot

    @pytest.fixture
    def admin_cog(self, mock_bot):
        """Create AdminCog instance for testing."""
        return AdminCog(mock_bot)

    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = MagicMock()
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()
        interaction.user = MagicMock()
        interaction.user.id = 987654321
        interaction.guild = MagicMock()
        return interaction

    @pytest.mark.asyncio
    async def test_debug_config_command_enabled_complete(self, admin_cog, mock_interaction):
        """Test debug config command with complete Obsidian configuration."""
        # Mock bot configuration - enabled and complete
        admin_cog.bot.config.github_obsidian_enabled = True
        admin_cog.bot.config.github_token = "test_token"
        admin_cog.bot.config.github_repo_owner = "test_owner"
        admin_cog.bot.config.github_repo_name = "test_repo"
        admin_cog.bot.obsidian_service = MagicMock()

        # Execute command
        await admin_cog._debug_config(mock_interaction)

        # Verify interaction response
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args
        embed = call_args[1]["embed"]

        # Verify embed content
        assert "🔧 設定診断レポート" in embed.title
        assert any("✅ 有効" in field.value for field in embed.fields)
        assert any("✅ GITHUB_TOKEN" in field.value for field in embed.fields)

    @pytest.mark.asyncio
    async def test_debug_config_command_disabled(self, admin_cog, mock_interaction):
        """Test debug config command with disabled configuration."""
        # Mock bot configuration - disabled
        admin_cog.bot.config.github_obsidian_enabled = False
        admin_cog.bot.config.github_token = None
        admin_cog.bot.config.github_repo_owner = None
        admin_cog.bot.config.github_repo_name = None
        admin_cog.bot.obsidian_service = None

        # Execute command
        await admin_cog._debug_config(mock_interaction)

        # Verify interaction response
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args
        embed = call_args[1]["embed"]

        # Verify embed shows disabled status
        assert any("❌ 無効" in field.value for field in embed.fields)
        assert any("❌ GITHUB_TOKEN" in field.value for field in embed.fields)
        assert any("💡 推奨アクション" in field.name for field in embed.fields)

    def test_debug_command_exists(self, admin_cog):
        """Test debug command is properly registered."""
        # Check that debug command exists in the cog
        assert hasattr(admin_cog, "debug")
        assert hasattr(admin_cog, "_debug_config")
        assert hasattr(admin_cog, "_debug_services")

    def test_config_attribute_check(self, admin_cog, mock_interaction):
        """Test config attribute checking logic."""
        # Mock getattr behavior
        admin_cog.bot.config.test_attr = "value"
        admin_cog.bot.config.missing_attr = None

        # Test existing attribute
        value = getattr(admin_cog.bot.config, "test_attr", None)
        assert value == "value"

        # Test missing attribute
        value = getattr(admin_cog.bot.config, "missing_attr", None)
        assert value is None
