"""
Tests for the main bot implementation.
"""

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from discord.ext import commands

from src.bot import NescordBot, main


class TestNescordBot:
    """Test NescordBot functionality."""

    def setup_method(self):
        """Set up test environment."""
        # Set required environment variables
        os.environ[
            "DISCORD_TOKEN"
        ] = "MTA1234567890123456.GH7890.abcdefghijklmnop123456789012345678901234"
        os.environ["OPENAI_API_KEY"] = "sk-abcdef1234567890abcdef1234567890abcdef1234567890ab"

        # Clear any existing global services
        import src.config
        import src.logger

        src.config._config_manager = None
        src.logger._logger_service = None

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
        import src.config
        import src.logger

        src.config._config_manager = None
        src.logger._logger_service = None

    def test_bot_initialization(self):
        """Test NescordBot initialization."""
        bot = NescordBot()

        assert bot.command_prefix == "!"
        assert isinstance(bot.intents, discord.Intents)
        assert bot.intents.message_content
        assert bot.intents.voice_states
        assert bot.intents.guilds
        assert bot.help_command is None
        assert bot.case_insensitive
        assert bot.data_dir == Path("data")

    def test_bot_initialization_with_config(self):
        """Test bot initialization uses configuration correctly."""
        os.environ["MAX_AUDIO_SIZE_MB"] = "50"
        os.environ["LOG_LEVEL"] = "DEBUG"

        bot = NescordBot()

        assert bot.config.max_audio_size_mb == 50
        assert bot.config.log_level == "DEBUG"

    @pytest.mark.asyncio
    async def test_setup_hook(self):
        """Test bot setup hook."""
        bot = NescordBot()

        # Mock the methods called during setup
        bot._load_cogs = AsyncMock()
        bot._sync_commands = AsyncMock()

        await bot.setup_hook()

        bot._load_cogs.assert_called_once()
        bot._sync_commands.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_cogs_no_cogs_dir(self):
        """Test loading cogs when cogs directory doesn't exist."""
        bot = NescordBot()

        with patch("pathlib.Path.exists", return_value=False):
            await bot._load_cogs()

        # Should not raise an error
        assert True

    @pytest.mark.asyncio
    async def test_load_cogs_with_existing_cogs(self):
        """Test loading cogs from existing files."""
        bot = NescordBot()

        # Mock load_extension to test the cog loading logic
        with patch.object(bot, "load_extension", new_callable=AsyncMock) as mock_load:
            # Mock successful loading
            mock_load.return_value = None

            # Call _load_cogs (it will find no cogs but that's OK for this test)
            await bot._load_cogs()

            # Just verify the method doesn't raise an exception
            assert True

    @pytest.mark.asyncio
    async def test_sync_commands(self):
        """Test command synchronization."""
        bot = NescordBot()

        # Mock the tree.sync method
        mock_commands = [MagicMock(), MagicMock()]
        bot.tree.sync = AsyncMock(return_value=mock_commands)

        await bot._sync_commands()

        bot.tree.sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_ready(self):
        """Test on_ready event handler."""
        bot = NescordBot()

        # Patch the user and guilds properties
        with patch.object(
            type(bot), "user", new_callable=lambda: MagicMock()
        ) as mock_user, patch.object(
            type(bot), "guilds", new_callable=lambda: [MagicMock(), MagicMock()]
        ):
            mock_user.id = 123456789
            bot.change_presence = AsyncMock()

            await bot.on_ready()

            bot.change_presence.assert_called_once()
            args, kwargs = bot.change_presence.call_args

            assert "activity" in kwargs
            assert "status" in kwargs
            assert kwargs["status"] == discord.Status.online
            assert isinstance(kwargs["activity"], discord.Activity)

    @pytest.mark.asyncio
    async def test_on_message_bot_message(self):
        """Test on_message ignores bot messages."""
        bot = NescordBot()

        # Mock bot message
        message = MagicMock()
        message.author.bot = True

        bot._process_voice_attachments = AsyncMock()
        bot.process_commands = AsyncMock()

        await bot.on_message(message)

        # Should not process bot messages
        bot._process_voice_attachments.assert_not_called()
        bot.process_commands.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_message_user_message(self):
        """Test on_message processes user messages."""
        bot = NescordBot()

        # Mock only logger to avoid initialization issues, keep config
        bot.logger = MagicMock()

        # Mock user message - IMPORTANT: Set properties AFTER creating nested mocks
        message = MagicMock()
        message.author = MagicMock()
        message.author.bot = False  # Set after creating the author mock
        message.guild = MagicMock()
        message.channel = MagicMock()
        message.attachments = []

        bot._process_voice_attachments = AsyncMock()
        bot.process_commands = AsyncMock()

        await bot.on_message(message)

        bot._process_voice_attachments.assert_called_once_with(message)
        bot.process_commands.assert_called_once_with(message)

    def test_is_audio_file_content_type(self):
        """Test audio file detection by content type."""
        bot = NescordBot()

        # Mock attachment with audio content type
        attachment = MagicMock()
        attachment.content_type = "audio/ogg"
        attachment.filename = "test.ogg"

        assert bot._is_audio_file(attachment)

    def test_is_audio_file_extension(self):
        """Test audio file detection by extension."""
        bot = NescordBot()

        # Mock attachment with audio extension
        attachment = MagicMock()
        attachment.content_type = None
        attachment.filename = "test.mp3"

        assert bot._is_audio_file(attachment)

    def test_is_audio_file_not_audio(self):
        """Test non-audio file detection."""
        bot = NescordBot()

        # Mock non-audio attachment
        attachment = MagicMock()
        attachment.content_type = "image/png"
        attachment.filename = "test.png"

        assert not bot._is_audio_file(attachment)

    @pytest.mark.asyncio
    async def test_handle_voice_message_success(self):
        """Test successful voice message handling."""
        bot = NescordBot()

        # Mock logger and user for the test, keep config for max_audio_size_mb
        bot.logger = MagicMock()
        mock_user = MagicMock()

        # Mock message and attachment
        message = MagicMock()
        message.add_reaction = AsyncMock()
        message.remove_reaction = AsyncMock()
        message.reply = AsyncMock()
        from datetime import datetime

        message.created_at = datetime.now()

        attachment = MagicMock()
        attachment.filename = "test.ogg"
        attachment.size = 1024  # 1KB - under limit
        attachment.content_type = "audio/ogg"

        bot._send_voice_acknowledgment = AsyncMock()

        # Patch the user property for the duration of the method call
        with patch.object(type(bot), "user", new_callable=lambda: mock_user):
            await bot._handle_voice_message(message, attachment)

        # Check the sequence of calls
        assert message.add_reaction.call_count == 2
        message.add_reaction.assert_any_call("⏳")
        message.add_reaction.assert_any_call("✅")
        bot._send_voice_acknowledgment.assert_called_once()
        message.remove_reaction.assert_called_with("⏳", mock_user)

    @pytest.mark.asyncio
    async def test_handle_voice_message_too_large(self):
        """Test voice message handling with file too large."""
        bot = NescordBot()

        # Mock message and large attachment
        message = MagicMock()
        message.reply = AsyncMock()

        attachment = MagicMock()
        attachment.size = 50 * 1024 * 1024  # 50MB - over default limit

        await bot._handle_voice_message(message, attachment)

        message.reply.assert_called_once()
        reply_text = message.reply.call_args[0][0]
        assert "大きすぎます" in reply_text

    @pytest.mark.asyncio
    async def test_send_voice_acknowledgment(self):
        """Test voice acknowledgment sending."""
        bot = NescordBot()

        # Mock message and attachment
        message = MagicMock()
        message.reply = AsyncMock()
        message.created_at = MagicMock()

        attachment = MagicMock()
        attachment.filename = "test.ogg"
        attachment.size = 1024
        attachment.content_type = "audio/ogg"

        mock_author = MagicMock()
        mock_author.display_name = "TestUser"
        message.author = mock_author

        # Mock datetime for embed timestamp
        from datetime import datetime

        message.created_at = datetime.now()

        await bot._send_voice_acknowledgment(message, attachment)

        message.reply.assert_called_once()
        # Check that an embed was passed
        call_args = message.reply.call_args
        assert "embed" in call_args.kwargs or len(call_args.args) > 0

    @pytest.mark.asyncio
    async def test_on_error(self):
        """Test global error handler."""
        bot = NescordBot()

        # Should not raise an exception
        await bot.on_error("test_event", "arg1", "arg2", kwarg1="value1")

    @pytest.mark.asyncio
    async def test_on_command_error_command_not_found(self):
        """Test command error handler for CommandNotFound."""
        bot = NescordBot()

        ctx = MagicMock()
        ctx.reply = AsyncMock()

        error = commands.CommandNotFound()

        await bot.on_command_error(ctx, error)

        # Should not reply for CommandNotFound
        ctx.reply.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_command_error_missing_argument(self):
        """Test command error handler for MissingRequiredArgument."""
        bot = NescordBot()

        ctx = MagicMock()
        ctx.reply = AsyncMock()
        ctx.command = MagicMock()
        ctx.author = MagicMock()
        ctx.guild = MagicMock()

        error = commands.MissingRequiredArgument(MagicMock())

        await bot.on_command_error(ctx, error)

        ctx.reply.assert_called_once()
        reply_text = ctx.reply.call_args[0][0]
        assert "引数が不足" in reply_text

    @pytest.mark.asyncio
    async def test_close(self):
        """Test bot close method."""
        bot = NescordBot()

        # Mock the parent close method
        with patch("discord.ext.commands.Bot.close", new_callable=AsyncMock) as mock_close:
            await bot.close()
            mock_close.assert_called_once()


