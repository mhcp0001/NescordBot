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
            discord_token=self.TEST_DISCORD_TOKEN,
            openai_api_key=self.TEST_OPENAI_API_KEY,
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
                openai_api_key=self.TEST_OPENAI_API_KEY,
            )

        errors = exc_info.value.errors()
        assert any("Invalid Discord token format" in str(error) for error in errors)

    def test_invalid_openai_api_key(self):
        """Test invalid OpenAI API key format."""
        with pytest.raises(ValidationError) as exc_info:
            BotConfig(
                discord_token=self.TEST_DISCORD_TOKEN,
                openai_api_key="invalid_key",
            )

        errors = exc_info.value.errors()
        assert any("Invalid OpenAI API key format" in str(error) for error in errors)

    def test_invalid_log_level(self):
        """Test invalid log level."""
        with pytest.raises(ValidationError) as exc_info:
            BotConfig(
                discord_token=self.TEST_DISCORD_TOKEN,
                openai_api_key=self.TEST_OPENAI_API_KEY,
                log_level="INVALID",
            )

        errors = exc_info.value.errors()
        assert any("Log level must be one of" in str(error) for error in errors)

    def test_invalid_max_audio_size(self):
        """Test invalid maximum audio size."""
        with pytest.raises(ValidationError) as exc_info:
            BotConfig(
                discord_token=self.TEST_DISCORD_TOKEN,
                openai_api_key=self.TEST_OPENAI_API_KEY,
                max_audio_size_mb=-1,
            )

        errors = exc_info.value.errors()
        assert any("Maximum audio size must be positive" in str(error) for error in errors)

    def test_log_level_case_insensitive(self):
        """Test log level case insensitivity."""
        config = BotConfig(
            discord_token=self.TEST_DISCORD_TOKEN,
            openai_api_key=self.TEST_OPENAI_API_KEY,
            log_level="debug",
        )

        assert config.log_level == "DEBUG"

    def test_default_values(self):
        """Test default values for optional fields."""
        config = BotConfig(
            discord_token=self.TEST_DISCORD_TOKEN,
            openai_api_key=self.TEST_OPENAI_API_KEY,
        )

        assert config.log_level == "INFO"
        assert config.max_audio_size_mb == 25
        assert config.speech_language == "ja"
        assert config.database_url == "sqlite:///data/nescordbot.db"
        assert config.github_token is None
        assert config.github_repo_owner is None
        assert config.github_repo_name is None
        assert config.obsidian_vault_path is None

    # Test constants for TestBotConfig
    TEST_DISCORD_TOKEN = "MTA1234567890123456.GH7890.abcdefghijklmnop123456789012345678901234"
    TEST_OPENAI_API_KEY = "sk-test1234567890abcdef1234567890abcdef1234567890ab"


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
            # Phase 4 variables
            "GEMINI_API_KEY",
            "GEMINI_MONTHLY_LIMIT",
            "GEMINI_REQUESTS_PER_MINUTE",
            "CHROMADB_PERSIST_DIRECTORY",
            "CHROMADB_COLLECTION_NAME",
            "CHROMADB_DISTANCE_METRIC",
            "CHROMADB_MAX_BATCH_SIZE",
            "PKM_ENABLED",
            "HYBRID_SEARCH_ENABLED",
            "HYBRID_SEARCH_ALPHA",
            "MAX_SEARCH_RESULTS",
            "EMBEDDING_DIMENSION",
            "AI_API_MODE",
            "ENABLE_API_FALLBACK",
            "API_TIMEOUT_SECONDS",
            "MAX_RETRY_ATTEMPTS",
        ]
        for var in test_vars:
            if var in os.environ:
                del os.environ[var]


