"""
Tests for the General cog.
"""

import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from discord import app_commands
from discord.ext import commands

from nescordbot.cogs.general import General


class TestGeneralCog:
    """Test General cog functionality."""

    def setup_method(self):
        """Set up test environment."""
        # Set required environment variables
        os.environ[
            "DISCORD_TOKEN"
        ] = "MTA1234567890123456.GH7890.abcdefghijklmnop123456789012345678901234"
        os.environ["OPENAI_API_KEY"] = "sk-abcdef1234567890abcdef1234567890abcdef1234567890ab"

        # Clear any existing global services
        import nescordbot.config
        import nescordbot.logger

        nescordbot.config._config_manager = None
        nescordbot.logger._logger_service = None

    def teardown_method(self):
        """Clean up test environment."""
        # Clean up environment variables
        test_vars = [
            "DISCORD_TOKEN",
            "OPENAI_API_KEY",
            "LOG_LEVEL",
            "MAX_AUDIO_SIZE_MB",
            "SPEECH_LANGUAGE",
        ]
        for var in test_vars:
            if var in os.environ:
                del os.environ[var]

        # Clear global services
        import nescordbot.config
        import nescordbot.logger

        nescordbot.config._config_manager = None
        nescordbot.logger._logger_service = None

    def test_cog_initialization(self):
        """Test General cog initialization."""
        bot = MagicMock()
        cog = General(bot)

        assert cog.bot is bot
        assert cog.logger is not None
        assert hasattr(cog, "help_command")
        assert hasattr(cog, "status_command")
        assert hasattr(cog, "ping_command")

    @pytest.mark.asyncio
    async def test_help_command(self):
        """Test help command."""
        bot = MagicMock()
        cog = General(bot)

        # Mock bot user
        bot.user = MagicMock()
        bot.user.avatar = MagicMock()
        bot.user.avatar.url = "https://example.com/avatar.png"

        # Mock interaction
        interaction = MagicMock()
        interaction.response.send_message = AsyncMock()
        interaction.user = MagicMock()
        interaction.guild = MagicMock()

        await cog.help_command.callback(cog, interaction)

        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args

        # Check that embed was passed
        assert "embed" in call_args.kwargs
        embed = call_args.kwargs["embed"]
        assert isinstance(embed, discord.Embed)
        assert "NescordBot ヘルプ" in embed.title
        assert call_args.kwargs.get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_status_command(self):
        """Test status command."""
        bot = MagicMock()
        bot.latency = 0.05  # 50ms
        bot.guilds = [MagicMock(), MagicMock()]  # 2 guilds

        # Mock guild member counts
        for i, guild in enumerate(bot.guilds):
            guild.member_count = 100 * (i + 1)  # 100, 200 members

        cog = General(bot)

        # Mock interaction
        interaction = MagicMock()
        interaction.response.send_message = AsyncMock()
        interaction.user = MagicMock()
        interaction.guild = MagicMock()

        # Mock psutil
        with patch("psutil.cpu_percent", return_value=25.5), patch(
            "psutil.virtual_memory"
        ) as mock_memory, patch("psutil.disk_usage") as mock_disk, patch(
            "platform.system", return_value="Linux"
        ):
            mock_memory.return_value.percent = 60.0
            mock_disk.return_value.percent = 45.0

            await cog.status_command.callback(cog, interaction)

        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args

        # Check that embed was passed
        assert "embed" in call_args.kwargs
        embed = call_args.kwargs["embed"]
        assert isinstance(embed, discord.Embed)
        assert "Bot ステータス" in embed.title

    @pytest.mark.asyncio
    async def test_ping_command(self):
        """Test ping command."""
        bot = MagicMock()
        bot.latency = 0.075  # 75ms

        cog = General(bot)

        # Mock interaction
        interaction = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.user = MagicMock()
        interaction.guild = MagicMock()

        await cog.ping_command.callback(cog, interaction)

        interaction.response.defer.assert_called_once()
        interaction.followup.send.assert_called_once()

        call_args = interaction.followup.send.call_args
        assert "embed" in call_args.kwargs
        embed = call_args.kwargs["embed"]
        assert isinstance(embed, discord.Embed)
        assert "Pong!" in embed.title

    def test_get_status_color(self):
        """Test status color determination."""
        bot = MagicMock()
        cog = General(bot)

        # Test green (good performance)
        color = cog._get_status_color(50, 30, 40)
        assert color == discord.Color.green()

        # Test yellow (medium performance)
        color = cog._get_status_color(150, 70, 70)
        assert color == discord.Color.yellow()

        # Test red (poor performance)
        color = cog._get_status_color(250, 90, 90)
        assert color == discord.Color.red()

    def test_get_ping_color(self):
        """Test ping color determination."""
        bot = MagicMock()
        cog = General(bot)

        # Test different latency ranges
        assert cog._get_ping_color(30) == discord.Color.green()
        assert cog._get_ping_color(75) == discord.Color.yellow()
        assert cog._get_ping_color(150) == discord.Color.orange()
        assert cog._get_ping_color(250) == discord.Color.red()

    def test_get_status_text(self):
        """Test status text generation."""
        bot = MagicMock()
        cog = General(bot)

        # Test normal status
        text = cog._get_status_text(50, 30, 40)
        assert "正常" in text
        assert "🟢" in text

        # Test medium load
        text = cog._get_status_text(150, 70, 70)
        assert "中程度の負荷" in text
        assert "🟡" in text

        # Test heavy load
        text = cog._get_status_text(250, 90, 90)
        assert "重い負荷" in text
        assert "🔴" in text

    def test_get_performance_rating(self):
        """Test performance rating generation."""
        bot = MagicMock()
        cog = General(bot)

        # Test different performance levels
        rating = cog._get_performance_rating(30)
        assert "優秀" in rating
        assert "🟢" in rating

        rating = cog._get_performance_rating(75)
        assert "良好" in rating
        assert "🟡" in rating

        rating = cog._get_performance_rating(150)
        assert "普通" in rating
        assert "🟠" in rating

        rating = cog._get_performance_rating(250)
        assert "遅延" in rating
        assert "🔴" in rating

    @pytest.mark.asyncio
    async def test_send_error_response_not_responded(self):
        """Test error response when interaction not yet responded."""
        bot = MagicMock()
        cog = General(bot)

        interaction = MagicMock()
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()

        await cog._send_error_response(interaction, "Test error message")

        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args

        assert "embed" in call_args.kwargs
        embed = call_args.kwargs["embed"]
        assert isinstance(embed, discord.Embed)
        assert "エラー" in embed.title
        assert "Test error message" in embed.description
        assert call_args.kwargs.get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_send_error_response_already_responded(self):
        """Test error response when interaction already responded."""
        bot = MagicMock()
        cog = General(bot)

        interaction = MagicMock()
        interaction.response.is_done.return_value = True
        interaction.followup.send = AsyncMock()

        await cog._send_error_response(interaction, "Test error message")

        interaction.followup.send.assert_called_once()
        call_args = interaction.followup.send.call_args

        assert "embed" in call_args.kwargs
        embed = call_args.kwargs["embed"]
        assert isinstance(embed, discord.Embed)
        assert call_args.kwargs.get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_help_command_error_handling(self):
        """Test help command error handling."""
        bot = MagicMock()
        cog = General(bot)

        # Mock bot user to raise an exception
        bot.user = None

        interaction = MagicMock()
        interaction.response.send_message = AsyncMock(side_effect=Exception("Test error"))
        interaction.user = MagicMock()
        interaction.guild = MagicMock()

        # Mock _send_error_response
        cog._send_error_response = AsyncMock()

        await cog.help_command.callback(cog, interaction)

        # Should call error response
        cog._send_error_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_status_command_with_disk_error(self):
        """Test status command when disk usage fails."""
        bot = MagicMock()
        bot.latency = 0.05
        bot.guilds = [MagicMock()]
        bot.guilds[0].member_count = 100

        cog = General(bot)

        interaction = MagicMock()
        interaction.response.send_message = AsyncMock()
        interaction.user = MagicMock()
        interaction.guild = MagicMock()

        # Mock psutil with disk error
        with patch("psutil.cpu_percent", return_value=25.5), patch(
            "psutil.virtual_memory"
        ) as mock_memory, patch("psutil.disk_usage", side_effect=Exception("Disk error")), patch(
            "platform.system", return_value="Linux"
        ):
            mock_memory.return_value.percent = 60.0

            await cog.status_command.callback(cog, interaction)

        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args
        embed = call_args.kwargs["embed"]

        # Should contain "取得不可" for disk usage
        embed_dict = embed.to_dict()
        system_field = next(field for field in embed_dict["fields"] if "システム情報" in field["name"])
        assert "取得不可" in system_field["value"]

    @pytest.mark.asyncio
    async def test_on_app_command_error_cooldown(self):
        """Test app command error handling for cooldown."""
        bot = MagicMock()
        cog = General(bot)

        interaction = MagicMock()
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()
        interaction.command = MagicMock()
        interaction.user = MagicMock()
        interaction.guild = MagicMock()

        error = app_commands.CommandOnCooldown(None, 30.5)

        await cog.on_app_command_error(interaction, error)

        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args
        embed = call_args.kwargs["embed"]

        assert "クールダウン中" in embed.title
        assert "30.5" in embed.description

    @pytest.mark.asyncio
    async def test_on_app_command_error_missing_permissions(self):
        """Test app command error handling for missing permissions."""
        bot = MagicMock()
        cog = General(bot)

        interaction = MagicMock()
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()
        interaction.command = MagicMock()
        interaction.user = MagicMock()
        interaction.guild = MagicMock()

        error = app_commands.MissingPermissions(["manage_messages"])

        await cog.on_app_command_error(interaction, error)

        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args
        embed = call_args.kwargs["embed"]

        assert "権限不足" in embed.title

    @pytest.mark.asyncio
    async def test_setup_function(self):
        """Test the setup function."""
        bot = MagicMock()
        bot.add_cog = AsyncMock()

        from nescordbot.cogs.general import setup

        await setup(bot)

        bot.add_cog.assert_called_once()
        args = bot.add_cog.call_args[0]
        assert isinstance(args[0], General)