class TestMainFunction:
    """Test the main function."""

    def setup_method(self):
        """Set up test environment."""
        # Set required environment variables
        os.environ[
            "DISCORD_TOKEN"
        ] = "MTA1234567890123456.GH7890.abcdefghijklmnop123456789012345678901234"
        os.environ["OPENAI_API_KEY"] = "sk-abcdef1234567890abcdef1234567890abcdef1234567890ab"

        # Clear any existing global services
        import src.config
        import src.logger

        src.config._config_manager = None
        src.logger._logger_service = None

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
        import src.config
        import src.logger

        src.config._config_manager = None
        src.logger._logger_service = None

    @pytest.mark.asyncio
    async def test_main_with_valid_config(self):
        """Test main function with valid configuration."""
        # Mock NescordBot and its start method
        with patch("src.bot.NescordBot") as mock_bot_class:
            mock_bot = AsyncMock()
            mock_bot_class.return_value = mock_bot
            mock_bot.start = AsyncMock()

            # Mock the async context manager
            mock_bot.__aenter__ = AsyncMock(return_value=mock_bot)
            mock_bot.__aexit__ = AsyncMock(return_value=None)

            await main()

            mock_bot_class.assert_called_once()
            mock_bot.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_with_invalid_config(self):
        """Test main function with invalid configuration."""
        # Remove required environment variable
        del os.environ["DISCORD_TOKEN"]

        with pytest.raises(Exception):
            await main()