class TestBotConfigPhase4:
    """Test Phase 4 specific configuration features."""

    # Test constants
    TEST_DISCORD_TOKEN = "MTA1234567890123456.GH7890.abcdefghijklmnop123456789012345678901234"
    TEST_OPENAI_API_KEY = "sk-test1234567890abcdef1234567890abcdef1234567890ab"
    TEST_GEMINI_API_KEY = "AIza-test1234567890abcdef1234567890abcdef12345678"

    def test_phase4_defaults(self):
        """Test Phase 4 default values."""
        config = BotConfig(
            discord_token=self.TEST_DISCORD_TOKEN,
            openai_api_key=self.TEST_OPENAI_API_KEY,
        )

        # Gemini API defaults
        assert config.gemini_api_key is None
        assert config.gemini_monthly_limit == 50000
        assert config.gemini_requests_per_minute == 15

        # ChromaDB defaults
        assert config.chromadb_persist_directory == "data/chromadb"
        assert config.chromadb_collection_name == "nescord_knowledge"
        assert config.chromadb_distance_metric == "cosine"
        assert config.chromadb_max_batch_size == 100

        # PKM features defaults
        assert config.pkm_enabled is False
        assert config.hybrid_search_enabled is True
        assert config.hybrid_search_alpha == 0.7
        assert config.max_search_results == 10
        assert config.embedding_dimension == 768

        # API migration mode defaults
        assert config.ai_api_mode == "openai"
        assert config.enable_api_fallback is True
        assert config.api_timeout_seconds == 30
        assert config.max_retry_attempts == 3

    def test_valid_gemini_api_key(self):
        """Test valid Gemini API key formats."""
        config = BotConfig(
            discord_token=self.TEST_DISCORD_TOKEN,
            openai_api_key=self.TEST_OPENAI_API_KEY,
            gemini_api_key=self.TEST_GEMINI_API_KEY,
        )
        assert config.gemini_api_key == self.TEST_GEMINI_API_KEY

    def test_invalid_gemini_api_key(self):
        """Test invalid Gemini API key formats."""
        with pytest.raises(ValidationError) as exc_info:
            BotConfig(
                discord_token=self.TEST_DISCORD_TOKEN,
                openai_api_key=self.TEST_OPENAI_API_KEY,
                gemini_api_key="invalid_key",
            )

        errors = exc_info.value.errors()
        assert any("Invalid Gemini API key format" in str(error) for error in errors)

    def test_chromadb_distance_metrics(self):
        """Test valid ChromaDB distance metrics."""
        valid_metrics = ["cosine", "l2", "ip"]

        for metric in valid_metrics:
            config = BotConfig(
                discord_token=self.TEST_DISCORD_TOKEN,
                openai_api_key=self.TEST_OPENAI_API_KEY,
                chromadb_distance_metric=metric,
            )
            assert config.chromadb_distance_metric == metric

    def test_invalid_chromadb_distance_metric(self):
        """Test invalid ChromaDB distance metric."""
        with pytest.raises(ValidationError) as exc_info:
            BotConfig(
                discord_token=self.TEST_DISCORD_TOKEN,
                openai_api_key=self.TEST_OPENAI_API_KEY,
                chromadb_distance_metric="invalid_metric",
            )

        errors = exc_info.value.errors()
        assert any("ChromaDB distance metric must be one of" in str(error) for error in errors)

    def test_hybrid_search_alpha_range(self):
        """Test hybrid search alpha parameter validation."""
        # Valid range
        config = BotConfig(
            discord_token=self.TEST_DISCORD_TOKEN,
            openai_api_key=self.TEST_OPENAI_API_KEY,
            hybrid_search_alpha=0.5,
        )
        assert config.hybrid_search_alpha == 0.5

        # Invalid range
        with pytest.raises(ValidationError) as exc_info:
            BotConfig(
                discord_token=self.TEST_DISCORD_TOKEN,
                openai_api_key=self.TEST_OPENAI_API_KEY,
                hybrid_search_alpha=1.5,
            )

        errors = exc_info.value.errors()
        assert any(
            "Hybrid search alpha must be between 0.0 and 1.0" in str(error) for error in errors
        )

    def test_ai_api_modes(self):
        """Test valid AI API modes."""
        # OpenAI mode (default)
        config_openai = BotConfig(
            discord_token=self.TEST_DISCORD_TOKEN,
            openai_api_key=self.TEST_OPENAI_API_KEY,
            ai_api_mode="openai",
        )
        assert config_openai.ai_api_mode == "openai"

        # Gemini mode (requires Gemini API key)
        config_gemini = BotConfig(
            discord_token=self.TEST_DISCORD_TOKEN,
            openai_api_key=self.TEST_OPENAI_API_KEY,
            gemini_api_key=self.TEST_GEMINI_API_KEY,
            ai_api_mode="gemini",
        )
        assert config_gemini.ai_api_mode == "gemini"

        # Hybrid mode (requires Gemini API key)
        config_hybrid = BotConfig(
            discord_token=self.TEST_DISCORD_TOKEN,
            openai_api_key=self.TEST_OPENAI_API_KEY,
            gemini_api_key=self.TEST_GEMINI_API_KEY,
            ai_api_mode="hybrid",
        )
        assert config_hybrid.ai_api_mode == "hybrid"

    def test_invalid_ai_api_mode(self):
        """Test invalid AI API mode."""
        with pytest.raises(ValidationError) as exc_info:
            BotConfig(
                discord_token=self.TEST_DISCORD_TOKEN,
                openai_api_key=self.TEST_OPENAI_API_KEY,
                ai_api_mode="invalid_mode",
            )

        errors = exc_info.value.errors()
        assert any("AI API mode must be one of" in str(error) for error in errors)

    def test_phase4_integration_validation_pkm_gemini_required(self):
        """Test PKM features require Gemini API when mode is gemini/hybrid."""
        with pytest.raises(ValidationError) as exc_info:
            BotConfig(
                discord_token=self.TEST_DISCORD_TOKEN,
                openai_api_key=self.TEST_OPENAI_API_KEY,
                pkm_enabled=True,
                ai_api_mode="gemini",
                # gemini_api_key missing
            )

        errors = exc_info.value.errors()
        assert any("Gemini API key is required" in str(error) for error in errors)

    def test_phase4_integration_validation_gemini_mode_requires_key(self):
        """Test Gemini API mode requires Gemini API key."""
        with pytest.raises(ValidationError) as exc_info:
            BotConfig(
                discord_token=self.TEST_DISCORD_TOKEN,
                openai_api_key=self.TEST_OPENAI_API_KEY,
                ai_api_mode="gemini",
                # gemini_api_key missing
            )

        errors = exc_info.value.errors()
        assert any("Gemini API key is required" in str(error) for error in errors)

    def test_phase4_integration_validation_hybrid_mode_requires_key(self):
        """Test hybrid API mode requires Gemini API key."""
        with pytest.raises(ValidationError) as exc_info:
            BotConfig(
                discord_token=self.TEST_DISCORD_TOKEN,
                openai_api_key=self.TEST_OPENAI_API_KEY,
                ai_api_mode="hybrid",
                # gemini_api_key missing
            )

        errors = exc_info.value.errors()
        assert any("Gemini API key is required" in str(error) for error in errors)

    def test_phase4_valid_configuration(self):
        """Test valid Phase 4 configuration."""
        config = BotConfig(
            discord_token=self.TEST_DISCORD_TOKEN,
            openai_api_key=self.TEST_OPENAI_API_KEY,
            gemini_api_key=self.TEST_GEMINI_API_KEY,
            pkm_enabled=True,
            ai_api_mode="hybrid",
            chromadb_persist_directory="data/test_chromadb",
            chromadb_collection_name="test_collection",
            hybrid_search_alpha=0.8,
            max_search_results=20,
        )

        assert config.pkm_enabled is True
        assert config.ai_api_mode == "hybrid"
        assert config.chromadb_persist_directory == "data/test_chromadb"
        assert config.chromadb_collection_name == "test_collection"
        assert config.hybrid_search_alpha == 0.8
        assert config.max_search_results == 20

    def teardown_method(self):
        """Clean up test environment."""
        # Clear environment variables
        test_vars = [
            "DISCORD_TOKEN",
            "OPENAI_API_KEY",
            "GEMINI_API_KEY",
            "PKM_ENABLED",
            "AI_API_MODE",
            "CHROMADB_PERSIST_DIRECTORY",
            "CHROMADB_COLLECTION_NAME",
            "HYBRID_SEARCH_ALPHA",
            "MAX_SEARCH_RESULTS",
        ]
        for var in test_vars:
            if var in os.environ:
                del os.environ[var]