class TestGeneralCogIntegration:
    """Integration tests for General cog."""

    def setup_method(self):
        """Set up test environment."""
        # Set required environment variables
        os.environ[
            "DISCORD_TOKEN"
        ] = "MTA1234567890123456.GH7890.abcdefghijklmnop123456789012345678901234"
        os.environ["OPENAI_API_KEY"] = "sk-abcdef1234567890abcdef1234567890abcdef1234567890ab"
        os.environ["LOG_LEVEL"] = "DEBUG"

        # Clear any existing global services
        import nescordbot.config
        import nescordbot.logger

        nescordbot.config._config_manager = None
        nescordbot.logger._logger_service = None

    def teardown_method(self):
        """Clean up test environment."""
        # Clean up environment variables
        test_vars = [
            "DISCORD_TOKEN",
            "OPENAI_API_KEY",
            "LOG_LEVEL",
            "MAX_AUDIO_SIZE_MB",
            "SPEECH_LANGUAGE",
        ]
        for var in test_vars:
            if var in os.environ:
                del os.environ[var]

        # Clear global services
        import nescordbot.config
        import nescordbot.logger

        nescordbot.config._config_manager = None
        nescordbot.logger._logger_service = None

    def test_cog_with_logger_integration(self):
        """Test General cog integration with logger service."""
        bot = MagicMock()
        cog = General(bot)

        # Check that logger is properly integrated
        assert cog.logger is not None
        assert hasattr(cog.logger, "info")
        assert hasattr(cog.logger, "error")

    @pytest.mark.asyncio
    async def test_command_registration(self):
        """Test that commands are properly registered."""
        bot = MagicMock()
        cog = General(bot)

        # Check that commands exist and are app_commands
        assert hasattr(cog, "help_command")
        assert hasattr(cog, "status_command")
        assert hasattr(cog, "ping_command")

        # Check that they are app_commands.Command instances
        assert isinstance(cog.help_command, app_commands.Command)
        assert isinstance(cog.status_command, app_commands.Command)
        assert isinstance(cog.ping_command, app_commands.Command)
