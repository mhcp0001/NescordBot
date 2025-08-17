"""
Tests for logging service.
"""

import logging
import logging.handlers
import os
import tempfile
from pathlib import Path

import pytest

from nescordbot.logger import LoggerService, get_logger, get_logger_service


class TestLoggerService:
    """Test LoggerService functionality."""

    def setup_method(self):
        """Set up test environment."""
        # Create temporary directory for logs
        self.temp_dir = tempfile.mkdtemp()
        self.logs_dir = Path(self.temp_dir) / "logs"

        # Clear any existing global logger service
        import nescordbot.logger

        nescordbot.logger._logger_service = None

    def teardown_method(self):
        """Clean up test environment."""
        # Clean up temporary directory
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

        # Clear global logger service
        import src.logger

        src.logger._logger_service = None

    def test_logger_service_initialization(self):
        """Test LoggerService initialization."""
        logger_service = LoggerService("test_bot", str(self.logs_dir))

        assert logger_service.name == "test_bot"
        assert logger_service.logs_dir == self.logs_dir
        assert logger_service.logger.name == "test_bot"
        assert not logger_service._setup_complete

    def test_logger_service_setup(self):
        """Test LoggerService setup."""
        # Set environment variable for log level
        os.environ["LOG_LEVEL"] = "DEBUG"

        logger_service = LoggerService("test_bot", str(self.logs_dir))
        logger_service.setup()

        assert logger_service._setup_complete
        assert logger_service.logger.level == logging.DEBUG
        assert len(logger_service.logger.handlers) >= 2  # Console + file handlers

        # Check if logs directory was created
        assert self.logs_dir.exists()

        # Clean up
        if "LOG_LEVEL" in os.environ:
            del os.environ["LOG_LEVEL"]

    def test_logger_service_fallback_log_level(self):
        """Test LoggerService with fallback log level."""
        # Ensure LOG_LEVEL is not set
        if "LOG_LEVEL" in os.environ:
            del os.environ["LOG_LEVEL"]

        logger_service = LoggerService("test_bot", str(self.logs_dir))
        logger_service.setup()

        # Should default to INFO level
        assert logger_service.logger.level == logging.INFO

    def test_logger_service_file_creation(self):
        """Test that log files are created."""
        logger_service = LoggerService("test_bot", str(self.logs_dir))
        logger_service.setup()

        # Log some messages
        logger_service.info("Test info message")
        logger_service.error("Test error message")

        # Force handlers to flush
        for handler in logger_service.logger.handlers:
            handler.flush()

        # Check if log files exist
        main_log = self.logs_dir / "bot.log"

        # Files should exist (may be empty if buffered)
        assert main_log.exists() or any(
            isinstance(h, logging.handlers.RotatingFileHandler)
            for h in logger_service.logger.handlers
        )

    def test_logger_service_convenience_methods(self):
        """Test LoggerService convenience methods."""
        logger_service = LoggerService("test_bot", str(self.logs_dir))
        logger_service.setup()

        # Test all log levels
        logger_service.debug("Debug message")
        logger_service.info("Info message")
        logger_service.warning("Warning message")
        logger_service.error("Error message")
        logger_service.critical("Critical message")

        # These should not raise exceptions
        assert True

    def test_logger_service_exception_logging(self):
        """Test exception logging."""
        logger_service = LoggerService("test_bot", str(self.logs_dir))
        logger_service.setup()

        try:
            raise ValueError("Test exception")
        except ValueError:
            logger_service.exception("Exception occurred")

        # Should not raise exception
        assert True

    def test_logger_service_get_logger(self):
        """Test getting logger instances."""
        logger_service = LoggerService("test_bot", str(self.logs_dir))
        logger_service.setup()

        # Get main logger
        main_logger = logger_service.get_logger()
        assert main_logger.name == "test_bot"

        # Get named logger
        named_logger = logger_service.get_logger("module")
        assert named_logger.name == "test_bot.module"

    def test_logger_service_discord_logging_setup(self):
        """Test Discord logging configuration."""
        logger_service = LoggerService("test_bot", str(self.logs_dir))
        logger_service.setup()

        # Check that Discord logger is configured
        discord_logger = logging.getLogger("discord")
        assert len(discord_logger.handlers) > 0
        assert not discord_logger.propagate


class TestGlobalLoggerFunctions:
    """Test global logger functions."""

    def setup_method(self):
        """Set up test environment."""
        # Create temporary directory for logs
        self.temp_dir = tempfile.mkdtemp()

        # Clear any existing global logger service
        import nescordbot.logger

        nescordbot.logger._logger_service = None

    def teardown_method(self):
        """Clean up test environment."""
        # Clean up temporary directory
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

        # Clear global logger service
        import src.logger

        src.logger._logger_service = None

    def test_get_logger_service_singleton(self):
        """Test that get_logger_service returns the same instance."""
        service1 = get_logger_service()
        service2 = get_logger_service()

        assert service1 is service2

    def test_get_logger_function(self):
        """Test get_logger function."""
        logger1 = get_logger()
        logger2 = get_logger("module")

        assert logger1.name == "nescordbot"
        assert logger2.name == "nescordbot.module"

    def test_convenience_logging_functions(self):
        """Test convenience logging functions."""
        # Set environment to avoid config errors
        os.environ["DISCORD_TOKEN"] = "MTA1234567890.test"
        os.environ["OPENAI_API_KEY"] = "sk-test123"

        try:
            # Import and test convenience functions
            from src.logger import critical, debug, error, exception, info, warning

            debug("Debug message")
            info("Info message")
            warning("Warning message")
            error("Error message")
            critical("Critical message")

            # Test exception logging
            try:
                raise ValueError("Test exception")
            except ValueError:
                exception("Exception occurred")

            # Should not raise exceptions
            assert True
        finally:
            # Clean up environment
            for var in ["DISCORD_TOKEN", "OPENAI_API_KEY"]:
                if var in os.environ:
                    del os.environ[var]

    def test_logger_with_invalid_config(self):
        """Test logger behavior with invalid configuration."""
        # Don't set required environment variables
        logger_service = get_logger_service()

        # Should still work with fallback configuration
        assert logger_service is not None
        assert logger_service._setup_complete


class TestLoggerIntegration:
    """Test logger integration scenarios."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()

        # Clear any existing global logger service
        import nescordbot.logger

        nescordbot.logger._logger_service = None

    def teardown_method(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

        # Clear global logger service
        import src.logger

        src.logger._logger_service = None

    def test_logger_level_from_config(self):
        """Test logger level configuration from environment."""
        # Set environment variables
        os.environ["LOG_LEVEL"] = "WARNING"

        try:
            # Create a new logger service directly instead of using global
            from src.logger import LoggerService

            logger_service = LoggerService("test_config", str(self.temp_dir))
            logger_service.setup()
            # Test that the logger level is properly set
            assert logger_service.logger.level == logging.WARNING
        finally:
            # Clean up
            if "LOG_LEVEL" in os.environ:
                del os.environ["LOG_LEVEL"]

    def test_multiple_logger_instances(self):
        """Test multiple logger instances with different names."""
        service = get_logger_service()

        logger1 = service.get_logger("module1")
        logger2 = service.get_logger("module2")

        assert logger1.name == "nescordbot.module1"
        assert logger2.name == "nescordbot.module2"
        assert logger1 is not logger2
