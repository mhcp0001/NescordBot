"""
Logging service for NescordBot.

This module provides centralized logging functionality with structured output,
file rotation, and level control through configuration.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional

import colorlog

from src.config import get_config_manager


class LoggerService:
    """
    Centralized logging service for the NescordBot application.

    Provides structured logging with console and file output, log rotation,
    and level control through configuration.
    """

    def __init__(self, name: str = "nescordbot", logs_dir: str = "logs"):
        """
        Initialize the logger service.

        Args:
            name: Logger name (default: "nescordbot")
            logs_dir: Directory for log files (default: "logs")
        """
        self.name = name
        self.logs_dir = Path(logs_dir)
        self.logger = logging.getLogger(name)
        self._setup_complete = False

        # Ensure logs directory exists
        self.logs_dir.mkdir(exist_ok=True)

    def setup(self) -> None:
        """Setup logging configuration."""
        if self._setup_complete:
            return

        # Get log level from environment variable first, then config
        import os

        log_level = os.getenv("LOG_LEVEL")

        if not log_level:
            try:
                config_manager = get_config_manager()
                log_level = config_manager.get_log_level()
            except Exception:
                # Fallback to default
                log_level = "INFO"

        # Clear existing handlers
        self.logger.handlers.clear()

        # Set logger level
        level_str = log_level.upper() if log_level else "INFO"
        numeric_level = getattr(logging, level_str, logging.INFO)
        self.logger.setLevel(numeric_level)

        # Setup console handler with colors
        self._setup_console_handler(numeric_level)

        # Setup file handlers
        self._setup_file_handlers(numeric_level)

        # Configure Discord.py logging
        self._setup_discord_logging(numeric_level)

        # Prevent propagation to root logger
        self.logger.propagate = False

        self._setup_complete = True

    def _setup_console_handler(self, level: int) -> None:
        """Setup colored console logging handler."""
        console_handler = colorlog.StreamHandler(sys.stdout)
        console_handler.setLevel(level)

        # Colored formatter for console
        console_formatter = colorlog.ColoredFormatter(
            "%(log_color)s%(asctime)s | %(levelname)-8s | %(name)s | " "%(message)s%(reset)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "red,bg_white",
            },
            style="%",
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

    def _setup_file_handlers(self, level: int) -> None:
        """Setup file logging handlers with rotation."""
        # Main log file with rotation
        main_log_file = self.logs_dir / "bot.log"
        file_handler = logging.handlers.RotatingFileHandler(
            main_log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"  # 10MB
        )
        file_handler.setLevel(level)

        # File formatter (more detailed)
        file_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | " "%(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)

        # Error-only log file
        error_log_file = self.logs_dir / "error.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"  # 5MB
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        self.logger.addHandler(error_handler)

    def _setup_discord_logging(self, level: int) -> None:
        """Configure Discord.py logging to use our logger."""
        # Discord.py logger
        discord_logger = logging.getLogger("discord")
        discord_logger.setLevel(level)
        discord_logger.handlers.clear()

        # Create a handler that forwards to our main logger
        class DiscordLogHandler(logging.Handler):
            def __init__(self, main_logger):
                super().__init__()
                self.main_logger = main_logger

            def emit(self, record):
                # Prefix Discord logs
                record.name = f"discord.{record.name.split('.')[-1]}"
                self.main_logger.handle(record)

        discord_handler = DiscordLogHandler(self.logger)
        discord_handler.setLevel(level)
        discord_logger.addHandler(discord_handler)
        discord_logger.propagate = False

        # Also handle HTTP and gateway logs separately if needed
        for logger_name in ["discord.http", "discord.gateway", "discord.client"]:
            logger = logging.getLogger(logger_name)
            logger.setLevel(max(level, logging.WARNING))  # Reduce noise

    def get_logger(self, name: Optional[str] = None) -> logging.Logger:
        """
        Get a logger instance.

        Args:
            name: Optional logger name suffix

        Returns:
            logging.Logger: Configured logger instance
        """
        if not self._setup_complete:
            self.setup()

        if name:
            return logging.getLogger(f"{self.name}.{name}")
        return self.logger

    def debug(self, message: str, *args, **kwargs) -> None:
        """Log debug message."""
        self.logger.debug(message, *args, **kwargs)

    def info(self, message: str, *args, **kwargs) -> None:
        """Log info message."""
        self.logger.info(message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs) -> None:
        """Log warning message."""
        self.logger.warning(message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs) -> None:
        """Log error message."""
        self.logger.error(message, *args, **kwargs)

    def critical(self, message: str, *args, **kwargs) -> None:
        """Log critical message."""
        self.logger.critical(message, *args, **kwargs)

    def exception(self, message: str, *args, **kwargs) -> None:
        """Log exception with traceback."""
        self.logger.exception(message, *args, **kwargs)


# Global logger service instance
_logger_service: Optional[LoggerService] = None


def get_logger_service() -> LoggerService:
    """
    Get global logger service instance.

    Returns:
        LoggerService: Global logger service instance
    """
    global _logger_service
    if _logger_service is None:
        _logger_service = LoggerService()
        _logger_service.setup()
    return _logger_service


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a configured logger instance.

    Args:
        name: Optional logger name suffix

    Returns:
        logging.Logger: Configured logger instance
    """
    return get_logger_service().get_logger(name)


# Convenience functions for direct logging
def debug(message: str, *args, **kwargs) -> None:
    """Log debug message."""
    get_logger_service().debug(message, *args, **kwargs)


def info(message: str, *args, **kwargs) -> None:
    """Log info message."""
    get_logger_service().info(message, *args, **kwargs)


def warning(message: str, *args, **kwargs) -> None:
    """Log warning message."""
    get_logger_service().warning(message, *args, **kwargs)


def error(message: str, *args, **kwargs) -> None:
    """Log error message."""
    get_logger_service().error(message, *args, **kwargs)


def critical(message: str, *args, **kwargs) -> None:
    """Log critical message."""
    get_logger_service().critical(message, *args, **kwargs)


def exception(message: str, *args, **kwargs) -> None:
    """Log exception with traceback."""
    get_logger_service().exception(message, *args, **kwargs)
