"""
Tests for configuration management.
"""

import os
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from nescordbot.config import BotConfig, ConfigManager


class TestBotConfig:
    """Test BotConfig model validation."""

    def test_valid_config(self):
        """Test valid configuration."""
        config = BotConfig(
            discord_token="MTA1234567890123456.GH7890.abcdefghijklmnop123456789012345678901234",
            openai_api_key="sk-abcdef1234567890abcdef1234567890abcdef1234567890ab",
            log_level="INFO",
            max_audio_size_mb=25,
            speech_language="ja",
        )

        assert config.discord_token.startswith("MTA")
        assert config.openai_api_key.startswith("sk-")
        assert config.log_level == "INFO"
        assert config.max_audio_size_mb == 25
        assert config.speech_language == "ja"

    def test_missing_required_fields(self):
        """Test missing required fields."""
        with pytest.raises(ValidationError) as exc_info:
            BotConfig(discord_token="", openai_api_key="")

        errors = exc_info.value.errors()
        assert len(errors) >= 2

    def test_invalid_discord_token(self):
        """Test invalid Discord token format."""
        with pytest.raises(ValidationError) as exc_info:
            BotConfig(
                discord_token="invalid_token",
                openai_api_key="sk-abcdef1234567890abcdef1234567890abcdef1234567890ab",
            )

        errors = exc_info.value.errors()
        assert any("Invalid Discord token format" in str(error) for error in errors)

    def test_invalid_openai_api_key(self):
        """Test invalid OpenAI API key format."""
        with pytest.raises(ValidationError) as exc_info:
            BotConfig(
                discord_token="MTA1234567890123456.GH7890.abcdefghijklmnop123456789012345678901234",
                openai_api_key="invalid_key",
            )

        errors = exc_info.value.errors()
        assert any("Invalid OpenAI API key format" in str(error) for error in errors)

    def test_invalid_log_level(self):
        """Test invalid log level."""
        with pytest.raises(ValidationError) as exc_info:
            BotConfig(
                discord_token="MTA1234567890123456.GH7890.abcdefghijklmnop123456789012345678901234",
                openai_api_key="sk-abcdef1234567890abcdef1234567890abcdef1234567890ab",
                log_level="INVALID",
            )

        errors = exc_info.value.errors()
        assert any("Log level must be one of" in str(error) for error in errors)

    def test_invalid_max_audio_size(self):
        """Test invalid maximum audio size."""
        with pytest.raises(ValidationError) as exc_info:
            BotConfig(
                discord_token="MTA1234567890123456.GH7890.abcdefghijklmnop123456789012345678901234",
                openai_api_key="sk-abcdef1234567890abcdef1234567890abcdef1234567890ab",
                max_audio_size_mb=-1,
            )

        errors = exc_info.value.errors()
        assert any("Maximum audio size must be positive" in str(error) for error in errors)

    def test_log_level_case_insensitive(self):
        """Test log level case insensitivity."""
        config = BotConfig(
            discord_token="MTA1234567890123456.GH7890.abcdefghijklmnop123456789012345678901234",
            openai_api_key="sk-abcdef1234567890abcdef1234567890abcdef1234567890ab",
            log_level="debug",
        )

        assert config.log_level == "DEBUG"

    def test_default_values(self):
        """Test default values for optional fields."""
        config = BotConfig(
            discord_token="MTA1234567890123456.GH7890.abcdefghijklmnop123456789012345678901234",
            openai_api_key="sk-abcdef1234567890abcdef1234567890abcdef1234567890ab",
        )

        assert config.log_level == "INFO"
        assert config.max_audio_size_mb == 25
        assert config.speech_language == "ja"
        assert config.database_url == "sqlite:///data/nescordbot.db"
        assert config.github_token is None
        assert config.github_repo_owner is None
        assert config.github_repo_name is None
        assert config.obsidian_vault_path is None


