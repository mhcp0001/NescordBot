"""
Tests for the bot runner startup script.
"""

import asyncio
import os
import signal
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nescordbot.main import BotRunner, main


class TestBotRunner:
    """Test BotRunner functionality."""

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

    def test_bot_runner_initialization(self):
        """Test BotRunner initialization."""
        runner = BotRunner()

        assert runner.bot is None
        assert runner.logger is None
        assert runner.shutdown_event is not None
        assert isinstance(runner.shutdown_event, asyncio.Event)

    def test_setup_logging_success(self):
        """Test successful logging setup."""
        runner = BotRunner()
        runner.setup_logging()

        assert runner.logger is not None
        assert hasattr(runner.logger, "info")
        assert hasattr(runner.logger, "error")

    def test_setup_logging_failure(self):
        """Test logging setup failure."""
        runner = BotRunner()

        with patch("run.get_logger", side_effect=Exception("Logging error")), pytest.raises(
            SystemExit
        ) as exc_info:
            runner.setup_logging()

        assert exc_info.value.code == 1

    def test_validate_environment_success(self):
        """Test successful environment validation."""
        runner = BotRunner()
        runner.setup_logging()

        # Mock .env file exists
        with patch("pathlib.Path.exists", return_value=True):
            result = runner.validate_environment()

        assert result is True

    def test_validate_environment_no_env_file(self):
        """Test environment validation without .env file."""
        runner = BotRunner()
        runner.setup_logging()

        # Mock .env file doesn't exist
        with patch("pathlib.Path.exists", return_value=False):
            result = runner.validate_environment()

        assert result is True

    def test_validate_environment_failure(self):
        """Test environment validation failure."""
        runner = BotRunner()
        runner.setup_logging()

        # Clear any existing global services first
        import nescordbot.config

        nescordbot.config._config_manager = None

        # Temporarily remove required environment variable
        original_token = os.environ.get("DISCORD_TOKEN")
        if "DISCORD_TOKEN" in os.environ:
            del os.environ["DISCORD_TOKEN"]

        try:
            with patch("builtins.print"):  # Suppress help output
                result = runner.validate_environment()

            assert result is False
        finally:
            # Restore the environment variable
            if original_token:
                os.environ["DISCORD_TOKEN"] = original_token

    def test_print_setup_help(self):
        """Test setup help printing."""
        runner = BotRunner()

        with patch("builtins.print") as mock_print:
            runner._print_setup_help()

        # Should print multiple lines of help
        assert mock_print.call_count > 10

        # Check for key help content
        help_text = " ".join(str(call) for call in mock_print.call_args_list)
        assert "DISCORD_TOKEN" in help_text
        assert "OPENAI_API_KEY" in help_text
        assert "discord.com/developers" in help_text
        assert "platform.openai.com" in help_text

    def test_setup_signal_handlers_unix(self):
        """Test signal handler setup on Unix systems."""
        runner = BotRunner()
        runner.setup_logging()

        with patch("sys.platform", "linux"), patch("signal.signal") as mock_signal:
            runner.setup_signal_handlers()

        # Should set up SIGINT and SIGTERM handlers
        assert mock_signal.call_count == 2
        # Check that the correct signals were registered
        call_args = [call[0][0] for call in mock_signal.call_args_list]
        assert signal.SIGINT in call_args
        assert signal.SIGTERM in call_args

    def test_setup_signal_handlers_windows(self):
        """Test signal handler setup on Windows."""
        runner = BotRunner()
        runner.setup_logging()

        with patch("sys.platform", "win32"), patch("signal.signal") as mock_signal:
            runner.setup_signal_handlers()

        # Should set up at least SIGINT handler on Windows
        # SIGBREAK may also be set if available (platform-dependent)
        assert mock_signal.call_count >= 1
        # Verify SIGINT is always set
        call_args = [call[0][0] for call in mock_signal.call_args_list]
        assert signal.SIGINT in call_args

    @pytest.mark.asyncio
    async def test_shutdown(self):
        """Test shutdown method."""
        runner = BotRunner()

        assert not runner.shutdown_event.is_set()

        await runner._shutdown()

        assert runner.shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_run_bot_shutdown_signal(self):
        """Test bot running with shutdown signal."""
        runner = BotRunner()
        runner.setup_logging()

        with patch("src.bot.main", new_callable=AsyncMock) as mock_bot_main:
            # Make bot_main run indefinitely
            mock_bot_main.return_value = None

            # Create a task to simulate the bot run
            async def simulate_run():
                # Trigger shutdown after a short delay
                await asyncio.sleep(0.1)
                await runner._shutdown()
                return await runner.run_bot()

            result = await simulate_run()

            assert result == 0

    @pytest.mark.asyncio
    async def test_run_bot_exception(self):
        """Test bot running with exception."""
        runner = BotRunner()
        runner.setup_logging()

        with patch("src.bot.main", new_callable=AsyncMock) as mock_bot_main:
            mock_bot_main.side_effect = Exception("Bot error")

            result = await runner.run_bot()

            assert result == 1

    @pytest.mark.asyncio
    async def test_start_success(self):
        """Test successful bot start."""
        runner = BotRunner()

        with patch.object(runner, "validate_environment", return_value=True), patch.object(
            runner, "setup_signal_handlers"
        ), patch.object(runner, "run_bot", new_callable=AsyncMock, return_value=0):
            result = await runner.start()

            assert result == 0

    @pytest.mark.asyncio
    async def test_start_validation_failure(self):
        """Test bot start with validation failure."""
        runner = BotRunner()

        with patch.object(runner, "validate_environment", return_value=False):
            result = await runner.start()

            assert result == 1

    @pytest.mark.asyncio
    async def test_start_exception(self):
        """Test bot start with exception."""
        runner = BotRunner()

        with patch.object(runner, "setup_logging", side_effect=Exception("Setup error")):
            result = await runner.start()

            assert result == 1


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

    def test_main_success(self):
        """Test successful main function execution."""
        with patch("asyncio.run", return_value=0), patch("builtins.print"):
            result = main()

            assert result == 0

    def test_main_exception(self):
        """Test main function with exception."""
        with patch("asyncio.run", side_effect=Exception("Fatal error")), patch("builtins.print"):
            result = main()

            assert result == 1


