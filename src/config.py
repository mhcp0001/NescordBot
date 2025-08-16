"""
Configuration management for NescordBot.

This module provides centralized configuration management using Pydantic
for type validation and python-dotenv for environment variable loading.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator, ConfigDict


class BotConfig(BaseModel):
    """
    Bot configuration model with validation.

    All configuration values are loaded from environment variables.
    Required values will raise ValidationError if not provided.
    """

    # Required settings
    discord_token: str = Field(..., description="Discord bot token")
    openai_api_key: str = Field(
        ..., description="OpenAI API key for Whisper and GPT"
    )

    # Optional settings with defaults
    log_level: str = Field(default="INFO", description="Logging level")
    max_audio_size_mb: int = Field(
        default=25, description="Maximum audio file size in MB"
    )
    speech_language: str = Field(
        default="ja", description="Speech recognition language"
    )

    # Database settings (for future use)
    database_url: str = Field(
        default="sqlite:///data/nescordbot.db", description="Database URL"
    )

    # GitHub integration settings (for future use)
    github_token: Optional[str] = Field(
        default=None, description="GitHub API token"
    )
    github_repo: Optional[str] = Field(
        default=None, description="GitHub repository"
    )

    # Obsidian integration settings (for future use)
    obsidian_vault_path: Optional[str] = Field(
        default=None, description="Obsidian vault path"
    )

    @field_validator("discord_token")
    @classmethod
    def validate_discord_token(cls, v):
        """Validate Discord token format."""
        if not v:
            raise ValueError("Discord token is required")
        if not v.startswith(("Bot ", "MTA", "ODQ", "OTQ", "MT")):
            raise ValueError("Invalid Discord token format")
        return v

    @field_validator("openai_api_key")
    @classmethod
    def validate_openai_api_key(cls, v):
        """Validate OpenAI API key format."""
        if not v:
            raise ValueError("OpenAI API key is required")
        if not v.startswith("sk-"):
            raise ValueError("Invalid OpenAI API key format")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            levels_str = ", ".join(valid_levels)
            raise ValueError(f"Log level must be one of: {levels_str}")
        return v.upper()

    @field_validator("max_audio_size_mb")
    @classmethod
    def validate_max_audio_size(cls, v):
        """Validate maximum audio file size."""
        if v <= 0:
            raise ValueError("Maximum audio size must be positive")
        if v > 100:
            raise ValueError("Maximum audio size should not exceed 100MB")
        return v

    @field_validator("speech_language")
    @classmethod
    def validate_speech_language(cls, v):
        """Validate speech language code."""
        # Common language codes
        valid_languages = [
            "ja", "en", "es", "fr", "de", "it", "pt", "ru", "ko", "zh"
        ]
        if v not in valid_languages:
            # Allow any 2-letter language code, but warn about common ones
            if len(v) != 2:
                raise ValueError(
                    "Speech language should be a 2-letter language code"
                )
        return v.lower()


class ConfigManager:
    """
    Configuration manager for the NescordBot application.

    Handles loading and validation of configuration from environment variables
    and .env files.
    """

    def __init__(self, env_file: Optional[str] = None):
        """
        Initialize configuration manager.

        Args:
            env_file: Path to .env file. If None, looks for .env in current
                directory.
        """
        self._config: Optional[BotConfig] = None
        self._env_file = env_file or ".env"
        self._load_env()

    def _load_env(self) -> None:
        """Load environment variables from .env file if it exists."""
        env_path = Path(self._env_file)
        if env_path.exists():
            load_dotenv(env_path)

    @property
    def config(self) -> BotConfig:
        """
        Get validated configuration.

        Returns:
            BotConfig: Validated configuration instance

        Raises:
            ValidationError: If required configuration is missing or
                invalid
        """
        if self._config is None:
            self._config = BotConfig(
                discord_token=os.getenv("DISCORD_TOKEN", ""),
                openai_api_key=os.getenv("OPENAI_API_KEY", ""),
                log_level=os.getenv("LOG_LEVEL", "INFO"),
                max_audio_size_mb=int(os.getenv("MAX_AUDIO_SIZE_MB", "25")),
                speech_language=os.getenv("SPEECH_LANGUAGE", "ja"),
                database_url=os.getenv(
                    "DATABASE_URL", "sqlite:///data/nescordbot.db"
                ),
                github_token=os.getenv("GITHUB_TOKEN"),
                github_repo=os.getenv("GITHUB_REPO"),
                obsidian_vault_path=os.getenv("OBSIDIAN_VAULT_PATH"),
            )
        return self._config

    def reload(self) -> None:
        """Reload configuration from environment variables."""
        self._config = None
        self._load_env()

    def get_discord_token(self) -> str:
        """Get Discord bot token."""
        return self.config.discord_token

    def get_openai_api_key(self) -> str:
        """Get OpenAI API key."""
        return self.config.openai_api_key

    def get_log_level(self) -> str:
        """Get logging level."""
        return self.config.log_level

    def get_max_audio_size_mb(self) -> int:
        """Get maximum audio file size in MB."""
        return self.config.max_audio_size_mb

    def get_speech_language(self) -> str:
        """Get speech recognition language."""
        return self.config.speech_language

    def get_database_url(self) -> str:
        """Get database URL."""
        return self.config.database_url

    def get_github_token(self) -> Optional[str]:
        """Get GitHub API token."""
        return self.config.github_token

    def get_github_repo(self) -> Optional[str]:
        """Get GitHub repository."""
        return self.config.github_repo

    def get_obsidian_vault_path(self) -> Optional[str]:
        """Get Obsidian vault path."""
        return self.config.obsidian_vault_path


# Global configuration manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """
    Get global configuration manager instance.

    Returns:
        ConfigManager: Global configuration manager instance
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_config() -> BotConfig:
    """
    Get validated bot configuration.

    Returns:
        BotConfig: Validated configuration instance
    """
    return get_config_manager().config