class TestConfigManager:
    """Test ConfigManager functionality."""

    def setup_method(self):
        """Set up test environment."""
        # Clear environment variables
        test_vars = [
            "DISCORD_TOKEN",
            "OPENAI_API_KEY",
            "LOG_LEVEL",
            "MAX_AUDIO_SIZE_MB",
            "SPEECH_LANGUAGE",
            "DATABASE_URL",
            "GITHUB_TOKEN",
            "GITHUB_REPO_OWNER",
            "GITHUB_REPO_NAME",
            "OBSIDIAN_VAULT_PATH",
        ]
        for var in test_vars:
            if var in os.environ:
                del os.environ[var]

    def test_config_manager_with_env_vars(self):
        """Test ConfigManager with environment variables."""
        # Set environment variables
        os.environ[
            "DISCORD_TOKEN"
        ] = "MTA1234567890123456.GH7890.abcdefghijklmnop123456789012345678901234"
        os.environ["OPENAI_API_KEY"] = "sk-abcdef1234567890abcdef1234567890abcdef1234567890ab"
        os.environ["LOG_LEVEL"] = "DEBUG"

        manager = ConfigManager()
        config = manager.config

        assert config.discord_token == os.environ["DISCORD_TOKEN"]
        assert config.openai_api_key == os.environ["OPENAI_API_KEY"]
        assert config.log_level == "DEBUG"

    def test_config_manager_with_env_file(self):
        """Test ConfigManager with .env file."""
        # Create temporary .env file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write(
                "DISCORD_TOKEN=MTA1234567890123456.GH7890."
                "abcdefghijklmnop123456789012345678901234\n"
            )
            f.write("OPENAI_API_KEY=sk-abcdef1234567890abcdef1234567890abcdef1234567890ab\n")
            f.write("LOG_LEVEL=WARNING\n")
            env_file_path = f.name

        try:
            manager = ConfigManager(env_file=env_file_path)
            config = manager.config

            assert config.discord_token.startswith("MTA")
            assert config.openai_api_key.startswith("sk-")
            assert config.log_level == "WARNING"
        finally:
            Path(env_file_path).unlink()

    def test_config_manager_missing_required(self):
        """Test ConfigManager with missing required configuration."""
        # Create a temporary non-existent .env file path to avoid loading actual .env
        with tempfile.NamedTemporaryFile(suffix=".env", delete=True) as tmp_env:
            manager = ConfigManager(env_file=tmp_env.name + "_nonexistent")

            with pytest.raises(ValidationError):
                _ = manager.config

    def test_config_manager_reload(self):
        """Test ConfigManager reload functionality."""
        # Set initial environment variables
        os.environ[
            "DISCORD_TOKEN"
        ] = "MTA1234567890123456.GH7890.abcdefghijklmnop123456789012345678901234"
        os.environ["OPENAI_API_KEY"] = "sk-abcdef1234567890abcdef1234567890abcdef1234567890ab"
        os.environ["LOG_LEVEL"] = "INFO"

        manager = ConfigManager()
        config1 = manager.config
        assert config1.log_level == "INFO"

        # Change environment variable
        os.environ["LOG_LEVEL"] = "DEBUG"

        # Reload configuration
        manager.reload()
        config2 = manager.config
        assert config2.log_level == "DEBUG"

    def test_config_manager_convenience_methods(self):
        """Test ConfigManager convenience methods."""
        os.environ[
            "DISCORD_TOKEN"
        ] = "MTA1234567890123456.GH7890.abcdefghijklmnop123456789012345678901234"
        os.environ["OPENAI_API_KEY"] = "sk-abcdef1234567890abcdef1234567890abcdef1234567890ab"
        os.environ["LOG_LEVEL"] = "DEBUG"
        os.environ["MAX_AUDIO_SIZE_MB"] = "50"
        os.environ["SPEECH_LANGUAGE"] = "en"

        manager = ConfigManager()

        assert manager.get_discord_token() == os.environ["DISCORD_TOKEN"]
        assert manager.get_openai_api_key() == os.environ["OPENAI_API_KEY"]
        assert manager.get_log_level() == "DEBUG"
        assert manager.get_max_audio_size_mb() == 50
        assert manager.get_speech_language() == "en"
        assert manager.get_database_url() == "sqlite:///data/nescordbot.db"
        assert manager.get_github_token() is None
        assert manager.get_github_repo_owner() is None
        assert manager.get_github_repo_name() is None
        assert manager.get_obsidian_vault_path() is None

    def teardown_method(self):
        """Clean up test environment."""
        # Clear environment variables
        test_vars = [
            "DISCORD_TOKEN",
            "OPENAI_API_KEY",
            "LOG_LEVEL",
            "MAX_AUDIO_SIZE_MB",
            "SPEECH_LANGUAGE",
            "DATABASE_URL",
            "GITHUB_TOKEN",
            "GITHUB_REPO_OWNER",
            "GITHUB_REPO_NAME",
            "OBSIDIAN_VAULT_PATH",
        ]
        for var in test_vars:
            if var in os.environ:
                del os.environ[var]