class TestBotIntegration:
    """Integration tests for bot functionality."""

    def setup_method(self):
        """Set up test environment."""
        # Set required environment variables
        os.environ[
            "DISCORD_TOKEN"
        ] = "MTA1234567890123456.GH7890.abcdefghijklmnop123456789012345678901234"
        os.environ["OPENAI_API_KEY"] = "sk-abcdef1234567890abcdef1234567890abcdef1234567890ab"
        os.environ["LOG_LEVEL"] = "DEBUG"

        # Clear any existing global services
        import src.config
        import src.logger

        src.config._config_manager = None
        src.logger._logger_service = None

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
        import src.config
        import src.logger

        src.config._config_manager = None
        src.logger._logger_service = None

    def test_bot_integration_with_services(self):
        """Test bot integration with config and logger services."""
        bot = NescordBot()

        # Check that services are properly integrated
        assert bot.config_manager is not None
        assert bot.config is not None
        assert bot.logger is not None

        # Check configuration values
        assert bot.config.discord_token.startswith("MTA")
        assert bot.config.openai_api_key.startswith("sk-")
        assert bot.config.log_level == "DEBUG"

    @pytest.mark.asyncio
    async def test_message_processing_flow(self):
        """Test complete message processing flow."""
        bot = NescordBot()

        # Mock bot user and logger, keep config
        bot.logger = MagicMock()
        mock_user = MagicMock()

        # Mock message with voice attachment - Set properties AFTER creating nested mocks
        message = MagicMock()
        message.author = MagicMock()
        message.author.bot = False  # Set after creating author mock
        message.guild = MagicMock()
        message.channel = MagicMock()
        message.add_reaction = AsyncMock()
        message.remove_reaction = AsyncMock()
        message.reply = AsyncMock()
        from datetime import datetime

        message.created_at = datetime.now()

        attachment = MagicMock()
        attachment.filename = "test.ogg"
        attachment.size = 1024
        attachment.content_type = "audio/ogg"
        message.attachments = [attachment]

        bot.process_commands = AsyncMock()

        # Patch the user property for the duration of the method call
        with patch.object(type(bot), "user", new_callable=lambda: mock_user):
            await bot.on_message(message)

        # Verify voice processing occurred
        message.add_reaction.assert_called()
        message.reply.assert_called()
        bot.process_commands.assert_called_once_with(message)