class TestRunnerIntegration:
    """Integration tests for the bot runner."""

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

    def test_runner_with_services_integration(self):
        """Test runner integration with config and logger services."""
        runner = BotRunner()
        runner.setup_logging()

        # Check that services are properly integrated
        assert runner.logger is not None

        # Test environment validation
        result = runner.validate_environment()
        assert result is True

    @pytest.mark.asyncio
    async def test_full_startup_sequence(self):
        """Test the complete startup sequence without actually running the bot."""
        runner = BotRunner()

        # Mock the bot main function to avoid actually starting Discord connection
        with patch("src.bot.main", new_callable=AsyncMock) as mock_bot_main:
            # Make the bot main return quickly
            mock_bot_main.return_value = None

            # Start the runner but trigger shutdown immediately
            start_task = asyncio.create_task(runner.start())

            # Give it a moment to initialize
            await asyncio.sleep(0.1)

            # Trigger shutdown
            await runner._shutdown()

            # Wait for completion
            result = await start_task

            assert result == 0

    def test_environment_masking(self):
        """Test that sensitive information is properly masked in logs."""
        runner = BotRunner()
        runner.setup_logging()

        # Capture log output
        import io
        import logging

        log_capture = io.StringIO()
        handler = logging.StreamHandler(log_capture)
        runner.logger.addHandler(handler)

        # Validate environment (this logs the masked tokens)
        runner.validate_environment()

        log_output = log_capture.getvalue()

        # Check that full tokens are not in the log
        assert (
            "MTA1234567890123456.GH7890.abcdefghijklmnop123456789012345678901234" not in log_output
        )
        assert "sk-abcdef1234567890abcdef1234567890abcdef1234567890ab" not in log_output

        # Check that masked versions are present
        assert "**********" in log_output
